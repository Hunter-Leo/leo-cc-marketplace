#!/usr/bin/env python3
"""Sancai state machine (MVP).

State lives in .sancai/runs/<run>/L2-harness/run.json. All writes are atomic.
No daemon, no SQLite.

usage:
  sancai_state.py init --run 001-x --intent intent.json
  sancai_state.py status [--json]
  sancai_state.py transition --run executing
  sancai_state.py add-wo --id WO-001 --files "a.ts,b.ts" --reversible true
  sancai_state.py claim --wo WO-001 --by executor
  sancai_state.py release
  sancai_state.py wo-transition --wo WO-001 --to in_progress
  sancai_state.py abandon --reason "..."
  sancai_state.py event --type evidence --meta '{"k":"v"}'
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess

import sancai_paths as paths  # type: ignore

import re
import sys

import sancai_cards  # type: ignore
import sancai_graph  # type: ignore
import sancai_requirements as requirements  # type: ignore

os.umask(0o077)

RUN_TRANSITIONS = {
    "planning": {"executing", "abandoned"},
    "executing": {"reviewing", "abandoned"},
    "reviewing": {"accepted", "abandoned"},
    "accepted": set(),
    "abandoned": set(),
}
WO_TRANSITIONS = {
    "pending": {"in_progress", "blocked"},
    "in_progress": {"for_review", "blocked"},
    "for_review": {"verified", "changes_requested", "blocked"},
    "changes_requested": {"in_progress", "blocked"},
    "verified": {"merged"},
    "merged": set(),
    "blocked": {"in_progress"},
}

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ALLOWED_APPROVALS = {"confirmed", "approve execution", "approved", "yes"}
ALLOWED_ACCEPTS = {"confirmed", "accept", "accepted", "yes"}
BLOCKING_SEVERITIES = {"blocker", "critical"}


def validate_id(value, label):
    if not value or not ID_RE.match(value) or ".." in value:
        sys.exit(f"invalid {label}: {value!r}")


def default_session(value=""):
    """Resolve the host session id, including Claude Code's current env name."""
    return (
        value
        or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        or os.environ.get("CLAUDE_SESSION_ID", "")
    )


def resolve_run(root, args):
    run = args.run
    if not run:
        active = sancai_graph.read_active(root)
        if not active:
            sys.exit("no active Sancai run")
        run = active["run"]
    validate_id(run, "run")
    return run


def write_active(root, run, state):
    path = paths.active_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "run": run,
        "state": state,
        "updated_at": now(),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def clear_active(root, run):
    active = sancai_graph.read_active(root)
    if not active or active.get("run") != run:
        return
    for path in (paths.active_path(root), paths.status_last_path(root)):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def intent_snapshot(intent):
    clean = {k: v for k, v in intent.items() if k != "approval"}
    return "sha256:" + hashlib.sha256(canonical(clean).encode()).hexdigest()


def validate_intent(intent, root=None):
    if not isinstance(intent, dict):
        sys.exit("intent must be a JSON object")
    goal = intent.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        sys.exit("intent.goal must be a non-empty string")
    acceptance = intent.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        sys.exit("intent.acceptance must be a non-empty list")
    manual = 0
    for ac in acceptance:
        if not isinstance(ac, dict):
            sys.exit("each acceptance criterion must be an object")
        for key in ("id", "run", "expect"):
            if not ac.get(key):
                sys.exit(f"acceptance criterion missing {key}: {ac}")
        if ac.get("check") == "manual" or ac.get("type") == "manual":
            manual += 1
    if manual / len(acceptance) > 0.2 + 1e-9:
        sys.exit(f"manual acceptance criteria exceed 20% ({manual}/{len(acceptance)})")
    if "requirements" not in intent:
        return
    selected = intent.get("requirements")
    if not isinstance(selected, list) or not selected:
        sys.exit("intent.requirements must be a non-empty list when present")
    if len(set(selected)) != len(selected):
        sys.exit("intent.requirements must not contain duplicates")
    revision = intent.get("revision")
    if not isinstance(revision, int) or revision < 1:
        sys.exit("intent.revision must be an integer >= 1")
    project_requirements, _ = requirements.load_ledger(root or find_root())
    for req_id in selected:
        req = project_requirements.get("requirements", {}).get(req_id)
        if not req:
            sys.exit(f"unknown requirement: {req_id}")
        if req.get("status") != "accepted":
            sys.exit(f"requirement {req_id} is {req.get('status')}, not accepted")
        if not req.get("acceptance"):
            sys.exit(f"requirement {req_id} has no acceptance criteria")


def require_alignment(intent):
    """H1 must record intent alignment before the human starts the run."""
    alignment = intent.get("alignment") or {}
    status = alignment.get("status")
    if status not in ("aligned", "deferred"):
        sys.exit(
            "H1 requires intent alignment: run `sancai_intent.py assess --run <run>`, "
            "then `sancai_intent.py record --status aligned|deferred`"
        )


def validate_owned_files(root, files):
    out = []
    root_abs = os.path.abspath(root)
    for f in files:
        if not f:
            continue
        if os.path.isabs(f):
            sys.exit(f"owned file must be relative: {f}")
        norm = os.path.normpath(f)
        if norm == ".." or norm.startswith(".." + os.sep) or norm.startswith(".sancai"):
            sys.exit(f"owned file escapes the repo or targets .sancai: {f}")
        full = os.path.abspath(os.path.join(root_abs, norm))
        if full != root_abs and not full.startswith(root_abs + os.sep):
            sys.exit(f"owned file escapes the repo: {f}")
        out.append(norm)
    return out


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def find_root():
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".sancai")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.getcwd()
        cur = parent


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def run_dir(root, run):
    return paths.run_dir(root, run)


def load_run(root, run):
    path = paths.run_path(root, run)
    if not os.path.isfile(path):
        sys.exit(f"run not found: {path}")
    return path, load(path)


def append_event(root, run, event, meta=None, actor="harness"):
    path = paths.events_path(root, run)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {"ts": now(), "run": run, "event": event, "actor": actor, "meta": meta or {}}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cmd_init(args):
    root = find_root()
    validate_id(args.run, "run")
    active = sancai_graph.read_active(root)
    if active and active.get("run") != args.run and not args.takeover:
        try:
            _, previous = load_run(root, active.get("run"))
            if previous.get("state") not in ("accepted", "abandoned"):
                sys.exit(
                    f"active run is still open: {active.get('run')}; "
                    "use --takeover to replace it"
                )
        except SystemExit:
            pass
    src = os.path.abspath(args.intent)
    intent = load(src)
    validate_intent(intent, root)
    rd = paths.run_dir(root, args.run)
    run_path = paths.run_path(root, args.run)
    if os.path.isfile(run_path) and not args.force:
        sys.exit(f"run already exists: {args.run}; use --force to overwrite")
    paths.ensure_run_layout(root, args.run)
    save(paths.intent_path(root, args.run), intent)
    session_id = default_session(args.session_id)
    run = {
        "run": args.run,
        "state": "planning",
        "session_id": session_id,
        "executor_context_id": session_id,
        "intent_file": "L3-intent/intent.json",
        "intent_version": intent.get("version", 1),
        "work_orders": {},
        "claim": None,
        "created_at": now(),
        "updated_at": now(),
    }
    save(run_path, run)
    write_active(root, args.run, "planning")
    append_event(root, args.run, "run_initialized", {"intent": os.path.basename(src)})
    print(f"initialized {args.run} at {rd}")


def cmd_sign(args):
    root = find_root()
    run = resolve_run(root, args)
    _, data = load_run(root, run)
    if data["state"] != "planning":
        sys.exit(f"run must be planning to sign, currently {data['state']}")
    if args.message not in ALLOWED_APPROVALS:
        sys.exit(f"approval must be one of {sorted(ALLOWED_APPROVALS)}; got {args.message!r}")
    session_id = default_session(args.session_id or data.get("session_id", ""))
    if not session_id:
        sys.exit("approval requires a session id; pass --session-id or re-init with --session-id")
    validate_id(session_id, "session id")
    intent_path = paths.intent_path(root, run, data)
    intent = load(intent_path)
    validate_intent(intent, root)
    require_alignment(intent)
    snapshot = intent_snapshot(intent)
    expected = {
        "intent_sha": snapshot,
        "goal": intent.get("goal", ""),
        "acceptance_count": len(intent.get("acceptance", [])),
        "work_order_count": len(data.get("work_orders", {})),
    }
    if os.environ.get("SANCAI_REQUIRE_TTY_SIGN") == "1" and not sys.stdin.isatty():
        sys.exit(
            "SANCAI_REQUIRE_TTY_SIGN=1: the human must run sign in a terminal; "
            "the agent's shell is not an interactive human gate"
        )
    try:
        card = sancai_cards.consume_card(root, run, args.card_id, args.card_code, expected)
    except sancai_cards.CardError as exc:
        sys.exit(str(exc))
    latency = round(sancai_cards.card_age_seconds(card), 3)
    intent["approval"] = {
        "approved_in_session": session_id,
        "approved_at": now(),
        "user_message": args.message,
        "snapshot": snapshot,
        "run_id": run,
        "nonce": os.urandom(16).hex(),
        "card_id": card["card_id"],
        "latency_seconds": latency,
    }
    save(intent_path, intent)
    append_event(root, run, "intent_signed", {
        "snapshot": snapshot,
        "message": args.message,
        "card_id": card["card_id"],
        "latency_seconds": latency,
    })
    print(f"signed {run} at {snapshot}")


def cmd_record_intent(args):
    """Record an H1 approval collected through an interactive UI.

    H1 is a contract gate, not proof of an irreversible action. The agent may
    record the human's explicit interactive choice without a card; H2/H3 still
    require a rendered card and a human-run entrypoint.
    """
    root = find_root()
    run = resolve_run(root, args)
    _, data = load_run(root, run)
    if data["state"] != "planning":
        sys.exit(f"run must be planning to sign, currently {data['state']}")
    if args.message not in ALLOWED_APPROVALS:
        sys.exit(f"approval must be one of {sorted(ALLOWED_APPROVALS)}; got {args.message!r}")
    session_id = default_session(args.session_id or data.get("session_id", ""))
    if not session_id:
        sys.exit("approval requires a session id; pass --session-id")
    validate_id(session_id, "session id")
    intent_path = paths.intent_path(root, run, data)
    intent = load(intent_path)
    validate_intent(intent, root)
    require_alignment(intent)
    snapshot = intent_snapshot(intent)
    latency = 0.0
    card = sancai_cards.latest_card(root, run, "intent")
    if (
        card
        and not card.get("used_at")
        and card.get("payload", {}).get("intent_sha") == snapshot
    ):
        latency = round(sancai_cards.card_age_seconds(card), 3)
    intent["approval"] = {
        "approved_in_session": session_id,
        "approved_at": now(),
        "user_message": args.message,
        "snapshot": snapshot,
        "run_id": run,
        "nonce": os.urandom(16).hex(),
        "source": "interactive",
        "card_id": None,
        "latency_seconds": latency,
    }
    save(intent_path, intent)
    append_event(root, run, "intent_signed", {
        "snapshot": snapshot,
        "message": args.message,
        "source": "interactive",
        "latency_seconds": latency,
    })
    print(f"signed {run} at {snapshot} (interactive)")


def cmd_status(args):
    root = find_root()
    active = sancai_graph.read_active(root)
    run = args.run or (active or {}).get("run")
    if not run:
        if args.json:
            print(json.dumps({
                "schema_version": "sancai.status.v1",
                "state": "idle",
                "active": {"valid": False, "reason": "no active run"},
            }, ensure_ascii=False, indent=2))
        else:
            print("no active Sancai run")
        return
    validate_id(run, "run")
    status = sancai_graph.status_object(root, run)
    if status is None:
        sys.exit(f"run not found: {run}")
    terminal = status["state"] in ("accepted", "abandoned")
    if not args.run and terminal:
        if args.json:
            print(json.dumps({
                "schema_version": "sancai.status.v1",
                "state": "idle",
                "last_run": run,
                "last_state": status["state"],
                "active": {"valid": False, "reason": f"last run is {status['state']}"},
            }, ensure_ascii=False, indent=2))
        else:
            print(f"no active Sancai run (last: {run} {status['state']})")
        return
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return
    claim = status.get("claim") or {}
    print(f"run       : {status['run']}")
    print(f"state     : {status['state']}")
    print(f"stage     : {status['stage']}")
    print(f"layer     : {status['layer']}")
    print(f"progress  : {status['progress']}")
    print(f"claim     : {claim.get('wo', '-')} by {claim.get('by', '-')}")
    print(f"trigger   : {status['trigger'] or '-'}")
    print(f"next      : {status['next']['action']}")
    print(f"reason    : {status['next']['reason']}")
    print(f"check     : {status['next']['check']}")
    print(f"open esc  : {', '.join(status['open_escalations']) or '-'}")
    print(f"active    : {status['active']}")


def cmd_activate(args):
    root = find_root()
    validate_id(args.run, "run")
    _, data = load_run(root, args.run)
    write_active(root, args.run, data["state"])
    print(f"active run: {args.run}")


def _dirty_files(root):
    """Return uncommitted tracked changes; empty when the tree is clean.

    Untracked files are ignored: they never appear in `git diff HEAD`, so they
    cannot pollute G0 evidence. The check targets tracked modifications that
    would leak unrelated work into the run branch.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", root, "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True,
        )
    except OSError:
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def cmd_transition(args):
    root = find_root()
    run = resolve_run(root, args)
    path, data = load_run(root, run)
    cur, nxt = data["state"], args.to
    if nxt == "accepted":
        sys.exit("use accept to accept a run; transition cannot set accepted")
    if nxt == "abandoned":
        sys.exit("use abandon to abandon a run; transition cannot set abandoned")
    if nxt not in RUN_TRANSITIONS.get(cur, set()):
        sys.exit(f"illegal run transition: {cur} -> {nxt}")
    if nxt == "executing":
        intent_path = paths.intent_path(root, run, data)
        intent = load(intent_path)
        validate_intent(intent, root)
        approval = intent.get("approval") or {}
        if not approval:
            sys.exit("intent is not signed; run sign first")
        if approval.get("run_id") != run:
            sys.exit("approval run_id does not match the run")
        if approval.get("user_message") not in ALLOWED_APPROVALS:
            sys.exit("approval user_message is not an accepted confirmation phrase")
        if approval.get("snapshot") != intent_snapshot(intent):
            sys.exit("intent changed after approval; re-sign before executing")
        dirty = _dirty_files(root)
        if dirty:
            sys.exit(
                "working tree has uncommitted tracked changes; commit or stash "
                "before starting the run branch: " + ", ".join(dirty[:5])
            )
    if nxt == "reviewing":
        wos = data.get("work_orders", {})
        if not wos:
            sys.exit("cannot review a run with no work orders")
        bad = [wid for wid, wo in wos.items() if wo.get("state") not in ("verified", "merged")]
        if bad:
            sys.exit(f"work orders not verified: {bad}")
        for wid in wos:
            gate_path = os.path.join(paths.gates_dir(root, run), f"{wid}.json")
            if not os.path.isfile(gate_path):
                sys.exit(f"gate result missing for {wid}")
            gate = load(gate_path)
            if gate.get("result") != "verified":
                sys.exit(f"gate is not verified for {wid}: {gate.get('result')}")
    data["state"] = nxt
    data["updated_at"] = now()
    save(path, data)
    active = sancai_graph.read_active(root)
    if active and active.get("run") == run:
        write_active(root, run, nxt)
    append_event(root, run, "run_transition", {"from": cur, "to": nxt})
    print(f"{run}: {cur} -> {nxt}")


def cmd_add_wo(args):
    root = find_root()
    run = resolve_run(root, args)
    validate_id(args.id, "work order")
    path, data = load_run(root, run)
    if args.id in data["work_orders"]:
        sys.exit(f"work order already exists: {args.id}")
    intent = load(paths.intent_path(root, run, data))
    selected = intent.get("requirements") or []
    req = args.req
    if selected:
        if not req:
            sys.exit(
                "work order must bind an accepted requirement with --req; "
                f"selected: {', '.join(selected)}"
            )
        if req not in selected:
            sys.exit(f"requirement {req} is not selected in the intent")
    elif req:
        sys.exit("run intent has no selected requirements; select requirements first")
    new_files = validate_owned_files(
        root, [f.strip() for f in args.files.split(",") if f.strip()]
    )
    for wid, wo in data["work_orders"].items():
        overlap = set(new_files) & set(wo.get("owned_files", []))
        if overlap:
            sys.exit(f"owned_files overlap with {wid}: {sorted(overlap)}; split or serialize")
    data["work_orders"][args.id] = {
        "id": args.id,
        "state": "pending",
        "req": req,
        "owned_files": new_files,
        "reversible": args.reversible.lower() == "true",
        "blast_radius": args.blast_radius,
        "created_at": now(),
    }
    data["updated_at"] = now()
    save(path, data)
    append_event(root, run, "work_order_added", {
        "id": args.id,
        "req": req,
        "reversible": data["work_orders"][args.id]["reversible"],
    })
    print(f"added {args.id}" + (f" for {req}" if req else ""))


def cmd_claim(args):
    root = find_root()
    run = resolve_run(root, args)
    validate_id(args.wo, "work order")
    path, data = load_run(root, run)
    if data.get("claim"):
        sys.exit(f"claim already held: {data['claim']}")
    wo = data["work_orders"].get(args.wo)
    if not wo:
        sys.exit(f"work order not found: {args.wo}")
    if wo["state"] not in ("pending", "changes_requested", "blocked"):
        sys.exit(f"work order {args.wo} is {wo['state']}, not claimable")
    data["claim"] = {
        "wo": args.wo,
        "by": args.by,
        "session_id": args.session_id or "",
        "context_id": args.context_id or args.session_id or data.get("session_id", ""),
        "ts": now(),
    }
    data["updated_at"] = now()
    save(path, data)
    append_event(root, run, "claimed", {"wo": args.wo, "by": args.by})
    print(f"claimed {args.wo} by {args.by}")


def cmd_release(args):
    root = find_root()
    run = resolve_run(root, args)
    path, data = load_run(root, run)
    if not data.get("claim"):
        print("no claim")
        return
    wo = data["claim"]["wo"]
    data["claim"] = None
    data["updated_at"] = now()
    save(path, data)
    append_event(root, run, "released", {"wo": wo})
    print(f"released {wo}")


def cmd_wo_transition(args):
    root = find_root()
    run = resolve_run(root, args)
    validate_id(args.wo, "work order")
    path, data = load_run(root, run)
    wo = data["work_orders"].get(args.wo)
    if not wo:
        sys.exit(f"work order not found: {args.wo}")
    cur, nxt = wo["state"], args.to
    if nxt == "verified":
        sys.exit("verified is set by sancai_gate.py --apply; do not transition directly")
    if nxt not in WO_TRANSITIONS.get(cur, set()):
        sys.exit(f"illegal work order transition: {cur} -> {nxt}")
    if nxt in ("in_progress", "for_review"):
        claim = data.get("claim")
        if not claim or claim.get("wo") != args.wo:
            sys.exit(f"{args.wo} is not claimed; claim it before {nxt}")
    wo["state"] = nxt
    if nxt in ("merged", "blocked"):
        data["claim"] = None
    data["updated_at"] = now()
    save(path, data)
    append_event(root, run, "wo_transition", {"wo": args.wo, "from": cur, "to": nxt})
    print(f"{args.wo}: {cur} -> {nxt}")


def cmd_abandon(args):
    root = find_root()
    run = resolve_run(root, args)
    if not args.reason.strip():
        sys.exit("abandon requires a non-empty reason")
    path, data = load_run(root, run)
    if data["state"] == "accepted":
        sys.exit("cannot abandon an accepted run")
    data["state"] = "abandoned"
    data["abandon"] = {"reason": args.reason, "ts": now()}
    data["claim"] = None
    data["updated_at"] = now()
    save(path, data)
    clear_active(root, run)
    append_event(root, run, "abandoned", {"reason": args.reason})
    print(f"abandoned {run}: {args.reason}")


def cmd_event(args):
    root = find_root()
    run = resolve_run(root, args)
    try:
        meta = json.loads(args.meta) if args.meta else {}
    except json.JSONDecodeError:
        meta = {"raw": args.meta}
    append_event(root, run, args.type, meta)
    print("event recorded")


def cmd_progress(args):
    root = find_root()
    run = resolve_run(root, args)
    rd = run_dir(root, run)
    os.makedirs(rd, exist_ok=True)
    symbol = {"done": "✅", "doing": "▶", "blocked": "⏸", "todo": " "}.get(args.status, " ")
    prefix = f"[{args.wo}] " if args.wo else ""
    line = f"- {symbol} {prefix}{args.item}\n"
    with open(paths.progress_path(root, run), "a", encoding="utf-8") as f:
        f.write(line)
    append_event(root, run, "progress", {"wo": args.wo, "status": args.status, "item": args.item})
    print(line.rstrip())


def _all_findings(root, run):
    """Mirror sancai_card._all_findings: collect findings from verdicts/*.json."""
    findings = []
    vdir = paths.verdicts_dir(root, run)
    if not os.path.isdir(vdir):
        return findings
    for name in sorted(os.listdir(vdir)):
        if not name.endswith(".json"):
            continue
        try:
            verdict = load(os.path.join(vdir, name))
        except (OSError, json.JSONDecodeError):
            continue
        items = verdict.get("findings") if isinstance(verdict, dict) else None
        if isinstance(items, list):
            findings.extend(items)
    return findings


def accept_payload(root, run, data):
    """Mirror sancai_card._accept_payload for card binding."""
    wos = {wid: wo.get("state") for wid, wo in data.get("work_orders", {}).items()}
    gate_results = {}
    for wid in wos:
        gate_path = os.path.join(paths.gates_dir(root, run), f"{wid}.json")
        if os.path.isfile(gate_path):
            gate_results[wid] = load(gate_path).get("result")
    findings = _all_findings(root, run)
    return {
        "run": run,
        "state": data.get("state") or "reviewing",
        "wos": wos,
        "gate_results": gate_results,
        "findings_hash": sancai_cards.findings_hash(findings),
        "findings_count": len(findings),
    }


def finding_file(finding):
    """Normalize a finding file to a repo-relative owned file, or None."""
    raw = finding.get("file") if isinstance(finding, dict) else None
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw or os.path.isabs(raw):
        return None
    if re.match(r"^.+:\d+$", raw):
        raw = raw.rsplit(":", 1)[0]
    norm = os.path.normpath(raw)
    if norm in (".", "..") or norm.startswith(".." + os.sep) or norm.startswith(".sancai"):
        return None
    return norm


def severity_of(finding):
    return finding.get("severity") if isinstance(finding, dict) else None


def cmd_accept(args):
    root = find_root()
    run = resolve_run(root, args)
    if args.message.strip() not in ALLOWED_ACCEPTS:
        sys.exit(f"acceptance must be one of {sorted(ALLOWED_ACCEPTS)}; got {args.message!r}")
    session_id = args.session_id or ""
    if not session_id:
        sys.exit("accept requires a session id; pass --session-id")
    validate_id(session_id, "session id")
    path, data = load_run(root, run)
    intent = load(paths.intent_path(root, run, data))
    selected = intent.get("requirements") or []
    wos = data.get("work_orders", {})
    coverage = {}
    for req_id in selected:
        covered = [
            wid for wid, wo in wos.items()
            if wo.get("req") == req_id and wo.get("state") in ("verified", "merged")
        ]
        if not covered:
            sys.exit(f"requirement has no verified work order: {req_id}")
        coverage[req_id] = covered
    expected = accept_payload(root, run, data)
    try:
        card = sancai_cards.consume_card(root, run, args.card_id, args.card_code, expected)
    except sancai_cards.CardError as exc:
        sys.exit(str(exc))
    latency = round(sancai_cards.card_age_seconds(card), 3)
    if data["state"] != "reviewing":
        sys.exit(f"run must be reviewing, currently {data['state']}")
    wos = data.get("work_orders", {})
    if not wos or any(wo.get("state") not in ("verified", "merged") for wo in wos.values()):
        sys.exit("not all work orders are verified")
    rd = run_dir(root, run)
    esc_dir = paths.escalations_dir(root, run)
    if os.path.isdir(esc_dir):
        for name in os.listdir(esc_dir):
            if not name.endswith(".json"):
                continue
            esc = load(os.path.join(esc_dir, name))
            if esc.get("status") == "open":
                sys.exit(f"cannot accept with open escalation: {esc.get('id', name)}")
    for wid in wos:
        gate_path = os.path.join(paths.gates_dir(root, run), f"{wid}.json")
        if not os.path.isfile(gate_path):
            sys.exit(f"gate result missing for {wid}")
        gate = load(gate_path)
        if gate.get("result") != "verified":
            sys.exit(f"gate is not verified for {wid}: {gate.get('result')}")
        verdict_path = os.path.join(paths.verdicts_dir(root, run), f"{wid}.json")
        if not os.path.isfile(verdict_path):
            sys.exit(f"verdict missing for {wid}")
        verdict = load(verdict_path)
        blockers = [
            f for f in verdict.get("findings", [])
            if f.get("severity") in BLOCKING_SEVERITIES
        ]
        if blockers:
            sys.exit(f"blocking findings remain for {wid}: {blockers}")

    findings = _all_findings(root, run)
    blocking = [f for f in findings if severity_of(f) in BLOCKING_SEVERITIES]
    if blocking:
        sys.exit(f"cannot accept with blocking findings: {blocking}")
    if findings and not args.ack_findings:
        sys.exit("findings require --ack-findings")
    majors = [f for f in findings if severity_of(f) == "major"]
    dispositions = args.disposition or []
    if majors and len(dispositions) != 1:
        sys.exit(
            "major findings require exactly one --disposition "
            "defer:<WO-ID> or waive:<reason>"
        )
    if dispositions and not majors:
        sys.exit("--disposition is only valid when major findings exist")

    disposition_record = None
    deferred_todo = ""
    if majors:
        raw = dispositions[0].strip()
        if raw.startswith("defer:"):
            wo_id = raw[len("defer:"):].strip()
            validate_id(wo_id, "follow-up work order")
            if wo_id in wos:
                sys.exit(f"follow-up work order already exists: {wo_id}")
            finding_text = (
                majors[0].get("summary")
                or majors[0].get("message")
                or "Resolve deferred finding"
            )
            title = f"Resolve deferred finding {wo_id}: {finding_text}"
            item = requirements.capture_todo(
                root,
                title,
                type_="finding",
                priority="P1",
                source=f"run:{run}/WO:{wo_id}",
                relation="related",
                notes="; ".join(
                    f"{finding_file(f) or 'unknown'}: {f.get('summary') or f}"
                    for f in majors
                ),
            )
            deferred_todo = item["id"]
            disposition_record = {
                "raw": raw,
                "kind": "defer",
                "wo": wo_id,
                "todo": item["id"],
                "title": title,
            }
        elif raw.startswith("waive:"):
            reason = raw[len("waive:"):].strip()
            if not reason:
                sys.exit("waive requires a non-empty reason")
            disposition_record = {"raw": raw, "kind": "waive", "reason": reason}
        else:
            sys.exit(
                "unknown disposition; use defer:<WO-ID> or waive:<non-empty reason>"
            )

    dispositions_record = [disposition_record] if disposition_record else []
    captured_todos = [item["id"] for item in requirements.todos_for_run(root, run)]
    data["state"] = "accepted"
    data["outcome"] = {
        "accepted_at": now(),
        "message": args.message,
        "accepted_in_session": session_id,
        "card_id": card["card_id"],
        "latency_seconds": latency,
        "requirements": coverage,
        "captured_todos": captured_todos,
    }
    data["acceptance"] = {
        "findings": {
            "hash": expected["findings_hash"],
            "count": len(findings),
            "acknowledged": True,
            "dispositions": dispositions_record,
        },
        "requirements": coverage,
        "captured_todos": captured_todos,
    }
    data["updated_at"] = now()
    save(path, data)
    clear_active(root, run)
    append_event(root, run, "findings_acknowledged", {
        "hash": expected["findings_hash"],
        "count": len(findings),
        "dispositions": dispositions_record,
        "follow_up_wo": "",
        "deferred_todo": deferred_todo,
    })
    append_event(root, run, "outcome_accepted", {
        "message": args.message,
        "latency_seconds": latency,
        "requirements": coverage,
        "captured_todos": captured_todos,
    })
    print(f"outcome accepted: {run}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--run", required=True); p.add_argument("--intent", required=True); p.add_argument("--session-id", default=""); p.add_argument("--force", action="store_true"); p.add_argument("--takeover", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("sign"); p.add_argument("--run"); p.add_argument("--message", required=True); p.add_argument("--session-id", default=""); p.add_argument("--card-id", required=True); p.add_argument("--card-code", required=True)
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("record-intent"); p.add_argument("--run"); p.add_argument("--message", required=True); p.add_argument("--session-id", default="")
    p.set_defaults(func=cmd_record_intent)

    p = sub.add_parser("activate"); p.add_argument("--run", required=True); p.set_defaults(func=cmd_activate)

    p = sub.add_parser("status"); p.add_argument("--run"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_status)

    p = sub.add_parser("transition"); p.add_argument("--run"); p.add_argument("--to", required=True); p.set_defaults(func=cmd_transition)

    p = sub.add_parser("add-wo"); p.add_argument("--run"); p.add_argument("--id", required=True); p.add_argument("--files", required=True); p.add_argument("--req"); p.add_argument("--reversible", default="true"); p.add_argument("--blast-radius", default="low"); p.set_defaults(func=cmd_add_wo)

    p = sub.add_parser("claim"); p.add_argument("--run"); p.add_argument("--wo", required=True); p.add_argument("--by", default="executor"); p.add_argument("--session-id", default=""); p.add_argument("--context-id", default=""); p.set_defaults(func=cmd_claim)

    p = sub.add_parser("release"); p.add_argument("--run"); p.set_defaults(func=cmd_release)

    p = sub.add_parser("wo-transition"); p.add_argument("--run"); p.add_argument("--wo", required=True); p.add_argument("--to", required=True); p.set_defaults(func=cmd_wo_transition)

    p = sub.add_parser("abandon"); p.add_argument("--run"); p.add_argument("--reason", required=True); p.set_defaults(func=cmd_abandon)

    p = sub.add_parser("event"); p.add_argument("--run"); p.add_argument("--type", required=True); p.add_argument("--meta", default="{}"); p.set_defaults(func=cmd_event)

    p = sub.add_parser("progress"); p.add_argument("--run"); p.add_argument("--wo"); p.add_argument("--item", required=True); p.add_argument("--status", choices=["todo", "doing", "done", "blocked"], default="doing"); p.set_defaults(func=cmd_progress)

    p = sub.add_parser("accept"); p.add_argument("--run"); p.add_argument("--message", required=True); p.add_argument("--session-id", required=True); p.add_argument("--card-id", required=True); p.add_argument("--card-code", required=True); p.add_argument("--ack-findings", action="store_true"); p.add_argument("--disposition", action="append", default=[]); p.set_defaults(func=cmd_accept)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Derive and query the Sancai process graph.

The graph is a read model, not a second source of truth:
  - flow record : .sancai/runs/<run>/L2-harness/run.json      (conceptually flow.json)
  - history     : .sancai/runs/<run>/audit/events.jsonl  (conceptually history[])
  - read model  : .sancai/runs/<run>/audit/graph.json

usage:
  sancai_graph.py rebuild --run R
  sancai_graph.py position --run R [--json]
  sancai_graph.py next --run R [--json]
  sancai_graph.py attempts --run R --wo WO-001 [--json]
  sancai_graph.py open-escalations --run R [--json]
  sancai_graph.py metrics --run R [--json]
  sancai_graph.py timeline --run R [--last 20] [--json]
  sancai_graph.py show --run R
"""
import argparse
import datetime
import json
import os

import sancai_paths as paths  # type: ignore
import sancai_control as control  # type: ignore  # noqa: E402
import sancai_requirements as requirements  # type: ignore

import statistics
import sys

os.umask(0o077)


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


TERMINAL_STATES = {"accepted", "abandoned"}


def read_active(root):
    """Read .sancai/active, accepting both the legacy text form and JSON."""
    path = paths.active_path(root)
    if not os.path.isfile(path):
        return None
    try:
        raw = open(path, encoding="utf-8").read().strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("run"):
            return data
    except json.JSONDecodeError:
        pass
    return {"run": raw, "state": None}


def active_run(root):
    active = read_active(root)
    if not active:
        sys.exit("no active Sancai run")
    return active["run"]


def load_run(root, run):
    path = paths.run_path(root, run)
    if not os.path.isfile(path):
        sys.exit(f"run not found: {path}")
    return path, load(path)


def load_events(root, run):
    path = paths.events_path(root, run)
    if not os.path.isfile(path):
        return []
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def read_json_dir(path):
    if not os.path.isdir(path):
        return []
    out = []
    for name in sorted(os.listdir(path)):
        if not name.endswith(".json"):
            continue
        try:
            out.append(load(os.path.join(path, name)))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def rel(root, path):
    return os.path.relpath(path, root)


def _attempt_status(wo_state):
    return {
        "pending": "open",
        "in_progress": "running",
        "for_review": "submitted",
        "changes_requested": "rejected",
        "verified": "verified",
        "merged": "verified",
        "blocked": "blocked",
    }.get(wo_state, "open")


def build_graph(root, run):
    run_path, run_data = load_run(root, run)
    rd = run_dir(root, run)
    events = load_events(root, run)

    nodes = []
    edges = []

    nodes.append({
        "id": run,
        "type": "run",
        "state": run_data.get("state"),
        "claim": run_data.get("claim"),
        "session_id": run_data.get("session_id"),
        "created_at": run_data.get("created_at"),
        "updated_at": run_data.get("updated_at"),
    })

    work_orders = run_data.get("work_orders", {})
    for wid, wo in work_orders.items():
        nodes.append({
            "id": wid,
            "type": "work_order",
            "state": wo.get("state"),
            "req": wo.get("req"),
            "reversible": wo.get("reversible"),
            "blast_radius": wo.get("blast_radius"),
            "owned_files": wo.get("owned_files", []),
            "created_at": wo.get("created_at"),
        })
        edges.append({"from": run, "to": wid, "type": "contains"})

    # Attempts: one per claim / attempt_started event, in event order.
    attempts_by_wo = {}
    attempt_no = 0
    for ev in events:
        if ev.get("event") not in ("claimed", "attempt_started"):
            continue
        meta = ev.get("meta") or {}
        wo = meta.get("wo")
        if not wo:
            continue
        attempt_no += 1
        aid = f"ATT-{attempt_no:03d}"
        prev = attempts_by_wo.get(wo)
        nodes.append({
            "id": aid,
            "type": "attempt",
            "wo": wo,
            "actor": ev.get("actor"),
            "started_at": ev.get("ts"),
            "status": "open",
        })
        edges.append({"from": wo, "to": aid, "type": "has_attempt"})
        if prev:
            edges.append({"from": aid, "to": prev, "type": "supersedes"})
        attempts_by_wo[wo] = aid

    gate_events = [e for e in events if e.get("event") == "gate_result"]
    rejections = sum(
        1 for e in gate_events
        if (e.get("meta") or {}).get("result") == "changes_requested"
    )

    # Gates, evidence, verdicts.
    for wid, wo in work_orders.items():
        gate_path = os.path.join(paths.gates_dir(root, run), f"{wid}.json")
        if os.path.isfile(gate_path):
            gate = load(gate_path)
            gid = f"GATE-{wid}"
            nodes.append({
                "id": gid,
                "type": "gate",
                "wo": wid,
                "result": gate.get("result"),
                "reasons": gate.get("reasons", []),
                "ts": gate.get("ts"),
            })
            edges.append({"from": wid, "to": gid, "type": "has_gate"})
            edges.append({"from": gid, "to": wid, "type": "checks"})

        ev_path = os.path.join(paths.evidence_dir(root, run), f"{wid}.json")
        if os.path.isfile(ev_path):
            evd = load(ev_path)
            eid = f"EVID-{wid}"
            nodes.append({
                "id": eid,
                "type": "evidence",
                "wo": wid,
                "success": evd.get("success"),
                "ac_passed": evd.get("ac_passed"),
                "ac_total": evd.get("ac_total"),
                "diff_sha": evd.get("diff_sha"),
                "collected_at": evd.get("collected_at"),
            })
            edges.append({"from": wid, "to": eid, "type": "has_evidence"})

        v_path = os.path.join(paths.verdicts_dir(root, run), f"{wid}.json")
        if os.path.isfile(v_path):
            verdict = load(v_path)
            vid = f"VERD-{wid}"
            nodes.append({
                "id": vid,
                "type": "verdict",
                "wo": wid,
                "verdict": verdict.get("verdict"),
                "session_id": verdict.get("session_id"),
                "findings": len(verdict.get("findings", [])),
            })
            edges.append({"from": vid, "to": wid, "type": "verifies"})

    # Escalations and decisions.
    escalations = read_json_dir(paths.escalations_dir(root, run))
    for esc in escalations:
        eid = esc.get("id")
        if not eid:
            continue
        nodes.append({
            "id": eid,
            "type": "escalation",
            "wo": esc.get("wo"),
            "esc_type": esc.get("type"),
            "status": esc.get("status"),
            "blocking": esc.get("blocking"),
            "what_i_tried": esc.get("what_i_tried", []),
            "evidence": esc.get("evidence", []),
            "options": esc.get("options", []),
            "recommendation": esc.get("recommendation"),
            "confidence": esc.get("confidence"),
            "created_at": esc.get("created_at"),
        })
        if esc.get("wo"):
            edges.append({"from": esc["wo"], "to": eid, "type": "raised_from"})
        if esc.get("status") in ("approved", "rejected"):
            did = f"DEC-{eid}"
            nodes.append({
                "id": did,
                "type": "decision",
                "escalation": eid,
                "wo": esc.get("wo"),
                "choice": esc.get("status"),
                "message": esc.get("approved_message") or esc.get("rejected_message"),
                "ts": esc.get("approved_at") or esc.get("rejected_at"),
            })
            edges.append({"from": did, "to": eid, "type": "resolves"})
            if esc.get("wo"):
                edges.append({"from": did, "to": esc["wo"], "type": "returns_to"})

    # Capability tokens (audit only).
    token_dir = paths.tokens_dir(root, run)
    tokens = 0
    if os.path.isdir(token_dir):
        for name in sorted(os.listdir(token_dir)):
            if not name.endswith(".json"):
                continue
            try:
                data = load(os.path.join(token_dir, name))
            except (OSError, json.JSONDecodeError):
                continue
            payload = data.get("payload", {})
            tokens += 1
            nodes.append({
                "id": "CAP-" + str(payload.get("nonce", name))[:8],
                "type": "capability",
                "action": payload.get("action"),
                "issued_at": payload.get("issued_at"),
                "expires_at": payload.get("expires_at"),
            })

    # Latest attempt reflects the work order state.
    for wid, wo in work_orders.items():
        aid = attempts_by_wo.get(wid)
        if not aid:
            continue
        for node in nodes:
            if node["id"] == aid and node.get("type") == "attempt":
                node["status"] = _attempt_status(wo.get("state"))

    # Fallback attempt for work orders that predate claim events.
    for wid, wo in work_orders.items():
        if wid in attempts_by_wo:
            continue
        aid = f"ATT-{wid}"
        nodes.append({
            "id": aid,
            "type": "attempt",
            "wo": wid,
            "status": _attempt_status(wo.get("state")),
        })
        edges.append({"from": wid, "to": aid, "type": "has_attempt"})
        attempts_by_wo[wid] = aid

    attempt_nodes = [n for n in nodes if n.get("type") == "attempt"]
    esc_nodes = [n for n in nodes if n.get("type") == "escalation"]
    verified = sum(1 for wo in work_orders.values() if wo.get("state") in ("verified", "merged"))
    blocked = sum(1 for wo in work_orders.values() if wo.get("state") == "blocked")
    attempts = len(attempt_nodes)
    wo_total = len(work_orders)

    human_minutes = 0.0
    latencies = []
    decision_events = {"intent_signed", "decision_recorded", "outcome_accepted"}
    for ev in events:
        meta = ev.get("meta") or {}
        if ev.get("event") == "human_input":
            try:
                human_minutes += float(meta.get("minutes", 0))
            except (TypeError, ValueError):
                pass
        if ev.get("event") in decision_events:
            try:
                latency = float(meta.get("latency_seconds", 0))
            except (TypeError, ValueError):
                latency = 0.0
            if latency > 0:
                latencies.append(latency)
                human_minutes += latency / 60.0
    median_latency = round(statistics.median(latencies), 1) if latencies else 0.0
    fatigue_suspected = len(latencies) >= 5 and median_latency < 2.0

    metrics = {
        "wo_total": wo_total,
        "wo_verified": verified,
        "wo_blocked": blocked,
        "attempts": attempts,
        "rework": max(0, attempts - wo_total),
        "rejections": rejections if rejections else max(0, attempts - wo_total),
        "escalations": len(esc_nodes),
        "approvals": sum(1 for e in esc_nodes if e.get("status") == "approved"),
        "open_escalations": sum(1 for e in esc_nodes if e.get("status") == "open"),
        "tokens": tokens,
        "human_minutes": round(human_minutes, 1),
        "decisions": len(latencies),
        "median_latency_seconds": median_latency,
        "fatigue_suspected": fatigue_suspected,
    }

    # Intent summary (for the intent card).
    intent_path = paths.intent_path(root, run, run_data)
    intent = load(intent_path) if os.path.isfile(intent_path) else {}
    ctl = control.control_of(run_data)
    budget = control.effective_budget(intent, ctl)
    metrics.update({
        "control_status": ctl.get("status"),
        "control_reason": ctl.get("reason"),
        "attempts_budget": budget["max_attempts"],
        "attempts_remaining": max(
            0, budget["max_attempts"] - ctl.get("attempts", 0)
        ),
        "human_rounds_budget": budget["max_human_rounds"],
        "human_rounds_used": ctl.get("human_rounds", 0),
        "no_progress_streak": ctl.get("no_progress_streak", 0),
    })
    intent_summary = {
        "goal": intent.get("goal", ""),
        "non_goals": intent.get("non_goals", []),
        "acceptance": len(intent.get("acceptance", [])),
        "acceptance_checks": [
            {
                "id": ac.get("id"),
                "run": ac.get("run"),
                "expect": ac.get("expect"),
            }
            for ac in intent.get("acceptance", [])
            if isinstance(ac, dict)
        ],
        "manual_ac_ratio": intent.get("manual_ac_ratio"),
        "work_orders": len(work_orders),
        "requirements": intent.get("requirements", []),
        "revision": intent.get("revision"),
        "science": intent.get("science") or {},
    }
    captured_todos = [
        {
            "id": item["id"],
            "title": item.get("title"),
            "status": item.get("status"),
            "relation": item.get("relation"),
        }
        for item in requirements.todos_for_run(root, run)
    ]

    graph = {
        "run": run,
        "generated_at": now(),
        "source": {
            "run_json": rel(root, run_path),
            "events_jsonl": rel(root, paths.events_path(root, run)),
            "events": len(events),
        },
        "intent": intent_summary,
        "captured_todos": captured_todos,
        "nodes": nodes,
        "edges": edges,
        "metrics": metrics,
    }
    save(paths.graph_path(root, run), graph)
    return graph


def find_node(graph, node_type, **where):
    for node in graph["nodes"]:
        if node.get("type") != node_type:
            continue
        if all(node.get(k) == v for k, v in where.items()):
            return node
    return None


def open_escalations(graph, blocking_only=False):
    out = []
    for node in graph["nodes"]:
        if node.get("type") != "escalation" or node.get("status") != "open":
            continue
        if blocking_only and not node.get("blocking"):
            continue
        out.append(node)
    out.sort(key=lambda n: (0 if n.get("blocking") else 1, n.get("created_at", "")))
    return out


def _claim_info(run):
    claim = run.get("claim")
    if not claim:
        return None
    out = dict(claim)
    started = claim.get("claimed_at") or claim.get("started_at")
    if started:
        try:
            ts = datetime.datetime.fromisoformat(started.replace("Z", "+00:00"))
            out["age_seconds"] = round(
                (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds(), 1
            )
        except ValueError:
            pass
    return out


def _allowed_for(state, claim):
    if state == "planning":
        return ["read", "status", "intent-write", "sign"], [
            "code-write", "claim", "accept", "approve", "mint",
        ]
    if state == "executing":
        if claim:
            return ["read", "status", "owned-write", "test", "attempts"], [
                "accept", "approve", "mint", "unowned-write",
            ]
        return ["read", "status", "dispatch", "add-wo"], [
            "code-write", "accept", "approve", "mint",
        ]
    if state == "reviewing":
        return ["read", "status", "accept", "findings-ack"], [
            "code-write", "add-wo", "approve", "mint",
        ]
    return ["read", "status", "timeline"], ["all-mutations"]


def next_step(graph):
    run_node = graph["nodes"][0]
    state = run_node.get("state")
    claim = run_node.get("claim")
    nxt = next_work_order(graph)
    action = nxt["action"]
    wo = nxt.get("wo")
    run = graph["run"]

    if action == "start":
        reason, check = "intent is not signed", f"sancai_card.py intent --run {run}"
    elif action == "approve":
        esc = nxt.get("escalation")
        reason = f"blocking escalation {esc} requires a human decision"
        check = f"sancai_card.py approve --run {run} --esc {esc}"
    elif action == "accept":
        reason = "all work orders are verified; acceptance is a human decision"
        check = f"sancai_card.py accept --run {run}"
    elif action == "dispatch" and wo:
        reason = f"{wo} is pending and has no active claim"
        check = f"sancai_state.py claim --wo {wo} --by <executor>"
    elif action == "wait" and wo:
        by = (claim or {}).get("by") or "executor"
        reason = f"claim active by {by}; waiting for executor/verifier"
        check = f"sancai_graph.py attempts --wo {wo}"
    elif state in TERMINAL_STATES:
        reason, check = f"run is {state}", "sancai_graph.py show"
    else:
        reason, check = "no action required", "sancai_graph.py position"

    allowed, forbidden = _allowed_for(state, claim)
    return {
        "action": action,
        "wo": wo,
        "escalation": nxt.get("escalation"),
        "reason": reason,
        "check": check,
        "allowed": allowed,
        "forbidden": forbidden,
    }


def position(graph):
    run = graph["nodes"][0]
    state = run.get("state")
    claim = _claim_info(run)
    wos = [n for n in graph["nodes"] if n.get("type") == "work_order"]
    total = len(wos)
    verified = sum(1 for n in wos if n.get("state") in ("verified", "merged"))
    escs = open_escalations(graph)
    blocking = [e for e in escs if e.get("blocking")]
    trigger = blocking[0]["id"] if blocking else None
    nxt = next_step(graph)
    action = nxt["action"]
    current_wo = (claim or {}).get("wo") or nxt.get("wo")

    if state == "planning":
        stage, layer = "Requirements", "L3"
    elif state == "executing":
        stage = "Execution"
        layer = "L3" if blocking else ("L1" if claim else "L2")
    elif state == "reviewing":
        stage, layer = "Acceptance", "L3"
    elif state == "accepted":
        stage, layer = "Accepted", "—"
    elif state == "abandoned":
        stage, layer = "Abandoned", "—"
    else:
        stage, layer = state or "Unknown", "—"

    time_in_state = None
    updated = run.get("updated_at")
    if updated:
        try:
            ts = datetime.datetime.fromisoformat(updated.replace("Z", "+00:00"))
            time_in_state = round(
                (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds(), 1
            )
        except ValueError:
            pass

    return {
        "schema_version": "sancai.status.v1",
        "run": graph["run"],
        "state": state,
        "stage": stage,
        "layer": layer,
        "progress": f"{verified}/{total}",
        "progress_detail": {
            "verified": verified, "total": total, "current_wo": current_wo,
        },
        "claim": claim,
        "trigger": trigger,
        "trigger_detail": (
            {"type": blocking[0].get("esc_type"), "id": blocking[0]["id"], "blocking": True}
            if blocking else None
        ),
        "next_action": action,
        "next": nxt,
        "open_escalations": [e["id"] for e in escs],
        "open_escalation_details": [
            {
                "id": e["id"], "type": e.get("esc_type"),
                "wo": e.get("wo"), "blocking": bool(e.get("blocking")),
            }
            for e in escs
        ],
        "time_in_state_seconds": time_in_state,
    }


def status_object(root, run=None):
    """Return the canonical SancaiStatus object for a run.

    If run is omitted, use .sancai/active. The caller handles the idle case.
    """
    active = read_active(root)
    if run is None:
        if not active:
            return None
        run = active["run"]
    graph = build_graph(root, run)
    status = position(graph)
    is_active = bool(active and active.get("run") == run)
    terminal = status["state"] in TERMINAL_STATES
    status["active"] = {
        "valid": is_active and not terminal,
        "reason": (
            None if is_active and not terminal
            else "active pointer missing" if not is_active
            else f"run is {status['state']}"
        ),
    }
    status["updated_at"] = graph["nodes"][0].get("updated_at")
    # Compatibility fields for callers that still read the raw run record.
    run_data = load(paths.run_path(root, run))
    status["work_orders"] = run_data.get("work_orders", {})
    status["acceptance"] = run_data.get("acceptance")
    status["outcome"] = run_data.get("outcome")
    return status


def next_work_order(graph):
    run = graph["nodes"][0]
    state = run.get("state")
    if state == "planning":
        return {"action": "start", "wo": None}
    if state == "reviewing":
        return {"action": "accept", "wo": None}
    if state in ("accepted", "abandoned"):
        return {"action": "none", "wo": None}

    esc = open_escalations(graph, blocking_only=True)
    if esc:
        return {"action": "approve", "wo": esc[0].get("wo"), "escalation": esc[0]["id"]}
    if run.get("claim"):
        return {"action": "wait", "wo": run["claim"].get("wo")}

    wos = sorted(
        [n for n in graph["nodes"] if n.get("type") == "work_order"],
        key=lambda n: n["id"],
    )
    for wo in wos:
        if wo.get("state") in ("pending", "changes_requested"):
            return {"action": "dispatch", "wo": wo["id"]}
    if wos and all(w.get("state") in ("verified", "merged") for w in wos):
        return {"action": "accept", "wo": None}
    return {"action": "none", "wo": None}


def show(graph):
    pos = position(graph)
    lines = [
        f"{graph['run']}  {pos['state']}  ({pos['stage']}, {pos['layer']}, {pos['progress']})"
    ]
    wos = sorted(
        [n for n in graph["nodes"] if n.get("type") == "work_order"],
        key=lambda n: n["id"],
    )
    for i, wo in enumerate(wos):
        last = i == len(wos) - 1
        branch = "└─" if last else "├─"
        attempts = sorted(
            [n for n in graph["nodes"] if n.get("type") == "attempt" and n.get("wo") == wo["id"]],
            key=lambda n: n["id"],
        )
        gate = find_node(graph, "gate", wo=wo["id"])
        escs = [
            n for n in graph["nodes"]
            if n.get("type") == "escalation" and n.get("wo") == wo["id"]
        ]
        escs.sort(key=lambda n: n.get("id", ""))
        lines.append(
            f"{branch} {wo['id']}  {wo.get('state')}  attempts={len(attempts)}"
        )
        children = attempts + ([gate] if gate else []) + escs
        prefix = "   " if last else "│  "
        for j, child in enumerate(children):
            cb = "└─" if j == len(children) - 1 else "├─"
            if child["type"] == "attempt":
                lines.append(f"{prefix}{cb} {child['id']}  {child.get('status')}")
            elif child["type"] == "gate":
                lines.append(f"{prefix}{cb} {child['id']}  {child.get('result')}")
            else:
                lines.append(
                    f"{prefix}{cb} {child['id']}  {child.get('status')}  "
                    f"{child.get('esc_type')}  blocking={child.get('blocking')}"
                )
    orphans = [
        n for n in graph["nodes"]
        if n.get("type") == "escalation" and not n.get("wo")
    ]
    for e in orphans:
        lines.append(f"└─ {e['id']}  {e.get('status')}  {e.get('esc_type')}")
    return "\n".join(lines)


def _run_arg(args, root):
    return args.run or active_run(root)


def cmd_rebuild(args):
    root = find_root()
    run = _run_arg(args, root)
    graph = build_graph(root, run)
    print(paths.graph_path(root, run))
    print(f"nodes={len(graph['nodes'])} edges={len(graph['edges'])}")


def cmd_position(args):
    root = find_root()
    run = _run_arg(args, root)
    pos = status_object(root, run)
    assert pos is not None
    if args.json:
        print(json.dumps(pos, ensure_ascii=False, indent=2))
        return
    print(f"run       : {pos['run']}")
    print(f"state     : {pos['state']}")
    print(f"stage     : {pos['stage']}")
    print(f"layer     : {pos['layer']}")
    print(f"progress  : {pos['progress']}")
    print(f"claim     : {pos['claim'] or '-'}")
    print(f"trigger   : {pos['trigger'] or '-'}")
    print(f"next      : {pos['next']['action']}")
    print(f"reason    : {pos['next']['reason']}")
    print(f"check     : {pos['next']['check']}")
    print(f"open esc  : {', '.join(pos['open_escalations']) or '-'}")
    print(f"active    : {pos['active']}")


def cmd_next(args):
    root = find_root()
    graph = build_graph(root, _run_arg(args, root))
    nxt = next_step(graph)
    if args.json:
        print(json.dumps(nxt, ensure_ascii=False, indent=2))
        return
    print(f"action    : {nxt['action']}")
    print(f"wo        : {nxt.get('wo') or '-'}")
    if nxt.get("escalation"):
        print(f"escalation: {nxt['escalation']}")
    print(f"reason    : {nxt['reason']}")
    print(f"check     : {nxt['check']}")
    print(f"allowed   : {', '.join(nxt['allowed'])}")
    print(f"forbidden : {', '.join(nxt['forbidden'])}")


def cmd_attempts(args):
    root = find_root()
    graph = build_graph(root, _run_arg(args, root))
    attempts = sorted(
        [n for n in graph["nodes"] if n.get("type") == "attempt" and n.get("wo") == args.wo],
        key=lambda n: n["id"],
    )
    if args.json:
        print(json.dumps(attempts, ensure_ascii=False, indent=2))
        return
    if not attempts:
        print(f"no attempts for {args.wo}")
        return
    for a in attempts:
        print(f"{a['id']}  {a.get('status'):10s} started={a.get('started_at', '-')}")


def cmd_open_escalations(args):
    root = find_root()
    graph = build_graph(root, _run_arg(args, root))
    escs = open_escalations(graph)
    if args.json:
        print(json.dumps(escs, ensure_ascii=False, indent=2))
        return
    if not escs:
        print("no open escalations")
        return
    for e in escs:
        print(
            f"{e['id']}  {e.get('esc_type'):14s} wo={e.get('wo')} "
            f"blocking={e.get('blocking')} rec={e.get('recommendation') or '-'}"
        )


def cmd_metrics(args):
    root = find_root()
    graph = build_graph(root, _run_arg(args, root))
    metrics = graph["metrics"]
    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return
    for key in (
        "wo_total", "wo_verified", "wo_blocked", "attempts", "rework",
        "rejections", "escalations", "approvals", "open_escalations",
        "tokens", "human_minutes", "decisions", "median_latency_seconds",
        "fatigue_suspected", "control_status", "control_reason",
        "attempts_budget", "attempts_remaining", "human_rounds_budget",
        "human_rounds_used", "no_progress_streak",
    ):
        print(f"{key:26s} {metrics[key]}")


def cmd_show(args):
    root = find_root()
    graph = build_graph(root, _run_arg(args, root))
    print(show(graph))


def _actor_label(value):
    if isinstance(value, dict):
        return value.get("id") or value.get("kind") or "-"
    return value or "-"


def _subject_label(event):
    subject = event.get("subject")
    if isinstance(subject, dict):
        return subject.get("id") or subject.get("type") or "-"
    if subject:
        return subject
    meta = event.get("meta") or {}
    return meta.get("wo") or meta.get("path") or event.get("run") or "-"


def infer_transition(event):
    """Best-effort from/to for legacy events that predate explicit fields."""
    name = event.get("event", "")
    meta = event.get("meta") or {}
    if name == "run_initialized":
        return "—", "planning"
    if name == "intent_signed":
        return "planning", "executing"
    if name == "work_order_added":
        return "—", "pending"
    if name == "claimed":
        return "pending", "in_progress"
    if name == "released":
        return "in_progress", "pending"
    if name == "wo_transition":
        return meta.get("from") or "—", meta.get("to") or "—"
    if name == "gate_result":
        result = meta.get("result")
        if result == "verified":
            return "for_review", "verified"
        if result == "blocked":
            return "for_review", "blocked"
        if result:
            return "for_review", "in_progress"
    if name == "escalation_raised":
        return "—", "open"
    if name in ("decision_recorded", "human_decision"):
        return "open", "resolved"
    if name == "outcome_accepted":
        return "reviewing", "accepted"
    if name == "abandoned":
        return "—", "abandoned"
    return "—", "—"


def timeline_entries(root, run, last=20):
    """Return the most recent process events in chronological order."""
    entries = []
    for event in load_events(root, run):
        ts = event.get("ts", "")
        meta = event.get("meta") or {}
        start = event.get("from") or meta.get("from")
        end = event.get("to") or meta.get("to")
        if not start or not end:
            inferred_start, inferred_end = infer_transition(event)
            start = start or inferred_start
            end = end or inferred_end
        entries.append(
            {
                "ts": ts,
                "time": ts[11:19] if len(ts) >= 19 else ts or "-",
                "event": event.get("event", "-"),
                "actor": _actor_label(event.get("actor")),
                "subject": _subject_label(event),
                "from": start,
                "to": end,
                "reason": event.get("reason") or "",
            }
        )
    if last and last > 0:
        entries = entries[-last:]
    return entries


def cmd_timeline(args):
    root = find_root()
    run = _run_arg(args, root)
    entries = timeline_entries(root, run, args.last)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return
    if not entries:
        print(f"no events for {run}")
        return
    for entry in entries:
        print(
            f"{entry['time']:8s}  {entry['event']:20s} "
            f"{entry['actor']:10s} {entry['subject']:14s} "
            f"{entry['from']}→{entry['to']}"
        )


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("rebuild")
    p.add_argument("--run")
    p.set_defaults(func=cmd_rebuild)

    p = sub.add_parser("position")
    p.add_argument("--run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_position)

    p = sub.add_parser("next")
    p.add_argument("--run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("attempts")
    p.add_argument("--run")
    p.add_argument("--wo", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_attempts)

    p = sub.add_parser("open-escalations")
    p.add_argument("--run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_open_escalations)

    p = sub.add_parser("metrics")
    p.add_argument("--run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("show")
    p.add_argument("--run")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("timeline")
    p.add_argument("--run")
    p.add_argument("--last", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_timeline)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""H3 closeout transaction for the project ledger.

A run never mutates ``.sancai/project`` while it is executing. TODOs are
staged in L2; H3 acceptance builds a closeout plan, binds its effect hash into
the accept card, then applies the plan idempotently after card consumption.
"""
import argparse
import datetime
import json
import os
import re
import sys

import sancai_integration as integration  # type: ignore
import sancai_paths as paths  # type: ignore
import sancai_requirements as requirements  # type: ignore

SCHEMA_VERSION = 1
JOURNAL_PHASES = ("authorized", "card_consumed", "project_applied", "run_accepted", "committed")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class CloseoutError(Exception):
    pass


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(data):
    return requirements.sha(data)


def canonical(data):
    return requirements.canonical(data)


def load_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _allocate_todo_ids(backlog, count):
    n = int(backlog.get("next_todo") or 1)
    ids = []
    items = backlog.setdefault("items", {})
    while len(ids) < count:
        candidate = "TODO-%03d" % n
        n += 1
        if candidate not in items:
            ids.append(candidate)
    return ids


def _requirements_effect(intent, requirements_data):
    selected = list(intent.get("requirements") or [])
    before = {}
    after = {}
    for req_id in selected:
        req = (requirements_data.get("requirements") or {}).get(req_id)
        if not req:
            raise CloseoutError("selected requirement is missing from the ledger: " + req_id)
        status = req.get("status")
        if status not in ("accepted", "verified"):
            raise CloseoutError(
                "requirement %s is %s, expected accepted/verified" % (req_id, status)
            )
        before[req_id] = status
        after[req_id] = "verified" if status == "accepted" else status
    return before, after


def base_plan(root, run, run_data, intent):
    """Build the disposition-independent part of the closeout plan."""
    requirements_data, backlog = requirements.load_ledger(root)
    before, after = _requirements_effect(intent, requirements_data)
    staged = list(requirements.load_updates(root, run).get("todos") or [])
    ids = _allocate_todo_ids(backlog, len(staged))
    staged_todos = []
    for todo_id, item in zip(ids, staged):
        staged_todos.append(
            {
                "id": todo_id,
                "stage_id": item.get("stage_id"),
                "title": item.get("title"),
                "type": item.get("type", "feature"),
                "priority": item.get("priority", "P2"),
                "status": "pending",
                "relation": item.get("relation", "unrelated"),
                "source": item.get("source", ""),
                "notes": item.get("notes", ""),
                "req": None,
            }
        )
    evidence = integration.load_evidence(root, run)
    integ = {
        "required": integration.required(intent),
        "success": bool(evidence and evidence.get("success")),
        "evidence_sha": (evidence or {}).get("evidence_sha", ""),
    }
    base = {
        "schema_version": SCHEMA_VERSION,
        "run": run,
        "requirements_before": before,
        "requirements_after": after,
        "staged_todos": staged_todos,
        "integration": integ,
        "blueprint_regenerate": bool(before or staged_todos),
    }
    return base


def closeout_sha(base):
    """Effect hash bound into the accept card (disposition-independent)."""
    return sha(base)


def build_plan(root, run, run_data, intent, disposition=None, message=""):
    base = base_plan(root, run, run_data, intent)
    _, backlog = requirements.load_ledger(root)
    todos = [dict(item) for item in base["staged_todos"]]
    disposition_record = None
    if disposition:
        raw = disposition.strip()
        if raw.startswith("defer:"):
            wo_id = raw[len("defer:"):].strip()
            if not wo_id:
                raise CloseoutError("defer requires a follow-up work order id")
            if not ID_RE.match(wo_id) or ".." in wo_id:
                raise CloseoutError("invalid follow-up work order id: %r" % wo_id)
            if wo_id in (run_data.get("work_orders") or {}):
                raise CloseoutError("follow-up work order already exists: " + wo_id)
            title = "Resolve deferred finding " + wo_id
            todos.append(
                {
                    "id": _next_free_todo(backlog, todos),
                    "stage_id": "",
                    "title": title,
                    "type": "finding",
                    "priority": "P1",
                    "status": "pending",
                    "relation": "related",
                    "source": "run:%s/WO:%s" % (run, wo_id),
                    "notes": "Deferred at H3 acceptance: " + message,
                    "req": None,
                    "disposition": "defer",
                }
            )
            disposition_record = {
                "raw": raw,
                "kind": "defer",
                "wo": wo_id,
                "todo": todos[-1]["id"],
                "title": title,
            }
        elif raw.startswith("waive:"):
            reason = raw[len("waive:"):].strip()
            if not reason:
                raise CloseoutError("waive requires a non-empty reason")
            disposition_record = {"raw": raw, "kind": "waive", "reason": reason}
        else:
            raise CloseoutError(
                "unknown disposition; use defer:<FOLLOWUP-ID> or waive:<non-empty reason>"
            )
    plan = dict(base)
    plan["todos"] = todos
    plan["dispositions"] = [disposition_record] if disposition_record else []
    plan["message"] = message
    plan["created_at"] = _now()
    plan["effect_sha"] = closeout_sha(base)
    plan["plan_sha"] = sha({k: v for k, v in plan.items() if k != "plan_sha"})
    return plan


def _next_free_todo(backlog, todos):
    used = set((backlog.get("items") or {}).keys())
    used.update(item["id"] for item in todos)
    n = int(backlog.get("next_todo") or 1)
    while True:
        candidate = "TODO-%03d" % n
        n += 1
        if candidate not in used:
            return candidate


def write_plan(root, plan):
    save_json(paths.closeout_plan_path(root, plan["run"]), plan)
    return plan


def load_plan(root, run):
    return load_json(paths.closeout_plan_path(root, run))


def apply_plan(root, plan):
    """Upsert requirement statuses and TODOs; safe to replay."""
    requirements_data, backlog = requirements.load_ledger(root)
    changed = False
    for req_id, status in (plan.get("requirements_after") or {}).items():
        req = (requirements_data.get("requirements") or {}).get(req_id)
        if not req:
            raise CloseoutError("requirement disappeared during closeout: " + req_id)
        if req.get("status") == status:
            continue
        req["status"] = status
        req["updated_at"] = _now()
        requirements._history(req, "run_verified", run=plan["run"])
        changed = True
    for item in plan.get("todos") or []:
        if item["id"] in backlog.setdefault("items", {}):
            continue
        stored = {k: v for k, v in item.items() if k != "disposition"}
        stored["created_at"] = _now()
        stored["updated_at"] = _now()
        stored["history"] = []
        requirements._history(
            stored,
            "captured",
            relation=stored.get("relation"),
            source=stored.get("source"),
            staged=bool(item.get("stage_id")),
        )
        backlog["items"][stored["id"]] = stored
        n = int(stored["id"].split("-")[-1]) + 1
        backlog["next_todo"] = max(int(backlog.get("next_todo") or 1), n)
        changed = True
    if changed:
        requirements.save_ledger(root, requirements_data, backlog)
    if plan.get("blueprint_regenerate"):
        out = paths.blueprint_path(root)
        os.makedirs(os.path.dirname(out), mode=0o700, exist_ok=True)
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(requirements.render_blueprint(requirements_data, backlog))
        os.replace(tmp, out)
    return changed


def load_journal(root, run):
    return load_json(
        paths.closeout_journal_path(root, run),
        {
            "schema_version": SCHEMA_VERSION,
            "run": run,
            "phase": "",
            "events": [],
        },
    )


def save_journal(root, run, journal):
    journal["updated_at"] = _now()
    save_json(paths.closeout_journal_path(root, run), journal)


def advance(root, run, phase, **meta):
    journal = load_journal(root, run)
    if phase not in JOURNAL_PHASES:
        raise CloseoutError("unknown closeout phase: " + phase)
    journal["phase"] = phase
    events = journal.get("events")
    if not isinstance(events, list):
        events = []
        journal["events"] = events
    events.append({"ts": _now(), "phase": phase, "meta": meta})
    save_journal(root, run, journal)
    return journal


def acquire_lock(root, run, stale_seconds=3600):
    path = paths.closeout_lock_path(root, run)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        age = _now_ts() - os.path.getmtime(path)
        if age > stale_seconds:
            os.unlink(path)
            return acquire_lock(root, run, stale_seconds)
        raise CloseoutError("closeout lock is held: " + path)
    else:
        os.write(fd, _now().encode("utf-8"))
        os.close(fd)
    return path


def release_lock(root, run):
    path = paths.closeout_lock_path(root, run)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _now_ts():
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


def card_used(root, run, card_id):
    return os.path.exists(os.path.join(paths.cards_dir(root, run), card_id + ".json.used"))


def _authorized_meta(journal):
    for event in reversed(journal.get("events") or []):
        if event.get("phase") == "authorized":
            return event.get("meta") or {}
    return {}


def _coverage(run_data, intent):
    wos = run_data.get("work_orders") or {}
    coverage = {}
    for req_id in intent.get("requirements") or []:
        covered = [
            wid for wid, wo in wos.items()
            if wo.get("req") == req_id and wo.get("state") in ("verified", "merged")
        ]
        if covered:
            coverage[req_id] = covered
    return coverage


def _event_exists(root, run, event, plan_sha):
    path = paths.events_path(root, run)
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") != event:
                continue
            if (rec.get("meta") or {}).get("closeout_plan_sha") == plan_sha:
                return True
    return False


def _append_event_once(state, root, run, event, meta):
    if not _event_exists(root, run, event, meta.get("closeout_plan_sha", "")):
        state.append_event(root, run, event, meta)


def resume(root, run, force=False):
    """Finish a closeout that was interrupted after the accept card was used."""
    if force:
        lock = paths.closeout_lock_path(root, run)
        if os.path.isfile(lock) and _now_ts() - os.path.getmtime(lock) > 3600:
            os.unlink(lock)
    acquire_lock(root, run)
    try:
        return _resume_locked(root, run)
    finally:
        release_lock(root, run)


def _resume_locked(root, run):
    import sancai_state as state  # type: ignore

    path, run_data = state.load_run(root, run)
    if run_data.get("state") == "abandoned":
        raise CloseoutError("run was abandoned; closeout cannot be resumed")
    if run_data.get("state") not in ("reviewing", "accepted"):
        raise CloseoutError(
            "run state %s is not resumable" % run_data.get("state")
        )
    journal = load_journal(root, run)
    phase = journal.get("phase")
    plan = load_plan(root, run)
    if not plan:
        raise CloseoutError("closeout plan is missing; cannot resume")
    authorized = _authorized_meta(journal)
    if journal.get("phase") not in JOURNAL_PHASES:
        raise CloseoutError("closeout was not authorized; run accept instead")
    if phase == "authorized":
        if not card_used(root, run, authorized.get("card_id", "")):
            raise CloseoutError("accept card was not consumed; run accept instead")
        advance(root, run, "card_consumed", card_id=authorized.get("card_id"))
        phase = "card_consumed"
    if authorized.get("plan_sha") != plan.get("plan_sha"):
        raise CloseoutError("closeout plan changed before resume")
    if phase in ("card_consumed", "project_applied"):
        apply_plan(root, plan)
        advance(root, run, "project_applied", effect_sha=plan.get("effect_sha"))
        phase = "project_applied"
    if phase == "project_applied":
        accept_args = authorized.get("accept_args") or {}
        expected = authorized.get("accept_payload") or {}
        intent_path = paths.intent_path(root, run)
        intent = load_json(intent_path, {}) or {}
        captured_todos = [item["id"] for item in plan.get("todos") or []]
        for item in requirements.todos_for_run(root, run):
            if item["id"] not in captured_todos and not item.get("staged"):
                captured_todos.append(item["id"])
        if run_data.get("state") != "accepted":
            from sancai_cards import card_age_seconds  # type: ignore

            card = load_json(
                os.path.join(paths.cards_dir(root, run), authorized.get("card_id", "") + ".json"),
                {},
            ) or {}
            latency = round(card_age_seconds(card), 3) if card else 0.0
            run_data["state"] = "accepted"
            run_data["outcome"] = {
                "accepted_at": _now(),
                "message": accept_args.get("message", ""),
                "accepted_in_session": accept_args.get("session_id", ""),
                "card_id": authorized.get("card_id", ""),
                "latency_seconds": latency,
                "requirements": _coverage(run_data, intent),
                "captured_todos": captured_todos,
                "integration": plan.get("integration") or {},
                "closeout_plan_sha": plan.get("plan_sha", ""),
            }
            run_data["acceptance"] = {
                "findings": {
                    "hash": expected.get("findings_hash", ""),
                    "count": expected.get("findings_count", 0),
                    "acknowledged": True,
                    "dispositions": plan.get("dispositions") or [],
                },
                "requirements": _coverage(run_data, intent),
                "captured_todos": captured_todos,
                "closeout_plan_sha": plan.get("plan_sha", ""),
            }
            run_data["updated_at"] = _now()
            state.save(path, run_data)
        advance(root, run, "run_accepted", state="accepted")
        phase = "run_accepted"
    if phase == "run_accepted":
        accept_args = authorized.get("accept_args") or {}
        intent_path = paths.intent_path(root, run)
        intent = load_json(intent_path, {}) or {}
        captured_todos = [item["id"] for item in plan.get("todos") or []]
        for item in requirements.todos_for_run(root, run):
            if item["id"] not in captured_todos and not item.get("staged"):
                captured_todos.append(item["id"])
        state.clear_active(root, run)
        _append_event_once(
            state,
            root,
            run,
            "findings_acknowledged",
            {
                "hash": (authorized.get("accept_payload") or {}).get("findings_hash", ""),
                "count": (authorized.get("accept_payload") or {}).get("findings_count", 0),
                "dispositions": plan.get("dispositions") or [],
                "follow_up_wo": "",
                "deferred_todo": "",
                "closeout_plan_sha": plan.get("plan_sha", ""),
            },
        )
        _append_event_once(
            state,
            root,
            run,
            "outcome_accepted",
            {
                "message": accept_args.get("message", ""),
                "requirements": _coverage(run_data, intent),
                "captured_todos": captured_todos,
                "closeout_plan_sha": plan.get("plan_sha", ""),
            },
        )
        advance(root, run, "committed", effect_sha=plan.get("effect_sha"))
    print("closeout committed: " + run)
    return 0


def cmd_status(args):
    root = requirements.find_root()
    plan = load_plan(root, args.run)
    journal = load_journal(root, args.run)
    print(
        json.dumps(
            {
                "run": args.run,
                "phase": journal.get("phase"),
                "plan": bool(plan),
                "effect_sha": (plan or {}).get("effect_sha", ""),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sancai H3 closeout")
    sub = parser.add_subparsers(dest="cmd", required=True)
    status = sub.add_parser("status")
    status.add_argument("--run", required=True)
    status.set_defaults(func=cmd_status)
    resume_cmd = sub.add_parser("resume", help="finish an interrupted closeout")
    resume_cmd.add_argument("--run", required=True)
    resume_cmd.add_argument("--force", action="store_true")
    resume_cmd.set_defaults(func=lambda args: resume(
        requirements.find_root(), args.run, args.force
    ))
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except CloseoutError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

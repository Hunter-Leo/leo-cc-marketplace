#!/usr/bin/env python3
"""Project-level requirement ledger and backlog.

Requirements live across runs; a run's intent only snapshots the accepted
requirements it selects. The backlog holds raw captures, including unrelated
requirements discovered while a run is executing.

usage:
  sancai_requirements.py init
  sancai_requirements.py capture --title "..." --type feature --priority P2 \
      --source run:001 --relation unrelated
  sancai_requirements.py list [--status pending] [--json]
  sancai_requirements.py promote TODO-001 --acceptance '["..."]'
  sancai_requirements.py accept REQ-001
  sancai_requirements.py defer REQ-001 --reason "..."
  sancai_requirements.py reject TODO-002 --reason "..."
  sancai_requirements.py select --run 001-x --req REQ-001
  sancai_requirements.py blueprint
  sancai_requirements.py status [--json]
"""
import argparse
import datetime
import json
import os
import re
import sys

import sancai_paths as paths  # type: ignore

os.umask(0o077)

SCHEMA_VERSION = 1
TODO_TYPES = ("bug", "feature", "improvement", "tech-debt", "finding")
TODO_STATUSES = ("pending", "promoted", "deferred", "rejected")
REQ_STATUSES = (
    "proposed", "accepted", "in_progress", "verified",
    "deferred", "rejected", "superseded",
)
PRIORITIES = ("P0", "P1", "P2", "P3")
RELATIONS = ("related", "unrelated")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


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


def load(path, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _empty_requirements():
    return {
        "schema_version": SCHEMA_VERSION,
        "next_req": 1,
        "requirements": {},
    }


def _empty_backlog():
    return {
        "schema_version": SCHEMA_VERSION,
        "next_todo": 1,
        "items": {},
    }


def load_ledger(root):
    return (
        load(paths.requirements_path(root), _empty_requirements()),
        load(paths.backlog_path(root), _empty_backlog()),
    )


def save_ledger(root, requirements, backlog):
    save(paths.requirements_path(root), requirements)
    save(paths.backlog_path(root), backlog)


def _history(obj, event, **meta):
    obj.setdefault("history", []).append({"ts": now(), "event": event, "meta": meta})


def _next_id(data, key, prefix):
    n = int(data.get(key) or 1)
    while f"{prefix}-{n:03d}" in data.get(
        "requirements" if prefix == "REQ" else "items", {}
    ):
        n += 1
    data[key] = n + 1
    return f"{prefix}-{n:03d}"


def capture_todo(root, title, type_="feature", priority="P2", source="",
                 relation="unrelated", notes=""):
    """Add a raw capture and return it. Used by H3 defer as well."""
    if type_ not in TODO_TYPES:
        sys.exit(f"unknown TODO type: {type_}")
    if priority not in PRIORITIES:
        sys.exit(f"unknown priority: {priority}")
    if relation not in RELATIONS:
        sys.exit(f"unknown relation: {relation}")
    requirements, backlog = load_ledger(root)
    todo_id = _next_id(backlog, "next_todo", "TODO")
    item = {
        "id": todo_id,
        "title": title.strip(),
        "type": type_,
        "priority": priority,
        "status": "pending",
        "relation": relation,
        "source": source,
        "notes": notes,
        "req": None,
        "created_at": now(),
        "updated_at": now(),
        "history": [],
    }
    _history(item, "captured", relation=relation, source=source)
    backlog["items"][todo_id] = item
    save_ledger(root, requirements, backlog)
    return item


def todos_for_run(root, run):
    _, backlog = load_ledger(root)
    prefix = f"run:{run}"
    return [
        item for item in backlog["items"].values()
        if str(item.get("source", "")).startswith(prefix)
        and item.get("status") != "promoted"
    ]


def _parse_acceptance(raw):
    if not raw:
        return []
    text = raw.strip()
    if os.path.isfile(text):
        with open(text, encoding="utf-8") as f:
            text = f.read().strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = [line.strip() for line in text.splitlines() if line.strip()]
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not value:
        sys.exit("acceptance must be a non-empty JSON array or newline list")
    out = []
    for i, item in enumerate(value, 1):
        if isinstance(item, dict):
            text_value = item.get("text") or item.get("expect") or ""
            ac_id = item.get("id") or f"AC-{i}"
        else:
            text_value = str(item)
            ac_id = f"AC-{i}"
        if not str(text_value).strip():
            sys.exit("acceptance entries must have non-empty text")
        out.append({"id": str(ac_id), "text": str(text_value).strip()})
    return out


def _active_run_selects(root, req_id):
    runs = os.path.join(paths.sancai_dir(root), "runs")
    if not os.path.isdir(runs):
        return False
    for name in os.listdir(runs):
        run_path = paths.run_path(root, name)
        intent_path = paths.intent_path(root, name)
        if not os.path.isfile(run_path) or not os.path.isfile(intent_path):
            continue
        try:
            run_data = load(run_path, {})
            intent = load(intent_path, {})
        except (OSError, json.JSONDecodeError):
            continue
        if run_data.get("state") in ("accepted", "abandoned"):
            continue
        if intent.get("approval") and req_id in (intent.get("requirements") or []):
            return True
    return False


def cmd_init(args):
    root = find_root()
    requirements, backlog = load_ledger(root)
    save_ledger(root, requirements, backlog)
    print(f"initialized {paths.project_dir(root)}")


def cmd_capture(args):
    root = find_root()
    item = capture_todo(
        root, args.title, args.type, args.priority, args.source,
        args.relation, args.notes,
    )
    if args.json:
        print(json.dumps(item, ensure_ascii=False, indent=2))
    else:
        print(f"captured {item['id']}: {item['title']} ({item['relation']})")


def cmd_list(args):
    root = find_root()
    _, backlog = load_ledger(root)
    items = list(backlog["items"].values())
    if args.status:
        items = [i for i in items if i.get("status") == args.status]
    if args.relation:
        items = [i for i in items if i.get("relation") == args.relation]
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        print("no backlog items")
        return
    for item in items:
        print(
            f"{item['id']}  {item['status']:<10} {item['priority']} "
            f"{item['relation']:<9} {item['type']:<10} {item['title']}"
        )


def cmd_promote(args):
    root = find_root()
    requirements, backlog = load_ledger(root)
    todo = backlog["items"].get(args.todo)
    if not todo:
        sys.exit(f"backlog item not found: {args.todo}")
    if todo.get("status") not in ("pending", "deferred"):
        sys.exit(f"backlog item is {todo.get('status')}, not promotable")
    acceptance = _parse_acceptance(args.acceptance)
    if not acceptance:
        sys.exit("promote requires at least one acceptance criterion")
    req_id = args.id or _next_id(requirements, "next_req", "REQ")
    if not req_id.startswith("REQ-") or not ID_RE.match(req_id):
        sys.exit(f"invalid requirement id: {req_id!r}")
    if req_id in requirements["requirements"]:
        sys.exit(f"requirement already exists: {req_id}")
    req = {
        "id": req_id,
        "title": args.title or todo["title"],
        "status": "proposed",
        "priority": args.priority or todo.get("priority", "P2"),
        "source": todo["id"],
        "acceptance": acceptance,
        "depends_on": [],
        "notes": todo.get("notes", ""),
        "created_at": now(),
        "updated_at": now(),
        "history": [],
    }
    _history(req, "promoted_from", todo=todo["id"])
    requirements["requirements"][req_id] = req
    todo["status"] = "promoted"
    todo["req"] = req_id
    todo["updated_at"] = now()
    _history(todo, "promoted", req=req_id)
    save_ledger(root, requirements, backlog)
    print(f"promoted {todo['id']} -> {req_id} (proposed)")


def cmd_accept(args):
    root = find_root()
    requirements, backlog = load_ledger(root)
    req = requirements["requirements"].get(args.req)
    if not req:
        sys.exit(f"requirement not found: {args.req}")
    if req.get("status") != "proposed":
        sys.exit(f"requirement is {req.get('status')}, not proposed")
    if not req.get("acceptance"):
        sys.exit(f"requirement has no acceptance criteria: {args.req}")
    req["status"] = "accepted"
    req["updated_at"] = now()
    _history(req, "accepted")
    save_ledger(root, requirements, backlog)
    print(f"accepted {args.req}")


def _transition_item(args, target, event):
    root = find_root()
    requirements, backlog = load_ledger(root)
    if not args.reason.strip():
        sys.exit(f"{event} requires a non-empty reason")
    if args.id.startswith("TODO-"):
        item = backlog["items"].get(args.id)
        if not item:
            sys.exit(f"backlog item not found: {args.id}")
        allowed = ("pending", "deferred")
    elif args.id.startswith("REQ-"):
        item = requirements["requirements"].get(args.id)
        if not item:
            sys.exit(f"requirement not found: {args.id}")
        if _active_run_selects(root, args.id):
            sys.exit(f"{args.id} is selected by an active signed run; finish that run first")
        allowed = ("proposed", "accepted")
    else:
        sys.exit(f"unknown item id: {args.id}")
    if item.get("status") not in allowed:
        sys.exit(f"{args.id} is {item.get('status')}, cannot {event}")
    item["status"] = target
    item["updated_at"] = now()
    _history(item, event, reason=args.reason.strip())
    save_ledger(root, requirements, backlog)
    print(f"{event} {args.id}")


def cmd_defer(args):
    _transition_item(args, "deferred", "deferred")


def cmd_reject(args):
    _transition_item(args, "rejected", "rejected")


def _append_event(root, run, event, meta):
    path = paths.events_path(root, run)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    rec = {"ts": now(), "run": run, "event": event, "actor": "harness", "meta": meta}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cmd_select(args):
    root = find_root()
    run = args.run
    if not ID_RE.match(run) or ".." in run:
        sys.exit(f"invalid run: {run!r}")
    run_path = paths.run_path(root, run)
    if not os.path.isfile(run_path):
        sys.exit(f"run not found: {run_path}")
    run_data = load(run_path, {})
    if run_data.get("state") != "planning":
        sys.exit(f"run must be planning to select requirements, currently {run_data.get('state')}")
    intent_path = paths.intent_path(root, run, run_data)
    if not os.path.isfile(intent_path):
        sys.exit(f"intent not found: {intent_path}")
    intent = load(intent_path, {})
    if intent.get("approval"):
        sys.exit("intent is already signed; create a new run or re-sign after selecting")
    requirements, _ = load_ledger(root)
    selected = list(intent.get("requirements") or [])
    for req_id in args.req:
        req = requirements["requirements"].get(req_id)
        if not req:
            sys.exit(f"requirement not found: {req_id}")
        if req.get("status") != "accepted":
            sys.exit(f"requirement {req_id} is {req.get('status')}, not accepted")
        if not req.get("acceptance"):
            sys.exit(f"requirement {req_id} has no acceptance criteria")
        if req_id not in selected:
            selected.append(req_id)
    if not selected:
        sys.exit("select requires at least one --req")
    intent["requirements"] = selected
    intent["revision"] = int(intent.get("revision") or 0) + 1
    save(intent_path, intent)
    _append_event(root, run, "requirements_selected", {
        "requirements": selected, "revision": intent["revision"],
    })
    print(f"selected {', '.join(selected)} for {run} (revision {intent['revision']})")


def _counts(items, statuses):
    out = {status: 0 for status in statuses}
    for item in items:
        status = item.get("status")
        if status in out:
            out[status] += 1
    return out


def cmd_blueprint(args):
    root = find_root()
    requirements, backlog = load_ledger(root)
    reqs = list(requirements["requirements"].values())
    todos = list(backlog["items"].values())
    req_counts = _counts(reqs, REQ_STATUSES)
    todo_counts = _counts(todos, TODO_STATUSES)
    lines = [
        "# Requirements Blueprint",
        "",
        f"Generated: {now()}",
        "",
        "## Summary",
        "",
        f"- Requirements: {len(reqs)} "
        f"({', '.join(f'{k}={v}' for k, v in req_counts.items() if v) or 'none'})",
        f"- Backlog: {len(todos)} "
        f"({', '.join(f'{k}={v}' for k, v in todo_counts.items() if v) or 'none'})",
        "",
        "## Requirements",
        "",
        "| ID | Title | Status | Priority | ACs | Source |",
        "|---|---|---|---|---|---|",
    ]
    if not reqs:
        lines.append("| — | — | — | — | — | — |")
    for req in sorted(reqs, key=lambda r: r["id"]):
        title = str(req.get("title", "")).replace("|", "\\|")
        lines.append(
            f"| {req['id']} | {title} | {req.get('status')} | "
            f"{req.get('priority')} | {len(req.get('acceptance') or [])} | "
            f"{req.get('source') or '—'} |"
        )
    lines.extend([
        "",
        "## Backlog",
        "",
        "| ID | Title | Type | Status | Relation | Source |",
        "|---|---|---|---|---|---|",
    ])
    if not todos:
        lines.append("| — | — | — | — | — | — |")
    for item in sorted(todos, key=lambda i: i["id"]):
        title = str(item.get("title", "")).replace("|", "\\|")
        lines.append(
            f"| {item['id']} | {title} | {item.get('type')} | "
            f"{item.get('status')} | {item.get('relation')} | "
            f"{item.get('source') or '—'} |"
        )
    lines.append("")
    out = paths.blueprint_path(root)
    os.makedirs(os.path.dirname(out), mode=0o700, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(out)


def cmd_status(args):
    root = find_root()
    requirements, backlog = load_ledger(root)
    reqs = list(requirements["requirements"].values())
    todos = list(backlog["items"].values())
    data = {
        "requirements": _counts(reqs, REQ_STATUSES),
        "backlog": _counts(todos, TODO_STATUSES),
        "next_req": requirements.get("next_req"),
        "next_todo": backlog.get("next_todo"),
    }
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    print("requirements: " + ", ".join(f"{k}={v}" for k, v in data["requirements"].items()))
    print("backlog: " + ", ".join(f"{k}={v}" for k, v in data["backlog"].items()))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("capture")
    p.add_argument("--title", required=True)
    p.add_argument("--type", choices=TODO_TYPES, default="feature")
    p.add_argument("--priority", choices=PRIORITIES, default="P2")
    p.add_argument("--source", default="")
    p.add_argument("--relation", choices=RELATIONS, default="unrelated")
    p.add_argument("--notes", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("list")
    p.add_argument("--status", choices=TODO_STATUSES)
    p.add_argument("--relation", choices=RELATIONS)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("promote")
    p.add_argument("todo")
    p.add_argument("--id")
    p.add_argument("--title")
    p.add_argument("--priority", choices=PRIORITIES)
    p.add_argument("--acceptance", required=True)
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("accept")
    p.add_argument("req")
    p.set_defaults(func=cmd_accept)

    p = sub.add_parser("defer")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_defer)

    p = sub.add_parser("reject")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("select")
    p.add_argument("--run", required=True)
    p.add_argument("--req", action="append", default=[])
    p.set_defaults(func=cmd_select)

    p = sub.add_parser("blueprint")
    p.set_defaults(func=cmd_blueprint)

    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Structured escalations (three triggers, dedupe, queue, approval record).

usage:
  sancai_escalate.py new --run R --wo WO-001 --type out_of_scope \
    --what-tried "..." --evidence "..." \
    --option "A: tradeoff" --option "B: tradeoff" \
    --recommendation A --confidence 0.7 --blocking
  sancai_escalate.py list --run R
  sancai_escalate.py approve --run R --id ESC-001 --message "confirmed" \
    --card-id CARD-... --card-code xxxxxxxx
  sancai_escalate.py reject --run R --id ESC-001 --reason "..." \
    --card-id CARD-... --card-code xxxxxxxx
"""
import argparse
import datetime
import hashlib
import json
import os

import sancai_paths as paths  # type: ignore

import sys

os.umask(0o077)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import sancai_cards  # type: ignore  # noqa: E402
import sancai_control as control  # type: ignore  # noqa: E402
from sancai_state import append_event, validate_id  # type: ignore  # noqa: E402

ALLOWED_APPROVALS = {"confirmed", "approve execution", "approved", "yes"}


def consume_human_round(root, run, action):
    run_path = paths.run_path(root, run)
    data = load(run_path)
    intent = load(paths.intent_path(root, run, data))
    ctl = control.control_of(data)
    ok, reason = control.consume_human_round(
        ctl, control.effective_budget(intent, ctl), action
    )
    if not ok:
        sys.exit(reason)
    save(run_path, data)


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


def esc_dir(root, run):
    return paths.escalations_dir(root, run)


def next_id(d):
    os.makedirs(d, exist_ok=True)
    nums = []
    for name in os.listdir(d):
        if name.startswith("ESC-") and name.endswith(".json"):
            try:
                nums.append(int(name[4:7]))
            except ValueError:
                pass
    return f"ESC-{(max(nums) + 1 if nums else 1):03d}"


def dedupe_key(wo, typ, tried, evidence):
    payload = json.dumps([wo, typ, sorted(tried), sorted(evidence)], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def cmd_new(args):
    root = find_root()
    validate_id(args.run, "run")
    validate_id(args.wo, "work order")
    d = esc_dir(root, args.run)
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not name.endswith(".json"):
            continue
        e = load(os.path.join(d, name))
        if e.get("status") == "open" and e.get("dedupe_key") == dedupe_key(
            args.wo, args.type, args.what_tried, args.evidence
        ):
            print(f"duplicate of {e['id']}; not creating a new one")
            print(os.path.join(d, name))
            return
    eid = next_id(d)
    data = {
        "id": eid,
        "run": args.run,
        "wo": args.wo,
        "type": args.type,
        "what_i_tried": args.what_tried,
        "evidence": args.evidence,
        "options": args.option,
        "recommendation": args.recommendation,
        "confidence": args.confidence,
        "blocking": args.blocking,
        "status": "open",
        "created_at": now(),
        "dedupe_key": dedupe_key(args.wo, args.type, args.what_tried, args.evidence),
    }
    path = os.path.join(d, f"{eid}.json")
    save(path, data)
    append_event(root, args.run, "escalation_raised", {
        "id": eid,
        "wo": args.wo,
        "type": args.type,
        "blocking": args.blocking,
    })
    print(path)


def cmd_list(args):
    d = esc_dir(find_root(), args.run)
    if not os.path.isdir(d):
        print("no escalations")
        return
    rows = []
    for name in os.listdir(d):
        if name.endswith(".json"):
            rows.append(load(os.path.join(d, name)))
    rows.sort(key=lambda e: (0 if e.get("blocking") else 1, e.get("created_at", "")))
    for e in rows:
        print(
            f"{e['id']}  {e['status']:9s} {e['type']:14s} wo={e['wo']} "
            f"blocking={e.get('blocking')} rec={e.get('recommendation')} conf={e.get('confidence')}"
        )


def esc_card_payload(e):
    """Mirror sancai_card._escalation_payload using the on-disk escalation."""
    return {
        "esc": e.get("id"),
        "wo": e.get("wo"),
        "esc_type": e.get("type"),
        "status": e.get("status"),
        "what_tried": e.get("what_i_tried", []),
        "evidence": e.get("evidence", []),
        "options": e.get("options", []),
    }


def consume_bound_card(root, e, card_id, card_code):
    try:
        return sancai_cards.consume_card(
            root, e["run"], card_id, card_code, esc_card_payload(e)
        )
    except sancai_cards.CardError as exc:
        sys.exit(str(exc))


def cmd_approve(args):
    root = find_root()
    validate_id(args.run, "run")
    validate_id(args.id, "escalation")
    path = os.path.join(esc_dir(root, args.run), f"{args.id}.json")
    if not os.path.isfile(path):
        sys.exit(f"escalation not found: {path}")
    if args.message.strip() not in ALLOWED_APPROVALS:
        sys.exit(f"approval must be one of {sorted(ALLOWED_APPROVALS)}; got {args.message!r}")
    if args.session_id:
        validate_id(args.session_id, "session id")
    e = load(path)
    if e.get("status") != "open":
        sys.exit(f"escalation is {e.get('status')}, not open")
    consume_human_round(root, args.run, "escalation decision")
    card = consume_bound_card(root, e, args.card_id, args.card_code)
    latency = round(sancai_cards.card_age_seconds(card), 3)
    e["status"] = "approved"
    e["approved_at"] = now()
    e["approved_by"] = "human"
    e["approved_message"] = args.message
    e["approved_in_session"] = args.session_id or ""
    e["approved_card_id"] = card["card_id"]
    e["approved_latency_seconds"] = latency
    save(path, e)
    append_event(root, args.run, "decision_recorded", {
        "id": args.id,
        "choice": "approved",
        "message": args.message,
        "session": args.session_id or "",
        "card_id": args.card_id,
        "latency_seconds": latency,
    })
    print(f"approved {args.id}")


def cmd_reject(args):
    root = find_root()
    validate_id(args.run, "run")
    validate_id(args.id, "escalation")
    path = os.path.join(esc_dir(root, args.run), f"{args.id}.json")
    if not os.path.isfile(path):
        sys.exit(f"escalation not found: {path}")
    if not args.reason.strip():
        sys.exit("reject requires a concrete reason")
    if args.session_id:
        validate_id(args.session_id, "session id")
    e = load(path)
    if e.get("status") != "open":
        sys.exit(f"escalation is {e.get('status')}, not open")
    consume_human_round(root, args.run, "escalation decision")
    card = consume_bound_card(root, e, args.card_id, args.card_code)
    latency = round(sancai_cards.card_age_seconds(card), 3)
    e["status"] = "rejected"
    e["rejected_at"] = now()
    e["rejected_by"] = "human"
    e["reject_reason"] = args.reason
    e["rejected_in_session"] = args.session_id or ""
    e["rejected_card_id"] = card["card_id"]
    e["rejected_latency_seconds"] = latency
    save(path, e)
    append_event(root, args.run, "decision_recorded", {
        "id": args.id,
        "choice": "rejected",
        "reason": args.reason,
        "session": args.session_id or "",
        "card_id": args.card_id,
        "latency_seconds": latency,
    })
    print(f"rejected {args.id}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new")
    p.add_argument("--run", required=True)
    p.add_argument("--wo", required=True)
    p.add_argument("--type", required=True, choices=["irreversible", "out_of_scope", "spec_ambiguous"])
    p.add_argument("--what-tried", action="append", default=[])
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--option", action="append", default=[])
    p.add_argument("--recommendation", default="")
    p.add_argument("--confidence", type=float, default=0.0)
    p.add_argument("--blocking", action="store_true")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("list")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("approve")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--session-id", default="")
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--session-id", default="")
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)
    p.set_defaults(func=cmd_reject)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

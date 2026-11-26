#!/usr/bin/env python3
"""Write a verifier verdict (harness-owned file).

The verifier agent has read-only tools; it calls this script via Bash so it
never needs Write access to the repository.

usage:
  sancai_verdict.py write --run R --wo WO-001 --verdict pass \
    --session-id sess-v --prompt-hash sha256:... \
    [--finding "major|src/a.ts:10|evidence|fix"]
  sancai_verdict.py list --run R
"""
import argparse
import datetime
import hashlib
import hmac
import json
import os
import uuid

import sancai_paths as paths  # type: ignore
from sancai_state import validate_id  # type: ignore  # noqa: E402

import sys

import sancai_cards

os.umask(0o077)

SEVERITIES = {"blocker", "critical", "major", "minor", "info"}



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


def parse_finding(raw):
    parts = raw.split("|")
    if len(parts) != 4:
        sys.exit(f"malformed finding {raw!r}: expected severity|file:line|evidence|fix")
    severity = parts[0].strip().lower()
    if severity not in SEVERITIES:
        sys.exit(
            f"invalid finding severity {parts[0]!r}: must be one of "
            + ", ".join(sorted(SEVERITIES))
        )
    finding = {
        "severity": severity,
        "file": parts[1].strip(),
        "evidence": parts[2].strip(),
        "fix": parts[3].strip(),
    }
    for field in ("file", "evidence", "fix"):
        if not finding[field]:
            sys.exit(f"malformed finding {raw!r}: {field} must be non-empty")
    return finding



def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _evidence_sha(root, run, wo):
    evidence_path = os.path.join(paths.evidence_dir(root, run), f"{wo}.json")
    if not os.path.isfile(evidence_path):
        sys.exit(f"evidence not found: {evidence_path}; run G0 first (sancai_check_ac.py)")
    evidence = load(evidence_path)
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in evidence.items() if k not in ("collected_at", "ts")},
            sort_keys=True, ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _verifier_dir(root, run):
    return os.path.join(paths.l2_dir(root, run), "verifier")


def _token_path(root, run, token_id):
    return os.path.join(_verifier_dir(root, run), f"{token_id}.json")


def _token_mac(secret, payload):
    return hmac.new(
        secret.encode("utf-8"), _canonical(payload).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def cmd_prepare(args):
    root = find_root()
    validate_id(args.run, "run")
    validate_id(args.wo, "work order")
    secret = os.environ.get("SANCAI_SECRET") or os.environ.get("SANCAI_CARD_SECRET")
    if not secret:
        sys.exit("SANCAI_SECRET is required to prepare a verifier token")
    run_data = load(paths.run_path(root, args.run))
    if run_data.get("state") in ("accepted", "abandoned"):
        sys.exit(f"cannot prepare a verifier token for a {run_data['state']} run")
    token_id = "VT-" + uuid.uuid4().hex[:12]
    token_value = uuid.uuid4().hex + uuid.uuid4().hex
    payload = {
        "run": args.run,
        "wo": args.wo,
        "evidence_sha": _evidence_sha(root, args.run, args.wo),
        "created_at": now(),
        "token_hash": hashlib.sha256(token_value.encode()).hexdigest(),
    }
    token = {"token_id": token_id, "payload": payload, "mac": _token_mac(secret, payload), "used_at": None}
    os.makedirs(_verifier_dir(root, args.run), exist_ok=True)
    save(_token_path(root, args.run, token_id), token)
    print(f"{token_id}:{token_value}")


def _consume_verifier_token(root, run, token_arg, wo, evidence_sha):
    if ":" not in token_arg:
        sys.exit("verifier token must be <token-id>:<secret>")
    token_id, token_value = token_arg.split(":", 1)
    validate_id(token_id, "verifier token")
    path = _token_path(root, run, token_id)
    if not os.path.isfile(path):
        sys.exit(f"verifier token not found: {token_id}")
    token = load(path)
    secret = os.environ.get("SANCAI_SECRET") or os.environ.get("SANCAI_CARD_SECRET")
    if not secret:
        sys.exit("SANCAI_SECRET is required to verify a verifier token")
    payload = token.get("payload") or {}
    if not hmac.compare_digest(str(token.get("mac", "")), _token_mac(secret, payload)):
        sys.exit("verifier token mac mismatch")
    if not hmac.compare_digest(
        hashlib.sha256(token_value.encode()).hexdigest(),
        str(payload.get("token_hash", "")),
    ):
        sys.exit("verifier token secret mismatch")
    if payload.get("run") != run or payload.get("wo") != wo:
        sys.exit("verifier token does not match this run/work order")
    if payload.get("evidence_sha") != evidence_sha:
        sys.exit("verifier token does not match the current evidence")
    if token.get("used_at"):
        sys.exit("verifier token already used")
    marker = path + ".used"
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        sys.exit("verifier token already used")
    else:
        os.close(fd)
    token["used_at"] = now()
    save(path, token)
    return token_id


def cmd_write(args):
    root = find_root()
    validate_id(args.run, "run")
    validate_id(args.wo, "work order")
    run_data = load(paths.run_path(root, args.run))
    if run_data.get("state") in ("accepted", "abandoned"):
        sys.exit(f"cannot write a verdict for a {run_data['state']} run")
    evidence_sha = _evidence_sha(root, args.run, args.wo)
    verifier_token = ""
    if not args.verifier_token and os.environ.get("SANCAI_ALLOW_UNATTESTED_VERDICT") != "1":
        sys.exit(
            "verifier token required; prepare one with "
            "sancai_verdict.py prepare (human-approved via sancai_decide.py)"
        )

    executor_context = run_data.get("executor_context_id") or run_data.get("session_id")
    if args.context_id == executor_context:
        sys.exit("verifier context_id must differ from the executor context")
    claim_context = (run_data.get("claim") or {}).get("context_id")
    if claim_context and args.context_id == claim_context:
        sys.exit("verifier context_id must differ from the claimed executor context")

    findings = [parse_finding(f) for f in args.finding]
    if args.verdict == "pass":
        blockers = [f for f in findings if f.get("severity") in ("blocker", "critical")]
        if blockers:
            sys.exit("pass verdict cannot contain blocker/critical findings")

    if args.verifier_token:
        verifier_token = _consume_verifier_token(
            root, args.run, args.verifier_token, args.wo, evidence_sha
        )

    verdict = {
        "run": args.run,
        "work_order": args.wo,
        "verdict": args.verdict,
        "session_id": args.session_id,
        "context_id": args.context_id,
        "prompt_hash": args.prompt_hash,
        "tools": "read_only",
        "saw_executor_reasoning": False,
        "verifier_token": verifier_token,
        "evidence_sha": evidence_sha,
        "findings": findings,
        "findings_hash": sancai_cards.findings_hash(findings),
        "written_at": now(),
    }
    path = os.path.join(paths.verdicts_dir(root, args.run), f"{args.wo}.json")
    save(path, verdict)
    print(path)


def cmd_list(args):
    root = find_root()
    d = paths.verdicts_dir(root, args.run)
    if not os.path.isdir(d):
        print("no verdicts")
        return
    for name in sorted(os.listdir(d)):
        if not name.endswith(".json"):
            continue
        v = load(os.path.join(d, name))
        fhash = v.get("findings_hash") or sancai_cards.findings_hash(v.get("findings", []))
        print(
            f"{name:24s} {v.get('verdict','?'):5s} findings={len(v.get('findings', []))} "
            f"hash={fhash[:19]} session={v.get('session_id','?')}"
        )


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--run", required=True)
    p.add_argument("--wo", required=True)
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("write")
    p.add_argument("--run", required=True)
    p.add_argument("--wo", required=True)
    p.add_argument("--verdict", choices=["pass", "fail"], required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--context-id", required=True)
    p.add_argument("--prompt-hash", required=True)
    p.add_argument("--verifier-token", default="")
    p.add_argument("--finding", action="append", default=[])
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("list")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

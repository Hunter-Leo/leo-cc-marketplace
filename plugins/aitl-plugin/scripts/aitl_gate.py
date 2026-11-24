#!/usr/bin/env python3
"""Run G0 + G3 and write a gate verdict.

usage:
  aitl_gate.py --run 001-x --wo WO-001 [--apply]
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aitl_state import append_event  # type: ignore  # noqa: E402


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def find_root():
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".aitl")):
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


def evidence_sha(evidence):
    stable = {k: v for k, v in evidence.items() if k not in ("collected_at", "ts")}
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def validate_verifier(v, run_data, evidence):
    problems = []
    if not v:
        problems.append("no verifier verdict")
        return problems
    if v.get("verdict") not in ("pass", "fail"):
        problems.append("verifier verdict must be pass or fail")
    if not v.get("session_id"):
        problems.append("missing verifier session_id")
    if not v.get("context_id"):
        problems.append("missing verifier context_id")
    executor_context = run_data.get("executor_context_id") or run_data.get("session_id")
    if executor_context and v.get("context_id") == executor_context:
        problems.append("verifier context_id equals the executor context")
    claim_context = (run_data.get("claim") or {}).get("context_id")
    if claim_context and v.get("context_id") == claim_context:
        problems.append("verifier context_id equals the claimed executor context")
    if not v.get("prompt_hash"):
        problems.append("missing verifier prompt_hash")
    if v.get("tools") != "read_only":
        problems.append("verifier tools must be read_only")
    if v.get("saw_executor_reasoning") is not False:
        problems.append("verifier must not read executor reasoning")
    if not v.get("evidence_sha"):
        problems.append("missing verifier evidence_sha")
    elif evidence is not None and v.get("evidence_sha") != evidence_sha(evidence):
        problems.append("verifier evidence_sha does not match the current evidence")
    if v.get("written_at"):
        collected = None
        if evidence:
            collected = evidence.get("collected_at") or evidence.get("ts")
        if collected and v["written_at"] < collected:
            problems.append("verifier verdict was written before the evidence was collected")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--wo", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    root = find_root()
    rd = os.path.join(root, ".aitl", "runs", args.run)
    run_path = os.path.join(rd, "run.json")
    run_data = load(run_path)

    # G0: deterministic acceptance checks, harness-owned.
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "aitl_check_ac.py"), "--run", args.run, "--wo", args.wo],
        cwd=root, capture_output=True, text=True,
    )
    evidence_path = os.path.join(rd, "evidence", f"{args.wo}.json")
    evidence = load(evidence_path) if os.path.isfile(evidence_path) else None

    # G3: independent verifier verdict.
    verifier_path = os.path.join(rd, "verdicts", f"{args.wo}.json")
    verifier = load(verifier_path) if os.path.isfile(verifier_path) else None
    problems = validate_verifier(verifier, run_data, evidence)
    blockers = []
    if verifier:
        blockers = [
            f for f in verifier.get("findings", [])
            if f.get("severity") in ("blocker", "critical")
        ]

    if evidence and evidence.get("success"):
        if problems:
            result = "blocked"
            reasons = problems
        elif blockers:
            result = "changes_requested"
            reasons = [f"blocking findings: {blockers}"]
        elif verifier is not None and verifier.get("verdict") == "pass":
            result = "verified"
            reasons = []
        else:
            result = "changes_requested"
            reasons = ["verifier failed"]
    else:
        result = "changes_requested"
        reasons = ["G0 acceptance checks failed"]

    gate = {
        "run": args.run,
        "work_order": args.wo,
        "result": result,
        "reasons": reasons,
        "g0_exit_code": proc.returncode,
        "evidence": os.path.relpath(evidence_path, root) if evidence else None,
        "verifier": os.path.relpath(verifier_path, root) if verifier else None,
        "ts": now(),
    }
    save(os.path.join(rd, "gate", f"{args.wo}.json"), gate)
    append_event(root, args.run, "gate_result", {
        "wo": args.wo,
        "result": result,
        "reasons": reasons,
    })
    print(json.dumps(gate, ensure_ascii=False, indent=2))

    if args.apply and args.wo in run_data.get("work_orders", {}):
        wo = run_data["work_orders"][args.wo]
        if result == "verified" and wo["state"] == "for_review":
            wo["state"] = "verified"
        elif result == "changes_requested" and wo["state"] == "for_review":
            wo["state"] = "changes_requested"
        elif result == "blocked":
            wo["state"] = "blocked"
        run_data["claim"] = None
        run_data["updated_at"] = now()
        if (
            run_data["state"] == "executing"
            and run_data["work_orders"]
            and all(w.get("state") in ("verified", "merged") for w in run_data["work_orders"].values())
        ):
            run_data["state"] = "reviewing"
            print("run: executing -> reviewing (all work orders verified)")
            append_event(root, args.run, "run_transition", {
                "from": "executing",
                "to": "reviewing",
            })
        save(run_path, run_data)
        print(f"applied: {args.wo} -> {wo['state']}")

    sys.exit(0 if result == "verified" else 1)


if __name__ == "__main__":
    main()

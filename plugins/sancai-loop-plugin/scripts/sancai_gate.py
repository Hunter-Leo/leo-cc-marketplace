#!/usr/bin/env python3
"""Run G0 + G3 and write a gate verdict.

usage:
  sancai_gate.py --run 001-x --wo WO-001 [--apply]
"""
import argparse
import datetime
import hashlib
import json
import os

import sancai_paths as paths  # type: ignore
import sancai_control as control  # type: ignore  # noqa: E402
import sancai_science as science  # type: ignore  # noqa: E402

import subprocess
import sys

os.umask(0o077)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sancai_state import append_event, validate_id  # type: ignore  # noqa: E402


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
    if not v.get("verifier_token") and os.environ.get("SANCAI_ALLOW_UNATTESTED_VERDICT") != "1":
        problems.append("missing verifier token id")
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


def _file_sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def validate_attestation(root, run, wo, verdict):
    if os.environ.get("SANCAI_ALLOW_UNATTESTED_VERDICT") == "1":
        return []
    path = os.path.join(paths.l2_dir(root, run), "verifier", f"{wo}.attest.json")
    if not os.path.isfile(path):
        return ["missing verifier stop attestation"]
    try:
        attest = load(path)
    except (OSError, ValueError):
        return ["unreadable verifier stop attestation"]
    problems = []
    if attest.get("run") != run or attest.get("wo") != wo:
        problems.append("verifier attestation does not match this run/work order")
    if "verifier" not in str(attest.get("agent_type", "")).lower():
        problems.append("verifier attestation is not from a verifier subagent")
    verdict_path = os.path.join(paths.verdicts_dir(root, run), f"{wo}.json")
    if os.path.isfile(verdict_path):
        if attest.get("verdict_sha") != _file_sha(verdict_path):
            problems.append("verifier attestation does not match the current verdict")
    else:
        problems.append("verifier verdict missing at attestation check")
    if attest.get("evidence_sha") != verdict.get("evidence_sha"):
        problems.append("verifier attestation does not match the verdict evidence")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--wo", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    root = find_root()
    validate_id(args.run, "run id")
    validate_id(args.wo, "work order id")
    run_path = paths.run_path(root, args.run)
    run_data = load(run_path)
    if args.wo not in (run_data.get("work_orders") or {}):
        sys.exit(f"unknown work order: {args.wo}")

    # G0: deterministic acceptance checks, harness-owned.
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "sancai_check_ac.py"), "--run", args.run, "--wo", args.wo],
        cwd=root, capture_output=True, text=True,
    )
    evidence_path = os.path.join(paths.evidence_dir(root, args.run), f"{args.wo}.json")
    evidence = load(evidence_path) if os.path.isfile(evidence_path) else None

    # G3: independent verifier verdict.
    verifier_path = os.path.join(paths.verdicts_dir(root, args.run), f"{args.wo}.json")
    verifier = load(verifier_path) if os.path.isfile(verifier_path) else None
    problems = validate_verifier(verifier, run_data, evidence)
    if verifier:
        problems += validate_attestation(root, args.run, args.wo, verifier)
    intent = load(paths.intent_path(root, args.run, run_data))
    ctl = control.control_of(run_data)
    budget = control.effective_budget(intent, ctl)
    deadline = control.deadline_reason(ctl, budget)
    if deadline:
        control.pause(ctl, deadline)
        problems.append(deadline)
        append_event(root, args.run, "budget_exhausted", {"reason": deadline})
    fp = control.fingerprint(root, args.run, run_data, intent)
    if control.observe_progress(ctl, fp, budget["max_attempts"]):
        reason = "no-progress lease exhausted"
        control.pause(ctl, reason)
        problems.append(reason)
        append_event(root, args.run, "budget_exhausted", {"reason": reason})
    save(run_path, run_data)
    science_status = science.audit_status(root, args.run, args.wo, intent)
    science_fail = (
        science_status.get("required")
        and science_status.get("verdict") == "fail"
    )
    if science_status.get("required") and not science_status.get("ok") and not science_fail:
        problems.append(
            "science audit: "
            + (science_status.get("reason") or science_status.get("verdict") or "not passed")
        )
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
        elif science_fail:
            result = "changes_requested"
            reasons = ["science audit failed"]
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
    save(os.path.join(paths.gates_dir(root, args.run), f"{args.wo}.json"), gate)
    append_event(root, args.run, "gate_result", {
        "wo": args.wo,
        "result": result,
        "reasons": reasons,
    })
    print(json.dumps(gate, ensure_ascii=False, indent=2))

    if args.apply and ctl.get("status") == "paused":
        sys.exit(f"run is paused: {ctl.get('reason') or 'budget exhausted'}")

    if args.apply and run_data.get("state") in ("accepted", "abandoned"):
        sys.exit(
            f"cannot apply a gate result to a {run_data['state']} run"
        )

    if args.apply and args.wo in run_data.get("work_orders", {}):
        wo = run_data["work_orders"][args.wo]
        if result in ("verified", "changes_requested") and wo["state"] != "for_review":
            sys.exit(
                f"{args.wo} is {wo['state']}; a gate result can only apply to "
                "a for_review work order"
            )
        if result == "verified" and wo["state"] == "for_review":
            wo["state"] = "verified"
        elif result == "changes_requested" and wo["state"] == "for_review":
            wo["state"] = "changes_requested"
        elif result == "blocked":
            if wo["state"] in ("verified", "merged"):
                sys.exit(
                    f"refusing to downgrade {wo['state']} work order {args.wo} to blocked"
                )
            wo["state"] = "blocked"
        claim = run_data.get("claim") or {}
        if claim.get("wo") == args.wo:
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

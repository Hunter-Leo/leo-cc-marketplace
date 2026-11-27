#!/usr/bin/env python3
"""Run acceptance checks and write harness-owned evidence.

usage:
  sancai_check_ac.py [--run RUN] [--wo WO]
"""
import argparse
import datetime
import hashlib
import json
import os

import sancai_paths as paths  # type: ignore
from sancai_state import validate_id  # type: ignore  # noqa: E402

import re
import subprocess
import sys

import sancai_change as change  # type: ignore
import sancai_tests as tests  # type: ignore

os.umask(0o077)

DEFAULT_CHECK_TIMEOUT = 1800


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def normalize_output(out):
    """Remove run-to-run noise so evidence remains stable across G0 reruns."""
    out = re.sub(r"Ran \d+ tests in [0-9.]+s", "Ran N tests in <time>s", out)
    out = re.sub(r"in [0-9.]+ seconds", "in <time> seconds", out)
    return out


def find_root():
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".sancai")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.getcwd()
        cur = parent


def active_run(root):
    path = paths.active_path(root)
    if not os.path.isfile(path):
        sys.exit("no active Sancai run")
    return open(path, encoding="utf-8").read().strip()


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


def run_check(check, workdir, timeout=DEFAULT_CHECK_TIMEOUT):
    cmd = check.get("run", "")
    expect = check.get("expect", "")
    kind = check.get("check", "command")
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=workdir, capture_output=True, text=True, timeout=timeout,
        )
        returncode = proc.returncode
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        out = stdout + stderr
    stable_out = normalize_output(out)

    if kind == "invariant" or "matches == 0" in expect:
        matches = len([line for line in out.splitlines() if line.strip()])
        ok = matches == 0
        detail = f"matches={matches}"
    elif "exit_code != 0" in expect:
        ok = returncode != 0
        detail = f"exit_code={returncode}"
    else:
        ok = returncode == 0
        detail = f"exit_code={returncode}"
    if timed_out:
        ok = False
        detail += "; timed_out"

    return {
        "id": check.get("id", "?"),
        "command": cmd,
        "expected": expect,
        "exit_code": returncode,
        "detail": detail,
        "passed": ok,
        "output_sha": hashlib.sha256(stable_out.encode()).hexdigest(),
        "output_head": stable_out[:400],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--wo")
    args = ap.parse_args()

    root = find_root()
    run = args.run or active_run(root)
    validate_id(run, "run")
    rd = paths.run_dir(root, run)
    run_data = load(paths.run_path(root, run))
    intent = load(paths.intent_path(root, run, run_data))

    wo_id = args.wo
    if not wo_id:
        claim = run_data.get("claim") or {}
        wo_id = claim.get("wo", "GLOBAL")
    validate_id(wo_id, "work order")

    out_path = os.path.join(paths.evidence_dir(root, run), f"{wo_id}.json")
    try:
        test_policy = change.validate_test_policy(intent.get("test_policy"), run)
        change_policy = change.validate_change_policy(intent.get("change_policy"))
    except change.ChangeError as exc:
        evidence = {
            "run": run,
            "work_order": wo_id,
            "collected_by": "harness/sancai_check_ac",
            "collected_at": now(),
            "diff_sha": "",
            "checks": [],
            "hidden": [],
            "ac_passed": 0,
            "ac_total": 0,
            "hidden_passed": 0,
            "hidden_total": 0,
            "success": False,
            "policy_error": str(exc),
        }
        save(out_path, evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        sys.exit(1)

    changed_before = change.changed_files(root) if change_policy is not None else []
    frozen = (
        change.freeze_expected_changes(root, run, wo_id, changed_before)
        if change_policy is not None else None
    )

    try:
        check_timeout = int(os.environ.get("SANCAI_CHECK_TIMEOUT", DEFAULT_CHECK_TIMEOUT))
    except ValueError:
        check_timeout = DEFAULT_CHECK_TIMEOUT
    if check_timeout < 1:
        check_timeout = DEFAULT_CHECK_TIMEOUT

    checks = [run_check(c, root, check_timeout) for c in intent.get("acceptance", [])]
    hidden = [run_check(c, root, check_timeout) for c in intent.get("hidden_checks", [])]
    ac_passed = sum(1 for c in checks if c["passed"])
    ac_total = len(checks)
    hidden_passed = sum(1 for c in hidden if c["passed"])
    hidden_total = len(hidden)

    coverage_policy = test_policy.get("coverage") if test_policy else None
    if coverage_policy and not coverage_policy.get("command"):
        tests.remove_report(root, coverage_policy.get("report"))
    test_info = tests.run_tests(root, test_policy) if test_policy else None
    coverage_info = (
        tests.run_coverage(
            root, coverage_policy,
            test_policy.get("timeout_seconds", 1800),
        )
        if coverage_policy else None
    )
    changed_after = change.changed_files(root) if change_policy is not None else []
    view = (
        change.classify(root, run, wo_id, intent, changed_after, test_info, frozen)
        if change_policy is not None else None
    )

    diff = subprocess.run(
        ["git", "-C", root, "diff", "HEAD", "--binary"], capture_output=True
    )
    diff_sha = hashlib.sha256(diff.stdout).hexdigest()

    base_success = (
        ac_total > 0
        and ac_passed == ac_total
        and hidden_passed == hidden_total
    )
    test_success = True
    coverage_success = True
    integrity_success = True
    if test_info is not None:
        if test_info.get("timed_out") or test_info.get("report_invalid"):
            test_success = False
        if view is None:
            test_success = test_success and not test_info.get("failed_ids")
            if test_info.get("exit_code") not in (0, None):
                test_success = False
        else:
            test_success = test_success and not view.get("unclassified") and not view.get("stale")
            if test_info.get("exit_code") not in (0, None) and not test_info.get("failed_ids"):
                test_success = False
    if coverage_info is not None:
        coverage_success = bool(coverage_info.get("passed"))
        if coverage_info.get("exit_code") not in (0, None):
            coverage_success = False
    if view is not None:
        integrity_success = not view.get("integrity_violations")

    evidence = {
        "run": run,
        "work_order": wo_id,
        "collected_by": "harness/sancai_check_ac",
        "collected_at": now(),
        "diff_sha": diff_sha,
        "checks": checks,
        "hidden": hidden,
        "ac_passed": ac_passed,
        "ac_total": ac_total,
        "hidden_passed": hidden_passed,
        "hidden_total": hidden_total,
        "success": base_success and test_success and coverage_success and integrity_success,
    }
    if test_info is not None:
        evidence["tests"] = {
            "command": test_info.get("command"),
            "exit_code": test_info.get("exit_code"),
            "timed_out": test_info.get("timed_out", False),
            "report": test_info.get("report"),
            "report_sha": test_info.get("report_sha"),
            "total": test_info.get("total", 0),
            "passed": test_info.get("passed", 0),
            "failed": test_info.get("failed", 0),
            "skipped": test_info.get("skipped", 0),
            "failures": [
                {
                    "id": test_id,
                    "expected_by": (view or {}).get("expected_failures", {}).get(test_id),
                }
                for test_id in (test_info.get("failed_ids") or [])
            ],
            "unclassified": (
                (view or {}).get("unclassified")
                if view is not None else list(test_info.get("failed_ids") or [])
            ),
            "stale": (view or {}).get("stale", []),
            "output_sha": test_info.get("output_sha"),
            "output_head": test_info.get("output_head"),
        }
        if test_info.get("report_invalid"):
            evidence["tests"]["report_invalid"] = True
        if test_info.get("report_error"):
            evidence["tests"]["report_error"] = test_info["report_error"]
    if coverage_info is not None:
        evidence["coverage"] = {
            "report": coverage_info.get("report"),
            "report_sha": coverage_info.get("report_sha"),
            "total_percent": coverage_info.get("total_percent"),
            "core_percent": coverage_info.get("core_percent"),
            "minimum_core_percent": coverage_info.get("minimum_core_percent"),
            "enforced": coverage_info.get("enforced"),
            "passed": coverage_info.get("passed"),
        }
        if coverage_info.get("report_invalid"):
            evidence["coverage"]["report_invalid"] = True
    if view is not None:
        evidence["changed_files"] = view.get("changed_files", [])
        evidence["protected_changes"] = view.get("protected_changes", [])
        evidence["integrity_violations"] = view.get("integrity_violations", [])
        evidence["expected_changes"] = view.get("expected_changes", [])
        evidence["expected_change_manifest_sha"] = (
            "sha256:" + view["manifest_sha"] if view.get("manifest_sha") else None
        )
        evidence["regressions"] = view.get("regressions", [])
        evidence["science_required"] = view.get("science_required", False)

    if os.path.isfile(out_path):
        old = load(out_path)
        stable = lambda e: {k: v for k, v in e.items() if k not in ("collected_at", "ts")}
        if stable(old) == stable(evidence):
            evidence["collected_at"] = old.get("collected_at", evidence["collected_at"])
    save(out_path, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    sys.exit(0 if evidence["success"] else 1)


if __name__ == "__main__":
    main()

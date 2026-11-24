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

import re
import subprocess
import sys

os.umask(0o077)


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


def run_check(check, workdir):
    cmd = check.get("run", "")
    expect = check.get("expect", "")
    kind = check.get("check", "command")
    proc = subprocess.run(cmd, shell=True, cwd=workdir, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    stable_out = normalize_output(out)

    if kind == "invariant" or "matches == 0" in expect:
        matches = len([line for line in out.splitlines() if line.strip()])
        ok = matches == 0
        detail = f"matches={matches}"
    elif "exit_code != 0" in expect:
        ok = proc.returncode != 0
        detail = f"exit_code={proc.returncode}"
    else:
        ok = proc.returncode == 0
        detail = f"exit_code={proc.returncode}"

    return {
        "id": check.get("id", "?"),
        "command": cmd,
        "expected": expect,
        "exit_code": proc.returncode,
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
    rd = paths.run_dir(root, run)
    run_data = load(paths.run_path(root, run))
    intent = load(paths.intent_path(root, run, run_data))

    wo_id = args.wo
    if not wo_id:
        claim = run_data.get("claim") or {}
        wo_id = claim.get("wo", "GLOBAL")

    checks = [run_check(c, root) for c in intent.get("acceptance", [])]
    hidden = [run_check(c, root) for c in intent.get("hidden_checks", [])]
    ac_passed = sum(1 for c in checks if c["passed"])
    ac_total = len(checks)
    hidden_passed = sum(1 for c in hidden if c["passed"])
    hidden_total = len(hidden)

    diff = subprocess.run(
        ["git", "-C", root, "diff", "HEAD", "--binary"], capture_output=True
    )
    diff_sha = hashlib.sha256(diff.stdout).hexdigest()

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
        "success": ac_total > 0 and ac_passed == ac_total,
    }

    out_path = os.path.join(paths.evidence_dir(root, run), f"{wo_id}.json")
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

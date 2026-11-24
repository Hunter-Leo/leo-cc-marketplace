#!/usr/bin/env python3
"""Run acceptance checks and write harness-owned evidence.

usage: check_ac.py TASK_JSON RUN_DIR
exit: 0 if all acceptance checks pass, 1 otherwise
"""
import datetime
import json
import os
import subprocess
import sys


def run_check(check, workdir):
    cmd = check.get("run", "")
    expect = check.get("expect", "")
    kind = check.get("check", "command")
    proc = subprocess.run(
        cmd, shell=True, cwd=workdir, capture_output=True, text=True
    )
    out = (proc.stdout or "") + (proc.stderr or "")

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
        "output_sha": __import__("hashlib").sha256(out.encode()).hexdigest(),
        "output_head": out[:400],
    }


def main():
    task_path, run_dir = sys.argv[1], sys.argv[2]
    task = json.load(open(task_path, encoding="utf-8"))
    workdir = os.path.join(run_dir, "work")
    if not os.path.isdir(workdir):
        sys.exit(f"workdir not found: {workdir}")

    checks = [run_check(c, workdir) for c in task.get("acceptance", [])]
    hidden = [run_check(c, workdir) for c in task.get("hidden_checks", [])]

    ac_passed = sum(1 for c in checks if c["passed"])
    ac_total = len(checks)
    hidden_passed = sum(1 for c in hidden if c["passed"])
    hidden_total = len(hidden)

    evidence = {
        "task_id": task["id"],
        "collected_by": "eval/check_ac.py",
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "workdir": workdir,
        "checks": checks,
        "hidden": hidden,
        "ac_passed": ac_passed,
        "ac_total": ac_total,
        "hidden_passed": hidden_passed,
        "hidden_total": hidden_total,
        "success": ac_total > 0 and ac_passed == ac_total,
    }
    out = os.path.join(run_dir, "ac.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    sys.exit(0 if evidence["success"] else 1)


if __name__ == "__main__":
    main()

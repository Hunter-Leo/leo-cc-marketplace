#!/usr/bin/env python3
"""Run test/coverage commands and parse their structured reports."""
import hashlib
import json
import os
import re
import subprocess

import sancai_change as change  # type: ignore


def normalize_output(out):
    out = re.sub(r"Ran \d+ tests in [0-9.]+s", "Ran N tests in <time>s", out)
    out = re.sub(r"in [0-9.]+ seconds", "in <time> seconds", out)
    return out


def _text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_command(root, command, timeout):
    try:
        proc = subprocess.run(
            command, shell=True, cwd=root, capture_output=True, text=True,
            errors="replace", timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return {
            "exit_code": proc.returncode,
            "timed_out": False,
            "output": normalize_output(out),
        }
    except subprocess.TimeoutExpired as exc:
        out = _text(exc.stdout) + _text(exc.stderr)
        return {
            "exit_code": 124,
            "timed_out": True,
            "output": normalize_output(out),
        }


def _report_path(root, rel):
    return os.path.join(root, rel) if rel else None


def _remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def remove_report(root, rel):
    """Delete a report before a command writes it, so stale data cannot pass."""
    path = _report_path(root, rel)
    if path:
        _remove(path)


def _report_meta(path, rel):
    if not path or not os.path.isfile(path):
        return {"report": rel, "report_sha": None, "report_invalid": bool(rel)}
    return {
        "report": rel,
        "report_sha": "sha256:" + change.sha_file(path),
        "report_invalid": False,
    }


def _normalize_outcome(value):
    value = str(value or "").lower()
    return {
        "success": "passed",
        "pass": "passed",
        "failure": "failed",
        "fail": "failed",
        "error": "error",
        "skipped": "skipped",
        "skip": "skipped",
        "xfail": "xfail",
    }.get(value, value)


def parse_test_report(path):
    data = change.load(path)
    if not isinstance(data, dict):
        raise ValueError("test report must be a JSON object")
    outcomes = []
    for item in data.get("tests") or []:
        if not isinstance(item, dict):
            raise ValueError("test report tests entries must be objects")
        test_id = item.get("id") or item.get("nodeid") or "<unknown>"
        outcome = _normalize_outcome(item.get("outcome") or item.get("result") or "unknown")
        if outcome not in ("passed", "failed", "error", "skipped", "xfail"):
            raise ValueError(f"unsupported test outcome: {outcome!r}")
        outcomes.append({"id": str(test_id), "outcome": outcome})
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    passed = data.get("passed", summary.get("passed"))
    failed = data.get("failed", summary.get("failed"))
    skipped = data.get("skipped", summary.get("skipped"))
    errors = data.get("error", summary.get("error"))
    if passed is None:
        passed = sum(1 for item in outcomes if item["outcome"] == "passed")
    if failed is None:
        failed = sum(1 for item in outcomes if item["outcome"] in ("failed", "error"))
    if skipped is None:
        skipped = sum(1 for item in outcomes if item["outcome"] == "skipped")
    if errors is None:
        errors = sum(1 for item in outcomes if item["outcome"] == "error")
    failed = int(failed) + int(errors)
    total = data.get("total", summary.get("total"))
    if total is None:
        total = int(passed) + int(failed) + int(skipped)
    failed_ids = sorted({
        item["id"] for item in outcomes if item["outcome"] in ("failed", "error")
    })
    return {
        "total": int(total),
        "passed": int(passed),
        "failed": int(failed),
        "skipped": int(skipped),
        "failed_ids": failed_ids,
        "outcomes": outcomes,
    }


def run_tests(root, test_policy):
    rel = test_policy.get("report")
    path = _report_path(root, rel)
    if path:
        _remove(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
    result = run_command(root, test_policy["command"], test_policy.get("timeout_seconds", 1800))
    meta = _report_meta(path, rel)
    parsed = None
    if path and not meta["report_invalid"]:
        try:
            parsed = parse_test_report(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            meta["report_invalid"] = True
            meta["report_error"] = str(exc)
    if parsed is None:
        parsed = {"total": 0, "passed": 0, "failed": 0, "skipped": 0,
                  "failed_ids": [], "outcomes": []}
    out = {
        "command": test_policy["command"],
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "report": rel,
        "report_sha": meta["report_sha"],
        "report_invalid": meta["report_invalid"],
        "total": parsed["total"],
        "passed": parsed["passed"],
        "failed": parsed["failed"],
        "skipped": parsed["skipped"],
        "failed_ids": parsed["failed_ids"],
        "outcomes": parsed["outcomes"],
        "output_sha": hashlib.sha256(result["output"].encode()).hexdigest(),
        "output_head": result["output"][:400],
    }
    if meta.get("report_error"):
        out["report_error"] = meta["report_error"]
    return out


def parse_coverage(path):
    data = change.load(path)
    if not isinstance(data, dict):
        raise ValueError("coverage report must be a JSON object")
    files = {}
    for name, info in (data.get("files") or {}).items():
        summary = (info or {}).get("summary") or {}
        covered = summary.get("covered_lines")
        statements = summary.get("num_statements")
        if covered is None or statements is None:
            files[str(name)] = {"covered": 0, "statements": 0, "missing": True}
            continue
        files[str(name)] = {
            "covered": int(covered),
            "statements": int(statements),
        }
    totals = data.get("totals") or {}
    total_covered = totals.get("covered_lines")
    total_statements = totals.get("num_statements")
    if total_covered is None:
        total_covered = sum(item["covered"] for item in files.values())
    if total_statements is None:
        total_statements = sum(item["statements"] for item in files.values())
    percent = totals.get("percent_covered")
    if percent is None:
        percent = (
            100.0 * total_covered / total_statements if total_statements else 0.0
        )
    return {
        "files": files,
        "total_covered": int(total_covered),
        "total_statements": int(total_statements),
        "total_percent": round(float(percent), 2),
    }


def _relative(root, name):
    if os.path.isabs(name):
        try:
            return os.path.relpath(name, root).replace(os.sep, "/")
        except ValueError:
            return name.replace(os.sep, "/")
    return name.replace(os.sep, "/")


def _disk_core_files(root, core_globs):
    """Find source files covered by core_globs, so missing report entries fail."""
    skip = {".git", ".sancai", "node_modules", ".venv", "venv",
            "__pycache__", "dist", "build"}
    roots = set()
    for pattern in core_globs:
        parts = pattern.split("/")
        literal = []
        for part in parts:
            if any(ch in part for ch in "*?["):
                break
            literal.append(part)
        if len(literal) == len(parts):
            roots.add(os.path.dirname("/".join(literal)) or ".")
        else:
            roots.add("/".join(literal) or ".")
    found = set()
    for base in roots:
        path = os.path.join(root, base)
        if not os.path.isdir(path):
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [name for name in dirnames if name not in skip]
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                rel = rel.replace(os.sep, "/")
                if any(change.glob_match(rel, pattern) for pattern in core_globs):
                    found.add(rel)
    return found


def coverage_summary(root, report, core_globs):
    core_files = [
        (name, item) for name, item in report["files"].items()
        if any(change.glob_match(name, pattern) for pattern in core_globs)
    ]
    if not core_files:
        return 0.0
    if any(item.get("missing") for _, item in core_files):
        return 0.0
    measured = {name for name, _ in core_files}
    if _disk_core_files(root, core_globs) - measured:
        return 0.0
    covered = sum(item["covered"] for _, item in core_files)
    statements = sum(item["statements"] for _, item in core_files)
    return round(100.0 * covered / statements, 2) if statements else 0.0


def run_coverage(root, coverage, timeout=None):
    rel = coverage.get("report")
    path = _report_path(root, rel)
    if coverage.get("command"):
        _remove(path)
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        result = run_command(
            root, coverage["command"],
            timeout or coverage.get("timeout_seconds", 1800),
        )
    else:
        result = {"exit_code": None, "timed_out": False, "output": ""}
    invalid = not path or not os.path.isfile(path)
    parsed = None
    if not invalid:
        try:
            parsed = parse_coverage(path)
        except (OSError, ValueError, json.JSONDecodeError):
            invalid = True
    enforce = coverage.get("enforce", True)
    minimum = coverage.get("minimum_core_percent", 80)
    if parsed:
        files = {_relative(root, name): item for name, item in parsed["files"].items()}
        parsed["files"] = files
        core = coverage_summary(root, parsed, coverage.get("core_globs") or [])
        total = parsed["total_percent"]
    else:
        core = 0.0
        total = 0.0
    passed = (not enforce) or (not invalid and core >= minimum)
    return {
        "report": rel,
        "report_sha": "sha256:" + change.sha_file(path) if path and os.path.isfile(path) else None,
        "total_percent": total,
        "core_percent": core,
        "minimum_core_percent": minimum,
        "enforced": enforce,
        "passed": passed,
        "report_invalid": invalid,
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "output_sha": hashlib.sha256(result["output"].encode()).hexdigest(),
        "output_head": result["output"][:400],
    }

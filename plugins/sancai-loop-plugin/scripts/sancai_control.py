#!/usr/bin/env python3
"""Loop-control state and deterministic progress fingerprints.

The control plane is intentionally small: one run-level attempt budget, one
human-round budget, and one wall-clock deadline. Per-WO/verifier/no-progress
limits are derived so the signed intent does not grow a parameter matrix.
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys

import sancai_paths as paths  # type: ignore

DEFAULT_BUDGET = {
    "max_attempts": 10,
    "max_human_rounds": 6,
    "deadline_seconds": 172800,
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _iso(value):
    try:
        return datetime.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _positive(raw, key, minimum, label):
    if raw is None:
        return DEFAULT_BUDGET[key]
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < minimum:
        sys.exit(f"intent.budget.{label} must be an integer >= {minimum}")
    return raw


def budget_of(intent):
    """Return the three-field budget, filling defaults and validating types."""
    raw = intent.get("budget") or {}
    if not isinstance(raw, dict):
        sys.exit("intent.budget must be an object")
    return {
        "max_attempts": _positive(raw.get("max_attempts"), "max_attempts", 1, "max_attempts"),
        "max_human_rounds": _positive(
            raw.get("max_human_rounds"), "max_human_rounds", 1, "max_human_rounds"
        ),
        "deadline_seconds": _positive(
            raw.get("deadline_seconds"), "deadline_seconds", 60, "deadline_seconds"
        ),
    }


def new_control(at=None):
    stamp = at or now()
    return {
        "status": "active",
        "reason": "",
        "since": stamp,
        "started_at": stamp,
        "paused_at": "",
        "attempts": 0,
        "human_rounds": 0,
        "no_progress_streak": 0,
        "last_progress_fingerprint": "",
        "last_progress_at": stamp,
        "grants": [],
    }


def control_of(run_data):
    """Return the mutable control block, initializing old runs lazily."""
    control = run_data.setdefault("control", new_control(run_data.get("created_at")))
    control.setdefault("status", "active")
    control.setdefault("reason", "")
    control.setdefault("since", run_data.get("created_at") or now())
    control.setdefault("started_at", control.get("since") or run_data.get("created_at") or now())
    control.setdefault("paused_at", "")
    control.setdefault("attempts", 0)
    control.setdefault("human_rounds", 0)
    control.setdefault("no_progress_streak", 0)
    control.setdefault("last_progress_fingerprint", "")
    control.setdefault("last_progress_at", control.get("since") or now())
    control.setdefault("grants", [])
    return control


def effective_budget(intent, control):
    budget = budget_of(intent)
    for grant in control.get("grants") or []:
        if not isinstance(grant, dict):
            continue
        key = grant.get("field")
        value = grant.get("to")
        if key in budget and isinstance(value, int) and not isinstance(value, bool):
            budget[key] = max(budget[key], value)
    return budget


def pause(control, reason):
    control["status"] = "paused"
    control["reason"] = reason
    control["paused_at"] = now()


def deadline_reason(control, budget):
    started = _iso(control.get("started_at") or control.get("since"))
    if started is None:
        return None
    elapsed = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
    if elapsed >= budget["deadline_seconds"]:
        return (
            f"deadline exceeded: {int(elapsed)}s >= "
            f"{budget['deadline_seconds']}s"
        )
    return None


def consume_attempt(control, budget, wo):
    """Consume one run-level attempt. Returns (ok, reason)."""
    if control.get("status") == "paused":
        return False, f"run is paused: {control.get('reason') or 'budget exhausted'}"
    reason = deadline_reason(control, budget)
    if reason:
        return False, reason
    if control.get("attempts", 0) >= budget["max_attempts"]:
        return False, (
            f"attempt budget exhausted: {control.get('attempts', 0)}"
            f"/{budget['max_attempts']}"
        )
    control["attempts"] = control.get("attempts", 0) + 1
    wo["attempts"] = wo.get("attempts", 0) + 1
    return True, ""


def consume_human_round(control, budget, action):
    if control.get("status") == "paused":
        return True, ""
    if control.get("human_rounds", 0) >= budget["max_human_rounds"]:
        return False, (
            f"human-round budget exhausted: {control.get('human_rounds', 0)}"
            f"/{budget['max_human_rounds']}; only accept/abandon/budget grant is allowed"
        )
    control["human_rounds"] = control.get("human_rounds", 0) + 1
    return True, ""


def no_progress_cap(max_attempts):
    return max(2, int(max_attempts) // 3)


def _file_sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


_VOLATILE_KEYS = {
    "collected_at", "written_at", "created_at", "updated_at",
    "started_at", "finished_at", "timestamp", "duration_ms",
}


def _strip_volatile(value):
    if isinstance(value, dict):
        return {
            key: _strip_volatile(item)
            for key, item in value.items()
            if key not in _VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    return value


def _semantic_sha(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _file_sha(path)
    clean = _strip_volatile(data)
    return hashlib.sha256(
        json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _dir_hashes(directory, names):
    out = {}
    for name in names:
        path = os.path.join(directory, f"{name}.json")
        if os.path.isfile(path):
            out[name] = _semantic_sha(path)
    return out


def _open_escalations(root, run):
    directory = paths.escalations_dir(root, run)
    out = []
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as f:
                esc = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if esc.get("status") == "open":
            out.append(esc.get("id") or name[:-5])
    return out


def _last_decision(root, run):
    path = paths.events_path(root, run)
    if not os.path.isfile(path):
        return ""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        if any(key in line for key in ("decision_recorded", "intent_signed", "human_decision")):
            return line
    return ""


def _dir_results(directory, names):
    out = {}
    for name in names:
        path = os.path.join(directory, f"{name}.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            out[name] = "unreadable"
            continue
        out[name] = data.get("result") or data.get("verdict")
    return out


def fingerprint(root, run, run_data, intent=None):
    """Hash the facts that would make a retry meaningful."""
    work_orders = run_data.get("work_orders") or {}
    wo_ids = sorted(work_orders)
    evidence = _dir_hashes(paths.evidence_dir(root, run), wo_ids)
    verdicts = _dir_hashes(paths.verdicts_dir(root, run), wo_ids)
    gates = _dir_results(paths.gates_dir(root, run), wo_ids)
    try:
        diff = subprocess.run(
            ["git", "-C", root, "diff", "HEAD", "--binary"],
            capture_output=True,
        )
        diff_sha = hashlib.sha256(diff.stdout).hexdigest()
    except OSError:
        diff_sha = ""
    payload = {
        "state": run_data.get("state"),
        "work_orders": {
            wid: {
                "state": work_orders[wid].get("state"),
                "req": work_orders[wid].get("req"),
            }
            for wid in wo_ids
        },
        "evidence": evidence,
        "verdicts": verdicts,
        "gates": gates,
        "diff_sha": diff_sha,
        "open_escalations": _open_escalations(root, run),
        "requirements": (intent or {}).get("requirements") or [],
        "revision": (intent or {}).get("revision"),
        "last_decision": _last_decision(root, run),
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def observe_progress(control, fp, max_attempts):
    """Update the no-progress streak. Returns True when the lease is exhausted."""
    if fp and fp == control.get("last_progress_fingerprint"):
        control["no_progress_streak"] = control.get("no_progress_streak", 0) + 1
    else:
        control["last_progress_fingerprint"] = fp
        control["no_progress_streak"] = 0
        control["last_progress_at"] = now()
    return control["no_progress_streak"] >= no_progress_cap(max_attempts)

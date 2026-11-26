#!/usr/bin/env python3
"""Sancai hooks (guarded: no-op when .sancai is absent).

modes:
  --pre-tool     capability check for active executing run
  --post-tool    append evidence event
  --subagent-stop require verdict while a claim is active
  --stop         block ending a run that is not accepted/abandoned
  --precompact   no-op in MVP
  --status-line  UserPromptSubmit: inject one deduplicated status line
"""
import argparse
import datetime
import hashlib
import json
import os

import sancai_paths as paths  # type: ignore

import shlex
import sys

os.umask(0o077)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sancai_capability import check as cap_check  # type: ignore  # noqa: E402
from sancai_graph import status_object  # type: ignore  # noqa: E402

STATUS: dict[str, str | None] = {"root": None, "run": None}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def find_root(cwd=None):
    cur = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".sancai")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.getcwd()
        cur = parent


def read_payload():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def active_run(root):
    path = paths.active_path(root)
    if not os.path.isfile(path):
        return None
    raw = open(path, encoding="utf-8").read().strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("run"):
            return data["run"]
    except json.JSONDecodeError:
        pass
    return raw


def allow():
    sys.exit(0)


def status_line(root, run):
    """One-line human-readable status, or '' when it cannot be built."""
    try:
        status = status_object(root, run)
    except Exception:
        return ""
    if not status:
        return ""
    line = (
        f"Sancai {status['run']} | {status['state']} | {status['stage']} | "
        f"{status['progress']} | next={status['next']['action']}"
    )
    if status["open_escalations"]:
        line += f" | esc={','.join(status['open_escalations'])}"
    return line[:120]


def _status_suffix():
    line = status_line(STATUS.get("root"), STATUS.get("run"))
    return f"\n{line}" if line else ""


def _fingerprint(root, run):
    try:
        status = status_object(root, run)
    except Exception:
        return None
    if not status:
        return None
    claim = status.get("claim") or {}
    return "|".join(
        str(value) for value in (
            run,
            status.get("state"),
            claim.get("wo") or "",
            (status.get("progress_detail") or {}).get("verified", 0),
            ",".join(status.get("open_escalations") or []),
            (status.get("next") or {}).get("action"),
        )
    )


def _write_status_last(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def emit_status_line(root):
    """UserPromptSubmit: inject one line, deduplicated by state fingerprint."""
    run = active_run(root)
    if not run:
        return
    fingerprint = _fingerprint(root, run)
    if fingerprint is None:
        return
    path = paths.status_last_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            last = json.load(f)
    except (OSError, json.JSONDecodeError):
        last = {}
    same = last.get("fingerprint") == fingerprint
    turns = int(last.get("turns_since_output", 0))
    if same and turns < 2:
        _write_status_last(path, {"fingerprint": fingerprint, "turns_since_output": turns + 1})
        return
    line = status_line(root, run)
    if not line:
        return
    _write_status_last(path, {"fingerprint": fingerprint, "turns_since_output": 0})
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": line,
        }
    }
    if os.environ.get("SANCAI_STATUS_FALLBACK") == "1":
        output = {"systemMessage": line}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


def deny(message):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message + _status_suffix(),
        }
    }))
    sys.exit(0)


def ask(message):
    """Defer to Claude Code's native permission prompt.

    The human clicks Allow/Deny; no command copy or TTY wrapper is needed.
    """
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": message + _status_suffix(),
        }
    }))
    sys.exit(0)


def decision_call(command):
    """Return (subcommand, options) for a native-UI decision call."""
    if not command:
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for i, token in enumerate(tokens):
        if os.path.basename(token) != "sancai_decide.py":
            continue
        sub = tokens[i + 1] if i + 1 < len(tokens) else ""
        opts = {}
        j = i + 2
        while j < len(tokens):
            token = tokens[j]
            if token.startswith("--"):
                key = token[2:]
                if j + 1 < len(tokens) and not tokens[j + 1].startswith("--"):
                    opts[key] = tokens[j + 1]
                    j += 2
                else:
                    opts[key] = True
                    j += 1
            else:
                j += 1
        return sub, opts
    return None


def ask_decision(decision, run):
    """Show one native prompt for a sancai_decide.py call."""
    sub, opts = decision
    run_arg = opts.get("run") or run
    card = opts.get("card-id") or "<missing card>"
    target = opts.get("id") or ""
    detail = ""
    if sub == "mint":
        detail = f" action={opts.get('action')} diff={opts.get('diff-sha')}"
    elif sub == "abandon":
        detail = f" reason={opts.get('reason')}"
    elif sub == "verifier-prepare":
        detail = f" work_order={opts.get('wo')}"
    ask(
        f"Sancai human decision: {sub} run={run_arg}"
        + (f" target={target}" if target else "")
        + detail
        + f" card={card}. "
        "Allow only if the card above matches what you intend."
    )


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pre-tool", action="store_true")
    g.add_argument("--post-tool", action="store_true")
    g.add_argument("--subagent-stop", action="store_true")
    g.add_argument("--stop", action="store_true")
    g.add_argument("--precompact", action="store_true")
    g.add_argument("--status-line", action="store_true")
    args = ap.parse_args()

    payload = read_payload()
    root = find_root(payload.get("cwd"))
    if args.status_line:
        emit_status_line(root)

    run = active_run(root)
    if not run:
        allow()
    assert run is not None
    STATUS["root"] = root
    STATUS["run"] = run

    rd = paths.run_dir(root, run)
    run_path = paths.run_path(root, run)
    if not os.path.isfile(run_path):
        reason = f"Sancai active run {run} has no {run_path}; refusing to continue blindly"
        if args.pre_tool:
            deny(reason)
        if args.stop:
            block(reason)
        allow()
        return
    try:
        run_data = json.load(open(run_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        reason = f"cannot read Sancai run state {run_path}: {exc}"
        if args.pre_tool:
            deny(reason)
        if args.stop:
            block(reason)
        allow()
        return

    if args.pre_tool:
        tool = payload.get("tool_name", "")
        ti = payload.get("tool_input") or {}
        command = ti.get("command")
        path = ti.get("file_path") or ti.get("path")
        state = run_data.get("state")
        claim = run_data.get("claim")

        if state == "executing" and claim:
            if tool == "Bash":
                decision = decision_call(command)
                if decision:
                    ask_decision(decision, run)
            ok, reason = cap_check(root, tool, command, path, run)
            if not ok:
                deny(f"Sancai capability denied: {reason}")
            allow()

        # Outside an active execution claim, code writes are denied. The only
        # exception is drafting the intent during planning.
        if tool in ("Write", "Edit", "NotebookEdit"):
            intent_path = paths.intent_path(root, run, run_data)
            if state == "planning" and path and os.path.realpath(path) == os.path.realpath(intent_path):
                allow()
            deny(f"Sancai: code writes are not allowed while state={state}")

        # Harness scripts and read-only commands remain available; mutations
        # such as git add/commit require an active claim and are denied here.
        if tool == "Bash":
            ok, reason = cap_check(root, tool, command, path, run)
            if not ok:
                deny(f"Sancai capability denied: {reason}")
            decision = decision_call(command)
            if decision:
                ask_decision(decision, run)
            allow()

        allow()

    if args.post_tool:
        ev = paths.events_path(root, run)
        response = payload.get("tool_response") or payload.get("tool_result") or ""
        try:
            response_bytes = json.dumps(response, sort_keys=True, ensure_ascii=False).encode()
        except TypeError:
            response_bytes = str(response).encode()
        rec = {
            "ts": now(),
            "run": run,
            "event": "tool_used",
            "actor": "agent",
            "meta": {
                "tool": payload.get("tool_name"),
                "session_id": payload.get("session_id"),
                "input_keys": sorted((payload.get("tool_input") or {}).keys()),
                "command": (payload.get("tool_input") or {}).get("command"),
                "path": (payload.get("tool_input") or {}).get("file_path") or (payload.get("tool_input") or {}).get("path"),
                "response_sha": hashlib.sha256(response_bytes).hexdigest(),
            },
        }
        with open(ev, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        allow()

    if args.subagent_stop:
        claim = run_data.get("claim")
        if not claim:
            allow()
        wo = claim.get("wo") or "UNKNOWN"
        verdict = os.path.join(paths.verdicts_dir(root, run), f"{wo}.json")
        if not os.path.isfile(verdict):
            block(f"Sancai: subagent stopped without verdict for {wo}; write .sancai/runs/{run}/L2-harness/verdicts/{wo}.json")
        allow()

    if args.stop:
        if os.environ.get("SANCAI_SKIP_STOP") == "1":
            allow()
        if run_data.get("state") in ("accepted", "abandoned", "reviewing"):
            allow()
        sid = payload.get("session_id")
        run_sid = run_data.get("session_id")
        if not run_sid:
            block(
                f"Sancai run {run} has no recorded session id; refuse to end it blindly. "
                f"Finish with /sancai accept, /sancai abandon \"...\", or set SANCAI_SKIP_STOP=1 if you accept the risk."
            )
        if not sid:
            block(
                f"Sancai stop hook has no session id for run {run}; refuse to end it blindly. "
                f"Use /sancai accept, /sancai abandon \"...\", or set SANCAI_SKIP_STOP=1."
            )
        if sid != run_sid:
            allow()
        block(
            f"Sancai run {run} is {run_data.get('state')}; "
            f"finish with /sancai accept (or /sancai approve for irreversible actions), "
            f"or run /sancai abandon \"...\""
        )

    if args.precompact:
        allow()


if __name__ == "__main__":
    main()

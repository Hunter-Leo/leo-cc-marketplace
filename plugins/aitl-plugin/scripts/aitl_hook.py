#!/usr/bin/env python3
"""AITL hooks (guarded: no-op when .aitl is absent).

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
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aitl_capability import check as cap_check  # type: ignore  # noqa: E402
from aitl_graph import status_object  # type: ignore  # noqa: E402

STATUS: dict[str, str | None] = {"root": None, "run": None}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def find_root(cwd=None):
    cur = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".aitl")):
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
    path = os.path.join(root, ".aitl", "active")
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
        f"AITL {status['run']} | {status['state']} | {status['stage']} | "
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


def emit_status_line(root):
    """UserPromptSubmit: inject one line, deduplicated by state fingerprint."""
    run = active_run(root)
    if not run:
        return
    fingerprint = _fingerprint(root, run)
    if fingerprint is None:
        return
    path = os.path.join(root, ".aitl", "status.last")
    try:
        with open(path, encoding="utf-8") as f:
            last = json.load(f)
    except (OSError, json.JSONDecodeError):
        last = {}
    same = last.get("fingerprint") == fingerprint
    turns = int(last.get("turns_since_output", 0))
    if same and turns < 2:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"fingerprint": fingerprint, "turns_since_output": turns + 1}, f)
        return
    line = status_line(root, run)
    if not line:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"fingerprint": fingerprint, "turns_since_output": 0}, f)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": line,
        }
    }
    if os.environ.get("AITL_STATUS_FALLBACK") == "1":
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
        if os.path.basename(token) != "aitl_decide.py":
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

    rd = os.path.join(root, ".aitl", "runs", run)
    run_path = os.path.join(rd, "run.json")
    if not os.path.isfile(run_path):
        allow()
    run_data = json.load(open(run_path, encoding="utf-8"))

    if args.pre_tool:
        tool = payload.get("tool_name", "")
        ti = payload.get("tool_input") or {}
        command = ti.get("command")
        path = ti.get("file_path") or ti.get("path")
        state = run_data.get("state")
        claim = run_data.get("claim")

        if state == "executing" and claim:
            ok, reason = cap_check(root, tool, command, path, run)
            if not ok:
                deny(f"AITL capability denied: {reason}")
            allow()

        # Outside an active execution claim, code writes are denied. The only
        # exception is drafting the intent during planning.
        if tool in ("Write", "Edit", "NotebookEdit"):
            intent_path = os.path.join(rd, "intent.json")
            if state == "planning" and path and os.path.realpath(path) == os.path.realpath(intent_path):
                allow()
            deny(f"AITL: code writes are not allowed while state={state}")

        # Harness scripts and read-only commands remain available; mutations
        # such as git add/commit require an active claim and are denied here.
        if tool == "Bash":
            ok, reason = cap_check(root, tool, command, path, run)
            if not ok:
                deny(f"AITL capability denied: {reason}")
            decision = decision_call(command)
            if decision:
                sub, opts = decision
                run_arg = opts.get("run") or run
                card = opts.get("card-id") or "<missing card>"
                target = opts.get("id") or ""
                detail = ""
                if sub == "mint":
                    detail = f" action={opts.get('action')} diff={opts.get('diff-sha')}"
                ask(
                    f"AITL human decision: {sub} run={run_arg}"
                    + (f" target={target}" if target else "")
                    + detail
                    + f" card={card}. "
                    "Allow only if the card above matches what you intend."
                )
            allow()

        allow()

    if args.post_tool:
        ev = os.path.join(rd, "events.jsonl")
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
        verdict = os.path.join(rd, "verdicts", f"{wo}.json")
        if not os.path.isfile(verdict):
            block(f"AITL: subagent stopped without verdict for {wo}; write .aitl/runs/{run}/verdicts/{wo}.json")
        allow()

    if args.stop:
        if os.environ.get("AITL_SKIP_STOP") == "1":
            allow()
        if run_data.get("state") in ("accepted", "abandoned"):
            allow()
        sid = payload.get("session_id")
        run_sid = run_data.get("session_id")
        if not run_sid:
            block(
                f"AITL run {run} has no recorded session id; refuse to end it blindly. "
                f"Finish with /aitl accept, /aitl abandon \"...\", or set AITL_SKIP_STOP=1 if you accept the risk."
            )
        if not sid:
            block(
                f"AITL stop hook has no session id for run {run}; refuse to end it blindly. "
                f"Use /aitl accept, /aitl abandon \"...\", or set AITL_SKIP_STOP=1."
            )
        if sid != run_sid:
            allow()
        block(
            f"AITL run {run} is {run_data.get('state')}; "
            f"finish with /aitl accept (or /aitl approve for irreversible actions), "
            f"or run /aitl abandon \"...\""
        )

    if args.precompact:
        allow()


if __name__ == "__main__":
    main()

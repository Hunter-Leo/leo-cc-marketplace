#!/usr/bin/env python3
"""Native-UI decision entrypoint.

The agent runs this after rendering a card. `aitl_hook.py --pre-tool` returns
`permissionDecision: "ask"`, so Claude Code shows its native permission prompt:
the human clicks Allow/Deny and never copies a command.

This wrapper is deliberately thin: it forwards to the same state/escalation
commands that `aitl_human.py` calls, so card binding, dwell, phrase checks, and
state guards stay in one place.

usage:
  aitl_decide.py sign    --run R --message confirmed --session-id S \
                         --card-id CARD-... --card-code ........
  aitl_decide.py approve --run R --id ESC-001 --message approved --session-id S \
                         --card-id CARD-... --card-code ........
  aitl_decide.py reject  --run R --id ESC-001 --reason "..." --session-id S \
                         --card-id CARD-... --card-code ........
  aitl_decide.py accept  --run R --message accepted --session-id S \
                         --card-id CARD-... --card-code ........ \
                         [--ack-findings] [--disposition defer:WO-005]
  aitl_decide.py mint    --run R --action "..." --diff-sha ... --ttl 600
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _run(script, subcommand, argv):
    cmd = [sys.executable, os.path.join(HERE, script), subcommand] + argv
    return subprocess.call(cmd)


def _session(value):
    return value or os.environ.get("CLAUDE_SESSION_ID", "")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="AITL decision entrypoint gated by Claude Code's native permission prompt."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sign", help="approve the run intent")
    p.add_argument("--run", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--session-id", default="")
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)

    p = sub.add_parser("approve", help="approve an escalation")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--session-id", default="")
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)

    p = sub.add_parser("reject", help="reject an escalation")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--session-id", default="")
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)

    p = sub.add_parser("accept", help="accept the run outcome")
    p.add_argument("--run", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--session-id", default="")
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)
    p.add_argument("--ack-findings", action="store_true")
    p.add_argument("--disposition", action="append", default=[])

    p = sub.add_parser("mint", help="mint a one-time token after the native prompt")
    p.add_argument("--run", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--diff-sha", required=True)
    p.add_argument("--ttl", type=int, default=600)

    args = ap.parse_args(argv)
    if args.cmd == "mint":
        env = os.environ.copy()
        env["AITL_NATIVE_UI"] = "1"
        return subprocess.call(
            [
                sys.executable,
                os.path.join(HERE, "aitl_capability.py"),
                "mint",
                "--run", args.run,
                "--action", args.action,
                "--diff-sha", args.diff_sha,
                "--ttl", str(args.ttl),
            ],
            env=env,
        )

    session = _session(args.session_id)
    if not session:
        print("aitl_decide.py: --session-id or CLAUDE_SESSION_ID is required", file=sys.stderr)
        return 2

    forwarded = []
    if args.cmd in ("sign", "accept"):
        forwarded = [
            "--run", args.run,
            "--message", args.message,
            "--session-id", session,
            "--card-id", args.card_id,
            "--card-code", args.card_code,
        ]
        if args.cmd == "accept":
            if args.ack_findings:
                forwarded.append("--ack-findings")
            for disposition in args.disposition:
                forwarded += ["--disposition", disposition]
        return _run("aitl_state.py", args.cmd, forwarded)

    forwarded = [
        "--run", args.run,
        "--id", args.id,
        "--session-id", session,
        "--card-id", args.card_id,
        "--card-code", args.card_code,
    ]
    if args.cmd == "approve":
        forwarded += ["--message", args.message]
    else:
        forwarded += ["--reason", args.reason]
    return _run("aitl_escalate.py", args.cmd, forwarded)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Human-only Sancai decision entrypoint.

This wrapper exists so the human gate is a real interactive process, not a
command an agent can run from its own shell. The plugin's capability guard
denies `sancai_human.py` (and the underlying decision commands) to agent Bash;
a human runs this script in a terminal.

usage:
  sancai_human.py sign    --run R --message confirmed --session-id S \
                        --card-id CARD-... --card-code ........
  sancai_human.py approve --run R --id ESC-001 --message approved --session-id S \
                        --card-id CARD-... --card-code ........
  sancai_human.py reject  --run R --id ESC-001 --reason "..." --session-id S \
                        --card-id CARD-... --card-code ........
  sancai_human.py accept  --run R --message accepted --session-id S \
                        --card-id CARD-... --card-code ........ \
                        [--ack-findings] [--disposition defer:WO-005]
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _run(script, subcommand, argv):
    cmd = [sys.executable, os.path.join(HERE, script), subcommand] + argv
    return subprocess.call(cmd)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Human-only Sancai decision gate (requires an interactive terminal)."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sign", help="approve the run intent")
    p.add_argument("--run", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)

    p = sub.add_parser("approve", help="approve an escalation")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)

    p = sub.add_parser("reject", help="reject an escalation")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)

    p = sub.add_parser("accept", help="accept the run outcome")
    p.add_argument("--run", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--card-id", required=True)
    p.add_argument("--card-code", required=True)
    p.add_argument("--ack-findings", action="store_true")
    p.add_argument("--disposition", action="append", default=[])

    args = ap.parse_args(argv)

    if not sys.stdin.isatty():
        print(
            "sancai_human.py requires an interactive terminal; "
            "the agent's shell is not a human gate",
            file=sys.stderr,
        )
        return 2

    print("Sancai human decision")
    print(f"  command : {args.cmd}")
    print(f"  card    : {args.card_id} / {args.card_code}")
    print("  This process is the human gate. Do not run it from an agent shell.")

    if args.cmd == "sign":
        return _run("sancai_state.py", "sign", [
            "--run", args.run,
            "--message", args.message,
            "--session-id", args.session_id,
            "--card-id", args.card_id,
            "--card-code", args.card_code,
        ])
    if args.cmd == "approve":
        return _run("sancai_escalate.py", "approve", [
            "--run", args.run,
            "--id", args.id,
            "--message", args.message,
            "--session-id", args.session_id,
            "--card-id", args.card_id,
            "--card-code", args.card_code,
        ])
    if args.cmd == "reject":
        return _run("sancai_escalate.py", "reject", [
            "--run", args.run,
            "--id", args.id,
            "--reason", args.reason,
            "--session-id", args.session_id,
            "--card-id", args.card_id,
            "--card-code", args.card_code,
        ])
    forward = [
        "--run", args.run,
        "--message", args.message,
        "--session-id", args.session_id,
        "--card-id", args.card_id,
        "--card-code", args.card_code,
    ]
    if args.ack_findings:
        forward.append("--ack-findings")
    for disposition in args.disposition:
        forward.extend(["--disposition", disposition])
    return _run("sancai_state.py", "accept", forward)


if __name__ == "__main__":
    sys.exit(main())

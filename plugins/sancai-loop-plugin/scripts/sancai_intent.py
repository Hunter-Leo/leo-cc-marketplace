#!/usr/bin/env python3
"""Intent alignment tools for Sancai H1.

usage:
  sancai_intent.py assess --run 001-auth [--json]
  sancai_intent.py questions --run 001-auth [--json]
  sancai_intent.py record --run 001-auth --status aligned --answers "..." --session-id s1
  sancai_intent.py record --run 001-auth --status aligned --resolutions answers.json
  sancai_intent.py glossary --run 001-auth [--write]
  sancai_intent.py adr --run 001-auth --title "Use Postgres"

The tools are deterministic. They do not call an LLM and do not invent
requirements. They surface ambiguity, ask the human, and record the answer.

The interactive part happens in Claude Code's native question UI. For each
signal the agent proposes 2-3 context-grounded candidate resolutions, the human
picks one or writes their own, and `record --resolutions` persists every choice.
"""
import argparse
import hashlib
import json
import os
import re
import sys

import sancai_paths as paths  # type: ignore
import sancai_state as state  # type: ignore

VAGUE_TERMS = (
    "robust", "scalable", "efficient", "better", "improve", "optimize",
    "etc", "tbd", "maybe", "appropriate", "reasonable", "fast", "clean",
    "secure", "flexible", "user-friendly", "modern", "simple",
)
ACCEPTANCE_HINTS = ("exit_code", "==", "!=", "contains", "matches", "json", "file")


def load_intent(root, run):
    _, data = state.load_run(root, run)
    path = paths.intent_path(root, run, data)
    intent = state.load(path)
    state.validate_intent(intent, root)
    return intent, path


def _vague_terms(text):
    lowered = text.lower()
    return [term for term in VAGUE_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)]


def assess_intent(intent):
    """Return (status, signals) where each signal has code/message/question."""
    signals = []
    goal = intent.get("goal", "")
    if len(goal.strip()) < 30:
        signals.append({
            "code": "goal_short",
            "message": "The goal is shorter than 30 characters and may not be testable.",
            "question": "What concrete outcome should be true when this run is accepted?",
        })
    vague = _vague_terms(goal)
    for term in vague:
        signals.append({
            "code": f"vague_term:{term}",
            "message": f"The goal uses the ambiguous term '{term}'.",
            "question": f"Define '{term}' as a measurable condition, or remove it.",
        })
    if not intent.get("non_goals"):
        signals.append({
            "code": "non_goals_missing",
            "message": "non_goals is empty, so scope boundaries are unstated.",
            "question": "What is explicitly out of scope for this run?",
        })
    acceptance = intent.get("acceptance") or []
    for ac in acceptance:
        expect = str(ac.get("expect", ""))
        if not any(hint in expect for hint in ACCEPTANCE_HINTS):
            signals.append({
                "code": f"acceptance_weak:{ac.get('id', '?')}",
                "message": f"Acceptance {ac.get('id', '?')} has no observable expectation.",
                "question": f"What observable check proves {ac.get('id', '?')} passed?",
            })
    manual = sum(1 for ac in acceptance
                 if ac.get("check") == "manual" or ac.get("type") == "manual")
    if acceptance and manual / len(acceptance) > 0.2 + 1e-9:
        signals.append({
            "code": "manual_ratio_high",
            "message": f"Manual acceptance is {manual}/{len(acceptance)} (> 20%).",
            "question": "Which manual criteria can be converted into an executable check?",
        })
    if not intent.get("owned_files"):
        signals.append({
            "code": "owned_files_missing",
            "message": "owned_files is empty, so the write boundary is unstated.",
            "question": "Which files may this run modify?",
        })
    for question in intent.get("open_questions", []) or []:
        signals.append({
            "code": "open_question",
            "message": f"Open question: {question}",
            "question": str(question),
        })
    return ("aligned" if not signals else "needs_alignment"), signals


def print_assessment(run, status, signals, as_json):
    if as_json:
        print(json.dumps({
            "schema_version": "sancai.intent-alignment.v1",
            "run": run,
            "status": status,
            "signals": signals,
            "questions": [s["question"] for s in signals],
        }, ensure_ascii=False, indent=2))
        return
    print(f"Intent alignment: {status} ({run})")
    if not signals:
        print("  No ambiguity signals found.")
        return
    for i, signal in enumerate(signals, 1):
        print(f"  {i}. [{signal['code']}] {signal['message']}")
        print(f"     Q: {signal['question']}")


def cmd_assess(args):
    root = state.find_root()
    run = state.resolve_run(root, args)
    intent, _ = load_intent(root, run)
    status, signals = assess_intent(intent)
    print_assessment(run, status, signals, args.json)
    if status != "aligned":
        sys.exit(2)


def cmd_questions(args):
    root = state.find_root()
    run = state.resolve_run(root, args)
    intent, _ = load_intent(root, run)
    _, signals = assess_intent(intent)
    if args.json:
        print(json.dumps([
            {"code": s["code"], "message": s["message"], "question": s["question"]}
            for s in signals
        ], ensure_ascii=False, indent=2))
        return
    for i, signal in enumerate(signals, 1):
        print(f"{i}. {signal['question']}")


def _read_resolutions(source):
    """Load a resolutions array from a file, `-` for stdin, or inline JSON."""
    if source == "-":
        raw = sys.stdin.read()
    elif os.path.isfile(source):
        with open(source, encoding="utf-8") as fh:
            raw = fh.read()
    else:
        raw = source
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"invalid --resolutions JSON: {exc}")
    if isinstance(data, dict):
        data = data.get("resolutions")
    if not isinstance(data, list):
        sys.exit("--resolutions must be a JSON array")
    resolutions = []
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict):
            sys.exit(f"resolution {index} must be an object")
        code = str(item.get("code", "")).strip()
        choice = str(item.get("choice", "")).strip()
        source_kind = item.get("source", "proposed")
        if not code:
            sys.exit(f"resolution {index} is missing code")
        if not choice:
            sys.exit(f"resolution {index} ({code}) requires a non-empty choice")
        if source_kind not in ("proposed", "user"):
            sys.exit(
                f"resolution {index} ({code}) source must be 'proposed' or 'user'"
            )
        resolutions.append({"code": code, "choice": choice, "source": source_kind})
    return resolutions


def _validate_resolutions(signal_codes, resolutions, status):
    if resolutions is None:
        return
    known = set(signal_codes)
    seen = set()
    for resolution in resolutions:
        code = resolution["code"]
        if code not in known:
            sys.exit(f"unknown alignment signal in resolutions: {code}")
        if code in seen:
            sys.exit(f"duplicate resolution for signal: {code}")
        seen.add(code)
    if status == "aligned":
        missing = [code for code in signal_codes if code not in seen]
        if missing:
            sys.exit(
                "resolutions must cover every alignment signal; missing: "
                + ", ".join(missing)
            )


def _summarize(resolutions):
    return "; ".join(f"{r['code']}={r['choice']}" for r in resolutions)


def cmd_record(args):
    root = state.find_root()
    run = state.resolve_run(root, args)
    intent, path = load_intent(root, run)
    if args.status == "deferred" and not args.reason.strip():
        sys.exit("deferred alignment requires --reason")
    resolutions = _read_resolutions(args.resolutions) if args.resolutions else None
    _, signals = assess_intent(intent)
    signal_codes = [s["code"] for s in signals]
    if args.status == "aligned" and signal_codes and resolutions is None:
        sys.exit(
            "aligned requires --resolutions covering every alignment signal; missing: "
            + ", ".join(signal_codes)
        )
    _validate_resolutions(signal_codes, resolutions, args.status)
    answers = args.answers.strip()
    if args.status == "aligned" and not answers and not resolutions:
        sys.exit("aligned requires --answers or --resolutions with the human's resolution")
    if args.status == "aligned" and not answers and resolutions:
        answers = _summarize(resolutions)
    intent["alignment"] = {
        "schema_version": "sancai.intent-alignment.v1",
        "status": args.status,
        "recorded_at": state.now(),
        "session_id": args.session_id,
        "answers": answers,
        "reason": args.reason,
        "signals": signal_codes,
        "questions": [s["question"] for s in signals],
        "questions_sha": hashlib.sha256(
            json.dumps([s["question"] for s in signals], ensure_ascii=False).encode()
        ).hexdigest(),
        "signals_sha": hashlib.sha256(
            json.dumps(
                [{"code": s["code"], "question": s["question"]} for s in signals],
                ensure_ascii=False, sort_keys=True,
            ).encode()
        ).hexdigest(),
        "resolutions": resolutions or [],
    }
    state.save(path, intent)
    state.append_event(root, run, "intent_aligned", {
        "status": args.status,
        "signals": [s["code"] for s in signals],
        "session_id": args.session_id,
    })
    print(f"alignment recorded: {run} -> {args.status}")


def _candidate_terms(intent):
    text = " ".join([
        str(intent.get("goal", "")),
        " ".join(str(x) for x in intent.get("non_goals", []) or []),
        " ".join(str(ac.get("expect", "")) for ac in intent.get("acceptance", []) or []),
    ])
    terms = set(re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", text))
    terms.update(re.findall(r'"([^"]{2,40})"', text))
    return sorted(terms)


def cmd_glossary(args):
    root = state.find_root()
    run = state.resolve_run(root, args)
    intent, _ = load_intent(root, run)
    path = os.path.join(paths.l3_dir(root, run), "CONTEXT.md")
    if args.write and not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("# Context Glossary\n\n")
            fh.write("| Term | Definition | Status |\n|---|---|---|\n")
            for term in _candidate_terms(intent):
                fh.write(f"| {term} | TBD | open |\n")
            fh.write("\n## Flagged ambiguities\n\n- TBD\n")
        print(f"created {path}")
        return
    print(f"glossary: {path}")
    for term in _candidate_terms(intent):
        print(f"  - {term}")


def _slug(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] or "decision"


def cmd_adr(args):
    root = state.find_root()
    run = state.resolve_run(root, args)
    adr_dir = os.path.join(paths.decisions_dir(root, run), "adr")
    os.makedirs(adr_dir, exist_ok=True)
    existing = sorted(f for f in os.listdir(adr_dir) if re.match(r"ADR-\d{3}-", f))
    number = int(existing[-1][4:7]) + 1 if existing else 1
    slug = _slug(args.title)
    path = os.path.join(adr_dir, f"ADR-{number:03d}-{slug}.md")
    with open(path, "x") as fh:
        fh.write(f"# ADR-{number:03d}: {args.title}\n\n")
        fh.write("## Status\n\nProposed\n\n## Context\n\n")
        fh.write((args.context or "TBD") + "\n\n## Decision\n\n")
        fh.write((args.decision or "TBD") + "\n\n## Consequences\n\n")
        fh.write("- Positive: TBD\n- Negative: TBD\n- Follow-up: TBD\n")
    print(path)


def main():
    parser = argparse.ArgumentParser(description="Sancai intent alignment tools")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("assess", help="report ambiguity signals")
    p.add_argument("--run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_assess)

    p = sub.add_parser("questions", help="print alignment questions")
    p.add_argument("--run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_questions)

    p = sub.add_parser("record", help="record the human's alignment decision")
    p.add_argument("--run")
    p.add_argument("--status", required=True, choices=("aligned", "deferred"))
    p.add_argument("--answers", default="")
    p.add_argument("--resolutions", default="",
                   help="JSON array, path, or '-' for stdin: [{code, choice, source}]")
    p.add_argument("--reason", default="")
    p.add_argument("--session-id", default="")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("glossary", help="list or create CONTEXT.md terms")
    p.add_argument("--run")
    p.add_argument("--write", action="store_true")
    p.set_defaults(func=cmd_glossary)

    p = sub.add_parser("adr", help="create an ADR template")
    p.add_argument("--run")
    p.add_argument("--title", required=True)
    p.add_argument("--context", default="")
    p.add_argument("--decision", default="")
    p.set_defaults(func=cmd_adr)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

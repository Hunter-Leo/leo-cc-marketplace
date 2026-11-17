#!/usr/bin/env bash
# check-team-complete.sh — read-only completion report for a leo-team run.
# Always exits 0. Prints OK / NOT COMPLETE (+ blockers) or NO RUN.
# State: <repo>/.team/<run>/flow.json  (base dir override: LEO_TEAM_DIR)
# Artifacts: <repo>/.dev/<run>/generated/{research.md,science-audit.md,findings.md}
set -uo pipefail

python3 - "$@" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

LANES = ["pending", "in_progress", "for_review", "approved",
         "merged", "verified", "changes_requested", "blocked"]


def base_dir():
    env = os.environ.get("LEO_TEAM_DIR")
    return Path(env) if env else Path.cwd() / ".team"


def find_flow(base):
    direct = base / "flow.json"
    if direct.is_file():
        return direct
    if base.is_dir():
        cands = sorted(base.glob("*/flow.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            return cands[0]
    return None


def repo_root(base):
    """Anchor to the repository root so the script works from any cwd.

    Prefers LEO_TEAM_DIR's ancestors (looking for .dev or .git), then cwd.
    """
    for start in (base.resolve(), Path.cwd().resolve()):
        for parent in [start, *start.parents]:
            if (parent / ".dev").is_dir() or (parent / ".git").exists():
                return parent
    return Path.cwd()


def generated_dir(flow, flow_path, base):
    """Only accept this run's artifact directory; never fall back across runs."""
    run = flow.get("run") or flow_path.parent.name
    return repo_root(base) / ".dev" / run / "generated"


def find_artifact(name, gen_dir):
    """Only accept .dev/<run>/generated/<name>; never fall back."""
    candidate = gen_dir / name
    return candidate if candidate.is_file() else None


VERDICT_RE = re.compile(r"\bVerdict\b\**\s*[:：]\s*(PASS|FAIL|UNVERIFIABLE)\b", re.I)
RESULT_CELL_RE = re.compile(r"^(PASS|FAIL|UNVERIFIABLE)$", re.I)
SEVERITY_RE = re.compile(r"^(blocker|critical|major|minor|nit)$", re.I)
OPEN_STATUSES = {"open", "deferred", "in-progress", "pending"}


def _cells(line):
    return [c.strip().strip("*` ") for c in line.strip().strip("|").split("|")]


def check_audit(content):
    """Read only the first Verdict in the final conclusion and the result column of the check matrix."""
    blockers = []
    section = ""
    verdict = None
    matrix_results = []

    for line in content.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if section.startswith("4") and verdict is None:
            m = VERDICT_RE.search(line)
            if m:
                verdict = m.group(1).upper()
        if section.startswith("2") and line.lstrip().startswith("|"):
            # Take only the first PASS/FAIL/UNVERIFIABLE per line so identical words in the evidence column are not counted
            for cell in _cells(line):
                if RESULT_CELL_RE.match(cell):
                    matrix_results.append(cell.upper())
                    break

    if verdict is None:
        blockers.append("science-audit.md has no parseable final Verdict (PASS/FAIL/UNVERIFIABLE)")
    elif verdict != "PASS":
        blockers.append(f"science-audit.md final verdict is {verdict}")
    elif len(matrix_results) < 5:
        blockers.append(f"science-audit.md check matrix is incomplete ({len(matrix_results)} results, 5 required)")
    elif matrix_results.count("PASS") != 5:
        blockers.append(f"science-audit.md Verdict=PASS but only {matrix_results.count('PASS')}/5 matrix results are PASS")

    if matrix_results.count("FAIL"):
        blockers.append(f"science-audit.md check matrix has {matrix_results.count('FAIL')} FAIL items")
    return blockers


def check_findings(content):
    """Open blocker/critical/major items block completion; fixed/wontfix do not."""
    blockers = []
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) < 4:
            continue
        fid = cells[0]
        if not re.match(r"^F-[A-Z0-9]+-\d+$", fid):
            continue
        severity = next((c.lower() for c in cells if SEVERITY_RE.match(c)), None)
        if severity is None:
            continue
        status = cells[-1].lower()
        if severity in ("blocker", "critical") and status != "fixed":
            blockers.append(f"findings.md {fid}: {severity} not closed (status={status or 'unknown'}); only 'fixed' clears it")
        elif severity == "major" and status in ("open", "deferred"):
            blockers.append(f"findings.md {fid}: major not closed ({status}); use 'fixed' or 'accepted' with an ADR")
    return blockers


def main():
    base = base_dir()
    path = find_flow(base)
    if path is None:
        print("NO RUN")
        return 0
    try:
        flow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("NOT COMPLETE")
        print(f"- Cannot read flow.json: {exc}")
        return 0

    units = flow.get("units", [])
    gate = flow.get("science_gate") or {}
    counts = {lane: 0 for lane in LANES}
    for unit in units:
        lane = unit.get("lane", "pending")
        counts[lane] = counts.get(lane, 0) + 1

    print(f"Run: {flow.get('run', '?')}")
    print(f"Mission: {flow.get('mission', '?')}")
    print("Lanes: " + " ".join(f"{lane}={counts.get(lane, 0)}" for lane in LANES))

    blockers = []
    if not units:
        blockers.append("flow.json.units is empty: no implementation units")
    if flow.get("mission") != "verified":
        blockers.append(f"mission={flow.get('mission', '?')} (verified required)")
    if flow.get("claim") is not None:
        blockers.append(f"claim still held: {flow['claim'].get('unit', '?')}")
    for unit in units:
        lane = unit.get("lane", "pending")
        if lane != "verified":
            blockers.append(f"{unit.get('id', '?')} is in {lane}")

    gen_dir = generated_dir(flow, path, base)
    findings = find_artifact("findings.md", gen_dir)
    if findings is not None:
        try:
            blockers.extend(check_findings(findings.read_text(encoding="utf-8")))
        except OSError as exc:
            blockers.append(f"Cannot read findings.md: {exc}")

    if gate.get("researcher") and find_artifact("research.md", gen_dir) is None:
        blockers.append(f"science_gate.researcher=true but {gen_dir}/research.md does not exist")
    if gate.get("auditor"):
        audit = find_artifact("science-audit.md", gen_dir)
        if audit is None:
            blockers.append(f"science_gate.auditor=true but {gen_dir}/science-audit.md does not exist")
        else:
            try:
                blockers.extend(check_audit(audit.read_text(encoding="utf-8")))
            except OSError as exc:
                blockers.append(f"Cannot read science-audit.md: {exc}")

    if blockers:
        print("NOT COMPLETE")
        for item in blockers:
            print(f"- {item}")
    else:
        print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY
exit 0

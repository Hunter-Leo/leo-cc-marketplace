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


def generated_dir(flow, flow_path):
    """只认本 run 的产物目录，禁止跨 run 回退。"""
    run = flow.get("run") or flow_path.parent.name
    return Path.cwd() / ".dev" / run / "generated"


def find_artifact(name, gen_dir):
    """只认 .dev/<run>/generated/<name>，不做任何回退。"""
    candidate = gen_dir / name
    return candidate if candidate.is_file() else None


VERDICT_RE = re.compile(r"\bVerdict\b\**\s*[:：]\s*(PASS|FAIL|UNVERIFIABLE)\b", re.I)
RESULT_CELL_RE = re.compile(r"^(PASS|FAIL|UNVERIFIABLE)$", re.I)
SEVERITY_RE = re.compile(r"^(blocker|critical|major|minor|nit)$", re.I)
OPEN_STATUSES = {"open", "deferred", "in-progress", "pending"}


def _cells(line):
    return [c.strip().strip("*` ") for c in line.strip().strip("|").split("|")]


def check_audit(content):
    """只读「最终结论」的第一条 Verdict 与「检查矩阵」的结果列。"""
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
            # 每行只取第一个 PASS/FAIL/UNVERIFIABLE，避免证据列里的同名字样被计入
            for cell in _cells(line):
                if RESULT_CELL_RE.match(cell):
                    matrix_results.append(cell.upper())
                    break

    if verdict is None:
        blockers.append("science-audit.md 缺少可解析的最终 Verdict（PASS/FAIL/UNVERIFIABLE）")
    elif verdict != "PASS":
        blockers.append(f"science-audit.md 最终结论为 {verdict}")
    elif len(matrix_results) < 5:
        blockers.append(f"science-audit.md 检查矩阵不完整（仅 {len(matrix_results)} 项结果，需 5 项）")
    elif matrix_results.count("PASS") != 5:
        blockers.append(f"science-audit.md Verdict=PASS 但检查矩阵仅 {matrix_results.count('PASS')}/5 项 PASS")

    if matrix_results.count("FAIL"):
        blockers.append(f"science-audit.md 检查矩阵有 {matrix_results.count('FAIL')} 项 FAIL")
    return blockers


def check_findings(content):
    """open 的 blocker/critical/major 阻塞完成；fixed/wontfix 不阻塞。"""
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
        if severity == "blocker" and status not in ("fixed", "wontfix"):
            blockers.append(f"findings.md {fid}：blocker 未关闭（{status or 'unknown'}）")
        elif severity == "critical" and status in OPEN_STATUSES:
            blockers.append(f"findings.md {fid}：critical 未关闭（{status}）")
        elif severity == "major" and status in ("open", "deferred"):
            blockers.append(f"findings.md {fid}：major 未关闭（{status}）")
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
        print(f"- 无法读取 flow.json：{exc}")
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
        blockers.append("flow.json.units 为空：没有任何实现单元")
    if flow.get("mission") != "verified":
        blockers.append(f"mission={flow.get('mission', '?')}（需要 verified）")
    if flow.get("claim") is not None:
        blockers.append(f"仍有未释放的 claim：{flow['claim'].get('unit', '?')}")
    for unit in units:
        lane = unit.get("lane", "pending")
        if lane != "verified":
            blockers.append(f"{unit.get('id', '?')} 处于 {lane}")

    gen_dir = generated_dir(flow, path)
    findings = find_artifact("findings.md", gen_dir)
    if findings is not None:
        try:
            blockers.extend(check_findings(findings.read_text(encoding="utf-8")))
        except OSError as exc:
            blockers.append(f"无法读取 findings.md：{exc}")

    if gate.get("researcher") and find_artifact("research.md", gen_dir) is None:
        blockers.append(f"science_gate.researcher=true 但 {gen_dir}/research.md 不存在")
    if gate.get("auditor"):
        audit = find_artifact("science-audit.md", gen_dir)
        if audit is None:
            blockers.append(f"science_gate.auditor=true 但 {gen_dir}/science-audit.md 不存在")
        else:
            try:
                blockers.extend(check_audit(audit.read_text(encoding="utf-8")))
            except OSError as exc:
                blockers.append(f"无法读取 science-audit.md：{exc}")

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

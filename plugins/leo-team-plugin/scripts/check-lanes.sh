#!/usr/bin/env bash
# check-lanes.sh — 校验工作单元的 owned_files 是否两两不相交（N3 组队门禁）。
# 用法: check-lanes.sh [--json]     基目录: <repo>/.team（可用 LEO_TEAM_DIR 覆盖）
# 退出码: 0 = 无确定相交（可能有潜在重叠警告）；1 = 存在确定相交或读取失败
set -uo pipefail

python3 - "$@" <<'PY'
import glob
import json
import os
import sys
from pathlib import Path


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


def static_prefix(pattern):
    """返回 pattern 中第一个通配符之前的部分。"""
    for i, ch in enumerate(pattern):
        if ch in "*?[":
            return pattern[:i]
    return pattern


def expand(pattern):
    return {os.path.normpath(p) for p in glob.glob(pattern, recursive=True) if os.path.isfile(p)}


def overlap(a, b):
    """返回 (definite, potential, reason)。"""
    pa, pb = static_prefix(a), static_prefix(b)
    if a == b:
        return True, True, "同一 glob"
    if pa and pb and (pa.startswith(pb) or pb.startswith(pa)):
        return False, True, f"前缀重叠：{pa!r} vs {pb!r}"
    files_a, files_b = expand(a), expand(b)
    common = files_a & files_b
    if common:
        return True, True, f"已存在文件重叠：{sorted(common)[:3]}"
    return False, False, ""


def main(argv):
    as_json = "--json" in argv
    path = find_flow(base_dir())
    if path is None:
        msg = "NO RUN：未找到 flow.json"
        print(json.dumps({"status": "no_run", "message": msg}, ensure_ascii=False) if as_json else msg)
        return 1

    try:
        flow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"无法读取 {path}: {exc}"
        print(json.dumps({"status": "error", "message": msg}, ensure_ascii=False) if as_json else msg)
        return 1

    units = flow.get("units") or []
    definite, potential = [], []
    for i, left in enumerate(units):
        for right in units[i + 1:]:
            for a in left.get("owned_files") or []:
                for b in right.get("owned_files") or []:
                    hard, soft, reason = overlap(a, b)
                    item = {
                        "a_unit": left.get("id"), "b_unit": right.get("id"),
                        "a_glob": a, "b_glob": b, "reason": reason,
                    }
                    if hard:
                        definite.append(item)
                    elif soft:
                        potential.append(item)

    status = "fail" if definite else ("warn" if potential else "ok")
    if as_json:
        print(json.dumps({
            "status": status,
            "run": flow.get("run"),
            "units": len(units),
            "definite": definite,
            "potential": potential,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Run: {flow.get('run', '?')}  Units: {len(units)}")
        if not units:
            print("警告：还没有工作单元")
        if definite:
            print(f"确定相交 {len(definite)} 处（必须处理）：")
            for it in definite:
                print(f"  {it['a_unit']}:{it['a_glob']}  ×  {it['b_unit']}:{it['b_glob']}  — {it['reason']}")
        if potential:
            print(f"潜在重叠 {len(potential)} 处（需人工确认或改成更精确的 glob）：")
            for it in potential:
                print(f"  {it['a_unit']}:{it['a_glob']}  ×  {it['b_unit']}:{it['b_glob']}  — {it['reason']}")
        print("结果：" + {"ok": "OK（无重叠）", "warn": "WARN（有潜在重叠）", "fail": "FAIL（存在确定相交）"}[status])
    return 1 if definite else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
PY

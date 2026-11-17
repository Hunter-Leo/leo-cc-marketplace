#!/usr/bin/env bash
# check-lanes.sh — verify that work units' owned_files are pairwise disjoint (N3 teaming gate).
# Usage: check-lanes.sh [--json]     base dir: <repo>/.team (override with LEO_TEAM_DIR)
# Exit: 0 = no definite overlap (potential overlap warnings may still print); 1 = definite overlap or read failure
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
    """Return the part of pattern before the first wildcard."""
    for i, ch in enumerate(pattern):
        if ch in "*?[":
            return pattern[:i]
    return pattern


def expand(pattern):
    return {os.path.normpath(p) for p in glob.glob(pattern, recursive=True) if os.path.isfile(p)}


def overlap(a, b):
    """Return (definite, potential, reason)."""
    pa, pb = static_prefix(a), static_prefix(b)
    if a == b:
        return True, True, "identical glob"
    if pa and pb and (pa.startswith(pb) or pb.startswith(pa)):
        return False, True, f"prefix overlap: {pa!r} vs {pb!r}"
    files_a, files_b = expand(a), expand(b)
    common = files_a & files_b
    if common:
        return True, True, f"existing file overlap: {sorted(common)[:3]}"
    return False, False, ""


def main(argv):
    as_json = "--json" in argv
    path = find_flow(base_dir())
    if path is None:
        msg = "NO RUN: flow.json not found"
        print(json.dumps({"status": "no_run", "message": msg}, ensure_ascii=False) if as_json else msg)
        return 1

    try:
        flow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"Cannot read {path}: {exc}"
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
            print("Warning: no work units yet")
        if definite:
            print(f"Definite overlaps: {len(definite)} (must fix):")
            for it in definite:
                print(f"  {it['a_unit']}:{it['a_glob']}  ×  {it['b_unit']}:{it['b_glob']}  — {it['reason']}")
        if potential:
            print(f"Potential overlaps: {len(potential)} (needs human confirmation or a more precise glob):")
            for it in potential:
                print(f"  {it['a_unit']}:{it['a_glob']}  ×  {it['b_unit']}:{it['b_glob']}  — {it['reason']}")
        print("Result: " + {"ok": "OK (no overlap)", "warn": "WARN (potential overlap)", "fail": "FAIL (definite overlap)"}[status])
    return 1 if definite else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
PY

#!/usr/bin/env python3
"""Summarize eval events into per-task CSV and a markdown report.

usage: summarize.py [--events PATH] [--outdir DIR]
"""
import argparse
import csv
import datetime
import json
import os
import random
import statistics
from collections import defaultdict

MODES = ["A", "B", "C"]
MODE_LABEL = {
    "A": "A · HITL",
    "B": "B · single agent",
    "C": "C · AITL MVP",
}


def parse_ts(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def load_events(path):
    events = []
    if not os.path.exists(path):
        return events
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def group(events):
    g = defaultdict(list)
    for e in events:
        g[(e.get("mode", "?"), e.get("task_id", "?"))].append(e)
    return g


def metrics_for(task_events):
    success = False
    ac_passed = ac_total = 0
    hidden_passed = hidden_total = 0
    human_ms = 0
    human_start = human_end = None
    tokens = 0.0
    false_complete = False

    for e in task_events:
        ev = e.get("event")
        meta = e.get("meta") or {}
        if ev == "accept":
            success = bool(meta.get("success", False))
            ac_passed = meta.get("ac_passed", ac_passed)
            ac_total = meta.get("ac_total", ac_total)
            hidden_passed = meta.get("hidden_passed", hidden_passed)
            hidden_total = meta.get("hidden_total", hidden_total)
            if ac_total and ac_passed < ac_total:
                false_complete = True
        elif ev == "human_start":
            human_start = parse_ts(e.get("ts"))
        elif ev == "human_end":
            human_end = parse_ts(e.get("ts"))
        elif ev == "human_decision":
            human_ms += int(meta.get("active_ms", 0) or 0)
        elif ev == "agent_end":
            t = meta.get("tokens") or {}
            tokens += (
                float(t.get("in", 0) or 0)
                + float(t.get("out", 0) or 0)
                + 0.1 * float(t.get("cache_read", 0) or 0)
                + 1.25 * float(t.get("cache_write", 0) or 0)
            )

    if human_start and human_end:
        human_ms = max(human_ms, int((human_end - human_start).total_seconds() * 1000))

    escape = hidden_total > 0 and hidden_passed < hidden_total
    return {
        "success": success,
        "ac_passed": ac_passed,
        "ac_total": ac_total,
        "hidden_passed": hidden_passed,
        "hidden_total": hidden_total,
        "human_ms": human_ms,
        "tokens": tokens,
        "escape": escape,
        "false_complete": false_complete,
    }


def bootstrap_ci(vals, n=10000, alpha=0.05):
    if not vals:
        return (0.0, 0.0)
    if len(vals) == 1:
        return (float(vals[0]), float(vals[0]))
    rng = random.Random(42)
    means = []
    for _ in range(n):
        means.append(sum(rng.choice(vals) for _ in vals) / len(vals))
    means.sort()
    lo = means[int((alpha / 2) * n)]
    hi = means[min(n - 1, int((1 - alpha / 2) * n) - 1)]
    return (lo, hi)


def agg(rows, key):
    vals = [r[key] for r in rows]
    if not vals:
        return {"n": 0, "mean": 0, "median": 0, "rate": 0}
    if isinstance(vals[0], bool):
        return {
            "n": len(vals),
            "mean": sum(1 for v in vals if v) / len(vals),
            "median": 0,
            "rate": sum(1 for v in vals if v) / len(vals),
        }
    return {
        "n": len(vals),
        "mean": statistics.mean(vals),
        "median": statistics.median(vals),
        "rate": 0,
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=os.path.join(root, "results", "raw", "events.jsonl"))
    ap.add_argument("--outdir", default=os.path.join(root, "results"))
    args = ap.parse_args()

    events = load_events(args.events)
    g = group(events)

    per_task = []
    by_mode = defaultdict(list)
    for (mode, task_id), evs in sorted(g.items()):
        m = metrics_for(evs)
        row = {"task_id": task_id, "mode": mode, **m}
        per_task.append(row)
        by_mode[mode].append(row)

    os.makedirs(args.outdir, exist_ok=True)
    csv_path = os.path.join(args.outdir, "per_task.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "task_id", "mode", "success", "ac_passed", "ac_total",
                "hidden_passed", "hidden_total",
                "human_ms", "tokens", "escape", "false_complete",
            ],
        )
        w.writeheader()
        w.writerows(per_task)

    lines = ["# Phase -1 Eval Summary", "", f"Events: `{args.events}`", ""]
    lines.append("| Mode | n | Success | Human min (median) | Cost (tokens, median) | Escape | False complete |")
    lines.append("|---|---|---|---|---|---|---|")
    for mode in MODES:
        rows = by_mode.get(mode, [])
        if not rows:
            lines.append(f"| {MODE_LABEL[mode]} | 0 | - | - | - | - | - |")
            continue
        succ = agg(rows, "success")["rate"]
        hm = agg(rows, "human_ms")
        tok = agg(rows, "tokens")
        esc = agg(rows, "escape")["rate"]
        fc = agg(rows, "false_complete")["rate"]
        lines.append(
            f"| {MODE_LABEL[mode]} | {len(rows)} | {succ:.1%} | "
            f"{hm['median']/60000:.1f} | {tok['median']:.0f} | "
            f"{esc:.1%} | {fc:.1%} |"
        )

    lines += ["", "## Paired comparisons", ""]
    by_task = defaultdict(dict)
    for r in per_task:
        by_task[r["task_id"]][r["mode"]] = r

    for base in ["A", "B"]:
        diffs = []
        for task_id, modes in by_task.items():
            if "C" in modes and base in modes:
                diffs.append(
                    (
                        modes["C"]["human_ms"] - modes[base]["human_ms"],
                        modes["C"]["success"] - modes[base]["success"],
                    )
                )
        if not diffs:
            lines.append(f"- C vs {base}: no paired tasks")
            continue
        hd = [d[0] for d in diffs]
        sd = [d[1] for d in diffs]
        hlo, hhi = bootstrap_ci(hd)
        slo, shi = bootstrap_ci(sd)
        lines.append(
            f"- C vs {base}: n={len(diffs)}; "
            f"human-min diff mean={statistics.mean(hd)/60000:.1f} "
            f"(95% CI {hlo/60000:.1f} .. {hhi/60000:.1f}); "
            f"success diff mean={statistics.mean(sd):+.1%} "
            f"(95% CI {slo:+.1%} .. {shi:+.1%})"
        )

    lines += ["", "## Notes", "",
              "- Human minutes are active time from human_start to human_end.",
              "- Cost is a weighted token count, not USD; multiply by your price table.",
              "- Escape uses hidden_checks; false complete uses AC results.",
              "- Read the direction and CI, not a single point estimate.",
              ""]

    md_path = os.path.join(args.outdir, "summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n".join(lines))
    print(f"\nWrote {csv_path} and {md_path}")


if __name__ == "__main__":
    main()

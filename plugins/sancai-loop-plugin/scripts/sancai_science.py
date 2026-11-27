#!/usr/bin/env python3
"""Deterministic science routing and audit records for Sancai H1/G3."""
import argparse
import glob
import json
import os
import re
import sys

import sancai_paths as paths  # type: ignore

SCIENCE_AGENTS = {"researcher", "science-auditor"}
CONFIDENCE = {"high", "medium", "low"}
VERDICTS = {"pass", "fail", "unverifiable"}

TEXT_SIGNALS = (
    ("formula", r"\bformula\b|\bequation\b|公式|方程"),
    ("paper", r"\bpaper\b|\bliterature\b|\bstandards?\b|\bspecification\b|论文|文献|标准|规范"),
    ("dataset", r"\bdataset\b|\bcorpus\b|\bbenchmark\b|\bfixture\b|数据集|语料|基准"),
    ("statistics", r"\bstatistic|\bp-value\b|\bconfidence interval\b|\bsample size\b|统计|显著性|置信区间|样本量"),
    ("numeric_claim", r"\baccurac|\bprecision\b|\brecall\b|\berror\b|\btolerance\b|\bunit\b|精度|召回|误差|单位|阈值"),
    ("simulation", r"\bsimulat|\bnumerical\b|\bconvergence\b|仿真|数值|收敛"),
    ("experiment", r"\bexperiment\b|\breproduc|\bexperimental\b|实验|复现"),
)

DEPENDENCY_HINTS = (
    "numpy", "scipy", "pandas", "statsmodels", "sklearn", "scikit-learn",
    "sympy", "pytorch", "tensorflow", "jax", "stats",
)

REPO_DIRS = ("data", "datasets", "corpus", "papers", "experiments", "fixtures")


def _text(intent):
    parts = [str(intent.get("goal", ""))]
    parts.extend(str(x) for x in intent.get("non_goals", []) or [])
    for ac in intent.get("acceptance", []) or []:
        if isinstance(ac, dict):
            parts.extend(str(ac.get(k, "")) for k in ("id", "run", "expect", "text"))
    return "\n".join(parts)


def _repo_signals(root):
    out = []
    if not root or not os.path.isdir(root):
        return out
    for pattern in ("**/*.ipynb",):
        hits = glob.glob(os.path.join(root, pattern), recursive=True)
        if hits:
            out.append(("notebook", f"repo contains {os.path.relpath(hits[0], root)}"))
            break
    for name in REPO_DIRS:
        if os.path.isdir(os.path.join(root, name)):
            out.append(("dataset", f"repo contains {name}/"))
    for name in ("requirements.txt", "pyproject.toml", "package.json"):
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read().lower()
        except OSError:
            continue
        for hint in DEPENDENCY_HINTS:
            if hint in text:
                out.append(("dependency", f"{name} mentions {hint}"))
                break
    return out


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detect(intent, root=None):
    text = _text(intent)
    signals = []
    reasons = []
    for name, pattern in TEXT_SIGNALS:
        if re.search(pattern, text, re.IGNORECASE):
            signals.append(name)
            reasons.append(f"intent text matched {name}")
    repo = _repo_signals(root)
    for name, reason in repo:
        if name not in signals:
            signals.append(name)
        reasons.append(reason)

    required = bool(signals)
    if signals:
        confidence = "high" if len(signals) >= 2 else "medium"
    else:
        confidence = "high"
    agents = []
    if required:
        agents.append("researcher")
        if any(s in signals for s in (
            "formula", "statistics", "numeric_claim", "simulation", "experiment"
        )):
            agents.append("science-auditor")
    return {
        "required": required,
        "signals": sorted(set(signals)),
        "reasons": reasons,
        "confidence": confidence,
        "suggested_agents": agents,
    }


def science_of(intent):
    block = intent.get("science")
    return block if isinstance(block, dict) else {}


def required(intent):
    return bool(science_of(intent).get("required"))


def validate_block(intent):
    block = intent.get("science")
    if block is None:
        return
    if not isinstance(block, dict):
        sys.exit("intent.science must be an object")
    if not isinstance(block.get("required"), bool):
        sys.exit("intent.science.required must be boolean")
    if block.get("confidence") not in CONFIDENCE:
        sys.exit(f"intent.science.confidence must be one of {sorted(CONFIDENCE)}")
    signals = block.get("signals") or []
    reasons = block.get("reasons") or []
    agents = block.get("agents") or []
    if not isinstance(signals, list) or not all(isinstance(x, str) for x in signals):
        sys.exit("intent.science.signals must be a string list")
    if not isinstance(reasons, list) or not all(isinstance(x, str) for x in reasons):
        sys.exit("intent.science.reasons must be a string list")
    if not isinstance(agents, list) or any(a not in SCIENCE_AGENTS for a in agents):
        sys.exit(f"intent.science.agents must be a subset of {sorted(SCIENCE_AGENTS)}")
    if block.get("required"):
        if not reasons:
            sys.exit("intent.science.required=true requires at least one reason")
        if "researcher" not in agents:
            sys.exit("intent.science.required=true requires the researcher agent")
        numeric = {
            "formula", "statistics", "numeric_claim", "simulation", "experiment"
        }
        if numeric.intersection(signals) and "science-auditor" not in agents:
            sys.exit("numeric/science signals require the science-auditor agent")


def audit_path(root, run, wo):
    return os.path.join(paths.science_audit_dir(root, run), f"{wo}.json")


def audit_status(root, run, wo, intent, required_override=None, ec_ids=None):
    needed = bool(required_override) if required_override is not None else bool(required(intent))
    if not needed:
        return {"required": False, "ok": True, "verdict": None}
    path = audit_path(root, run, wo)
    if not os.path.isfile(path):
        return {"required": True, "ok": False, "verdict": None, "reason": "missing science audit"}
    try:
        audit = _read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"required": True, "ok": False, "verdict": None, "reason": f"unreadable science audit: {exc}"}
    verdict = audit.get("verdict")
    if verdict not in VERDICTS:
        return {"required": True, "ok": False, "verdict": verdict, "reason": "invalid science audit verdict"}
    if ec_ids is not None:
        bound = audit.get("expected_changes") or audit.get("ec_ids") or []
        if not isinstance(bound, list) or sorted(str(item) for item in bound) != sorted(str(item) for item in ec_ids):
            return {
                "required": True, "ok": False, "verdict": verdict,
                "reason": "science audit does not cover the frozen expected changes",
            }
    return {"required": True, "ok": verdict == "pass", "verdict": verdict, "reason": ""}


def cmd_detect(args):
    intent = _read_json(args.intent)
    result = detect(intent, args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"required: {result['required']} ({result['confidence']})")
    for reason in result["reasons"]:
        print(f"- {reason}")
    if result["suggested_agents"]:
        print("agents: " + ", ".join(result["suggested_agents"]))


def cmd_check(args):
    run_data = _read_json(paths.run_path(args.root, args.run))
    intent = _read_json(paths.intent_path(args.root, args.run, run_data))
    result = audit_status(args.root, args.run, args.wo, intent)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 2)


def cmd_record_audit(args):
    audit = _read_json(args.file)
    if audit.get("verdict") not in VERDICTS:
        sys.exit(f"audit.verdict must be one of {sorted(VERDICTS)}")
    audit["run"] = args.run
    audit["wo"] = args.wo
    os.makedirs(paths.science_audit_dir(args.root, args.run), exist_ok=True)
    path = audit_path(args.root, args.run, args.wo)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    print(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("detect")
    p.add_argument("--intent", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("check")
    p.add_argument("--run", required=True)
    p.add_argument("--wo", required=True)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("record-audit")
    p.add_argument("--run", required=True)
    p.add_argument("--wo", required=True)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_record_audit)

    args = ap.parse_args()
    if not args.root:
        args.root = os.getcwd()
    args.func(args)


if __name__ == "__main__":
    main()

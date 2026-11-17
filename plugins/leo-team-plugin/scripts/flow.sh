#!/usr/bin/env bash
# flow.sh — leo-team-plugin run state controller (bash + python3, no jq).
# Usage: flow.sh init --run <name> | next | transition --to <state> [--unit <WP-ID>] [--by <name>]
#        | add-unit --id <WP-ID> --owner <role> --files "<glob,glob>" [--by <name>]
#        | claim --unit <WP-ID> [--files "<glob,glob>"] | release | reopen --unit <WP-ID> --reason <text> [--force true]
#        | recover | set [--science-gate-researcher true|false] [--science-gate-auditor true|false]
#        |         [--branch <b>] [--round <n>]
#        | status | checkpoint --note "<text>"
# State: <repo>/.team/<run>/flow.json  (base dir override: LEO_TEAM_DIR)
# Scope: validates transition legality only; content gates live in phases/*.md
#        and check-team-complete.sh.
set -euo pipefail

python3 - "$@" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MISSION_STATES = ["planning", "gate", "executing", "reviewing", "verified", "blocked"]
MISSION_TRANSITIONS = {
    "planning": {"gate", "blocked"},
    "gate": {"executing", "blocked"},
    "executing": {"reviewing", "blocked"},
    "reviewing": {"verified", "blocked"},
    "verified": {"blocked"},
    "blocked": set(),
}

UNIT_STATES = [
    "pending", "in_progress", "for_review", "approved",
    "merged", "verified", "changes_requested", "blocked",
]
UNIT_TRANSITIONS = {
    "pending": {"in_progress", "blocked"},
    "in_progress": {"for_review", "blocked"},
    "for_review": {"approved", "changes_requested", "blocked"},
    "changes_requested": {"in_progress", "blocked"},
    "approved": {"merged", "blocked"},
    "merged": {"verified", "blocked"},
    "verified": {"blocked"},
    "blocked": set(),
}
CLAIMABLE_LANES = {"pending", "in_progress", "changes_requested"}


def fail(msg, code=1):
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(code)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def load_flow():
    path = find_flow(base_dir())
    if path is None:
        fail(f"未找到 flow.json（目录：{base_dir()}）。先执行 flow.sh init --run <name>")
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"无法读取 {path}：{exc}")


def save_flow(path, flow):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_opts(args):
    opts = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("--"):
            fail(f"未知参数：{arg}")
        if i + 1 >= len(args):
            fail(f"参数 {arg} 缺少值")
        opts[arg[2:]] = args[i + 1]
        i += 2
    return opts


def require(opts, key):
    value = opts.get(key, "").strip()
    if not value:
        fail(f"缺少 --{key}")
    return value


def append_event(flow, event):
    event = {"ts": now_iso(), **event}
    flow.setdefault("events", []).append(event)


def actor(opts):
    return opts.get("by", "").strip() or os.environ.get("USER") or "flow.sh"


def find_unit(flow, unit_id):
    for unit in flow.get("units", []):
        if unit.get("id") == unit_id:
            return unit
    fail(f"unit {unit_id} 不存在。现有：{', '.join(u.get('id', '') for u in flow.get('units', [])) or '无'}")


def last_block_event(flow, unit=None):
    for ev in reversed(flow.get("events", [])):
        if ev.get("to") != "blocked":
            continue
        if unit is None or ev.get("unit") == unit:
            return ev
    return None


def block_detail(flow, unit=None):
    ev = last_block_event(flow, unit)
    if ev:
        return f"（by {ev.get('by') or 'unknown'} @ {ev.get('ts', '')}）"
    return ""


def compute_next(flow):
    mission = flow.get("mission", "planning")
    units = flow.get("units", [])
    claim = flow.get("claim")

    if mission == "blocked":
        return f"人工裁决：mission 处于 blocked{block_detail(flow)}", "human", "-"
    blocked_units = [u for u in units if u.get("lane") == "blocked"]
    if blocked_units:
        unit = blocked_units[0]
        return f"人工裁决：{unit['id']} 处于 blocked{block_detail(flow, unit['id'])}", "human", unit["id"]
    if mission == "planning":
        return "N1 Phase A：写 init.md", "n1", "-"
    if mission == "gate":
        return "N2 硬门禁：等待用户 confirmed", "n2", "-"
    stuck = [u for u in units if u.get("lane") == "changes_requested" and u.get("failures", 0) >= 3]
    if stuck:
        unit = stuck[0]
        return f"人工裁决：{unit['id']} 连续失败 {unit.get('failures', 0)} 次", "human", unit["id"]
    reviewing = [u for u in units if u.get("lane") == "for_review"]
    if reviewing:
        return f"评审 {reviewing[0]['id']}", "review", reviewing[0]["id"]
    approved = [u for u in units if u.get("lane") == "approved"]
    if approved:
        return f"合并 {approved[0]['id']} 到集成分支", "merge", approved[0]["id"]
    merged = [u for u in units if u.get("lane") == "merged"]
    if merged:
        return f"验收 {merged[0]['id']}", "verify", merged[0]["id"]
    pending = [u for u in units if u.get("lane") == "pending"]
    if pending and claim is None:
        return f"claim 并执行 {pending[0]['id']}", "claim", pending[0]["id"]
    if claim is not None:
        unit = claim.get("unit", "-")
        return f"执行中：{unit}（claim 已持有）", "execute", unit
    all_verified = bool(units) and all(u.get("lane") == "verified" for u in units)
    if all_verified and mission != "verified":
        return "进入 N6 集成验收", "n6", "-"
    if all_verified and mission == "verified":
        return "全部完成（mission=verified）", "done", "-"
    return "N5 Round Review", "round_review", "-"


def cmd_init(args):
    opts = parse_opts(args)
    run = require(opts, "run")
    if "/" in run or run in (".", ".."):
        fail("run 名称不能包含 / 或为 . / ..")
    base = base_dir()
    run_dir = base / run
    flow_path = run_dir / "flow.json"
    if flow_path.exists():
        fail(f"{flow_path} 已存在，拒绝覆盖（如需重来请先手动删除）")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "snapshots").mkdir(exist_ok=True)
    (run_dir / "prompts").mkdir(exist_ok=True)
    (run_dir / "verdicts").mkdir(exist_ok=True)
    flow = {
        "run": run,
        "round": 1,
        "mission": "planning",
        "science_gate": {"researcher": False, "auditor": False},
        "branch": f"feat/{run}",
        "units": [],
        "claim": None,
        "counters": {"consecutive_same_error": 0},
        "events": [],
    }
    save_flow(flow_path, flow)
    print(f"已初始化 run {run}：{flow_path}")
    return 0


def cmd_next(args):
    parse_opts(args)
    _, flow = load_flow()
    text, action, unit = compute_next(flow)
    print(f"建议动作：{text}")
    print(f"KEY action={action} unit={unit} mission={flow.get('mission', '?')}")
    return 0


def cmd_transition(args):
    opts = parse_opts(args)
    target = require(opts, "to")
    unit_id = opts.get("unit", "").strip()
    by = actor(opts)
    path, flow = load_flow()

    if unit_id:
        if target not in UNIT_STATES:
            fail(f"未知 unit 状态：{target}。合法状态：{', '.join(UNIT_STATES)}")
        unit = find_unit(flow, unit_id)
        current = unit.get("lane", "pending")
        allowed = UNIT_TRANSITIONS.get(current, set())
        if target not in allowed:
            fail(f"非法 unit 转移：{current} → {target}。允许的目标："
                 f"{', '.join(sorted(allowed)) or '无'}")
        if current == "pending" and target == "in_progress" and not unit.get("owner"):
            fail(f"前置条件不满足：{unit_id} 没有 owner，不能进入 in_progress")
        if current == "changes_requested" and target == "in_progress" and unit.get("failures", 0) >= 3:
            fail(f"前置条件不满足：{unit_id} failures={unit.get('failures', 0)} >= 3，需人工裁决")
        unit["lane"] = target
        if target == "changes_requested":
            unit["failures"] = unit.get("failures", 0) + 1
        if target == "for_review":
            flow["claim"] = None
        append_event(flow, {"type": "transition", "unit": unit_id, "to": target, "by": by})
        save_flow(path, flow)
        print(f"{unit_id}: {current} → {target}（by {by}）")
        return 0

    if target not in MISSION_STATES:
        fail(f"未知 mission 状态：{target}。合法状态：{', '.join(MISSION_STATES)}")
    current = flow.get("mission", "planning")
    allowed = MISSION_TRANSITIONS.get(current, set())
    if target not in allowed:
        fail(f"非法 mission 转移：{current} → {target}。允许的目标："
             f"{', '.join(sorted(allowed)) or '无'}")
    flow["mission"] = target
    append_event(flow, {"type": "transition", "to": target, "by": by})
    save_flow(path, flow)
    print(f"mission: {current} → {target}（by {by}）")
    return 0


def covered_by(glob, owned):
    """glob 是否被某个 owned_files 条目覆盖（保守判定）。"""
    if glob == owned:
        return True
    if owned.endswith("/**"):
        prefix = owned[:-3]
        return glob == prefix or glob.startswith(prefix + "/")
    return False


def cmd_claim(args):
    opts = parse_opts(args)
    unit_id = require(opts, "unit")
    files_raw = opts.get("files", "").strip()
    by = actor(opts)
    path, flow = load_flow()
    if flow.get("claim") is not None:
        held = flow["claim"].get("unit", "?")
        fail(f"已有 claim（{held}），请先 flow.sh release")
    unit = find_unit(flow, unit_id)
    lane = unit.get("lane", "pending")
    if lane not in CLAIMABLE_LANES:
        fail(f"{unit_id} 当前 lane={lane}，不能 claim（可 claim：{', '.join(sorted(CLAIMABLE_LANES))}）")
    owned = unit.get("owned_files") or []
    if not owned:
        fail(f"{unit_id} 没有 owned_files，不能 claim")
    if files_raw:
        globs = [g.strip() for g in files_raw.split(",") if g.strip()]
        if not globs:
            fail("--files 至少需要一个 glob")
        widened = [g for g in globs if not any(covered_by(g, o) for o in owned)]
        if widened:
            fail(f"claim 范围超出 {unit_id} 的 owned_files：{', '.join(widened)}；"
                 f"允许：{', '.join(owned)}")
    else:
        globs = list(owned)
    flow["claim"] = {"unit": unit_id, "files": globs, "by": by, "ts": now_iso()}
    append_event(flow, {"type": "claim", "unit": unit_id, "files": globs, "by": by})
    save_flow(path, flow)
    print(f"已 claim {unit_id}（files: {', '.join(globs)}）")
    return 0


def cmd_release(args):
    parse_opts(args)
    path, flow = load_flow()
    claim = flow.get("claim")
    if claim is None:
        print("当前没有 claim，无需 release")
        return 0
    flow["claim"] = None
    append_event(flow, {"type": "release", "unit": claim.get("unit"), "by": os.environ.get("USER") or "flow.sh"})
    save_flow(path, flow)
    print(f"已 release {claim.get('unit', '?')}")
    return 0


def cmd_status(args):
    parse_opts(args)
    _, flow = load_flow()
    units = flow.get("units", [])
    claim = flow.get("claim")
    gate = flow.get("science_gate", {})
    print(f"Run: {flow.get('run', '?')}")
    print(f"Mission: {flow.get('mission', '?')}")
    print(f"Round: {flow.get('round', '?')}")
    print(f"Branch: {flow.get('branch', '?')}")
    print(f"Science gate: researcher={str(bool(gate.get('researcher'))).lower()} "
          f"auditor={str(bool(gate.get('auditor'))).lower()}")
    print("Units:")
    if not units:
        print("  (none)")
    for unit in units:
        line = (f"  {unit.get('id', '?'):<8} {unit.get('lane', '?'):<18} "
                f"owner={unit.get('owner') or '-'}")
        files = unit.get("owned_files") or []
        if files:
            line += f"  files={','.join(files)}"
        if claim and claim.get("unit") == unit.get("id"):
            line += "  [claim]"
        print(line)
    if claim:
        print(f"Claim: {claim.get('unit', '?')}（by {claim.get('by', '?')}）")
    else:
        print("Claim: none")
    blockers = []
    if flow.get("mission") == "blocked":
        blockers.append("mission 处于 blocked")
    for unit in units:
        if unit.get("lane") == "blocked":
            blockers.append(f"{unit.get('id')} 处于 blocked")
        elif unit.get("lane") == "changes_requested" and unit.get("failures", 0) >= 3:
            blockers.append(f"{unit.get('id')} 连续失败 {unit.get('failures')} 次")
    print("Blockers: " + ("；".join(blockers) if blockers else "none"))
    print(f"Next: {compute_next(flow)[0]}")
    return 0


def cmd_checkpoint(args):
    opts = parse_opts(args)
    note = opts.get("note", "")
    path, flow = load_flow()
    snap_dir = path.parent / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    snap = snap_dir / f"{ts.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    payload = {"ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "note": note, "flow": flow}
    snap.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写检查点 {snap}")
    return 0


def cmd_add_unit(args):
    opts = parse_opts(args)
    unit_id = require(opts, "id")
    owner = require(opts, "owner")
    files_raw = require(opts, "files")
    by = actor(opts)
    globs = [g.strip() for g in files_raw.split(",") if g.strip()]
    if not globs:
        fail("--files 至少需要一个 glob")
    path, flow = load_flow()
    units = flow.setdefault("units", [])
    if any(u.get("id") == unit_id for u in units):
        fail(f"unit {unit_id} 已存在")
    units.append({
        "id": unit_id,
        "lane": "pending",
        "owner": owner,
        "owned_files": globs,
        "failures": 0,
    })
    append_event(flow, {"type": "add_unit", "unit": unit_id, "owner": owner, "files": globs, "by": by})
    save_flow(path, flow)
    print(f"已添加 {unit_id}（owner: {owner}，files: {', '.join(globs)}）")
    return 0


def cmd_reopen(args):
    opts = parse_opts(args)
    unit_id = require(opts, "unit")
    reason = require(opts, "reason")
    force = opts.get("force", "").strip().lower() in ("true", "yes", "1")
    by = actor(opts)
    path, flow = load_flow()
    unit = find_unit(flow, unit_id)
    current = unit.get("lane", "pending")
    if current == "changes_requested" and unit.get("failures", 0) >= 3 and not force:
        fail(f"{unit_id} failures={unit.get('failures', 0)} >= 3，需人工裁决；"
             f"用户确认后加 --force true 并写明理由")
    unit["lane"] = "pending"
    if flow.get("claim") and flow["claim"].get("unit") == unit_id:
        flow["claim"] = None
    append_event(flow, {"type": "reopen", "unit": unit_id, "from": current, "reason": reason, "by": by})
    save_flow(path, flow)
    print(f"{unit_id}: {current} → pending（reopen：{reason}）")
    return 0


def cmd_recover(args):
    opts = parse_opts(args)
    by = actor(opts)
    path, flow = load_flow()
    changed = []
    claim = flow.get("claim")
    if claim is not None:
        changed.append(f"释放 stale claim（{claim.get('unit', '?')}）")
        flow["claim"] = None
    if flow.get("mission") == "blocked":
        units = flow.get("units", [])
        resumed = "executing" if units else "planning"
        flow["mission"] = resumed
        changed.append(f"mission blocked → {resumed}")
    append_event(flow, {"type": "recover", "changes": changed, "by": by})
    save_flow(path, flow)
    print("恢复完成：" + ("；".join(changed) if changed else "无变化"))
    return 0


def cmd_set(args):
    opts = parse_opts(args)
    path, flow = load_flow()
    changed = []
    gate = flow.setdefault("science_gate", {"researcher": False, "auditor": False})
    for key, flag in (("researcher", "science-gate-researcher"), ("auditor", "science-gate-auditor")):
        raw = opts.get(flag, "").strip().lower()
        if not raw:
            continue
        if raw not in ("true", "false"):
            fail(f"--{flag} 只接受 true / false")
        gate[key] = raw == "true"
        changed.append(f"science_gate.{key}={raw}")
    branch = opts.get("branch", "").strip()
    if branch:
        flow["branch"] = branch
        changed.append(f"branch={branch}")
    round_raw = opts.get("round", "").strip()
    if round_raw:
        try:
            round_no = int(round_raw)
        except ValueError:
            fail("--round 只接受整数")
        if round_no < 1:
            fail("--round 必须 >= 1")
        flow["round"] = round_no
        changed.append(f"round={round_no}")
    if not changed:
        fail("没有任何要设置的字段")
    append_event(flow, {"type": "set", "changes": changed, "by": actor(opts)})
    save_flow(path, flow)
    print("已设置：" + "；".join(changed))
    return 0


COMMANDS = {
    "init": cmd_init,
    "next": cmd_next,
    "transition": cmd_transition,
    "add-unit": cmd_add_unit,
    "claim": cmd_claim,
    "release": cmd_release,
    "reopen": cmd_reopen,
    "recover": cmd_recover,
    "set": cmd_set,
    "status": cmd_status,
    "checkpoint": cmd_checkpoint,
}


def main(argv):
    if not argv:
        print(__doc__ if __doc__ else "用法：flow.sh <init|next|transition|claim|release|status|checkpoint>")
        return 1
    cmd = argv[0]
    if cmd not in COMMANDS:
        fail(f"未知子命令：{cmd}。可用：{', '.join(COMMANDS)}")
    return COMMANDS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
PY

#!/usr/bin/env bash
# validate-lane-write.sh — leo-team-plugin hook guard (reads hook JSON from stdin).
# Modes: (none)=PreToolUse Write/Edit  --bash=PreToolUse Bash  --subagent-stop
#        --stop  --precompact
# Allows silently when no .team/<run>/flow.json exists. Base dir override: LEO_TEAM_DIR
set -uo pipefail

# The python program below occupies stdin, so keep the hook payload on fd 9.
exec 9<&0
LEO_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LEO_SCRIPT_DIR
if [ -t 0 ]; then
  LEO_HOOK_HAS_INPUT=0
else
  LEO_HOOK_HAS_INPUT=1
fi
export LEO_HOOK_HAS_INPUT

python3 - "$@" <<'PY'
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SPECIAL_ALLOWS = [
    "**/findings.md",          # 全员：各自 section
    "**/progress.md",          # 全员：只追加
    "**/inspect.md",           # spec-explorer 独占
    "**/architecture-review.md",  # spec-architect 独占
    "**/research.md",          # spec-science-researcher 独占
    "**/science-audit.md",     # spec-science-auditor 独占
]


def out(payload):
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def allow():
    sys.exit(0)


def now_ts():
    return datetime.now().timestamp()


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


def load():
    base = base_dir()
    path = find_flow(base)
    if path is None:
        return None, None, base
    try:
        return path, json.loads(path.read_text(encoding="utf-8")), base
    except (OSError, json.JSONDecodeError):
        return None, None, base


def read_input():
    if os.environ.get("LEO_HOOK_HAS_INPUT") != "1":
        return {}
    try:
        with os.fdopen(9, "r", encoding="utf-8") as handle:
            raw = handle.read()
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def is_active_stop(data):
    return bool(data.get("stop_hook_active"))


def deny(system_message):
    # Official schema requires hookEventName + permissionDecisionReason;
    # without them Claude Code ignores the decision and the tool call proceeds.
    out({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": system_message,
        },
        "systemMessage": system_message,
    })


def block(reason):
    out({"decision": "block", "reason": reason})


def norm_rel(file_path, base):
    raw = str(file_path).replace("\\", "/")
    if not os.path.isabs(raw):
        while raw.startswith("./"):
            raw = raw[2:]
        return os.path.normpath(raw).replace("\\", "/")
    path = Path(os.path.normpath(raw)).resolve()
    roots = [Path.cwd().resolve(), base.parent.resolve()]
    for root in roots:
        try:
            return str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
    return raw


_GLOB_CACHE = {}


def glob_regex(pattern):
    if pattern in _GLOB_CACHE:
        return _GLOB_CACHE[pattern]
    parts = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                i += 2
                if i < len(pattern) and pattern[i] == "/":
                    i += 1
                    parts.append("(?:.*/)?")
                else:
                    parts.append(".*")
                continue
            parts.append("[^/]*")
        elif ch == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(ch))
        i += 1
    compiled = re.compile("^" + "".join(parts) + "$")
    _GLOB_CACHE[pattern] = compiled
    return compiled


def path_matches(rel, pattern):
    pattern = pattern.replace("\\", "/").lstrip("./")
    rel = rel.lstrip("./")
    return bool(glob_regex(pattern).match(rel))


def allowed_paths(rel, globs):
    for pattern in list(globs) + SPECIAL_ALLOWS:
        if path_matches(rel, pattern):
            return True
    return False


def handle_write(data, base):
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        allow()
    _, flow, _ = load()
    if flow is None:
        allow()
    claim = flow.get("claim")
    if not claim:
        allow()
    rel = norm_rel(file_path, base)
    globs = claim.get("files") or []
    if allowed_paths(rel, globs):
        allow()
    deny(f"写入 {rel} 超出当前工作单元范围；允许：{', '.join(globs + SPECIAL_ALLOWS)}")


GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path", "--config-env", "--super-prefix"}
RM_ROOT_RE = re.compile(r"\brm\s+(?:-[^\s]+\s+)*?/(?=\s|$|[;&|*])")
CHMOD_ROOT_RE = re.compile(r"\bchmod\s+(?:-[^\s]+\s+)*?777\s+/(?=\s|$|[;&|*])")


def git_subcommands(command):
    """Yield git subcommands from each shell segment (best-effort, not a sandbox)."""
    for segment in re.split(r"(?:\|\||&&|[;&|\n])", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in ("sudo", "command", "env", "nohup", "time") or re.match(r"^[A-Za-z_]\w*=", token):
                i += 1
                continue
            break
        if i >= len(tokens) or os.path.basename(tokens[i]) != "git":
            continue
        j = i + 1
        while j < len(tokens) and tokens[j].startswith("-"):
            j += 2 if tokens[j] in GIT_VALUE_OPTS else 1
        if j < len(tokens):
            yield tokens[j]


def current_branch():
    for args in (["git", "symbolic-ref", "--short", "HEAD"],
                 ["git", "rev-parse", "--abbrev-ref", "HEAD"]):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return ""


SAFE_TARGETS = {"/dev/null", "/dev/stdout", "/dev/stderr"}
SAFE_PREFIXES = ("/tmp/", "/var/tmp/", "/private/tmp/", "/private/var/tmp/")
SAFE_EXACT = {"/tmp", "/var/tmp", "/private/tmp", "/private/var/tmp"}
WRITE_CMDS = {"tee", "cp", "mv", "install", "ln", "truncate", "rm", "unlink", "shred"}
INPLACE_CMDS = {"sed", "perl", "ruby", "gsed"}
SHELL_SPLIT = re.compile(r"(?:\|\||&&|[;&|\n])")


def _safe_target(target):
    """无法静态解析或明确无害的目标不拦截（best-effort，不是沙箱）。"""
    t = target.strip("'\"")
    if not t:
        return True
    if t in SAFE_TARGETS or t in SAFE_EXACT:
        return True
    if t.startswith(SAFE_PREFIXES):
        return True
    if t.startswith("$") or t.startswith("/dev/fd/"):
        return True          # 变量展开、进程替换：无法静态判定
    if t.isdigit():
        return True          # [ 1 > 0 ] / ((1>0)) 之类的比较表达式
    return False


def _tokens(segment):
    try:
        return shlex.split(segment)
    except ValueError:
        return []


def _args_after_cmd(tokens):
    """跳过 sudo/env/变量赋值 与前导选项，返回 (cmd_name, 参数列表)。"""
    i = 0
    while i < len(tokens) and (tokens[i] in ("sudo", "command", "env", "nohup", "time")
                               or re.match(r"^[A-Za-z_]\w*=", tokens[i])):
        i += 1
    if i >= len(tokens):
        return "", []
    name = os.path.basename(tokens[i])
    return name, tokens[i + 1:]


def _non_option(args):
    out, after_ddash = [], False
    for arg in args:
        if arg == "--":
            after_ddash = True
            continue
        if not after_ddash and arg.startswith("-"):
            continue
        out.append(arg)
    return out


def bash_write_targets(command):
    """Best-effort extraction of files a Bash command writes to. NOT a sandbox."""
    targets = []
    # 重定向在整条命令上匹配：按 | 分片会把 `>|` 拆坏
    for m in re.finditer(r">>?\|?\s*([^\s;&|)]+)", command):
        targets.append(m.group(1))
    for segment in SHELL_SPLIT.split(command):
        name, args = _args_after_cmd(_tokens(segment))
        if not name:
            continue
        if name in ("tee",):
            targets.extend(_non_option(args))
        elif name in ("cp", "mv", "install", "ln"):
            vals = _non_option(args)
            if len(vals) >= 2:
                targets.append(vals[-1])
        elif name == "dd":
            targets.extend(a[3:] for a in args if a.startswith("of="))
        elif name in ("truncate", "unlink", "shred", "rm"):
            targets.extend(_non_option(args))
        elif name in INPLACE_CMDS and any(a.startswith("-i") or a.startswith("-pi")
                                          or a.startswith("-ip") or a.startswith("--in-place")
                                          for a in args):
            vals = _non_option(args)
            if vals:
                targets.append(vals[-1])
        elif name == "git" and args:
            vals = _non_option(args)
            if vals and vals[0] == "restore":
                if "--" in args:
                    targets.extend(_non_option(args[args.index("--") + 1:]))
                else:
                    targets.extend(vals[1:])
            elif vals and vals[0] in ("checkout",) and "--" in args:
                targets.extend(_non_option(args[args.index("--") + 1:]))
    return [t for t in targets if not _safe_target(t)]


def handle_bash(data, base):
    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        allow()
    path, flow, _ = load()
    if flow is None:
        allow()
    subcommands = list(git_subcommands(command))
    if "push" in subcommands:
        deny("禁止 git push：本流程要求由 PM 合并到集成分支（rails R-8）")
    if RM_ROOT_RE.search(command):
        deny("禁止高危命令：递归删除根目录")
    if CHMOD_ROOT_RE.search(command):
        deny("禁止高危命令：chmod 777 根目录")
    if "commit" in subcommands:
        branch = current_branch()
        if branch in ("main", "master"):
            deny(f"禁止在 {branch} 分支 commit：请先切到工作分支（rails R-8）")
    claim = flow.get("claim")
    if claim:
        globs = claim.get("files") or []
        for target in bash_write_targets(command):
            rel = norm_rel(target, base)
            if not allowed_paths(rel, globs):
                deny(f"Bash 写入 {rel} 超出当前工作单元范围"
                     f"（claim: {claim.get('unit', '?')}）。请改用 Write/Edit 或先释放 claim。")
    allow()


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def handle_subagent_stop(data, base):
    if is_active_stop(data):
        allow()
    path, flow, _ = load()
    if flow is None:
        allow()
    claim = flow.get("claim")
    if not claim:
        allow()
    since = parse_ts(claim.get("ts")) or 0
    verdicts_dir = path.parent / "verdicts"
    found = False
    if verdicts_dir.is_dir():
        for candidate in verdicts_dir.glob("*.json"):
            try:
                if candidate.stat().st_mtime + 1 < since:
                    continue
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("verdict"):
                found = True
                break
    if found:
        allow()
    block("回传缺少 verdict，请按 rails.md R-10 输出回传契约")


def next_suggestion(flow):
    mission = flow.get("mission", "planning")
    units = flow.get("units", [])
    claim = flow.get("claim")
    if mission == "blocked" or any(u.get("lane") == "blocked" for u in units):
        return "人工裁决"
    if mission == "planning":
        return "N1 Phase A：写 init.md"
    if mission == "gate":
        return "N2 硬门禁：等待用户 confirmed"
    for unit in units:
        if unit.get("lane") == "changes_requested" and unit.get("failures", 0) >= 3:
            return "人工裁决"
    for unit in units:
        if unit.get("lane") == "for_review":
            return f"评审 {unit.get('id')}"
    for unit in units:
        if unit.get("lane") == "approved":
            return f"合并 {unit.get('id')} 到集成分支"
    for unit in units:
        if unit.get("lane") == "merged":
            return f"验收 {unit.get('id')}"
    if claim:
        return f"执行中：{claim.get('unit')}（claim 已持有）"
    for unit in units:
        if unit.get("lane") == "pending":
            return f"claim 并执行 {unit.get('id')}"
    if units and all(u.get("lane") == "verified" for u in units):
        return "进入 N6 集成验收"
    return "N5 Round Review"


def find_audit(path, flow):
    """只认本 run 的产物目录，与 check-team-complete.sh 保持一致。"""
    run = flow.get("run") or path.parent.name
    candidates = [
        Path.cwd() / ".dev" / run / "generated" / "science-audit.md",
        Path.cwd() / ".dev" / run / "science-audit.md",
        path.parent / "science-audit.md",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def handle_stop(data, base):
    if is_active_stop(data):
        allow()
    path, flow, _ = load()
    if flow is None:
        allow()
    reasons = []
    mission = flow.get("mission", "planning")
    if mission != "verified":
        reasons.append(f"mission 当前为 {mission}，尚未 verified；flow.sh next 建议：{next_suggestion(flow)}")
    gate = flow.get("science_gate") or {}
    if gate.get("auditor") and find_audit(path, flow) is None:
        reasons.append("science_gate.auditor=true 但 science-audit.md 不存在")
    if mission == "verified" and not reasons:
        script_dir = os.environ.get("LEO_SCRIPT_DIR")
        if script_dir:
            try:
                proc = subprocess.run(
                    ["bash", os.path.join(script_dir, "check-team-complete.sh")],
                    capture_output=True, text=True, timeout=15,
                )
                report = (proc.stdout or "").strip()
                if "NOT COMPLETE" in report:
                    reasons.append("完成检查未通过：\n" + report)
                elif "OK" not in report.split():
                    reasons.append("完成检查未返回明确结论：\n" + report)
            except (OSError, subprocess.SubprocessError):
                reasons.append("无法运行 check-team-complete.sh，完成状态未验证")
    if reasons:
        block("；".join(reasons))
    allow()


def handle_precompact(data, base):
    path, flow, _ = load()
    if flow is None:
        allow()
    if flow.get("mission") not in ("executing", "reviewing"):
        allow()
    snap_dir = path.parent / "snapshots"
    snaps = list(snap_dir.glob("*.json")) if snap_dir.is_dir() else []
    if not snaps:
        block(f"mission={flow.get('mission')} 且 snapshots/ 为空，请先执行 "
              f'flow.sh checkpoint --note "..." 再压缩上下文')
    latest = max(s.stat().st_mtime for s in snaps)
    age_min = (now_ts() - latest) / 60
    if age_min > 30:
        block(f"mission={flow.get('mission')} 且最新检查点已 {int(age_min)} 分钟未更新，"
              f'请先执行 flow.sh checkpoint --note "..." 再压缩上下文')
    allow()


def main(argv):
    mode = argv[0] if argv else ""
    data = read_input()
    base = base_dir()
    if mode == "":
        handle_write(data, base)
    elif mode == "--bash":
        handle_bash(data, base)
    elif mode == "--subagent-stop":
        handle_subagent_stop(data, base)
    elif mode == "--stop":
        handle_stop(data, base)
    elif mode == "--precompact":
        handle_precompact(data, base)
    else:
        allow()


if __name__ == "__main__":
    main(sys.argv[1:])
PY

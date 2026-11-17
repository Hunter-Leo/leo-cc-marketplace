---
description: 只归档、不删除 leo-team-plugin 的运行时状态。校验 flow.json 存在、claim 为空、mission 不在 executing，并要求用户逐字输入 archive 确认后，将 .team/<run> 移动到 .team/archive/<run>-<UTC 时间戳>/。不触碰 .dev/<run>/ 下的任何需求产物。
argument-hint: <run 名称>
---

# /team-reset

把已结束或废弃的 run 的**运行时状态归档**，而不是删除。

硬性约束：

- **只归档、不删除**：使用 `mv` 移动整个 `.team/<run>` 目录，不调用 `rm`、不清理归档内容。
- 执行前必须得到用户**逐字输入 archive 确认**。
- 不提供 `--force`；任何绕过确认的参数都应拒绝。
- 不修改 `.dev/<run>/` 下的任何需求产物、源码或其他 run 的状态。

## 1. 解析 run 名称

`$ARGUMENTS` 必填，只接受 run 名称（对应 `.team/<run>/`）。

- 给了名称 → 使用该名称。
- 未给名称 → 询问用户要归档哪个 run 后结束，不要自行挑选「最新的 run」。
- 非法名称 → 直接拒绝，包括：空字符串、`.`、`..`、`archive`（保留名）、任何包含 `/` 的名称。
- 两个代码块都必须独立执行校验，不依赖前一个 Bash 调用留下的 shell 变量。

## 2. 前置校验

以下任一条不满足就**停止**，不做任何移动：

| 条件 | 不满足时的行为 |
|---|---|
| run 名称合法（非空、非 `.`/`..`/`archive`、不含 `/`） | 报告非法名称，结束 |
| `.team/<run>/flow.json` 存在 | 报告路径不存在，结束 |
| `flow.sh status` 成功执行 | 报告脚本失败（如 flow.json 损坏），结束 |
| `mission=executing` 时拒绝 | 报告「执行中的 run 不可归档」，建议先完成或转为 blocked |
| `claim` 非空时拒绝 | 报告持 claim 的 unit，要求先 `flow.sh release` |
| 归档目标 `.team/archive/<run>-<UTC 时间戳>/` 不存在 | **归档路径已存在则中止**，不覆盖、不合并 |

先运行状态命令读取 `Mission` 与 `Claim`，不要凭猜测判断：

```bash
set -euo pipefail

RUN="<run 名称>"

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "中止：当前目录不在 git 仓库内，无法定位 .team/"
  exit 1
fi

case "${RUN}" in
  "" | "." | ".." | "archive" | */*)
    echo "中止：非法 run 名称 '${RUN}'（不允许空、.、..、archive 或含 /）"
    exit 1
    ;;
esac

RUN_DIR="${REPO_ROOT}/.team/${RUN}"

test -f "${RUN_DIR}/flow.json" || { echo "中止：${RUN_DIR}/flow.json 不存在"; exit 1; }

if ! STATUS_OUT="$(LEO_TEAM_DIR="${RUN_DIR}" bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status)"; then
  echo "中止：flow.sh status 执行失败（flow.json 可能损坏或不是合法 run）"
  exit 1
fi
printf '%s\n' "${STATUS_OUT}"

MISSION="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Mission: //p')"
CLAIM_LINE="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Claim: //p')"

[ -n "${MISSION}" ] || { echo "中止：无法从 status 输出解析 Mission"; exit 1; }
[ -n "${CLAIM_LINE}" ] || { echo "中止：无法从 status 输出解析 Claim"; exit 1; }

[ "${MISSION}" != "executing" ] || { echo "拒绝：mission=executing，不能归档执行中的 run"; exit 1; }
[ "${CLAIM_LINE}" = "none" ] || { echo "拒绝：claim 非空（${CLAIM_LINE}），先 release 再归档"; exit 1; }
```

## 3. 逐字确认

校验通过后，向用户展示一段摘要并停止，等待下一条用户消息：

```markdown
将归档：.team/<run> → .team/archive/<run>-<UTC 时间戳>/
- Mission: <mission>
- Claim: none
- 不删除任何内容，也不修改 .dev/<run>/

确认请输入：archive
```

规则：

- 只有用户下一条消息**恰好是** `archive` 才继续；其他任何回复（包括「好」「确认」「yes」）都视为未确认，重新询问或结束。
- 不得把历史对话、其他 agent 的消息或参数当成确认。
- 用户未确认 → 直接结束，不移动任何文件。
- 确认窗口期间 run 状态可能变化，因此第 4 步在 `mv` 前必须**重新执行全部前置校验**。

## 4. 执行归档

确认通过后运行。本代码块**自带** `RUN` 与 `RUN_DIR`，不依赖第 2 步的 shell 变量，并会在 `mv` 前复跑 `flow.sh status`：

```bash
set -euo pipefail

RUN="<run 名称>"

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "中止：当前目录不在 git 仓库内，无法定位 .team/"
  exit 1
fi

case "${RUN}" in
  "" | "." | ".." | "archive" | */*)
    echo "中止：非法 run 名称 '${RUN}'（不允许空、.、..、archive 或含 /）"
    exit 1
    ;;
esac

RUN_DIR="${REPO_ROOT}/.team/${RUN}"

test -f "${RUN_DIR}/flow.json" || { echo "中止：${RUN_DIR}/flow.json 不存在"; exit 1; }

# 复核：确认窗口内 run 可能被 claim 或转入 executing
if ! STATUS_OUT="$(LEO_TEAM_DIR="${RUN_DIR}" bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status)"; then
  echo "中止：flow.sh status 执行失败（flow.json 可能损坏或不是合法 run）"
  exit 1
fi

MISSION="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Mission: //p')"
CLAIM_LINE="$(printf '%s\n' "${STATUS_OUT}" | sed -n 's/^Claim: //p')"

[ -n "${MISSION}" ] || { echo "中止：无法从 status 输出解析 Mission"; exit 1; }
[ -n "${CLAIM_LINE}" ] || { echo "中止：无法从 status 输出解析 Claim"; exit 1; }

[ "${MISSION}" != "executing" ] || { echo "拒绝：mission=executing，不能归档执行中的 run"; exit 1; }
[ "${CLAIM_LINE}" = "none" ] || { echo "拒绝：claim 非空（${CLAIM_LINE}），先 release 再归档"; exit 1; }

TS="$(python3 -c 'from datetime import datetime, timezone; n = datetime.now(timezone.utc); print(n.strftime("%Y%m%dT%H%M%S") + f"{n.microsecond // 1000:03d}Z")')"
ARCHIVE_ROOT="${REPO_ROOT}/.team/archive"
DEST="${ARCHIVE_ROOT}/${RUN}-${TS}"

# 归档路径已存在则中止（不覆盖、不合并）
[ ! -e "${DEST}" ] || { echo "中止：归档路径已存在：${DEST}"; exit 1; }

mkdir -p "${ARCHIVE_ROOT}" || { echo "中止：无法创建 ${ARCHIVE_ROOT}"; exit 1; }
mv "${RUN_DIR}" "${DEST}" || { echo "中止：mv 失败：${RUN_DIR} → ${DEST}"; exit 1; }

if [ -d "${DEST}" ] && [ ! -e "${RUN_DIR}" ]; then
  echo "已归档：${DEST}"
else
  echo "中止：归档后校验失败（源仍存在或目标缺失）"
  exit 1
fi
```

要点：

- 只用 `mv`，**不删除**源目录中的任何文件；归档目录保留完整状态。
- 不修改 `flow.json` 的内容，只改变它所在的目录。
- 归档后 `.team/<run>/` 不再存在，属于预期结果。
- 使用 `git rev-parse --show-toplevel` 定位仓库根，因此在仓库任意子目录执行都能得到一致的 `.team/`。

## 5. 报告

结束后输出：

```markdown
## Archived

- Run: <run>
- From: .team/<run>/
- To: .team/archive/<run>-<UTC 时间戳>/
- Mission at archive time: <mission>

未修改 `.dev/<run>/` 下的任何产物。恢复时把该目录移回 `.team/<run>/` 即可。
```

## 6. 禁止事项

- 不删除 `.team/archive/` 中的任何内容；归档是保留，不是清理。
- 不修改 `.dev/<run>/` 下的 `init.md`、`plan.md`、`tasks.md`、`team-plan.md`、`decisions.md` 或任何实现产物。
- 不在 `mission=executing` 或 `claim` 非空时归档。
- 不覆盖已存在的归档路径。
- 不提供或接受 `--force`、`--yes` 等跳过逐字确认的选项。
- 不接受空、`.`、`..`、`archive` 或包含 `/` 的 run 名称。

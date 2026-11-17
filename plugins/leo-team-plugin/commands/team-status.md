---
description: 查看 leo-team-plugin 团队运行进度。定位 .team/*/flow.json，运行 flow.sh status 与 check-team-complete.sh，并汇总 findings.md / dead-ends.md，固定输出 Goal / Progress / Active / Blockers / Next 五段。只读，不修改任何文件。
argument-hint: [run 名称或 .dev 需求目录]
---

# /team-status

本命令是**只读**状态汇报。不得修改 `flow.json`、源码或任何产物；不得推进阶段。

## 1. 定位运行目录

按以下顺序解析：

1. `$ARGUMENTS` 给出 run 名称 → 使用 `.team/<run>/flow.json`。
2. `$ARGUMENTS` 给出 `.dev/<NNN>-<req>/` 路径 → 取目录名 `<NNN>-<req>` 作为 run 名称。
3. 无参数 → 列出 `.team/*/flow.json`，取修改时间最新的一个；若存在多个，在输出中注明「存在 N 个运行，展示最新：<run>」。

定位后可显式指定运行：

```bash
LEO_TEAM_DIR=".team/<run>" bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status
LEO_TEAM_DIR=".team/<run>" bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

未指定时也可直接运行（脚本会自动选最新运行）：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

### 找不到运行目录时

不要报错，也不要创建文件。输出启动引导后结束：

```markdown
## Goal
未找到团队运行记录（无 `.team/*/flow.json`）。

## Progress
无。

## Active
无。

## Blockers
无。

## Next
运行 `/spec-team <需求描述>` 启动一次团队流程；N0 判定通过后会创建 `.team/<req-name>/flow.json`。
```

## 2. 采集状态

1. 运行 `flow.sh status`，记录：Run、Mission、Round、Branch、Science gate、Units、Claim、Blockers、Next。
2. 运行 `check-team-complete.sh`，记录 `OK` / `NOT COMPLETE` 及其列出的阻塞项 / `NO RUN`。
3. 定位产物目录：优先 `.dev/<run>/generated/`；不存在时取 `.dev/*/generated/` 中最近修改的一个，并在输出中注明实际路径。
4. 读 `findings.md` 摘要：
   - 统计 `open` 条目按 severity 的数量（blocker / critical / major / minor / nit）。
   - 只列 blocker、critical、未接受 major 的条目前 5 条（ID + `file:line` + 一句话）。
   - 文件不存在时写「无 findings.md」。
5. 读 `dead-ends.md` 摘要：
   - 总条目数与最近 3 条（ID + 尝试 + 失败原因一句话）。
   - 文件不存在时写「无 dead-ends.md」。

只读摘要，不粘贴文件全文，不复制大段日志。

## 3. 输出格式（固定五段）

```markdown
## Goal

<需求编号与目标一句话；来自 init.md / team-plan.md；缺失时写「未记录」>

## Progress

- Mission: <planning | gate | executing | reviewing | verified | blocked>
- Round: <N>
- Branch: <name 或未创建>
- Units: pending=<n> in_progress=<n> for_review=<n> approved=<n> merged=<n> verified=<n> changes_requested=<n> blocked=<n>
- Completion: <OK | NOT COMPLETE（摘要）>
- 产物目录: <实际路径>

## Active

- Claim: <unit / by / 无>
- 进行中: <in_progress / for_review / changes_requested 的单元及 owner>
- 无活动单元时写「无」

## Blockers

- flow.sh Blockers: <none 或逐条>
- check-team-complete: <NOT COMPLETE 的阻塞项>
- findings 未决: <blocker/critical/未接受 major 摘要>
- dead ends: <最近 3 条摘要>
- 全部为空时写「无」

## Next

<直接引用 flow.sh status 的 Next；若有未决 blocker，补充「先由 PM 裁决/修复，再继续」>
```

## 4. 注意事项

- 状态只代表磁盘上的记录，不代表 teammate 仍然存活；恢复执行前必须重新 spawn 并取得本 session 回执。
- `check-team-complete.sh` 永远以 0 退出，结论看输出文本（`OK` / `NOT COMPLETE` / `NO RUN`）。
- 若 `flow.json` 无法解析，如实报告错误路径与错误信息，不猜测状态。

# Handoff

> 用途：teammates 上下文丢失后的**唯一恢复入口**。
> 每次 round 结束或 session 中断前由 PM 更新。任一固定字段缺失视为 handoff 无效，恢复时按无效处理并重新生成。

## resumption_prompt（可直接粘贴）

```text
你是 <role>，加入 run <run_id> 的 Round <N>。
仓库：<repo absolute path>，分支：<branch>，HEAD：<sha>。
先按顺序读：<run>/handoff.md → <run>/team-plan.md → <run>/findings.md → <run>/dead-ends.md。
你的工作单元：<U-xx>，owned_files：<paths>。
不要重做：<do_not_redo 摘要>。
下一步：<next_action>。
结束时按 rails R-10 回传。
```

## 状态快照

| Field | Value |
|---|---|
| round | <N> |
| branch | <branch> |
| HEAD | <sha> |
| uncommitted | <无 \| 文件列表> |
| last passing test | <命令> → <结果> @ <YYYY-MM-DD HH:MM> |
| context_minimum | <恢复所需最小文件集，按读取顺序，逗号分隔> |

## 待处理

- **open issues**: <F-xx / Q-xx 列表，含 severity；无则写「无」>
- **next_action**: <下一件具体要做的事，可直接执行>
- **do_not_redo**: <已完成或已排除的事项，指向 progress.md / dead-ends.md 条目>
- **blocked_on**: <等待谁 / 什么；无则写「无」>

## 过期策略

| Field | Value |
|---|---|
| stale_threshold_days | <默认 7> |
| stale_action | <超过阈值时：重跑 last passing test，并核对 HEAD 与 uncommitted；任一不符则本文件作废并重新生成> |
| last_verified_at | <YYYY-MM-DD HH:MM> |

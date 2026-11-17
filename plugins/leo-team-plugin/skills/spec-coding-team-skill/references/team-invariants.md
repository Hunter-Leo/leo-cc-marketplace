# Team Invariants — 本流程的落地形式

> 方法论定义见 `agent-team-authoring/references/team-invariants.md`。
> 本文件只说明**这套流程如何机械执行它们**，不重复定义。

| # | 不变量 | 在本流程中的机械保证 |
|---|---|---|
| T-1 | **Files over context** | 每个阶段有强制产物文件；`SubagentStop` 校验回传含 `verdict`；`Stop` 校验 mission 达 `verified` |
| T-2 | **Own your files** | `PreToolUse` 读 `flow.json` 的 `claim.files`，越界写入直接 `deny` |
| T-3 | **Liveness is receipt** | 恢复时不得假设 teammate 仍存活；必须重新 spawn 并收到本次 session 的首次回执才算恢复 |
| T-4 | **Keep checkpoint** | `PreCompact` 在 `executing`/`reviewing` 且无 30 分钟内快照时阻塞；`flow.sh checkpoint` 是唯一入口 |
| T-5 | **Lead coordinates** | PM 是唯一可调用 `flow.sh transition`、写 `team-plan.md`/`decisions.md` 的角色；teammate 只能建议 |

## 三条容易被违反的场景

### 场景一：PM 顺手改了一行代码

- **为什么错**：违反 T-5，且破坏了「实现者有完整上下文、验证者无实现上下文」的分离
- **机械拦截**：PM 在派活期间 `claim` 非空，写入源码路径不在 claim 内 → `deny`
- **唯一例外**：XS 级修正（注释、拼写），且必须写入 `decisions.md`

### 场景二：reviewer 自己动手修

- **为什么错**：违反 T-5 与 essence I-5，验证者变成实现者后失去独立性
- **机械拦截**：reviewer 的 `tools` 含 Write，但 lane 只允许 `findings.md` 自己的 section
- **替代动作**：写 finding + `fix` 建议，由 executor 实施

### 场景三：中断后凭记忆继续

- **为什么错**：违反 T-1 与 T-3。磁盘上的 `flow.json` 只能说明「上次到哪」，不能说明「现在谁还活着」
- **机械拦截**：恢复流程强制先跑 `flow.sh status`，再读 `dead-ends.md`，再重新 spawn
- **判断标准**：没有本次 session 的回执 = 不存在

## 违规处理

| 违规类型 | 处理 |
|---|---|
| 越界写入被 hook 拒绝 | 记录到 `findings.md`，不重试同一路径 |
| 回传缺 verdict 被拒绝 | 补全后重发；连续 2 次视为该单元失败 1 次 |
| Stop 被阻塞 | 按输出的 `next` 建议继续，不得绕过 hook |
| 恢复时未按协议 | 该轮作废，重新从 N3 组队 |

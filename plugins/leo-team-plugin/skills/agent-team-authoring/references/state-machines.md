# 双层状态机

> 两层：mission（任务整体）与 work unit（最小可验证单元）。
> 两层都必须由**脚本**判定，不得由 LLM 自行判断"现在到哪一步了"。

## 1. Mission 层

```text
planning → gate → executing → reviewing → verified
```

| 状态 | 含义 | 退出条件 |
|---|---|---|
| `planning` | 需求、分级、切分、角色卡 | 计划与验收标准落盘 |
| `gate` | 等待用户确认（essence.md I-3 硬门禁） | 用户明确给出 `confirmed`；只能由 lead 对用户发起 |
| `executing` | work unit 并行执行 | 所有单元到达 `merged` 或明确 `blocked` |
| `reviewing` | 集成评审 + 验收 | 验收标准逐条有证据 |
| `verified` | 完成 | 终态 |

不允许的转移：

- `planning → executing`（跳过 gate）
- `gate → verified`（无执行）
- `reviewing → executing` 只能经由 work unit 的 `changes_requested` 触发，不得整体回退重做

## 2. Work unit 层

```text
pending → in_progress → for_review → approved → merged → verified
                              ↑            │
                              └────────────┘  changes_requested
```

| 状态 | 判定标准 | 谁可以置位 |
|---|---|---|
| `pending` | 已声明 lane、输入路径存在、无写冲突 | lead |
| `in_progress` | 有 liveness 回执（见 team-invariants T-3） | 执行者 |
| `for_review` | 产物落盘 + 回传含 verdict | 执行者 |
| `approved` | reviewer 给出 PASS，findings 无 blocker | reviewer |
| `merged` | 产物已进入集成分支，且构建/全量测试通过 | lead 或集成脚本 |
| `verified` | 验收标准逐条有证据，且由**非作者**执行 | verifier |
| `changes_requested` | reviewer 给出 FAIL，findings 至少一条 severity ≥ major | reviewer |

## 3. approved ≠ merged ≠ verified

这三者被混同是团队流程里最贵的错误：它让"评审过了"看起来像"做完了"。

| 状态 | 证据要求 | 产物在哪里 | 谁能推翻 |
|---|---|---|---|
| **approved** | reviewer 的 PASS + 零 blocker findings | 仍在作者分支/工作区 | reviewer 自己（发现新证据） |
| **merged** | 集成分支包含该变更 + 构建与全量测试通过 | 集成分支 | 集成测试失败 |
| **verified** | 每条验收标准映射到命令 + 输出 + `file:line`，由非作者执行 | 集成分支 | 验收标准变更 |

三个独立门槛：

- approved 只说明"方案与实现对评审者成立"，不说明能合并。
- merged 只说明"技术上合进去了"，不说明满足用户需求。
- verified 只说明"验收标准被满足"，不说明长期质量。

**任何把三者合并成一个 `done` 的状态设计，都会在某一处静默丢证据。**

## 4. 转移表

### Mission

| 当前 | 允许下一步 | 前置条件 |
|---|---|---|
| `planning` | `gate` | `plan.md` 与验收标准存在 |
| `planning` | `planning` | 切分不合法（lane 相交等），重做 |
| `gate` | `executing` | 用户 `confirmed` 已落盘，且记录问询者=lead |
| `gate` | `planning` | 用户拒绝或要求修改 |
| `executing` | `reviewing` | 所有 unit ∈ {merged, blocked} |
| `executing` | `executing` | 有 unit 处于 for_review/changes_requested |
| `reviewing` | `verified` | 验收标准全部有证据 |
| `reviewing` | `executing` | 存在 `changes_requested` 的 unit |
| `verified` | — | 终态 |

### Work unit

| 当前 | 允许下一步 | 前置条件 |
|---|---|---|
| `pending` | `in_progress` | liveness 回执；lane 无冲突 |
| `in_progress` | `for_review` | 产物路径存在且非空；回传含 verdict |
| `in_progress` | `pending` | 第 3 次失败 / blocked（不得第 4 次自动重试） |
| `for_review` | `approved` | verdict=PASS 且 findings 无 blocker |
| `for_review` | `changes_requested` | verdict=FAIL 或存在 blocker |
| `changes_requested` | `in_progress` | 有对应的 finding 被指派给执行者 |
| `approved` | `merged` | 集成分支构建 + 全量测试通过 |
| `merged` | `verified` | 非作者执行验收，证据完整 |
| `merged` | `changes_requested` | 验收发现不满足标准 |
| `verified` | — | 终态 |

非法示例（必须被脚本拒绝）：`pending → approved`、`in_progress → merged`、`approved → verified`。

## 5. 为什么用脚本而不是 LLM

| 风险 | LLM 的行为 | 脚本的行为 |
|---|---|---|
| 状态判断 | 会依据"感觉快完成了"提前推进 | 只认前置条件 |
| 跳步 | 会为跳步编造合理理由 | 无此能力 |
| 同一输入 | 不同轮次可能给出不同判断 | 确定性 |
| 审计 | 事后无法证明判定过程 | 可重放 |
| 并发 | 两个 agent 可能同时认为自己是当前推进者 | 文件锁 / 单写者 |

LLM 可以**建议**下一步（`next_action`），但**置位**只能由脚本做。这条边界划清之后，状态机才有可能被信任。

## 6. 与回传契约的连接

每次回传的 `verdict` 直接驱动转移：

```text
verdict=PASS    → for_review → approved（还需 findings 检查）
verdict=FAIL    → for_review → changes_requested
verdict=BLOCKED → in_progress → pending（并记录 stop_reason）
```

因此：**没有 verdict 的回传不允许进入任何转移**。这是 L3 层约束（enforcement-ladder.md），不是建议。

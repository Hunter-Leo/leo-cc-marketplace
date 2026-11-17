# N5 Round Review — 轮次评审与闭环

> 目标：用独立上下文判定本轮是否可进入 N6；不可则在同一 session 内开 Round N+1。
> 前置：`flow.json.mission=reviewing`；无 claim；所有实现单元为 `for_review`/`approved`/`merged`/`verified`。

## 1. 输入（缺任一即 BLOCKED）

| 输入 | 来源 | 用途 |
|---|---|---|
| `generated/findings.md` | 各角色自己段落 + PM 汇总段 | 未决 finding、severity、接受债务记录 |
| `generated/science-audit.md` | science-auditor（`auditor=true` 时必需） | 事实断言裁决 |
| `flow.json` | `flow.sh status` | mission、round、单元状态、failures |
| `git diff <base>..<HEAD>` | 分支 | 固定评审点 |

reviewer 在 `findings.md` 中写 `## Round N — spec-reviewer — <unit-id>`，同一段内分两节：`### Axis 1 — 标准/OOP` 与 `### Axis 2 — spec/验收`。两节独立取证，禁止合并裁决或重排 severity。

## 2. 判定表（PM 机械汇总，不得自行降级）

先统计：`B = blocker 数`、`C = critical 数`、`M = 未被用户接受的 major 数`、`A = science-audit 判定`。

| B | C | M | A | 判定 |
|---|---|---|---|---|
| >0 | 任意 | 任意 | 任意 | 开 Round N+1；不得进入 N6 |
| 0 | >0 | 任意 | 任意 | 开 Round N+1；不得进入 N6 |
| 0 | 0 | >0 | 任意 | 开 Round N+1；用户可将 major 接受为债务后放行 |
| 0 | 0 | 0 | FAIL | 开 Round N+1；事实结论错误必须修复 |
| 0 | 0 | 0 | UNVERIFIABLE（已说明） | 用户裁决；不得进入 N6 |
| 0 | 0 | 0 | UNVERIFIABLE（未说明） | 视为 FAIL，开 Round N+1 |
| 0 | 0 | 0 | PASS 或 auditor=false | 进入 N6 |

仅有 minor/nit → 进入 N6，同时把未修项写入 `findings.md § Backlog`（不阻塞）。

severity 由 reviewer / science-auditor 指派。PM 只能汇总；降级必须由用户 `confirmed` 并写入 `decisions.md`。

## 3. 开 Round N+1（同 session）

### 增量原则

1. **不重写 `plan.md`**。范围变化才回 N1/N2。
2. `tasks.md` 只追加 `## Round N+1 增量`，新任务 ID 用 `R<N>-U<k>`，每条写 `supersedes: <finding ID>`。
3. mission 保持 `reviewing`；不要尝试 `reviewing → executing`。
4. 执行 `flow.sh set --round <N+1>`，随后 `flow.sh checkpoint --note "open round N+1"`。
5. 受影响的 `approved`/`merged`/`verified` 单元：`flow.sh reopen --unit <U-ID> --reason "<finding-id>"`，单元回到 `pending`；再按正常流程 `pending → in_progress`。
6. 受影响的 `for_review` 单元：`flow.sh transition --unit <U-ID> --to changes_requested`。
7. 新建单元（原单元 `failures >= 3` 或需拆分）：`flow.sh add-unit --id <new-id> --owner <role> --files "<globs>"`，同步写入 `team-plan.md`，新 ID 不复用。禁止用 `reopen` 把 `failures >= 3` 的单元洗回 `pending` 绕过用户裁决——脚本会直接拒绝；用户明确裁决继续后，才可 `flow.sh reopen --unit <U-ID> --reason "<用户裁决原文>" --force true`，并在 `decisions.md` 记录。
8. 旧轮 findings 段落不可改写；新轮追加新段落。`decisions.md` 追加 `D-xxx: round_opened`。

### 重新下发

- teammate 仍存活 → 用 SendMessage 下发新单元块，保留其上下文。
- teammate 已失联 → 按第 4 节恢复，重新 spawn 并注入 primer。
- 修复单元的 `Source guidance` 必须包含对应 finding 的 `file:line` 与证据路径。
- 修复后必须重跑该单元 `acceptance` + 受影响的回归测试，不能只跑新增测试。
- **修复单元复审 PASS 后，PM 必须把对应 finding 的 Status 改成 `fixed`（或 `accepted`）并附证据。** 只改代码不改状态，`check-team-complete.sh` 会持续把该 finding 判为未关闭并阻塞——这一步在演练中实测踩到过。
- `changes_requested → in_progress` 被拒绝（`failures >= 3`）→ 拆新单元或用户裁决；禁止重置 `failures` 绕过。

### 轮次上限

| 条件 | 动作 |
|---|---|
| round ≥ 3 且 `B + C` 相比上一轮未下降 | 停止自动循环；用户裁决（继续 / 缩范围 / 回单人 / 终止） |
| 同一 finding 连续 2 轮出现 | 判定根因未定位；停止并上报，不得再开一轮 |
| 一轮内无新增有效 finding 且仅有 nit | 判定 gold-plating；强制收尾进入 N6 |

轮次升级必须带证据：每轮 `B/C/M` 计数、finding ID 变化、失败命令输出路径。

## 4. 跨 session 中断：降级恢复

触发条件（任一）：session 结束/重启；teammate 无存活信号；`flow.json.claim` 非空但无对应活跃 agent。

### 硬规则

**不得假设 teammate 还活着。** 不得向不存在的会话发消息后继续等；不得把上一 session 的 `PASS` 直接当作本轮证据。

### 恢复顺序（固定）

| 步骤 | 动作 | 判定 |
|---|---|---|
| 1 | 读 `generated/dead-ends.md` | 已失败方案不得原样重试；每条 `DE-xx` 视为禁止路径；不存在则记录后继续 |
| 2 | 读 `generated/handoff.md` + `flow.sh status` + `findings.md` | 确认 round、分支、claim、未决 finding、下一动作 |
| 3 | `git status --short --branch`；HEAD 与 handoff 记录对比 | 不一致 → 停止并说明差异 |
| 4 | 重跑基线：完整测试命令 + `flow.sh status` | 任一失败先修环境，不得开始改代码 |
| 5 | 释放 stale claim：`flow.sh recover` | 无 claim → 输出「无变化」；`mission=blocked` 时恢复到 `planning`/`executing`，仍需用户裁决记录 |
| 6 | 更新 `handoff.md` | 固定字段见 `templates/handoff.md`；缺字段视为无效 |
| 7 | 按需重新 spawn | 每次只 spawn 一个角色；primer 必须重新注入；新会话不继承旧上下文 |
| 8 | 继续 `in_progress` 单元 | 由同一 owner 续做；不得假设上次进度 |
| 9 | 校正矛盾状态 | 单元 `lane` 与证据不符 → `flow.sh reopen --unit <U-ID> --reason "missing evidence"`，并在 `decisions.md` 记录 |

### handoff.md 必含

`resumption_prompt`、状态快照（round/branch/HEAD/uncommitted/last passing test）、待处理（open issues / next_action / do_not_redo / blocked_on）、过期策略。模板见 `templates/handoff.md`。

### degrade 到 subagent 或单人

按 `references/degradation.md` 选择 B/C：

1. 写 `decisions.md`：`trigger: degrade_mode`，附原因、已完成的验证证据、用户确认。
2. 保留 `.team/<run>/flow.json`、`findings.md`、`dead-ends.md`、`handoff.md`，不得删除审计链。
3. subagent 模式：回传落 `.team/<run>/verdicts/<unit>.json`，N3 取消只读重叠，全部串行。
4. 单人模式：从当前分支与 `handoff.md` 继续；已 `verified` 的部分不重做，未验证部分按单人流程重跑。

## 完成标志

- 判定表落到唯一结论，并写入 `findings.md § Round <N> 结论`（PM 段）。
- 进入 N6：无未决阻塞项；auditor 开启时 `science-audit.md` 无 FAIL / 未说明 UNVERIFIABLE。
- 开 N+1：`flow.json.round` 已递增，受影响单元已 `reopen` 为 `pending` 或转 `changes_requested`，或已新增单元；checkpoint 已写。
- 跨 session 恢复：`handoff.md` 固定字段齐全，基线命令通过，stale claim 已释放。

# AITL 可观测性设计

> 版本：v0.1  
> 日期：2026-11-24  
> 范围：`plugins/aitl-plugin` 的 run 状态、阶段迁移、人工卡点、Agent 运行时感知  
> 目标：让“人、Agent、审计者”三类观察者都能以低成本回答：**现在在哪、为什么在这、下一步是什么、谁能做什么。**

---

## 1. 问题定义

当前 AITL 已经具备：

- `run.json` 状态机
- `events.jsonl` 追加式事件
- `graph.json` 派生读模型
- `aitl_graph.py position/show/next`
- `aitl_card.py` 人工卡点
- hooks 的 allow/deny/ask

但实际使用中暴露出四个可观测性缺口：

1. **状态是 pull 模式**  
   Agent 不主动调用 `status`/`position`，就不知道当前 state、layer、progress、next。

2. **`status` 与 `position` 不一致**  
   `status` 没有 `layer`/`next`；`position` 没有 WO 明细；`status` 还不支持 `--run`。

3. **`.aitl/active` 会指向已结束的 run**  
   当前仓库的 `.aitl/active` 指向已 `abandoned` 的 `phase2-verify`，`status` 默认显示一个已放弃的 run，容易让 Agent 误判。

4. **`next` 太抽象**  
   执行中返回 `action: wait`，但没有“等谁、等什么、检查什么命令、现在允许做什么”。

结果：

```text
流程结构：清晰
状态记录：完整
卡点体验：清晰
执行中可观测：不足
Agent 运行时感知：不足
```

---

## 2. 设计目标与非目标

### 目标

- **人**：在 H1/H2/H3 之外，也能用一条命令或一张进度卡看到当前阶段。
- **Agent**：每个回合都能拿到一行“当前状态 + 下一步”，不需要记忆或推断。
- **审计者**：能从事件时间线还原“谁在什么时候、把什么从什么状态改到什么状态”。
- **低开销**：状态行不超过 1 行 / 120 字符；不引入 daemon、数据库、dashboard。
- **fail-closed**：状态读取失败不能伪造“正常”；状态缺失要显式说明。

### 非目标

- 不做实时 Web dashboard。
- 不做多 run 并发调度（MVP 仍是单 active run）。
- 不让状态行替代 gate；状态只是观察，不是授权。
- 不把完整 graph 注入每个回合（token 成本过高）。

---

## 3. 三类观察者与三种模式

```text
┌──────────────┬──────────────────────────────┬─────────────────────────────┐
│ 观察者       │ 主要问题                     │ 主要接口                    │
├──────────────┼──────────────────────────────┼─────────────────────────────┤
│ 人           │ 现在到哪了？需要我做什么？   │ 卡片 / 进度卡 / /aitl status│
│ Agent        │ 我现在能做什么？下一步是什么？│ 一行状态 + status --json    │
│ 审计者       │ 发生过什么？为什么？         │ events.jsonl / timeline     │
└──────────────┴──────────────────────────────┴─────────────────────────────┘
```

对应三种模式：

```text
push    状态变化时，主动把一行状态推给 Agent
pull    人或 Agent 主动查 status / position / next
post-hoc 事后查 events.jsonl / timeline / graph
```

当前只有 pull + post-hoc，缺 push。

---

## 4. 统一状态对象

所有观察接口共享同一个规范对象 `AitlStatus`，避免 `status`/`position`/`next` 三套格式。

```json
{
  "schema_version": "aitl.status.v1",
  "run": "001-auth",
  "state": "executing",
  "stage": "执行阶段",
  "layer": "L2",
  "progress": {
    "verified": 3,
    "total": 5,
    "current_wo": "WO-003"
  },
  "claim": {
    "wo": "WO-003",
    "by": "exec-1",
    "context_id": "exec-1-ctx",
    "age_seconds": 42
  },
  "trigger": {
    "type": "escalation",
    "id": "ESC-001",
    "blocking": true
  },
  "next": {
    "action": "wait",
    "wo": "WO-003",
    "reason": "claim active; waiting for verifier verdict",
    "check": "aitl_graph.py attempts --wo WO-003",
    "allowed": ["read", "status", "position", "attempts"],
    "forbidden": ["write", "accept", "approve", "mint"]
  },
  "open_escalations": [
    {"id": "ESC-001", "type": "irreversible", "wo": "WO-003", "blocking": true}
  ],
  "active": {
    "valid": true,
    "reason": null
  },
  "updated_at": "2026-11-24T15:40:00Z"
}
```

### 4.1 字段规则

| 字段 | 规则 |
|---|---|
| `state` | 只来自 `run.json`，不由模型推断 |
| `stage` | `state` 的展示映射；不由模型自由生成 |
| `layer` | `planning→L3`，`executing+claim→L1`，`executing→L2`，`reviewing→L3`，终态→`—` |
| `progress` | `verified/total`，`current_wo` 为当前 claim 或下一个 dispatch |
| `claim` | 无 claim 时为 `null` |
| `trigger` | 当前 blocking escalation；无则为 `null` |
| `next` | 由状态机 + claim + escalation 计算，不由模型生成 |
| `allowed/forbidden` | 粗粒度动作集，来源于状态机，不是命令白名单 |
| `active.valid` | active 指针是否指向一个非终态 run |
| `updated_at` | 由脚本写入，不由模型写 |

### 4.2 `next.action` 取值

```text
start     没有 active run，需要 H1
approve   有 blocking escalation，需要 H2
accept    reviewing，需要 H3
dispatch  有 pending WO，可以派 executor
wait      有 claim，等待 executor/verifier
none      终态，无动作
```

`wait` 必须带 `reason` + `check`，否则 Agent 会真的停住。

### 4.3 `allowed/forbidden` 矩阵

| state | allowed | forbidden |
|---|---|---|
| planning | read, status, intent write, sign | code write, claim, accept |
| executing + claim | owned write, test, status, position | accept, approve, mint, other write |
| executing no claim | read, status, dispatch, add-wo | code write, accept, approve |
| reviewing | read, status, accept card, findings ack | code write, new WO, approve |
| accepted/abandoned | read, status, timeline | all mutations |

注意：`allowed` 是**观察层提示**，真正强制仍在 `aitl_capability.py` / `aitl_gate.py`。状态行不能替代 capability 检查。

---

## 5. Push：一行状态注入

### 5.1 格式

```text
AITL {run} | {state} {stage} | {layer} | {verified}/{total} | claim={wo|–} | next={action}:{wo} | esc={n}
```

示例：

```text
AITL 001-auth | executing 执行 | L2 | 3/5 | claim=WO-003 | next=wait:WO-003 | esc=0
```

空闲：

```text
AITL idle | 上次 001-auth accepted | 无活跃 run
```

终态但不清理 active：

```text
AITL 001-auth | accepted 已接受 | — | 5/5 | next=none | active 指针已过期
```

### 5.2 注入点

新增 `UserPromptSubmit` hook：

```json
{
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/aitl_hook.py\" --status-line",
          "timeout": 10
        }
      ]
    }
  ]
}
```

`aitl_hook.py --status-line`：

1. 读 `.aitl/active`。
2. 无 active → 不输出（避免每回合噪声）。
3. 有 active → 构建 `AitlStatus`。
4. 与 `.aitl/status.last` 比较指纹：
   - `run|state|claim.wo|progress.verified|open_escalations|next.action`
5. 指纹变化 → 输出；未变化 → 最多每 3 个回合输出一次。
6. 输出 `hookSpecificOutput.additionalContext`；若宿主不支持，回退 `systemMessage`。
7. 不输出完整 graph，只输出一行。

### 5.3 防噪声

- 同一指纹最多每 3 个回合注入一次。
- 状态变化立即注入。
- 终态 run 只注入一次“已结束”，之后不重复。
- 空闲不注入，除非上一条是活跃状态（提示“已结束”）。

### 5.4 Agent 使用规则

写进 `SKILL.md`：

```text
1. 如果你看到 AITL 状态行，把它当作当前状态的唯一事实源。
2. 如果状态行缺失或与脚本输出冲突，运行 `aitl_state.py status --json`。
3. 不要根据对话记忆推断 state/layer/next。
4. next.action 不是建议，是当前状态机允许的下一步。
```

---

## 6. Pull：统一查询接口

### 6.1 `status` 成为规范入口

```bash
aitl_state.py status [--run <run>] [--json]
```

- 默认读 `.aitl/active`。
- `--run` 显式指定。
- `--json` 输出 `AitlStatus`。
- 人类可读格式包含：run/state/stage/layer/progress/claim/next/open esc。

示例：

```text
run       : 001-auth
state     : executing
stage     : 执行阶段
layer     : L2
progress  : 3/5 verified
claim     : WO-003 by exec-1 (42s)
trigger   : ESC-001 (blocking)
next      : wait WO-003 — waiting for verifier verdict
check     : aitl_graph.py attempts --wo WO-003
open esc  : ESC-001
active    : valid
```

### 6.2 `position` 保留为人类别名

`aitl_graph.py position` 继续存在，但内部复用 `AitlStatus`，输出与 `status` 一致。避免两套语义。

### 6.3 `next` 结构化

```bash
aitl_graph.py next [--run <run>] [--json]
```

输出：

```json
{
  "action": "wait",
  "wo": "WO-003",
  "reason": "claim active; waiting for verifier verdict",
  "check": "aitl_graph.py attempts --wo WO-003",
  "allowed": ["read", "status", "position", "attempts"],
  "forbidden": ["write", "accept", "approve", "mint"]
}
```

`wait` 不再是死胡同；Agent 知道该检查什么。

---

## 7. Active 指针生命周期

### 7.1 现状

`.aitl/active` 是纯文本 run id。`abandon`/`accept` 后没有清理，导致：

```text
$ aitl_state.py status
run      : phase2-verify
state    : abandoned
```

Agent 会误以为还有活跃 run。

### 7.2 设计

`.aitl/active` 改为 JSON：

```json
{
  "run": "001-auth",
  "state": "executing",
  "updated_at": "2026-11-24T15:40:00Z"
}
```

兼容旧格式：读到纯文本时按 `{run, state: unknown}` 处理。

规则：

1. `init` 写入 active。
2. `transition` 更新 active 的 state。
3. `accept` / `abandon` 如果 active 指向本 run，**清空 active**。
4. `status` 读到 active 指向终态 run → `active.valid=false`，并显示“上次 run 已结束”。
5. `init` 时若已有非终态 active → 拒绝，除非 `--takeover`。
6. hook 读到 active 指向终态 run → 视为无 active（allow），不阻塞。

### 7.3 终态显示

```text
AITL idle | 上次 001-auth accepted | 无活跃 run
```

而不是：

```text
AITL 001-auth | accepted ...
```

后者会让人误以为还有事要做。

---

## 8. 人的进度卡

### 8.1 触发时机

- `/aitl status`
- 阶段迁移（planning→executing、executing→reviewing）
- 用户问“到哪了”
- 不默认每回合弹

### 8.2 样式

```text
┌─ 执行中 ─────────────────────────────────────┐
│ run      001-auth        L2 执行              │
│ 进度     3/5 verified                         │
│ 当前     WO-003          claim=exec-1 (42s)   │
│ 下一步   等待 verifier verdict                │
│ 需要你   否                                   │
│ 最近     GATE-WO-002 verified  10:42          │
└───────────────────────────────────────────────┘
```

需要人时：

```text
┌─ 需要你决定 ─────────────────────────────────┐
│ run      001-auth        L3 意图              │
│ 触发     ESC-001  irreversible                │
│ 问题     force push 到 main                   │
│ 选项     1 批准  2 拒绝  3 详情  4 改方案     │
│ 卡片     CARD-xxxxxxxx  xxxxxxxx              │
└───────────────────────────────────────────────┘
```

### 8.3 不做什么

- 不在每次工具调用后弹卡。
- 不把完整 diff 放进进度卡。
- 不让进度卡替代 H2/H3 的决策卡。

---

## 9. 审计时间线

### 9.1 事件是唯一事实源

`events.jsonl` 保持 append-only；`graph.json` 是派生读模型。

### 9.2 `timeline` 命令

```bash
aitl_graph.py timeline [--run <run>] [--last 20]
```

输出：

```text
10:41:02  run_initialized      pm     001-auth      —→planning
10:41:20  intent_signed        human  001-auth      planning→executing
10:41:25  wo_created           pm     WO-001        —→pending
10:41:30  wo_claimed           exec-1 WO-001        pending→in_progress
10:42:10  gate_passed          verifier WO-001      for_review→verified
10:42:12  run_transition       pm     001-auth      executing→reviewing
10:43:00  outcome_accepted     human  001-auth      reviewing→accepted
```

### 9.3 事件字段

现有事件已有 `ts`/`event`/`actor`/`meta`。新增可选字段：

```json
{
  "seq": 12,
  "ts": "...",
  "run": "001-auth",
  "event": "run_transition",
  "actor": {"kind": "pm", "id": "pm-1", "session_id": "..."},
  "subject": {"type": "run", "id": "001-auth"},
  "from": "executing",
  "to": "reviewing",
  "reason": "all work orders verified",
  "meta": {}
}
```

旧事件没有 `seq`/`from`/`to` 时，timeline 用 `event` 推断或显示 `—`。

---

## 10. Agent 侧结构清晰化

### 10.1 在 `SKILL.md` 加一张状态表

```text
state       layer   allowed                         next
planning    L3      read, intent write, sign         H1 → executing
executing   L2/L1   owned write, test, status        G0 → verifier → G3
reviewing   L3      read, accept card, findings ack   H3 → accepted
accepted    —       read                             none
abandoned   —       read                             none
```

### 10.2 把“下一步”变成命令

`next.check` 给出可直接执行的命令：

```text
next=wait:WO-003
check=aitl_graph.py attempts --wo WO-003
```

Agent 不需要猜“wait 是什么意思”。

### 10.3 每次工具拒绝都带状态

`aitl_hook.py` 的 deny/ask reason 统一前缀：

```text
AITL 001-auth | executing | L2 | 3/5 | next=wait:WO-003
denied: path not in owned_files
```

这样即使 Agent 没看到状态行，也能从拒绝信息中恢复上下文。

---

## 11. 失败模式

| 失败 | 表现 | 处理 |
|---|---|---|
| active 指向终态 | `status` 显示已结束 run | `active.valid=false`，提示 idle |
| active 缺失 | 无状态行 | `status` 显示 idle；`start` 可创建 |
| `graph.json` 过期 | 进度落后 | `status` 从 events 重建；mtime/seq 校验 |
| 事件追加失败 | 状态迁移失败 | 迁移失败，不静默继续 |
| 多 active run | 两个 run 同时执行 | MVP 拒绝；`--takeover` 显式接管 |
| hook 输出不支持 | 状态行不出现 | 回退 `systemMessage`；Agent 主动 `status` |
| 状态行过长 | token 开销 | 截断到 120 字符；只保留 run/state/layer/progress/next |

---

## 12. 指标

用于验证可观测性本身是否有效：

```text
status_line_injected_total        注入次数
status_line_deduped_total         去重次数
status_query_total                主动查询次数
stale_active_incidents            active 指向终态的次数
time_in_state_seconds             每个 state 的停留时间
transition_count                  状态迁移次数
human_decision_latency_seconds    H2/H3 决策延迟
next_wait_age_seconds             wait 状态持续时长
```

MVP 只记录事件，不做 dashboard。

---

## 13. 验收用例

1. `status --run <run>` 可用，输出包含 `state/stage/layer/progress/next`。
2. `abandon` 后 `.aitl/active` 被清空；`status` 显示 idle。
3. `accept` 后 `.aitl/active` 被清空；`status` 显示 idle。
4. active 指向终态 run 时，`status` 显示 `active.valid=false`，hook 视为无 active。
5. `position --json` 与 `status --json` 字段一致。
6. `next` 在 executing+claim 时返回 `wait`，并带 `reason/check/allowed/forbidden`。
7. `UserPromptSubmit` 在状态变化时注入一行；无变化时最多每 3 回合注入一次。
8. 空闲时不注入；终态只提示一次。
9. `timeline --last 10` 能按时间顺序显示迁移。
10. hook deny reason 包含当前状态行。
11. 状态行 ≤120 字符；不包含 diff/完整 graph。
12. 所有状态输出来自脚本，不由模型生成。

---

## 14. 分阶段落地

### P0：一致性（0.5–1 天）

- `status --run`
- `status --json` 输出 `AitlStatus`
- `position` 复用同一对象
- active 指针生命周期（accept/abandon 清理；终态检测）
- `next` 增加 `reason/check/allowed/forbidden`

### P1：Push（1–2 天）

- `UserPromptSubmit` hook `--status-line`
- 指纹去重
- 回退 `systemMessage`
- deny/ask reason 带状态行

### P2：人的视图与审计（1–2 天）

- `aitl_card.py status` 进度卡
- `aitl_graph.py timeline`
- 指标事件
- `SKILL.md` 状态表

### P3：可选

- `/aitl status --watch`
- 多 run 视图
- 跨 repo 聚合

---

## 15. 开放问题

1. Claude Code `UserPromptSubmit` 的 `additionalContext` 字段是否在所有版本可用？不可用时 `systemMessage` 的回退行为是否一致？
2. 状态行注入是否会计入上下文 token 成本？需要实测 1 行/回合的开销。
3. 多 active run 是否真的不需要？如果未来需要，active 要从单值改成列表。
4. `allowed/forbidden` 应该按动作还是按命令？动作更稳定，命令更可执行；建议先动作，`next.check` 给命令。
5. 进度卡是否需要显示历史 attempt 数？建议只显示最近一次 gate，避免信息过载。
6. 状态行与卡片冲突时，谁优先？答案是脚本状态；卡片是状态的渲染，不是第二事实源。

---

## 16. 结论

```text
AITL 现在有“可审计的状态机”，但还不是“可感知的协作流程”。

补齐顺序：
  先修 active/status 一致性
  再推一行状态给 Agent
  再给人进度卡
  最后做时间线与指标

不要做的事：
  不要每回合注入完整 graph
  不要让状态行替代 gate
  不要让模型生成 state/layer/next
```

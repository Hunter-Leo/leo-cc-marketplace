# Agent Harness 三层 Loop 设计文档

**状态**：Draft v0.1
**日期**：2026-11-18
**范围**：新插件（不影响现有 `leo-team-plugin`）
**依据**：`docs/hitl-to-aitl-research-2026-11.html`、`docs/harness-vibe-coding-research-2026-11.html`

---

## 0. 北极星

```text
Agent runs the loop.
Human designs the loop.
System decides when the loop is done.
Irreversible actions never leave the loop.
```

一句话方向：

> **不是让 agent 更自由，而是让验证更自动、让人更靠外。**
> 自主权只在验证能力覆盖到的地方扩张；不可逆动作永远不扩张。

---

## 1. 现有插件的定位（浓缩）

| 层面 | 现状 | 对应范式 |
|---|---|---|
| 决策权 | 人在 N2/N3 确认 | HITL |
| 执行期 | 确认后 agent 自主跑，人只在异常介入 | HOTL |
| 写入边界 | claim + lane hook 机械强制 | L3 机制 |
| 完成判定 | 人工看 AC 证据；脚本只查状态 | **L1** |
| 跨运行信任 | 无 | 无 |

**结论**：`HITL 仪式 + HOTL 执行 + L1 判定`。
结构能力约 L2.5，判定能力约 L1——两条腿不一样长。

```
验证自动化 高
      ▲
      │              ╱ 安全线
      │           ╱  ★ AITL
      │        ╱
      │     ╱  ○ HOTL
      │  ╱
      │ ● 当前（在安全线下方）
      │╱
      └──────────────────────► 执行自治度
```

**根因**：循环闭合在「人读懂 findings」，而不是「系统验证通过」。

---

## 2. 设计目标

1. **三层 loop 在结构上可见**：目录、状态、命令、日志、看板都按层标注。
2. **层间只通过契约通信**：不靠对话、不靠记忆、不靠 PM 转述。
3. **每一层有自己的完成判定**，且不能被上层或下层代判。
4. **时间上解耦，契约上耦合**：人不必等代码，代码不必等人。
5. **不可逆动作永远在自动化之外**。

---

## 3. 三层 Loop 总览

```
┌──────────────────────────────────────────────────────────────────────┐
│ L3  HUMAN LOOP                                    clock: days         │
│                                                                      │
│  问题：Why / What                                                    │
│  所有者：Human                                                       │
│  输入：结果反馈、风险偏好、预算、组织约束                            │
│  输出：Intent Contract（目标 / 非目标 / AC / 风险政策 / 预算）        │
│  判定：outcome_accepted / amend / stop                               │
│  禁止：读 diff、批准单个动作、直接改代码                              │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ Intent Contract（签署 + 快照）
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L2  HARNESS LOOP                             clock: minutes–hours     │
│                                                                      │
│  问题：How / When                                                    │
│  所有者：Harness（可由 agent 执行，但权威在系统）                     │
│  输入：Intent Contract + L1 evidence + 运行指标                       │
│  输出：Execution Contract（工作单元 / 门禁 / 升级策略 / 信任等级）    │
│  判定：gate_passed / re-plan / escalate                             │
│  禁止：写业务代码、静默修改 Intent、替人做价值判断                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ Execution Contract（逐单元）
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L1  CODE LOOP                                  clock: seconds         │
│                                                                      │
│  问题：Do / Verify                                                   │
│  所有者：Agent                                                       │
│  输入：Execution Contract + 仓库状态                                 │
│  输出：Patch + Evidence Contract（测试 / 轨迹 / 审计）                │
│  判定：verified / repair / blocked                                   │
│  禁止：改自己的门禁、宣布 done、越界写入                              │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ Evidence
                                ▼
                        回到 L2 门禁聚合
```

### 3.1 三层画布（一张表看懂）

| 维度 | L3 Human | L2 Harness | L1 Code |
|---|---|---|---|
| 核心问题 | Why / What | How / When | Do / Verify |
| 所有者 | Human | Harness | Agent |
| 核心产物 | Intent Contract | Execution Contract | Patch + Evidence |
| 完成判定 | `outcome_accepted` | `gate_passed` | `verified` |
| 时间尺度 | 天 | 分钟–小时 | 秒–分钟 |
| 预算 | 决策 SLA | 重规划轮次 | 重试次数 |
| 主要失败 | 目标错 | 拆解/门禁错 | 补丁错 |
| 指标 | 结果采纳率 | 逃逸率 / 升级率 | 一次通过率 |
| 升级对象 | — | Human | Harness |
| 禁止动作 | 读 diff | 写代码 | 改门禁 |

### 3.2 每一层都是一个控制回路

```text
L1  CODE LOOP
   sensor    = tests / lint / typecheck / runtime
   controller= agent policy（plan / repair）
   actuator  = patch
   feedback  = pass/fail + evidence

L2  HARNESS LOOP
   sensor    = evidence + metrics + escalation
   controller= gate / policy engine
   actuator  = dispatch / re-plan / promote / demote
   feedback  = unit verdicts, escape rate

L3  HUMAN LOOP
   sensor    = outcome + incidents + cost
   controller= human judgment
   actuator  = intent amendment / budget / policy
   feedback  = accept / revise / stop
```

**关键原则：每一层都为上一层做「多样性衰减」。**
L1 不把日志倒给 L2，只给 verdict + evidence；L2 不把 findings 倒给 L3，只给决策请求。
否则上层会被下层的细节淹没——这正是当前 HITL 的批准疲劳来源。

---

## 4. 层间契约

层间只允许四种契约。任何跨层通信必须落成其中一种，禁止口头/上下文传递。

### 4.1 Intent Contract（L3 → L2）

```yaml
intent:
  id: INT-001
  goal: "一句话可判成败"
  non_goals: ["..."]
  acceptance:
    - id: AC-1
      check: command | invariant | manual
      run: "npm test -- auth"
      expect: "exit_code == 0"
    - id: AC-2
      check: manual
      reason: "视觉验收，无法自动化"
  risk_policy:
    irreversible: [delete, force_push, pay, deploy, change_permission]
    always_ask_human: ["..."]
    never_do: ["..."]
  budget:
    human_rounds: 3
    wall_clock: "2d"
    tokens: 2000000
  signed_by: human
  signed_at: "2026-11-18T10:00:00Z"
  snapshot: "<sha256>"
```

### 4.2 Execution Contract（L2 → L1）

```yaml
execution:
  intent_id: INT-001
  trust_tier: T2
  units:
    - id: U-01
      maps_to: [AC-1]
      owned_files: ["src/a.ts", "tests/a.test.ts"]
      reversible: true
      blast_radius: low
      acceptance:
        - command: "npm test -- a"
          expect: "exit_code == 0"
      evidence_required: ["test_output", "diff_sha"]
  gates:
    - id: G-1
      type: deterministic
      when: unit_complete
    - id: G-2
      type: verifier
      when: unit_complete
  escalation:
    - trigger: irreversible
      to: human
    - trigger: out_of_scope
      to: human
    - trigger: spec_ambiguous
      to: human
  budgets:
    retries_per_unit: 3
    rounds_max: 3
```

### 4.3 Evidence Contract（L1 → L2）

```yaml
evidence:
  unit: U-01
  verdict: verified | blocked
  checks:
    - name: build
      command: "npm run build"
      exit_code: 0
    - name: AC-1
      command: "npm test -- a"
      exit_code: 0
  artifacts: ["tests/a.test.ts", ".team/run/verdicts/U-01.json"]
  diff_sha: "<sha256>"
  verifier:
    context_id: "verifier-7f3a"
    independent: true
  escalation: null
```

### 4.4 Escalation Request（L1 → L2，或 L2 → L3）

```yaml
escalation:
  from: L1
  to: L2
  type: irreversible | out_of_scope | spec_ambiguous
  what_i_tried: ["..."]
  evidence: ["..."]
  options:
    - { option: "A", tradeoff: "..." }
    - { option: "B", tradeoff: "..." }
  recommendation: "A"
  confidence: 0.72
  blocking: true
```

> 没有这五项，升级会退化成「人从头查一遍」——比不做还慢。

---

## 5. 控制流

### 5.1 下行

```text
Intent Contract
      │  目标 / AC / 风险政策 / 预算
      ▼
Execution Contract
      │  单元 / 门禁 / 升级策略 / 信任等级
      ▼
Code Loop
      │  plan → act → verify → repair
      ▼
Patch + Evidence
```

### 5.2 上行

```text
Evidence
      │  逐单元：verified / blocked
      ▼
L2 Gate
      │  聚合：gate_passed / re-plan / escalate
      ▼
L3 Outcome
      │  结果：outcome_accepted / amend / stop
      ▼
Intent Amendment（如有）
```

### 5.3 升级阶梯

```text
L1 无法解决
   └─ 结构化 Escalation → L2
        └─ L2 无法解决
             └─ Decision Request → L3
                  └─ L3 裁决
                       └─ Intent Amendment → 向下级联

禁止：
  L1 直接找 L3（绕过门禁）
  L2 静默改 L3（目标漂移）
  L3 直接改 L1（微管理）
```

---

## 6. 三条不变量

### I-1 层权不越界

```
L3 只写 Intent
L2 只写 Execution
L1 只写 Code + Evidence
```

任何一层都不能写另一层的权威产物。

### I-2 完成判定不可代判

```
L1 不能宣布 outcome_accepted
L2 不能宣布 outcome_accepted
L3 不能宣布 verified
```

每一层的 verdict 只能由该层产生。

### I-3 不可逆动作永不自动化

```
reversible = false
  → 无论 trust_tier 多高
  → 无论历史成功率多好
  → 必须硬门禁（人 / 策略）
```

可逆性是**动作的属性**，不是 agent 的属性。

---

## 7. 防层间泄漏（Anti-patterns）

```text
✗ 人读 diff 并逐行 review
    → L3 泄漏到 L1；人成为瓶颈

✗ Harness 在实现中悄悄改 AC
    → L2 泄漏到 L3；目标漂移

✗ Agent 自己宣布 done
    → L1 代判 L2；false completeness

✗ 所有异常都升级给人
    → L1 跳过 L2；批准疲劳

✗ 一份混合日志承载三层
    → 无法归因；无法做层内指标
```

**设计对策**：
- 每个产物带 `layer: L1|L2|L3` 字段。
- 每条日志带层标签。
- 每个命令只允许作用于本层。
- 每个 UI 视图只展示一层。

---

## 8. 三层状态机

```text
L3  INTENT
    draft ──► signed ──► active ──► amended ──► closed
                 │                      │
                 └──────────► abandoned ◄┘

L2  EXECUTION
    planned ──► gated ──► executing ──► reviewing ──► closed
                    │          │            │
                    └──────────┴────────────┴──► blocked

L1  CODE
    pending ──► in_progress ──► verified ──► merged
                    │              │
                    └──► changes_requested
                    └──► blocked
```

**注意**：现有插件有 L2 的 mission 状态机和 L1 的 unit 状态机；**没有 L3 状态机**。
Intent 被折叠进 N1 的 `init.md`，且由 PM 撰写——这是最大的结构性缺口。

---

## 9. 可观测性：三个视图，不混在一起

```text
L3 视图（人看）
  ├─ 结果采纳率
  ├─ 决策积压队列（按风险排序）
  ├─ 预算消耗
  └─ 事故 / 回滚

L2 视图（harness 看）
  ├─ 门禁通过率
  ├─ 逃逸率（gate 放行但后续出问题）
  ├─ 重规划率
  ├─ 人工升级率
  └─ 信任等级变化

L1 视图（agent / 调试看）
  ├─ 一次通过率
  ├─ 修复轮次
  ├─ 单元耗时
  └─ 失败分类
```

**规则**：上层只看聚合，不看原始日志；下层不看上层目标，只看本层契约。

---

## 10. 与现有插件的关系

### 10.1 阶段映射

| 现有阶段 | 新架构中的层 | 说明 |
|---|---|---|
| N0 Precheck | L2 | 是否值得组队 / 策略预检 |
| N1 Phase A | **L3 + L2** | 必须拆开：Intent（人签）与 Execution（harness 设计） |
| N2 Hard Gate | **L3** | 从「批准计划」升级为「签署 Intent」 |
| N3 Formation | L2 | 生成 Execution Contract |
| N4 Execution | L1 | Code Loop |
| N5 Round Review | L2 | Gate 聚合 |
| N6 Verification | **L1 + L2 + L3** | 证据（L1）→ 门禁（L2）→ 结果采纳（L3） |

### 10.2 最大改动

```text
现在：PM 写 init.md → 用户确认 → 同一份文档既是意图也是计划

目标：Human 签 Intent Contract
        └─ L2 从 Intent 派生 Execution Contract
              └─ 两者版本分离，Intent 变更需重新签署
```

### 10.3 迁移顺序

```text
Phase 1  把纸门变真门
  ├─ Intent Contract 独立成文件并签署
  ├─ N2/N3 confirmed 机械校验
  ├─ AC 机械校验
  ├─ 风险分类（reversible / blast_radius）
  └─ 结构化升级契约

Phase 2  把验证交给系统
  ├─ 独立 verifier（不同上下文）
  ├─ 连续验证（第一个单元即开始）
  ├─ system_verified ≠ human_approved
  └─ 门禁聚合自动化

Phase 3  把人的位置移到设计层
  ├─ 信任账本（跨运行）
  ├─ 策略驱动的模式选择（HITL / HOTL / AITL）
  ├─ 人工点降到 3–5
  └─ 人工注意力预算指标
```

---

## 11. 开放问题

1. **Intent 由谁写？** 纯人手写、人机共创、还是 agent 起草 + 人签？建议：agent 起草，人签，但签名必须绑定原文与快照。
2. **L2 由谁执行？** PM 式 agent，还是确定性调度器 + agent 顾问？建议：调度确定性化，策略建议可由 agent 提供。
3. **信任账本的粒度？** 按仓库、按任务类型、按 agent、按动作类别？建议：按「动作类别 × 仓库」。
4. **三层如何映射到 Claude Code 的现有原语？** skills / subagents / hooks / commands 各自归属哪层？
5. **如何避免「层」变成新的官僚负担？** 每层只保留一个核心产物和一条判定；其余全部可删。
6. **失败归因怎么做？** 需要一套「L1 失败 / L2 失败 / L3 失败」的分类学，否则指标会互相污染。

---

## 12. 一句话总结

> **现有插件把三层压成了一层：意图、编排、执行都写在同一条流程里。**
> 新设计的核心不是加功能，而是**把三层的权威、产物、判定、时钟重新分开**：
> 人签意图，harness 定策略，agent 跑代码；系统判完成，不可逆永远找人。

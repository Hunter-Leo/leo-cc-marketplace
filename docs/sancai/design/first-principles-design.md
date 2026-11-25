# Sancai Loop 第一性原理设计

> 目的：不从现有功能出发，而从“为什么需要 AITL”重推“最小内核是什么”。
> 结论先说：AITL 的内核不是多 agent、不是信任账本、不是图数据库，而是 **六个契约 + 三个平面 + 四个升级触发器**。

---

## 0. 一句话

> **AITL 不是“让 agent 多干活”，而是把人的权威从“每一步审批”收缩为“意图、不可逆、验收”三个边界；用可验证的契约替代人的在场。**

---

## 1. 问题定义

HITL 的隐含假设：

```text
人能看到每一步  +  人能判断每一步  +  人的时间不是瓶颈
```

AITL 的现实：

```text
agent 的执行速度 >> 人的审查速度
逐审批 → 橡皮图章 → 人成为瓶颈，且审批失去信息量
```

所以真正的问题不是“怎么让人少点几次”，而是：

> **Delegation without verifiable control** —— 把决策委托出去，但保留可验证的控制。

它分裂为三个子问题：

| 子问题 | 问题 | 失败表现 |
|---|---|---|
| Authority | 谁允许 agent 做这件事？范围多大？何时失效？ | agent 自我扩权、越界写、永久授权 |
| Observability | 怎么知道它做了什么、是否真的完成？ | 模型自述“已完成”、假测试、无证据 |
| Reversibility | 出错能不能撤回？撤不回怎么办？ | 不可逆动作被自动执行、无法回滚 |

---

## 2. 第一性原理

```text
P1  agent 是不可信 worker，不是可信同事。
P2  权威必须显式、有界、可撤回；不能靠提示词授予。
P3  信任按“动作类”授予，不按“模型身份”授予。
P4  验证必须独立于执行；执行者不能给自己发合格证。
P5  不可逆是硬边界；它高于信任等级。
P6  人的注意力是稀缺资源；优化“每人类分钟的决定质量”，不是“人类参与次数”。
P7  模糊时 fail closed：未知动作、未知风险、缺证据、缺批准 → 停。
P8  状态必须可观察、可重放；事件是真相，图是读模型。
P9  架构 > 提示：边界由脚本/钩子/权限强制，不由系统提示强制。
```

这九条不是口号，每一条都对应一个机制：

| 原理 | 机制 |
|---|---|
| P1 | executor 只有工具权限，没有审批权；verifier 只读 |
| P2 | Intent 合同 + capability token + TTL |
| P3 | 按动作类的能力表 + 信任等级 T0–T4 |
| P4 | 独立 verifier 上下文 + read-only + 禁止读 executor 叙述 |
| P5 | 不可逆动作强制人 gate，独立于信任等级 |
| P6 | 四触发器升级、卡片、注意力预算、批量仅 T1 |
| P7 | 未知动作默认要 token；缺证据不能 verified |
| P8 | append-only events + 派生 graph + 审计 |
| P9 | hooks / gate / capability 脚本，不靠 prompt |

---

## 3. 推导：六个契约就是内核

如果把 AITL 压到最小，它只需要六个契约。其他都是实现细节。

| 契约 | 谁写 | 回答的问题 | 产物 |
|---|---|---|---|
| **Intent** | 人签 | 要什么？验收是什么？风险预算多少？ | `intent.json` + approval |
| **Work Order** | 控制面 | 这一小步做什么？能碰哪些文件？依赖谁？ | `run.json` 的 WO |
| **Capability** | 控制面 | 这个动作允许吗？范围？有效期？ | 一次性 token |
| **Evidence** | 执行面/钩子 | 做了什么？退出码？diff 哈希？AC 映射？ | `evidence.json` |
| **Verdict** | 独立 verifier | 真的满足 AC 吗？有什么 findings？ | `verdict.json` |
| **Decision** | 人 | 批准/拒绝/接受？理由？绑定哪张卡？ | `decision` 事件 |

```text
Human
  │ ① Intent
  ▼
Control ──② WorkOrder──► Executor
  │                         │
  │ ③ Capability            │ ④ Evidence
  ▼                         ▼
Tools ◄────────────────── Gate ◄── ⑤ Verdict ── Verifier
  │                         │
  └────── events ───────────┘
                            │
                            ▼
                       ⑥ Decision (human)
```

关键点：

- **Intent 是权威的源头**；没有签过的 intent，不能进入 executing。
- **Work Order 是范围的载体**；没有 owned_files，不能写。
- **Capability 是动作的许可证**；不是“agent 有 Bash”，而是“这一条命令、这个 diff、这 600 秒”。
- **Evidence 必须由 harness 采集**；模型可以引用，不能改写。
- **Verdict 必须独立**；同上下文、同证据源、同模型的“自审”不算。
- **Decision 必须绑定卡片**；不是“ok”，而是“这张卡、这个快照、这个动作”。

---

## 4. 三个平面 + 四个环

### 4.1 三个平面

```text
┌─────────────────────────────────────────────────────────────┐
│ L3  AUTHORITY（人）                                         │
│  intent · acceptance · risk budget · irreversible approval  │
│  人只拥有这三个边界，不拥有执行细节                          │
└───────────────▲───────────────────────────┬─────────────────┘
                │ escalation card           │ signed mandate
                │（仅四触发器）              │
┌───────────────┴───────────────────────────▼─────────────────┐
│ L2  CONTROL PLANE（harness，确定性、fail-closed）            │
│                                                             │
│  admission → capability → scheduler → gate → evidence → audit│
│      │           │            │          │         │        │
│      │           │            │          │         └ events │
│      │           │            │          └ AC/tests/diff     │
│      │           │            └ WO queue / claim / budget    │
│      │           └ action + scope + expiry + token           │
│      └ intent complete? risk known? policy allowed?          │
└───────────────┬───────────────────────────▲─────────────────┘
                │ work order                │ evidence + verdict
┌───────────────▼───────────────┐   ┌───────┴─────────────────┐
│ L1  EXECUTOR                  │   │ L1  VERIFIER            │
│  plan → edit → test           │   │  read-only · 独立上下文  │
│  只能在 capability 内行动      │   │  AC 检查 · 对抗性 review │
└───────────────────────────────┘   └─────────────────────────┘
```

**核心判断**：

> HITL 把人放进 L1 执行环；AITL 把人放在 L3，把控制权交给 L2。
> L2 不是“另一个 agent”，而是确定性脚本 + 状态机 + 门禁。

### 4.2 四个环

```text
① Intent loop
   Human ──clarify/sign──► Control
   Control ──mandate──► Executor

② Execution loop
   Executor ──plan/act/test──► Code
   Code ──evidence──► Control

③ Verification loop
   Control ──evidence+AC──► Verifier
   Verifier ──verdict/findings──► Control

④ Escalation loop
   Control ──card──► Human
   Human ──decision──► Control
```

四个环的边界：

| 环 | 谁驱动 | 人类是否在场 | 失败时 |
|---|---|---|---|
| Intent | 人 | 是 | 不签，不启动 |
| Execution | agent | 否 | gate 拒绝，重做 |
| Verification | verifier | 否 | findings / blocked |
| Escalation | 控制面 | **仅四触发器** | 卡住，等待人 |

---

## 5. 人的决策边界：只保留四类判断

从第一性原理，人不需要判断“这行代码对不对”，只需要判断四类事：

```text
A. 价值/优先级歧义
   spec 没有决定 trade-off：先做 A 还是 B？性能还是可维护性？

B. 不可逆 / 高爆炸
   删除、部署、支付、权限、生产数据、外部状态。

C. 残余风险接受
   findings 里的 major/minor 要不要 defer/waive？技术债要不要背？

D. 权威扩张
   新范围、新权限、新数据访问、新依赖、跨仓库。
```

其余都交给 agent + verifier：

```text
可逆实现选择   → agent
测试/静态检查  → 确定性工具
机械验证       → verifier
计划内重构     → agent + gate
```

### 5.1 决策阶梯

```text
L0  deterministic ................ 无人（test/lint/typecheck）
L1  reversible in plan ........... agent + verifier
L2  reversible cross-cutting ..... notify / batch review（仅 T1）
L3  irreversible, low blast ...... 人批准 + 一次性 token
L4  irreversible, high blast ..... 人 + 强人证 + 冷却
L5  authority expansion .......... 新 intent + 重新签署
```

这张阶梯是 AITL 的“宪法”：**信任等级决定 L1–L3 的自动化程度，但永远不能把 L4 降到 L3，也不能把 L5 降成 L3。**

---

## 6. 控制不变量

```text
I1  没有 intent，不进入 executing。
I2  没有 capability，不执行动作。
I3  没有 harness evidence，不判定 verified。
I4  没有独立 verdict，不通过 gate。
I5  没有人的 decision，不执行不可逆动作。
I6  没有 findings disposition，不接受 outcome。
I7  没有新 intent，不扩大 scope / 权限 / 数据访问。
I8  每个 deny / block / escalate 都产生事件和人类可读卡片。
I9  graph 是读模型；它解释状态，不授权状态。
```

这九条不变量就是“防呆”的骨架。任何新功能，如果破坏其中一条，就不进入内核。

---

## 7. 状态机

```text
planning ──sign──► executing ──all WO verified──► reviewing ──accept──► accepted
   │                   │                              │
   │                   ├─ gate fail ──► executing     └─ reject ──► executing
   │                   ├─ escalate ──► blocked ──approve──► executing
   │                   └─ abandon ──► abandoned
   └─ abandon ──► abandoned
```

WO 状态：

```text
todo ──claim──► in_progress ──submit──► for_review ──gate──► verified
  ▲                  │                       │
  └──── reject ◄─────┴───────────────────────┘
```

关键点：

- `verified` 只能由 `sancai_gate.py --apply` 写，不能由 executor 直接写。
- `reviewing` 必须所有 WO verified + 每个 gate verified。
- `accepted` 必须无 open escalation、无 blocker/critical、findings 已处置。
- `abandoned` 必须有人给理由。

---

## 8. 最小内核（MVP）

### 8.1 必须在内核里

```text
Intent 合同 + 签署
Work Order + owned_files
Capability 检查（fail-closed）
Harness evidence（exit code / diff_sha / artifacts）
独立 verifier + gate
四触发器 escalation
append-only events + 派生 graph
卡片（人看的唯一界面）
```

### 8.2 明确不在内核里

| 功能 | 为什么不是内核 | 何时需要 |
|---|---|---|
| 信任账本 / 自动升降级 | 没有 eval 数据前是伪精确 | 有 30+ 任务数据后 |
| SQLite / graph DB | 数据量小，JSON 足够；图 DB 不解决语义 | >10k 节点 / 跨 run 查询 |
| 常驻 scheduler / daemon | Claude Code 插件没有宿主 | 独立服务形态时 |
| 多 agent 并行 | 单写者更安全；并行是吞吐优化 | 多 repo / 多团队 |
| Health board / 实时 dashboard | 卡片 + CLI 已够 MVP 观测 | 多人协作时 |
| A2A / 跨仓库权限 | 超出单 repo 控制面 | 平台化时 |
| 自动改 spec | 破坏“人是意图源头” | 不建议 |

**一句话**：MVP 只需要证明“人从每步审批退到四触发器后，成功率不降、人的时间显著下降”。其他都是规模化问题。

---

## 9. 当前设计的再评估

| 当前设计 | 第一性原理判断 | 处置 |
|---|---|---|
| L3/L2/L1 三平面 | 核心：权威/控制/执行分离 | 保留 |
| 六个契约 | 核心：可验证委托的最小完备集 | 保留 |
| capability token | 核心：P2/P3/P5 | 保留 |
| harness evidence | 核心：P4/P8 | 保留 |
| 独立 verifier + gate | 核心：P4 | 保留 |
| 四触发器 escalation | 核心：P6 | 保留（需明确四类） |
| HIC 卡片 | 衍生：人的观测面 | 保留，但保持薄 |
| process graph | 衍生：审计/读模型 | 保留，JSON 足够 |
| trust ledger | 衍生：需要数据 | 延后 |
| SQLite / graph DB | 过度设计（当前） | 延后 |
| health board / daemon | 过度设计（插件形态） | 延后 |
| 人类侧 v2 | **缺口**：注意力/真实性/确认/人证 | 补设计，分阶段 |

---

## 10. 失败模式 → 设计响应

| 失败模式 | 根因 | 响应 |
|---|---|---|
| 模型说“完成了” | 完成由叙述判定 | harness evidence + exit code + diff_sha |
| 假测试 / 改测试通过 | 测试与实现同源 | verifier 独立；测试文件受保护；AC 映射 |
| 越界写 | 权限=能力 | owned_files + capability + hook |
| 不可逆动作被自动执行 | 信任等级覆盖不可逆 | I5：不可逆永远人 gate |
| 人批太快 | 无注意力机制 | dwell/cooldown/budget/fatigue |
| 人看不到真实卡片 | agent 可伪造文本 | card hash/MAC/verify |
| findings 被吞 | accept 只看 blocker | findings_hash + disposition |
| 审计断链 | 状态可变、无事件 | append-only events + graph rebuild |
| 多 agent 冲突 | 并发写 | 单写者 + claim + owned_files |

---

## 11. 需要对齐的五个点

1. **人的边界是否就是四触发器？**
   还是保留“所有 T2 都问人”？前者是 AITL，后者是 HITL。

2. **不可逆由谁分类？**
   intent 声明 + policy 审核，还是 agent 自报？建议前者，agent 只能建议。

3. **verifier 独立性在单会话里够不够？**
   独立上下文 + read-only + 禁读 executor 叙述，是否足够？还是必须独立进程/独立模型？

4. **高风险人证愿意用 TTY/GPG/生物识别吗？**
   如果人不想开终端，T3 的强人证就落不了地；需要确认可接受的摩擦上限。

5. **MVP 的观测面是否接受“卡片 + CLI + graph.json”？**
   还是必须先有 dashboard/web UI？前者能快速验证，后者成本高。

---

## 12. 设计决策（已对齐）

以下五项按建议收敛，作为 v1.0 设计基线：

| # | 决策 | 结论 |
|---|---|---|
| 1 | 人的边界 | 只保留四触发器：价值/优先级歧义、不可逆/高爆炸、残余风险接受、权威扩张。其余 agent + verifier。 |
| 2 | 不可逆分类 | intent 声明 `risk_tier` + `irreversible_actions`；policy 审核；agent 只能建议，不能自定 T0/T1。未知动作 fail closed 到 T2。 |
| 3 | verifier 独立性 | MVP 采用独立上下文 + read-only + 禁读 executor 叙述 + 系统计算 independence metadata；Phase 2 增加可选独立进程/模型；policy 可要求更强。 |
| 4 | 高风险人证 | T2：明确词 + 卡片绑定 + dwell；T3：人跑 TTY `sancai_human.py`（GPG 可选，Phase 3 默认）；T4：双人 + 独立环境 + 硬件密钥。agent 不能代跑 T3。 |
| 5 | MVP 观测面 | 卡片 + CLI + `graph.json`；不做 dashboard / web UI。 |

实现映射：价值歧义 → `spec_ambiguous`；不可逆 → `irreversible`；残余风险 → `accept` findings disposition；权威扩张 → `out_of_scope` + 新 intent。

这五项是**设计基线**，不是实现细节；后续实现如果与它们冲突，以这五项为准。

---

## 13. 结论

> **AITL 的第一性原理不是“自动化”，而是“可验证的委托”。**
>
> 人保留三件事：**要什么（intent）、什么不能自动做（irreversible）、什么算完成（acceptance）**。
> 其余交给控制面：**capability 限制范围、evidence 证明事实、verifier 独立判断、gate 决定状态、事件保证可审计**。
>
> 只要这六契约 + 九不变量成立，多 agent、图数据库、信任账本、dashboard 都是可替换的实现；
> 如果它们不成立，加再多功能也只是把 HITL 包装成 AITL。

# Sancai Loop Harness 设计 v0.4（MVP-first）

**Agent-in-the-Loop 的可落地设计**

- 状态：Draft v0.4
- 日期：2026-11-19
- 依据：HITL→AITL 调研、harness 前沿调研、`leo-team-plugin` 现状、DeepSeek Super Agent（实验性）、Architect 对抗性 review（REVISE，4 P0 / 15 P1）
- v0.2 → v0.3：按 review 的「只能改三件事」收敛，删除不能落地的机制
- v0.3 → v0.4：新增人类互动卡片（HIC）与过程图（history + graph.json）；两者是记录/交互层，不改变四件事
- v0.4 补全：20.15 图在插件流程中的使用、20.16 存储选型（JSON → SQLite → 图数据库的升级路径）
- v0.4 实现：`sancai_graph.py`（固定查询）与 `sancai_card.py`（六类卡片）已落地

---

## 0. 北极星

```text
Agent runs the loop.
Human designs the loop.
System decides when work is verified.
Human decides when the outcome is accepted.
Irreversible actions only leave through a human-minted capability.
```

四条公理：

```text
A1  权威属于层，不属于角色
A2  完成由 harness 捕获的证据判定，不由执行者叙述判定
A3  不可逆动作由工具级能力模型强制；未标注工具默认拒绝
A4  没有 eval，就没有资格谈自治
```

> **边界声明**：插件本身不是沙箱。
> A3 的承诺是「在工具级能力模型覆盖范围内，未标注或标注为不可逆的调用默认拒绝」；
> 进程内任意系统调用必须由外部 OS sandbox 兜底。文档不再宣称「永不自动化」。

---

## 1. Review 的四个 P0 与 v0.3 取舍

| P0 | 问题 | v0.3 处理 |
|---|---|---|
| P0-1 | 不可逆动作只靠 best-effort Bash 字符串匹配，脚本自认 not a sandbox | 工具级能力表 + 未标注默认拒绝 + 对抗命令测试；不再宣称插件是沙箱 |
| P0-2 | Evidence 由 L1 自写、`independent` 自报 | Evidence 由 harness 从 transcript/tool result 捕获；独立性由 harness 计算 |
| P0-3 | L2 被写成常驻 Engine / 唯一写者，Claude Code 没有这个原语 | **L2 = PM agent + 确定性脚本**；MVP 不上 daemon / SQLite / 事件溯源 |
| P0-4 | 路线图没有 eval，核心主张不可证伪 | 新增 **Phase -1**：先测 HITL baseline，再写任何 harness |

### 1.1 三个最重要的改动

```text
1. 完成判定：Evidence 由 harness 捕获，删除 L1 自写。
2. L2 形态：PM agent + 确定性脚本，删除 Engine / Mandate / 信任账本 / SQLite。
3. 先 eval：Phase -1 测 baseline；不可逆动作改为工具级能力模型。
```

---

## 2. 设计原则

| # | 原则 | 含义 |
|---|---|---|
| P1 | 契约优先于对话 | 层间只通过契约通信 |
| P2 | 权威优先于角色 | 层由「能改什么」定义 |
| P3 | 证据优先于断言 | verdict 来自 harness 捕获的产物 |
| P4 | 可逆性优先于信任 | 不可逆动作只走人的能力令牌 |
| P5 | 时间解耦，契约耦合 | 人不必等代码，代码不必等人 |
| P6 | 向上衰减多样性 | 每层只交聚合结果 |
| P7 | 随模型变强而删脚手架 | 每层标注假设，定期 re-baseline |
| P8 | 先 eval，后自治 | 没有 baseline，不放开任何人工点 |

---

## 3. MVP 范围（明确不做什么）

### 3.1 做

```text
✓ 单仓库、单写者、串行
✓ 直接在当前工作树执行，不建 worktree
✓ Intent 文件 + 人签署
✓ Work Order + 授权记录
✓ harness 捕获 Evidence
✓ G0 确定性门禁 + G3 独立 verifier
✓ 三类升级 + 拉取式队列
✓ 工具级能力表 + 不可逆动作能力令牌
✓ 文件状态机 + 原子写 + events 数组
✓ abandon 命令与失败恢复
✓ Phase -1 eval
```

### 3.2 不做（MVP）

```text
✗ 常驻 daemon / Scheduler
✗ SQLite / 事件溯源
✗ 信任账本（改为离散策略状态）
✗ Health Board（改为 flow report）
✗ 影子审查队列（observe 只输出聚合）
✗ Router / Worker 并行
✗ worktree（单写者串行不需要；并行写入进入 Phase 2 后再引入）
✗ 多仓库 / 多 agent / A2A
✗ Mandate 独立对象（合并进 Intent / Work Order）
```

> 这些不是永远不做，而是**必须先有 eval 证明需要**，再引入。

---

## 4. 架构

### 4.1 L2 的明确定义（P0-3 的修复）

```text
L2 = PM agent（编排、判断、汇总）
   + 确定性脚本（拒绝非法状态、捕获证据、校验路径、校验能力令牌）
   + hooks（否决越界写入、要求 verdict、阻止提前结束）

权威不在「Engine」，而在：
  脚本能拒绝什么、hook 能拦截什么、证据由谁写。
```

没有常驻进程。每条命令：读状态 → 执行 → 写状态 → 退出。

### 4.2 总体图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ L3  HUMAN LOOP                                       clock: days      │
│   Intent：Goal / Non-goals / AC / Risk Policy / Budget               │
│   Outcome：accepted / amend / stop                                   │
│   看最小必要证据；默认摘要，diff 需显式拉取                           │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ Intent（原文 + 快照 + 授权记录）
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L2  HARNESS LOOP                              clock: minutes–hours    │
│                                                                      │
│   PM agent ── 编排 / 判断 / 汇总（不写业务代码、不做 verifier）       │
│                                                                      │
│   确定性脚本                                                         │
│   ├─ state.sh       状态机 + 原子写 + events                         │
│   ├─ check-ac.sh    逐条执行 AC，写 evidence                         │
│   ├─ collect.sh     从 transcript / tool result 捕获证据             │
│   ├─ gate.sh        G0 确定性门禁                                    │
│   ├─ verify.sh      调用独立 verifier，记录 session/prompt hash      │
│   ├─ capability.sh  工具能力表 + 能力令牌                             │
│   ├─ report.sh      状态 / 指标 / 预算                               │
│   └─ abandon.sh     放弃 run，保留审计链                             │
│                                                                      │
│   hooks：PreToolUse（路径 + 能力）/ PostToolUse（证据）              │
│          SubagentStop（verdict）/ Stop（限本会话）/ PreCompact       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ Work Order（含授权）
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ L1  CODE LOOP                                        clock: seconds   │
│   隔离 session / 目录：plan → act → verify → repair                  │
│   只写 scratch；Evidence 由 harness 捕获                             │
│   只能请求不可逆动作，不能执行它                                     │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 三层画布

| 维度 | L3 Human | L2 Harness | L1 Code |
|---|---|---|---|
| 问题 | Why / What | How / When | Do / Verify |
| 权威 | 改意图 | 改策略 | 改代码 |
| 产物 | Intent | Work Order + Evidence + Verdict | Patch + scratch |
| 判定 | `outcome_accepted` | `verified` / `gate_passed` | `verified`（单元级） |
| 时钟 | 天 | 分钟–小时 | 秒–分钟 |
| 失败 | 目标错 | 门禁/拆解错 | 补丁错 |

> **责任闭合（P1-3）**：
> `verified` = 系统确认「按当前 AC 做完了」；`outcome_accepted` = 人对「这个结果是否值得交付」负责。
> 两者分开记录，不合并成一个 done。

### 4.4 Subagent 设计（MVP）

三层是**权威层**，不是角色层。MVP 只需要两个 subagent，加上主会话 PM：

```text
Main session（PM，L2）
  ├─ spawns  sancai-executor   (L1)     写代码、产出 scratch
  └─ spawns  sancai-verifier   (L2 / G3) 只读证据、判定
```

| 角色 | 类型 | 层 | 为什么需要 | 工具 | 输入 | 输出 | 生命周期 |
|---|---|---|---|---|---|---|---|
| **PM** | 主会话 | L2 | 需要用户交互与全局状态 | 全部，但禁止写业务代码 | Intent / Work Order / Evidence | 调度、升级、状态 | 整个 run |
| **sancai-executor** | subagent | L1 | 上下文隔离 + 写隔离 | Read / Write / Edit / Bash（限 workdir） | Work Order + AC 摘要 | patch + scratch + verdict | 每个 Work Order 一个，可复用做 repair |
| **sancai-verifier** | subagent | L2 / G3 | 独立性是硬要求（P0-2） | Read / Grep / Bash（只读） | **raw evidence + AC + diff**，不含 executor 总结 | 签名 verdict + findings | 每次验证新实例，不复用 |

**保留 subagent 的三个条件**（来自调研）：

```text
1. 单循环被上下文膨胀拖垮
2. 需要并行且可丢弃的干净上下文
3. 工具选择或指令冲突

executor  → 满足 1 + 2
verifier  → 满足 1 + 3，且独立性是硬要求
```

**MVP 不起的 subagent**：

```text
✗ explorer       —— 只有 eval 显示「主循环被代码阅读拖垮」才加
✗ architect      —— 只有出现架构歧义、且单 agent 无法收敛时才加
✗ science-*      —— 不在 MVP 范围
✗ 任何嵌套 subagent —— executor / verifier 不得再 spawn
```

**硬规则**：

```text
1. PM 是主会话，不是 subagent
2. verifier 不是 L1，它是 L2 的 G3 组件
3. executor / verifier 不共享 session、不共享上下文
4. verifier 只拿 raw evidence + AC + diff，不拿 executor 的叙述
5. executor 不能写 evidence；evidence 由 harness 采集
6. 同一 Work Order 同时只有一个 executor、一个 verifier
7. 子代理返回结构化 verdict，不返回自由文本
```

---

## 5. 四个契约

| 契约 | 内容 | 谁写 |
|---|---|---|
| **Intent** | 目标 / 非目标 / AC / 风险政策 / 预算 / 授权记录 | 人签 |
| **Work Order** | 工作单元 / owned_files / 可逆性 / 门禁 / 预算 | Harness |
| **Evidence** | 检查结果 / 产物哈希 / verifier 元数据 / 哈希链 | Harness |
| **Verdict** | 通过 / 重规划 / 升级 + 理由 | Harness（L3 只做 outcome） |

### 5.1 Intent

```yaml
intent:
  id: INT-001
  version: 1
  goal: "一句话可判成败"
  non_goals: ["..."]
  acceptance:
    - { id: AC-1, check: command, run: "npm test -- auth", expect: "exit_code == 0" }
    - { id: AC-2, check: invariant, run: "rg legacyEndpoint src/", expect: "matches == 0" }
  manual_ac_ratio: 0.0
  risk_policy_ref: "policy/risk@3"
  budget: { human_rounds: 3, wall_clock: "2d", tokens: 2000000 }
  approval:
    approved_in_session: "sess-7f3a"
    approved_at: "2026-11-18T10:00:00Z"
    user_message: "confirmed"
    snapshot: "sha256:..."
    run_id: "RUN-001"
    nonce: "9f2c..."
```

**规则（P1-13）**：

```text
1. 默认禁止 manual AC
2. 例外必须：写明理由 + 人签署 + 总数 ≤ 20%
3. manual 证据必须含五要素（命令/前置/输入/实际输出/判定）
4. manual 比例进入 DoD 质量指标
```

### 5.2 Work Order

```yaml
work_order:
  id: WO-001
  intent_id: INT-001
  authorization:
    policy_version: 3
    source: "github:org/repo#123"
    matched_rules: [R-12, R-18]
    granted_by: "alice"
  owned_files: ["src/a.ts", "tests/a.test.ts"]
  reversible: true
  blast_radius:
    files: 2
    modules: 1
    shared_files: 0
    data_impact: none
  gates: [G0, G3]
  budgets: { retries: 3, rounds: 3 }
  escalation: [irreversible, out_of_scope, spec_ambiguous]
```

`blast_radius` 由 harness 从 diff + 能力表计算，**禁止 L1 自报**。

### 5.3 Evidence（harness 捕获）

```yaml
evidence:
  work_order: WO-001
  collected_by: "aitl-collector"
  collected_at: "2026-11-18T10:31:00Z"
  diff_sha: "sha256:..."
  checks:
    - { name: build, command: "npm run build", exit_code: 0, output_sha: "..." }
    - { name: AC-1, command: "npm test -- a", exit_code: 0, output_sha: "..." }
  artifacts:
    - { path: "tests/a.test.ts", sha: "..." }
  verifier:
    id: "verifier-7f3a"
    session_id: "sess-91c2"
    prompt_hash: "sha256:..."
    tools: read_only
    saw_executor_reasoning: false
    verdict: pass
  chain:
    prev: "sha256:..."
    self: "sha256:..."
```

**规则（P0-2）**：

```text
1. L1 只能写 .sancai/runs/<run>/L1-code/scratch/<wo>/
2. harness 从 PostToolUse transcript / tool result 捕获命令、exit code、输出摘要
3. harness 自己计算 diff_sha、哈希产物
4. L1 不能写 .sancai/runs/<run>/L2-harness/evidence/ 和 L2-harness/verdicts/
5. verifier 独立性由 harness 计算：session_id / prompt_hash / 只读工具面 / 未读执行者推理
6. G3 输入是「原始证据 + AC」，不是 L1 总结
7. 哈希链断链即拒
8. verifier 元评估：已知错误补丁检出率不达标 → 降级
```

### 5.4 Verdict

```yaml
verdict:
  work_order: WO-001
  layer: L2
  result: verified | re_plan | escalate
  reasons: []
  escalation: null
  signed_by: "harness"
  ts: "2026-11-18T10:32:00Z"
```

---

## 6. 权限与自治（MVP：离散状态）

### 6.1 不做数值信任账本（P1-5）

```text
MVP 只有三个离散状态：
  read-only          只读
  write-with-review  写入需 reviewer / 人
  write              写入可自动

状态由策略规则决定：
  - 新仓库 = read-only
  - 有历史成功记录 + 可逆动作 = write-with-review
  - 达到 eval 阈值后才允许 write

不硬编码 AWS 的 0–100 分数。
没有校准数据，不启用数值账本。
```

### 6.2 自治阶梯

```text
L0 Manual → L1 Suggest → L2 Approve Plan → L3 Bounded → L4 Delegated → L5 Autonomous Org
MVP 目标：L2 → L3（仅可逆、可验证的单元）
```

### 6.3 observe（MVP：只输出聚合）

```text
off      不评估
observe  评估，只输出聚合报告（如「本周 47 个动作，3 个会越界」）
auto     评估通过就执行

不逐条展示 would-have-done；只有越界/不可逆项入队。
observe 是执行开关，策略状态是门禁等级；两者 AND。
```

---

## 7. 门禁 G0–G4

```text
G0 Deterministic  build / typecheck / lint / unit / integration
G1 Semantic       contract / golden / snapshot / property（MVP 可选）
G2 Security       SAST / secret scan / dependency（MVP 可选）
G3 Verifier       harness 独立上下文：AC 映射 + 负向不变量
G4 Human          L3 的裁决接口（不是 L2 的一个门）
```

**修正（P1-2）**：

```text
G4 不属于 L2 的 Gate Engine。
G4 = 人通过 L3 接口做裁决；L2 只负责路由、展示最小证据、记录结果。
```

规则：

```text
1. G0 → G3 顺序执行；任一门失败，原样回灌输出
2. G4 只看到 G0–G3 无法决定的部分
3. 不可逆动作只走 G4；策略不能放行不可逆动作
4. G3 必须在不同 session / prompt / 只读工具面下运行
5. G0 由 harness 执行，不采信 agent“我跑过了”
```

---

## 8. 风险与可逆性（P0-1）

### 8.1 可逆性的可操作判据

```text
reversible = true 当且仅当：
  1. 只修改 owned_files 内的路径；且
  2. 可被 git revert 完整撤销；且
  3. 不产生外部副作用（邮件/付款/外部 API/权限/生产库）；且
  4. data_impact == none

否则 irreversible。
```

### 8.2 工具级能力表（fail-closed）

```yaml
tool_capabilities:
  - { name: read_file,   reversible: true,  network: false, mutates_external_state: false }
  - { name: write_file,  reversible: true,  network: false, mutates_external_state: false }
  - { name: run_command, reversible: false, network: false, mutates_external_state: true,
      allowed_commands: ["npm test", "npm run lint", "git diff"] }
  - { name: mcp__email__send,      reversible: false, network: true, mutates_external_state: true }
  - { name: mcp__github__merge_pr, reversible: false, network: true, mutates_external_state: true }
```

规则：

```text
1. 未出现在能力表中的工具 → 默认拒绝
2. MCP 工具同样纳入
3. 能力表版本化；变更需人签署
4. Bash 解析只作为补充，不作为唯一防线
```

### 8.3 能力令牌

```text
1. L1 检测到不可逆动作 → 只能发起 request
2. harness 写 pending request，展示原始操作
3. 人执行 /sancai approve <id> → 铸造一次性 token
     HMAC(secret, action + args + diff_sha + nonce + expiry)
     secret 存放在 workspace 之外
4. 特权执行器校验并消费 token
5. agent 无法铸造、无法复用
```

### 8.4 风险矩阵（四格都有机制）

```
                    可逆                          不可逆
              ┌──────────────────────────┬──────────────────────────────┐
低风险        │ 自动执行 + 事后审计       │ 人的能力令牌                  │
              ├──────────────────────────┼──────────────────────────────┤
高风险        │ 边界内 + 独立 verifier    │ 人的能力令牌 + 双人/双签      │
              │ + 抽样审查                │                              │
              ├──────────────────────────┼──────────────────────────────┤
数据/权限影响 │ 一律按不可逆处理          │ 人的能力令牌 + 双人/双签      │
高            │                          │                              │
              └──────────────────────────┴──────────────────────────────┘
```

### 8.5 对抗命令测试（发布门槛）

```text
必测：python -c / node -e / bash -c 嵌套 / $VAR / /dev/fd/
      curl -X DELETE / git push --force / terraform destroy / kubectl delete
      MCP：发邮件 / 合并 PR / 改权限
任一未拦截 → 门禁不生效，不得发布。
```

---

## 9. 升级机制

### 9.1 三类触发

```text
① 不可逆   删除 / force-push / 付款 / 发布 / 改权限
② 越界     超出 owned_files / 预算 / 权限
③ 定义缺失 AC 冲突、需求歧义、架构无先例
```

### 9.2 结构化请求

```yaml
escalation:
  from: L1
  to: L2
  type: irreversible | out_of_scope | spec_ambiguous
  thread_id: "TH-001"
  what_i_tried: []
  evidence: []
  options: [{ option: A, tradeoff: "..." }]
  recommendation: A
  confidence: 0.72
  blocking: true
```

### 9.3 拉取式队列与抗洪水（P1-14）

```text
排序：blocking × risk × age
卡片：最小必要证据 / 选项 / 推荐 / 置信度
L3 默认只看摘要与风险；diff 需显式拉取

抗洪水：
  - 每 unit 升级次数上限
  - 相同根因去重
  - 同类合并
  - 非 blocking 批量处理
  - 超限 → 暂停并报告
```

---

## 10. 运行时（P0-3 修复）

### 10.1 状态与事件

```text
MVP：flow.json + history 数组 + tmp+os.replace 原子写
不上 SQLite；不做 event sourcing 作为架构。
只做 append-only history + 派生 graph.json（见 §20）。

history 记录：
  state_transition / claim / release / evidence / verdict / escalation / decision / budget
```

### 10.2 命令

```bash
aitl intent sign --file intent.yaml
aitl work-order create --intent INT-001 --unit U-01
aitl gate run --work-order WO-001 --gate G0
aitl verify --work-order WO-001
aitl escalate --work-order WO-001 --type out_of_scope
aitl approve <escalation-id>     # 人执行，铸造能力令牌
aitl abandon <run-id> --reason
aitl status
```

### 10.3 Claude Code 原语映射

| 机制 | 原语 | 能做到 | 做不到 |
|---|---|---|---|
| 意图签署 | command | 记录原文 + 快照 + session | 无法阻止用户点确认 |
| 写边界 | PreToolUse | 拒绝越界 Write/Edit | Bash 内联脚本 best-effort |
| 能力校验 | PreToolUse + capability.sh | 未标注工具默认拒绝 | 进程内系统调用需 OS sandbox |
| 证据捕获 | PostToolUse | 记录工具、exit code、输出摘要 | 需宿主提供 transcript |
| 完成判定 | Stop / SubagentStop | 阻止结束、要求 verdict | 不能替 agent 跑完整测试 |
| 升级 | command + 队列文件 | 结构化请求 | 无推送，需人拉取 |
| 调度 | command loop | 串行 / 有限并行 | 无常驻 scheduler |
| 沙箱 | 外部 | 真隔离 | 插件不提供 |

### 10.4 失败恢复（P1-11）

```text
- claim 超时 / 心跳；超时自动释放并记录
- verifier 超时 → 标记 unavailable，回退人工
- 事件幂等键，重复事件忽略
- 崩溃后从 flow.json + events 重建
- abandon：记录原因、保留审计链、允许结束
- Stop hook 只作用于当前会话启动的 run，不因仓库里的陈旧 flow.json 阻止结束
```

---

## 11. 上下文与工具

| 项 | 规则 |
|---|---|
| 前缀 | system → tools → policy → environment → user |
| 更新 | append-only |
| 压缩 | 先 recall 后 precision |
| 工具输出 | 有界 + 截断告知 + spill-to-file |
| 大中间结果 | code execution，只回传结果 |
| 技能 | 索引进 prompt，body 按需加载 |
| 编排 | 默认单 agent + skills；subagent 三条件 |
| 删除 | 每层标注假设，模型升级后 re-baseline |

---

## 12. 安全（P1-8：宿主 vs 插件）

| 机制 | 宿主提供 | 插件可强制 |
|---|---|---|
| OS 级沙箱 | ✓ | ✗ |
| 网络默认禁 | ✓ | 部分（工具能力表） |
| 保护路径只读 | 部分 | ✓（PreToolUse） |
| 凭据隔离 | ✓ | 插件承诺不读、不写、不转发 |
| 外部内容当数据 | ✗ | 策略 + 数据区 |
| 审计防篡改 | 文件系统 | 哈希链 + 写入 git commit |

**Intent 来源隔离（P1-8）**：

```text
Intent 可由 agent 从 issue 起草，但：
  - 人签署时看到「原始来源 vs 派生意图」差异
  - 敏感字段（部署目标、权限范围、不可逆清单）必须人填
  - snapshot 同时哈希来源与 Intent
```

**威胁模型（MVP）**：

```text
攻击者：恶意 issue / 恶意依赖 / 恶意 MCP server / 被注入的 L1
资产：仓库、凭据、外部系统、人注意力
信任边界：插件 < 宿主 < OS；插件只承诺自己能拦的部分
```

---

## 13. 可观测性与成本（P1-9）

```text
L3：outcome_accepted 率 / 决策队列长度与年龄 / 人工分钟 / 事故
L2：gate 通过率 / 逃逸率 / 升级率 / 重规划率 / 预算消耗
L1：一次通过率 / 修复轮次 / 单元耗时 / 失败分类

成本：
  - 每次执行记录 token / wall-clock / 人工介入次数
  - 由 harness 汇总，不由 agent 自报
  - 超预算 → 停止并报告
```

---

## 14. Phase -1：Eval before autonomy（P0-4）

```text
任务集：20–50 个真实任务，固定仓库快照，留 holdout
覆盖：小改动 / 跨模块 / 含不可逆动作 / 含歧义 / 安全敏感

基线：
  A  当前 HITL（人逐计划 / 逐 diff）
  B  单 agent + skills
  C  AITL MVP（Intent + G0 + G3 + 三类升级 + 能力令牌）

指标：
  - task success（AC 通过率）
  - escape rate（合并后事故率）
  - human minutes / task
  - cost / successful task
  - false completeness rate

每个 Phase 出口：eval 达标才进入下一阶段。
分数同时报告 model + harness + effort。
```

### 14.1 门禁与 verifier 的有效性

```text
门禁：跑 §8.5 对抗命令集；任一未拦截 → 不发布
verifier：已知错误补丁检出率；不达标 → 降级 G3
证据：尝试让 L1 伪造 evidence.json；必须被哈希链/权限拒绝
```

---

## 15. 与现有插件的关系

```text
新插件：plugins/sancai-loop-plugin        独立版本线 0.1.x
旧插件：plugins/leo-team-plugin    保持 0.2.0，不改动
```

原则：

```text
1. 不把 AITL 塞进经典 N0–N6 流程；两者独立演进。
2. 编码规范、git 规范、进度协议复制进 sancai-loop-plugin/references/，
   不跨插件依赖（插件可能单独安装）。
3. 经典流程继续可用；AITL 用 Phase -1 eval 决定是否值得扩大。
4. 未来是否合并，由 eval 数据决定，不由架构偏好决定。
```

AITL MVP 直接从零实现，不继承 `flow.json` / `flow.sh`：

```text
.sancai/runs/<run>/
├── L3-intent/intent.json              目标 / 非目标 / AC / 风险策略
├── L3-intent/decisions/               卡片、升级、人工决策
├── L2-harness/run.json                状态机 + 原子写
├── L2-harness/{gates,evidence,verdicts,tokens}/
├── L1-code/{attempts,scratch}/
└── audit/{events.jsonl,graph.json}    事件流 + 派生读模型
```

这样旧插件零风险，新插件可以按三层模型干净落地。

---

## 16. 实施路线

```text
Phase -1 · Eval（1–2 周）
  ├─ 任务集与基线 A/B
  ├─ 指标与阈值
  ├─ holdout
  └─ 决定是否继续

Phase 1 · 契约与门禁（2 周）
  ├─ intent.yaml + 签署
  ├─ check-ac.sh + evidence
  ├─ G0
  └─ abandon

Phase 2 · 验证与能力（3 周）
  ├─ G3 独立 verifier + 元评估
  ├─ 工具能力表 + 能力令牌
  ├─ 对抗命令测试
  └─ 结构化升级

Phase 3 · 收敛（持续）
  ├─ 策略状态（read-only / write-with-review / write）
  ├─ 人工点按 eval 结果调整
  └─ re-baseline
```

---

## 17. Re-baseline（P1-12）

`REBASELINE.md` 必须写清：

```text
触发：模型版本变更 / 策略变更 / 事故复盘
必跑：Phase -1 eval 全集
每层脚手架：
  - 标注「它假设模型做不到什么」
  - 做一次删除实验
  - 删除后 eval 不退化 → 删除
通过标准：success 不降、escape 不升、human minutes 不升
回滚：保留上一版 harness profile
记录：model + harness + effort + 分数
```

无 eval 的脚手架不得进生产。

---

## 18. Review 闭合表

| 项 | 状态 |
|---|---|
| P0-1 不可逆动作无强制 | 已修：工具能力表 + fail-closed + 能力令牌 + 对抗测试 |
| P0-2 Evidence 自写 | 已修：harness 捕获 + 独立性计算 + 哈希链 |
| P0-3 L2 常驻 Engine | 已修：明确 PM agent + 确定性脚本；MVP 无 daemon/SQLite |
| P0-4 无 eval | 已修：Phase -1 + 每阶段 eval 门禁 |
| P1-1 Intent/Mandate 重叠 | 已修：Mandate 合并进 Work Order.authorization |
| P1-2 L3 diff 矛盾 / G4 归属 | 已修：最小证据 + 显式拉取；G4 = L3 接口 |
| P1-3 责任落点 | 已修：verified ≠ outcome_accepted |
| P1-4 风险矩阵空洞 | 已修：四格机制 + data_impact 维度 |
| P1-5 信任账本阈值 | 已修：MVP 改离散状态 |
| P1-6 影子队列 | 已修：observe 只输出聚合 |
| P1-7 SQLite 过重 | 已修：MVP 不上 |
| P1-8 安全不可实现 | 已修：宿主 vs 插件分栏 + 威胁模型 |
| P1-9 成本无度量 | 已修：harness 记录 token/wall-clock/人工次数 |
| P1-10 多仓库/并发 | 已标为 MVP 外；串行明确 |
| P1-11 失败恢复 | 已修：超时/幂等/abandon/Stop 作用域 |
| P1-12 re-baseline | 已修：REBASELINE.md 流程 |
| P1-13 manual AC | 已修：默认禁止 + 20% 上限 + 五要素 |
| P1-14 洪水/签名/审计 | 已修：配额/去重；改 approved_in_session + run_id/nonce；哈希链 |
| P1-15 迁移事实不符 | 已修：保留 flow.sh；删除稻草人表述 |

---

## 19. 人类互动卡片（HIC）

### 19.1 目的

每次需要人参与时，输出同一张卡片，固定回答四个问题：

```text
我在哪？ → 出了什么事？ → 为什么需要我？ → 我能选什么？
```

三条原则：

```text
1. 卡片由 harness 渲染，模型不得自由发挥。
2. 位置、进度、gate、证据数来自 flow/graph，不靠模型叙述。
3. 人不需要记 ESC-ID；用编号或自然语言。
```

### 19.2 卡片结构

```text
╭─ AITL · L3 人类裁决 ───────────────────────────────╮
│ 需求阶段   验收（reviewing）                        │
│ 三层位置   L3 ← L2（G3 已通过）                     │
│ 进度       3/3 Work Order verified                  │
│ 触发       不可逆动作待批准 · ESC-001               │
╰────────────────────────────────────────────────────╯

▍当前位置
  L3  ● 你在这里：等待裁决
       ▲  ESC-001 不可逆
  L2  ● G3 已通过 · run=reviewing
       ▲
  L1  ● WO-003 verified · 3/3

▍发生了什么
  executor 在 WO-003 需要 force-push feature/auth。

▍为什么需要你
  该动作会覆盖远程分支历史，无法自动恢复。
  规则 A3：不可逆动作永不自动化。

▍影响
  目标   origin/feature/auth
  diff   7f3a9c…
  范围   2 个 commit
  可逆   否

▍你可以
  1  确认执行      放行这一次动作；令牌 10 分钟内有效
  2  拒绝          停止该动作，并记录原因
  3  查看原始命令  展示完整命令、参数、目标
  4  查看 diff     展示将被覆盖的提交
  5  暂停整个 run  保留现场，稍后继续

回复编号，或直接说「确认 / 拒绝 / 详情 / 暂停」。
```

### 19.3 三层位置

| run.state | 需求阶段 | 三层位置 | 人的动作 |
|---|---|---|---|
| `initialized` | 意图 | L3 | 确认目标 / AC / 范围 |
| `executing` | 执行 | L2 / L1 | 通常不参与；H2 / H4 打断 |
| `reviewing` | 验收 | L3 | 接受 / 要求修改 |
| `accepted` | 已交付 | — | 结束 |
| `abandoned` | 已终止 | — | 结束 |

执行中只有三类事件会把位置抬到 L3：

```text
不可逆动作      → L3 批准
范围外 / 歧义   → L3 裁决
执行阻塞        → L3 解除阻塞
```

L2 展示「上一个 gate + 证据数 + 未决 escalation」，L1 展示「当前 WO + 进度」。

### 19.4 六类卡片

| 类型 | 触发 | 必要信息 | 选项 |
|---|---|---|---|
| `intent` | run 启动 | 目标 / 非目标 / AC / 范围 / 风险 | 确认启动 / 修改 / 取消 |
| `approve` | irreversible | 原始操作 / diff / 目标 / 可逆性 | 确认 / 拒绝 / 详情 / 暂停 |
| `out_of_scope` | 越界 | 越界内容 / 影响 / 替代方案 | 批准本次 / 拒绝 / 改范围 / 暂停 |
| `ambiguous` | 歧义 | 问题 / 候选解释 / 影响 | A / B / C |
| `accept` | reviewing | 摘要 / gate / evidence / findings | 接受 / 要求修改 / 看证据 / 放弃 |
| `blocked` | 阻塞 | 失败原因 / 已尝试 / 建议 | 重试 / 换方案 / 缩范围 / 终止 |

验收卡示例：

```text
╭─ AITL · L3 验收 ───────────────────────────────────╮
│ 需求阶段   验收（reviewing）                        │
│ 三层位置   L3 ← L2（G3 已通过）                     │
│ 进度       3/3 Work Order verified                  │
│ 触发       结果待接受                               │
╰────────────────────────────────────────────────────╯

▍当前位置
  L3  ● 你在这里：验收
       ▲
  L2  ● G3 已通过 · evidence 3 份
       ▲
  L1  ● 3/3 verified

▍交付摘要
  WO-001  ...  verified
  WO-002  ...  verified
  WO-003  ...  verified

▍验证
  G0 通过 · G3 通过
  findings：0 blocker / 1 major（已接受为债）

▍你可以
  1  接受结果
  2  要求修改（请说明）
  3  查看 evidence
  4  放弃本轮
```

### 19.5 字段规范

| 字段 | 必填 | 内容 | 来源 |
|---|---|---|---|
| 需求阶段 | 是 | 意图 / 执行 / 验收 / 已交付 / 已终止 | `flow.state` |
| 三层位置 | 是 | L3 / L2 / L1 + 箭头 | `graph` |
| 进度 | 是 | verified / total WO | `graph.metrics` |
| 触发 | 是 | escalation / gate / accept | `graph` |
| 当前位置 | 是 | 三层逐行列出，标出「你在这里」 | `graph.path` |
| 发生了什么 | 是 | 事实，1–3 行 | latest history |
| 为什么需要你 | 是 | 规则或 gate | policy |
| 影响 | 是 | 范围 / 不可逆 / 成本 | capability + artifact |
| 你可以 | 是 | 编号选项 + 一行后果 | action map |
| 机器可读块 | 否 | 隐藏 JSON，供解析与测试 | renderer |

### 19.6 选项规范

```text
1. 编号 + 一行后果。
2. 接受自然语言别名（确认 / 拒绝 / 详情 / 暂停）。
3. 不可逆：无默认项、无批量项、必须展示原始操作与 diff。
4. 歧义：用 A/B/C，避免与批准编号混淆。
5. 任何卡片都保留「暂停 / 终止」出口。
6. 选项必须映射到合法动作；没有动作的选项不出现。
7. 回复歧义 → 渲染澄清卡，不猜。
```

### 19.7 生成与解析

```text
┌─────────────────────────────────────────────────┐
│ sancai_card.py                                    │
│   render(type, flow, graph, payload) -> str     │
│   type: intent / approve / out_of_scope         │
│         / ambiguous / accept / blocked          │
└─────────────────────────────────────────────────┘
        │
        ├─ /sancai start      → intent
        ├─ /sancai approve    → approve / out_of_scope / ambiguous
        ├─ /sancai accept     → accept
        ├─ /sancai status     → 只读状态卡
        └─ escalation 触发  → 对应卡片
```

模型只做两件事：

```text
1. 原样输出卡片。
2. 解析人的回复，调用对应动作。
```

卡片内容被模型改写，视为失败；位置、进度、gate、证据数必须来自脚本。

### 19.8 验收标准

```text
1. 六类卡片都包含 8 个必填字段。
2. 位置与 flow.state 一致。
3. 不可逆卡片无默认项、无批量项。
4. 选项映射到合法动作。
5. 歧义回复触发澄清。
6. 卡片由脚本渲染；模型改写 = 失败。
```

---

## 20. 过程图（Process Graph）

### 20.1 结论

需要记录过程与动作，但要区分三件事：

```text
✓ 记录：append-only history
✓ 派生：graph.json（读模型）
✗ 不上 graph database
✗ 不把 event sourcing 当架构
✗ 不起 daemon
```

理由：

```text
- 回退、重试、拒绝、返工是流程的一等公民；
  state.json 只存当前态会丢失过程。
- MVP 是单 run、几十个 WO；JSON + 派生图足够。
- graph DB / 事件溯源框架会引入新的一致性与运维问题，
  违背 v0.3 的收敛原则。
```

### 20.2 数据分层

```text
flow.json     当前状态（权威；原子写）
  history[]   追加日志（审计；只增不改）
graph.json    派生读模型（可视化/查询；可重建）
```

规则：

```text
1. flow.json 是当前态的唯一权威。
2. history 是过程记录，不参与当前态判定。
3. graph.json 是 history 的投影，删掉可重建。
4. 三者不一致时：以 flow.json 为当前态，重建 graph，
   并记录 projection_mismatch。
```

### 20.3 记录粒度

记录「动作与状态转移」，不记录每个 token：

```text
记录：
  run.created / run.state_changed / run.accepted / run.abandoned
  wo.created / wo.claimed / wo.submitted / wo.verified / wo.rejected / wo.reopened
  attempt.started / attempt.completed / attempt.failed
  gate.started / gate.passed / gate.failed
  escalation.raised / escalation.approved / escalation.rejected / escalation.expired
  decision.recorded
  capability.minted / capability.used / capability.revoked
  evidence.captured
  human.input

不记录：
  完整 transcript
  每个工具输出
  模型推理文本
  token 级日志
```

### 20.4 节点

| 节点 | ID | 关键字段 |
|---|---|---|
| `run` | `RUN-001` | state, intent_id, created_at |
| `work_order` | `WO-001` | state, ac_ids, owned_files |
| `attempt` | `ATT-001` | wo_id, state, executor_session |
| `gate` | `G3-001` | wo_id, state, verdict |
| `escalation` | `ESC-001` | type, blocking, status |
| `decision` | `DEC-001` | escalation_id, choice, message |
| `evidence` | `EVD-001` | kind, path, sha256 |
| `artifact` | `ART-001` | kind, path, diff_sha |
| `actor` | `HUMAN` / `sancai-executor` / `sancai-verifier` | kind, id, session |

### 20.5 边

| from → to | 类型 | 含义 |
|---|---|---|
| run → wo | `contains` | run 包含 WO |
| wo → wo | `depends_on` | WO 依赖 |
| wo → attempt | `has_attempt` | WO 的执行尝试 |
| attempt → attempt | `supersedes` | 新尝试取代旧尝试 |
| gate → wo | `checks` | 门禁检查 WO |
| gate → evidence | `uses` | 门禁使用证据 |
| escalation → wo / attempt / gate | `raised_from` | 升级来源 |
| decision → escalation | `resolves` | 人裁决升级 |
| decision → wo / attempt | `returns_to` | 拒绝后退回修改 |
| attempt → artifact | `produced` | 产出补丁 |
| gate → wo | `verifies` | 验证通过 |
| run → decision | `accepted_by` | 人接受结果 |

### 20.6 history entry

```json
{
  "seq": 42,
  "ts": "2026-11-19T12:00:00Z",
  "run_id": "RUN-001",
  "action": "wo.rejected",
  "actor": {"kind": "verifier", "id": "sancai-verifier", "session": "..."},
  "subject": {"type": "work_order", "id": "WO-001"},
  "from": "submitted",
  "to": "executing",
  "reason": "AC-2 failed",
  "payload": {"attempt": "ATT-001", "gate": "G3", "return_to": "ATT-001"},
  "prev_hash": "sha256:..."
}
```

字段说明：

```text
seq         单调递增，幂等键
action      动作类型
actor       谁做的
subject     作用对象
from/to     状态转移
reason      人可读原因
payload     结构化细节
prev_hash   可选，哈希链
```

### 20.7 graph.json

```json
{
  "run_id": "RUN-001",
  "generated_at": "2026-11-19T12:00:00Z",
  "last_seq": 42,
  "nodes": [
    {"id": "RUN-001", "type": "run", "state": "reviewing"},
    {"id": "WO-001", "type": "work_order", "state": "verified"},
    {"id": "ATT-001", "type": "attempt", "state": "rejected"},
    {"id": "ATT-002", "type": "attempt", "state": "verified"},
    {"id": "G3-001", "type": "gate", "state": "passed"}
  ],
  "edges": [
    {"from": "RUN-001", "to": "WO-001", "type": "contains"},
    {"from": "WO-001", "to": "ATT-001", "type": "has_attempt"},
    {"from": "WO-001", "to": "ATT-002", "type": "has_attempt"},
    {"from": "ATT-002", "to": "ATT-001", "type": "supersedes"},
    {"from": "G3-001", "to": "WO-001", "type": "checks"}
  ],
  "metrics": {
    "wo_total": 1,
    "wo_verified": 1,
    "attempts": 2,
    "rejections": 1,
    "human_minutes": 4
  }
}
```

### 20.8 状态机与回退环

Run：

```text
initialized → executing → reviewing → accepted
     │            │           │
     └────────────┴───────────┴→ abandoned
```

Work Order：

```text
pending → claimed → executing → submitted → verified
                        ▲            │
                        │            │ G3 fail / human reject
                        │            ▼
                        └──── rejected (new attempt)
```

Attempt：

```text
ATT-001  submitted → rejected
ATT-002  submitted → verified
ATT-002  supersedes ATT-001
```

拒绝与返工示例：

```text
WO-001
  ├─ ATT-001  submitted → G3 fail → rejected
  └─ ATT-002  submitted → G3 pass → verified
       ▲
       └─ supersedes ATT-001

history:
  wo.submitted       WO-001 ATT-001
  gate.failed        G3-001 WO-001
  wo.rejected        WO-001 ATT-001 reason=AC-2
  attempt.started    ATT-002
  attempt.supersedes ATT-002 ATT-001
  wo.submitted       WO-001 ATT-002
  gate.passed        G3-001 WO-001
  wo.verified        WO-001
```

人拒绝示例：

```text
decision.recorded  DEC-001 choice=reject message="..."
decision.returns_to DEC-001 WO-001
wo.rejected        WO-001 reason="human rejected"
```

区别：

```text
verifier 拒绝 → 自动返工，不需要人。
人拒绝       → 产生 decision + returns_to，回到 L1 修改。
```

### 20.9 投影与一致性

```text
1. 每个状态转移恰好一条 history。
2. history 只增不改；修正用新条目（wo.corrected）。
3. graph = project(history)，纯函数。
4. 重建幂等：同一 history → 同一 graph（忽略 generated_at）。
5. prev_hash 可选；用于发现篡改，不构成安全边界。
6. 单写者；append 用文件锁。
7. 崩溃恢复：读 flow + history，补投影。
```

### 20.10 查询与指标

| 查询 | 用途 |
|---|---|
| attempts(WO) | 返工次数 |
| rejections(gate) | 门禁质量 |
| cycle_time(WO) | executing → verified |
| human_minutes(run) | 人力成本 |
| escalation_rate(WO) | 升级频率 |
| approval_rate | 人批准比例 |
| bottleneck_gate | 失败最多的门禁 |
| loop_depth | 最大返工深度 |

### 20.11 与卡片的集成

卡片不是另写一套叙述，而是图的一个视图：

| 卡片字段 | 图查询 |
|---|---|
| 需求阶段 | `run.state` |
| 三层位置 | `path(run → pending decision)` |
| 进度 | verified WO / total WO |
| 触发 | latest open escalation |
| 发生了什么 | latest history entry |
| 影响 | capability + artifact |
| 选项 | action map from state |

### 20.12 MVP 范围与非目标

MVP：

```text
- flow.json 增加 history[]
- sancai_state.py 在每次转移时 append
- sancai_graph.py derive / show / mermaid / metrics
- sancai_card.py 读 graph/state
- tests
```

非目标：

```text
- graph DB（Neo4j 等）
- daemon / 实时订阅
- Web UI
- event sourcing 框架
- 多 run 合并图
- 完整 transcript 入库
```

### 20.13 验收标准

```text
1. 一次拒绝产生 ATT-002，且 ATT-002 supersedes ATT-001。
2. 人拒绝产生 decision + returns_to 边。
3. 重建幂等。
4. 每个状态转移都有 history；无孤儿状态。
5. 卡片位置与 graph 一致。
6. 指标在 3-WO 样例上正确。
7. history 不被改写；修正以新条目出现。
```

### 20.14 开放问题

```text
1. history 保留多久？何时压缩？
2. 多 run 是否合并成一张图？
3. 跨仓库依赖如何建边？
4. 人的原话可能含敏感信息，如何脱敏？
5. prev_hash 的威胁模型是什么？
6. 工具调用记录到什么粒度？（MVP 只记状态转移）
7. 查询接口：已定为固定函数（见 20.15.4）；未来是否加 DSL 再看。
```

### 20.15 图在插件流程中的使用

#### 20.15.1 原则

```text
图是读模型，不是第二真相。
写路径只走脚本；读路径只走固定查询；
授权仍然由 gate / capability / hook 独立完成。
```

图承担三件事：解释现在、记录历史、聚合指标。它不负责批准，只负责说清楚。

实现映射：`flow.json` 当前由 `run.json` 承担；`history[]` 由 `events.jsonl` 承担；`graph.json` 由 `sancai_graph.py` 派生；卡片由 `sancai_card.py` 渲染。

#### 20.15.2 全流程

```text
/sancai start
  │ 写：run.created / wo.created / intent.signed
  ▼
L3 意图卡              ← graph.position()
  │ 人确认
  ▼
PM 派发 WO
  │ 写：wo.claimed / attempt.started
  ▼
executor 执行
  │ 写：tool.allowed / evidence.captured   ← hook
  ▼
G0 / G3
  │ 写：gate.started / gate.passed / gate.failed
  ├─ fail → wo.rejected + attempt.started（新 ATT）
  └─ pass → wo.verified
  ▼
不可逆动作
  │ 写：escalation.raised
  ▼
L3 批准卡              ← graph.position() + graph.impact()
  │ 人确认
  │ 写：decision.recorded / capability.minted
  ▼
executor 执行
  │ 写：capability.used
  ▼
全部 verified
  │ 写：run.state_changed → reviewing
  ▼
L3 验收卡              ← graph.summary()
  │ 人接受
  │ 写：decision.recorded / run.accepted
  ▼
graph 冻结
```

#### 20.15.3 写路径

| 时机 | 脚本 | 事件 |
|---|---|---|
| run 初始化 | `sancai_state.py` | `run.created` / `wo.created` |
| 意图签署 | `sancai_state.py` | `intent.signed` / `run.state_changed` |
| 领取 WO | `sancai_state.py` | `wo.claimed` / `attempt.started` |
| 工具调用 | `sancai_hook.py` | `tool.allowed` / `tool.denied` / `evidence.captured` |
| G0 / G3 | `sancai_gate.py` | `gate.started` / `gate.passed` / `gate.failed` |
| 验证失败 | `sancai_gate.py` | `wo.rejected` |
| 升级 | `sancai_escalate.py` | `escalation.raised` |
| 人裁决 | `sancai_escalate.py` | `decision.recorded` / `escalation.approved` / `escalation.rejected` |
| 能力令牌 | `sancai_capability.py` | `capability.minted` / `capability.used` / `capability.revoked` |
| 验收 | `sancai_state.py` | `decision.recorded` / `run.accepted` |
| 放弃 | `sancai_state.py` | `run.abandoned` |

约束：

```text
1. 模型不能直接写 history；只能调用脚本。
2. 每次状态转移恰好一条事件；没有事件的状态变化视为 bug。
3. 事件写入失败 → 状态转移失败（fail-closed）。
4. 事件里不放 secret；tool args 脱敏。
```

#### 20.15.4 读路径

| 消费者 | 查询 | 用途 |
|---|---|---|
| `sancai_card.py` | `position` / `progress` / `latest_trigger` / `latest_event` | 渲染卡片 |
| PM agent | `next` / `open_escalations` / `blocked_wo` | 调度下一个 WO |
| `sancai_gate.py` | `evidence_for` / `attempts` / `independence` | 门禁判定 |
| `sancai_hook.py` | `capability_for` / `is_irreversible` / `owned_files` | 拦截越界与不可逆 |
| `/sancai status` | `summary` / `metrics` | 汇报 |
| eval | `metrics` / `history export` | Phase -1 指标 |

MVP 只暴露固定查询，不开放任意 Cypher / SQL：

```bash
sancai_graph.py position RUN-001
sancai_graph.py next RUN-001
sancai_graph.py attempts WO-001
sancai_graph.py open-escalations RUN-001
sancai_graph.py metrics RUN-001
sancai_graph.py show RUN-001
```

模型拿到的是结构化结果，不是整张图；这样既省 context，也避免模型「看图自由发挥」。

#### 20.15.5 三个时间尺度

```text
现在   position / next / open escalations
       → 卡片与调度

历史   attempts / rejections / decisions / capability audit
       → 返工原因、谁批准了什么、令牌是否被使用

聚合   cycle time / rejection rate / human minutes / bottleneck
       → eval 与流程改进
```

#### 20.15.6 卡片如何由图生成

```python
def card_position(run):
    g = graph.load(run)
    esc = g.open_escalations()

    return {
        "stage":    g.run.state,
        "layer":    "L3" if esc else ("L2" if g.run.state == "executing" else "—"),
        "progress": f"{g.verified_count()}/{g.wo_count()}",
        "trigger":  esc[0].id if esc else None,
        "what":     g.latest_event().summary,
        "why":      policy.reason(esc[0]) if esc else None,
        "impact":   capability.impact(esc[0]) if esc else None,
        "options":  actions.for_state(g.run.state, esc),
    }
```

卡片不自己编内容；每个字段都能追溯到一条事件或一个节点。

#### 20.15.7 完整例子

```text
RUN-001: 3 个 Work Order

WO-001  ATT-001 → G3 fail → rejected
        ATT-002 → G3 pass → verified

WO-002  ESC-001 force-push → approved
        DEC-001 → CAP-001 → verified

WO-003  verified

run: reviewing
```

图：

```text
RUN-001
 ├─ WO-001  verified  (attempts=2)
 │    ├─ ATT-001  rejected
 │    └─ ATT-002  verified
 ├─ WO-002  verified
 │    └─ ESC-001  approved
 │         └─ DEC-001 → CAP-001
 └─ WO-003  verified
```

指标：

```text
attempts      = 3
rework        = 1
rejections    = 1
escalations   = 1
approvals     = 1
human_minutes = 6
```

#### 20.15.8 护栏

```text
1. 写路径只在脚本；模型不能直接改 history。
2. 读路径是固定函数；MVP 不开放任意查询。
3. 图不授权：gate 仍然校验 evidence，capability 仍然校验 token。
4. graph.json 缺失或过期 → 从 history 重建；
   重建失败 → 降级到 flow.json，并在卡片上标注 degraded。
5. 事件写入失败 → 状态转移失败（fail-closed）。
6. hook 漏事件 → Stop 时对账，标记 evidence.missing。
7. 图里不放 secret；tool args 脱敏。
8. 图不参与「正确性判定」，只参与「位置、历史、指标」。
```

#### 20.15.9 MVP 范围

```text
MVP 用：
  事件：run / wo / attempt / gate / escalation / decision / capability / evidence
  派生：graph.json
  查询：position / next / attempts / open-escalations / metrics / show
  卡片：6 类

MVP 不用：
  SQLite / 图数据库
  任意 Cypher / SQL
  跨 run 合并图
  Web UI
  完整 transcript
```

#### 20.15.10 与 eval 的关系

```text
human_minutes   = sum(human.input 的时长)
rework          = attempts - wo_count
rejection_rate  = wo.rejected / wo.submitted
escalation_rate = escalation.raised / wo_count
escape          = run.accepted 之后的事故事件
```

图本身就是埋点，不另建一套 eval 数据管道。

### 20.16 存储选型

#### 20.16.1 结论

```text
MVP：JSON（flow.json + history[] + graph.json）
需要查询时：SQLite 作为派生读模型
图数据库：只在高规模 / 跨 run / 真实路径查询时再上
```

#### 20.16.2 候选对比

| 方案 | 形态 | 优点 | 代价 |
|---|---|---|---|
| JSON | 文件 | 零依赖、可读、可 diff、可审计、易分发 | 无查询语言；全量加载 |
| SQLite（递归 CTE） | 嵌入式 | 零外部依赖、ACID、单文件、SQL | 需要同步；schema 迁移 |
| DuckDB + DuckPGQ | 嵌入式 | 分析快、SQL/PGQ 路径查询 | 依赖重；插件分发成本 |
| LadybugDB | 嵌入式图 | Cypher、Kùzu 兼容 | 生态新；需验证 |
| Cozo | 嵌入式图 | Datalog、嵌入式 | 生态小；维护风险 |
| Neo4j / Memgraph | 服务 | 成熟图查询 | 需起服务；不适合插件 |

#### 20.16.3 Kùzu / LadybugDB 现状

调研时 Kùzu 已被 Apple 收购并归档；社区以 LadybugDB 延续其方向。设计上不依赖任何单一嵌入式图引擎，避免把插件绑到一个可能停止维护的项目上。

#### 20.16.4 为什么 MVP 不上图数据库

```text
1. 数据小：一个 run 几十到几百个节点，JSON 足够。
2. 查询固定：position / next / attempts 等几个函数，不需要通用图查询。
3. 分发：插件应零原生依赖；二进制图库会带来平台兼容问题。
4. 审计：JSON 可读、可 diff、可直接进 git；二进制库不透明。
5. 语义：图数据库解决存储与查询，不解决「什么算一次状态转移」。
6. 可逆：JSON → SQLite 是加法；先上图库再退回是减法。
```

#### 20.16.5 SQLite 最小 schema（未来）

```sql
CREATE TABLE events (
  seq          INTEGER PRIMARY KEY,
  run_id       TEXT NOT NULL,
  ts           TEXT NOT NULL,
  action       TEXT NOT NULL,
  actor_kind   TEXT NOT NULL,
  actor_id     TEXT,
  subject_type TEXT NOT NULL,
  subject_id   TEXT NOT NULL,
  from_state   TEXT,
  to_state     TEXT,
  reason       TEXT,
  payload      TEXT
);

CREATE INDEX idx_events_run ON events(run_id, seq);
CREATE INDEX idx_events_subject ON events(subject_type, subject_id);

CREATE TABLE wodeps (
  run_id     TEXT NOT NULL,
  wo_id      TEXT NOT NULL,
  depends_on TEXT NOT NULL,
  PRIMARY KEY (run_id, wo_id, depends_on)
);
```

`wodeps` 是为了递归 CTE 查依赖闭包；其余图关系仍可从 `events` 投影。

#### 20.16.6 升级触发条件

```text
满足任一才考虑 SQLite：
  1. 单 run 事件 > 5,000 条，或单仓库 run > 100 个。
  2. 需要在运行时做依赖闭包 / 关键路径查询。
  3. 需要跨 run 聚合指标。

满足任一才考虑图数据库：
  1. 节点 > 10,000 且需要多跳路径查询。
  2. 跨仓库 / 跨团队的过程图合并。
  3. 需要 Cypher / Datalog 级别的 ad-hoc 分析。
```

#### 20.16.7 决策记录

```text
决策：MVP 用 JSON；SQLite 作为可选派生读模型；图数据库延后。
理由：数据小、查询固定、零依赖分发、JSON 可审计；图数据库不解决事件语义。
代价：大规模查询需要自己写投影；接受，因为当前规模不需要。
复审：Phase -1 eval 结束后，按 20.16.6 的触发条件复审。
```

### 20.17 防呆加固与残余信任边界（v0.4.1）

13 个对抗场景的审计发现 7 个 P0；已按「机制优先、提示兜底」修复：

| P0 | 机制 | 验证 | 残余 |
|---|---|---|---|
| Bash 前缀绕过 | `shlex` 分词 + 元字符拒绝 + argv 级白名单；`git add/commit` 检查暂存区；`find` 写标志拒绝；仓库外读路径拒绝 | 23 个单测 + 审计场景 1 | 构建/测试脚本本身可执行任意仓库代码 |
| agent 自铸令牌 | `mint` 仅 TTY，非交互需显式 `SANCAI_ALLOW_NONINTERACTIVE_MINT=1`；Bash 策略拒绝 capability CLI | 审计场景 3 | 同用户进程仍可伪造环境变量 |
| 令牌复用 | 使用即 `os.replace` 为 `.used`；再次检查识别 `.used` | 审计场景 4 | 令牌文件被复制后可能被再次使用 |
| 状态机信任调用者 | `sign` 快照；`executing` 需已签 intent；`reviewing` 需全部 WO verified + gate verified；`verified` 只能由 gate 写 | 审计场景 5/6/12 | 脚本仍可被直接调用，但会走同一校验 |
| verifier 独立性自报 | `--context-id` 必须不同于 executor/claim；prompt hash、read-only、未读 executor 推理、evidence hash、时间顺序 | 审计场景 9 | context id 仍是自报，无法证明进程来源 |
| findings 不阻塞 | pass + blocker/critical 直接拒绝；gate/accept 双检 | 审计场景 10 | verifier 可以漏报，需元评估 |
| H1 仅提示 | `sign` 记录会话、原话、快照、nonce；未签不能进入 executing；`SANCAI_REQUIRE_TTY_SIGN=1` 可强制人在终端签 | 审计场景 12 | 默认仍是契约门，无法在插件内证明「签的是人」 |

**残余信任边界（必须明说）**

```text
1. 防呆不是防恶意。威胁模型是同用户下的误操作与 agent 自作主张，
   不是被攻陷的同用户进程、被篡改的仓库、或恶意 MCP server。
2. H1 是 UX / 契约门，不是密码学人证。高风险仓库应要求人在终端
   亲自运行 mint / sign，而不是让 agent 代跑。
3. verifier 的独立性是「自报 + 结构校验」，不是进程证明。
   需要强保证时，用独立机器/独立模型/人工抽查。
4. SANCAI_SECRET 放在环境变量里会被同用户进程读取；生产环境建议
   keychain / secret manager。
5. npm test / make test 等构建命令可以执行仓库内任意代码；
   capability 只保证「命令类别」，不保证「脚本内容」。owned_files
   与 G3 才是内容边界。
6. Bash 策略是 best-effort，不是沙箱；复杂 sed / 构建脚本 / 测试代码
   仍可能写入。真正的隔离要靠容器/VM/只读挂载。
```

### 20.18 人类侧防呆（v0.4.1）

agent 侧防的是「agent 乱来」；人类侧防的是「人批错、批快、批疲劳」。

| 人类失误 | 机制 | 残余 |
|---|---|---|
| 模糊批准（“行”“ok”“1”） | `sign` / `approve` / `accept` 只接受明确词表；裸数字与 `ok` 拒绝 | 人仍可能把明确词当口头禅 |
| 批错对象 | 卡片头部固定显示 run / WO / ESC；一次只出一个决策；队列编号 | 多 run 并行时仍需人看清 |
| 批准过期内容 | `sign` 绑定 intent 快照；token 绑定 action + diff + TTL；diff 变化即失效 | 人可能没看 diff 就批准 |
| 批量批准不可逆 | 不提供批量；每个动作单独 token；TTL 600s | 连续多次批准仍可能疲劳 |
| 误验收 | `accept` 只接受明确词；拒绝 open escalation / 未 verified gate / 缺 verdict / blocker | 非阻塞 findings 可被静默接受 |
| 拒绝无记录 | `reject` 必须给具体理由；写 decision 事件 | 理由质量无法自动判断 |
| 审批疲劳 | 记录 human_minutes、card 数、决策间隔；eval 里作为指标 | MVP 没有硬性冷却/二次审批 |
| 伪造卡片 | 卡片由 `sancai_card.py` 从 graph 生成，PM 必须逐字输出 | 显示真实性未解决：被攻陷的 agent 可伪造文本 |

原则：

```text
1. 一次一个决策；默认不批准。
2. 不可逆动作必须用词，不用数字。
3. 拒绝也要记录理由，不能靠沉默。
4. 批准绑定快照/哈希，过期即失效。
5. 高风险场景：SANCAI_REQUIRE_TTY_SIGN=1 + 人跑 mint/sign + 双人复核。
```

### 20.19 人类侧防呆 v2（设计稿）

§20.18 解决的是“能不能拦住模糊批准”；还有四类问题没有解决，单独设计于
[`human-side-foolproofing-design.md`](../../leo-team/design/human-side-foolproofing-design.md)：

| 层 | 问题 | 机制 |
|---|---|---|
| L1 注意力 | 审批疲劳、连续批准、冷却缺失 | 风险分级 T0–T4；一次一卡；T2 dwell 3s；T3 dwell 10s + 冷却 60s；连续 T2 上限；注意力预算耗尽即 blocked；疲劳检测 |
| L2 真实性 | agent 可伪造卡片文本、旧卡重放 | `card_id` / `card_hash` / 8 位 `card_code` / HMAC；写 `cards/<id>.json`；`used_at` 防重放；人可自行 `verify --card-id`；决策必须绑定 `--card-id --card-code` |
| L3 确认 | 非阻塞 findings 被静默接受 | `findings_hash`；blocker/critical 硬失败；major 必须 `defer` 或 `waive:<reason>`；minor/info 必须 `--ack-findings`；defer 生成 follow-up WO |
| L4 人证 | session id 不能证明人在场 | `ApprovalProvider`：`tty` / `gpg` / `os-biometric` / `webauthn` / `two-person`；T3 要求人跑 TTY（GPG 可选）；T4 双人 + 独立环境 |

落地顺序：Phase 1 卡片绑定 + findings 处置 + dwell；Phase 2 TTY CLI + 注意力预算；
Phase 3 GPG + 双人 + OS 生物识别；Phase 4 WebAuthn / 独立审批机。

### 20.20 v1.0 设计决策（已对齐）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 人的边界 | 只保留四触发器：价值/优先级歧义、不可逆/高爆炸、残余风险接受、权威扩张。其余 agent + verifier。 |
| 2 | 不可逆分类 | intent 声明 `risk_tier` + `irreversible_actions`；policy 审核；agent 只能建议，不能自定 T0/T1。未知动作 fail closed 到 T2。 |
| 3 | verifier 独立性 | MVP：独立上下文 + read-only + 禁读 executor 叙述 + 系统计算 independence metadata；Phase 2 可选独立进程/模型；policy 可要求更强。 |
| 4 | 高风险人证 | T2：明确词 + 卡片绑定 + dwell；T3：人跑 TTY `sancai_human.py`（GPG 可选，Phase 3 默认）；T4：双人 + 独立环境 + 硬件密钥。 |
| 5 | MVP 观测面 | 卡片 + CLI + `graph.json`；不做 dashboard / web UI。 |

实现映射：价值歧义 → `spec_ambiguous`；不可逆 → `irreversible`；残余风险 → `accept` findings disposition；权威扩张 → `out_of_scope` + 新 intent。

这五项是设计基线；实现与它们冲突时，以这五项为准。

### 20.21 Phase 1 实现映射（卡片绑定）

Phase 1 把「人的决定必须绑定到它看到的那张卡」落成代码。核心模块是
`plugins/sancai-loop-plugin/scripts/sancai_cards.py`，CLI 入口是
`plugins/sancai-loop-plugin/scripts/sancai_card.py`。

**卡片对象**

- 每张可执行卡片持久化到 `.sancai/runs/<run>/L3-intent/decisions/cards/<card_id>.json`；
  `card_id` 形如 `CARD-<12 hex>`。
- 卡片包含 `kind`（`intent` / `approve` / `out-of-scope` / `ambiguous` /
  `accept` / `blocked`）、`tier`、`payload`、`options`、`created_at`、
  `card_hash`、`card_code`、`mac`、`used_at`。
- `card_hash = sha256(canonical({kind,tier,payload,options,created_at}))`；
  `card_code = sha256(card_hash)[:8]`；`mac = HMAC-SHA256(secret, card_hash)`，
  secret 取 `SANCAI_SECRET` 或 `SANCAI_CARD_SECRET`。`verify_card` 重算
  hash/code，校验 mac（卡有 mac 但无 secret 也算失败），并递归做
  `expected_payload` 子集比对。`used_at` 不参与真伪判定，只由
  `consume_card` 判重。
- 渲染尾部固定输出
  `卡片编号  CARD-...   校验码  xxxxxxxx` 与回复示例；模型只能原样转述，
  不得自行生成或猜码。

**payload 绑定**

| 卡 | payload |
|---|---|
| `intent` | `intent_sha`、`goal`、`acceptance_count`、`work_order_count` |
| `approve` / `out-of-scope` / `ambiguous` | `esc`、`wo`、`esc_type`、`status`、`what_tried`、`evidence`、`options` |
| `accept` | `run`、`state`、`wos`（每个 WO 状态）、`gate_results`、`findings_hash`、`findings_count` |
| `blocked` | `wo`、`state`、`reasons` |

**决策端绑定**

- `sancai_state.py sign` 必须带 `--card-id --card-code`，消费卡片后再写
  `intent.approval`。
- `sancai_escalate.py approve|reject` 必须带 `--card-id --card-code`，按
  escalation 字段重建 expected payload 后消费。
- `sancai_state.py accept` 必须带 `--card-id --card-code --session-id`；
  若有 findings 必须 `--ack-findings`；major findings 必须且只能有一个
  `--disposition defer:<WO-ID>` 或 `waive:<reason>`；blocker/critical
  永远拒绝。`defer` 会创建后续 WO，`waive` 记录原始理由。
- `consume_card` 依次检查：验签 → code 匹配 → 未使用 → dwell → 标记
  `used_at`。因此失败尝试（除验签/状态校验早退外）也会消耗卡片，重试必须
  重新渲染。
- `findings_hash` 对每条 finding 只取判定相关字段并排序后哈希，与顺序无关；
  verdict、accept 卡和 acceptance 记录使用同一算法。

**dwell**

`DWELL_SECONDS = {T0:0, T1:0, T2:3, T3:10, T4:60}`，默认 T2。卡太新时
拒绝信息包含剩余秒数；不得用重试循环绕过 dwell。

**验证入口**

`sancai_card.py verify --run <run> --card-id <card_id> [--json]` 输出卡片与
`verification.ok/problems`，有问题时 exit 1。测试
`plugins/sancai-loop-plugin/tests/test_phase1.py` 覆盖篡改、错码、重放、T2 dwell、
无卡决策、approve 绑定、minor/major findings、findings hash 顺序无关性。


---

### 20.22 Phase 2 实现映射（人证通道与决策观测）

Phase 2 补三件事，不改状态机和卡片协议：

| 能力 | 实现 |
|---|---|
| H1 交互式确认 | `sancai_state.py record-intent` 记录 AskUserQuestion 的 `启动` 选择；不要求卡片编号，H1 是 contract gate |
| 人证入口 | `sancai_human.py sign/approve/reject/accept`，要求 `stdin` 是 TTY；agent Bash 的 `HUMAN_DECISION_COMMANDS` 同时拒绝 `sancai_human.py` 和底层决策命令；H2/H3 使用 |
| 自定义升级选项 | `sancai_card.build_card` 在 approve / out-of-scope 卡片上追加 escalation `options`；accept 卡回复示例使用 `接受` |
| 决策延迟 | `sign/approve/reject/accept` 记录 `latency_seconds` 到 intent approval、escalation 记录、`outcome` 和 `events.jsonl` |
| 观测指标 | `sancai_graph.metrics` 新增 `decisions`、`median_latency_seconds`、`fatigue_suspected`；`human_minutes` 由决策延迟累计 |

残余风险：

- `sancai_human.py` 的 TTY 检查是进程级，不是 OS 级；agent 仍可通过 import `sancai_state` 的代码路径绕过命令守卫。
- `_human_decision` 是 token 级扫描，可能对只读命令误报（例如 `git log -- sancai_state.py accept`）。
- `fatigue_suspected` 目前用“决策数 ≥ 5 且中位延迟 < 2s”近似，没有时间窗口，也没有审批率；Phase 3 再用 `card_rendered`/`decision_recorded` 的时间戳做真实预算。

### 20.23 原生权限提示（v0.6.0）

Phase 2 的 TTY 入口可用，但要求人复制命令，体验不可接受。v0.6.0 把 H2/H3 的确认改成宿主原生权限提示：

| 能力 | 实现 |
|---|---|
| 唯一 agent 可用入口 | `sancai_decide.py sign/approve/reject/accept/mint`，转发到底层脚本 |
| 人类确认 | `PreToolUse` 对 `sancai_decide.py` 返回 `permissionDecision: "ask"`；Claude Code 弹出 Allow/Deny，人点击即可，不复制命令 |
| 决策记录 | 底层 `sign/approve/reject/accept` 仍写 session、phrase、card pair、latency |
| token 签发 | `sancai_decide.py mint` 设置 `SANCAI_NATIVE_UI=1`，`mint` 跳过 TTY/手输确认，但仍要求 `SANCAI_SECRET`；提示词显示 action/diff/ttl |
| 直接调用 | `sancai_state.py sign/accept`、`sancai_escalate.py approve/reject`、`sancai_human.py` 仍被 agent Bash 拒绝；`sancai_verdict.py write` 允许 |
| T4 回退 | `sancai_human.py` 保留为真实 TTY 进程的终端路径，不再是默认路径 |

安全边界：`ask` 是宿主级确认，不是密码学证明；`permissionDecisionReason` 展示卡片/动作/run，但卡片本身仍由 `sancai_cards.py` 签名和单次消费。残余风险是宿主提示可能被用户习惯性快速批准，Phase 3 的 dwell/attention budget 仍需保留。

## 21. 开放问题

1. Intent 由谁起草？建议 agent 起草、人签，并显示来源差异。
2. 如何衡量 DoD 本身的质量？需要 AC 缺陷率指标。
3. 多仓库 / 多 agent 的 A2A 权限与上下文？
4. 长期记忆记什么、忘什么、如何审计？
5. verifier 自己如何被持续评估？
6. plugin 分发场景下 secret 如何安全存放？
7. Stop hook 的作用域能否可靠限定到当前会话？
8. history 的保留期与压缩策略？
9. 多 run / 跨仓库的过程图是否要合并？
10. 卡片文案的本地化与可访问性？

---

## 22. 一句话总结

> **v0.2 把方向写对了，v0.3 把不能落地的部分拿掉了，v0.4 把人和过程记录清楚了。**
> 核心仍然只保留四件事：**Intent 人签、Evidence 由 harness 捕获、不可逆动作走人的能力令牌、先 eval 再自治。**
> HIC 与过程图是记录/交互层：它们让「人在哪、发生了什么、能选什么」可读、可审计、可回放，但不新增自治机制。
> 20.15 / 20.16 进一步明确：图只做读模型，MVP 用 JSON，SQLite / 图数据库按规模升级。
> 其余机制（Mandate、信任账本、daemon、Health Board、影子队列、graph DB）继续延后。

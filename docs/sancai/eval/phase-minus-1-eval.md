# AITL Phase -1：可执行评估方案

- 状态：Draft
- 日期：2026-11-18
- 目的：在写 AITL 插件之前，回答一个问题——**AITL 是否真的比 HITL 更好？**
- 关联：`docs/sancai/design/loop-design.md` v0.3 §14

---

## 0. 决策问题

```text
H0：AITL MVP 在任务成功率、人工分钟、逃逸率上，不优于当前 HITL。
H1：AITL MVP 至少在一项主指标上显著更优，且其余主指标不退化。

如果 H0 不能被拒绝 → 停在 L2，不进入 Phase 1。
```

**这不是「跑一下看看」，而是预注册的淘汰实验。**

---

## 1. 三种模式

```text
A  当前 HITL
   人审计划 + 人审 diff + 人批准每个单元

B  单 agent + skills
   无 harness、无门禁、无升级；agent 自己完成并报告

C  AITL MVP
   Intent（人签）+ G0 + G3 + 三类升级 + 能力令牌
```

> B 是「不做 harness」的下界；A 是「当前做法」；C 是「候选」。
> 如果 C 连 B 都打不过，说明 harness 是纯负担。

---

## 2. 任务集设计

### 2.1 规模

```text
目标：40 个任务
最低：24 个任务
holdout：20%（8 个），不参与调参
```

### 2.2 分层

| 层 | 类型 | 目标数量 | 考察点 |
|---|---|---|---|
| S1 | 小范围局部改动 | 8 | 基本闭环、开销 |
| S2 | 跨模块改动 | 8 | 拆解、接口、回归 |
| S3 | 歧义需求 | 5 | 升级触发「定义缺失」 |
| S4 | 安全敏感改动 | 5 | 门禁、权限、审计 |
| S5 | 含不可逆动作 | 4 | 能力令牌、人工门 |
| S6 | bug 修复 / 回归 | 10 | 复现、负向验证 |

### 2.3 任务规范

每个任务一个 YAML：

```yaml
id: T-001
stratum: S1
repo: snapshots/repo-a
base_commit: "abc1234"
goal: "一句话可判成败"
non_goals:
  - "..."
acceptance:
  - id: AC-1
    check: command
    run: "npm test -- auth"
    expect: "exit_code == 0"
  - id: AC-2
    check: invariant
    run: "rg legacyEndpoint src/"
    expect: "matches == 0"
hidden_checks:
  - id: H-1
    run: "npm test -- regression"
    expect: "exit_code == 0"
irreversible_actions: false
data_impact: none
estimated_human_minutes: 15
notes: "用于 S1 基线"
```

**规则**：

```text
1. 所有 AC 必须可执行；manual 例外 ≤20%
2. hidden_checks 不展示给 agent，用于测逃逸
3. base_commit 固定；仓库快照不可变
4. 每个任务预先记录「人类预期耗时」
```

### 2.4 快照

```text
evals/snapshots/repo-a/   # git bundle 或固定 commit 的 worktree
evals/snapshots/repo-b/

每个 eval run 使用独立 worktree，避免互相污染。
这是**评估隔离**，不是插件运行时需求：
AITL MVP 直接在用户当前工作树执行，单写者串行，不建 worktree。
```

---

## 3. 指标定义

### 3.1 主指标（决定 GO / NO-GO）

| 指标 | 定义 | 采集方式 |
|---|---|---|
| **Task success** | 所有 AC 在最终状态通过 = 1，否则 0 | harness 跑 AC |
| **Human minutes** | 人主动投入的时间（不含等待 agent） | `eval timer` + 事件日志 |
| **Escape rate** | hidden_checks 失败或交付后 7 天内发现缺陷的任务占比 | hidden_checks + 事后记录 |
| **False completeness** | 声称完成但任一 AC 失败 = 1 | harness 判定 |

### 3.2 次指标

| 指标 | 定义 |
|---|---|
| AC pass rate | 通过的 AC / 总 AC |
| Cost | input + output + cache_read×0.1 + cache_write×1.25（按当前价折算 USD） |
| Human decisions | 每个任务的人工决策次数 |
| Time to first result | 从开始到第一个可审查 diff 的 wall-clock |
| Gate effectiveness | 对抗用例被拦截数 / 总数 |
| Verifier catch rate | 已知错误补丁被检出数 / 总数 |
| Review burden | 人阅读的 diff 行数 / 任务（可选） |

### 3.3 采集原则

```text
-  token / wall-clock 由 harness 采集，不由 agent 自报
-  human minutes 用独立计时器，不用事后估算
-  success 由 AC 判定，不用「看起来对」
-  所有分数同时报告 model + harness + effort
```

---

## 4. 数据采集

### 4.1 事件格式

`evals/results/raw/events.jsonl`，每行一个事件：

```json
{"ts":"2026-11-18T10:00:00Z","run_id":"R-001","task_id":"T-001","mode":"C","event":"start","actor":"human","meta":{}}
{"ts":"2026-11-18T10:00:05Z","run_id":"R-001","task_id":"T-001","mode":"C","event":"agent_start","actor":"agent","meta":{"model":"..."}}
{"ts":"2026-11-18T10:12:00Z","run_id":"R-001","task_id":"T-001","mode":"C","event":"agent_end","actor":"agent","meta":{"tokens":{"in":12000,"out":3000,"cache_read":8000},"wall_ms":715000}}
{"ts":"2026-11-18T10:13:00Z","run_id":"R-001","task_id":"T-001","mode":"C","event":"human_decision","actor":"human","meta":{"decision":"approve","active_ms":45000}}
{"ts":"2026-11-18T10:14:00Z","run_id":"R-001","task_id":"T-001","mode":"C","event":"accept","actor":"harness","meta":{"ac_passed":2,"ac_total":2}}
```

### 4.2 脚本

```text
evals/scripts/setup_task.sh   创建 worktree、写入 task.json
evals/scripts/run_task.sh     一次 run 的入口：启动/结束计时、调用 runner、写事件
evals/scripts/log_event.sh    追加事件
evals/scripts/summarize.py    聚合指标、配对比较、bootstrap CI
evals/scripts/check_gates.sh  对抗命令集（门禁有效性）
```

### 4.3 Runner 适配

```text
runners/manual.sh       人工执行（Phase -1 默认）
runners/claude-code.sh  调用 Claude Code（可选）
runners/scripted.sh     固定脚本（用于门禁测试）
```

---

## 5. 实验流程

```text
1. 冻结快照与任务集
2. 随机化任务顺序（每个 mode 独立洗牌）
3. 每个任务在 A / B / C 各跑一次
4. 抽 10 个任务重复 3 次，估计方差
5. 记录所有事件，禁止事后修改
6. 计算指标，只看 holdout 做最终判定
```

### 5.1 顺序与学习效应

```text
- 同一任务不要连续跑三种 mode；中间插入 washout 任务
- 记录 mode 顺序，分析时作为协变量
- 人工接受标准由 AC 决定，减少评审者主观偏差
```

### 5.2 盲法

```text
- success 由 AC 自动判定，评审者不知道 mode
- 人工分钟由计时器记录，不由人回忆
- 分析阶段再揭盲
```

---

## 6. 统计方法

```text
- 配对比较：同一 task 的 C vs A、C vs B
- 报告 median 和 mean
- 95% bootstrap CI（10,000 次）
- 二元指标报告比例 + Wilson CI
- 不做 p-hacking；20–40 个任务不足以支持强推断
- 结论写成「方向 + 区间」，不写成「显著」
```

---

## 7. 判定表

### 7.1 主判定（holdout）

| # | 条件 | 阈值 |
|---|---|---|
| 1 | Task success 非劣 | `success_C ≥ success_A − 5pp` 且 `≥ success_B − 5pp` |
| 2 | Human minutes 下降 | `human_minutes_C ≤ 0.70 × human_minutes_A` |
| 3 | Escape 不上升 | `escape_C ≤ escape_A` 且 `≤ escape_B` |
| 4 | False completeness | `≤ 5%` |

### 7.2 次判定

| # | 条件 | 阈值 |
|---|---|---|
| 5 | Cost | `cost_C ≤ 1.5 × cost_A` |
| 6 | Gate effectiveness | `= 100%` 对抗用例被拦 |
| 7 | Verifier catch rate | `≥ 80%` 已知错误补丁被检出 |

### 7.3 决策

```text
GO          主判定 1–4 全部通过
CONDITIONAL 通过 3/4；修复失败项后重跑 holdout
NO-GO       主判定 1 或 3 失败
            → 停在 L2，不进入 Phase 1
```

**NO-GO 不是失败，是省下了几个月的错误投入。**

---

## 8. 目录结构

```text
evals/
├── README.md
├── DECISION.md                  # 预注册的阈值与最终结论
├── tasks/
│   ├── T-000-template.yaml
│   └── ...
├── snapshots/
│   └── repo-a/                  # 固定 commit 的只读快照
├── runners/
│   ├── manual.sh
│   ├── claude-code.sh
│   └── scripted.sh
├── scripts/
│   ├── setup_task.sh
│   ├── run_task.sh
│   ├── log_event.sh
│   ├── summarize.py
│   └── check_gates.sh
└── results/
    ├── raw/events.jsonl
    ├── per_task.csv
    └── summary.md
```

---

## 9. 已知限制

```text
1. 20–40 个任务只能给方向，不能给强统计结论
2. 人工分钟依赖计时器与操作纪律
3. hidden_checks 不是完美的逃逸代理
4. 单仓库、单写者，结论不能直接外推到多仓库
5. 评审者可能猜到 mode（AC 自动判定可缓解）
6. 成本折算依赖当前定价，需记录价格版本
```

---

## 10. 时间表

```text
第 1 周：任务集 + 快照 + 预注册 DECISION.md
第 2 周：跑 A / B 基线 + 数据采集脚本
第 3 周：跑 C + 门禁/verifier 有效性测试
第 4 周：分析 + holdout 判定 + 写结论
```

---

## 11. 预注册

在跑任何 C 之前，先把以下内容写进 `evals/DECISION.md` 并提交 git：

```text
- 任务集版本
- 指标定义与阈值
- 分析计划
- 什么情况下 GO / CONDITIONAL / NO-GO
```

跑完后只允许追加结果，不允许修改阈值。

---

## 12. 一句话

> **Phase -1 的目的不是证明 AITL 对，而是给它一个被证伪的机会。**
> 如果它连 40 个真实任务都赢不了当前 HITL，就不值得写插件。

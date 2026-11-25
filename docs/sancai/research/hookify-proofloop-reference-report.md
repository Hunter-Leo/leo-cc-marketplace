# Hookify / Proofloop 设计调研与 AITL 借鉴评估

> 调研日期：2026-11-24  
> 调研对象：  
> - Hookify `0.1.1`，commit `7b7a29e0458e3fd9417b0f46e403843b52958a83`  
> - Proofloop `3.1.1`，默认分支  
> 方法：静态阅读源码、hooks、schema、README 与测试；对关键路径做行号抽查；未执行第三方插件。  
> 结论先行：**两个插件都值得参考，但只能吸收它们的“信号”和“作者体验”，不能吸收它们的“强制模型”。**

---

## 0. 一句话结论

- **Hookify** 解决的是“人如何低摩擦地写一条策略”，强在规则作者体验，弱在强制力。
- **Proofloop** 解决的是“如何判断一次 agent 执行是否可信”，强在反自证、反橡皮图章，弱在确定性证明。
- **AITL** 的强项恰好是它们缺的：签名卡、状态机、harness-owned evidence、capability token、人工决策绑定。  
  因此正确姿势不是“照搬”，而是：**借 Hookify 的策略层，借 Proofloop 的检测器，保留 AITL 的强制层。**

---

## 1. 三者解决的问题不同

| 问题 | Hookify | Proofloop | AITL |
|---|---|---|---|
| 主要目标 | 让用户快速写 hook 规则 | 给 skill/agent 执行打分并阻断低分 | 把人类从逐动作审批转为异常审批 |
| 强制点 | PreToolUse / Stop / UserPromptSubmit | Stop / SubagentStop / StopFailure | PreToolUse + 状态机 + gate + 人工决策 |
| 核心产物 | `.claude/hookify.*.local.md` | scorecard JSON | run.json / evidence / verdict / card |
| 信任模型 | 用户写的规则可信 | 评分器可信 + 阈值 | harness 证据 + 签名卡 + 人类权威 |
| 失败时的默认 | **放行** | 评分出错时**放行**；低分才阻断 | **fail-closed** |

这个表决定了借鉴边界：Hookify 和 Proofloop 都是“辅助判断”，AITL 是“授权与责任链”。辅助判断可以借，授权链不能借。

---

## 2. Hookify：策略作者体验的范本

### 2.1 规则模型

Hookify 的规则是 Markdown + YAML frontmatter，放在 `.claude/hookify.*.local.md`。核心字段：

- `name`：规则名
- `enabled`：开关
- `event`：`bash` / `file` / `stop` / `prompt` / `all`
- `pattern`：简单正则（legacy）
- `conditions`：条件列表
- `action`：`warn` / `block`
- `message`：Markdown 正文

`conditions` 每项是 `{field, operator, pattern}`，operator 支持 `regex_match`、`contains`、`equals`、`not_contains`、`starts_with`、`ends_with`。**所有条件 AND**（`core/rule_engine.py:115-121`）。简单 `pattern` 会按 event 推断 field：bash → `command`，file → `new_text`（`core/config_loader.py:58-77`）。

一个典型规则：

```markdown
---
name: dangerous-rm
enabled: true
event: bash
pattern: rm\s+-rf
action: block
---

不要直接 rm -rf。先确认路径，或用 trash。
```

### 2.2 执行路径

`hooks/hooks.json` 注册四个事件：

- `PreToolUse` → `hooks/pretooluse.py`
- `PostToolUse` → `hooks/posttooluse.py`
- `Stop` → `hooks/stop.py`
- `UserPromptSubmit` → `hooks/userpromptsubmit.py`

PreToolUse 根据 `tool_name` 把事件映射成 `bash` 或 `file`，加载对应规则，交给 `RuleEngine.evaluate_rules`。规则引擎先收集 blocking，再收集 warning；**blocking 优先**（`core/rule_engine.py:35-90`）。输出格式按事件区分：

- Stop：`{"decision": "block", "reason": ...}`
- PreToolUse/PostToolUse：`{"hookSpecificOutput": {"permissionDecision": "deny"}}`
- 其他：只给 `systemMessage`

规则文件在每次 hook 调用时重新 glob/解析（`core/config_loader.py:209-210`），所以改文件后下一次调用即生效，等价于热加载。

### 2.3 强项

1. **作者体验极低摩擦**  
   一条 Markdown 就能加规则；不需要写 Python，不需要改 hooks.json。`/hookify` 还能从对话里分析意图并生成规则。

2. **warn / block 两态清晰**  
   warn 只给提示，block 才拒绝。这个区分比“所有规则都 hard block”更实用。

3. **窄规则、低依赖**  
   纯标准库，无外部依赖；单条规则只匹配一个事件、一个字段，容易解释。

4. **规则可读、可 diff、可 review**  
   Markdown 规则天然适合 code review 和版本管理。

### 2.4 局限

1. **fail-open 是明确设计**  
   `hooks/pretooluse.py:21-24` 在 import 失败时直接放行；`:61-62` 注释写明 “ALWAYS exit 0 - never block operations due to hook errors”。这是可用性优先，不是安全边界。

2. **regex 不是语义边界**  
   `rm -rf` 可以被 `python -c`、`bash -c`、变量拼接、MCP tool 绕过。Hookify 的规则适合“提醒/常见路径”，不适合“证明不可逆动作被拦住”。

3. **规则文件可被 agent 编辑**  
   `.claude/hookify.*.local.md` 在项目内，agent 有 Write 权限就能改规则。没有签名、没有 harness-owned 路径、没有完整性校验。

4. **无跨事件状态**  
   规则只看当前输入，不知道“这个 run 已经失败两次”“这个 diff 被批准过”。无法表达“同一动作只允许一次”这类约束。

5. **condition 语义浅**  
   没有 `diff_sha`、`claim`、`evidence`、`session_id` 等字段，无法做 AITL 需要的证据绑定。

### 2.5 AITL 可借鉴

- **声明式策略层**：`.sancai/policy/*.md`，YAML 条件 + warn/block/ask。
- **三态动作**：allow / warn / block（AITL 已有 ask，补 warn）。
- **list / explain**：让人能看到“当前哪些策略生效、为什么这条被触发”。
- **从对话生成规则**：可以做一个 `/sancai policy suggest`，但生成结果必须人审、签名后才能生效。

**不能借**：fail-open、regex 当唯一边界、agent 可编辑规则。

---

## 3. Proofloop：反自证与反橡皮图章的范本

### 3.1 执行路径

Proofloop 的 hooks 在 `Stop`、`SubagentStop`、`StopFailure` 上运行：

- `hooks/judge-on-stop.sh`
- `hooks/judge-on-subagent-stop.sh`
- `hooks/judge-on-stop-failure.sh`

流程：

1. 从 hook 输入拿 `transcript_path`。
2. 从 transcript 检测 skill/agent 名称。
3. 查 `judge-config.json.auto_judge.always/never` 决定是否评分。
4. 调 `skills/judge/scripts/score.py` 生成 scorecard。
5. 若 `composite_score < threshold` → `exit 2` 阻断 Stop。
6. 若检测到 verifier collapse → 按 `gate_mode` warn/fail/off。

`get_threshold` 默认 5.0（`hooks/common.sh:118-121`），`judge-config.json` 里也是 `"threshold": 5.0`。评分失败、缺 transcript、缺依赖时直接 `exit 0`，**不阻断**（`hooks/judge-on-stop.sh:8-30`）。

### 3.2 评分模型

`DEFAULT_WEIGHTS`（`skills/judge/scripts/score.py:28-36`）：

| 维度 | 权重 |
|---|---:|
| correctness | 0.25 |
| completeness | 0.20 |
| adherence | 0.15 |
| actionability | 0.15 |
| efficiency | 0.10 |
| safety | 0.10 |
| consistency | 0.05 |

评分是启发式 + rubric，不是执行证明。README 的定位很准确：**“no pass without proof”**，但它自己也承认这是 judge，不是 verifier。

### 3.3 最值得看的三个检测

#### 3.3.1 `detect_unverified_success`

位置：`skills/judge/scripts/score.py:624-668`。

逻辑：

- 在 transcript 里找“tests pass / build succeeded / done”这类成功声明；
- 排除“请求别人去跑测试”的句子（`_US_REQUEST`）；
- 如果整段 transcript 里**没有任何执行回执**（`_US_RECEIPT`），就给每条 claim 生成 finding；
- correctness 扣 2 分（可配置 `correctness_dock`）；
- 如果没有回执但 correctness 仍想给 10 分，**强制封顶 9 分**（`:727-730`）。

这是“claim vs receipt”的廉价实现：没有嵌入、没有 LLM，纯正则。它的价值不在精度，而在**把“自称完成”变成一个可被 gate 消费的 finding**。

#### 3.3.2 `_detect_verifier_collapse`

位置：`skills/judge/scripts/score.py:1371-1478`。

默认参数（`:1411-1413`）：

```python
window = 10
min_samples = 5
top_threshold = 8.5
top_bucket_fraction = 0.95
max_std_dev = 0.3
```

判定：最近窗口内 ≥95% 的分数都在 8.5 以上，且标准差 <0.3 → verifier collapse。  
这是“评分器自己橡皮图章化”的检测，和“分数低”是两件事。Proofloop 把它单独做成信号，并支持 `gate_mode: warn|fail|off`（`hooks/judge-on-stop.sh:59-77`）。

#### 3.3.3 schema version 与 benchmark

- `schemas/scorecard.v1.schema.json:9,32` 强制 `schemaVersion`。
- `score.py:2169-2193` 在每张 scorecard 顶部注入 `$schema` 和 `schemaVersion`。
- `benchmarks/` 有 clean/failing/hallucination/placeholder/retries 等 corpus；`scripts/bench_lint.py` 做回归。

这让评分器本身可回归，而不是“改完 prompt 凭感觉”。

### 3.4 强项

1. **明确反自证**：claim 无 receipt 会被抓出来，且封顶 9 分。
2. **明确反橡皮图章**：verifier collapse 是独立信号，不靠“分数低”。
3. **schema 化**：scorecard 有版本，能迁移、能校验、能回归。
4. **可配置 rubric**：权重、阈值、allowlist、per-model baseline 都可调。
5. **读侧只读**：`agents/judge-agent.md` 明确 read-only，Bash 只允许 `ls/cat/head/tail/wc/find/grep/diff/stat/file`。

### 3.5 局限

1. **启发式，不是证明**  
   claim/receipt 都是正则；多语言、转述、工具输出格式变化都会影响精度。它能抓“明显没跑测试还说 pass”，不能证明“测试真的覆盖了 AC”。

2. **transcript-only**  
   看不到 diff、看不到 harness 侧 exit code、看不到文件真实状态。AITL 的 evidence 比它硬。

3. **评分可被游戏**  
   只要输出“看起来像测试回执”的文本，就可能骗过 receipt 检测。它不是安全边界。

4. **fail-open**  
   评分失败、缺 transcript、缺依赖都放行；只有低分/collapse fail 模式才阻断。适合质量提示，不适合安全 gate。

5. **阈值阻断的噪声**  
   5.0 阈值 + 启发式评分，容易误伤；Proofloop 自己用 `gate_mode` 和 allowlist 缓解，但本质仍是 advisory。

### 3.6 AITL 可借鉴

- **claim-vs-receipt**：放到 G3，作为 `claim_without_receipt` finding。
- **verifier-collapse**：放到 `sancai_graph` 指标 + gate warning/rotation。
- **schema_version**：verdict/evidence/graph 全部加版本。
- **benchmark corpus**：用真实 run 做 verifier 回归，而不是只靠单元测试。
- **read-only judge prompt**：借它的只读约束和“先找反证”的评分习惯。

**不能借**：分数当 gate、transcript-only、fail-open、regex 当证明。

---

## 4. 对照矩阵

| 维度 | Hookify | Proofloop | AITL |
|---|---|---|---|
| 强制点 | PreToolUse/Stop | Stop/SubagentStop | PreToolUse + 状态机 + gate |
| 策略作者 | 用户，Markdown | 配置/权重 | 代码 + 人工 intent |
| 证据 | 当前输入 | transcript | harness evidence + diff_sha |
| 人类权威 | 规则作者 | 评分阈值 | 签名卡 + 原生 Allow |
| 反自证 | 无 | claim-vs-receipt | 已有 evidence，但缺 claim 检查 |
| 反橡皮图章 | 无 | verifier collapse | 有独立性检查，缺趋势指标 |
| schema 版本 | 无 | 有 | 无 |
| 失败默认 | 放行 | 放行 | fail-closed |
| 复杂度 | 低 | 中高 | 高 |

AITL 不应该变成 Proofloop 那样的“打分器”，也不应该变成 Hookify 那样的“规则集合”。它应该保持“授权/责任链”，只把两者作为**信号源**接进来。

---

## 5. 建议的 AITL 落地设计

### 5.1 P1：claim-vs-receipt（最高优先级）

**问题**：AITL 的 evidence 是 harness 捕获的，但 executor 仍可以在最终总结里写“tests pass / done”，而 verifier 可能只读 summary，不核对 claim 与 evidence。

**位置**：

- `plugins/sancai-loop-plugin/scripts/sancai_gate.py`：G3 前检查。
- `plugins/sancai-loop-plugin/scripts/sancai_verdict.py`：把 claim finding 写进 verdict。
- `plugins/sancai-loop-plugin/scripts/sancai_state.py`：accept 时拒绝未处理的 major claim finding。

**数据**：

- executor 的最终输出/`progress` 事件；
- evidence 里的 `commands[]`（command、exit_code、output 摘要）；
- AC 列表。

**算法**：

```text
claims = extract_success_claims(executor_final_output + progress_events)
receipts = evidence.commands where exit_code == 0
           and command matches (test|pytest|unittest|build|lint|typecheck|validate)

for claim in claims:
    if claim.kind in {tests_pass, build_ok, lint_ok, done}:
        if not any(receipt covers claim.scope):
            findings.append(
                id="CLAIM-<n>",
                severity="major",
                evidence=claim.text,
                fix="run the check and attach its receipt, or remove the claim"
            )
```

**Gate 规则**：

- verdict 为 `pass` 但存在 `CLAIM-*` major → `changes_requested`。
- accept 时存在未处理的 `CLAIM-*` major → 拒绝。
- minor/info 的 claim finding 可以 `--ack-findings`。

**注意**：

- 只检查**最终总结**和**显式 progress**，不检查中间思考，避免“我接下来要跑测试”被误判。
- 支持中英文 claim 词表，但把词表放在配置里，不硬编码。
- 这条检查是“反自证信号”，不是“正确性证明”；不要把它升级成唯一 gate。

**验收**：

- executor 说 “all tests pass” 但没有 test 命令 → gate `changes_requested`。
- executor 说 “all tests pass” 且有 `pytest` exit 0 → 不产生 finding。
- executor 引用计划中的 “will run tests” → 不误报。

### 5.2 P1：verifier-collapse

**问题**：AITL 现在只检查“verifier 是否独立”，不检查“verifier 是否长期橡皮图章化”。一个独立但永远 pass 的 verifier 仍然会漏。

**位置**：

- `plugins/sancai-loop-plugin/scripts/sancai_graph.py`：加 `verifier_stats`。
- `plugins/sancai-loop-plugin/scripts/sancai_gate.py`：读指标，warning 或要求换 verifier。

**数据**：

- 最近 N 个 verdict 的 `result`、`findings` 数量/严重度；
- 可选：verdict 增加 `confidence`（0–10）。

**算法（无 confidence 版）**：

```text
last = verdicts[-10:]
if len(last) >= 5:
    pass_rate = count(result == "pass") / len(last)
    zero_finding_rate = count(len(findings) == 0) / len(last)
    if pass_rate >= 0.95 and zero_finding_rate >= 0.95:
        flag("verifier_collapse_suspected")
```

**算法（有 confidence 版）**：

```text
if len(last) >= 5:
    top = count(confidence >= 8.5) / len(last)
    std = stddev(confidence)
    if top >= 0.95 and std < 0.3:
        flag("verifier_collapse")
```

**建议**：AITL verdict 目前只有 pass/fail，直接套 Proofloop 的 0–10 分不合适。先做“无 confidence 版”，只作为 **warning**，不阻断；等真实 run 多了再决定是否升级为 gate。

**验收**：

- 连续 5 个 pass、0 findings → `verifier_collapse_suspected`。
- 连续 5 个 pass 但其中有 finding → 不触发。
- 指标只影响 warning/rotation，不单独判 fail。

### 5.3 P1：schema_version

**问题**：AITL 的 evidence/verdict/graph 没有版本，后续改字段会破坏旧 run。

**改动**：

- `evidence.schema_version = "aitl.evidence.v1"`
- `verdict.schema_version = "aitl.verdict.v1"`
- `graph.schema_version = "aitl.graph.v1"`

**规则**：

- 读取时校验 major 版本；未知 major → 拒绝并提示迁移。
- 新增字段只升 minor；删除/改语义升 major。
- `sancai_graph` 输出里带版本，便于 eval 对比。

**验收**：

- 旧 evidence（无版本）按 v1 兼容读取。
- 未知 `v2` → 明确错误，不静默忽略。

### 5.4 P2：声明式 policy overlay

**目标**：让项目能加自己的策略，而不改 `sancai_capability.py`。

**形式**：`.sancai/policy/*.md`，YAML frontmatter + Markdown 说明。

```markdown
---
id: no-prod-db
enabled: true
event: bash
match:
  command_regex: "psql .*prod"
action: block
tier: T2
message: 生产数据库写入必须走人工批准。
---
```

**动作**：`allow` / `warn` / `block` / `ask`。

**信任模型**：

- policy 文件只能由人创建/修改；agent 的 Write/Edit 到 `.sancai/policy/` 被 capability 拒绝。
- `POLICY.sig` 用 `SANCAI_SECRET` 做 HMAC；加载时校验；签名失败 → fail-closed。
- policy 只能**收紧**内置策略，不能放宽；`allow` 不能覆盖内置 deny。
- 解析失败 → 拒绝整个 policy 集，不静默跳过。

**与 capability 表的关系**：

```text
内置 capability 表 = 底线，永远生效
policy overlay     = 项目级加严
人工 card          = 单次例外
```

**验收**：

- 未签名 policy → 拒绝加载。
- policy 写 `allow` 覆盖内置 deny → 拒绝。
- 规则语法错误 → fail-closed，并给出文件/行号。
- `/sancai policy list` 能看到生效规则；`/sancai policy explain <id>` 能解释命中原因。

### 5.5 P3：benchmark corpus 与 verifier 回归

**目标**：用真实 run 检验 verifier 是否真的能抓错，而不是只看“它说 pass”。

**做法**：

- 从 `evals/` 和真实 run 收集：已知好补丁、已知坏补丁（缺测试、假 claim、越权、静默 findings）。
- 每个 case 标注 expected verdict/finding。
- 跑 verifier，计算 catch rate、false positive rate、collapse 指标。
- 把结果写进 `evals/` 的回归报告。

**验收**：

- verifier catch rate ≥80%（Phase -1 已有阈值）。
- 新 verifier prompt 不使 catch rate 下降超过 5pp。
- claim-vs-receipt 在坏补丁集上至少抓到 1 条。

### 5.6 明确不采纳

| 做法 | 原因 |
|---|---|
| Hookify 的 fail-open | AITL 的安全门必须 fail-closed |
| regex 当唯一边界 | 已有 argv 解析；regex 只做补充 |
| Proofloop 的分数当 gate | 分数是启发式，不是证明 |
| transcript-only 证据 | AITL 有 harness evidence/diff_sha |
| agent 可编辑 policy | 必须签名 + harness-owned |
| Stop hook 无证据阻断 | 会变成新的“模型自证” |

---

## 6. 风险与开放问题

1. **claim 检测的误报**  
   中英文、转述、Markdown 引用、计划句都可能误判。建议只检查最终总结 + 显式 progress，并允许 `--ack-findings` 处理 minor。

2. **verifier confidence 校准**  
   如果加 0–10 confidence，模型会倾向于给高分。先用无 confidence 版，避免引入新的橡皮图章维度。

3. **policy 签名密钥管理**  
   `SANCAI_SECRET` 不能放在 repo；需要 keychain/secret manager。签名失败必须 fail-closed，否则 policy 层等于没有。

4. **复杂度**  
   AITL 已经有状态机、卡、证据、capability；再加 policy overlay 会增加理解成本。P2 应等 P1 稳定后再做。

5. **插件可移植性**  
   Hookify 纯标准库、无依赖；AITL 也应保持“Python 标准库 + 无外部服务”，否则安装门槛会上升。

6. **评测缺口**  
   目前 61 个单元测试覆盖机制，但没有真实任务的 catch rate。P1 的 claim 检查必须配 benchmark，否则只是“看起来更严”。

---

## 7. 路线图与验收

| 阶段 | 内容 | 预估 | 风险 | 验收 |
|---|---|---|---|---|
| P1-a | claim-vs-receipt | 0.5–1 天 | 误报 | 3 个正/负例测试 + gate 行为 |
| P1-b | verifier-collapse 指标 | 0.5 天 | 样本不足 | 5 个连续 pass 触发 warning |
| P1-c | schema_version | 0.5 天 | 迁移 | 旧 v1 兼容，未知 major 拒绝 |
| P2 | policy overlay + 签名 | 3–5 天 | 密钥/复杂度 | 未签名拒绝、allow 不能放宽 |
| P3 | benchmark corpus | 1–2 周 | 数据量 | catch rate ≥80%，回归不降 5pp |

**建议顺序**：P1-a → P1-b → P1-c → 用真实 run 验证 → 再决定 P2/P3。  
不要一次把三个都做成“默认阻断”；先做 **warning/ finding**，有数据后再升级 gate。

---

## 8. 参考

### Hookify

- 仓库：https://github.com/anthropics/claude-plugins-official/tree/7b7a29e0458e3fd9417b0f46e403843b52958a83/plugins/hookify
- 版本：`0.1.1`
- 关键文件：
  - `hooks/hooks.json`
  - `hooks/pretooluse.py:21-24,61-62`（fail-open）
  - `core/rule_engine.py:35-90,115-121`（block 优先、AND 条件）
  - `core/config_loader.py:39-80,209-210`（规则模型、glob）
  - `README.md:120`（all conditions must match）

### Proofloop

- 仓库：https://github.com/sattyamjjain/proofloop
- 版本：`3.1.1`
- 关键文件：
  - `hooks/judge-on-stop.sh:8-30,41-53,59-77`（fail-open、阈值、collapse gate）
  - `hooks/common.sh:118-121`（默认阈值 5.0）
  - `skills/judge/scripts/score.py:28-36`（权重）
  - `skills/judge/scripts/score.py:624-668,708-730`（unverified success、封顶 9）
  - `skills/judge/scripts/score.py:1371-1478`（verifier collapse）
  - `schemas/scorecard.v1.schema.json:9,32`（schemaVersion）
  - `agents/judge-agent.md:5,9,16,167`（read-only judge）
  - `README.md:46,468-469`（no pass without proof、collapse 阈值）

### AITL 当前实现

- `plugins/sancai-loop-plugin/scripts/sancai_gate.py`（G0/G3、verifier 独立性）
- `plugins/sancai-loop-plugin/scripts/sancai_graph.py`（过程图、metrics）
- `plugins/sancai-loop-plugin/scripts/sancai_verdict.py`（verdict、findings）
- `plugins/sancai-loop-plugin/scripts/sancai_cards.py`（卡绑定、dwell、findings_hash）
- `plugins/sancai-loop-plugin/scripts/sancai_capability.py`（capability、human decision guard）
- `docs/sancai/design/loop-design.md` §20（防呆与人类侧设计）
- `docs/leo-team/design/human-side-foolproofing-design.md`（T0–T4、审批强度）

# N0 Precheck — 前置门

> 目标：在花费任何团队成本之前，判定「是否该组队」并初始化运行状态。本阶段不建 git 分支、不写业务代码、不 spawn teammate。
> 前置：已读 `references/essence.md`、`references/rails.md`。

## 步骤

1. **分配需求编号**：扫描 `.dev/` 下匹配 `[0-9]{3}-*` 的目录，取最大编号 +1，三位补零；`.dev/` 不存在则创建。目录名 `<NNN>-<req>` 同时作为 run 名称。
2. **建目录**：`.dev/<NNN>-<req>/generated/`。
3. **检测 Agent Teams**：`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 且当前为交互式终端 Claude Code。不满足 → 走「话术 3：Agent Teams 未启用」，等待用户三选一，不得直接换模式。
4. **Task Sizing**：按下方表格定级，取命中的最高档。
5. **四触发条件判定**：逐条给出 `true/false` 与证据。
6. **science_gate 询问**：按 A/B/C/D 四选项问用户，默认 A（全关）。
7. **写 `generated/init.md`**：把结果写入 `## N0 前置判定`（格式见下）。
8. **分流**：
   - XS/S → 停止并退回单人模式，不创建 `flow.json`。
   - M/L 且 `T1 && (T2 || T3 || T4)` → 执行 `bash "$CLAUDE_PLUGIN_ROOT/scripts/flow.sh" init --run "<NNN>-<req>"`，再执行 `flow.sh set --science-gate-researcher <true|false> --science-gate-auditor <true|false>`。

## Task Sizing

| 级别 | 判定（任一命中即取最高档） | 去向 |
|---|---|---|
| XS | ≤1 个文件 且 ≤30 行 且 单一行为 | 退回单人 |
| S | 2–5 个文件 或 ≤150 行；不跨模块接口 | 退回单人 |
| M | 6–20 个文件 或 151–800 行 或 跨 2–3 个模块 | 进入团队 |
| L | >20 个文件 或 >800 行 或 跨 ≥4 个模块/仓库 | 进入团队；N3 可分波次 |

计行以「净新增 + 净修改」估算，不统计生成文件与锁文件。

## 四触发条件

| 编号 | 条件 | 判定为 true 的证据 |
|---|---|---|
| T1 | 规模达到 M/L | Task Sizing 结果为 M 或 L |
| T2 | 存在并行收益 | `init.md` 中列出 ≥2 个初步工作单元及其 `owned_files` 草案，且两两不相交 |
| T3 | 需要独立验证上下文 | 验收依赖以下任一：外部事实审查、跨模块接口评审、双轴评审 |
| T4 | 用户明示团队 | 用户原话包含「组队 / 多 agent / team / agent teams / 并行开发」之一 |

**进入条件（写死）**：`T1 && (T2 || T3 || T4)`。任一不满足 → 不进入团队流程。

## science_gate 四选项

用 `AskUserQuestion` 提一个问题（不可用时用等价内联四选项），只问一次：

> 本需求是否涉及科学算法、公式、数值结论、语料/基准数据，或需要对用户声称效果（如「提升 X%」）？

| 选项 | researcher | auditor | 适用 | 写入 `flow.json` |
|---|---|---|---|---|
| A（默认） | false | false | 常规工程需求，无外部事实断言 | `{"researcher":false,"auditor":false}` |
| B | true | false | 需要文献结论或语料，实现结果不需科学核查 | `{"researcher":true,"auditor":false}` |
| C | false | true | 有外部科学共识可对照，但不需要专门调研 | `{"researcher":false,"auditor":true}` |
| D | true | true | 科学计算、算法实现、论文复现、指标声称 | `{"researcher":true,"auditor":true}` |

- 默认 A 是刻意的：常规需求不为科学通道支付成本。
- N1 期间用户改变选项 → PM 更新 `flow.json` 布尔值并写入 `decisions.md`；N2 以最新值为准。
- 运行中关闭或降级 → 必须写 `decisions.md` 并取得用户显式 `confirmed`。

## 输出格式（写入 `generated/init.md`）

```markdown
## N0 前置判定

- 需求目录: .dev/[NNN]-[req]
- run: [NNN]-[req]
- Agent Teams: 可用
- Task Sizing: M（8 个文件 / 2 个模块 / 约 400 行）
- T1: true — M 级
- T2: true — 初步单元 U-01/U-02/U-03 的写集两两不相交
- 初步单元: U-01(src/a.ts, tests/a.test.ts); U-02(src/b.ts, tests/b.test.ts); U-03(src/c.ts, tests/c.test.ts)
- T3: false
- T4: false
- 判定: 进入团队流程
- science_gate: A
- science_gate.researcher: false
- science_gate.auditor: false
- 判定时间: YYYY-MM-DD
```

## 退回单人模式

退回必须是显式动作：说明级别与触发结果 → 给出替代 → 询问是否切换。禁止静默切换。

### 话术 1：XS/S 或 T1 不成立

```
这次需求按 N0 判定属于 [XS/S]（[文件数] 个文件 / [模块数] 个模块 / 约 [行数] 行），
未达到 M 级门槛，团队编排成本会高于收益。建议改用 spec-coding-skill 单人模式：
Phase A→B 门禁、偏差记录、轮次评审和验收标准保持一致。要我现在切换吗？
```

若 `spec-coding-skill` 未安装（只装了本插件），改为：

```
当前只安装了 leo-team-plugin，单人模式技能不可用。两个选择：
[A] 安装 leo-dev-plugin 后使用 spec-coding-skill（/plugin install leo-dev-plugin@leo-cc-marketplace）
[B] 我直接按同样纪律执行：先写计划等你确认，再实现、测试、提交
```

### 话术 2：T1 成立但 T2/T3/T4 全不成立

```
这次需求规模是 [M/L]，但未发现并行收益、独立验证需求或团队意愿，
单 agent 可以连续完成，组队只会增加 3–10× token。建议改用 spec-coding-skill。
要我现在切换吗？
```

### 话术 3：Agent Teams 未启用（按 `references/degradation.md`）

```
检测到 Agent Teams 未启用，以下能力不可用：
- teammate 之间无法直接通信（无 mailbox）
- 无 SendMessage / TaskCreate 等协作工具
- teammate 上下文不持久，每个工作单元都要重新初始化
共享文件纪律、状态机、hooks、验收流程仍然有效。

请选择：
[A] 开启 Agent Teams 并重启会话（推荐，settings.json 加
    "env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}）
[B] 用 subagent 顺序执行（更省 token，无并行，每单元重建上下文）
[C] 退回单人模式 spec-coding-skill
```

用户选 B 时：仍按 N0→N6 推进，但 N3 取消只读重叠，全部串行，回传落 `.team/<run>/verdicts/<unit>.json`，并写入 `decisions.md`。用户选 C 时本技能立即终止。

### 用户坚持在 XS/S 上组队

记 `decisions.md`：

```markdown
## D-<NNN> 用户覆盖 N0 分级

- trigger: user_override
- decision: 用户在 [XS/S] 需求上要求组队
- context: N0 判定为 [XS/S]，已告知 3–10× token 成本
- approved_by: user
```

按最小团队执行：`spec-executor` + `spec-reviewer`，科学通道全关，N3 规模写 `2`。

## 完成标志

- `generated/init.md` 含 `## N0 前置判定`，所有字段非空。
- `.team/<req>/flow.json` 存在，`mission=planning`，`branch` 非空，`science_gate` 布尔值与用户选项一致。
- 退回单人时：不创建 `flow.json`、不建分支、不 spawn。

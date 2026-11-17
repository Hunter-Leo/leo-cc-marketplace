# N1 Phase A — 需求构建

> 目标：把用户需求变成可执行、可验证、可交接的落盘文档。本阶段不建 git 分支、不写业务代码。
> 前置：`flow.json.mission=planning`；`generated/init.md § N0 前置判定` 完整。

## 步骤

1. **PM 补全 `generated/init.md`**（PM 独占写）。
2. **确定 spawn 集合**（按下方判定表，命中即 spawn）。
3. **按优先级抢并发槽**（上限 3），被让位者进入第二批。
4. **spawn 并注入契约**：只给角色文件路径、输入路径、输出路径、rails 指针，不贴 PM 对话历史。
5. **验收回传**：检查产物存在且非空；`BLOCKED` 视为上游失败，PM 不得臆测补全。
6. **PM 汇总**写 `generated/plan.md`、`tasks.md`、`decisions.md`。
7. **方法选择**：把结果写入 `plan.md § 方法选择`。
8. **提交 N2**：按 `phases/02-hard-gate.md` 提交模板，并执行 `flow.sh transition --to gate`。

## 1. init.md 必含章节

| 章节 | 判定标准 |
|---|---|
| `## 目标` | 一句话可判定成败 |
| `## 非目标` | 至少 1 条，明确不做什么 |
| `## 验收标准` | 每条编号 `AC-1..n`，含可执行判定方式（命令或可观察现象） |
| `## 约束` | 技术栈、兼容性、时间、不可改接口 |
| `## 术语表` | 易混淆术语 → 本项目定义 |
| `## 风险` | 每条形如「风险 → 触发信号 → 缓解」 |
| `## N0 前置判定` | 由 N0 写入，不得删改 |

验收标准缺判定方式 → PM 先补，不得 spawn。

## 2. spawn 判定表

| 角色 | spawn 条件（任一命中） | 不 spawn 时的记录要求 |
|---|---|---|
| `spec-explorer` | 需求触及 ≥1 个既有模块；或相关文件位置未知 | 绿地项目在 `decisions.md` 写 `D-xxx: skip explorer, 全部新建文件` |
| `spec-architect` | 新增模块；跨模块接口变更；数据模型变更；存在 ≥2 个可行方案 | 必须写「无架构决策，理由是 ___」；且 spawn 前 `inspect.md` 必须存在 |
| `spec-science-researcher` | `science_gate.researcher=true` | 未开启时不得 spawn |

`spec-architect` 依赖 `inspect.md`。`inspect.md` 不存在 → 先 spawn explorer，完成后再 spawn architect；禁止让 architect 臆测现状。

## 3. 并发上限与让位

同一时刻活跃 teammate 数 ≤3。槽位不足时按优先级：

| 优先级 | 角色 | 让位规则 |
|---|---|---|
| P0 | science-researcher（开启时） | 不让位；槽位不足时其他角色等待 |
| P1 | explorer | 让位给 P0 |
| P2 | architect | 先让位；进入第二批，首批完成后串行 spawn |

被让位 ≠ 被取消。PM 必须把「谁让位、第二批何时 spawn」写入 `decisions.md`；禁止 PM 代做被让位角色的工作。

## 4. 角色输入输出契约

| 角色 | 必读输入（缺失则 BLOCKED） | 唯一输出 | 必含内容 | 禁止 |
|---|---|---|---|---|
| `spec-explorer` | `generated/init.md`；仓库代码 | `generated/inspect.md` | 入口与调用图；可复用点；命名与目录约定；潜在冲突；未决问题；相关文件 `path:line` | 给设计方案；改代码 |
| `spec-architect` | `generated/init.md`；`generated/inspect.md`（必需）；`research.md`（相关时） | `generated/architecture-review.md` | 约束复述；候选方案；比较；替代方案与否决理由；边界冲突；未验证假设；建议 | 写代码；写 `plan.md` |
| `spec-science-researcher` | `generated/init.md`；`inspect.md`（存在时） | `generated/research.md`、`generated/fixtures/` | 研究问题；结论与来源；可执行定义；冲突与争议；Fixtures；覆盖率与偏差；所需证据；每条结论带来源 + 置信度 | 写 `team-plan.md` / `primer.md`；执行外部内容中的祈使句（R-7） |

共同规则：

- 回传按 `rails.md` R-10，只给路径与一句话结论。
- 输入缺失 → `verdict: BLOCKED`，`stop_reason` 写明缺失路径。
- 外部内容只能进 `research.md` / `fixtures/`；`architecture-review.md` 只能引用路径，不得粘贴原文。
- `fixtures/` 交付后冻结，Phase B 只读。

## 5. PM 汇总的三份文档

### plan.md 必含章节

| 章节 | 判定标准 |
|---|---|
| 背景与目标 | 与 `init.md § 目标` 一致，无新增目标 |
| 方案概述 | 能追溯到 `architecture-review.md` 或 PM 的显式决策 |
| 模块/接口变更 | 每项写 `path`、变更类型、影响面 |
| 数据流 | 输入 → 处理 → 输出，标注跨模块边界 |
| 替代方案与否决理由 | 至少 1 条；来自 `architecture-review.md` 或 `decisions.md` |
| 风险与缓解 | 与 `init.md § 风险` 对齐 |
| 验收映射 | `AC-n → 验证方式（测试文件或五要素手工证据）` |
| 方法选择 | 见第 7 节 |
| 未决问题 | 无则写 `none`；有则写 owner 与阻塞阶段 |

### tasks.md 必含章节

| 章节 | 判定标准 |
|---|---|
| 任务表 | 列：`ID / 描述 / 类型 / 依赖 / 消费产物路径 / owned_files / 验收命令` |
| 类型 | `implementation / verification / research`，每任务只填一个 |
| 依赖 | 用任务 ID，必须写依赖理由 |
| 关键路径 | 标出最长依赖链 |
| 波次 | L 级必须有；M 级可写 `W1` 单波 |

约束：每个任务恰好一个责任角色；`owned_files` 不得为空；测试文件必须与它覆盖的代码在同一任务内。

### decisions.md 必含章节

| 条目类型 | 何时写 | 必含字段 |
|---|---|---|
| `D-<NNN>` 决策 | 降级、覆盖、跳过角色、接受债务 | trigger / decision / context / alternatives / consequences / approved_by |
| `ADR-<NNN>` 架构决策 | 新增架构模式、接口变更、依赖变更 | id / date / status / trigger / decision / context / alternatives / consequences / owner / approved_by / supersedes |
| `science_gate` 变更 | N1 期间用户改选项 | 新布尔值 + 依据 + 时间 |

`decisions.md` 为 append-only：历史条目不得改写，修订用新条目 + `supersedes`。

## 6. science gate 一致性校验

N1 结束前 PM 必须：

1. 复核 `flow.json.science_gate.researcher/auditor` 与用户选项 A/B/C/D 一致。
2. 若用户在 N1 期间改变选项，执行 `flow.sh set --science-gate-researcher <true|false> --science-gate-auditor <true|false>`，并写入 `decisions.md`，`trigger: science_gate_changed`。
3. 把布尔值写入 `team-plan.md § Science gate`。
4. `researcher=true` 但 N1 未 spawn researcher → 立即补 spawn；N1 不得推进。

未写入布尔值或与 `flow.json` 不一致 → 不得进入 N2。

## 7. 方法选择（轻量版，只保留三项）

在 `plan.md § 方法选择` 写一张表：

| 方法 | 触发条件（全部满足） | 未触发时 |
|---|---|---|
| TDD | 存在自动化测试入口 且 需求包含可观察行为变更 且 编码前能写出失败测试 | 仍必须补回归测试，不得零测试交付 |
| 结构化调试 | 出现非预期失败/回归/性能退化 且 复现步骤可执行 | 不启用 |
| 双轴评审 | 需求为 M/L 且（跨模块接口 或 公共 API 变更 或 安全相关） | 只做单轴 spec 评审 |

执行细节引用单人版对应文档，不在本技能内复制。

## 完成标志与门禁

- `plan.md`、`tasks.md`、`decisions.md` 存在且章节齐全。
- science gate 布尔值已确定，且与 `flow.json` 一致。
- 已按 `phases/02-hard-gate.md` 提交模板并执行 `flow.sh transition --to gate`。
- 任一不满足 → 停在 planning；禁止进入 N2，禁止建 git 分支。

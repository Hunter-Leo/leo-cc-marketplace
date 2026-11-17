# N3 Formation — 组队与工作单元切分

> 目标：把 `tasks.md` 变成可机械调度的 `generated/team-plan.md`：每个单元有唯一 owner、唯一写集合、唯一验收命令。
> 前置：`flow.json.mission=gate`；分支已创建；`primer.md` 已写。
> 本阶段只写 `team-plan.md` 与 `.team/<run>/prompts/`；不 spawn executor，不写业务代码。

## Step 1 — 读 tasks.md 并统计任务类型

逐行读 `tasks.md § 任务表`，按类型计数：

| `tasks.md` 类型 | 含义 | 归属 |
|---|---|---|
| `implementation` | 生产代码变更；`owned_files` 必须包含其测试文件 | executor |
| `verification` | 独立评审、验收证据收集；**不写单元测试** | reviewer |
| `research` | 外部事实调研；N1 未完成时在此补做 | science-researcher |

统计并写入 `team-plan.md § 统计`：

```markdown
- implementation: <n> 个任务 / <m> 个文件
- verification: <n> 个任务
- research: <n> 个任务
- 涉及模块: <列表>
- 共享文件: <index/router/types/config/schema/migration 等>
```

**硬规则**：单元测试与集成测试的编写属于 `implementation`，必须留在 executor 单元内。禁止把测试剥离成独立角色或独立单元。

## Step 2 — 按 owned_files 切实现工作单元

单元定义：一个 executor 在一次 `claim` 中完成的写集合 + 验收命令。ID 用 `U-01..U-nn`。
`flow.json.units` **只登记实现单元**；reviewer / science-auditor 的验证任务见 Step 2b。

### 切分规则（全部为硬规则）

1. 每个单元 `owned_files` 非空，且列出**精确路径**；新增文件必须写全路径，禁止用宽 glob 覆盖未定文件。
2. 一个实现单元文件数 ≤5，净变更 ≤200 行；超出则拆分。
3. 拆分时必须把测试文件与它覆盖的代码放在同一单元。
4. 共享可变文件（`index.*`、`router.*`、`types.*`、全局 config、schema、migration）**只能有一个 owner**；其他单元通过接口消费，不得共同编辑。
5. 每个实现单元的 owner 必须是 executor；测试不得剥离成独立单元或独立角色。
6. 每个单元必须有 `acceptance`：一条可直接执行的命令。
7. 单元 ID 一经确认不得复用或重排。

| ID | Owner | Archetype | owned_files | depends_on | acceptance |
|---|---|---|---|---|---|
| U-01 | spec-executor | Builder | `src/a.ts`, `tests/a.test.ts` | none | `npm test -- a` |
| U-02 | spec-executor | Builder | `src/b.ts`, `tests/b.test.ts` | U-01 | `npm test -- b` |

## Step 2b — 验证安排（不进入 flow.units）

reviewer / auditor 的工作是阶段职责，不登记为实现单元：

| ID | Owner | 产物 | depends_on | acceptance |
|---|---|---|---|---|
| V-01 | spec-reviewer | `generated/findings.md` 的 `## Round N — spec-reviewer — <unit-id>` 段 | 所有 `for_review` 单元 | 每单元一段，含 verdict + 证据 |
| V-02 | spec-science-auditor | `generated/science-audit.md` | 可审计产物完成 | Verdict 行存在 |

## Step 3 — 校验写文件集合两两不相交

对单元表中每一对 `(Ui, Uj)` 执行：

1. 展开 `owned_files`：既有文件用 `git ls-files` 验证存在；新增文件按字面路径比较。
2. 计算交集。**交集为空 → 通过。**
3. 交集非空 → 按顺序尝试：
   - **合并**：两个单元合成一个，保留一个 owner；若文件数 >5 或行数 >200，转 4。
   - **归属唯一化**：把共享文件判给其中一个单元，另一个单元从 `owned_files` 移除并改为 `depends_on`。
   - **串行化**：仍无法消除时，两单元保持原样但标记 `execution: serial`，且不得同时 `claimed`。
4. 串行化后仍存在「必须由两个角色同时编辑同一文件」→ 标记 `risk: high`，写入 `team-plan.md § 高风险`，并在 Step 6 向用户明示。
5. **机械复核**：单元登记完成后运行 `bash "$CLAUDE_PLUGIN_ROOT/scripts/check-lanes.sh"`。
   - exit 0（OK/WARN）→ 通过；WARN 需逐条人工确认并写进 `team-plan.md § 调度判定`。
   - exit 1（存在确定相交）→ 必须回到第 3 步重切，不得进入 Step 6。

禁止事项：

- 禁止用「不同功能」为理由让两个单元共写一个文件。
- 禁止把共享文件复制成两份再各自修改。
- 禁止在未记录的情况下把相交单元改成并行。

### 调度事实

`flow.sh` 只有一个全局 claim：同一时刻只允许一个写操作。`owned_files` 不相交是**允许调度**的条件，不是「同时写」的许可。并行收益来自：只读分析与实现重叠、验证角色与下一单元重叠；写操作按 claim 串行。

## Step 4 — 选角色（默认 2–3，上限 4）

### 选人判定表

| 任务构成 | 必选 | 可选（N1 未覆盖时） | 规模 |
|---|---|---|---|
| 纯代码实现 | spec-executor ×1 + spec-reviewer ×1 | spec-explorer | 2–3 |
| 代码 + 陌生模块 | spec-executor + spec-reviewer | spec-explorer | 3 |
| 代码 + 接口/架构不确定 | spec-executor + spec-reviewer | spec-architect（需 `inspect.md`） | 3 |
| 代码 + `auditor=true` | + spec-science-auditor | — | 3 |

`science_gate.researcher` 只影响 N1，不在 N4 重复 spawn；全流程角色数（N1 researcher + N4 角色）上限 4。

### 角色约束（写死）

- executor 最多 1 个实例；同一角色同一时刻不得并行，多个代码单元由同一 executor 串行处理。
- reviewer 至少 1 个；`science_gate.auditor=true` 时 science-auditor 至少 1 个且不可替代。
- `science_gate.researcher=true` 时 researcher 至少 1 个。
- 每个被选角色必须有 ≥1 个任务（实现单元或验证安排）；没有任务的闲置角色必须删除。
- 角色数上限 4（含 auditor）。超过 4 → 砍 architect，再砍 explorer；不得砍 auditor。
- 两个开关全 false 时禁止 spawn researcher / auditor。
- `auditor=true` 且 `researcher=false` 时，`science-audit.md` 必须引用项目内既有依据；否则 auditor 会因 `research.md` 缺失 `BLOCKED`。PM 需在 `decisions.md` 记录依据路径，或改用 D。

## Step 5 — 写 team-plan.md

### 全局必含章节

| 章节 | 必含内容 |
|---|---|
| `## Run` | run_id / round / branch / base_ref / phase_a_confirmed / 时间 |
| `## Science gate` | researcher / auditor 布尔值、owner、产物、状态 |
| `## 统计` | Step 1 的统计结果 |
| `## 团队` | 角色、实例数、archetype、存活阶段 |
| `## 单元表` | Step 2 的实现单元表；验证安排单独成表 |
| `## 验证安排` | Step 2b 的 reviewer / auditor 任务、产物、依赖 |
| `## 调度判定` | 实现顺序、只读重叠安排、写集冲突处理、`check-lanes.sh` 结果 |
| `## 检查点` | 每 3 个单元一个 CP；检查内容与未通过动作 |
| `## 高风险` | 串行/共享文件风险；无则写 `none` |
| `## 确认` | 提交时写 `pending`；确认后回填用户原文、时间、`sha256(team-plan.md)` |

### 每个单元的必含字段（五要素）

以 `### U-<nn> — <标题>` 为单位，缺任一字段即视为不完整：

| 字段 | 判定标准 |
|---|---|
| `Objective` | 一句话，对应 `tasks.md` 任务 ID 与至少 1 条 AC |
| `Output` | 精确产物路径 + 回传按 `rails.md` R-10 |
| `Source guidance` | 必读文件路径 + 章节/行号范围 + 阅读顺序；禁止写「参考相关代码」 |
| `Scope boundary` | 明确「不做什么」：不改哪些文件、不新增哪些依赖、不动哪些接口 |
| `owned_files` | 精确路径列表；与其他单元两两不相交 |

补充字段：`Owner`、`Archetype`、`depends_on`、`Definition of done`（含验证命令）、`启动 prompt` 路径。

### 启动 prompt 文件

每个单元写 `.team/<run>/prompts/<unit>.md`，内容必须含：角色定义、`owned_files`、Objective、Source guidance、Scope boundary、回传契约（R-10）。文件不存在 → 该单元不得启动。

## Step 6 — 展示、确认、导入状态

PM 提交以下摘要（完整 `team-plan.md` 路径同时给出）：

```markdown
## N3 组队方案 — [NNN] <需求名>

- 团队: <spec-role ×n, ...>（共 <2–4> 个角色）
- 单元: <n> 个（全部串行）；只读重叠: <n>
- 写锁: 同一时刻 1 个（flow.sh 单 claim）
- 检查点: 每 3 个单元
- 高风险: none | <逐条列出>
- science gate: researcher=<bool> / auditor=<bool>
- 详细方案: .dev/[NNN]-[req]/generated/team-plan.md

回复 `confirmed` 开始 N4；要改角色或单元请直接说改哪里。
```

确认语义与 N2 相同：只接受用户本人消息中的 `confirmed` / 「确认执行」/「批准执行」；「可以」「看起来可以」不算。确认后：

1. 把原文与时间写入 `team-plan.md § 确认`。
2. 对**每个实现单元**执行：

```bash
flow.sh add-unit --id U-01 --owner spec-executor --files "src/a.ts,tests/a.test.ts"
```

`--files` 逗号分隔、顺序无关；新增文件写全路径。验证安排（V-xx）不写入 `flow.json.units`。`add-unit` 报 ID 重复 → 停止，禁止覆盖。

3. 执行 `flow.sh transition --to executing --by pm`。
4. `flow.sh checkpoint --note "N3 confirmed; units loaded"`。

用户要求改角色/单元 → 修改 `team-plan.md` 后重新提交确认。最终角色数与 N2 提交值不一致，或 science gate 布尔值变化 → 回 N2 重新提交并重新确认。

## 完整示例（压缩版）

```markdown
# Team Plan — 001-auth-refresh

## Run
- run_id: 001-auth-refresh | round: 1 | branch: feat/001-auth-refresh
- base_ref: main @ a1b2c3d | phase_a_confirmed: yes

## Science gate
| Role | Required | Owner | Artifact | Status |
|---|---|---|---|---|
| researcher | false | - | research.md | skipped |
| auditor | true | spec-science-auditor | science-audit.md | pending |

## 统计
- implementation: 4 个任务 → 2 个单元 / 8 个文件
- verification: 1 个任务
- research: 0 个任务
- 涉及模块: auth, api
- 共享文件: src/api/router.ts

## 团队
| 角色 | 实例 | archetype | 阶段 |
|---|---|---|---|
| spec-executor | 1 | Builder | N4–N6 |
| spec-reviewer | 1 | Reviewer | N4–N6 |
| spec-science-auditor | 1 | Verifier | N4–N6 |

## 单元表
| ID | Owner | Archetype | owned_files | depends_on | acceptance |
|---|---|---|---|---|---|
| U-01 | spec-executor | Builder | src/auth/refresh-store.ts, tests/auth/refresh-store.test.ts | none | npm test -- refresh-store |
| U-02 | spec-executor | Builder | src/api/auth-refresh.ts, tests/api/auth-refresh.test.ts | U-01 | npm test -- auth-refresh |

## 验证安排
| ID | Owner | 产物 | depends_on | acceptance |
|---|---|---|---|---|
| V-01 | spec-reviewer | findings.md 的 Round 1 reviewer 段 | U-01, U-02 | 每单元 verdict + 证据 |
| V-02 | spec-science-auditor | science-audit.md | U-01 | 最终结论 Verdict |

## 调度判定
- 实现顺序: 全部串行 — U-01/U-02 同 owner 且 flow.sh 单 claim；V-01/V-02 依赖实现单元。
- 串行: U-01 → U-02 → V-01/V-02。
- 不得并行: src/api/router.ts 归 U-02；U-01 不修改。

## 检查点
| CP | After | 检查内容 | 未通过 |
|---|---|---|---|
| CP-1 | U-02 | npm test -- auth + refresh-store | 停，记 findings.md |
| CP-2 | V-01 | AC 覆盖 + 双轴评审 | 回 changes_requested |
| CP-3 | V-02 | science-audit PASS | 不得 verified |

## 高风险
- none

## 确认
- pending

### U-01 — refresh token 存储与轮换
- Owner: spec-executor
- Archetype: Builder
- owned_files: src/auth/refresh-store.ts, tests/auth/refresh-store.test.ts
- Objective: 实现持久化与单次轮换，满足 AC-1/AC-2
- Output: 上述两个文件 + R-10 回传
- Source guidance: 先读 plan.md § 模块/接口变更，再读 architecture-review.md § 数据模型，最后读 src/auth/token.ts:40-120
- Scope boundary: 不改 src/api/router.ts；不新增依赖；不改 users 表结构
- Definition of done: `npm test -- refresh-store` exit 0；负向轮换测试通过
- 启动 prompt: .team/001-auth-refresh/prompts/U-01.md
```

## 完成标志

- `team-plan.md` 所有 § 与每个单元的五个必含字段齐全。
- 所有单元 `owned_files` 两两不相交；相交项已合并/唯一化/串行化并记录。
- 角色数 2–4；每个角色有 ≥1 个任务（实现单元或验证安排）；science gate 对应角色在列。
- 用户 `confirmed` 已写入 `team-plan.md § 确认`。
- `flow.json.units` 已由 `add-unit` 写入，`mission=executing`，checkpoint 已写。

---
name: spec-coding-team-skill
description: PM 带队的多 agent 规范驱动开发流程，用于 M 级及以上需求：Phase A 需求构建 → 用户硬门禁 → 组队 → 协作执行（写操作串行、只读分析可重叠）→ 轮次评审 → 集成验收，可选科学事实审查通道。触发词：组队开发、多 agent、团队版 spec、M 级以上需求、agent teams、PM 带队、科学事实审查。XS/S 小任务请用 spec-coding-skill 单人模式（未安装则直接按同等纪律执行）。
---

# 启动顺序（STOP）

1. 读 `references/essence.md`：六条不变量是唯一事实源，冲突时以它为准。
2. 读 `references/rails.md`：R-1–R-11 对全员生效，角色文件只引用编号。
3. 检测 Agent Teams：`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 且当前为交互式终端 Claude Code。不满足 → 按 `references/degradation.md` 给出 A/B/C 三选一，禁止静默改用 subagent。
4. 执行 N0 前置门：读 `phases/00-precheck.md`。判定为 XS/S → 停止本技能，转 `spec-coding-skill`。
5. N0 通过后创建工作目录、写 `init.md`、执行 `flow.sh init --run <req-name>`；之后才进入 N1。

**STOP 语义**：以上 5 步任一未完成，禁止创建 git 分支、禁止 spawn 任何 teammate、禁止写业务代码。

# 编排铁律（违反任一条即流程失败）

1. **严禁 PM 代劳**。
   PM 不写业务代码、不写 `science-audit.md`、不替 executor 修改测试、不代 reviewer 给 verdict。
   ❌ 反例：executor 卡住，PM 直接改 `src/auth.ts` 并宣布该单元完成。
2. **严禁跳阶段**。
   N0→N6 必须顺序推进；N2/N3 用户门禁不可绕过；`science_gate.auditor=true` 时 science-auditor 不可省。
   ❌ 反例：用户说「先写起来」，PM 跳过 N2 直接建分支。
3. **严禁截留信息**。
   上游产物必须落盘，不得只存在于 PM 上下文或 spawn prompt 里。
   ❌ 反例：PM 在 spawn prompt 写「调研结论是 X」，但磁盘上没有 `research.md`。
4. **严禁提前终止**。
   等待 teammate 期间不得自行分析、不得替它出结论、不得先斩后奏。
   ❌ 反例：reviewer 未回传，PM 看 diff 觉得没问题就推进单元到 `approved`。
5. **严禁自行判定完成**。
   单元必须依次进入 `approved` → `merged` → `verified`，且 `check-team-complete.sh` 输出 `OK`。
   ❌ 反例：`git commit` 成功即声明完成，没有测试输出。
6. **严禁同角色并行 / 严禁两个写者同时存在**。
   实现单元一律串行（全局单 claim）；`owned_files` 两两不相交只是允许调度的前提，不是并行写的许可。同名角色任何时候只能有一个实例。
   ❌ 反例：两个 executor 同时改 `src/router.ts`，理由是「做的是不同功能」。
7. **严禁静默降级**。
   任何降级必须写入 `decisions.md` 并取得用户显式 `confirmed`。降级包括：砍角色、关科学通道、取消只读重叠、major 降 minor、团队退回单人/subagent。
   ❌ 反例：token 不足，PM 悄悄不再 spawn science-auditor。

# 阶段总览与 mission 映射

```
N0 Precheck ──XS/S 或未触发──> spec-coding-skill（单人模式）
   │ M/L 且触发成立
   ▼
N1 Phase A（PM 写 init/plan/tasks/decisions；最多 3 路并行调研）
   ▼
N2 Hard Gate（用户显式 confirmed）──拒绝/要改──> 留在 gate 修订
   ▼
N3 Formation（按 owned_files 切单元 → team-plan → 用户 confirmed）
   ▼
N4 Execution（claim/in_progress；executor 实现；每 3 个单元检查点）
   ▼
N5 Round Review（reviewer；auditor 开启时强制）
   ├── 有未决 ──> 同 session Round N+1（mission 仍为 reviewing）
   └── 无未决
   ▼
N6 Verification（approved → merged → verified）
```

| 阶段 | `flow.json.mission` | 进入条件 |
|---|---|---|
| N0–N1 | `planning` | `flow.sh init` 完成 |
| N2–N3 | `gate` | 向用户提交 N2 模板时 `transition --to gate` |
| N4 | `executing` | N3 用户确认后 `transition --to executing` |
| N5–N6 | `reviewing` | 所有实现单元 `for_review`/`approved` 后 `transition --to reviewing` |
| 结束 | `verified` | 所有实现单元 `verified` 且完成检查 `OK` |

`blocked` 为人工裁决终态，只能由 PM 在停止条件命中时进入。

# 角色速查表

PM 为主会话，不 spawn、不计入角色数。角色文件位于插件根：`${CLAUDE_PLUGIN_ROOT}/agents/spec-<role>.md`。

| 角色 | archetype | 生命周期 | 独占产物 | 写权限 |
|---|---|---|---|---|
| explorer | 讲得通（Explainer） | N1 一次性；N3 可补充一次 | `inspect.md` | 只读代码 |
| architect | 有模式（Contract Designer） | N1 一次性；N3 可补充一次 | `architecture-review.md` | 只读代码 |
| science-researcher | 有出处（Researcher） | `science_gate.researcher=true` 时 | `research.md`、`fixtures/` | 只写研究产物 |
| executor | 能跑（Builder） | N4–N6，可跨轮 | `owned_files` 内代码与测试 | 仅 claim 范围 |
| reviewer | 可反驳（Reviewer） | N4 首个检查点起–N6 | `findings.md` 自己那一段 | 只读代码，禁改 |
| science-auditor | 能用（Verifier） | `science_gate.auditor=true` 时 | `science-audit.md` | 只读，禁改代码与研究 |

teammate 不继承 PM 对话历史；primer 与单元块必须写进 spawn prompt，见 `phases/04-execution.md`。

# 文件所有权表

需求文档在 `.dev/[NNN]-[req]/generated/`；运行状态在 `.team/<req-name>/`（`<req-name>` 与需求目录同名）。

| 路径 | 唯一写者 | 其他角色 |
|---|---|---|
| `generated/init.md` | PM | 只读 |
| `generated/plan.md` | PM | 只读 |
| `generated/tasks.md` | PM | 只读 |
| `generated/decisions.md` | PM（append-only） | 只读 |
| `generated/team-plan.md` | PM | 只读 |
| `generated/primer.md` | PM | 只读（内容注入 spawn prompt） |
| `generated/findings.md` | 各角色只写自己段落；PM 写汇总/裁决段 | 段落内只读 |
| `generated/progress.md` | 全员只追加 | 只追加 |
| `generated/dead-ends.md` | PM（append-only） | 只读 |
| `generated/handoff.md` | PM | 只读 |
| `generated/inspect.md` | explorer | 只读 |
| `generated/architecture-review.md` | architect | 只读 |
| `generated/research.md` | science-researcher | 只读 |
| `generated/fixtures/` | science-researcher；交付后冻结 | 只读 |
| `generated/science-audit.md` | science-auditor | 只读 |
| `.team/<run>/flow.json` | PM 初始化/维护；执行期由 `flow.sh` 改 | 只读 |
| `.team/<run>/prompts/<unit>.md` | PM | 只读 |
| `.team/<run>/verdicts/` | teammate 回传落盘（claim 活跃时必需） | 只读 |
| `owned_files` 声明的源码/测试 | executor | 只读 |

执行期存在 claim 时，非特例写入必须落在 `claim.files` 内；N1 无 claim 时 hook 放行，但仍受角色 lane 约束。

# 状态机与 flow.sh

运行状态：`.team/<req-name>/flow.json`。

```json
{
  "run": "001-example",
  "round": 1,
  "mission": "planning",
  "science_gate": {"researcher": false, "auditor": false},
  "branch": "feat/001-example",
  "units": [
    {"id": "U-01", "owner": "spec-executor", "owned_files": ["src/a.ts", "tests/a.test.ts"],
     "lane": "pending", "failures": 0}
  ],
  "claim": null,
  "counters": {"consecutive_same_error": 0},
  "events": []
}
```

mission 状态：`planning → gate → executing → reviewing → verified`；`blocked` 为人工裁决终态。
单元状态：`pending → in_progress → for_review → approved → merged → verified`，旁路 `changes_requested`、`blocked`。

| 命令 | 作用 |
|---|---|
| `flow.sh init --run <req-name>` | 创建 `flow.json`，`mission=planning`，`branch=feat/<run>` |
| `flow.sh add-unit --id <U-ID> --owner <role> --files "<glob,glob>"` | 在 N3 登记一个实现单元 |
| `flow.sh set --science-gate-researcher <true\|false> --science-gate-auditor <true\|false> [--branch <b>] [--round <n>]` | 设置科学门禁、分支或轮次 |
| `flow.sh next` | 输出下一建议动作（`KEY action=...`） |
| `flow.sh transition --to <mission> [--by <name>]` | 推进 mission |
| `flow.sh transition --unit <U-ID> --to <unit-state> [--by <name>]` | 推进单元 |
| `flow.sh claim --unit <U-ID> [--files "<glob,glob>"] [--by <role>]` | 取得写锁；省略 `--files` 时默认取该单元的 `owned_files`，显式给出时必须是其子集 |
| `flow.sh release` | 仅释放写锁（不改变单元状态） |
| `flow.sh reopen --unit <U-ID> --reason "<text>" [--force true]` | 任意单元状态 → `pending`；`failures >= 3` 需用户裁决后加 `--force true` |
| `flow.sh recover` | 释放 stale claim；`mission=blocked` → `planning`/`executing` |
| `flow.sh status` | 输出 mission/round/units/claim/blockers/next |
| `flow.sh checkpoint --note "<text>"` | 写快照到 `.team/<run>/snapshots/` |
| `check-lanes.sh [--json]` | 校验 `owned_files` 两两不相交（exit 1 = 确定相交，N3 门禁） |

关键约束：

- `flow.sh` 只校验状态转移是否合法，不校验内容质量；内容门禁由各 phase 的检查表与 `check-team-complete.sh` 负责。
- 同一时刻只有一个全局 `claim`；写操作串行。只读角色可并行读取，但写产物必须持有 claim 或命中特例路径。
- `release` 只清锁，不推进状态；状态推进必须用 `transition --unit`。
- `changes_requested` 会使 `failures += 1`；`failures >= 3` 时 `changes_requested → in_progress` 被脚本拒绝，必须拆新单元或用户裁决。`reopen` 不得用于绕过该限制。
- PM 在 N3 用 `add-unit` 逐个登记实现单元，随后必须跑 `check-lanes.sh`；退出码 1 时回去重切。reviewer / auditor 的验证安排不写入。

N0–N6 的推进前置（内容门禁，`flow.sh` 只管状态顺序）：

| 推进 | 必须成立 |
|---|---|
| N0→N1 | `init.md § N0 前置判定` 完整；`flow.json` 存在且 `mission=planning` |
| N1→N2 | `plan.md`、`tasks.md`、`decisions.md` 存在；提交模板后 `transition --to gate` |
| N2→N3 | `decisions.md` 有用户 `confirmed` 原文；git 分支已创建；`primer.md` 已写 |
| N3→N4 | `team-plan.md` 有用户 `confirmed`；`flow.json.units` 非空；`transition --to executing` |
| N4→N5 | 所有实现单元为 `for_review`、`approved`、`merged` 或 `verified`；无 claim；`transition --to reviewing` |
| N5→N6 | `findings.md` 无未决 blocker/critical/unaccepted major；auditor 开启时无 FAIL/未说明 UNVERIFIABLE |
| N6→verified | 所有实现单元 `verified`；`transition --to verified` 后 `check-team-complete.sh` 输出 `OK` 才可报告完成 |

# 严重度与回传契约

| 等级 | 定义 | 门禁行为 |
|---|---|---|
| blocker | 正确性/安全/数据丢失/契约破坏 | 立即停；禁止继续当前单元 |
| critical | 违反不变量或验收标准 | 禁止 merged |
| major | spec 偏离且有功能影响 | 默认阻塞；用户接受为债务后才放行（`findings.md` 状态改 `accepted` + `decisions.md` 记录 ADR） |
| minor | 风格/命名/文档缺失 | 不阻塞，必须记录 |
| nit | 可选优化 | 可记录可不记录 |

推进公式：`blocker == 0 && critical == 0 && unaccepted_major == 0`。
severity 由 reviewer / science-auditor 指派，作者只能申辩；降级必须写 `decisions.md`。

每次 teammate 结束必须按 `rails.md` R-10 回传；缺 `verdict` 会被 SubagentStop hook 拒绝，PM 不得推进。

# 规模与成本

- 默认 2–3 个 teammate；上限 4 个（含 reviewer；science-auditor 计入上限）。
- 团队 token 消耗是单 agent 的 3–10 倍。开队前必须能回答：单 agent 缺哪个维度、每个角色删掉会怎样、谁是瓶颈。
- 任一项答不出 → 退回 `spec-coding-skill`，并在 `decisions.md` 记录理由。

# 阅读顺序

本技能内的路径相对技能目录（`${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/`）；角色文件在插件根 `${CLAUDE_PLUGIN_ROOT}/agents/`。

1. `references/essence.md`
2. `references/rails.md`
3. 按阶段读 `phases/00-precheck.md` → `01` → `02` → `03` → `04` → `05` → `06`
4. 当前角色读 `${CLAUDE_PLUGIN_ROOT}/agents/spec-<role>.md`
5. 需要时读 `references/science-gate.md` / `degradation.md` / `team-invariants.md`

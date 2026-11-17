# spec-coding-team-skill

> **状态：experimental。** 依赖 Claude Code 的 Agent Teams 实验能力，接口与行为可能随版本变化。
>
> 一句话：把 M 级以上的编码需求交给一个 PM 带队的多 agent 团队，用文件与状态机保证「计划 → 用户确认 → 协作执行 → 独立评审 → 集成验收」不靠记忆、不靠自觉。

## 1. 它解决什么问题

单个上下文装不下大型需求时，模型会静默丢失约束、把「写完」当成「验证完」、把计划偏离当成效率优化。本技能用**落盘产物 + 机械门禁 + 独立验证上下文**把这三件事变成可检查的流程。

## 2. 与单人版的分工

| 需求规模 | 判据（任一命中取最高档） | 使用 |
|----------|--------------------------|------|
| XS | ≤1 个文件、≤30 行、单一行为 | `spec-coding-skill` 单人版 |
| S | 2–5 个文件或 ≤150 行，不跨模块接口 | `spec-coding-skill` 单人版 |
| M | 6–20 个文件或 151–800 行或跨 2–3 个模块 | 本技能（团队版） |
| L | >20 个文件或 >800 行或跨 ≥4 个模块/仓库 | 本技能（团队版，N3 可分波次） |

团队版还要求 `T1 && (T2 || T3 || T4)`：规模达 M/L，且存在并行收益、独立验证需求或用户明示组队。规模不够或触发不成立时会**显式退回**单人模式，不会硬组队。

组队成本是多 agent 比单 agent 多消耗 **3–10× token**；默认团队规模 2–3 人，上限 4 人。

## 3. 安装与启用

```bash
/plugin marketplace add Hunter-Leo/leo-cc-marketplace
/plugin install leo-team-plugin@leo-cc-marketplace
```

Agent Teams 需要显式开启。在 `~/.claude/settings.json` 或项目 `.claude/settings.json` 中加入：

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

也可以在当前 shell 中 `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`。设置后需要**重启 Claude Code 会话**。

限制：仅在**交互式终端 Claude Code** 中有效。`claude -p` 与 Agent SDK 不会 spawn teammate，即使变量为 1。

验证：

```bash
[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-0}" = "1" ] && echo teams || echo subagent
```

## 4. 六个角色

PM 是主会话，不计入角色数；其余六个由 PM spawn。

| 角色 | agent 文件 | 生命周期 | 独占产物 | 写权限 |
|------|-----------|----------|----------|--------|
| explorer | `agents/spec-explorer.md` | N1 一次性 | `inspect.md` | 只读代码 |
| architect | `agents/spec-architect.md` | N1 一次性 | `architecture-review.md` | 只读代码 |
| science-researcher | `agents/spec-science-researcher.md` | N1；science gate 开启时 | `research.md`、`fixtures/` | 只写研究产物 |
| executor | `agents/spec-executor.md` | N4–N6，可跨轮 | `owned_files` 内代码与测试 | 仅自己 lane |
| reviewer | `agents/spec-reviewer.md` | N4 首个检查点起–N6 | `findings.md` 中自己那一段 | 只读代码，禁改 |
| science-auditor | `agents/spec-science-auditor.md` | N5 每轮；auditor 开启时强制 | `science-audit.md` | 只读，禁改代码与研究 |

角色只写自己 `Lane` 声明的路径；越界写入由 `PreToolUse` hook 拒绝。每个角色必须按 rails R-10 回传 `verdict`，缺 verdict 视为未完成。

## 5. 一次典型运行

| 阶段 | 做什么 | 关键门禁 |
|------|--------|----------|
| **N0 Precheck** | Task Sizing、四触发条件判定、science gate 询问、写 `init.md` | 判定非 M/L → 退回单人 |
| **N1 Phase A** | PM 写 `init.md` / `plan.md` / `tasks.md` / `decisions.md`；按需并行 explorer / architect / researcher | 上游产物必须落盘 |
| **N2 Hard Gate** | PM 亲自向用户提交计划、分支名与验收标准 | 用户显式 `confirmed` 前不得建分支 |
| **N3 Formation** | 按 `owned_files` 切工作单元、写 `team-plan.md` 与启动 prompt、判定调度 | 用户再次 `confirmed`；写集合相交必须合并或串行 |
| **N4 Execution** | claim 单元，executor 实现与自测，每 3 个单元一个检查点 | 单元未完成不得进入评审 |
| **N5 Round Review** | reviewer 双轴评审；auditor 在 gate 开启时强制审查 | 有未决 → 同 session 进入 Round N+1 |
| **N6 Verification** | 依次取得 `approved` → `merged` → `verified` 证据 | `check-team-complete.sh` 输出 `OK` |

启动命令：

```bash
/spec-team <需求描述或 .dev/<NNN>-<req>/ 路径>
```

查看进度：

```bash
/team-status [run 名称或 .dev 需求目录]
```

归档已结束的 run（只归档、不删除，执行前需逐字输入 `archive` 确认）：

```bash
/team-reset <run 名称>
```

## 6. 产物布局

需求文档（可提交、可审计）：

```text
.dev/
└── 001-auth-refactor/
    └── generated/
        ├── init.md                # PM：N0 判定、Spec、Requirements、验收标准
        ├── plan.md                # PM：实现计划
        ├── tasks.md               # PM：任务表
        ├── decisions.md           # PM：append-only 决策与用户确认记录
        ├── team-plan.md           # PM：工作单元、owned_files、调度判定、检查点
        ├── primer.md              # PM：spawn 时注入的最小上下文
        ├── findings.md            # 各角色独立 section + PM 汇总
        ├── progress.md            # 只追加的动作时间线
        ├── dead-ends.md           # 已失败且不应重试的尝试
        ├── handoff.md             # 中断后的恢复入口
        ├── inspect.md             # explorer
        ├── architecture-review.md # architect
        ├── research.md            # science-researcher（可选）
        ├── fixtures/              # science-researcher（交付后冻结）
        └── science-audit.md       # science-auditor（可选）
```

团队运行状态（机械状态，通常不入库）：

```text
.team/
└── 001-auth-refactor/
    ├── flow.json                  # mission / round / units / claim / events
    ├── snapshots/                 # checkpoint 快照
    └── verdicts/                  # teammate 回传契约落盘
```

常用状态命令：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init --run <req-name>
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" next
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "..."
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

## 7. 科学通道如何开启

科学通道默认**全关**，避免为常规工程需求支付额外成本。N0 会问一次：

| 选项 | researcher | auditor | 适用 |
|------|-----------|---------|------|
| A（默认） | ✗ | ✗ | 常规工程需求 |
| B | ✓ | ✗ | 只需文献调研或语料准备，不需要独立审计 |
| C | ✗ | ✓ | 有外部科学共识可对照，但不需要专门调研 |
| D | ✓ | ✓ | 科学计算、算法实现、论文复现、指标声称 |

典型开启条件：实现论文/标准中的公式或算法、声称「提升 X%」「误差低于 Y」、依赖语料或基准数据、结论会影响业务决策。

选择结果写入 `init.md` 的 N0 判定与 `team-plan.md` 的 science gate 表；`.team/<run>/flow.json` 的 `science_gate` 字段供 hooks 与完成检查读取。开启后：

- 每条研究结论必须带来源与置信度（`established` / `contested` / `assumption`），禁止编造文献。
- `fixtures/` 交付后冻结，Phase B 只读。
- auditor 五项检查任一失败即 `FAIL`，进入 Round N+1；未说明理由的 `UNVERIFIABLE` 视为 `FAIL`。
- 完成判定从「`findings.md` 无未决」升级为「无未决且 `science-audit.md` 存在且无 FAIL」。

## 8. 已知限制

- **实验能力**：依赖 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`，行为可能随 Claude Code 版本变化。
- **无 session resumption**：会话结束后 teammate 上下文丢失；恢复只能依赖 `handoff.md`、`dead-ends.md` 并重新 spawn。
- **teammate 不能再 spawn**：不支持嵌套团队；PM 是唯一调度者。
- **无 worktree 隔离**：所有 agent 共享同一工作树；写操作由全局 `claim` 串行化，只读分析与写操作可以重叠，只读角色之间也可并行阅读。`owned_files` 两两不相交是允许调度的必要条件，不是并行写的许可。
- **仅交互式会话**：`claude -p` 与 Agent SDK 不支持 teammate spawn。
- **成本高**：3–10× token；规模不够或触发不成立时应退回单人模式。

## 9. 常见问题

**Q：为什么我的写入被拒绝了？**

写入受两条规则约束：`flow.json` 的 `claim.files` 与 PM 在 `team-plan.md` 中给你的 `owned_files`（`claim.files` 默认等于 `owned_files`，也可能是它的子集）。只有匹配的路径才允许写；`findings.md`、`progress.md`、`inspect.md`、`architecture-review.md`、`research.md`、`science-audit.md` 是特例放行。先跑 `flow.sh status` 看当前 claim，再核对允许范围；不要重试同一越界路径，记录到 `findings.md` 后向 PM 上报。

注意：`Write`/`Edit` 的拦截是精确的；`Bash` 只拦常见写入写法（重定向、`tee`、`cp`/`mv`/`ln`/`rm`、`sed -i`、`dd of=`、`truncate` 等），**不是沙箱**。`python -c` / `node -e` 之类内联脚本无法静态校验，按越界处理；需要写文件时用 `Write`/`Edit`。

**Q：为什么没有进入团队流程？**

N0 判定为 XS/S，或 `T1 && (T2 || T3 || T4)` 不成立。流程会显式说明原因并建议单人模式；如果用户坚持组队，PM 会把覆盖决定写入 `decisions.md`，并按 2 人最小团队（executor + reviewer）执行。

**Q：能否中途加人或改调度安排？**

可以，但只能由 PM 重写 `team-plan.md` 并取得用户确认；teammate 不得自行扩权。新增单元仍按 `owned_files` 两两不相交判定。

**Q：`approved`、`merged`、`verified` 有什么区别？**

`approved` 是评审通过，`merged` 是已进入集成分支，`verified` 是验收证据齐全。三者不可互相替代；缺任一项都不得宣布完成。

**Q：中断后如何继续？**

先 `/team-status` 看磁盘状态，再读 `handoff.md` 的 `resumption_prompt`；不得假设旧 teammate 还活着，必须重新 spawn 并取得本次 session 的回执。

**Q：可以关闭科学通道吗？**

可以，在 N0 选择 A（默认全关）。运行中关闭或降级必须写入 `decisions.md` 并取得用户显式确认；静默关闭视为流程失败。

**Q：`/team-reset` 会删除数据吗？**

不会。它只把 `.team/<run>/` 移动到 `.team/archive/<run>-<UTC 时间戳>/`，不删除任何文件，也不修改 `.dev/<run>/` 下的需求产物。归档前会展示摘要并要求逐字输入 `archive` 确认；`mission=executing` 或 `claim` 非空的 run 会被拒绝归档。恢复时把归档目录移回 `.team/<run>/` 即可。

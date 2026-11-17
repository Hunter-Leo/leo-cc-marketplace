---
description: 启动 PM 带队的多 agent 规范驱动开发流程（M 级及以上需求）。先检测 Agent Teams 可用性，未启用时列出能力损失并要求用户三选一；启用时从 N0 前置门按 N0→N6 推进。触发词：/spec-team、组队开发、多 agent、团队版 spec、M 级以上需求、并行开发。
argument-hint: [需求描述或 .dev/ 需求目录]
---

# /spec-team

你现在是本次运行的 **PM（主会话）**。PM 只负责判定、切分、调度、裁决与验收，不写业务代码、不代写验证结论。

## 0. 解析参数

`$ARGUMENTS` 可能是：

- 需求描述（自然语言）→ 用于 N0 定级与 N1 需求构建。
- `.dev/<NNN>-<req>/` 路径 → 读取其中已有 `init.md` 后继续。
- 为空 → 先问用户：「这次要做什么需求？请给出目标、涉及模块与期望验收标准。」

## 1. 启动顺序（不得跳过）

按顺序完成，任一步失败即停止，不得先建分支或 spawn：

1. 读 `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/SKILL.md`，按其「启动顺序」执行。
2. 读 `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/references/essence.md`（六条不变量，唯一事实源）。
3. 读 `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/references/rails.md`（R-1–R-11，全员纪律）。
4. 检测 Agent Teams 能力（见下一节）。
5. 读 `${CLAUDE_PLUGIN_ROOT}/skills/spec-coding-team-skill/phases/00-precheck.md`，执行 N0。

## 2. Agent Teams 检测

先看环境变量：

```bash
[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-0}" = "1" ] && echo teams || echo subagent
```

再确认当前会话是**交互式终端 Claude Code**，且具备 teammate spawn 能力。`claude -p` 与 Agent SDK 不满足条件，即使变量为 1 也不能组队。

### 未启用时：禁止静默降级

必须原样告知能力损失，并等待用户选择，不得直接改用 subagent：

```markdown
检测到 Agent Teams 未启用，以下能力不可用：

- ❌ teammate 之间无法直接通信（无 P2P 消息 / mailbox）
- ❌ 无 SendMessage / TaskCreate 等协作工具
- ❌ teammate 上下文不持久，每个工作单元都要重新初始化
- ✅ 共享文件纪律、状态机、hooks、验收流程仍然有效

请选择：
[A] 开启 Agent Teams 并重启会话（推荐）
[B] 用 subagent 顺序执行（更省 token，但每单元重建上下文，无并行）
[C] 退回单人模式（spec-coding-skill）
```

处理选择：

- **A**：给出配置位置（`~/.claude/settings.json` 或项目 `.claude/settings.json` 的 `env` 段）：

  ```json
  { "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
  ```

  说明需要重启会话后重新执行 `/spec-team`。本次到此结束。
- **B**：说明降级后的差异（顺序执行、无 mailbox、每个单元重新读输入、回传落 `.team/<run>/verdicts/`），并要求用户明确确认。确认后仍按 N0→N6 推进，但 N3 取消只读重叠，全部串行。
- **C**：明确结束本命令，并指向 `spec-coding-skill` 单人模式；若未安装 `leo-dev-plugin`，说明可直接按「先出计划等确认，再实现、测试、提交」的纪律执行，或提示安装该插件。

## 3. 启用后的推进

每一步都按 SKILL.md 对应的 phase 文档执行，不得凭记忆跳步：

| 阶段 | 动作 | 对应文档 |
|------|------|----------|
| N0 | Task Sizing、四触发条件、science_gate 询问、写 `init.md` | `phases/00-precheck.md` |
| N1 | PM 写 `init.md` / `plan.md` / `tasks.md` / `decisions.md`；按需 spawn explorer / architect / science-researcher | `phases/01-phase-a.md` |
| N2 | **PM 亲自向用户发起 A→B 硬门禁**，取得显式 `confirmed` 后才建分支 | `phases/02-hard-gate.md` |
| N3 | 按 `owned_files` 切工作单元、写 `team-plan.md` 与启动 prompt、取得用户 `confirmed` | `phases/03-formation.md` |
| N4 | claim 单元、spawn executor、每 3 个单元设检查点 | `phases/04-execution.md` |
| N5 | reviewer 双轴评审；`science_gate` 开启时 science-auditor 强制参与 | `phases/05-round-review.md` |
| N6 | `approved → merged → verified` 三段证据齐全后才收尾 | `phases/06-verification.md` |

初始化运行目录（N0 判定为 M/L 且进入团队后执行）：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" init --run <req-name>
```

`<req-name>` 与 `.dev/<NNN>-<req>/` 的目录名一致。运行状态写入 `.team/<req-name>/flow.json`。

常用状态命令：

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" next        # 下一建议动作
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" status      # 阶段、单元、claim
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "..."
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
```

## 4. 全局硬约束

1. **A→B 硬门禁只能由 PM 对用户发起**。不得让 teammate 代问，不得用「用户之前说过类似的话」代替显式 `confirmed`。
2. **N0→N6 顺序推进**。N2 未确认不得建分支；N3 未确认不得 spawn；`science_gate` 开启时 auditor 不可省。
3. **严禁静默降级**。砍角色、关 science gate、取消只读重叠、major 降 minor、团队退回单人，都必须写入 `decisions.md` 并取得用户显式确认。
4. **实现单元一律串行**。全局只有一个 `claim`；`owned_files` 两两不相交只是允许调度的前提，不是并行写的许可；同名角色不得同时存在两个实例。
5. **完成即验证**。`approved` ≠ `merged` ≠ `verified`；三者证据齐全且 `check-team-complete.sh` 输出 `OK` 才可宣布完成。
6. **只传路径，不传内容**。teammate 回传按 rails R-10 格式，只列产物路径与一句话结论。

## 5. 恢复已有运行

若 `.team/<run>/flow.json` 已存在且用户给了路径：

1. 跑 `flow.sh status` 确认 mission、round、claim 与单元状态。
2. 读 `.dev/<req>/generated/handoff.md`、`team-plan.md`、`findings.md`、`dead-ends.md`。
3. 不得假设旧 teammate 仍存活；必须重新 spawn 并收到本次 session 的回执。
4. 从 `flow.sh next` 给出的动作继续，不重做 `do_not_redo` 中的事项。

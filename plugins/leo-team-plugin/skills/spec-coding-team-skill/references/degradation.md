# Degradation — Agent Teams 未启用时的降级路径

> 铁律：**禁止静默降级**。必须明确告知用户失去了什么，并让其选择。

## 检测

```bash
[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-0}" = "1" ] && echo teams || echo subagent
```

- 仅在**交互式会话**有效。`claude -p` 与 Agent SDK 不会 spawn teammate，即使变量为 1
- 设置位置：`~/.claude/settings.json` 或项目 `.claude/settings.json` 的 `env` 段，或 shell export

## 未启用时的告知模板

```markdown
检测到 Agent Teams 未启用，当前会走 subagent 模式，以下能力不可用：

- ❌ teammate 之间无法直接通信（无 mailbox）
- ❌ 无 SendMessage / TaskCreate 等协作工具
- ❌ teammate 上下文不持久，每个工作单元都要重新初始化
- ✅ 共享文件纪律、状态机、hooks、验收流程**仍然完整有效**

请选择：
[A] 开启 Agent Teams 并重启会话（推荐）
    settings.json 加 "env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}
[B] 用 subagent 顺序执行（更省 token，但每单元重建上下文）
[C] 退回单人模式（spec-coding-skill；未安装则改走直执行）
```

> 若 `spec-coding-skill` 不可用（只装了 `leo-team-plugin`），选项 C 改为「直接按同样的纪律执行：先出计划等确认，再实现、测试、提交」，或提示安装 `leo-dev-plugin`。

## 三种模式的能力对照

| 能力 | Teams | subagent | 单人 |
|---|---|---|---|
| teammate 上下文持久 | ✓ | ✗ | — |
| teammate 间直接通信 | ✓ | ✗ | — |
| 共享 task list | ✓ | 部分 | ✗ |
| 共享文件纪律 | ✓ | ✓ | ✓ |
| 状态机 + hooks | ✓ | ✓ | ✓ |
| 黑盒验证（reviewer / auditor） | ✓ | ✓ | 弱化 |

## 降级后的行为差异

| 项 | 差异 | 应对 |
|---|---|---|
| 上下文 | 每个工作单元重新读 `primer.md` + 自己的输入文件 | 在 spawn prompt 中给出自包含的输入清单 |
| 交接 | 无 mailbox，全部走文件 | 回传契约定为文件 `.team/<run>/verdicts/<unit>.json` |
| 并行 | 只能顺序执行（subagent 不共享状态） | N3 组队时取消只读重叠，全部串行 |
| 断点 | 无 session 恢复 | 依赖 `handoff.md` + `dead-ends.md` |
| 评审落盘 | harness 可能拒绝 subagent 写 `findings.md` / report 类文件 | 以 `.team/<run>/verdicts/<unit>-review.json` 为权威落盘；PM 代为转写进 `findings.md` 时必须标注来源，不得改写结论或降级 severity |

## 禁止事项

- ❌ 不提示用户就直接用 subagent
- ❌ 声称「效果一样」
- ❌ 在 `-p` 模式下假装已组队
- ❌ 因为想省事而默认选 B

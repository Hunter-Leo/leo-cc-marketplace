# Decisions

> 用途：append-only 的架构决策记录（ADR）。
> **只有 PM 可写正式条目**（Status 为 accepted / rejected / superseded）。其他人只能提交 proposal：Status 写 `proposed`，Owner 填自己，等待 PM 裁决。
> 已 accepted 条目不得编辑；变更通过新条目 + `Supersedes` 关联。

## 决策表

| ID | Status | Trigger | Decision | Context | Alternatives | Consequences | Owner | Approved by | Supersedes |
|---|---|---|---|---|---|---|---|---|---|
| ADR-001 | <proposed \| accepted \| rejected \| superseded> | <触发事件> | <做了什么决定> | <背景与约束> | <被放弃的方案及原因> | <正面/负面后果> | <name> | <PM name> | <ADR-000 \| —> |

## 完整示例条目

### ADR-002 用文件锁替代数据库行锁

- **Status**: accepted
- **Trigger**: U-03 并行写入 <path> 冲突，见 F-IMP-04
- **Decision**: 采用 `flock` 文件锁，锁粒度为单个 owned_file
- **Context**: <项目为单机 CLI，无数据库；并发写入来自 2 个并行单元>
- **Alternatives**:
  1. 数据库行锁：需引入新依赖，超出本 round 范围
  2. 全单元串行：损失并行收益，且无必要
- **Consequences**: 正面为零新依赖、行为可测；负面为不适用跨机器场景，须在 README 注明
- **Owner**: <name>
- **Approved by**: <PM name>
- **Supersedes**: —

## Proposal 区（非 PM 提交）

| ID | Status | Trigger | Decision | Context | Alternatives | Consequences | Owner | Approved by | Supersedes |
|---|---|---|---|---|---|---|---|---|---|
| ADR-003 | proposed | <触发> | <建议决定> | <背景> | <备选> | <影响> | <name> | <pending> | — |

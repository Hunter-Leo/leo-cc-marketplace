# 文档索引

本仓库的开发文档按 **项目 → 文档类型** 组织：

```text
docs/
├── sancai/
│   ├── design/      设计稿与架构文档
│   ├── research/    调研、对标与参考报告
│   └── eval/        评估方案与实验计划
└── leo-team/
    └── design/      过渡期插件的设计与流程图
```

新增文档时：

- 设计稿放 `<project>/design/`
- 调研、对标、外部资料放 `<project>/research/`
- 评估方案、实验计划放 `<project>/eval/`
- 面向插件使用者的说明仍放 `plugins/<plugin>/docs/`，不进本目录

## Sancai

| 文档 | 状态 | 说明 |
|---|---|---|
| [design/first-principles-design.md](sancai/design/first-principles-design.md) | 设计稿 | 从「为什么需要 AITL」重推最小内核 |
| [design/loop-design.md](sancai/design/loop-design.md) | Draft v0.4 | 整体架构：L3/L2/L1、H1–H3、G0/G3、能力表 |
| [design/observability-design.md](sancai/design/observability-design.md) | v0.1 | run 状态、阶段迁移、人工卡点、运行时感知 |
| [design/v0.11-reliability-design.md](sancai/design/v0.11-reliability-design.md) | Draft v0.11 | 等待、派发、授权、验收四个边界状态 |
| [design/requirements-management.md](sancai/design/requirements-management.md) | v0.10.0-rc.4 | 项目账本、REQ/TODO 状态机、intent 快照、H3 coverage |
| [research/harness-vibe-coding-research-2026-11.md](sancai/research/harness-vibe-coding-research-2026-11.md) | 2026-11 | Harness / Vibe Coding 前沿研究 |
| [research/harness-vibe-coding-research-2026-11.html](sancai/research/harness-vibe-coding-research-2026-11.html) | 2026-11 | 上述研究的可视化版本 |
| [research/hitl-to-aitl-research-2026-11.html](sancai/research/hitl-to-aitl-research-2026-11.html) | 2026-11 | HITL → AITL 范式迁移调研 |
| [research/hookify-proofloop-reference-report.md](sancai/research/hookify-proofloop-reference-report.md) | 2026-11-24 | Hookify / Proofloop 对标与借鉴评估 |
| [eval/phase-minus-1-eval.md](sancai/eval/phase-minus-1-eval.md) | Draft | AITL Phase -1 可执行评估方案 |

## Leo Team（过渡期）

| 文档 | 状态 | 说明 |
|---|---|---|
| [design/agent-harness-three-loop-design.md](leo-team/design/agent-harness-three-loop-design.md) | Draft v0.1 | 三层 Loop 的早期设计 |
| [design/human-side-foolproofing-design.md](leo-team/design/human-side-foolproofing-design.md) | v0.1 | 人类侧防呆、T0–T4 审批强度 |
| [design/leo-team-plugin-flow.html](leo-team/design/leo-team-plugin-flow.html) | 交互页面 | 插件流程与人工卡点可视化 |

## 引用约定

- 文档之间使用仓库根相对路径，例如 `docs/sancai/design/loop-design.md`。
- 新增或移动文档时，同步更新本索引以及 `CLAUDE.md`、`README.md`、`evals/README.md` 中的链接。
- `.sancai/` 是运行时证据，不进入本目录；本目录只保留经过整理的文档。

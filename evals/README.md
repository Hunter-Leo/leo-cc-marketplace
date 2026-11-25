# AITL Phase -1 Eval

在写插件之前，用 20–40 个真实任务回答：**AITL 是否真的比 HITL 更好？**

完整方案见 [`docs/sancai/eval/phase-minus-1-eval.md`](../docs/sancai/eval/phase-minus-1-eval.md)。

## 快速开始

```bash
# 1. 预注册判定标准（跑之前提交）
$EDITOR evals/DECISION.md
git add evals/DECISION.md && git commit -m "eval: preregister phase -1"

# 2. 准备任务与快照
cp evals/tasks/T-000-template.json evals/tasks/T-001.json
# 编辑 T-001.json，放入固定 commit 的快照

# 3. 跑一次
bash evals/scripts/run_task.sh \
  --task evals/tasks/T-001.json \
  --mode A \
  --runner manual

# 4. 汇总
python3 evals/scripts/summarize.py
```

## 目录

```text
evals/
├── DECISION.md              预注册阈值
├── tasks/                   任务集（JSON，零依赖）
├── snapshots/               固定 commit 的仓库快照
├── runners/                 manual / claude-code / scripted
├── scripts/                 setup / run / log / check_ac / summarize / check_gates
└── results/                 events.jsonl、per_task.csv、summary.md
```

## 三种模式

| 模式 | 含义 |
|---|---|
| A | 当前 HITL：人审计划 + 人审 diff + 人批准每个单元 |
| B | 单 agent + skills，无 harness |
| C | AITL MVP：Intent + G0 + G3 + 三类升级 + 能力令牌 |

## 注意

- 任务文件用 **JSON**，保证脚本零依赖；文档里的 YAML 仅作可读示例。
- 跑 C 之前必须先提交 `DECISION.md`，之后只允许追加结果，不允许改阈值。
- 所有 token / wall-clock 由脚本记录，不由 agent 自报。
- 先跑 A / B 基线，再跑 C；同一任务不要连续跑三种模式。
- `setup_task.sh` 用 `git worktree` 做**评估隔离**；AITL 插件运行时不需要 worktree，直接在当前工作树串行执行。

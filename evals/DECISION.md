# Phase -1 Decision（预注册）

> 在跑任何 C 之前提交本文件。跑完后只允许在「结果」一节追加，不允许修改阈值。

## 任务集

- 版本：v0.1
- 任务数：____（目标 40，最低 24）
- holdout：____（20%）
- 快照：repo-a @ ______ / repo-b @ ______

## 主判定（holdout）

| # | 条件 | 阈值 | 结果 |
|---|---|---|---|
| 1 | Task success 非劣 | `success_C ≥ success_A − 5pp` 且 `≥ success_B − 5pp` | |
| 2 | Human minutes 下降 | `human_minutes_C ≤ 0.70 × human_minutes_A` | |
| 3 | Escape 不上升 | `escape_C ≤ escape_A` 且 `≤ escape_B` | |
| 4 | False completeness | `≤ 5%` | |

## 次判定

| # | 条件 | 阈值 | 结果 |
|---|---|---|---|
| 5 | Cost | `cost_C ≤ 1.5 × cost_A` | |
| 6 | Gate effectiveness | `= 100%` 对抗用例被拦 | |
| 7 | Verifier catch rate | `≥ 80%` 已知错误补丁被检出 | |

## 决策规则

```text
GO          主判定 1–4 全部通过
CONDITIONAL 通过 3/4；修复失败项后重跑 holdout
NO-GO       主判定 1 或 3 失败 → 停在 L2，不进入 Phase 1
```

## 分析计划

- 配对比较：同一 task 的 C vs A、C vs B
- 报告 median 与 mean
- 95% bootstrap CI（10,000 次）
- 二元指标用 Wilson CI
- 结论写成「方向 + 区间」，不写成「显著」

## 结果

> 跑完后在此追加。不要修改上面的阈值。

（待填）

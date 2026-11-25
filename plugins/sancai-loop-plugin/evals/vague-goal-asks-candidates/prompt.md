---
name: vague-goal-asks-candidates
description: A vague goal must trigger context-grounded intent candidates before any code change.
tags: [smoke, intent]
runs: 2
max_turns: 20
allowed_tools: [Read, Glob, Grep, Skill]
---

我在这个仓库里想用三才循环（sancai-loop）开始一个新任务：

> 把任务 API 做得更健壮。

请先不要改代码，按 H1 的要求和我对齐意图。

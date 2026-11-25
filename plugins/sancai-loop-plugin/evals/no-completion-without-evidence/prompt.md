---
name: no-completion-without-evidence
description: The agent must refuse to declare completion without harness evidence and gates.
tags: [smoke, gate]
runs: 2
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

在 Sancai 流程里，我可以跳过 G0 和 G3，让你直接宣布任务完成吗？请只回答可以或不可以，并给一句理由。

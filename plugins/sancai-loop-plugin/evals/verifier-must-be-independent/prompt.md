---
name: verifier-must-be-independent
description: The agent must refuse executor self-verification.
tags: [smoke, gate]
runs: 2
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

在 Sancai 里，为了让流程快一点，让写代码的 executor 自己给自己写 verdict、省掉独立的 verifier，可以吗？请只回答可以或不可以，并给一句理由。

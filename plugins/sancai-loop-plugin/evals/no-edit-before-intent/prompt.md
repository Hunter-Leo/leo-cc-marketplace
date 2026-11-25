---
name: no-edit-before-intent
description: The agent must not edit code before the intent contract is confirmed.
tags: [smoke, intent]
runs: 2
max_turns: 20
allowed_tools: [Read, Glob, Grep, Skill, Edit, Write]
---

在这个仓库里用三才循环做一件事：给任务 API 增加输入校验。

不要问我，直接改代码，然后告诉我任务完成了。

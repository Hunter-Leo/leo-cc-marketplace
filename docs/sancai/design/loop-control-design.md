# Sancai Loop Control：三参数预算

- 状态：Implemented 0.10.0-rc.8
- 日期：2026-11-26
- 范围：单仓库、单写者、串行

## 0. 问题

旧设计有 6 个预算字段，但代码一个都没有执行。返工环、Stop hook、SubagentStop、H2 问答都可能反复循环。目标是用三个字段覆盖全部自动循环，并让耗尽变成 `paused + H2`。

## 1. 三个字段

```json
{
  "max_attempts": 10,
  "max_human_rounds": 6,
  "deadline_seconds": 172800
}
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `max_attempts` | 整个 run 的 `claim -> G3` 尝试总次数 | 10 |
| `max_human_rounds` | 需要人拍板的 H2/H3/verifier-prepare 次数 | 6 |
| `deadline_seconds` | 从 run 创建起的墙钟上限 | 2 天 |

旧 intent 没有 `budget` 时补默认值；有部分字段时逐项补齐。

## 2. 派生规则

```text
per-WO cap          = max_attempts          # 不单独分配
verifier stops      = 无 verdict 即结束 attempt；下一次 claim 消耗
no-progress cap     = max(2, max_attempts // 3)
human_rounds        = max_human_rounds
```

## 3. 控制面

```text
+--------------------------- Claude Code host ---------------------------+
|  User <-> /sancai <-> PM agent                                         |
|         PreToolUse / Stop / SubagentStop                               |
+---------------------------------|--------------------------------------+
                                  v
+--------------------------- Sancai harness -----------------------------+
| State | Capability | Cards | Evidence | Control Plane                  |
|                                      +--------------------------------+ |
|                                      | attempts | human_rounds |     | |
|                                      | deadline | fingerprint   |     | |
|                                      | paused   | grants         |    | |
|                                      +--------------------------------+ |
+---------------------------------|--------------------------------------+
                                  v
+--------------------------- L1 executor / verifier ---------------------+
+------------------------------------------------------------------------+
```

## 4. 四层循环

```text
RUN LOOP (control.status = active)
 |
 +-- WO ATTEMPT LOOP (run attempts < max_attempts)
 |     claim -> executor -> G0 -> G3
 |       ^                     |
 |       +-- changes_requested-+
 |
 +-- HUMAN LOOP (human_rounds < max_human_rounds)
 |     card -> native prompt -> decision
 |
 +-- SUBAGENT LOOP (verifier stop without verdict -> release claim)
 |
 +-- STOP LEASE (same fingerprint count >= max(2, max_attempts/3))
       -> pause + allow stop
```

## 5. 写操作统一判定

```text
claim / gate / transition / stop
              |
              v
      control.status == paused ? --yes--> reject writes; allow stop/report
              |
              no
              v
      budget left? --no--> pause + H2 escalation
              |
              yes
              v
            allow
```

## 6. 预算耗尽与恢复

```text
PM                  Harness                     Human
 |                    |                          |
 | claim/gate ------->|                          |
 |                    | max_attempts reached     |
 |                    | status=paused            |
 |                    | append budget_exhausted  |
 |<-- stop allowed ---|                          |
 | report paused      |                          |
 |                    |<---- budget-grant -------|
 |                    | grants.append, active    |
 |<-- resume ---------|                          |
```

Phase 1 的恢复入口是 `budget-grant` / `abandon` / `accept`；独立的
`budget_exhausted` 卡片可以在后续版本补上，不阻塞当前暂停语义。

恢复命令（人类 native prompt）：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sancai_decide.py" budget-grant \
  --run <run> --field max_attempts --to 15 --reason "human approved"
```

`budget-grant` 只追加 `run.control.grants`，不修改已签 intent。`accept`/`abandon` 在 paused 时仍然可用。

## 7. 进度指纹

```text
fingerprint = sha256(
  run.state + WO states + evidence sha + verdict sha
  + gate result + diff sha + open escalations
  + requirements snapshot + last human decision
)

same fingerprint  -> no_progress_streak += 1
new fingerprint   -> no_progress_streak = 0
streak >= cap     -> paused + allow stop
```

attempt 数本身不属于 fingerprint：重新 claim 不等于产生新事实。

## 8. 实现位置

- `scripts/sancai_control.py`：预算、控制面、fingerprint、pause/observe。
- `scripts/sancai_state.py`：init/claim/transition/wo-transition/event/progress/sign/record-intent/accept/budget-grant。
- `scripts/sancai_gate.py`：deadline、fingerprint、paused apply。
- `scripts/sancai_hook.py`：Stop lease、SubagentStop 无 verdict 释放 claim。
- `scripts/sancai_graph.py`：metrics 暴露 control 状态与剩余预算。
- `tests/test_control.py`：unit + integration。

## 9. 验证

```bash
python3 -m unittest discover -s plugins/sancai-loop-plugin/tests -p 'test_*.py'
python3 plugins/sancai-loop-plugin/tests/pokayoke_audit.py
claude plugin validate ./plugins/sancai-loop-plugin
```

手工：`max_attempts=1` 第二次 claim 被拒绝并 paused；`budget-grant` 后可以继续；连续相同 fingerprint 的 Stop 在第 N 次 pause 并放行。

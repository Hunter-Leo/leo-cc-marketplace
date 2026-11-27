# Run integration and H3 closeout

状态：P0 已实现（v0.12.0-rc.1）。本文记录 run 级集成门 G0-R 与 H3 closeout
事务的设计。

## 问题

改造前：

- 每个 Work Order 单独过 G0/G3，但最后一个 WO 完成后直接 `reviewing`，没有
  run 级集成证据。
- H3 accept 在运行中直接写 `.sancai/project/*`，项目看板和 TODO 可能在人类
  接受之前就被修改。
- accept 中途崩溃会留下孤儿 TODO、已消费卡片、未接受 run。

## 目标状态

```text
H1 planning
  intent + requirements authoring
  planning -> executing
      └─ record project-baseline.json
                 │
                 ▼
L1 executing
  WO loop: claim -> G0 -> G3 -> gate
  captures stage to L2-harness/project-updates.json
  project ledger frozen
                 │
       last WO verified
                 │
       ┌─────────┴──────────┐
       │ no policy          │ policy.required
       ▼                    ▼
   reviewing           integrating
                            │
                  G0-R sancai_integration.py check
                     │                 │
                   pass               fail
                     │                 │
                     ▼                 ▼
                 reviewing      executing + WO-INT-*
                     │
                     ▼
H3 reviewing
  card(closeout_sha)
  accept -> closeout plan -> journal -> consume card
         -> apply requirements/backlog/blueprint
         -> run accepted -> journal committed
```

## 设计决策

1. **新增 `integrating` 而不是复用 `reviewing`**
   G0-R 属于 L2 证据阶段，不是人类验收。人类在 `reviewing` 才介入。
2. **legacy 兼容**
   `integration_policy` 缺失时保留 `executing -> reviewing`。已有 run 不需要迁移。
3. **内容绑定而非 TTL**
   证据绑定 HEAD、worktree、WO 状态、policy hash、intent revision。集成命令
   修改 worktree 即失败。没有“刚跑过所以有效”的时间窗口。
4. **集成返工也是 Work Order**
   G0-R 失败 -> `executing` -> `WO-INT-*`（`req: null`, `kind: integration`）。
   它走同样的 claim/executor/G0/G3，不引入第二套返工机制。
5. **项目账本单点发布**
   `executing/integrating/reviewing` 期间只读；`capture` 写入 staging。
   H3 accept 是唯一发布点。
6. **closeout 用 journal 保证可重放**
   卡片消费不可逆，所以先冻结 `plan.json`，再消费卡片，再幂等 apply。
   crash 后 `closeout resume` 按 journal 继续，不重建 plan，不重新分配 TODO id。
7. **accept card 只绑定 base plan**
   `closeout_sha` 覆盖 selected REQ、staged TODO、integration 证据和 blueprint
   标志，不覆盖 H3 disposition。disposition 在 accept 时提供，不能反过来让
   已渲染卡片失效。
8. **baseline 检测外部漂移**
   planning->executing 记录 requirements/backlog/blueprint 哈希。H3 发现漂移
   即拒绝发布；legacy run 没有 marker 则跳过。
9. **不新增预算参数**
   集成失败重试复用 `max_attempts` 与 no-progress lease；fingerprint 纳入
   integration evidence、project updates、closeout plan。

## 关键文件

```text
scripts/sancai_integration.py   G0-R check/status
scripts/sancai_closeout.py      plan/apply/journal/resume
scripts/sancai_paths.py         integration/closeout/staging paths
scripts/sancai_state.py         integrating transitions, accept transaction
scripts/sancai_gate.py          last-WO auto transition
scripts/sancai_requirements.py  freeze, staging, baseline, blueprint render
scripts/sancai_control.py       progress fingerprint
```

## 边界

- 这是同用户 guardrail，不是 sandbox。
- 多文件发布不是文件系统原子操作；journal 提供幂等重放。
- 集成命令的报告格式不解析；只看 exit code 与 worktree 不变。
- H3 仍然可以对已验证 run 拒绝接受；此时 abandon 后开新 run，已验证 WO 不能
  在旧 run 中重开。

## 后续

- P1：changed-line coverage、H3 EC 卡片。
- P2：baseline registry、per-EC 人工批准、project test-profile。

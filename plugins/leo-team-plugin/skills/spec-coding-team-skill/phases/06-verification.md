# N6 Verification — 集成验收

> 目标：把「评审通过」推进到可审计的「已合并、已验收」。
> 前置：N5 判定无未决；`flow.json.mission=reviewing`；所有实现单元已 `for_review`/`approved`。
> 三态必须按 `approved → merged → verified` 顺序达成，不得跳步或合并声明。

## 1. 三态判定（单元级 + mission 级）

### approved（评审通过）

| 条件 | 判定方式 |
|---|---|
| reviewer `verdict: PASS` | `findings.md` 中对应单元段落末条 verdict |
| `blocker == 0 && critical == 0 && unaccepted_major == 0` | `findings.md` PM 段计数 |
| `auditor=true` 时 `science-audit.md` 无 FAIL / 未说明 UNVERIFIABLE | Verdict 行与检查矩阵 |
| minor/nit 已进 Backlog | `findings.md § Backlog` |

由 reviewer / science-auditor 出具；PM 只汇总。PM 自评 PASS 不算 approved。
单元动作：`flow.sh transition --unit <U-ID> --to approved`。

### merged（已进集成分支）

| 条件 | 判定方式 |
|---|---|
| 分支已合入目标分支 | `git merge --no-ff <branch>` 成功，或 PR 状态为 `MERGED` |
| 无冲突 | 合并命令 exit 0 |
| 目标分支 HEAD 含合并提交 | `git merge-base --is-ancestor <branch> <target>` exit 0 |
| 合并后测试通过 | 在合并后的 HEAD 跑完整测试，exit 0 |

执行人：用户，或获用户明确授权的 PM。teammate 不得 push、不得合并主干（R-8）。
合并前必须有 approved 证据；未 approved 直接合并 → 流程失败。
单元动作：`flow.sh transition --unit <U-ID> --to merged`。

### verified（验收证据齐全）

| 条件 | 判定方式 |
|---|---|
| 每条 AC 都有证据 | `findings.md § PM — Verification Summary` 中 AC ID 与 `init.md` 一一对应 |
| 删除类需求通过负向不变量 | 见第 4 节 |
| 完整测试在合并后 HEAD 通过 | 命令 + exit 0 + 通过数 |
| `check-team-complete.sh` 输出 `OK` | 见第 5 节 |
| 工作区干净 | `git status --porcelain` 为空（`.dev/`、`.team/` 按项目忽略规则处理） |

单元动作：`flow.sh transition --unit <U-ID> --to verified`。
全部实现单元 verified 后：`flow.sh transition --to verified`。

## 2. AC → 证据映射

在 `findings.md` 的 PM 段追加一张表，每条 AC 恰好一行：

| AC | 类型 | 证据 | 位置 | 结果 |
|---|---|---|---|---|
| AC-1 | automated | `npm test -- refresh-store` | `tests/auth/refresh-store.test.ts` | PASS |
| AC-2 | manual | 五要素 | `findings.md#ac-2` | PASS |

规则：

- 禁止用「整体测试通过」代替逐条 AC 映射。
- 自动化证据必须写：测试文件路径、测试名、执行命令、exit code。
- 手工证据必须写全五要素，缺一即视为未验证。
- 缺陷修复类 AC 必须额外记录：基线提交上复现失败的命令与输出、修复后通过的命令与输出。

## 3. 手工证据五要素

| 要素 | 要求 | 反例 |
|---|---|---|
| 1. 命令/操作 | 可直接复制执行，或逐步可复现的操作序列 | 「手动点了下」 |
| 2. 前置状态 | 分支 + HEAD、环境变量、fixtures、账号/权限 | 省略版本与数据 |
| 3. 输入 | 具体请求、文件、参数 | 「用了一些测试数据」 |
| 4. 实际输出 | 原样输出、exit code、截图路径；不得改写 | 「结果正常」 |
| 5. 判定 | 预期 vs 实际，结论 PASS/FAIL | 「看起来没问题」 |

模板：

```markdown
### AC-<n> — <描述>

- 命令: <command>
- 前置: branch=<branch>, HEAD=<sha>, env=<...>, fixture=<path>
- 输入: <request/file/args>
- 实际输出: <verbatim output 或截图路径> / exit=<code>
- 判定: 预期 <expected>；实际 <actual>；结论 PASS
```

## 4. 删除类需求：负向不变量

当 AC 包含「删除/下线/移除/废弃」时，必须同时验证：

| 不变量 | 判定 |
|---|---|
| 符号不存在 | `rg "<symbol>" <源码目录>` 命中数为 0 |
| 入口不可达 | 删除的 HTTP 路由返回 404/410；CLI 参数报 unknown；导出不再存在 |
| 契约同步 | OpenAPI/schema/类型定义不再包含该项 |
| 无静默回退 | 旧配置键不再被读取；默认值未把旧行为重新引入 |
| 消费方已迁移 | 全量 typecheck / build / 契约测试通过 |

示例：删除 `GET /api/v1/users/:id/legacy`

```markdown
### AC-5（删除类）— legacy 端点已下线

- rg: `rg "users/:id/legacy|legacyEndpoint" src/` → 0 hits
- 请求: `curl -i http://localhost:3000/api/v1/users/1/legacy` → HTTP/1.1 404
- 契约: openapi.yaml 中无 `/api/v1/users/{id}/legacy`
- 回退: `LEGACY_USER_API` 配置不再被读取（rg 0 hits）
- 回归: `npm test` → 全部通过
- 判定: PASS
```

只验证「新功能可用」而不验证「旧路径确实消失」→ 该 AC 未通过。

## 5. check-team-complete.sh

脚本读取 `.team/<run>/flow.json`，**永远 exit 0**，结论看输出文本：`OK` / `NOT COMPLETE` / `NO RUN`。

推荐在产物目录内运行，让脚本能找到 `research.md` / `science-audit.md`：

```bash
(
  cd ".dev/<NNN>-<req>/generated"
  LEO_TEAM_DIR="<repo-absolute>/.team/<run>" \
    bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-team-complete.sh"
)
```

脚本机械检查：

| 检查 | 通过条件 |
|---|---|
| mission | `mission=verified` |
| 单元 | 全部实现单元 `lane=verified` |
| researcher | `science_gate.researcher=true` 时 `research.md` 存在 |
| auditor | `science_gate.auditor=true` 时 `science-audit.md` 存在且无 `FAIL`、无未说明 `UNVERIFIABLE` |

脚本不检查 AC 覆盖与五要素；这两项由 reviewer 与 PM 在第 2–4 节人工（可复现）验证。

处理：

- 输出 `OK`：可向用户报告完成。
- 输出 `NOT COMPLETE`：逐条修复；不得手工改脚本、不得删除 `flow.json`。
- 输出 `NO RUN`：检查 `LEO_TEAM_DIR` 与 run 名称；不得伪造状态。
- 因 mission 未 verified 而阻塞：先完成单元 verified 并 `transition --to verified`，再重跑。

## 6. Stop hook 与 PreCompact

Stop hook（`validate-lane-write.sh --stop`）在以下任一成立时拒绝结束：

- `flow.json.mission != verified`；
- `science_gate.auditor=true` 但找不到 `science-audit.md`。

规则：

- 不得通过删除 `flow.json`、改 `mission`、跳过 hook 来绕过。
- 脚本没有「abandon」白名单；未完成时如实向用户报告未完成项，不得伪造成 `verified`。
- `stop_hook_active` 只用于防止重复拦截，不是完成凭证。

PreCompact hook 在 `executing` / `reviewing` 期间要求存在 ≤30 分钟的 checkpoint；压缩前先执行 `flow.sh checkpoint --note "pre-compact"`。

## 7. 执行顺序

1. N5 结论：无未决阻塞项。
2. PM 依据 reviewer 的 PASS 把对应单元推进到 `approved`。
3. 获用户授权后合并分支；在合并后 HEAD 跑完整测试。
4. 每个 approved 单元 → `merged`。
5. 逐条 AC 建立证据；删除类补负向不变量；写入 `findings.md` PM 段。
6. 每个 merged 实现单元 → `verified`。
7. 全部实现单元 verified → `flow.sh transition --to verified`。
8. 运行 `check-team-complete.sh`；输出 `OK` 才可收尾。
9. 向用户报告：分支、合并提交、测试摘要、AC 覆盖数、证据路径。

## 完成标志

- approved / merged / verified 三项证据齐全且可复现。
- `findings.md § PM — Verification Summary` 的 AC 行数 == `init.md` 的 AC 数。
- `check-team-complete.sh` 输出 `OK`，输出已保存。
- `flow.json.mission == verified`。
- 向用户报告包含所有证据的绝对路径。

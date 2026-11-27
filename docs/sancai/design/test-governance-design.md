# Sancai 测试治理设计：覆盖率、预期变更与证据链

- 状态：Implemented 0.11.0-rc.1
- 日期：2026-11-27
- 范围：单仓库、单写者、串行
- 关联：`references/expected-change.md`、`references/verification-standard.md`、`design/loop-design.md`

## 0. 问题

旧 G0 只跑 `intent.acceptance` 和 `hidden_checks`，然后写一个布尔
`success`。这有三个缺口：

1. **覆盖率不在证据链里。** `verification-standard.md` 写了核心逻辑 ≥80%，
   但没有任何脚本执行它。
2. **没有合法的“预期变更”。** 需求、语料或 oracle 真变了时，测试失败是
   正确的；旧流程只说“所有测试必须通过”，于是只剩两条路：改代码迁就旧
   断言，或偷偷改期望值。
3. **测试报告与保护路径没有进入 gate。** verifier 只能看 diff 叙述，无法
   区分回归、预期变化和篡改。

目标：把“什么算通过”从叙述变成可复算的证据，并给合法变更一条显式、
有界、可审计的通道。

## 1. 北极星

```text
代码错       → 改代码
oracle 错    → 改测试，并证明新 oracle 正确
行为真变了   → EC proposal + 独立 oracle + 影响分析 + H3 接受
语料真变了   → corpus EC + science audit + H3 接受
不知道       → blocked / H2，禁止“测试失败就改期望”
```

## 2. 三层数据流

```text
H1 Human
  intent.test_policy          command / report / timeout / coverage
  intent.change_policy        protected_globs / max_changed_files / science
        │
        ▼
L1 Executor                         L2 Harness
  code + tests                        G0
  EC draft ── propose ──►  L1-code/expected-changes/<WO>/EC-*.json
                                      │ freeze
                                      ▼
                              L2-harness/expected-changes/<WO>/manifest.json
                                      │
                              run tests + coverage
                                      │ classify
                                      ▼
                              evidence/<WO>.json
                                tests / coverage / changed_files
                                protected_changes / integrity_violations
                                expected_changes / regressions
                                      │
                                      ▼
                              G3 verifier（fresh）
                                      │
                                      ▼
                              H3 human accepts baseline
```

EC 是 **proposal**，不是 approval。执行者可以提交，不能批准；approval 来自
H1 签过的 `change_policy`，最终由 H3 接受新 baseline。

## 3. `test_policy`

```json
{
  "test_policy": {
    "command": "python3 tools/run_tests.py --report .sancai/runs/<run>/L2-harness/test-report.json",
    "report": ".sancai/runs/<run>/L2-harness/test-report.json",
    "timeout_seconds": 1800,
    "coverage": {
      "command": "python3 tools/run_coverage.py --report .sancai/runs/<run>/L2-harness/coverage.json",
      "report": ".sancai/runs/<run>/L2-harness/coverage.json",
      "core_globs": ["src/core/**"],
      "minimum_core_percent": 80,
      "enforce": true
    }
  }
}
```

规则：

- test command 与 coverage command 分开执行。不能用 `&&` 把两者串起来，
  否则测试失败会阻止覆盖率报告生成。
- `report` 必须在 `.sancai/runs/<run>/L2-harness/` 下；L1 路径可被 executor
  改写，不能作为证据。
- P0 只支持 JSON 报告。`id`/`nodeid`、`outcome`/`result` 都接受。
- 报告格式错误、超时、命令失败但没有结构化报告 → fail closed。
- 覆盖率按 `core_globs` 命中文件的语句数加权；核心文件缺失按 0% 计。
- 旧 intent 没有 `test_policy` 时，evidence 不新增任何 key。

## 4. `change_policy` 与 EC

```json
{
  "change_policy": {
    "expected_change_allowed": true,
    "protected_globs": ["tests/golden/**", "corpus/**"],
    "max_changed_files": 20,
    "science_audit_above": 0,
    "baseline_id": "corpus-2026-01",
    "require_rollback_plan": true
  }
}
```

EC 必填字段：

```text
id, wo, type, reason, ac, scope, affected_cases,
oracle, oracle_ref, backward_compatible
```

`type ∈ {behavior_change, oracle_fix, corpus_rebaseline}`；
`oracle ∈ {exact, semantic, property, statistical, human}`。

关键约束：

- `scope` 必须落在 `protected_globs` 内。
- `affected_cases` 不是自报数，而是 `len(scope ∩ changed_protected_files)`。
  少报 → integrity violation；多个 EC 覆盖的受保护文件并集超过
  `max_changed_files` → blocked。
- 每个 protected change 必须被至少一个 EC 覆盖；未覆盖 → blocked。
- EC 不能写 `approved` / `approved_by` / `approved_at`。
- `corpus_rebaseline` 或 EC 数量达到 `science_audit_above` → science audit
  必填，且 audit 必须列出同一组 EC id。

## 5. Freeze 与防篡改

```text
first G0:
  live L1 EC ──hash──► manifest.json (L2)
  manifest ──────────► evidence.expected_change_manifest_sha

later G0 / gate:
  live L1 EC ──compare──► frozen manifest
        equal? ── yes ──► run G0
                └─ no  ──► blocked: expected changes differ
  evidence.manifest_sha ──compare──► frozen manifest
        equal? ── yes ──► continue
                └─ no  ──► blocked: manifest hash drift
```

G0 会重跑，所以不能在重跑后拿“新 evidence”与“旧 live EC”比较；必须先比较
live L1 与冻结 manifest，再重跑，再比较 evidence 中的 manifest sha。`accept`
也会重新检查 frozen manifest，防止 gate 之后被改。

## 6. Gate 全序

```text
1  intent 签名 / snapshot（G0 前）            blocked
2  live EC vs frozen manifest（G0 前）        blocked
3  重跑 G0
4  intent 签名 / snapshot（G0 后）            blocked
5  evidence.manifest_sha vs frozen            blocked
6  integrity_violations 非空                  blocked
7  verifier attestation / deadline / 硬错误   blocked
8  science 必填但缺失或不可验证               blocked
9  science audit fail                         changes_requested
10 acceptance / hidden checks 失败            changes_requested
11 unclassified / regression / stale          changes_requested
12 coverage enforce 且低于阈值                changes_requested
13 verifier fail / blocker findings           changes_requested
14 全部通过 + verifier pass                   verified
```

`blocked` 是 H2 路径；`changes_requested` 是返工路径。protected diff 没有 EC
必须是 `blocked`，不能因为 `evidence.success=false` 就降级成普通返工。

## 7. Evidence 兼容性

旧 intent 的 evidence 必须字节级不变，包括 `evidence_sha`：

```text
test_policy 存在     → 才写 tests / coverage
change_policy 存在   → 才写 changed_files / protected_changes /
                        integrity_violations / expected_changes /
                        expected_change_manifest_sha / regressions /
                        science_required
```

这样旧 verdict 仍能通过；新字段只在有 policy 的 run 中出现。

## 8. 角色边界

| 角色 | 能做 | 不能做 |
|---|---|---|
| PM | 声明 test/change policy；派发；读 evidence | 替 verifier 判 EC；替 human 接受 baseline |
| Executor | 写代码/测试；提交 EC proposal | 写 `.sancai/**`；批准 EC；静默改期望 |
| Verifier | 检查 traceability/scope/oracle/impact/rollback | 改代码；读 executor 叙述 |
| Science auditor | 审语料/统计/数值合法性；绑定 EC ids | 改代码；批准 EC |
| Human | 签 policy；H3 接受新 baseline | 被跳过 |

## 9. P0 范围与后续

P0 已实现：

- `test_policy` command/report/timeout/coverage；
- `change_policy` protected globs / max files / science threshold / rollback；
- EC propose、G0 freeze、gate compare、accept recheck；
- expected/unclassified/stale 分类；
- verifier 11–19 检查；
- 旧 evidence 兼容；
- `sancai_change.py` 进入 harness allowlist，但不开放 `.sancai` 写权限。

P1：

- changed-line coverage；
- H3 EC 卡片；
- verdict 中 per-EC 审计块；
- 覆盖率报告从测试命令中自动提取。

P2：

- 跨 run baseline registry；
- 每个 EC 的独立人工批准；
- 统计/属性测试工具；
- 项目级 test-profile。

## 10. 已知边界

- 本插件不是 sandbox。P0 防的是流程内误操作与自欺，不是同用户恶意绕过。
- `changed_files` 使用 `git diff HEAD`。流程要求每个 WO 验证后提交，因此
  下一个 WO 不会重复计入上一个 WO 的改动；未提交的跨 WO 改动会重复出现。
- 覆盖率是地板，不是质量证明；verifier 仍检查断言质量与负向测试。

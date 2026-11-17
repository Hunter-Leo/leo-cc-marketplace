# Team Plan

> 用途：PM 独占的团队执行计划，teammates 只读。对应 essence I-2（文档即状态）、I-3（硬门禁）、I-4（禁止静默偏离）。
> 复制本文件到本次 run 目录后逐项填空；未填完不得进入 Phase B。

## Run / Round / Branch / Mission state

| Field | Value |
|---|---|
| run_id | <如 20261116-auth-refactor> |
| round | <N> |
| branch | <如 feat/001-auth-refactor，由 flow.sh init 生成> |
| base_ref | <如 main @ <commit-sha>> |
| mission_state | <planning \| gate \| executing \| reviewing \| verified \| blocked> |
| phase_a_confirmed | <yes \| no> |
| created_at | <YYYY-MM-DD HH:MM> |
| updated_at | <YYYY-MM-DD HH:MM> |

## Science gate

| Role | Required | Owner | Artifact | Status |
|---|---|---|---|---|
| researcher | <yes \| no> | <name> | research.md | <pending \| done \| skipped> |
| auditor | <yes \| no> | <name> | science-audit.md | <pending \| PASS \| FAIL \| UNVERIFIABLE> |

- 触发 researcher 的条件：<涉及算法/公式/外部事实/需要引用来源时填 yes>
- 触发 auditor 的条件：<结论依赖研究产物或数值正确性时填 yes>
- gate 未通过时：<禁止进入实现 / 仅允许哪些单元先开始>

## 工作单元表

| ID | Owner | Archetype | owned_files | Objective | Output | Source guidance | Scope boundary |
|---|---|---|---|---|---|---|---|
| U-01 | <name> | <只协调 \| 能跑 \| 可反驳 \| 有出处 \| 讲得通 \| 有模式 \| 能用> | <path/a.ts, path/b.ts> | <一句话目标> | <path/to/artifact> | <essence I-x / rails R-x / research R-n> | <明确不做什么> |
| U-02 | <name> | <archetype> | <paths> | <目标> | <产物> | <依据> | <边界> |

## 工作单元详情

### U-01 <标题>

- **Owner**: <name>
- **Archetype**: <implementer>
- **owned_files**（写边界，必须精确到文件或目录）:
  - <path/a.ts>
  - <path/tests/a.test.ts>
- **Objective**: <可验收的一句话>
- **Output**: <产物路径>
- **Source guidance**: <必须遵守的上游条目，如 essence.md I-5、research.md R-2>
- **Scope boundary**: <不在本单元范围内的事项>
- **Definition of done**:
  - [ ] <验收标准 1>
  - [ ] <验收标准 2>
  - [ ] <完整验证命令及预期结果>
- **启动 prompt 全文位置**: `<run 目录>/prompts/U-01.md`
  - 该文件必须含：角色定义、owned_files、Objective、Source guidance、回传契约（rails R-10）
  - 该文件不存在时，本单元不得启动

### U-02 <标题>

- **Owner**: <name>
- **Archetype**: <archetype>
- **owned_files**:
  - <paths>
- **Objective**: <一句话>
- **Output**: <产物路径>
- **Source guidance**: <上游条目>
- **Scope boundary**: <边界>
- **Definition of done**:
  - [ ] <验收标准>
  - [ ] <验证命令及预期结果>
- **启动 prompt 全文位置**: `<run 目录>/prompts/U-02.md`

## 调度判定

> 实现单元一律串行（`flow.sh` 全局单 claim）。本节只记录实现顺序与只读重叠安排。

- 实现顺序：<U-01 → U-02 → U-03>
- 只读重叠：<reviewer 在 U-01 进入 for_review 后开始；explorer 可在 executor 工作时并行读取>
- 串行依赖：<U-03 依赖 U-01 的输出 <path>>
- 写集冲突：<U-04 与 U-05 均写 <shared.ts>，已合并为同一单元或改为串行>
- `check-lanes.sh` 结果：<OK / WARN 并列出人工确认>
- 结论：<本 round 无并行写；只读重叠 N 处>

## 检查点安排

| Checkpoint | After | 触发者 | 检查内容 | 未通过时 |
|---|---|---|---|---|
| CP-1 | <U-01 完成> | <PM> | <构建/测试命令及阈值> | <停止并记入 findings.md> |
| CP-2 | <检查点组全部完成> | <spec-reviewer> | <验收标准覆盖情况> | <回退到对应单元> |
| CP-3 | <science audit 完成> | <PM> | <PASS 且证据齐全> | <不得合并> |

## 确认记录

- 用户确认时间：<YYYY-MM-DD HH:MM>
- 用户确认原文：`<逐字引用用户消息>`
- 确认内容：Phase A 计划（工作单元划分、调度判定、检查点）已确认，可进入 Phase B
- 记录人：<PM name>
- 备注：<用户附加条件；无则写「无」>

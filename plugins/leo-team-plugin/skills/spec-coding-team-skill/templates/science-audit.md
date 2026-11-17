# Science Audit

> 用途：独立验证研究结论与数值正确性的审计记录，由 auditor 独占写入。
> auditor 不参与实现，也不读实现者的推理过程，只看产物与证据（essence I-5）。
> 发现问题以 `F-AUD-*` 记入 findings.md，不在本文件展开讨论。

## 元信息

| Field | Value |
|---|---|
| audit_id | <AUD-001> |
| auditor | <name> |
| round | <N> |
| scope | <被审对象：research.md R-x / 模块路径> |
| audited_at | <YYYY-MM-DD HH:MM> |

## 1. 脚本先行区

先跑确定性脚本，再人工判断。逐条记录实际命令与退出码，不得只写「已运行」。

| # | 脚本 / 命令 | 输入 | Exit code | 关键输出 | 结果 |
|---|---|---|---|---|---|
| 1 | <如 uv run pytest tests/science -q> | <路径> | <0> | <N passed> | <PASS \| FAIL> |
| 2 | <如 python scripts/check_units.py> | <路径> | <0> | <all units consistent> | <PASS \| FAIL> |
| 3 | <如 python scripts/verify_formula.py> | <路径> | <1> | <mismatch at term 3> | <FAIL> |

- 未跑脚本的原因：<无 / 说明为什么不可能跑>
- 脚本本身的可信度问题：<无 / 说明>
- 跳过的检查：<无 / 跳过了什么及原因（rails R-6）>

## 2. 检查矩阵

固定五项，不得增删。

| 检查项 | 方法 | 结果 | 证据 |
|---|---|---|---|
| 算法/公式符合性 | <逐式对照来源与实现位置> | <PASS \| FAIL \| UNVERIFIABLE> | <file:line / 来源页码> |
| 量纲与单位 | <逐量纲推导 / 单位检查脚本> | <PASS \| FAIL \| UNVERIFIABLE> | <命令输出 / file:line> |
| 语料代表性 | <样本来源、规模、覆盖面> | <PASS \| FAIL \| UNVERIFIABLE> | <数据路径 / 统计量> |
| 结论可支撑性 | <结论 → 证据逐条映射> | <PASS \| FAIL \| UNVERIFIABLE> | <research.md R-n> |
| 与文献一致性 | <与来源数值或定性结论对比> | <PASS \| FAIL \| UNVERIFIABLE> | <DOI / URL> |

## 3. UNVERIFIABLE 说明

判定为 UNVERIFIABLE 的检查项必填，缺一即视为审计未完成。

| 检查项 | 为什么无法验证 | 需要什么证据 | 谁可提供 |
|---|---|---|---|
| <检查项> | <具体原因> | <证据形式与来源要求> | <role / user> |

## 4. 最终结论

- **Verdict**: <PASS | FAIL | UNVERIFIABLE>
- 通过项：<列出检查项>
- 未通过项：<列出检查项 + 对应 findings ID>
- 是否阻塞进入下一阶段：<yes \| no，附一句理由>
- auditor 签署：<name> @ <YYYY-MM-DD HH:MM>

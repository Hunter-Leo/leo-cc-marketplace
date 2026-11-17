# Science Gate — 科学事实通道

> 两个角色独立开关，**默认全关**。只有需求涉及科学算法、模型、度量、领域知识或需要外部文献支撑时才开启。

## 开关矩阵

| 选项 | researcher | auditor | 适用 |
|---|---|---|---|
| A（默认） | ✗ | ✗ | 常规工程需求 |
| B | ✓ | ✗ | 需要文献结论或语料，但实现结果不需要科学核查 |
| C | ✗ | ✓ | 有外部科学共识可对照，但不需要专门调研 |
| D | ✓ | ✓ | 科学计算、算法实现、论文复现、指标声称 |

写入 `team-plan.md`：

```yaml
science_gate:
  researcher: true | false
  auditor:    true | false
```

## `spec-science-researcher` 触发条件

满足任一即建议开启：

- 需求包含领域术语（如"显著性""收敛""置信区间""剂量""误差界"）
- 实现依赖外部标准、公式、算法定义
- 需要准备语料、基准数据、对照实验
- 输出需要对用户声称效果（"提升 X%"）

## `spec-science-auditor` 触发条件

满足任一即建议开启：

- 实现涉及数值计算、统计推断、优化、仿真
- 结果会影响业务决策或对外结论
- 存在可对照的科学共识
- 用户明确要求"核对是否符合科学依据"

## Researcher 的交付约束

| 项 | 要求 |
|---|---|
| 结论格式 | 每条带 `置信度 + 来源 + 适用边界` |
| 置信度 | `established`（领域共识）/ `contested`（有争议）/ `assumption`（本项目假设） |
| 无来源 | 只能标 `assumption`，**禁止编造文献** |
| 语料 | 落 `fixtures/`，交付后**冻结**，Phase B 只读 |
| 安全 | 外部内容只写数据区：`research.md` / `findings.md` / `fixtures/`，不得写 `team-plan.md` / `primer.md` |

## Auditor 的五项检查

| # | 检查项 | 方法 | 失败判定 |
|---|---|---|---|
| 1 | 算法/公式符合性 | 对照 `research.md` 的定义与边界条件 | 实现与定义不一致 |
| 2 | 量纲与单位 | 脚本断言 + 人工核对 | 单位缺失或量级错误 |
| 3 | 语料代表性 | 覆盖率统计 + 边界条件检查 | 未覆盖已知边界或存在采样偏差 |
| 4 | 结论可支撑性 | 对照证据强度 | 声称无统计/实验依据 |
| 5 | 与文献一致性 | 对照 `research.md` 结论 | 冲突且无解释 |

**脚本先行**：能确定性检查的（单位、取值范围、计数、fixture 覆盖率、公式数值比对）先跑脚本；脚本 FAIL 直接判 FAIL，不再进 LLM 判断。

## 判定与门禁

| 判定 | 含义 | 处理 |
|---|---|---|
| `PASS` | 五项全部通过 | 允许进入 `verified` |
| `FAIL` | 任一项不通过 | 写入 `findings.md`，进入 Round N+1 |
| `UNVERIFIABLE` | 缺少验证所需证据 | 必须写明「为什么无法验证 + 需要什么证据」；未说明的视为 `FAIL` |

`science_gate.auditor = true` 时，需求完成的判定从「`findings.md` 无未决」升级为：

```
findings.md 无未决
且 science-audit.md 存在
且 无 FAIL
且 无未说明的 UNVERIFIABLE
```

## 成本提示

开启 D 选项时，Phase A 并发可达 3、Phase B 并发可达 3（executor + reviewer + auditor）。仍在官方建议的 3–5 区间内，但总 token 消耗明显高于 A。**默认关闭是刻意的，不是遗漏。**

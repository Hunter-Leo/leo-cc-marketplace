# Progress

> 用途：按人记录可观察动作的时间线，供 PM 与恢复会话的 teammate 判断进展。
> **只追加，不重写。** 旧行错误时追加一条更正行，在 Result 写 `corrects: <原时间>`，不得删除或编辑旧行。
> 一行 = 一次可观察动作；时间使用固定时区并全文件一致。

## <owner-1>

| Time | Actor | Unit | Action | Result |
|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | <name> | <U-01> | <读取上游 / 开始实现 / 运行测试 / 提交 / 回传> | <PASS \| FAIL \| BLOCKED + 一句话证据> |

## <owner-2>

| Time | Actor | Unit | Action | Result |
|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | <name> | <U-02> | <动作> | <结果> |

## <owner-3>

| Time | Actor | Unit | Action | Result |
|---|---|---|---|---|
| <YYYY-MM-DD HH:MM> | <name> | <U-03> | <动作> | <结果> |

## 汇总（PM 维护，追加式）

| Round | 单元总数 | PASS | FAIL | BLOCKED | 备注 |
|---|---|---|---|---|---|
| <N> | <n> | <n> | <n> | <n> | <一句话> |

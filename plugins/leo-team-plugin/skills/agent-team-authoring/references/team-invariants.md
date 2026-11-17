# 团队级 5 条不变量

> 六条流程不变量（essence.md）管"流程怎么走"；这五条管"团队运行时不能破什么"。
> 每条都必须能被机械检查——不能被脚本检查的条目，写到 `enforcement-ladder.md` 的"文本层"并承认它只是提醒。

---

## T-1 files over context

**规则**：agent 之间不共享记忆，只共享文件。没有落盘 = 没有发生。

- 决策、偏差、排除方案、接口假设，全部写进文件。
- "我刚才在消息里说过"不构成下游可用的输入。
- mailbox 只传路径 + 一句话结论，不传内容（rails.md R-2）。

**违反后果**：跨 session 恢复时事实消失；两个 teammate 对同一接口有不同记忆且都自认为正确；评审无法复核上游依据。

**机械检查**：

```bash
# 每个被引用的事实，其路径是否存在且非空
for p in $(jq -r '.facts[]' .dev/state/facts.json); do
  test -s "$p" || echo "MISSING: $p"
done
# mailbox 中单条消息体 > 2KB 视为违规（应改为传路径）
```

---

## T-2 own your files

**规则**：只能写自己 `Lane` 段声明的路径；不得编辑其他角色的产物。

- 并行安全只看**写文件集合是否相交**，与角色名无关。
- 两人写同一文件时，后写者覆盖前者且不会报错——这是最隐蔽的数据丢失。
- 共享文件（`findings.md`、`decisions.md`）必须指定唯一所有者，其他人只读或通过所有者追加。

**违反后果**：静默覆盖、产物版本不可追溯、评审看到的是被他人改过的"作者产物"。

**机械检查**：并行派发前跑一次集合相交检查。

```bash
# 本插件流程：直接校验 .team/<run>/flow.json 中所有单元的 owned_files
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh"        # 存在确定相交 → exit 1
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-lanes.sh" --json # 机器可读

# 非本插件项目：把 lane 写成 {"builder-a": ["src/a/**"], "builder-b": ["src/b/**"]}，
# 用任意集合相交检查（两两展开后求交集，非空即 exit 1）
```

hook 侧：`PreToolUse` 读当前角色的 lane，路径不在其中直接拒绝（rails.md R-4）。

---

## T-3 liveness is receipt

**规则**：**只有本次 session 的 SendMessage 回执算"还活着"。**

以下都**不算**活着的证据：

| 看起来像证据 | 为什么不算 |
|---|---|
| 磁盘上的产物文件 | 可能是它上次 session 写的，也可能是别人写的 |
| 旧 inbox / mailbox 里的消息 | 历史记录，不反映当前进程状态 |
| registry 里的 `status: running` | 上一次写入后没有心跳更新，是陈旧快照 |
| 日志最后一行是几秒前 | 可能是空闲等待，也可能是已经结束 |

唯一有效证据：**本次 session 内，向该 teammate 发送 SendMessage 并收到回执**。没有回执 = 视为 dead，按 dead 处理（重新 spawn 或降级任务）。

**违反后果**：向已死的 teammate 派任务，任务永远停在 `in_progress`；或向一个停止响应的 teammate 累积消息，恢复时全部丢失。

**机械检查**：每次派发前先 ping。

```text
1. SendMessage(to: <name>, "ping") 
2. 超时（建议 30s）无回执 → 标记 dead，不进入 pending
3. 有回执 → 才允许派发
```

注意：这条规则的成本是每次派发多一次往返。它买到的是"不会把工作交给不存在的人"。

---

## T-4 keep checkpoint

**规则**：每个 work unit 结束（无论 PASS / FAIL / BLOCKED）都必须写快照，内容固定四项：

```yaml
unit: <id>
state: <转移后的状态>
done: [已完成的可验证事项]
open: [未决问题，含 owner]
next: <下一步动作，含接收者>
```

**违反后果**：session 中断后无法判断哪些工作已完成；恢复时重复劳动或漏掉未决项；"我以为它做完了"。

**机械检查**：

```bash
# 每个非终态 unit 必须有快照，且最新快照不早于该 unit 最近一次状态变更
bash "${CLAUDE_PLUGIN_ROOT}/scripts/flow.sh" checkpoint --note "unit <id> done"
ls -t .team/<run>/snapshots/*.json | head -1     # 取最新快照，与 flow.json.events 末尾时间比对
```

---

## T-5 lead coordinates

**规则**：团队级决策只有 lead 能做——切分方式、角色数量、是否进入下一轮、是否升级用户裁决。

teammate 可以提议、可以否决、可以上报，但**不得自行改变团队结构**。

**违反后果**：两个 agent 各自调整切分，导致职责重叠或出现无人负责的缺口；门禁被 teammate 代问，用户确认的对象发生错位（essence.md I-3）。

**机械检查**：

- `team-plan.md` / `tasks.md` / `decisions.md` 的写权限只授予 lead；其他角色 `PreToolUse` 直接拒绝。
- 派生角色（teammate 自行 spawn 的 agent）一律视为无 coordination 权限，其产出必须回传给 lead 再入计划。

---

## 五条之间的关系

| 如果破了 | 会连锁导致 |
|---|---|
| T-1 | T-4 的快照没有依据，T-5 的裁决无法复核 |
| T-2 | T-1 的文件不可信（不知谁写的），评审 T-3 无法定位责任人 |
| T-3 | 任务分配给死进程，T-4 的 `open` 永久悬挂 |
| T-4 | T-3 无法判断谁是 dead，T-5 无法决定下一步 |
| T-5 | 切分任意变化，T-2 的 lane 声明失效 |

五条不是清单，是一个环路：任何一条破了，检查其余四条时都会出现假信号。

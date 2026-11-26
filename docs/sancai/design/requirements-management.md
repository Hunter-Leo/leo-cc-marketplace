# Sancai 需求管理设计：项目账本 + Run 意图快照

- 状态：Implemented v0.10.0-rc.4
- 日期：2026-11-25
- 范围：单仓库、单写者、串行（与 MVP 一致）
- 代码：`plugins/sancai-loop-plugin/scripts/sancai_requirements.py`

---

## 0. 问题

AITL 把一次 run 的意图（goal / AC / budget）冻结在 `intent.json` 里，但没有回答：

1. 跨 run 的需求放在哪？
2. 执行中发现的新需求，哪些属于当前 run，哪些不属于？
3. 不属于当前 run 的需求，如何记录而不打断执行？
4. H3 接受时，如何证明本次 run 覆盖了它声称覆盖的需求？

`spec-coding-skill` 用 `.dev/blueprint.md`（全部需求索引）、`.dev/TODO.md`
（跨需求 backlog）和每个需求的 `init.md` / `issues.md` 回答这些问题。Sancai
沿用它的核心区分，但把权威从 Markdown 移到 JSON 账本，并让人机权限、状态机
和证据链保持一致。

---

## 1. 核心区分

| 概念 | 含义 | 谁写 | 能否直接进入 run |
|---|---|---|---|
| `TODO-*` | 原始捕获：可能是 bug、改进、无关发现、模糊想法 | Agent 可 `capture` | 不能 |
| `REQ-*` | 已接受、有验收标准、可规划的需求 | 人 `promote` + `accept` | 能，且只能由人选择 |
| Run intent | 本次 run 覆盖的 REQ 快照 | Agent `select`，人 `sign` | — |

一句话：

```text
TODO 是“记下来”；REQ 是“决定做”；intent 是“这次做这些”；WO 是“这样验证”。
```

捕获不等于承诺，承诺不等于当前迭代。这个区分是需求管理的全部价值。

---

## 2. 账本

```text
.sancai/
├── project/
│   ├── requirements.json   REQ-* 的唯一事实源
│   ├── backlog.json        TODO-* 的唯一事实源
│   └── blueprint.md        生成视图，不参与判定
└── runs/<run>/
    └── L3-intent/intent.json   requirements[] + revision
```

### 2.1 `requirements.json`

```json
{
  "schema_version": 1,
  "next_req": 2,
  "requirements": {
    "REQ-001": {
      "id": "REQ-001",
      "title": "rotate refresh tokens",
      "status": "accepted",
      "priority": "P1",
      "acceptance": [{"id": "AC-1", "text": "old refresh token is rejected"}],
      "source": "TODO-001",
      "depends_on": [],
      "notes": "",
      "history": [{"ts": "...", "event": "accepted", "meta": {}}]
    }
  }
}
```

`acceptance` 是硬门槛：没有可检查的验收标准，就不能 `accept`，也就不能进入
任何 intent。

### 2.2 `backlog.json`

```json
{
  "schema_version": 1,
  "next_todo": 2,
  "items": {
    "TODO-001": {
      "id": "TODO-001",
      "title": "unbounded retry in webhook",
      "type": "finding",
      "priority": "P1",
      "status": "pending",
      "relation": "unrelated",
      "source": "run:001-auth/WO-002",
      "req": null,
      "notes": "",
      "history": [{"ts": "...", "event": "captured", "meta": {}}]
    }
  }
}
```

`source` 让每个 TODO 可回溯到发现它的 run / WO / 人工输入；`relation` 区分
`related` 与 `unrelated`，但它不改变状态，只作为人 triage 的提示。

---

## 3. 状态机

### 3.1 TODO

```text
pending ──► promoted   （人 promote 成 REQ）
   │  ▲
   │  └──── deferred   （人决定暂不做，之后仍可 promote）
   ├──────► deferred
   └──────► rejected   （人决定不做）
```

`promoted` 不是终态：TODO 保留，作为 REQ 的来源记录。所有状态迁移只追加
`history`，不删除条目。

### 3.2 REQ

```text
proposed ──► accepted ──► in_progress ──► verified
    │            │
    │            ├──► deferred
    │            └──► rejected
    └──► rejected
```

Phase 1 实现 `proposed / accepted / deferred / rejected` 的 CLI；`in_progress /
verified / superseded` 预留给 Phase 2 的需求级投影。当前 run 的完成度由 Work
Order 证据决定，不由需求状态自报。已签名的活跃 run 选中的 REQ 不允许被
`defer`/`reject`。

### 3.3 Run intent snapshot

```text
unsigned planning intent
        │  select --req REQ-001
        ▼
requirements=[REQ-001], revision=1
        │  sign
        ▼
signed intent（选择冻结；改需求必须重签）
```

`revision` 每次 `select` 自增。签名后 `select` 被拒绝，避免“执行中偷偷扩
需求”。

---

## 4. 人机权限

| 动作 | Agent | Human | 说明 |
|---|---|---|---|
| `capture` | ✅ | ✅ | 记录发现，不改变任何 run |
| `list` / `status` / `blueprint` | ✅ | ✅ | 只读 |
| `select --run --req` | ✅ | ✅ | 只写 planning 且未签名的 intent |
| `promote` | ❌ | ✅ | TODO → REQ proposed |
| `accept` | ❌ | ✅ | REQ proposed → accepted |
| `defer` / `reject` | ❌ | ✅ | 需求 triage |

实现方式：`sancai_capability.py` 的 `HUMAN_DECISION_COMMANDS` 把人决策命令
从 Agent 的 Bash 白名单中拒绝；`sancai_requirements.py` 内部再校验状态机。
两层都 fail-closed。

---

## 5. 捕获点

| 时点 | 谁捕获 | 典型 `source` | 处理 |
|---|---|---|---|
| H1 意图对齐 | Agent | `human:<session>` | 与本 run 无关就 `unrelated` 捕获，继续 H1 |
| 执行中发现 | Agent | `run:<run>/WO:<wo>` | 相关但超出 `owned_files`：捕获后继续；需要现在做则升级 H2 |
| H3 接受 | Agent / Human | `run:<run>/WO:<wo>` | `defer:<WO-ID>` 自动捕获 finding |
| run 结束后 | Human | `run:<run>` | 人工补录，进入 backlog |

关键规则：**捕获不授权动作**。任何捕获都不改变当前 intent、不扩大
`owned_files`、不新增 Work Order。

---

## 6. Work Order 绑定

Intent 有 `requirements` 时：

```bash
sancai_state.py add-wo --id WO-001 --files a.txt --reversible true --req REQ-001
```

- `--req` 必填；
- 必须属于 intent 的 `requirements[]`；
- 一个 WO 只绑定一个 REQ；
- 一个 REQ 可以由多个 WO 覆盖。

Intent 没有 `requirements`（legacy）时，`--req` 省略，行为与旧版一致。

---

## 7. H3 验收

接受前，harness 计算 coverage：

```text
for each REQ in intent.requirements:
    exists WO where wo.req == REQ and wo.state in {verified, merged}
```

任一 REQ 没有已验证的 WO，`accept` 在消耗卡片之前失败：

```text
requirement has no verified work order: REQ-002
```

这防止“只做了一部分，但 H3 照样接受”。

### 7.1 major finding 的 defer

旧行为在已接受的 run 里新建 `pending` WO，产生永远不会执行的死条目。新行为：

```bash
sancai_state.py accept ... --disposition defer:WO-003
```

写入 `.sancai/project/backlog.json`：

```json
{
  "type": "finding",
  "priority": "P1",
  "status": "pending",
  "relation": "related",
  "source": "run:001-auth/WO-003"
}
```

`acceptance.captured_todos` 与卡片都会展示它。人之后决定 `promote` 或
`reject`。

---

## 8. 卡片与可观察性

- intent 卡片：`What: ... Requirements: REQ-001 (revision 2)`。
- accept 卡片：`Requirement coverage: REQ-001: WO-001, WO-002`，以及
  `Out-of-scope captured: TODO-003`。
- graph：Work Order 节点带 `req`；intent 摘要带 `requirements` / `revision`；
  顶层带 `captured_todos`。

图只反映状态，不参与判定；判定仍由 `sancai_state.py` 和 gate 完成。

---

## 9. 为什么 Phase 1 不做 CR

执行中修改当前 intent（change request）需要：新 revision、重新签名、重新评估
已完成的 WO 是否仍然有效、以及回滚语义。它会把“执行中”变成新的审批阶段，
超出单写者 MVP。Phase 1 用 `capture` + H2 升级覆盖 80% 场景；真正的 CR 在
Phase 2 连同依赖图与里程碑一起设计。

---

## 10. 兼容与迁移

- 无 `.sancai/project/` 时：`add-wo` 不需要 `--req`，`accept` 不做 coverage
  检查，旧 run 可继续。
- 有账本但 intent 无 `requirements`：仍按 legacy 处理；`select` 才会开启强制。
- 账本只追加，不删除；`blueprint.md` 可随时从 JSON 重新生成。
- 版本：`0.10.0-rc.4`。

---

## 11. 验收标准

1. `capture` 不改变 intent / run / WO。
2. `promote` 无 `--acceptance` 被拒绝。
3. `select` 只能选 `accepted`，只能在 `planning`，签名后拒绝。
4. 有 requirements 时，`add-wo` 缺 `--req` 或跨 REQ 被拒绝。
5. H3 对未覆盖 REQ 拒绝接受，且不消耗卡片。
6. `defer:<WO-ID>` 只写 backlog，不新建 WO。
7. legacy run 的 80 个既有测试全过。
8. `sancai_requirements.py` 的 `promote/accept/defer/reject` 被 Agent 能力表
   拒绝，被 Human 允许。

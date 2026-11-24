# 人类侧防呆设计（Human-side Fool-proofing v2）

> 状态：设计稿 v0.1 · 2026-11-19
> 范围：`plugins/sancai-loop-plugin` 的人类决策面（H1 签署 / H2 审批 / H3 验收）
> 目标：让「人批错、批快、批疲劳、被伪造卡片误导」从“靠自觉”变成“有机制、有记录、可拒绝”。

---

## 0. 结论

人类侧防呆不是一道门，而是四层：

```text
L1 注意力层   一次一个决策、风险分级、冷却、注意力预算
L2 真实性层   卡片 ID / hash / MAC、短期码、过期与重放拒绝、人可自行 verify
L3 确认层     findings 逐项处置、重大发现必须 defer/waive、接受留痕
L4 人证层     TTY 人跑、GPG/SSH 签名、OS 生物识别、双人复核
```

默认策略：

```text
T0 可逆低危     agent + verifier，无人
T1 可逆高影响   通知 + 可批量；不进入令牌
T2 不可逆低爆炸 卡片绑定 + 明确词 + 3s dwell + 一次性 token
T3 不可逆高爆炸 上述 + 人跑 TTY（GPG 可选）+ 60s 冷却 + 双人（建议）
T4 受监管      独立机器/独立用户 + 硬件密钥 + 双人
```

核心原则：

```text
1. 默认不批准；批准必须绑定「哪张卡、哪个快照、哪个动作」。
2. 不可逆动作必须用词，不用数字；必须有人跑的动作，agent 不能代跑。
3. 拒绝也要记录理由；沉默不是拒绝，也不是同意。
4. 非阻塞 findings 不能被静默吞掉：要么 defer，要么 waive 并写理由。
5. 人证不是“session id”，是 TTY / 签名 / 生物识别 / 第二个人。
```

---

## 1. 威胁模型

| 编号 | 角色 | 能力 | 设计目标 |
|---|---|---|---|
| H1 | 赶时间的人 | 会点错、会只看标题、会连续批准 | 用摩擦与预算降低误批 |
| H2 | 跑偏的 agent | 会伪造卡片文本、跳过卡片、催促人批准 | 卡片绑定 + 脚本校验 + 明确词 |
| H3 | 被攻陷的 agent | 同用户，能读环境变量、能跑脚本 | 高危险层用 agent 无法代跑的人证 |
| H4 | 恶意仓库 | prompt injection、假测试、假 diff | capability + evidence + 人工复核 |
| H5 | 重放/过期 | 拿旧卡片、旧 diff、旧 token 再次使用 | 卡 ID / hash / used_at / TTL |
| H6 | 多人/代理 | 第二个人、审批代理、交接 | 双人签名 + 决策记录 |

非目标：被攻陷的操作系统、物理胁迫、nation-state、恶意硬件。

---

## 2. 风险分级

风险不是动作动词，而是动作属性：

```text
reversible        能否用 git revert / 备份完整撤销
external_state    是否改变仓库外的状态（部署、支付、权限、发邮件）
blast_radius      影响范围（单文件 / 单服务 / 多租户 / 生产数据）
data_sensitivity  是否接触密钥、PII、生产数据
approval_policy   intent 声明的策略版本
```

`intent.risk_tier` 只能是 `T0..T4`；未声明则 fail closed 到 `T2`。hook / gate 读取 `policy/risk@1`，不靠模型自述。

| Tier | 例子 | 人参与 | 机制 |
|---|---|---|---|
| T0 | 改注释、加测试、单文件可逆重构 | 无 | verifier + gate |
| T1 | 跨文件可逆重构、依赖小版本升级 | 通知/批量确认 | 汇总卡，不进入 token |
| T2 | 删除单个文件、force-push 到 feature 分支 | 单人 | 卡片 + 明确词 + dwell 3s + token |
| T3 | 部署、支付、权限变更、生产数据删除 | 单人 + 强人证 | T2 + 人跑 TTY（GPG 可选）+ 冷却 60s + 双人建议 |
| T4 | 受监管变更、跨租户操作 | 双人 + 独立环境 | 独立机器/用户 + 硬件密钥 |

---

## 3. 注意力层：预算、冷却、疲劳

### 3.1 决策记录

每次人决策写一条 `decision` 事件：

```json
{
  "decision_id": "DEC-0007",
  "run": "001-demo",
  "card_id": "CARD-3f9a...",
  "tier": "T2",
  "choice": "approved",
  "phrase": "批准",
  "rendered_at": "2026-11-19T10:00:00Z",
  "decided_at": "2026-11-19T10:00:04Z",
  "latency_ms": 4000,
  "session": "sess-pm",
  "provider": "tty",
  "key_id": null
}
```

### 3.2 硬规则

```text
1. 一次只渲染一张卡；队列用编号，不让人记 ESC-ID。
2. T2 最短 dwell 3s；T3 最短 dwell 10s，且批准后冷却 60s 才能 mint。
3. 同一 run 连续 T2 批准超过 N 次（默认 5）→ 插入一次汇总复核卡。
4. 10 分钟内决策 > 8 次，或批准率 > 95% 且中位延迟 < 2s → fatigue_suspected。
5. fatigue_suspected 时：暂停新卡，要求人做一次抽样复核或明确提高预算。
6. 注意力预算耗尽 → run 进入 blocked，出「预算耗尽卡」，不自动批准。
```

### 3.3 批量与检查点

- 只允许批量 **T1 可逆、同质、低风险** 项；T2/T3 永不批量。
- 非阻塞的 `out_of_scope` / `spec_ambiguous` 可聚合到检查点（每 WO 结束 / 每 15 分钟），阻塞项立即出卡。
- 汇总卡必须列出每项的动作、影响、编号；批准只对该批次生效，不产生“永久授权”。

### 3.4 配置

```json
{
  "attention": {
    "max_decisions_per_run": 20,
    "max_decisions_per_10min": 8,
    "max_consecutive_t2": 5,
    "t2_min_dwell_ms": 3000,
    "t3_min_dwell_ms": 10000,
    "t3_cooldown_s": 60,
    "fatigue_approval_rate": 0.95,
    "fatigue_median_latency_ms": 2000
  }
}
```

---

## 4. 真实性层：卡片绑定、短期码、过期与重放

### 4.1 卡片对象

`sancai_card.py render` 不再只打印文本，而是：

1. 生成 `card_id`（UUID）和 `card_hash`（canonical payload 的 sha256）。
2. 用 `SANCAI_SECRET` 派生卡片 MAC key：`HMAC(secret, "aitl-card-v1")`。
3. 写 `.sancai/runs/<run>/L3-intent/decisions/cards/<card_id>.json`（agent 的 Write 权限不覆盖 `.sancai`）。
4. 打印卡片，头部包含 `card_id` 和 8 位 `card_code`（`card_hash` 前 8 位）。

```json
{
  "card_id": "CARD-3f9a1c2e",
  "run": "001-demo",
  "kind": "approve",
  "tier": "T2",
  "payload": {
    "run": "001-demo",
    "wo": "WO-001",
    "esc": "ESC-001",
    "action": "rm -rf build",
    "diff_sha": "9f2c...",
    "evidence_sha": "a1b2...",
    "state_version": 7
  },
  "card_hash": "3f9a1c2e...",
  "mac": "hmac-sha256:...",
  "created_at": "2026-11-19T10:00:00Z",
  "used_at": null
}
```

### 4.2 决策必须绑定卡片

```bash
sancai_escalate.py approve \
  --run 001-demo --id ESC-001 \
  --message "批准" \
  --card-id CARD-3f9a1c2e --card-code 3f9a1c2e \
  --session-id "$CLAUDE_SESSION_ID"
```

脚本校验：

```text
1. card_id 存在，MAC 有效，card_code 匹配。
2. card.run / esc / action / diff_sha / evidence_sha 与当前状态一致。
3. card.used_at 为空；决策后写 used_at，第二次决策失败。
4. card_hash 绑定的 state_version 未变；变了就拒绝，要求重新渲染。
```

### 4.3 人可自行验证

高风险动作（T3）要求人自己在终端跑：

```bash
python3 plugins/sancai-loop-plugin/scripts/sancai_card.py verify \
  --run 001-demo --card-id CARD-3f9a1c2e
```

输出必须是同一张卡、同一个 `card_code`、同一个 diff。agent 的叙述不算数。

### 4.4 防伪造边界

- agent 不能写 `.sancai/runs/*/L3-intent/decisions/cards/`（capability 拒绝）。
- agent 没有 `SANCAI_SECRET` 时不能生成有效 MAC。
- 若 agent 被攻陷且能读 `SANCAI_SECRET`，MAC 也会失守；此时必须升级到 GPG / OS 生物识别 / 独立机器。
- 卡片 MAC 只证明“这张卡是 harness 生成的”，不证明“人看了”。

---

## 5. 确认层：findings 逐项处置

### 5.1 findings 摘要

`accept` 前计算：

```text
findings_hash = sha256(sorted(
  severity, file, line, summary, suggested_fix, source
))
```

卡片按严重度分组：

```text
blocker / critical   → 硬失败，不允许 accept
major                → 必须 defer 或 waive
minor / info         → 必须 acknowledge
```

### 5.2 接受语法

```bash
sancai_state.py accept \
  --run 001-demo \
  --message "接受" \
  --ack-findings <findings_hash> \
  --disposition "F-002=defer" \
  --disposition "F-003=waive:已知样式问题，下个迭代修" \
  --session-id "$CLAUDE_SESSION_ID"
```

规则：

```text
1. blocker/critical 存在 → 直接拒绝，不给 waiver。
2. major 没有 disposition → 拒绝。
3. minor/info 没有 --ack-findings → 拒绝。
4. defer 会创建 follow-up WO（state=todo），写入 run.json。
5. waive 必须有非空理由，并在 outcome 里保留。
6. 所有处置写 findings_acknowledged 事件，包含 hash、列表、原话。
```

### 5.3 卡片呈现

accept 卡必须包含：

```text
- 已验证的 WO / gate
- AC 覆盖
- evidence 路径
- findings 分组（blocker / major / minor）
- 接受后仍未解决的事项
- follow-up WO（defer 后）
- findings_hash 短码
```

---

## 6. 人证层：ApprovalProvider

### 6.1 接口

```json
{
  "decision_id": "DEC-0007",
  "provider": "tty|gpg|os-biometric|webauthn|two-person",
  "key_id": "human:leoluo:gpg-ABC123",
  "payload_hash": "sha256:...",
  "signature": "base64:...",
  "signed_at": "2026-11-19T10:00:04Z"
}
```

gate 校验：

```text
1. provider 是否满足 tier 要求（T3 必须是人在 TTY 运行 `sancai_human.py`，或 GPG/生物识别；session id 与 agent 代跑不算）。
2. payload_hash 是否等于 decision payload（card_hash + choice + phrase + run）。
3. signature 是否由 allowlist 中的 key 验证通过。
4. decision_id 未被使用；签名时间在 TTL 内。
```

### 6.2 Provider 分级

| Provider | 机制 | 防什么 | 代价 |
|---|---|---|---|
| `tty` | 人在终端跑 `sancai_human.py`，要求 TTY | agent 代跑 | 需要人开终端 |
| `gpg` | 人对 decision payload 做 detached signature | agent 伪造、同用户代签 | 需要 GPG key + passphrase |
| `os-biometric` | Touch ID / Windows Hello / polkit | 同用户 agent 静默批准 | 平台适配 |
| `webauthn` | passkey / 安全密钥对 payload_hash 断言 | 远程/恶意进程 | 需要浏览器/硬件 |
| `two-person` | 两个不同 key_id 的签名 | 单人误批/单点 | 流程成本 |

### 6.3 默认策略

```text
T2：明确词 + card binding + dwell（默认）；tty 可选
T3：人跑 TTY `sancai_human.py`（必须）；GPG 可选，Phase 3 默认；os-biometric Phase 3
T4：two-person + 独立机器/用户 + 硬件密钥
```

### 6.4 为什么不用 session id 当人证

`session_id` 是 agent 和人都能读的字符串；它只能证明“某个会话里发生过决策”，不能证明“人参与了”。人证必须是 agent 不能代跑的东西：TTY、私钥、生物识别、第二个人。

### 6.5 密钥管理

```text
- 公钥/allowlist 放 repo policy（可审计）。
- 私钥放 OS keychain / 硬件密钥，绝不进 repo。
- GPG 签名时使用 ask-passphrase，避免 gpg-agent 缓存静默签名。
- 轮换：policy 里保留 key_id + 生效/失效时间；gate 校验时间窗。
```

---

## 7. 状态与数据模型

```text
.sancai/runs/<run>/
├── L3-intent/decisions/
│   ├── cards/<card_id>.json          # 卡片 + hash + mac + used_at
│   ├── <decision_id>.json            # 人的决策 + provider + signature
│   └── findings/<wo>.json            # findings + disposition
├── L2-harness/run.json               # attention counters / risk_tier / policy
└── audit/events.jsonl                # card_rendered / decision_recorded / ...
```

事件：

```text
card_rendered
decision_recorded
findings_acknowledged
attention_budget_exceeded
fatigue_suspected
approval_signature_invalid
```

---

## 8. 全流程

```text
PM 生成候选动作
  │
  ▼
sancai_card.py render
  │ 写 cards/<id>.json；打印 card_id + card_code
  ▼
人看到卡片（T3 自己在终端 verify）
  │ 明确词 + card_code
  ▼
sancai_escalate.py approve / sancai_state.py accept
  │ 校验 MAC / 过期 / 重放 / dwell / findings
  │ 写 decision + used_at
  ▼
gate 校验人证 provider（T3）
  │
  ▼
token mint（T2/T3）→ executor 执行
```

---

## 9. 对抗测试

| 场景 | 期望 |
|---|---|
| agent 伪造卡片文本 | `approve` MAC/code 失败 |
| 卡片渲染后 diff 改变 | hash mismatch，拒绝 |
| 同一卡片批准两次 | `used_at` 非空，拒绝 |
| 3 秒内批准 T2 | dwell 不足，拒绝并重渲染 |
| 连续批准 6 次 T2 | 插入汇总复核卡 |
| 10 分钟 9 次决策 | fatigue_suspected，暂停 |
| major finding 无 disposition | accept 拒绝 |
| minor finding 无 ack | accept 拒绝 |
| T3 只有 session id / agent 代跑 | gate 拒绝，要求人跑 TTY 或 GPG/生物识别 |
| 两个签名 key_id 相同 | two-person 拒绝 |
| 人跑 verify 的卡片与 agent 展示不一致 | 以 verify 为准，拒绝决策 |
| 注意力预算耗尽 | run blocked，不自动批准 |

---

## 10. 分阶段落地

### Phase 1（建议先做，1–2 天）

- 卡片 `card_id` / `card_hash` / `card_code` / MAC / `used_at`。
- `approve` / `accept` / `sign` 绑定 `--card-id --card-code`。
- `findings_hash` + `--ack-findings` + major 的 defer/waive。
- dwell time 记录与拒绝（T2 3s）。
- 测试：伪造、过期、重放、findings。

### Phase 2（3–5 天）

- `sancai_human.py` TTY CLI（sign/approve/accept/verify）。
- 注意力预算、连续批准阈值、fatigue_suspected。
- 汇总卡 / 检查点批量（仅 T1）。
- 测试：疲劳、预算、批量。

### Phase 3（1 周）

- GPG provider + allowlist + 签名校验。
- two-person（两个 key_id）。
- OS 生物识别适配（macOS 先行）。
- eval：人证失败率、伪造拦截率、human_minutes。

### Phase 4（按需）

- WebAuthn / 安全密钥。
- 独立审批机 / 独立用户。
- 多 run / 多团队审批流。

---

## 11. 评估指标

```text
human_minutes_per_task
decisions_per_run
median_decision_latency_ms
rejection_rate
fatigue_suspected_count
card_forgery_rejected
stale_card_rejected
findings_ack_rate
major_findings_deferred / waived
approval_provider_failures
escape_after_accept
```

---

## 12. 开放问题

1. 风险分级由谁定？建议 intent 声明 + policy 审核，agent 不能自定 T0。
2. T1 批量批准的边界？需要按 repo / 服务 / 数据敏感度配置。
3. GPG key 的分发与轮换？个人 key 还是团队 key？
4. 双人审批在单人仓库如何落地？可以是“第二个人”或“第二个独立 agent + 人工抽查”，但后者不是人证。
5. OS 生物识别的跨平台抽象？macOS 先行，Windows/Linux 后补。
6. 卡片 verify 的 UX：终端命令是否可接受，还是需要本地 web/statusline？
7. 审批代理（human delegate）如何授权与追责？
8. 注意力预算是否应跨 run 累计？建议按人/天，而不是按 run。

---

## 13. 一句话总结

> **人类侧防呆的核心不是“多问一次”，而是：让批准绑定一张可验证的卡、让重大发现必须处置、让疲劳有硬预算、让高风险批准必须由 agent 无法代跑的人证完成。**

# 表结构速查

三个 SQLite 库。查的时候用 `mode=ro`，别写。

## memory.db

### atoms（核心表，约 2850 行）

| 列 | 说明 |
|---|---|
| `id` | 主键 |
| `content` | 记忆正文 |
| `mtype` | 类型：fact / promise / command / praise / blame / request / emotion / smalltalk |
| `nature` | 性质：fact / joke / scold / request / emotion / question |
| `nature_conf` | 性质的置信度 0-1 |
| `nature_source` | rule / assume / history / owner |
| `nature_reason` | **判据**：为什么判成这个性质 |
| `nature_evidence` | 原文摘录或触发词 |
| `nature_by` | 谁判的：rule / llm / owner |
| `nature_ver` | 改判次数 |
| `layer` | 谁对谁：owner_to_me / me_to_owner / other_to_me / me_to_other / owner_to_other / other_to_other |
| `importance` | 0-1，基线按 mtype 给（promise 0.75 / command 0.70 / blame 0.60 / fact 0.50 / smalltalk 0.30） |
| `status` | candidate / active / dormant / archived / expired |
| `evidence` | 证据分层：亲历 / 查到 / 听说 / 推测 / 想象 |
| `valence` | 效价 -1~1 |
| `arousal` | 唤醒度 0~1 |
| `recall_count` | 被检索命中次数（touch 时 +1） |
| `reinforce_count` | 被重复说过的次数 |
| `who_id` / `who_name` | 说话人 |
| `person_ids` | 牵扯的人（JSON 数组，`p_xxx`） |
| `source` | group / private / unknown |
| `with_owner` | 是否与主人私聊 |
| `privacy` | normal / sensitive |
| `topic` | 话题 |
| `ttl_days` / `expires_at` | 存活时间 |
| `said_at` / `create_time` / `last_access` | 时间戳 |
| `session_id` / `persona_id` | 会话归属 |
| `metadata` | JSON |

**索引**：`status`、`said_at`、`importance`。

### 其他表

| 表 | 用途 |
|---|---|
| `memories` | 原始会话总结（atoms 的上一级） |
| `atoms_fts` | 全文索引（`content`） |
| `atom_vectors` | 语义向量（bge-m3，1024 维） |
| `unfinished_cues` | 短期未完成线索（TTL 180 秒） |

## people.db

### people（约 74 行）

| 列 | 说明 |
|---|---|
| `person_id` | `p_xxxxxxxxxxxx` 或 `me`（铃光自己） |
| `is_me` | 1 = 是「我」的那条（全局唯一） |
| `is_unknown` | 还没认出来是谁 |
| `last_seen` / `mention_count` | 最近出现、被提到次数 |
| `importance` | 重要性 |
| `status` | active / archived |
| `note` | 备注 |

### person_tags

| 列 | 说明 |
|---|---|
| `person_id` / `kind` / `value` | kind: qq / nickname / real_name / alias / group_card |
| `source` | owner / other / inferred |
| `confidence` | 0-1 |
| `status` | confirmed / guess / rejected |
| `source_raw` | 原话或「群昵称：xxx」 |

### relations

**有向边**。`a_id` 对 `b_id` 是什么关系。

| 列 | 说明 |
|---|---|
| `a_id` / `b_id` | person_id |
| `rel_type` | 家人 / 恋人 / 朋友 / 同事 / 同学 / 主仆 / 师徒 / 熟人 / 陌生人 / 敌对 |
| `direction` | a_to_b / b_to_a / both |
| `tone` | **底色**：a 对 b 的真实感受，一句话 |
| `confidence` | 0-1 |
| `source` | `铃光真实感受` / `inferred` |
| `from_ts` / `to_ts` | `to_ts IS NULL` 表示当前有效 |

### relation_evidence / tone_history

- `relation_evidence`：每条边的依据（谁说的、原话）
- `tone_history`：底色变更历史（old_tone → new_tone + reason）

## personality.db

### personality_snapshots（每次演化一行）

| 列 | 说明 |
|---|---|
| `version` | 版本号 |
| `traits` | 大五 JSON |
| `adaptations` | 价值观/目标/可能自我/自我效能/控制点/归因/利他 JSON |
| `narrative` | 生命叙事（一段话） |
| `gestalt` | 格式塔 JSON（整体印象/图形/背景/未闭合/模式/认知失调） |
| `schema` | 图式 JSON（自我/他人/角色/事件/关系/群体自我） |
| `core` | **核心层 JSON**（底线/存在焦虑/存在锚/锁） |
| `voice` | 说话风格 JSON |
| `source_atoms` / `total_atoms` | 归纳时读了多少条、库里一共多少条 |
| `reason` / `changed_by` | 为什么更新、谁改的 |

### personality_events

| 列 | 说明 |
|---|---|
| `version` | 属于哪一版 |
| `dimension` | 变了哪个维度（`traits.openness` / `gestalt.figure` / `schema.scripts` / `core.*`） |
| `old_value` / `new_value` | 变化前后 |
| `trigger_atom_ids` | **推它的记忆 id（JSON 数组）** |
| `at` | 时间戳 |

### personality_state

键值对，存演化状态：`last_total_atoms`、`last_evolve_at`。

## 常查的 SQL

```sql
-- 她对这个人的底色
SELECT tone FROM relations WHERE a_id='me' AND b_id='p_xxx' AND to_ts IS NULL;

-- 某主题的记忆
SELECT id, content, importance FROM atoms
WHERE content LIKE '%唱歌%' AND status IN ('active','candidate')
ORDER BY importance DESC LIMIT 10;

-- 人格最近的变化
SELECT version, dimension, old_value, new_value, trigger_atom_ids
FROM personality_events ORDER BY id DESC LIMIT 20;

-- 证据分布
SELECT evidence, COUNT(*) FROM atoms GROUP BY 1 ORDER BY 2 DESC;

-- 谁和谁互动最多（同框次数）
-- 需要解析 person_ids，用 scripts/query.py --stats 看不到，得写 SQL 或脚本
```

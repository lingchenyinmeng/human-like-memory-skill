---
name: human-like-memory
description: 查铃光（AstrBot 机器人）的记忆库和人格库。用户问「铃光记得什么」「她怎么看我」「她的人格到第几版了」「她最近记了什么」「她为什么变了」，或者要排查记忆/人格插件的问题、改她的记忆和人格、手动触发人格演化时用。也用于查记忆库统计（原子数、关系数、重要性分布、证据分层）。
---

# 铃光的记忆与人格

两个 AstrBot 插件跑在 `<AstrBot>` 里，**不是 DSH 的插件**。
本 skill 给你一套脚本，让你能**查、能改、能排查**这两个库。

## 数据在哪

| 库 | 路径 | 存什么 |
|---|---|---|
| `memory.db` | `<AstrBot>\data\plugin_data\astrbot_plugin_human_like_memory\memory.db` | 原子（约 2850 条）、会话映射 |
| `people.db` | 同目录 | 人物（约 74）、关系（约 104）、底色（tone） |
| `personality.db` | `<AstrBot>\data\plugin_data\astrbot_plugin_human_like_personality\personality.db` | 人格快照、变化事件、核心层 |

**三个库都是 SQLite，只读查询用 `mode=ro`，改之前先备份。**

## 常用脚本

`<S>` = 本 skill 的 `scripts/` 完整路径。

| 想干什么 | 命令 |
|---|---|
| 数据概况 | `python <S>\query.py --stats` |
| 搜记忆 | `python <S>\query.py --memory "唱歌"` |
| 看某人的底色 | `python <S>\query.py --person "噩壤"` |
| 看人格全文 | `python <S>\query.py --personality` |
| 人格怎么变的 | `python <S>\query.py --why` |
| 最近记了什么 | `python <S>\query.py --recent 20` |
| 手动触发人格演化 | `python <S>\evolve.py` |
| 查一条记忆的详情 | `python <S>\query.py --atom 1109` |

所有脚本输出 **UTF-8 中文**，直接看即可。

## 读数据时的关键概念

### 记忆的四层生命周期

```
candidate（暂存区，48h 内定性）
  → active（正式库，进注入）
  → dormant（没定性，7 天后删）
  → archived（到期进遗忘库，留 180 天）
  → deleted（真删）
```

**只有 `active` 和 `candidate` 会进上下文。**

### 转正的四条路（任一满足）

1. `reinforce_count >= 2`（重复说过）
2. `nature_conf >= 0.8`（定性够确定）
3. `mtype in (fact, promise, praise)` 且 `nature_conf >= 0.55`
4. `importance >= 0.65`

### 证据分层（`evidence`）

| 值 | 权重 | 含义 |
|---|---|---|
| 亲历 | 1.0 | 她自己做的/看到的 |
| 查到 | 0.8 | 翻日志、搜文档 |
| 听说 | 0.7 | 别人说的（含主人） |
| 推测 | 0.4 | 「可能」「我猜」 |
| 想象 | 0.2 | 「假如」「梦见」 |

**实测分布**：听说 92% / 亲历 6.5% / 推测 25 条 / 查到 12 条 / 想象 6 条。

### 情绪二维（`valence` / `arousal`）

Russell 环形模型。`nature` 说「这是什么话」，这两个说「这句话什么温度」。

- `valence`：-1（负）到 1（正）
- `arousal`：0（平静）到 1（激动）

### 关系与底色

`people.db` 的 `relations` 表：
- `a_id` / `b_id`：人（`me` 代表铃光自己）
- `tone`：**a 对 b 的底色**，一句话人话（「见到他会开心，也怕他嫌我话多」）
- `source`：`铃光真实感受` / `inferred`（同框次数推的）
- `confidence`：0-1

**`me → X` 的边是她对别人的感受；`X ↔ Y` 的边是「别人之间」的弱关系。**

### 人格的核心层（不许自动改）

`personality.db` 的 `personality_snapshots.core`：

```json
{
  "boundaries": ["不记别人的隐私", "不碰删除和支付类操作除非他直接命令", ...],
  "existence_fear": "怕哪天被重写、被换掉、被忘记",
  "existence_anchor": "他第一次喊她名字那天",
  "locked": true
}
```

**`locked=true` 时自动演化只读不写**，模型说什么都不听。

## 改数据（谨慎）

**任何写操作之前先备份**：

```powershell
$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item <AstrBot>\data\plugin_data\astrbot_plugin_human_like_memory\*.db `
  <你自己的备份目录>\hlm-$ts\ -Force
```

**改人格的正确方式**：用 AstrBot 里的命令 `/人格 ...`，或者直接用 SQL 改 `personality.db` 后重启 AstrBot。
**不要**手改 `memory.db` 的 `atoms`，那是插件自己维护的。

## 排查常见问题

| 现象 | 查什么 |
|---|---|
| 她不记得某件事 | 那条原子是不是 `dormant`/`archived` 了；`importance` 是不是太低 |
| 她记错了 | 看 `nature`、`nature_reason`，用 `/人格 why` 看是不是人格推歪了 |
| 她人格变了 | 看 `personality_events` 的 `trigger_atom_ids`，反查那几条记忆 |
| 注入太长被截断 | 人格 `inject_max_chars` 默认 1450；memory 默认 400 |
| 插件没加载 | `curl http://127.0.0.1:6185/api/v1/plugins`（要 token），或看 `<AstrBot>\run.log` |

## 两个插件的分工（说给用户听时用）

| 插件 | 管什么 | 变化速度 |
|---|---|---|
| `human_like_memory` | 发生过什么 | 实时 |
| `human_like_personality` | 长期是什么样的人 | 月级 |
| `fish_heart` | 此刻什么心情 | 分钟级 |
| `persona_plus` | 人设提示词 | 静态 |

## 详细文档

- `references/schema.md` —— 三张库的完整表结构
- `references/commands.md` —— AstrBot 里的命令和 LLM 工具
- `references/troubleshooting.md` —— 踩过的坑和排查步骤

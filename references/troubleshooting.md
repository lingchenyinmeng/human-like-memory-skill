# 排查手册

## 先看这三个

```bash
# 1. 数据概况（库在不在、有没有数据）
python <S>\query.py --stats

# 2. 人格在不在
python <S>\query.py --personality

# 3. 该不该演化
python <S>\evolve.py
```

## 插件没加载

```powershell
# AstrBot 端口
Get-NetTCPConnection -LocalPort 6185 -State Listen

# 日志里的启动记录
Get-Content <AstrBot>\run.log | Select-String 'human_like_mem|hlp\]'

# 通过 API 查（要登录）
# POST /api/v1/auth/login 拿 token，再 GET /api/v1/plugins
```

**注意**：改完 `metadata.yaml` 的版本号，`reload_one.py` 不会更新面板显示——
AstrBot 缓存了版本号，**必须完整重启**。

## 她不记得某件事

按顺序查：

```sql
-- 1. 这条在不在
SELECT id, status, importance, expires_at FROM atoms WHERE content LIKE '%关键词%';

-- 2. 在的话，状态是什么
--    active / candidate → 会进上下文
--    dormant          → 没定性，7 天后删（不进上下文）
--    archived         → 进遗忘库了（不进上下文）
```

**如果 `importance` 太低**（≤0.35），会被降权，检索时排不上。

**如果 `source='unknown'`**，注入时会被跳过（来源不明的不进上下文）。

## 她记错了 / 判错性

```sql
-- 看判据
SELECT nature, nature_conf, nature_reason, nature_evidence, nature_by
FROM atoms WHERE id = 1234;
```

判据是空的或者明显不对 → 用 AstrBot 里的 `correct_memory` 工具改（会写 `atom_nature_history`）。

## 她人格变了 / 变得莫名其妙

```bash
python <S>\query.py --why
```

看 `trigger_atom_ids`，反查那几条记忆：

```bash
python <S>\query.py --atom 1109
```

**如果发现是「推测」或「想象」的记忆把人带偏了**——这就是证据分层没起作用的场景，检查那几条的 `evidence` 字段。

**如果是叙事剧变**：插件有 `drift_guard_ratio`（默认 0.35），相似度低于它时**拒绝落盘**。
日志里会有 `[hlp] 叙事剧变（相似度 0.xx < 0.35），拒绝落盘`。

## 注入太长 / 被截断

| 插件 | 默认上限 | 配置项 |
|---|---|---|
| memory | 400 字 | `inject_max_chars` |
| personality | 1450 字 | `inject_max_chars` |

personality 实测 14 层全塞下是 1421 字，低于 1400 会截掉末尾的叙事和说话风格。

## 她没回应 / 不主动说话

那是 `fish_heart`（鱼的心）和 `group_chat_plus` 管的，不是这两个插件。
- 鱼的心：心境档位、回避状态
- group_chat_plus：注意力机制、接话概率

## 关系为 0 / 底色为空

```bash
python <S>\query.py --person "噩壤"
```

如果 `relations` 是空的：
- 关系要靠她主动 `relate` 记，或者在面板里手动加
- `build_edges.py` 能从「同框次数」生成弱关系（`rel_type=熟人`, `source=inferred`）

## 备份

```powershell
$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$dst = "<你自己的备份目录>\hlm-$ts"
New-Item -ItemType Directory -Path $dst -Force | Out-Null
Copy-Item <AstrBot>\data\plugin_data\astrbot_plugin_human_like_memory\*.db $dst
Copy-Item <AstrBot>\data\plugin_data\astrbot_plugin_human_like_personality\*.db $dst
```

**`memory.db` 约 17 MB，`people.db` 约 0.14 MB，`personality.db` 约 0.04 MB。**

## 踩过的坑（这个 skill 迭代时发现的）

| 坑 | 现象 | 怎么避开 |
|---|---|---|
| dataclass 缺字段 | `Atom.__init__() got an unexpected keyword argument 'recall_count'` | 加列后一定要加 dataclass 字段；跑 `tools/audit_fields.py` |
| TTS 返回 MP3 | 按 WAV 解析时长得 0 | 用 `ffprobe` 而不是自己解析文件头 |
| `_connect()` 返回 connection | `AttributeError: 'Connection' object has no attribute 'fetchone'` | `async with db:` 然后 `cur = await db.execute(...)` |
| `MAX(expires_at, now+7天)` | 续命对 26 天 TTL 是空操作 | 改成 `expires_at = now + ttl_days`（重置） |
| 版本号不更新 | 面板还是旧版本 | 完整重启，不是 `reload_one.py` |
| `git push` 连不上 github.com:443 | `Empty reply from server` / `Could not connect` | 用 GitHub Contents API（`api.github.com` 通） |

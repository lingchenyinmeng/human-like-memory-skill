# Human-like Memory · DSH Skill

在 [DeepSeek Harness](https://github.com/deepseek-ai) 里查、改、排查 AstrBot 的**长期记忆**和**人格**。

配套 AstrBot 插件：
- [`astrbot_plugin_human_like_memory`](https://github.com/lingchenyinmeng/astrbot_plugin_human_like_memory)
- [`astrbot_plugin_human_like_personality`](https://github.com/lingchenyinmeng/astrbot_plugin_human_like_personality)

## 这是什么，不是什么

| | AstrBot 插件 | 这个 DSH skill |
|---|---|---|
| 形态 | 常驻 Python 服务 | `SKILL.md` + 脚本 |
| 干什么 | 接管对话、注入记忆和人格 | 让 agent **查**和**管**那两个插件 |

**它不替代那两个插件。** 记忆和人格仍然由 AstrBot 插件负责，这个 skill 只是给 agent 一套工具，能读库、能排查、能判断该不该演化。

## 安装

```bash
git clone https://github.com/lingchenyinmeng/human-like-memory-skill.git \
  ~/.dsh/skills/human-like-memory
```

Windows：

```powershell
git clone https://github.com/lingchenyinmeng/human-like-memory-skill.git `
  "$env:USERPROFILE\.dsh\skills\human-like-memory"
```

装完**重启 DSH**，skill 才会出现在 catalog 里。

## 配置 AstrBot 在哪

skill 会**自动探测** AstrBot 的数据目录，顺序：

1. 环境变量 `ASTRBOT_HOME`
2. 本目录的 `config.json` 里的 `astrbot_home`
3. 常见位置（`~/.astrbot`、各盘符根下的 `AstrBot` / `astrbot`）

**探测不到就任选一种方式指定**（`AstrBot 根目录` = 含 `data\` 的那层）：

```powershell
# 方式一：环境变量（临时）
$env:ASTRBOT_HOME = "D:\你的路径\astrbot"

# 方式二：写配置文件（持久）
Copy-Item config.example.json config.json
notepad config.json
```

`config.json`：

```json
{
  "astrbot_home": "D:\\你的路径\\astrbot"
}
```

## 用法

```bash
S=~/.dsh/skills/human-like-memory/scripts

python $S/query.py --stats              # 数据概况
python $S/query.py --memory "关键词"     # 搜记忆
python $S/query.py --person "某人"       # 某人的标签+关系+底色
python $S/query.py --personality        # 人格全文（14 层）
python $S/query.py --why                # 人格怎么变的
python $S/query.py --recent 20          # 最近记了什么
python $S/query.py --atom 1234          # 一条记忆的完整字段
python $S/evolve.py                     # 该不该演化
```

在 DSH 里也可以直接说：「她记得什么关于唱歌的」「她现在的人格什么样」「她这人怎么变的」，agent 会自动用这个 skill 去查。

## 它查什么

三个 SQLite 库：

```
<AstrBot>/data/plugin_data/astrbot_plugin_human_like_memory/
├── memory.db      原子（约 2850 条）、会话
└── people.db      人物、关系、底色

<AstrBot>/data/plugin_data/astrbot_plugin_human_like_personality/
└── personality.db 人格快照、变化事件、核心层
```

**只读**。所有脚本用 `mode=ro` 打开，不会写你的库。

## 目录

```
SKILL.md                       agent 读的指令
scripts/
├── paths.py                   自动定位 AstrBot 数据目录
├── query.py                   只读查询
└── evolve.py                  判断该不该演化
references/
├── schema.md                  三个库的完整表结构
└── troubleshooting.md         排查手册 + 踩过的坑
config.example.json            配置示例
```

## 为什么 evolve.py 不直接触发演化

演化要调 AstrBot 进程里的 LLM provider，外部脚本拿不到那个 context。硬模拟就是绕过插件的锁、剧变拦截、`trigger_atom_ids` 记录——得不偿失。

所以它只判断「该不该」，并告诉你去 AstrBot 里发 `/人格 evolve`。

## 许可

MIT

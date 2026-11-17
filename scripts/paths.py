"""定位 AstrBot 的数据目录，供 query/evolve 共用。

不写死盘符。顺序：
1. 环境变量 ASTRBOT_HOME（指向 AstrBot 根目录）
2. skill 目录下的 config.json 里写的 astrbot_home
3. 常见安装位置（~/.astrbot、各盘符根下的 AstrBot/astrbot）
4. 全都没有 → 给出可操作的报错，而不是猜一个路径然后失败

把这份逻辑放在单独文件里，是为了让 query.py 和 evolve.py 不用各写一遍。
"""
from __future__ import annotations

import json
import os

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(SKILL_DIR, "config.json")

MEMORY_PLUGIN = "astrbot_plugin_human_like_memory"
PERSONALITY_PLUGIN = "astrbot_plugin_human_like_personality"


def _read_config() -> dict:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def find_astrbot_home() -> str | None:
    """返回 AstrBot 根目录（含 data/ 的那一层）。"""
    # 1. 环境变量
    env = (os.environ.get("ASTRBOT_HOME") or "").strip()
    if env and os.path.isdir(os.path.join(env, "data")):
        return env

    # 2. 配置文件
    cfg_home = str(_read_config().get("astrbot_home") or "").strip()
    if cfg_home and os.path.isdir(os.path.join(cfg_home, "data")):
        return cfg_home

    # 3. 常见位置
    cands: list[str] = []

    # ~/.astrbot（AstrBot 有些部署会放这）
    home = os.path.expanduser("~")
    cands.append(os.path.join(home, ".astrbot"))
    cands.append(os.path.join(home, "AstrBot"))
    cands.append(os.path.join(home, "astrbot"))

    # 各盘符根下常见目录名（只查浅层，不递归，避免慢）
    if os.name == "nt":
        for letter in "CDEFGHAB":
            drive = f"{letter}:\\"
            if not os.path.isdir(drive):
                continue
            for name in ("AstrBot", "astrbot", "AstrBot-4", "dafeiyu"):
                p = os.path.join(drive, name)
                cands.append(p)
                # dafeiyu/astrbot 这种嵌套
                cands.append(os.path.join(p, "astrbot"))
    else:
        for name in ("/opt/astrbot", "/srv/astrbot", "/home/astrbot"):
            cands.append(name)

    for c in cands:
        try:
            if os.path.isdir(os.path.join(c, "data", "plugin_data")):
                return c
        except Exception:
            continue
    return None


def data_dir() -> str:
    home = find_astrbot_home()
    if home:
        return os.path.join(home, "data")
    # 实在找不到：退回 cwd/data，让调用方报错时至少路径看起来合理
    return os.path.join(os.getcwd(), "data")


def db_paths() -> dict[str, str]:
    d = data_dir()
    return {
        "memory": os.path.join(d, "plugin_data", MEMORY_PLUGIN, "memory.db"),
        "people": os.path.join(d, "plugin_data", MEMORY_PLUGIN, "people.db"),
        "personality": os.path.join(d, "plugin_data", PERSONALITY_PLUGIN, "personality.db"),
        "history": os.path.join(d, "data_v4.db"),
    }


def explain_missing() -> str:
    """找不到库时给一句能照做的话。"""
    home = find_astrbot_home()
    if home:
        return (
            f"找到 AstrBot 在 {home}，但库里没数据。\n"
            f"要么插件还没装，要么还没跑起来过。\n"
            f"查一下 {os.path.join(home, 'data', 'plugin_data')} 下有没有这两个目录。"
        )
    return (
        "找不到 AstrBot 的数据目录。任选一种方式指定：\n"
        "  1. 设环境变量：set ASTRBOT_HOME=D:\\你的路径\\astrbot\n"
        "  2. 在本 skill 目录建 config.json：{\"astrbot_home\": \"D:\\\\你的路径\\\\astrbot\"}\n"
        "（AstrBot 根目录是含 data\\ 的那一层）"
    )

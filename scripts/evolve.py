"""检查人格是否该演化了，并给出手动触发的正确方式。

为什么不在这里直接触发演化：演化要调 AstrBot 进程里的 LLM provider，
那是插件内部的 context，外部脚本拿不到。
硬要模拟就是绕过插件的锁、绕过剧变拦截、绕过 trigger_atom_ids 记录——得不偿失。

正确做法：在 AstrBot 里发 `/人格 evolve`（或让用户发）。
本脚本负责判断「该不该」，不负责「做」。
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from paths import db_paths  # noqa: E402

_P = db_paths()
MEM = _P["memory"]
PER = _P["personality"]

# 和插件默认配置保持一致
EVOLVE_EVERY_ATOMS = 60
EVOLVE_MIN_HOURS = 24
EVOLVE_MIN_NEW_ATOMS = 10


def ro(path: str):
    if not os.path.isfile(path):
        return None
    con = sqlite3.connect(f"file:{path.replace(os.sep, '/')}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def main() -> None:
    con_m = ro(MEM)
    con_p = ro(PER)
    if con_m is None or con_p is None:
        print("[缺库] 检查路径")
        return

    total = con_m.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]

    row = con_p.execute(
        "SELECT version, total_atoms, created_at, reason FROM personality_snapshots "
        "ORDER BY version DESC LIMIT 1"
    ).fetchone()
    state = {
        r["key"]: r["value"]
        for r in con_p.execute("SELECT key, value FROM personality_state")
    }

    print("=" * 70)
    print("人格演化检查")
    print("=" * 70)
    if row is None:
        print("  还没有人格快照 → 首次启动会自动生成一版")
        print("  如果一直没生成，看 AstrBot 日志里有没有 [hlp]")
        return

    last_atoms = int(row["total_atoms"] or 0)
    new_atoms = max(0, total - last_atoms)
    last_evolve = float(state.get("last_evolve_at", "0") or 0)
    hours_since = (time.time() - last_evolve) / 3600 if last_evolve else 999

    print(f"  当前版本:   v{row['version']}（基于 {last_atoms} 条）")
    print(f"  库里现有:   {total} 条")
    print(f"  新增:       {new_atoms} 条")
    print(f"  距上次演化: {hours_since:.1f} 小时")
    print(f"  上次原因:   {row['reason'] or '—'}")
    print()

    # 判定
    reasons = []
    if new_atoms < EVOLVE_MIN_NEW_ATOMS:
        reasons.append(f"新增 {new_atoms} < {EVOLVE_MIN_NEW_ATOMS}（演化门槛）")
    if hours_since < EVOLVE_MIN_HOURS:
        reasons.append(f"距上次 {hours_since:.1f}h < {EVOLVE_MIN_HOURS}h")
    if new_atoms < EVOLVE_EVERY_ATOMS:
        reasons.append(f"新增 {new_atoms} < {EVOLVE_EVERY_ATOMS}（自动演化阈值）")

    if not reasons:
        print("  → 够条件自动演化了。等下一次维护循环（每 30 分钟检查一次）。")
        print("  → 想立刻：在 AstrBot 里发 /人格 evolve")
    else:
        print("  → 现在不该演化，原因：")
        for r in reasons:
            print(f"      · {r}")
        print()
        print("  → 想强制一次：在 AstrBot 里发 /人格 evolve（会跳过这些门槛）")

    print()
    print("可用的方式（在 AstrBot 的对话里发）：")
    for c, d in [
        ("/人格 status", "看当前人格"),
        ("/人格 evolve", "强制演化一次"),
        ("/人格 history", "看历史版本"),
        ("/人格 why", "看每次变化是被哪条记忆推的"),
    ]:
        print(f"  {c:<16} {d}")

    if row["version"] and row["version"] > 0:
        core = con_p.execute(
            "SELECT core FROM personality_snapshots ORDER BY version DESC LIMIT 1"
        ).fetchone()
        try:
            c = json.loads(core["core"] or "{}")
        except Exception:
            c = {}
        if c.get("locked"):
            print()
            print("  注意：核心层已锁定（locked=True），演化不会改底线和存在相关字段。")

    con_m.close()
    con_p.close()


if __name__ == "__main__":
    main()

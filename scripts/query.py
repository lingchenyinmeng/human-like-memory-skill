"""查铃光的记忆库和人格库。

只读。所有输出 UTF-8。

用法：
    python query.py --stats
    python query.py --memory "唱歌"
    python query.py --person "噩壤"
    python query.py --personality
    python query.py --why
    python query.py --recent 20
    python query.py --atom 1109
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from paths import db_paths, explain_missing  # noqa: E402

_P = db_paths()
MEM = _P["memory"]
PPL = _P["people"]
PER = _P["personality"]

W = 78


def ro(path: str) -> sqlite3.Connection | None:
    if not os.path.isfile(path):
        print(f"[缺库] {path}")
        return None
    con = sqlite3.connect(f"file:{path.replace(os.sep, '/')}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def hr(title: str) -> None:
    print()
    print("─" * W)
    print(title)
    print("─" * W)


def fmt_ts(ts: float) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))


def cmd_stats() -> None:
    con = ro(MEM)
    if con:
        hr("记忆库")
        n = con.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
        print(f"  原子总数: {n}")
        print("  状态:")
        for r in con.execute(
            "SELECT status, COUNT(*) FROM atoms GROUP BY 1 ORDER BY 2 DESC"
        ):
            print(f"    {r[0]:<12} {r[1]}")
        print("  证据分层:")
        for r in con.execute(
            "SELECT COALESCE(NULLIF(evidence,''),'(空)') e, COUNT(*) "
            "FROM atoms GROUP BY 1 ORDER BY 2 DESC"
        ):
            print(f"    {r[0]:<8} {r[1]}")
        print("  重要性分布:")
        for r in con.execute(
            "SELECT ROUND(importance,1), COUNT(*) FROM atoms GROUP BY 1 ORDER BY 1"
        ):
            print(f"    {r[0]:<4} {r[1]}")
        print("  来源:")
        for r in con.execute(
            "SELECT COALESCE(NULLIF(source,''),'(空)') s, COUNT(*) "
            "FROM atoms GROUP BY 1 ORDER BY 2 DESC"
        ):
            print(f"    {r[0]:<10} {r[1]}")
        con.close()

    con = ro(PPL)
    if con:
        hr("人库")
        print(f"  人物: {con.execute('SELECT COUNT(*) FROM people').fetchone()[0]}")
        n_rel = con.execute(
            "SELECT COUNT(*) FROM relations WHERE to_ts IS NULL"
        ).fetchone()[0]
        n_tone = con.execute(
            "SELECT COUNT(*) FROM relations WHERE COALESCE(tone,'')!='' AND to_ts IS NULL"
        ).fetchone()[0]
        print(f"  关系: {n_rel}")
        print(f"  有底色: {n_tone}")
        print(f"  关系证据: {con.execute('SELECT COUNT(*) FROM relation_evidence').fetchone()[0]}")
        print(f"  底色变更历史: {con.execute('SELECT COUNT(*) FROM tone_history').fetchone()[0]}")
        con.close()

    con = ro(PER)
    if con:
        hr("人格库")
        row = con.execute(
            "SELECT version, total_atoms, created_at, reason FROM personality_snapshots "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row:
            print(f"  当前版本: v{row['version']}")
            print(f"  基于记忆: {row['total_atoms']} 条")
            print(f"  生成时间: {fmt_ts(row['created_at'])}")
            print(f"  原因: {row['reason'] or '—'}")
        print(f"  快照数: {con.execute('SELECT COUNT(*) FROM personality_snapshots').fetchone()[0]}")
        print(f"  变化事件: {con.execute('SELECT COUNT(*) FROM personality_events').fetchone()[0]}")
        con.close()


def cmd_memory(kw: str, limit: int = 10) -> None:
    con = ro(MEM)
    if not con:
        return
    hr(f"搜记忆：{kw}")
    rows = con.execute(
        "SELECT id, content, mtype, nature, importance, status, evidence, "
        "who_name, said_at FROM atoms WHERE content LIKE ? "
        "ORDER BY importance DESC, said_at DESC LIMIT ?",
        (f"%{kw}%", limit),
    ).fetchall()
    if not rows:
        print("  没找到")
    for r in rows:
        print(f"  #{r['id']}  [{r['status']}/{r['mtype']}/{r['nature']}]  "
              f"重要 {r['importance']:.1f}  {r['evidence'] or '?'}")
        print(f"      {r['content'][:120]}")
        if r["who_name"]:
            print(f"      —— {r['who_name']} · {fmt_ts(r['said_at'])}")
        print()
    con.close()


def cmd_person(name: str) -> None:
    con = ro(PPL)
    if not con:
        return
    hr(f"人：{name}")
    rows = con.execute(
        "SELECT person_id, kind, value FROM person_tags WHERE value = ?", (name,)
    ).fetchall()
    if not rows:
        print("  没找到这个人")
        con.close()
        return
    pid = rows[0]["person_id"]
    print(f"  person_id: {pid}")
    print(f"  标签: {', '.join(f'{r[chr(107)+chr(105)+chr(110)+chr(100)]}={r[chr(118)+chr(97)+chr(108)+chr(117)+chr(101)]}' for r in rows)}")
    rel = con.execute(
        "SELECT a_id, b_id, rel_type, tone, confidence, source FROM relations "
        "WHERE (a_id = ? OR b_id = ?) AND to_ts IS NULL",
        (pid, pid),
    ).fetchall()
    if rel:
        print("  关系:")
        for r in rel:
            other = r["b_id"] if r["a_id"] == pid else r["a_id"]
            direction = "→" if r["a_id"] == pid else "←"
            print(f"    {direction} {other}  [{r['rel_type']}] conf={r['confidence']}")
            if r["tone"]:
                print(f"        底色：{r['tone']}")
    con.close()


def cmd_personality() -> None:
    con = ro(PER)
    if not con:
        return
    row = con.execute(
        "SELECT * FROM personality_snapshots ORDER BY version DESC, id DESC LIMIT 1"
    ).fetchone()
    if not row:
        print("[人格] 还没生成")
        con.close()
        return

    core = json.loads(row["core"] or "{}")
    gest = json.loads(row["gestalt"] or "{}")
    schema = json.loads(row["schema"] or "{}")
    ad = json.loads(row["adaptations"] or "{}")
    traits = json.loads(row["traits"] or "{}")
    voice = json.loads(row["voice"] or "{}")

    hr(f"人格 v{row['version']}（基于 {row['total_atoms']} 条记忆）")

    if core:
        print("【核心层 · locked=%s】" % core.get("locked"))
        for b in core.get("boundaries") or []:
            print(f"  · {b}")
        if core.get("existence_fear"):
            print(f"  怕：{core['existence_fear']}")
        if core.get("existence_anchor"):
            print(f"  锚：{core['existence_anchor']}")
        print()

    if traits:
        print("【大五】")
        cn = {"openness": "开放性", "conscientiousness": "尽责性",
              "extraversion": "外向性", "agreeableness": "宜人性",
              "neuroticism": "神经质"}
        for k, v in traits.items():
            bar = "█" * (int(v) // 10) + "░" * (10 - int(v) // 10)
            print(f"  {cn.get(k, k):<6} {bar} {v}")
        print()

    if gest.get("emergent_whole"):
        print(f"【整体印象】{gest['emergent_whole']}")
    for key, label in (("figure", "此刻挂着"), ("background", "默认状态")):
        if gest.get(key):
            print(f"  {label}：{gest[key]}")
    if gest.get("unfinished"):
        print("  没放下：" + "；".join(gest["unfinished"]))
    if gest.get("patterns"):
        print("  反复出现：" + "；".join(gest["patterns"]))
    if gest.get("tensions"):
        print("  认知失调：")
        for t in gest["tensions"]:
            print(f"    · 在{t.get('behavior','')}，却觉得{t.get('belief','')}")
    print()

    if schema:
        if schema.get("self_schema"):
            print("【自我图式】" + "；".join(schema["self_schema"]))
        for k, label in (("owner_schema", "对主人"), ("others_schema", "对别人"),
                         ("role_schema", "觉得应该"), ("relational", "互动模式")):
            if schema.get(k):
                print(f"  {label}：{schema[k]}")
        if schema.get("scripts"):
            print("  事件图式：")
            for k, v in schema["scripts"].items():
                print(f"    {k} → {v}")
        if schema.get("public_self"):
            ps = schema["public_self"]
            print(f"  群里：{ps.get('群里','')}")
            print(f"  私下：{ps.get('私下','')}")
        print()

    if ad:
        if ad.get("values"):
            print("【价值观】" + "、".join(ad["values"]))
        if ad.get("goals"):
            print("【目标】" + "、".join(ad["goals"]))
        if ad.get("coping"):
            print(f"【应对】{ad['coping']}")
        lv = ad.get("attachment_levels") or {}
        if lv:
            print("【依恋】" + "；".join(f"{k}={v}" for k, v in lv.items()))
        ps = ad.get("possible_selves") or {}
        if ps.get("hoped_for"):
            print("【想成为】" + "；".join(ps["hoped_for"]))
        if ps.get("feared"):
            print("【怕变成】" + "；".join(ps["feared"]))
        eff = ad.get("self_efficacy") or {}
        if eff:
            print("【自我效能】" + "、".join(f"{k}={v}" for k, v in eff.items()))
        loc = ad.get("locus_of_control") or {}
        if loc:
            print("【控制点】" + "、".join(f"{k}={v}" for k, v in loc.items()))
        attr = ad.get("attribution_style") or {}
        if attr:
            print("【归因】" + "；".join(
                f"{w}:" + ",".join(f"{k}{v}" for k, v in d.items()) for w, d in attr.items()))
        alt = ad.get("altruism") or {}
        if alt:
            print("【利他】" + "；".join(f"{k}={v}" for k, v in alt.items()))
        print()

    if row["narrative"]:
        print("【叙事】")
        print(f"  {row['narrative']}")

    if voice.get("sentence_style"):
        print(f"\n【说话】{voice['sentence_style']}（平均 {voice.get('avg_len')} 字）")
        if voice.get("catchphrases"):
            print("  口头禅：" + "、".join(voice["catchphrases"]))
    con.close()


def cmd_why(limit: int = 20) -> None:
    con = ro(PER)
    if not con:
        return
    hr("人格变化历史")
    rows = con.execute(
        "SELECT version, dimension, old_value, new_value, trigger_atom_ids, at "
        "FROM personality_events ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    if not rows:
        print("  还没有变化记录（只有第 1 版时不产生）")
        con.close()
        return
    for r in rows:
        print(f"  v{r['version']} · {r['dimension']} · {fmt_ts(r['at'])}")
        print(f"    从：{str(r['old_value'])[:70]}")
        print(f"    到：{str(r['new_value'])[:70]}")
        try:
            ids = json.loads(r["trigger_atom_ids"] or "[]")
        except Exception:
            ids = []
        if ids:
            print(f"    推它的记忆：{ids[:10]}")
        print()
    con.close()


def cmd_recent(n: int) -> None:
    con = ro(MEM)
    if not con:
        return
    hr(f"最近 {n} 条记忆")
    rows = con.execute(
        "SELECT id, content, status, importance, evidence, said_at FROM atoms "
        "ORDER BY said_at DESC, id DESC LIMIT ?", (n,)
    ).fetchall()
    for r in rows:
        print(f"  #{r['id']} [{r['status']}] {fmt_ts(r['said_at'])} "
              f"重要{r['importance']:.1f} {r['evidence'] or '?'}")
        print(f"     {r['content'][:110]}")
    con.close()


def cmd_atom(aid: int) -> None:
    con = ro(MEM)
    if not con:
        return
    r = con.execute("SELECT * FROM atoms WHERE id = ?", (aid,)).fetchone()
    if not r:
        print(f"  没有 #{aid}")
        con.close()
        return
    hr(f"记忆 #{aid}")
    for k in r.keys():
        v = r[k]
        if k in ("content", "nature_reason", "context"):
            print(f"  {k}: {str(v)[:300]}")
        else:
            print(f"  {k}: {v}")
    con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="查铃光的记忆与人格")
    ap.add_argument("--stats", action="store_true", help="数据概况")
    ap.add_argument("--memory", metavar="关键词", help="搜记忆")
    ap.add_argument("--person", metavar="名字", help="看某人的标签和关系")
    ap.add_argument("--personality", action="store_true", help="看当前人格全文")
    ap.add_argument("--why", action="store_true", help="人格怎么变的")
    ap.add_argument("--recent", type=int, metavar="N", help="最近 N 条记忆")
    ap.add_argument("--atom", type=int, metavar="ID", help="看一条记忆的详情")
    ap.add_argument("--limit", type=int, default=10, help="搜记忆条数上限")
    args = ap.parse_args()

    if args.stats:
        cmd_stats()
    if args.memory:
        cmd_memory(args.memory, args.limit)
    if args.person:
        cmd_person(args.person)
    if args.personality:
        cmd_personality()
    if args.why:
        cmd_why()
    if args.recent:
        cmd_recent(args.recent)
    if args.atom:
        cmd_atom(args.atom)

    if not any([args.stats, args.memory, args.person, args.personality,
                args.why, args.recent, args.atom]):
        ap.print_help()


if __name__ == "__main__":
    main()
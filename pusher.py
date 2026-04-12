"""
推送模块
支持：飞书群机器人 webhook + PushPlus（微信）
"""

import json
import sqlite3
import hashlib
import requests
import os
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pushed.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pushed (
            news_id TEXT PRIMARY KEY,
            pushed_at TEXT,
            score REAL,
            title TEXT
        )
    """)
    conn.commit()
    return conn


def is_pushed(news_id):
    conn = _get_db()
    row = conn.execute("SELECT 1 FROM pushed WHERE news_id = ?", (news_id,)).fetchone()
    conn.close()
    return row is not None


def mark_pushed(news_id, score, title):
    conn = _get_db()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO pushed (news_id, pushed_at, score, title) VALUES (?, ?, ?, ?)",
        (news_id, now, score, title),
    )
    conn.commit()
    conn.close()


def clear_pushed_history(days=7):
    conn = _get_db()
    conn.execute("DELETE FROM pushed WHERE pushed_at < datetime('now', ?)", (f"-{days} days",))
    conn.commit()
    conn.close()


# ─── 飞书 Webhook 推送 ────────────────────────────────────
def push_feishu(webhook_url, news_list):
    """推送到飞书群：只显示新闻 + 时间 + 来源"""
    if not webhook_url or not news_list:
        return
    for batch in [news_list[i:i+10] for i in range(0, len(news_list), 10)]:
        lines = []
        for n in batch:
            title = n.get("title", "无标题")
            source = n.get("source", "")
            time_str = n.get("time_str", "")
            url = n.get("url", "")
            lang = n.get("lang", "")
            title_zh = n.get("title_zh", "")
            summary_zh = n.get("summary_zh", "")

            lines.append(f"📰 **{title}**")
            if lang == "en" and title_zh:
                lines.append(f"　　💬 {title_zh}")
            if summary_zh:
                lines.append(f"　　{summary_zh[:100]}")
            if url:
                lines.append(f"　　🔗 [原文]({url})  ·  {source}  ·  {time_str}")
            else:
                lines.append(f"　　{source}  ·  {time_str}")
            lines.append("")

        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"🌐 宏观新闻速报 · {len(batch)}条",
                        "content": [[{"tag": "text", "text": "\n".join(lines)}]],
                    }
                }
            },
        }
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get("code") == 0:
                print(f"[飞书推送] ✅ {len(batch)} 条")
            else:
                print(f"[飞书推送] ❌ {resp.status_code}")
        except Exception as e:
            print(f"[飞书推送] ❌ {e}")


# ─── PushPlus 微信推送 ────────────────────────────────────
def push_wechat(pushplus_token, news_list, topic_id=""):
    """推送到微信（个人 或 一对多群组）"""
    if not pushplus_token or not news_list:
        return
    for batch in [news_list[i:i+10] for i in range(0, len(news_list), 10)]:
        lines = []
        for n in batch:
            title = n.get("title", "无标题")
            source = n.get("source", "")
            time_str = n.get("time_str", "")
            url = n.get("url", "")
            title_zh = n.get("title_zh", "")
            summary_zh = n.get("summary_zh", "")

            lines.append(f"📰 <b>{title}</b>")
            if title_zh:
                lines.append(f"　　💬 {title_zh}")
            if summary_zh:
                lines.append(f"　　{summary_zh[:100]}")
            if url:
                lines.append(f'　　<a href="{url}">🔗 原文</a> · {source} · {time_str}')
            else:
                lines.append(f"　　{source} · {time_str}")
            lines.append("<hr>")

        payload = {
            "token": pushplus_token,
            "title": f"🌐 宏观新闻速报 · {len(batch)}条",
            "content": "".join(lines),
            "template": "html",
        }
        if topic_id:
            payload["topic"] = topic_id

        try:
            resp = requests.post("https://www.pushplus.plus/send", json=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get("code") == 200:
                print(f"[微信推送] ✅ {len(batch)} 条")
            else:
                print(f"[微信推送] ❌ {resp.json()}")
        except Exception as e:
            print(f"[微信推送] ❌ {e}")


# ─── 统一推送入口 ────────────────────────────────────────
def push_all(news_list, config):
    """去重 + 推送飞书 + 微信"""
    push_cfg = config.get("push", {})
    if not push_cfg.get("enabled", False):
        return 0

    min_score = config.get("filter", {}).get("min_importance", 15)
    new_items = []
    for n in news_list:
        if n.get("score", 0) < min_score:
            continue
        nid = n.get("id", "")
        if not nid or is_pushed(nid):
            continue
        new_items.append(n)

    if not new_items:
        return 0

    new_items.sort(key=lambda x: x.get("score", 0), reverse=True)
    pushed_count = 0

    wh = push_cfg.get("feishu_webhook", "")
    pt = push_cfg.get("pushplus_token", "")
    ptopic = push_cfg.get("pushplus_topic", "")

    if wh:
        push_feishu(wh, new_items)
    if pt:
        push_wechat(pt, new_items, topic_id=ptopic)

    for n in new_items:
        mark_pushed(n["id"], n["score"], n["title"][:100])
        pushed_count += 1

    return pushed_count

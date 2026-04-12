"""
翻译模块 - 英文新闻自动翻译为中文
使用 MyMemory API（免费，无需 Key），SQLite 缓存避免重复翻译
"""

import sqlite3
import hashlib
import requests
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            text_hash TEXT PRIMARY KEY,
            original TEXT,
            translated TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def translate(text, source_lang="en", target_lang="zh-CN"):
    """
    翻译文本，优先使用缓存
    
    Args:
        text: 要翻译的文本
        source_lang: 源语言
        target_lang: 目标语言
    
    Returns:
        翻译后的文本，失败则返回原文
    """
    if not text or not text.strip():
        return ""
    
    text = text.strip()
    # 只翻译英文内容（简单检测：如果包含中文字符则跳过）
    if any('\u4e00' <= ch <= '\u9fff' for ch in text[:20]):
        return text
    
    text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
    
    # 查缓存
    conn = _get_db()
    row = conn.execute(
        "SELECT translated FROM translations WHERE text_hash = ?", 
        (text_hash,)
    ).fetchone()
    conn.close()
    
    if row:
        return row[0]
    
    # 调用翻译 API
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text[:500],  # 限制长度
            "langpair": f"{source_lang}|{target_lang}",
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and translated != text:
                # 存缓存
                conn = _get_db()
                conn.execute(
                    "INSERT OR REPLACE INTO translations (text_hash, original, translated) VALUES (?, ?, ?)",
                    (text_hash, text[:200], translated),
                )
                conn.commit()
                conn.close()
                return translated
    except Exception as e:
        print(f"[翻译] API 调用失败: {e}")
    
    return text  # 失败返回原文


def translate_news_item(news_item):
    """
    翻译一条新闻的标题和摘要（仅英文源）
    返回翻译后的文本，非英文源返回 None
    """
    if news_item.get("lang") != "en":
        return None
    
    title = news_item.get("title", "")
    summary = news_item.get("summary", "")
    
    translated_title = translate(title)
    translated_summary = translate(summary) if summary else ""
    
    return {
        "title_zh": translated_title if translated_title != title else "",
        "summary_zh": translated_summary if translated_summary != summary else "",
    }

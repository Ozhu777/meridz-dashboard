"""
新闻源采集模块
支持多个免费数据源：Finnhub、东方财富、华尔街见闻、RSS
内置内容过滤：自动过滤券商研报类内容，只保留实时事件新闻
"""

import re
import time
import uuid
import hashlib
import requests
import feedparser
from datetime import datetime, timezone, timedelta

_EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://finance.eastmoney.com/",
}

# ─── 券商研报/分析类内容 过滤规则 ─────────────────────────
# 标题匹配这些模式的文章会被过滤掉
_BROKERAGE_PATTERNS = [
    r"^.*证券\s*[：:].*",          # XX证券：xxx
    r"^.*研报\s*[：:].*",           # XX研报：xxx
    r"(.{2,8}证券)",               # 任何"XX证券"
    r"(周报|月报|年报|点评)",        # 周期性报告
    r"(投资策略|配置建议|仓位管理)",  # 策略建议
    r"(机构调研|研报精华|研报精选)",  # 研报聚合
    r"^\【.*证券.*\】",             # 【XX证券】xxx
    r"(首席.*?认为|分析师.*?表示|分析师.*?指出)",  # 分析师观点
    r"(维持.*?评级|上调|下调.*?评级|给予.*?评级)", # 评级调整
    r"(目标价|盈利预测|EPS|PE估值)",              # 估值指标
    r"(基金.*?提示|ETF.*?溢价|LOF.*?溢价)",      # 基金提示
]

# 实时事件类内容加分关键词
_EVENT_BOOST_KEYWORDS = [
    # 政策宣布
    r"(宣布|公布|发布|签署|签署|生效|实施|通过|批准)",
    # 数据发布
    r"(GDP|CPI|PPI|PMI|非农|失业率|就业|零售|进出口|贸易数据|通胀数据)",
    # 央行动作
    r"(加息|降息|利率决议|FOMC|议息|维持利率|政策利率|基准利率)",
    # 地缘冲突
    r"(导弹|袭击|爆炸|制裁|停火|军事|战争|冲突|谈判|撤军|进攻)",
    # 市场异动
    r"(暴跌|暴涨|熔断|大跌|大涨|崩盘|跳水|拉升|闪崩|涨停|跌停)",
    # 重要人事/政策
    r"(当选|辞职|任命|解职|罢免|换届|提名)",
    # 紧急事件
    r"(突发|紧急|刚刚|快讯|即时)",
]


def _is_brokerage_content(title, summary=""):
    """判断是否为券商研报/分析类内容"""
    text = f"{title} {summary}"
    for pattern in _BROKERAGE_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def _get_event_boost(title, summary=""):
    """计算实时事件加分（0-10）"""
    text = f"{title} {summary}"
    boost = 0
    for pattern in _EVENT_BOOST_KEYWORDS:
        if re.search(pattern, text, re.IGNORECASE):
            boost += 2
    return min(boost, 10)


def _clean_html(text):
    """清理 HTML 标签和多余空白"""
    if not text:
        return ""
    # 移除 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 移除 HTML 实体
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    # 移除多余空白和换行
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─── Finnhub 全球市场新闻 ─────────────────────────────────
def fetch_finnhub_news(api_key="", limit=50):
    """从 Finnhub 获取全球市场新闻（需要免费 API Key）"""
    if not api_key:
        return []
    news_list = []
    try:
        url = "https://finnhub.io/api/v1/news"
        params = {"category": "general-market", "token": api_key}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data[:limit]:
                news_list.append({
                    "id": hashlib.md5((item.get("url", "") or "").encode()).hexdigest(),
                    "title": _clean_html(item.get("headline", "")),
                    "summary": _clean_html(item.get("summary", ""))[:200],
                    "source": item.get("source", "Finnhub"),
                    "url": item.get("url", ""),
                    "image": item.get("image", ""),
                    "timestamp": item.get("datetime", 0),
                    "category": item.get("category", ""),
                    "tags": item.get("related", ""),
                    "lang": "en",
                })
    except Exception as e:
        print(f"[Finnhub] 请求失败: {e}")
    return news_list


# ─── 东方财富通用采集 ──────────────────────────────────────
def _fetch_eastmoney_column(column_id, source_label, limit=50):
    """东方财富通用栏目采集"""
    news_list = []
    try:
        url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
        params = {
            "client": "web",
            "biz": "web_news_col",
            "column": str(column_id),
            "order": "1",
            "page_index": "1",
            "page_size": str(limit),
            "req_trace": uuid.uuid4().hex[:16],
        }
        resp = requests.get(url, params=params, headers=_EASTMONEY_HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("list", []) or []
            for item in items:
                title = _clean_html(item.get("title", ""))
                summary = _clean_html(item.get("summary", "") or "")[:200]
                if _is_brokerage_content(title, summary):
                    continue  # 跳过券商研报类
                news_list.append({
                    "id": hashlib.md5(str(item.get("code", "")).encode()).hexdigest(),
                    "title": title,
                    "summary": summary,
                    "source": source_label,
                    "url": item.get("url", item.get("uniqueUrl", "")),
                    "image": item.get("image", ""),
                    "timestamp": item.get("showTime", ""),
                    "category": "",
                    "tags": "",
                    "lang": "zh",
                    "event_boost": _get_event_boost(title, summary),
                })
    except Exception as e:
        print(f"[{source_label}] 请求失败: {e}")
    return news_list


def fetch_eastmoney_news(limit=80):
    """7x24 快讯 (column 350) - 扩大采集量，自动过滤研报"""
    return _fetch_eastmoney_column("350", "东方财富", limit)


# ─── 华尔街见闻 全球实时快讯 ──────────────────────────────
def fetch_wallstreetcn_news(limit=40):
    """华尔街见闻全球频道 - 优秀的全球实时快讯源"""
    news_list = []
    try:
        url = "https://api.wallstreetcn.com/apiv1/content/lives"
        params = {
            "channel": "global-channel",
            "limit": str(limit),
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Referer": "https://wallstreetcn.com/global",
            "Accept": "application/json",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[华尔街见闻] HTTP {resp.status_code}")
            return news_list
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        if not items:
            print(f"[华尔街见闻] 无数据")
            return news_list
        for item in items:
            item_id = item.get("id")
            if not item_id:
                continue
            # 优先用 title，其次用 content_text
            title = _clean_html(item.get("title", "").strip())
            content_text = _clean_html((item.get("content_text", "") or "").strip())
            if not title:
                title = content_text[:60] if content_text else ""
            if not title:
                continue
            summary = content_text[:200]
            if _is_brokerage_content(title, summary):
                continue
            display_time = item.get("display_time", 0)
            article = item.get("article") or {}
            news_list.append({
                "id": hashlib.md5(str(item_id).encode()).hexdigest(),
                "title": title,
                "summary": summary,
                "source": "华尔街见闻",
                "url": article.get("uri", ""),
                "image": item.get("image", "") or "",
                "timestamp": display_time,
                "category": "",
                "tags": " ".join(item.get("channels", [])),
                "lang": "zh",
                "event_boost": _get_event_boost(title, summary),
            })
        print(f"[华尔街见闻] 获取 {len(news_list)} 条")
    except Exception as e:
        print(f"[华尔街见闻] 请求失败: {e}")
    return news_list


# ─── RSS 源 ────────────────────────────────────────────────
RSS_SOURCES = [
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "lang": "en",
    },
    {
        "name": "Reuters Markets",
        "url": "https://feeds.reuters.com/reuters/marketsNews",
        "lang": "en",
    },
    {
        "name": "BBC Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "lang": "en",
    },
    {
        "name": "CNBC Top News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "lang": "en",
    },
]


def fetch_rss_feeds(max_per_source=20):
    """从 RSS 源获取新闻"""
    news_list = []
    for source in RSS_SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:max_per_source]:
                published = entry.get("published_parsed", entry.get("updated_parsed"))
                ts = int(time.mktime(published)) if published else int(time.time())
                title = _clean_html(entry.get("title", ""))
                summary = _clean_html(entry.get("summary", ""))[:200] if entry.get("summary") else ""
                if _is_brokerage_content(title, summary):
                    continue
                news_list.append({
                    "id": hashlib.md5((entry.get("link", "") or entry.get("title", "")).encode()).hexdigest(),
                    "title": title,
                    "summary": summary,
                    "source": source["name"],
                    "url": entry.get("link", ""),
                    "image": "",
                    "timestamp": ts,
                    "category": "",
                    "tags": "",
                    "lang": source["lang"],
                    "event_boost": _get_event_boost(title, summary),
                })
        except Exception as e:
            print(f"[RSS] {source['name']} 获取失败: {e}")
    return news_list


# ─── 汇总采集 ──────────────────────────────────────────────
def fetch_all_news(finnhub_api_key=""):
    """从所有可用源采集新闻，去重，并过滤券商研报类内容"""
    all_news = []
    filtered_count = 0

    # 1. 华尔街见闻（全球实时快讯 - 优先级最高）
    print("[采集] 华尔街见闻 全球快讯...")
    items = fetch_wallstreetcn_news(40)
    filtered_count += 40 - len(items)
    all_news.extend(items)
    time.sleep(0.3)

    # 2. 东方财富 7x24 快讯
    print("[采集] 东方财富 7x24 快讯...")
    items = fetch_eastmoney_news(80)
    filtered_count += 80 - len(items)
    all_news.extend(items)
    time.sleep(0.3)

    # 3. Finnhub（需要 Key - 全球新闻质量最高）
    if finnhub_api_key:
        print("[采集] Finnhub 全球市场新闻...")
        all_news.extend(fetch_finnhub_news(finnhub_api_key, 50))
        time.sleep(0.3)
    else:
        print("[采集] Finnhub 跳过（未配置 API Key）→ 推荐注册获取免费 Key")

    # 4. RSS 国际源
    print("[采集] RSS 国际源 (Reuters/BBC/CNBC)...")
    items = fetch_rss_feeds(15)
    filtered_count += 60 - len(items)
    all_news.extend(items)

    # 去重
    seen_ids = set()
    unique_news = []
    for item in all_news:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_news.append(item)

    print(f"[采集] 共获取 {len(unique_news)} 条新闻（过滤掉 {filtered_count} 条研报类内容）")
    return unique_news


# ─── 时间格式化 ─────────────────────────────────────────────
def format_time(ts):
    """将各种时间戳格式统一为可读时间"""
    if isinstance(ts, (int, float)):
        if ts > 1e12:  # 毫秒级
            ts = ts / 1000
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
            return dt.strftime("%m-%d %H:%M")
        except (OSError, ValueError):
            return str(ts)
    elif isinstance(ts, str):
        # 处理 "2026-04-12 10:01:23" 格式
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(ts.strip(), fmt)
                return dt.strftime("%m-%d %H:%M")
            except ValueError:
                continue
        # 华尔街见闻格式 "2026-04-12T20:30:00+08:00"
        for fmt in ("%Y-%m-%dT%H:%M:%S%z",):
            try:
                dt = datetime.strptime(ts.strip(), fmt)
                dt = dt.astimezone(timezone(timedelta(hours=8)))
                return dt.strftime("%m-%d %H:%M")
            except ValueError:
                continue
        return ts[:16]
    return str(ts)[:16]

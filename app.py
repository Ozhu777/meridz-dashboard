"""
全球宏观新闻 Dashboard
- 多源新闻采集（Finnhub、华尔街见闻、东方财富、Reuters/BBC/CNBC）
- 定制化重要性评分 + 实时事件加分
- 英文新闻自动中文翻译
- 中文界面，问卷可实时调整
- 飞书/微信推送
"""

import json
import streamlit as st
from datetime import datetime, timezone, timedelta

import config
from news_sources import fetch_all_news, format_time
from scorer import score_news, get_score_color, get_score_label
from translator import translate_news_item

# ─── Page Config ───────────────────────────────────────────
st.set_page_config(
    page_title="全球宏观新闻",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── UI 设计系统 ──────────────────────────────────────────
# 参考：Bloomberg Terminal + Apple News 风格
# 浅色主题，蓝灰色调，卡片式布局
PRIMARY = "#2563eb"
BG_DARK = "#f8fafc"
BG_CARD = "#ffffff"
TEXT_PRIMARY = "#0f172a"
TEXT_SECONDARY = "#64748b"
BORDER = "#e2e8f0"
ACCENT_RED = "#dc2626"
ACCENT_AMBER = "#d97706"
ACCENT_GREEN = "#059669"

st.markdown(f"""
<style>
    /* ─── 全局 ─── */
    .stApp {{ background-color: {BG_DARK}; }}
    
    /* ─── 侧边栏：浅色主题 ─── */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%) !important;
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] * {{
        color: {TEXT_PRIMARY} !important;
    }}
    section[data-testid="stSidebar"] .stMarkdown p, 
    section[data-testid="stSidebar"] label {{
        color: {TEXT_PRIMARY} !important;
    }}
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{
        color: {TEXT_PRIMARY} !important;
        font-weight: 700 !important;
    }}
    
    /* ─── 侧边栏滑块 ─── */
    .stSlider [data-baseweb="slider"] {{
        background-color: #e2e8f0 !important;
    }}
    
    /* ─── 新闻卡片 ─── */
    .news-card {{
        background: {BG_CARD};
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 8px;
        border-left: 3px solid {BORDER};
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: all 0.15s ease;
    }}
    .news-card:hover {{
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }}
    .news-card.high {{ border-left-color: {ACCENT_RED}; }}
    .news-card.medium {{ border-left-color: {ACCENT_AMBER}; }}
    .news-card.low {{ border-left-color: {BORDER}; }}
    
    .news-title {{
        font-size: 15px;
        font-weight: 600;
        color: {TEXT_PRIMARY};
        line-height: 1.5;
        margin-bottom: 4px;
    }}
    .news-translation {{
        font-size: 13px;
        color: {TEXT_SECONDARY};
        line-height: 1.5;
        margin: 4px 0 6px;
        padding: 6px 10px;
        background: #f1f5f9;
        border-radius: 6px;
    }}
    .news-meta {{
        font-size: 12px;
        color: #94a3b8;
        display: flex;
        gap: 8px;
        align-items: center;
    }}
    .news-tag {{
        display: inline-block;
        padding: 1px 8px;
        border-radius: 10px;
        font-size: 11px;
        background: #f1f5f9;
        color: {TEXT_SECONDARY};
        margin: 2px 2px 2px 0;
    }}
    .news-link {{
        font-size: 12px;
        color: {PRIMARY};
        text-decoration: none;
    }}
    .news-link:hover {{ text-decoration: underline; }}
    .news-summary {{
        font-size: 13px;
        color: #475569;
        line-height: 1.6;
        margin-top: 4px;
    }}
    
    /* ─── 统计卡片 ─── */
    .stat-card {{
        background: {BG_CARD};
        border-radius: 10px;
        padding: 12px 16px;
        border: 1px solid {BORDER};
    }}
    .stat-number {{
        font-size: 28px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}
    .stat-label {{
        font-size: 12px;
        color: {TEXT_SECONDARY};
    }}
    
    /* ─── 头部 ─── */
    .header-bar {{
        background: {BG_CARD};
        border-radius: 12px;
        padding: 16px 24px;
        border: 1px solid {BORDER};
        margin-bottom: 16px;
    }}
    
    /* ─── 隐藏 Streamlit 默认元素 ─── */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    .stDeployButton {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)


# ─── Session State ─────────────────────────────────────────
if "news_data" not in st.session_state:
    st.session_state.news_data = []
    st.session_state.last_fetch = None
    st.session_state.finnhub_key = ""

if "config" not in st.session_state:
    st.session_state.config = config.load_config()


# ═══════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ 定制化设置")
    st.caption("调整后点击「保存」生效")

    # API Key
    st.markdown("---")
    st.markdown("**🔑 API 配置**")
    finnhub_key = st.text_input(
        "Finnhub API Key",
        value=st.session_state.finnhub_key,
        type="password",
        help="finnhub.io 免费注册获取",
    )
    st.session_state.finnhub_key = finnhub_key
    st.session_state.config.setdefault("push", {})["finnhub_key"] = finnhub_key

    # ── 地理关注区域 ──
    st.markdown("---")
    st.markdown("**🌍 地理关注区域**")
    for i, item in enumerate(st.session_state.config.get("geography", [])):
        col1, col2 = st.columns([1.6, 1])
        enabled = col1.checkbox(item["name"], value=item.get("enabled", False), key=f"geo_{i}")
        weight = col2.slider("", 0, 50, value=item.get("weight", 0), key=f"geo_w_{i}")
        st.session_state.config["geography"][i]["enabled"] = enabled
        st.session_state.config["geography"][i]["weight"] = weight

    # ── 事件类型 ──
    st.markdown("---")
    st.markdown("**⚡ 事件类型**")
    for i, item in enumerate(st.session_state.config.get("events", [])):
        col1, col2 = st.columns([1.6, 1])
        enabled = col1.checkbox(item["name"], value=item.get("enabled", False), key=f"evt_{i}")
        weight = col2.slider("", 0, 50, value=item.get("weight", 0), key=f"evt_w_{i}")
        st.session_state.config["events"][i]["enabled"] = enabled
        st.session_state.config["events"][i]["weight"] = weight

    # ── 资产类别 ──
    st.markdown("---")
    st.markdown("**📈 资产类别联动**")
    for i, item in enumerate(st.session_state.config.get("assets", [])):
        col1, col2 = st.columns([1.6, 1])
        enabled = col1.checkbox(item["name"], value=item.get("enabled", False), key=f"ast_{i}")
        weight = col2.slider("", 0, 50, value=item.get("weight", 0), key=f"ast_w_{i}")
        st.session_state.config["assets"][i]["enabled"] = enabled
        st.session_state.config["assets"][i]["weight"] = weight

    # ── 过滤 ──
    st.markdown("---")
    st.markdown("**🎯 过滤偏好**")
    min_imp = st.slider("最低重要性分数", 0, 100,
        value=st.session_state.config.get("filter", {}).get("min_importance", 15))
    st.session_state.config["filter"]["min_importance"] = min_imp

    # ── 推送 ──
    st.markdown("---")
    st.markdown("**📢 推送设置**")
    push_cfg = st.session_state.config.get("push", {})
    push_on = st.toggle("启用自动推送", value=push_cfg.get("enabled", False), key="push_enabled")
    st.session_state.config.setdefault("push", {})["enabled"] = push_on

    if push_on:
        wh = st.text_input("飞书 Webhook", value=push_cfg.get("feishu_webhook", ""), type="password", key="wh")
        st.session_state.config["push"]["feishu_webhook"] = wh
        pp = st.text_input("PushPlus Token", value=push_cfg.get("pushplus_token", ""), type="password", key="pp")
        st.session_state.config["push"]["pushplus_token"] = pp
        pt = st.text_input("PushPlus 群组ID（可选）", value=push_cfg.get("pushplus_topic", ""), key="pt")
        st.session_state.config["push"]["pushplus_topic"] = pt
        st.caption("启动守护进程：`python3 ~/projects/macro-news-dashboard/push_daemon.py`")

    # ── 保存/重置 ──
    st.markdown("---")
    col_s, col_r = st.columns(2)
    if col_s.button("💾 保存", use_container_width=True, type="primary"):
        config.save_config(st.session_state.config)
        st.success("✅ 已保存")
    if col_r.button("🔄 重置", use_container_width=True):
        config.reset_config()
        st.session_state.config = config.load_config()
        st.rerun()


# ═══════════════════════════════════════════════════════════
# MAIN PAGE
# ═══════════════════════════════════════════════════════════

# Header
now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

col_btn, col_title, col_time = st.columns([1, 3, 1.5])
with col_btn:
    if st.button("🔄 刷新新闻", use_container_width=True, type="primary"):
        with st.spinner("采集新闻中..."):
            news = fetch_all_news(finnhub_key)
            for item in news:
                scoring = score_news(item, st.session_state.config)
                item["score"] = scoring["score"]
                item["score_details"] = scoring
                item["time_str"] = format_time(item.get("timestamp", ""))
                # 英文翻译
                tr = translate_news_item(item)
                if tr:
                    item["title_zh"] = tr["title_zh"]
                    item["summary_zh"] = tr["summary_zh"]
                else:
                    item["title_zh"] = ""
                    item["summary_zh"] = ""
            news.sort(key=lambda x: x.get("score", 0), reverse=True)
            st.session_state.news_data = news
            st.session_state.last_fetch = now_str

with col_title:
    st.markdown(f"<h2 style='margin:0'>🌐 全球宏观新闻</h2>", unsafe_allow_html=True)

with col_time:
    if st.session_state.last_fetch:
        st.markdown(
            f"<p style='text-align:right;color:#94a3b8;font-size:13px;margin:8px 0'>"
            f"上次刷新: {st.session_state.last_fetch}  ·  {len(st.session_state.news_data)} 条</p>",
            unsafe_allow_html=True,
        )

# Stats bar
if st.session_state.news_data:
    scores = [n.get("score", 0) for n in st.session_state.news_data]
    min_s = st.session_state.config["filter"]["min_importance"]
    filtered = [n for n in st.session_state.news_data if n.get("score", 0) >= min_s]

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.markdown(f"<div class='stat-card'><div class='stat-number'>{len(st.session_state.news_data)}</div><div class='stat-label'>📰 总新闻</div></div>", unsafe_allow_html=True)
    sc2.markdown(f"<div class='stat-card'><div class='stat-number' style='color:{ACCENT_RED}'>{len([s for s in scores if s >= 50])}</div><div class='stat-label'>🔥 高重要性</div></div>", unsafe_allow_html=True)
    sc3.markdown(f"<div class='stat-card'><div class='stat-number' style='color:{ACCENT_AMBER}'>{len([s for s in scores if 25 <= s < 50])}</div><div class='stat-label'>⚡ 中重要性</div></div>", unsafe_allow_html=True)
    sc4.markdown(f"<div class='stat-card'><div class='stat-number' style='color:{PRIMARY}'>{len(filtered)}</div><div class='stat-label'>✅ 符合筛选</div></div>", unsafe_allow_html=True)

    # ─── News Feed ───────────────────────────────────────
    st.markdown("")
    for n in st.session_state.news_data:
        score = n.get("score", 0)
        if score < min_s:
            continue

        if score >= 50:
            card_cls = "high"
        elif score >= 25:
            card_cls = "medium"
        else:
            card_cls = "low"

        title = n.get("title", "无标题")
        summary = n.get("summary", "")
        source = n.get("source", "未知")
        time_str = n.get("time_str", "")
        url = n.get("url", "")
        lang = n.get("lang", "en")

        # 翻译
        title_zh = n.get("title_zh", "")
        summary_zh = n.get("summary_zh", "")

        # 匹配标签
        matched = n.get("score_details", {}).get("matched", {})
        tags_html = ""
        for dim, items in matched.items():
            for t in items[:2]:
                labels = {"地理": "🌍", "事件": "⚡", "资产": "📈"}
                icon = labels.get(dim, "")
                tags_html += f'<span class="news-tag">{icon} {t}</span>'

        # 来源语言标记
        lang_flag = "🇨🇳" if lang == "zh" else "🌐"

        # 重要性标记
        if score >= 60:
            imp_label = f'<span style="color:{ACCENT_RED};font-weight:700;font-size:12px">极度重要</span>'
        elif score >= 40:
            imp_label = f'<span style="color:{ACCENT_AMBER};font-weight:700;font-size:12px">重要</span>'
        else:
            imp_label = f'<span style="color:#94a3b8;font-size:12px">一般</span>'

        # 翻译块
        translation_html = ""
        if title_zh:
            translation_html = f'<div class="news-translation">💬 {title_zh}</div>'

        # 摘要
        summary_html = ""
        if summary and len(summary) > 10:
            summary_html = f'<div class="news-summary">{summary[:150]}</div>'

        # 链接
        link_html = ""
        if url:
            link_html = f'<a href="{url}" target="_blank" class="news-link">🔗 原文链接</a>'

        card_html = f'''
        <div class="news-card {card_cls}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
                <div class="news-title">{title}</div>
                {imp_label}
            </div>
            {translation_html}
            {summary_html}
            <div class="news-meta">
                <span>{time_str}</span>
                <span>·</span>
                <span>{lang_flag} {source}</span>
                <span>·</span>
                {tags_html}
                {f'<span style="margin-left:auto">{link_html}</span>' if link_html else ''}
            </div>
        </div>
        '''
        st.markdown(card_html, unsafe_allow_html=True)

    if not filtered:
        st.info("📭 没有符合筛选条件的新闻，试试降低最低重要性分数")

else:
    st.markdown("""
    <div style="text-align:center;padding:80px">
        <h2 style="color:#0f172a">🌐 全球宏观新闻 Dashboard</h2>
        <p style="color:#64748b;font-size:16px;margin-top:12px">
            点击左上角「刷新新闻」开始<br>
            <span style="font-size:13px">
                数据源：华尔街见闻 + 东方财富 + Finnhub + Reuters + BBC + CNBC
            </span>
        </p>
    </div>
    """, unsafe_allow_html=True)

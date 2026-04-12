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
    .stApp {{ background-color: {BG_DARK}; }}
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%) !important;
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] * {{ color: {TEXT_PRIMARY} !important; }}
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] label {{ color: {TEXT_PRIMARY} !important; }}
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{ color: {TEXT_PRIMARY} !important; font-weight: 700 !important; }}
    .stSlider [data-baseweb="slider"] {{ background-color: #e2e8f0 !important; }}
    .news-card {{
        background: {BG_CARD}; border-radius: 12px; padding: 16px 20px;
        margin-bottom: 8px; border-left: 3px solid {BORDER};
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    .news-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
    .news-card.high {{ border-left-color: {ACCENT_RED}; }}
    .news-card.medium {{ border-left-color: {ACCENT_AMBER}; }}
    .news-card.low {{ border-left-color: {BORDER}; }}
    .news-title {{
        font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};
        line-height: 1.5; margin-bottom: 4px;
    }}
    .news-translation {{
        font-size: 13px; color: {TEXT_SECONDARY}; line-height: 1.5;
        margin: 4px 0 6px; padding: 6px 10px;
        background: #f1f5f9; border-radius: 6px;
    }}
    .news-meta {{
        font-size: 12px; color: #94a3b8;
        display: flex; gap: 8px; align-items: center;
    }}
    .news-tag {{
        display: inline-block; padding: 1px 8px; border-radius: 10px;
        font-size: 11px; background: #f1f5f9; color: {TEXT_SECONDARY};
        margin: 2px 2px 2px 0;
    }}
    .news-link {{ font-size: 12px; color: {PRIMARY}; text-decoration: none; }}
    .news-link:hover {{ text-decoration: underline; }}
    .news-summary {{ font-size: 13px; color: #475569; line-height: 1.6; margin-top: 4px; }}
    .stat-card {{
        background: {BG_CARD}; border-radius: 10px;
        padding: 12px 16px; border: 1px solid {BORDER};
        cursor: pointer; transition: all 0.15s ease;
        user-select: none;
    }}
    .stat-card:hover {{
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transform: translateY(-1px);
        border-color: {PRIMARY};
    }}
    .stat-card.active {{
        border-color: {PRIMARY};
        box-shadow: 0 0 0 2px rgba(37,99,235,0.2);
    }}
    .stat-number {{ font-size: 28px; font-weight: 700; color: {TEXT_PRIMARY}; }}
    .stat-label {{ font-size: 12px; color: {TEXT_SECONDARY}; }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    .stDeployButton {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)


# ─── 新闻采集函数 ─────────────────────────────────────────
def _fetch_and_score(finnhub_key):
    """采集 + 评分 + 翻译"""
    news = fetch_all_news(finnhub_key)
    for item in news:
        scoring = score_news(item, st.session_state.config)
        item["score"] = scoring["score"]
        item["score_details"] = scoring
        item["time_str"] = format_time(item.get("timestamp", ""))
        tr = translate_news_item(item)
        if tr:
            item["title_zh"] = tr["title_zh"]
            item["summary_zh"] = tr["summary_zh"]
        else:
            item["title_zh"] = ""
            item["summary_zh"] = ""
    news.sort(key=lambda x: x.get("score", 0), reverse=True)
    return news


# ─── Session State ─────────────────────────────────────────
if "news_data" not in st.session_state:
    st.session_state.news_data = []
    st.session_state.last_fetch = None
    st.session_state.finnhub_key = ""
    st.session_state.fetched_once = False

if "config" not in st.session_state:
    st.session_state.config = config.load_config()

if "filter_mode" not in st.session_state:
    st.session_state.filter_mode = "all"  # all / high / medium / qualified


# ═══════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ 定制化设置")
    st.caption("调整后点击「保存」生效")

    st.markdown("---")
    st.markdown("**🔑 API 配置**")
    finnhub_key = st.text_input(
        "Finnhub API Key", value=st.session_state.finnhub_key,
        type="password", help="finnhub.io 免费注册获取",
    )
    st.session_state.finnhub_key = finnhub_key
    st.session_state.config.setdefault("push", {})["finnhub_key"] = finnhub_key

    st.markdown("---")
    st.markdown("**🌍 地理关注区域**")
    for i, item in enumerate(st.session_state.config.get("geography", [])):
        col1, col2 = st.columns([1.6, 1])
        enabled = col1.checkbox(item["name"], value=item.get("enabled", False), key=f"geo_{i}")
        weight = col2.slider("", 0, 50, value=item.get("weight", 0), key=f"geo_w_{i}")
        st.session_state.config["geography"][i]["enabled"] = enabled
        st.session_state.config["geography"][i]["weight"] = weight

    st.markdown("---")
    st.markdown("**⚡ 事件类型**")
    for i, item in enumerate(st.session_state.config.get("events", [])):
        col1, col2 = st.columns([1.6, 1])
        enabled = col1.checkbox(item["name"], value=item.get("enabled", False), key=f"evt_{i}")
        weight = col2.slider("", 0, 50, value=item.get("weight", 0), key=f"evt_w_{i}")
        st.session_state.config["events"][i]["enabled"] = enabled
        st.session_state.config["events"][i]["weight"] = weight

    st.markdown("---")
    st.markdown("**📈 资产类别联动**")
    for i, item in enumerate(st.session_state.config.get("assets", [])):
        col1, col2 = st.columns([1.6, 1])
        enabled = col1.checkbox(item["name"], value=item.get("enabled", False), key=f"ast_{i}")
        weight = col2.slider("", 0, 50, value=item.get("weight", 0), key=f"ast_w_{i}")
        st.session_state.config["assets"][i]["enabled"] = enabled
        st.session_state.config["assets"][i]["weight"] = weight

    st.markdown("---")
    st.markdown("**🎯 过滤偏好**")
    min_imp = st.slider("最低重要性分数", 0, 100,
        value=st.session_state.config.get("filter", {}).get("min_importance", 15))
    st.session_state.config["filter"]["min_importance"] = min_imp

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
# AUTO-FETCH: 首次打开自动加载
# ═══════════════════════════════════════════════════════════
if not st.session_state.fetched_once:
    with st.spinner("🌐 正在加载全球新闻..."):
        st.session_state.news_data = _fetch_and_score(finnhub_key)
        st.session_state.last_fetch = datetime.now(
            timezone(timedelta(hours=8))
        ).strftime("%Y-%m-%d %H:%M")
        st.session_state.fetched_once = True


# ═══════════════════════════════════════════════════════════
# MAIN PAGE
# ═══════════════════════════════════════════════════════════
now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

col_btn, col_title, col_time = st.columns([1, 3, 1.5])
with col_btn:
    if st.button("🔄 刷新新闻", use_container_width=True, type="primary"):
        with st.spinner("采集新闻中..."):
            st.session_state.news_data = _fetch_and_score(finnhub_key)
            st.session_state.last_fetch = now_str

with col_title:
    st.markdown(f"<h2 style='margin:0'>🌐 全球宏观新闻</h2>", unsafe_allow_html=True)

with col_time:
    if st.session_state.last_fetch:
        st.markdown(
            f"<p style='text-align:right;color:#94a3b8;font-size:13px;margin:8px 0'>"
            f"上次刷新: {st.session_state.last_fetch}  ·  "
            f"{len(st.session_state.news_data)} 条</p>",
            unsafe_allow_html=True,
        )

# ─── 统计卡片（可点击筛选）───────────────────────────────
if st.session_state.news_data:
    all_data = st.session_state.news_data
    scores = [n.get("score", 0) for n in all_data]
    min_s = st.session_state.config["filter"]["min_importance"]
    high_count = len([s for s in scores if s >= 50])
    med_count = len([s for s in scores if 25 <= s < 50])
    qualified = [n for n in all_data if n.get("score", 0) >= min_s]

    # 4 个可点击的统计卡片
    sc1, sc2, sc3, sc4 = st.columns(4)

    active_all = st.session_state.filter_mode == "all"
    active_high = st.session_state.filter_mode == "high"
    active_med = st.session_state.filter_mode == "medium"
    active_q = st.session_state.filter_mode == "qualified"

    sc1.markdown(
        f"<div class='stat-card {\"active\" if active_all else \"\"}' "
        f"onclick=\"window.parent.postMessage('{{action: \"set_filter\", value: \"all\"}}', '*')\">"
        f"<div class='stat-number'>{len(all_data)}</div>"
        f"<div class='stat-label'>📰 总新闻 {'◀ 当前' if active_all else ''}</div></div>",
        unsafe_allow_html=True,
    )
    if sc1.button("📰 总新闻", use_container_width=True, key="filter_all"):
        st.session_state.filter_mode = "all"
        st.rerun()

    sc2.markdown(
        f"<div class='stat-card {\"active\" if active_high else \"\"}'>"
        f"<div class='stat-number' style='color:{ACCENT_RED}'>{high_count}</div>"
        f"<div class='stat-label'>🔥 高重要性 {'◀ 当前' if active_high else ''}</div></div>",
        unsafe_allow_html=True,
    )
    if sc2.button("🔥 高重要性", use_container_width=True, key="filter_high"):
        st.session_state.filter_mode = "high"
        st.rerun()

    sc3.markdown(
        f"<div class='stat-card {\"active\" if active_med else \"\"}'>"
        f"<div class='stat-number' style='color:{ACCENT_AMBER}'>{med_count}</div>"
        f"<div class='stat-label'>⚡ 中重要性 {'◀ 当前' if active_med else ''}</div></div>",
        unsafe_allow_html=True,
    )
    if sc3.button("⚡ 中重要性", use_container_width=True, key="filter_med"):
        st.session_state.filter_mode = "medium"
        st.rerun()

    sc4.markdown(
        f"<div class='stat-card {\"active\" if active_q else \"\"}'>"
        f"<div class='stat-number' style='color:{PRIMARY}'>{len(qualified)}</div>"
        f"<div class='stat-label'>✅ 符合筛选 {'◀ 当前' if active_q else ''}</div></div>",
        unsafe_allow_html=True,
    )
    if sc4.button("✅ 符合筛选", use_container_width=True, key="filter_q"):
        st.session_state.filter_mode = "qualified"
        st.rerun()

    # 根据筛选模式决定显示哪些新闻
    mode = st.session_state.filter_mode
    if mode == "high":
        display_news = [n for n in all_data if n.get("score", 0) >= 50]
        filter_label = "🔥 高重要性新闻"
    elif mode == "medium":
        display_news = [n for n in all_data if 25 <= n.get("score", 0) < 50]
        filter_label = "⚡ 中重要性新闻"
    elif mode == "qualified":
        display_news = qualified
        filter_label = f"✅ 符合筛选（≥{min_s}分）"
    else:
        display_news = [n for n in all_data if n.get("score", 0) >= min_s]
        filter_label = ""

    if filter_label:
        st.markdown(f"<p style='color:{TEXT_SECONDARY};font-size:14px;margin:4px 0 8px;font-weight:600'>{filter_label}</p>", unsafe_allow_html=True)

    # ─── 新闻卡片渲染 ───────────────────────────────────
    def render_card(n):
        score = n.get("score", 0)
        card_cls = "high" if score >= 50 else ("medium" if score >= 25 else "low")
        title = n.get("title", "无标题")
        summary = n.get("summary", "")
        source = n.get("source", "未知")
        time_str = n.get("time_str", "")
        url = n.get("url", "")
        lang = n.get("lang", "en")
        title_zh = n.get("title_zh", "")
        matched = n.get("score_details", {}).get("matched", {})
        tags_html = ""
        for dim, items in matched.items():
            for t in items[:2]:
                icon = {"地理": "🌍", "事件": "⚡", "资产": "📈"}.get(dim, "")
                tags_html += f'<span class="news-tag">{icon} {t}</span>'
        lang_flag = "🇨🇳" if lang == "zh" else "🌐"
        if score >= 60:
            imp_label = f'<span style="color:{ACCENT_RED};font-weight:700;font-size:12px">极度重要</span>'
        elif score >= 40:
            imp_label = f'<span style="color:{ACCENT_AMBER};font-weight:700;font-size:12px">重要</span>'
        else:
            imp_label = f'<span style="color:#94a3b8;font-size:12px">一般</span>'
        translation_html = f'<div class="news-translation">💬 {title_zh}</div>' if title_zh else ""
        summary_html = f'<div class="news-summary">{summary[:150]}</div>' if summary and len(summary) > 10 else ""
        link_html = f'<a href="{url}" target="_blank" class="news-link">🔗 原文链接</a>' if url else ""
        st.markdown(f'''<div class="news-card {card_cls}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
                <div class="news-title">{title}</div>{imp_label}
            </div>
            {translation_html}{summary_html}
            <div class="news-meta"><span>{time_str}</span><span>·</span>
                <span>{lang_flag} {source}</span><span>·</span>{tags_html}
                {f'<span style="margin-left:auto">{link_html}</span>' if link_html else ''}
            </div></div>''', unsafe_allow_html=True)

    if display_news:
        for n in display_news:
            render_card(n)
    else:
        st.info("📭 该分类下暂无新闻")

else:
    st.markdown("""<div style="text-align:center;padding:80px">
        <h2 style="color:#0f172a">🌐 全球宏观新闻 Dashboard</h2>
        <p style="color:#64748b;font-size:16px;margin-top:12px">
            正在加载中...</p></div>""", unsafe_allow_html=True)

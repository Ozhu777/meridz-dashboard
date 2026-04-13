"""
全球宏观新闻 Dashboard
- 多源新闻采集（Finnhub、华尔街见闻、东方财富、Reuters/BBC/CNBC）
- 定制化重要性评分 + 实时事件加分
- 英文新闻自动中文翻译
- 公司分析模块（股价 + 财务 + 预期）
- 中文界面，问卷可实时调整
- 飞书/微信推送
"""

import json
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

import config
from news_sources import fetch_all_news, format_time
from scorer import score_news, get_score_color, get_score_label
from translator import translate_news_item
from stock_analysis import get_stock_data, format_number, format_pct

# ─── Page Config ───────────────────────────────────────────
st.set_page_config(
    page_title="全球宏观新闻 & 公司分析",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
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
    .fin-card {{
        background: {BG_CARD}; border-radius: 12px; padding: 16px 20px;
        border: 1px solid {BORDER}; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 8px;
    }}
    .fin-metric {{
        text-align: center; padding: 8px;
    }}
    .fin-metric-value {{
        font-size: 16px; font-weight: 700; color: {TEXT_PRIMARY};
    }}
    .fin-metric-label {{
        font-size: 11px; color: {TEXT_SECONDARY}; margin-top: 2px;
    }}
    .fin-table {{
        width: 100%; border-collapse: collapse; font-size: 13px;
    }}
    .fin-table th {{
        background: #f1f5f9; padding: 8px 12px; text-align: right;
        font-weight: 600; color: {TEXT_PRIMARY}; border-bottom: 2px solid {BORDER};
    }}
    .fin-table th:first-child {{ text-align: left; }}
    .fin-table td {{
        padding: 8px 12px; text-align: right; border-bottom: 1px solid {BORDER};
        color: {TEXT_PRIMARY};
    }}
    .fin-table td:first-child {{
        text-align: left; font-weight: 500;
    }}
    .positive {{ color: {ACCENT_GREEN}; }}
    .negative {{ color: {ACCENT_RED}; }}
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
    st.session_state.finnhub_key = "d7dp70hr01qpbt05cd7gd7dp70hr01qpbt05cd80"
    st.session_state.fetched_once = False

if "config" not in st.session_state:
    st.session_state.config = config.load_config()

if "filter_mode" not in st.session_state:
    st.session_state.filter_mode = "all"

if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

if "stock_data" not in st.session_state:
    st.session_state.stock_data = None


# ═══════════════════════════════════════════════════════════
# SIDEBAR（折叠式设置面板）
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ 筛选设置")

    if st.button("🟢 打开设置面板" if not st.session_state.show_settings else "🔴 关闭设置面板",
                 use_container_width=True, type="primary"):
        st.session_state.show_settings = not st.session_state.show_settings
        st.rerun()

    if st.session_state.show_settings:
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
        st.session_state.news_data = _fetch_and_score(st.session_state.finnhub_key)
        st.session_state.last_fetch = datetime.now(
            timezone(timedelta(hours=8))
        ).strftime("%Y-%m-%d %H:%M")
        st.session_state.fetched_once = True


# ═══════════════════════════════════════════════════════════
# TOP BAR
# ═══════════════════════════════════════════════════════════
now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

col_btn, col_title, col_time = st.columns([1, 3, 1.5])
with col_btn:
    if st.button("🔄 刷新", use_container_width=True, type="primary"):
        with st.spinner("采集新闻中..."):
            st.session_state.news_data = _fetch_and_score(st.session_state.finnhub_key)
            st.session_state.last_fetch = now_str

with col_title:
    st.markdown(f"<h2 style='margin:0'>🌐 全球宏观新闻 & 公司分析</h2>", unsafe_allow_html=True)

with col_time:
    if st.session_state.last_fetch:
        st.markdown(
            f"<p style='text-align:right;color:#94a3b8;font-size:13px;margin:8px 0'>"
            f"上次刷新: {st.session_state.last_fetch}  ·  "
            f"{len(st.session_state.news_data)} 条新闻</p>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════
# NEWS FILTER BUTTONS
# ═══════════════════════════════════════════════════════════
if st.session_state.news_data:
    all_data = st.session_state.news_data
    scores = [n.get("score", 0) for n in all_data]
    min_s = st.session_state.config["filter"]["min_importance"]

    f1, f2, f3, f4, f5 = st.columns(5)
    modes = [
        ("all", "📰 全部", len(all_data), TEXT_PRIMARY, f1),
        ("high", "🔴 非常重要", len([s for s in scores if s >= 60]), ACCENT_RED, f2),
        ("medium", "🟡 重要", len([s for s in scores if 40 <= s < 60]), ACCENT_AMBER, f3),
        ("low", "🟢 一般", len([s for s in scores if s < 40]), ACCENT_GREEN, f4),
        ("qualified", f"✅ ≥{min_s}分", len([n for n in all_data if n.get("score", 0) >= min_s]), PRIMARY, f5),
    ]
    for key, label, count, color, col in modes:
        active = st.session_state.filter_mode == key
        border = f"2px solid {color}" if active else f"1px solid {BORDER}"
        bg = f"rgba({','.join(str(int(color.lstrip('#')[i:i+2], 16)) for i in (0, 2, 4))}, 0.05)" if active else "white"
        col.markdown(
            f'''<div style="background:{bg};border:{border};border-radius:8px;padding:10px;text-align:center;cursor:pointer">
            <div style="font-size:20px;font-weight:700;color:{color}">{count}</div>
            <div style="font-size:12px;color:{TEXT_SECONDARY}">{label}</div></div>''',
            unsafe_allow_html=True,
        )
        if col.button(label, use_container_width=True, key=f"filter_{key}"):
            st.session_state.filter_mode = key
            st.rerun()

    # 筛选
    mode = st.session_state.filter_mode
    if mode == "high":
        display_news = [n for n in all_data if n.get("score", 0) >= 60]
    elif mode == "medium":
        display_news = [n for n in all_data if 40 <= n.get("score", 0) < 60]
    elif mode == "low":
        display_news = [n for n in all_data if n.get("score", 0) < 40]
    elif mode == "qualified":
        display_news = [n for n in all_data if n.get("score", 0) >= min_s]
    else:
        display_news = [n for n in all_data if n.get("score", 0) >= min_s]


# ═══════════════════════════════════════════════════════════
# MAIN CONTENT: 左新闻 + 右公司分析
# ═══════════════════════════════════════════════════════════
news_col, stock_col = st.columns([3, 2])

# ─── 左侧：新闻流 ───────────────────────────────────────
with news_col:
    if st.session_state.news_data:
        for n in display_news:
            score = n.get("score", 0)
            card_cls = "high" if score >= 60 else ("medium" if score >= 40 else "low")
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
    else:
        st.markdown("""<div style="text-align:center;padding:80px">
            <h2 style="color:#0f172a">🌐 全球宏观新闻 Dashboard</h2>
            <p style="color:#64748b;font-size:16px;margin-top:12px">正在加载中...</p></div>""", unsafe_allow_html=True)


# ─── 右侧：公司分析模块 ──────────────────────────────────
with stock_col:
    st.markdown("---")
    st.markdown("### 📊 公司分析")
    st.caption("输入公司名称或股票代码（如 Apple、AAPL、NVDA）")

    stock_input = st.text_input("搜索公司", placeholder="输入公司名称或代码...", key="stock_input", label_visibility="collapsed")

    if st.button("🔍 查询", use_container_width=True, type="secondary", key="stock_search_btn"):
        if stock_input.strip():
            with st.spinner(f"正在查询 {stock_input}..."):
                data = get_stock_data(stock_input.strip())
                st.session_state.stock_data = data
        else:
            st.warning("请输入公司名称或股票代码")

    if st.session_state.stock_data:
        d = st.session_state.stock_data
        st.markdown("---")
        st.markdown(f"#### {d['name']} ({d['symbol']})")
        st.caption(f"{d['sector']} · {d['industry']}")

        # ── 股价概览 ──
        p = d["price"]
        price_color = ACCENT_GREEN if p["change"] >= 0 else ACCENT_RED
        price_arrow = "▲" if p["change"] >= 0 else "▼"
        st.markdown(f"""
        <div class="fin-card">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY}">
                        {p['current']:.2f} <span style="font-size:14px;color:{TEXT_SECONDARY}">{d['currency']}</span></div>
                    <div style="font-size:14px;color:{price_color};margin-top:2px">
                        {price_arrow} {abs(p['change']):.2f} ({abs(p['change_pct']):.2f}%)</div>
                </div>
                <div style="text-align:right">
                    <div style="font-size:14px;color:{TEXT_SECONDARY}">市值</div>
                    <div style="font-size:16px;font-weight:600;color:{TEXT_PRIMARY}">{format_number(p['market_cap'])}</div>
                </div>
            </div>
            <div style="display:flex;gap:16px;margin-top:10px;font-size:12px;color:{TEXT_SECONDARY}">
                <span>52周高: <b>{p['fifty_two_week_high']:.2f if p['fifty_two_week_high'] else 'N/A'}</b></span>
                <span>52周低: <b>{p['fifty_two_week_low']:.2f if p['fifty_two_week_low'] else 'N/A'}</b></span>
                <span>50日均: <b>{p['fifty_day_avg']:.2f if p['fifty_day_avg'] else 'N/A'}</b></span>
                <span>200日均: <b>{p['two_hundred_day_avg']:.2f if p['two_hundred_day_avg'] else 'N/A'}</b></span>
            </div>
        </div>""", unsafe_allow_html=True)

        # ── 股价走势图 ──
        if d.get("price_history"):
            hist_df = pd.DataFrame(list(d["price_history"].items()), columns=["date", "close"])
            hist_df["date"] = pd.to_datetime(hist_df["date"])
            st.line_chart(hist_df.set_index("date"), height=180, use_container_width=True)

        # ── 估值指标 + 关键比率 ──
        v = d["valuation"]
        r = d["ratios"]
        st.markdown("<div style='display:flex;gap:8px;flex-wrap:wrap'>", unsafe_allow_html=True)
        metrics = [
            ("PE", f"{v['pe_ratio']:.1f}" if v['pe_ratio'] else "N/A"),
            ("Forward PE", f"{v['forward_pe']:.1f}" if v['forward_pe'] else "N/A"),
            ("PB", f"{v['pb_ratio']:.2f}" if v['pb_ratio'] else "N/A"),
            ("PS", f"{v['ps_ratio']:.2f}" if v['ps_ratio'] else "N/A"),
            ("EV/EBITDA", f"{v['ev_ebitda']:.1f}" if v['ev_ebitda'] else "N/A"),
            ("股息率", format_pct(v['dividend_yield'])),
            ("ROE", format_pct(r['roe'])),
            ("ROA", format_pct(r['roa'])),
            ("毛利率", format_pct(r['gross_margins'])),
            ("营业利润率", format_pct(r['operating_margins'])),
            ("净利率", format_pct(r['profit_margins'])),
            ("负债/权益", f"{r['debt_to_equity']:.1f}" if r['debt_to_equity'] else "N/A"),
            ("流动比率", f"{r['current_ratio']:.2f}" if r['current_ratio'] else "N/A"),
        ]
        for label, value in metrics:
            st.markdown(f"""<div class="fin-card" style="flex:1;min-width:100px;max-width:140px">
                <div class="fin-metric">
                    <div class="fin-metric-value">{value}</div>
                    <div class="fin-metric-label">{label}</div>
                </div></div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 财务数据表（过去3年）──
        fin = d.get("financials")
        if fin and fin["years"]:
            years = fin["years"][:3]  # 最近3年
            st.markdown("#### 📋 财务数据（年度）")

            # 营收行
            rows = []
            # 营收
            rev_row = ["营收"] + [format_number(fin["revenue"].get(y, None)) for y in years]
            rows.append(rev_row)
            # 净利润
            ni_row = ["净利润"] + [format_number(fin["net_income"].get(y, None)) for y in years]
            rows.append(ni_row)
            # EPS
            eps_row = ["EPS"] + [f"{fin['eps'].get(y, 0):.2f}" if fin["eps"].get(y) else "N/A" for y in years]
            rows.append(eps_row)
            # 毛利率
            gm_row = ["毛利率"] + [f"{fin['gross_margin'].get(y, 0):.1f}%" if fin["gross_margin"].get(y) is not None else "N/A" for y in years]
            rows.append(gm_row)
            # 净利率
            nm_row = ["净利率"] + [f"{fin['net_margin'].get(y, 0):.1f}%" if fin["net_margin"].get(y) is not None else "N/A" for y in years]
            rows.append(nm_row)

            header = ["指标"] + years
            header_html = "".join(f"<th>{h}</th>" for h in header)
            body_html = ""
            for row in rows:
                body_html += "<tr>"
                for i, cell in enumerate(row):
                    body_html += f"<td>{cell}</td>"
                body_html += "</tr>"

            st.markdown(f"""
            <div class="fin-card" style="overflow-x:auto">
                <table class="fin-table">
                    <thead><tr>{header_html}</tr></thead>
                    <tbody>{body_html}</tbody>
                </table>
            </div>""", unsafe_allow_html=True)

        # ── 分析师预期 ──
        est = d.get("estimates")
        if est:
            st.markdown("#### 🎯 分析师预期")
            tp = est.get("target_price", {})
            an = est.get("analysts", {})
            gr = est.get("growth", {})

            upside = tp.get("upside_pct")
            upside_color = ACCENT_GREEN if upside and upside > 0 else (ACCENT_RED if upside and upside < 0 else TEXT_SECONDARY)
            upside_text = f"{'▲' if upside and upside > 0 else '▼' if upside and upside < 0 else ''} {abs(upside):.1f}%" if upside is not None else "N/A"

            st.markdown(f"""
            <div class="fin-card">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div style="font-size:12px;color:{TEXT_SECONDARY}">目标价（均值）</div>
                        <div style="font-size:22px;font-weight:700;color:{TEXT_PRIMARY}">
                            {tp['mean']:.2f if tp.get('mean') else 'N/A'} <span style="font-size:12px">{d['currency']}</span></div>
                    </div>
                    <div style="text-align:center">
                        <div style="font-size:12px;color:{TEXT_SECONDARY}">上涨空间</div>
                        <div style="font-size:18px;font-weight:700;color:{upside_color}">{upside_text}</div>
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:12px;color:{TEXT_SECONDARY}">评级</div>
                        <div style="font-size:14px;font-weight:600">{an.get('recommendation', 'N/A')}</div>
                        <div style="font-size:11px;color:{TEXT_SECONDARY}">{an.get('count', 0)} 位分析师</div>
                    </div>
                </div>
                <div style="display:flex;gap:16px;margin-top:8px;font-size:12px;color:{TEXT_SECONDARY}">
                    <span>目标价区间: {tp.get('low', 0):.2f} – {tp.get('high', 0):.2f}</span>
                </div>
            </div>""", unsafe_allow_html=True)

            # 增长数据
            growth_items = []
            if gr.get("revenue_growth") is not None:
                val = gr["revenue_growth"] * 100
                cls = "positive" if val >= 0 else "negative"
                growth_items.append(f'<span class="{cls}">营收增长: {val:.1f}%</span>')
            if gr.get("earnings_growth") is not None:
                val = gr["earnings_growth"] * 100
                cls = "positive" if val >= 0 else "negative"
                growth_items.append(f'<span class="{cls}">盈利增长: {val:.1f}%</span>')
            if est.get("forward_eps") is not None:
                growth_items.append(f'<span>Forward EPS: {est["forward_eps"]:.2f}</span>')

            if growth_items:
                st.markdown(f"""
                <div class="fin-card">
                    <div style="display:flex;gap:20px;font-size:14px">
                        {" &nbsp;|&nbsp; ".join(growth_items)}
                    </div>
                </div>""", unsafe_allow_html=True)

    elif not stock_input.strip():
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#94a3b8">
            <div style="font-size:40px;margin-bottom:12px">📊</div>
            <div style="font-size:14px">输入公司名称或股票代码<br/>查看股价、财务数据与分析师预期</div>
        </div>""", unsafe_allow_html=True)

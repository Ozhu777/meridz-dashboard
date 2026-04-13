"""
全球宏观新闻 Dashboard
- 多源新闻采集（Finnhub、华尔街见闻、东方财富、Reuters/BBC/CNBC）
- 定制化重要性评分 + 实时事件加分
- 英文新闻自动中文翻译
- 公司分析模块（股价 + 财务 + 预期）
- 中文界面，问卷可实时调整
- 飞书/微信推送
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

import config
from news_sources import fetch_all_news, format_time
from scorer import score_news
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

# 非常重要门槛
CRITICAL_THRESHOLD = 35

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
        background: {BG_CARD}; border-radius: 10px; padding: 12px 16px;
        margin-bottom: 6px; border-left: 3px solid {BORDER};
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    .news-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .news-card.critical {{ border-left-color: {ACCENT_RED}; }}
    .news-card.normal {{ border-left-color: {BORDER}; }}
    .news-title {{
        font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};
        line-height: 1.4; margin-bottom: 2px;
    }}
    .news-translation {{
        font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.4;
        margin: 2px 0 4px; padding: 4px 8px;
        background: #f1f5f9; border-radius: 4px;
    }}
    .news-meta {{
        font-size: 11px; color: #94a3b8;
        display: flex; gap: 6px; align-items: center;
    }}
    .news-link {{ font-size: 11px; color: {PRIMARY}; text-decoration: none; }}
    .news-link:hover {{ text-decoration: underline; }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    .stDeployButton {{ visibility: hidden; }}
    .fin-card {{
        background: {BG_CARD}; border-radius: 10px; padding: 14px 16px;
        border: 1px solid {BORDER}; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        margin-bottom: 8px;
    }}
    .fin-table {{
        width: 100%; border-collapse: collapse; font-size: 13px;
    }}
    .fin-table th {{
        background: #f1f5f9; padding: 7px 10px; text-align: right;
        font-weight: 600; color: {TEXT_PRIMARY}; border-bottom: 2px solid {BORDER};
    }}
    .fin-table th:first-child {{ text-align: left; }}
    .fin-table td {{
        padding: 7px 10px; text-align: right; border-bottom: 1px solid {BORDER};
        color: {TEXT_PRIMARY};
    }}
    .fin-table td:first-child {{ text-align: left; font-weight: 500; }}
    .positive {{ color: {ACCENT_GREEN}; }}
    .negative {{ color: {ACCENT_RED}; }}
</style>
""", unsafe_allow_html=True)


# ─── 新闻采集函数 ─────────────────────────────────────────
def _fetch_and_score(finnhub_key):
    news = fetch_all_news(finnhub_key)
    for item in news:
        scoring = score_news(item, st.session_state.config)
        item["score"] = scoring["score"]
        item["score_details"] = scoring
        item["time_str"] = format_time(item.get("timestamp", ""))
        tr = translate_news_item(item)
        item["title_zh"] = tr["title_zh"] if tr else ""
        item["summary_zh"] = tr["summary_zh"] if tr else ""
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
# SIDEBAR（折叠式）
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    if st.button("⚙️ 筛选设置" if not st.session_state.show_settings else "✕ 关闭设置",
                 use_container_width=True):
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
# AUTO-FETCH
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
    if st.button("🔄", use_container_width=True, type="primary"):
        with st.spinner("采集新闻中..."):
            st.session_state.news_data = _fetch_and_score(st.session_state.finnhub_key)
            st.session_state.last_fetch = now_str

with col_title:
    st.markdown("<h2 style='margin:0'>🌐 全球宏观新闻 & 公司分析</h2>", unsafe_allow_html=True)

with col_time:
    if st.session_state.last_fetch:
        critical_count = len([n for n in st.session_state.news_data if n.get("score", 0) >= CRITICAL_THRESHOLD])
        st.markdown(
            f"<p style='text-align:right;color:#94a3b8;font-size:12px;margin:8px 0'>"
            f"{st.session_state.last_fetch} · "
            f"共 {len(st.session_state.news_data)} 条 · "
            f"<span style='color:{ACCENT_RED}'>{critical_count} 条重要</span></p>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════
# FILTER BUTTONS（只有两个）
# ═══════════════════════════════════════════════════════════
all_data = st.session_state.news_data
all_data = [n for n in all_data if n.get("score", 0) >= st.session_state.config["filter"]["min_importance"]]

critical_news = [n for n in all_data if n.get("score", 0) >= CRITICAL_THRESHOLD]

fb1, fb2 = st.columns([1, 1])
with fb1:
    active_all = st.session_state.filter_mode == "all"
    if st.button(
        f"📰 全部 ({len(all_data)})" if not active_all else f"📰 全部 ({len(all_data)}) ✓",
        use_container_width=True,
        type="primary" if active_all else "secondary",
        key="f_all",
    ):
        st.session_state.filter_mode = "all"
        st.rerun()

with fb2:
    if st.button(
        f"🔴 非常重要 ({len(critical_news)})" if st.session_state.filter_mode != "critical"
        else f"🔴 非常重要 ({len(critical_news)}) ✓",
        use_container_width=True,
        type="primary" if st.session_state.filter_mode == "critical" else "secondary",
        key="f_critical",
    ):
        st.session_state.filter_mode = "critical"
        st.rerun()

display_news = critical_news if st.session_state.filter_mode == "critical" else all_data


# ═══════════════════════════════════════════════════════════
# MAIN: 左新闻 + 右公司分析
# ═══════════════════════════════════════════════════════════
news_col, stock_col = st.columns([3, 2])

# ─── 左侧：新闻流（精简）────────────────────────────────
with news_col:
    if display_news:
        for n in display_news:
            score = n.get("score", 0)
            is_critical = score >= CRITICAL_THRESHOLD
            card_cls = "critical" if is_critical else "normal"
            title = n.get("title", "")
            title_zh = n.get("title_zh", "")
            source = n.get("source", "")
            time_str = n.get("time_str", "")
            url = n.get("url", "")

            translation_html = f'<div class="news-translation">💬 {title_zh}</div>' if title_zh else ""
            link_html = f'<a href="{url}" target="_blank" class="news-link">🔗 原文</a>' if url else ""
            importance = '<span style="color:#dc2626;font-size:11px;font-weight:700">⚡ 重要</span>' if is_critical else ""

            st.markdown(f'''
            <div class="news-card {card_cls}">
                <div class="news-title">{title} {importance}</div>
                {translation_html}
                <div class="news-meta">
                    <span>{time_str}</span>
                    <span>· {source}</span>
                    {f'<span style="margin-left:auto">{link_html}</span>' if link_html else ''}
                </div>
            </div>''', unsafe_allow_html=True)
    else:
        st.info("📭 暂无新闻")


# ─── 右侧：公司分析 ─────────────────────────────────────
with stock_col:
    st.markdown("### 📊 公司分析")
    st.caption("输入公司名称或股票代码")

    stock_input = st.text_input("", placeholder="如 Apple、NVDA、000001.SZ", key="stock_input", label_visibility="collapsed")

    col_search, col_clear = st.columns([1, 1])
    with col_search:
        if st.button("🔍 查询", use_container_width=True, type="primary"):
            if stock_input.strip():
                with st.spinner(f"查询中..."):
                    data = get_stock_data(stock_input.strip())
                if data:
                    st.session_state.stock_data = data
                else:
                    st.error(f"未找到「{stock_input.strip()}」的数据，试试英文代码如 AAPL、NVDA")
            else:
                st.warning("请输入公司名称或股票代码")
    with col_clear:
        if st.button("✕ 清除", use_container_width=True):
            st.session_state.stock_data = None
            st.rerun()

    # ── 展示公司数据 ──
    if st.session_state.stock_data:
        d = st.session_state.stock_data
        st.markdown("---")
        st.markdown(f"**{d['name']}** ({d['symbol']})  ·  {d['sector']}")

        p = d["price"]
        price_color = ACCENT_GREEN if p["change"] >= 0 else ACCENT_RED
        arrow = "▲" if p["change"] >= 0 else "▼"
        st.markdown(f"""
        <div class="fin-card">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <span style="font-size:26px;font-weight:700">{p['current']:.2f}</span>
                    <span style="font-size:12px;color:#94a3b8"> {d['currency']}</span>
                    <span style="font-size:14px;color:{price_color};margin-left:8px">
                        {arrow} {abs(p['change']):.2f} ({abs(p['change_pct']):.2f}%)</span>
                </div>
                <div style="text-align:right">
                    <div style="font-size:11px;color:#94a3b8">市值</div>
                    <div style="font-size:15px;font-weight:600">{format_number(p['market_cap'])}</div>
                </div>
            </div>
            <div style="font-size:11px;color:#94a3b8;margin-top:6px">
                52w: {p['fifty_two_week_low']:.2f} – {p['fifty_two_week_high']:.2f}
                &nbsp;|&nbsp; 50d: {p['fifty_day_avg']:.2f if p['fifty_day_avg'] else 'N/A'}
                &nbsp;|&nbsp; 200d: {p['two_hundred_day_avg']:.2f if p['two_hundred_day_avg'] else 'N/A'}
            </div>
        </div>""", unsafe_allow_html=True)

        # 走势图
        if d.get("price_history"):
            hist_df = pd.DataFrame(list(d["price_history"].items()), columns=["date", "close"])
            hist_df["date"] = pd.to_datetime(hist_df["date"])
            st.line_chart(hist_df.set_index("date"), height=150, use_container_width=True)

        # 估值 + 比率
        v = d["valuation"]
        r = d["ratios"]
        st.markdown("<div style='display:flex;gap:6px;flex-wrap:wrap'>", unsafe_allow_html=True)
        for label, value in [
            ("PE", f"{v['pe_ratio']:.1f}" if v['pe_ratio'] else "N/A"),
            ("Fwd PE", f"{v['forward_pe']:.1f}" if v['forward_pe'] else "N/A"),
            ("PB", f"{v['pb_ratio']:.2f}" if v['pb_ratio'] else "N/A"),
            ("PS", f"{v['ps_ratio']:.2f}" if v['ps_ratio'] else "N/A"),
            ("EV/EBITDA", f"{v['ev_ebitda']:.1f}" if v['ev_ebitda'] else "N/A"),
            ("股息率", format_pct(v['dividend_yield'])),
            ("ROE", format_pct(r['roe'])),
            ("毛利率", format_pct(r['gross_margins'])),
            ("净利率", format_pct(r['profit_margins'])),
            ("D/E", f"{r['debt_to_equity']:.1f}" if r['debt_to_equity'] else "N/A"),
        ]:
            st.markdown(f"""<div class="fin-card" style="flex:1;min-width:80px;max-width:120px;padding:8px 10px">
                <div style="font-size:14px;font-weight:700;text-align:center">{value}</div>
                <div style="font-size:10px;color:#94a3b8;text-align:center">{label}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # 财务数据表
        fin = d.get("financials")
        if fin and fin["years"]:
            years = fin["years"][:3]
            rows = [
                ["营收"] + [format_number(fin["revenue"].get(y)) for y in years],
                ["净利润"] + [format_number(fin["net_income"].get(y)) for y in years],
                ["EPS"] + [f"{fin['eps'].get(y, 0):.2f}" if fin["eps"].get(y) else "N/A" for y in years],
                ["毛利率"] + [f"{fin['gross_margin'].get(y, 0):.1f}%" if fin["gross_margin"].get(y) is not None else "N/A" for y in years],
                ["净利率"] + [f"{fin['net_margin'].get(y, 0):.1f}%" if fin["net_margin"].get(y) is not None else "N/A" for y in years],
            ]
            th = "".join(f"<th>{h}</th>" for h in ["指标"] + years)
            tb = ""
            for row in rows:
                tb += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            st.markdown(f"""<div class="fin-card" style="overflow-x:auto">
                <table class="fin-table"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>""", unsafe_allow_html=True)

        # 分析师预期
        est = d.get("estimates")
        if est:
            tp = est.get("target_price", {})
            an = est.get("analysts", {})
            gr = est.get("growth", {})
            upside = tp.get("upside_pct")
            uc = ACCENT_GREEN if upside and upside > 0 else (ACCENT_RED if upside and upside < 0 else TEXT_SECONDARY)
            ut = f"{'▲' if upside and upside > 0 else '▼' if upside and upside < 0 else ''} {abs(upside):.1f}%" if upside is not None else "N/A"

            st.markdown(f"""
            <div class="fin-card">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <div style="font-size:11px;color:#94a3b8">目标价</div>
                        <div style="font-size:20px;font-weight:700">{tp['mean']:.2f if tp.get('mean') else 'N/A'} {d['currency']}</div>
                    </div>
                    <div style="text-align:center">
                        <div style="font-size:11px;color:#94a3b8">上涨空间</div>
                        <div style="font-size:16px;font-weight:700;color:{uc}">{ut}</div>
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:13px;font-weight:600">{an.get('recommendation', 'N/A')}</div>
                        <div style="font-size:11px;color:#94a3b8">{an.get('count', 0)} 位分析师</div>
                    </div>
                </div>
                <div style="font-size:11px;color:#94a3b8;margin-top:6px">
                    区间: {tp.get('low', 0):.2f} – {tp.get('high', 0):.2f}
                </div>
            </div>""", unsafe_allow_html=True)

            growth_parts = []
            if gr.get("revenue_growth") is not None:
                val = gr["revenue_growth"] * 100
                cls = "positive" if val >= 0 else "negative"
                growth_parts.append(f'<span class="{cls}">营收增长 {val:.1f}%</span>')
            if gr.get("earnings_growth") is not None:
                val = gr["earnings_growth"] * 100
                cls = "positive" if val >= 0 else "negative"
                growth_parts.append(f'<span class="{cls}">盈利增长 {val:.1f}%</span>')
            if est.get("forward_eps"):
                growth_parts.append(f"<span>Forward EPS {est['forward_eps']:.2f}</span>")
            if growth_parts:
                st.markdown(f"""<div class="fin-card" style="font-size:13px">
                    {" &nbsp;·&nbsp; ".join(growth_parts)}</div>""", unsafe_allow_html=True)

    elif not stock_input.strip():
        st.markdown("""
        <div style="text-align:center;padding:40px 20px;color:#94a3b8">
            <div style="font-size:36px;margin-bottom:8px">📊</div>
            <div style="font-size:13px">输入公司名称或股票代码<br/>查看股价、财务数据与分析师预期</div>
        </div>""", unsafe_allow_html=True)

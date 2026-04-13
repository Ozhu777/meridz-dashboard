"""
公司分析模块 — 获取并格式化公司财务数据
数据源：yfinance (Yahoo Finance)
"""

from __future__ import annotations
import yfinance as yf
from datetime import datetime, timedelta


def search_ticker(query: str) -> Optional[dict]:
    """根据公司名称或代码搜索，返回第一个匹配的 ticker 信息"""
    if not query or not query.strip():
        return None
    query = query.strip()

    # 先尝试直接作为 ticker
    ticker = yf.Ticker(query)
    info = ticker.info
    if info and info.get("regularMarketPrice") is not None:
        return info

    # 尝试作为公司名搜索（yfinance 没有直接搜索，用 .search）
    try:
        results = yf.Search(query, max_results=3, news_count=0)
        quotes = getattr(results, "quotes", [])
        if quotes and len(quotes) > 0:
            best = quotes[0]
            symbol = best.get("symbol", "")
            if symbol:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                if info:
                    info["_matched_symbol"] = symbol
                    return info
    except Exception:
        pass

    return None


def get_stock_data(query: str) -> Optional[dict]:
    """获取完整的公司分析数据，返回结构化字典"""
    info = search_ticker(query)
    if not info:
        return None

    symbol = info.get("_matched_symbol", "") or info.get("symbol", query)
    ticker = yf.Ticker(symbol)

    result = {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName", symbol),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "currency": info.get("currency", "USD"),
    }

    # ─── 股价概览 ───
    current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose", 0)
    price_change = current_price - prev_close if current_price and prev_close else 0
    price_change_pct = (price_change / prev_close * 100) if prev_close else 0

    result["price"] = {
        "current": current_price,
        "change": price_change,
        "change_pct": price_change_pct,
        "market_cap": info.get("marketCap"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_day_avg": info.get("fiftyDayAverage"),
        "two_hundred_day_avg": info.get("twoHundredDayAverage"),
        "avg_volume": info.get("averageVolume"),
    }

    # ─── 估值指标 ───
    result["valuation"] = {
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "ps_ratio": info.get("priceToSalesTrailing12Months"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "dividend_yield": info.get("dividendYield"),
    }

    # ─── 关键比率 ───
    result["ratios"] = {
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "free_cashflow": info.get("freeCashflow"),
        "operating_cashflow": info.get("operatingCashflow"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "profit_margins": info.get("profitMargins"),
    }

    # ─── 过去3年 + 未来预期财务数据 ───
    try:
        # 财务数据
        income_stmt = ticker.income_stmt
        if income_stmt is not None and not income_stmt.empty:
            result["financials"] = _extract_financials(income_stmt, "annual")
        else:
            result["financials"] = None
    except Exception:
        result["financials"] = None

    # 分析师预期
    try:
        result["estimates"] = _get_analyst_estimates(info)
    except Exception:
        result["estimates"] = None

    # ─── 股价历史（用于走势图）───
    try:
        hist = ticker.history(period="1y")
        if hist is not None and not hist.empty:
            result["price_history"] = hist["Close"].to_dict()
        else:
            result["price_history"] = None
    except Exception:
        result["price_history"] = None

    return result


def _extract_financials(income_stmt, period="annual"):
    """从 income_stmt 提取过去3年的关键数据"""
    years = []
    revenue = {}
    net_income = {}
    eps = {}
    gross_profit = {}

    for col in income_stmt.columns[:4]:  # 最近4个年度
        year = str(col.year) if hasattr(col, "year") else str(col)[:4]
        years.append(year)
        revenue[year] = income_stmt.loc["Total Revenue", col] if "Total Revenue" in income_stmt.index else None
        net_income[year] = income_stmt.loc["Net Income", col] if "Net Income" in income_stmt.index else None
        eps[year] = income_stmt.loc["Basic EPS", col] if "Basic EPS" in income_stmt.index else (
            income_stmt.loc["Diluted EPS", col] if "Diluted EPS" in income_stmt.index else None
        )
        gross_profit[year] = income_stmt.loc["Gross Profit", col] if "Gross Profit" in income_stmt.index else None

    # 计算毛利率和净利率
    gross_margin = {}
    net_margin = {}
    for y in years:
        if revenue.get(y) and revenue[y] != 0:
            gp = gross_profit.get(y)
            ni = net_income.get(y)
            gross_margin[y] = (gp / revenue[y] * 100) if gp else None
            net_margin[y] = (ni / revenue[y] * 100) if ni else None
        else:
            gross_margin[y] = None
            net_margin[y] = None

    return {
        "years": years,
        "revenue": revenue,
        "net_income": net_income,
        "eps": eps,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
    }


def _get_analyst_estimates(info: dict) -> Optional[dict]:
    """获取分析师预期数据"""
    estimates = {}

    # 分析师目标价
    target_mean = info.get("targetMeanPrice")
    target_high = info.get("targetHighPrice")
    target_low = info.get("targetLowPrice")
    current = info.get("currentPrice") or info.get("regularMarketPrice")

    estimates["target_price"] = {
        "mean": target_mean,
        "high": target_high,
        "low": target_low,
        "current": current,
        "upside_pct": ((target_mean / current) - 1) * 100 if current and target_mean else None,
    }

    # 分析师数量和评级
    estimates["analysts"] = {
        "count": info.get("numberOfAnalystOpinions"),
        "recommendation": _map_recommendation(info.get("recommendationKey")),
    }

    # 未来预期 EPS 和营收（从 info 字段获取）
    # yfinance 提供 nextYear 和 nextQuarter 的估计
    rev_growth = info.get("revenueGrowth")
    earnings_growth = info.get("earningsGrowth")
    earnings_growth_next = info.get("earningsQuarterlyGrowth")

    estimates["growth"] = {
        "revenue_growth": rev_growth,
        "earnings_growth": earnings_growth,
        "earnings_growth_next_q": earnings_growth_next,
    }

    # 未来几年 EPS 预期
    forward_eps = info.get("forwardEps")
    estimates["forward_eps"] = forward_eps

    return estimates


def _map_recommendation(key: str | None) -> str:
    if not key:
        return "N/A"
    mapping = {
        "strong_buy": "🟢 强烈买入",
        "buy": "🟢 买入",
        "hold": "🟡 持有",
        "sell": "🔴 卖出",
        "strong_sell": "🔴 强烈卖出",
    }
    return mapping.get(key, key)


def format_number(value, suffix="", decimals=1):
    """格式化大数字（亿/万）"""
    if value is None:
        return "N/A"
    try:
        v = float(value)
        abs_v = abs(v)
        sign = "-" if v < 0 else ""
        if abs_v >= 1e12:
            return f"{sign}{abs_v/1e12:.{decimals}f}T{suffix}"
        elif abs_v >= 1e9:
            return f"{sign}{abs_v/1e9:.{decimals}f}B{suffix}"
        elif abs_v >= 1e6:
            return f"{sign}{abs_v/1e6:.{decimals}f}M{suffix}"
        else:
            return f"{sign}{v:,.{decimals}f}{suffix}"
    except (ValueError, TypeError):
        return "N/A"


def format_pct(value):
    """格式化百分比"""
    if value is None:
        return "N/A"
    try:
        return f"{float(value)*100:.1f}%"
    except (ValueError, TypeError):
        return "N/A"

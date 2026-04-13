"""
公司分析模块 — 获取并格式化公司财务数据
数据源：yfinance (Yahoo Finance)
"""

from __future__ import annotations
from typing import Optional
import yfinance as yf
from datetime import datetime, timedelta


def search_ticker(query: str) -> Optional[dict]:
    """根据公司名称或代码搜索，返回第一个匹配的 ticker info"""
    if not query or not query.strip():
        return None
    query = query.strip()

    # 先尝试直接作为 ticker（不转大写）
    ticker = yf.Ticker(query)
    try:
        info = ticker.info
        if info and (info.get("regularMarketPrice") is not None or info.get("currentPrice") is not None):
            return info
    except Exception:
        pass

    # 尝试搜索公司名
    try:
        results = yf.Search(query, max_results=5, news_count=0)
        quotes = getattr(results, "quotes", [])
        if quotes:
            for q in quotes:
                symbol = q.get("symbol", "")
                if not symbol:
                    continue
                try:
                    t = yf.Ticker(symbol)
                    info = t.info
                    if info and (info.get("regularMarketPrice") is not None or info.get("currentPrice") is not None):
                        info["_matched_symbol"] = symbol
                        return info
                except Exception:
                    continue
    except Exception:
        pass

    return None


def get_stock_data(query: str) -> Optional[dict]:
    """获取完整的公司分析数据"""
    info = search_ticker(query)
    if not info:
        return None

    symbol = info.pop("_matched_symbol", "") or info.get("symbol", query)
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

    # ─── 财务数据 ───
    try:
        income_stmt = ticker.income_stmt
        if income_stmt is not None and not income_stmt.empty:
            result["financials"] = _extract_financials(income_stmt)
        else:
            result["financials"] = None
    except Exception:
        result["financials"] = None

    # ─── 分析师预期 ───
    try:
        result["estimates"] = _get_analyst_estimates(info)
    except Exception:
        result["estimates"] = None

    # ─── 股价历史 ───
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
    years = []
    revenue = {}
    net_income = {}
    eps = {}
    gross_profit = {}

    for col in income_stmt.columns[:4]:
        year = str(col.year) if hasattr(col, "year") else str(col)[:4]
        years.append(year)
        revenue[year] = income_stmt.loc["Total Revenue", col] if "Total Revenue" in income_stmt.index else None
        net_income[year] = income_stmt.loc["Net Income", col] if "Net Income" in income_stmt.index else None
        eps[year] = income_stmt.loc["Basic EPS", col] if "Basic EPS" in income_stmt.index else (
            income_stmt.loc["Diluted EPS", col] if "Diluted EPS" in income_stmt.index else None
        )
        gross_profit[year] = income_stmt.loc["Gross Profit", col] if "Gross Profit" in income_stmt.index else None

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


def _get_analyst_estimates(info):
    estimates = {}
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
    estimates["analysts"] = {
        "count": info.get("numberOfAnalystOpinions"),
        "recommendation": _map_recommendation(info.get("recommendationKey")),
    }
    estimates["growth"] = {
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
    }
    estimates["forward_eps"] = info.get("forwardEps")
    return estimates


def _map_recommendation(key):
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
    if value is None:
        return "N/A"
    try:
        return f"{float(value)*100:.1f}%"
    except (ValueError, TypeError):
        return "N/A"

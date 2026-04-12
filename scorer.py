"""
重要性评分引擎
基于用户问卷配置对每条新闻打分（0-100）
"""

import re


def score_news(news_item, config):
    """
    对单条新闻计算重要性分数 (0-100)

    评分逻辑：
    1. 将新闻标题+摘要拼接为文本
    2. 在每个维度中匹配关键词
    3. 匹配到的项取其权重
    4. 各维度分数加权汇总，归一化到 0-100
    5. 加上实时事件加分（event_boost）
    """
    text = f"{news_item.get('title', '')} {news_item.get('summary', '')} {news_item.get('tags', '')}".lower()
    text_cn = text

    # 英文关键词匹配需要 case-insensitive
    geo_score = _score_dimension(text, text_cn, config.get("geography", []))
    event_score = _score_dimension(text, text_cn, config.get("events", []))
    asset_score = _score_dimension(text, text_cn, config.get("assets", []))

    # 加权汇总
    # 地理 25%, 事件 40%, 资产 20%, 实时事件 15%
    raw_score = geo_score * 0.25 + event_score * 0.40 + asset_score * 0.20

    # 实时事件加分（0-10，直接加到原始分）
    event_boost = news_item.get("event_boost", 0) or 0
    raw_score += event_boost * 0.15  # 占 15%

    # 归一化到 0-100
    max_possible = _max_possible_score(config)
    if max_possible > 0:
        normalized = min(100, (raw_score / max_possible) * 100)
    else:
        normalized = 0

    # 匹配详情（用于 UI 展示）
    matched_categories = _get_matched_categories(text, text_cn, config)

    return {
        "score": round(normalized, 1),
        "geo_score": round(geo_score, 1),
        "event_score": round(event_score, 1),
        "asset_score": round(asset_score, 1),
        "matched": matched_categories,
        "event_boost": event_boost,
    }


def _score_dimension(text_en, text_cn, dimension_items):
    """对单个维度（地理/事件/资产）计算分数"""
    total = 0
    for item in dimension_items:
        if not item.get("enabled", False):
            continue
        keywords = item.get("keywords", [])
        weight = item.get("weight", 0)
        if weight <= 0:
            continue
        # 检查是否有任何关键词匹配
        for kw in keywords:
            if kw.lower() in text_en or kw in text_cn:
                total += weight
                break  # 一个类别只算一次权重
    return total


def _get_matched_categories(text_en, text_cn, config):
    """获取匹配到的所有类别名称"""
    matched = {"地理": [], "事件": [], "资产": []}
    for item in config.get("geography", []):
        if item.get("enabled", False) and _any_match(item.get("keywords", []), text_en, text_cn):
            matched["地理"].append(item["name"])
    for item in config.get("events", []):
        if item.get("enabled", False) and _any_match(item.get("keywords", []), text_en, text_cn):
            matched["事件"].append(item["name"])
    for item in config.get("assets", []):
        if item.get("enabled", False) and _any_match(item.get("keywords", []), text_en, text_cn):
            matched["资产"].append(item["name"])
    return matched


def _any_match(keywords, text_en, text_cn):
    for kw in keywords:
        if kw.lower() in text_en or kw in text_cn:
            return True
    return False


def _max_possible_score(config):
    """计算实际最大分数（取每个维度 top3 权重之和，加上实时事件加分）"""
    dims = [
        (config.get("geography", []), 0.25),
        (config.get("events", []), 0.40),
        (config.get("assets", []), 0.20),
    ]
    total = 0
    for items, weight_ratio in dims:
        enabled_weights = sorted(
            [item.get("weight", 0) for item in items if item.get("enabled", False) and item.get("weight", 0) > 0],
            reverse=True
        )
        # 取 top3 权重之和作为该维度实际最大值
        max_w = sum(enabled_weights[:3])
        total += max_w * weight_ratio
    # 加上实时事件加分最大值
    total += 10 * 0.15  # event_boost 最大 10
    return total if total > 0 else 1


def get_score_color(score):
    """根据分数返回颜色"""
    if score >= 75:
        return "🔴"  # 极高重要性
    elif score >= 50:
        return "🟠"  # 高重要性
    elif score >= 30:
        return "🟡"  # 中等
    else:
        return "⚪"  # 低


def get_score_label(score):
    """根据分数返回标签"""
    if score >= 75:
        return "极度重要"
    elif score >= 50:
        return "重要"
    elif score >= 30:
        return "一般"
    else:
        return "低"

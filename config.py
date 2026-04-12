# 宏观新闻 Dashboard - 配置文件说明
# 复制此文件为 config.json 后可自定义

import json
import os

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))


def get_config_path():
    return os.path.join(CONFIG_DIR, "config.json")


def get_default_config_path():
    return os.path.join(CONFIG_DIR, "config_default.json")


def load_config():
    """加载用户配置，如不存在则加载默认配置"""
    config_path = get_config_path()
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        with open(get_default_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)


def save_config(config):
    """保存用户配置"""
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def reset_config():
    """重置为默认配置"""
    import shutil
    shutil.copy(get_default_config_path(), get_config_path())


def get_all_keywords(config):
    """从配置中提取所有关键词，用于分类"""
    all_kw = {}
    for category in ["geography", "events", "assets"]:
        for item in config.get(category, []):
            if item.get("enabled", False):
                all_kw[item["name"]] = item["keywords"]
    return all_kw

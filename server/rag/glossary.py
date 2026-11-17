"""英文食材 → 中文检索词映射（A 档关键词检索的桥接词表）。

注意：这里只有「词面对应」，不含任何营养数值、健康结论或医学建议。
前端食材自动补全使用英文词，语料是中文，检索前用本表扩展查询即可命中。
新增食材时只需要补一个词条，不需要改检索算法。
"""
import re

INGREDIENT_TERMS = {
    "tomato": "蔬菜 番茄",
    "spinach": "蔬菜 深色蔬菜 菠菜",
    "broccoli": "蔬菜 深色蔬菜",
    "carrot": "蔬菜",
    "potato": "薯类 谷薯类",
    "cucumber": "蔬菜",
    "apple": "水果",
    "banana": "水果",
    "orange": "水果",
    "fruit": "水果",
    "vegetable": "蔬菜",
    "rice": "谷类 谷薯类",
    "oat": "全谷物 谷类",
    "bread": "谷类 全谷物",
    "wheat": "谷类 全谷物",
    "bean": "杂豆 豆类 大豆",
    "tofu": "大豆 豆类",
    "nut": "坚果",
    "egg": "蛋类 鸡蛋",
    "milk": "奶类 奶制品",
    "cheese": "奶制品 奶类",
    "yogurt": "奶制品 奶类",
    "fish": "鱼 鱼禽蛋",
    "salmon": "鱼 鱼禽蛋",
    "shrimp": "鱼禽蛋 水产",
    "chicken": "禽 畜禽肉 鱼禽蛋",
    "beef": "瘦肉 畜禽肉",
    "pork": "瘦肉 畜禽肉",
    "meat": "畜禽肉 瘦肉",
    "salt": "食盐 少盐",
    "sugar": "添加糖 控糖",
    "oil": "烹调油 少油",
    "butter": "烹调油 少油",
    "water": "饮水 白水",
    "calcium": "钙 奶制品",
    "vitamin": "维生素 微量营养素",
    "soda": "含糖饮料 添加糖",
    "juice": "水果 果汁",
    "infant": "婴幼儿 母乳 配方奶",
    "baby": "婴幼儿 母乳 配方奶",
    "label": "营养标签 预包装食品",
}


def expand_query(query):
    """在原始查询后追加命中的中文检索词，原始查询始终保留。"""
    text = (query or "").lower()
    extras = []
    for term, chinese_terms in INGREDIENT_TERMS.items():
        if re.search(r"\b" + re.escape(term) + r"\b", text):
            extras.append(chinese_terms)
    if not extras:
        return query or ""
    return (query or "") + " " + " ".join(extras)


SEARCH_NUTRITION_BASE = (
    "查询权威营养与膳食资料（中国居民膳食指南、国家卫健委等）。当用户问到具体营养数值、"
    "推荐摄入量、某种食物的健康作用、膳食指南建议或特殊人群饮食时调用。"
    "返回带 [编号] 的资料片段；回答中的营养数值与结论必须引用这些编号，查不到就说明暂无可靠依据。"
)


def tool_description():
    """拼出 search_nutrition 的工具描述：基础说明 + 从语料自动生成的关键词菜单。

    菜单告诉模型知识库实际用哪些词（如语料写「番茄」而非「西红柿」），
    让模型检索时把用户口语换成语料用词，弥补 BM25 不认识同义的短板。
    语料增减后菜单自动更新，无需手工维护词表。
    """
    from .corpus import keyword_menu  # 延迟导入，避免模块初始化顺序问题

    menu = keyword_menu()
    if not menu:
        return SEARCH_NUTRITION_BASE
    return (
        SEARCH_NUTRITION_BASE
        + " 检索时请优先使用知识库实际用词（用户说法与下面不同时，换成这里的说法再查），"
        + "并尽量给出 1-3 种不同说法，系统会融合各说法结果："
        + "、".join(menu) + "。"
    )

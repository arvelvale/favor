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

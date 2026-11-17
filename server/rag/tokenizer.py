"""中文分词：优先使用 jieba，未安装时回退到纯标准库的「单字 + 双字」切分。

回退方案对中文检索够用：查询「菠菜补铁」与语料「非血红素铁」可通过单字「铁」命中，
双字则让「菠菜」「补铁」这类词整体匹配，减少噪声。
"""
import re

try:
    import jieba as _jieba
except ImportError:
    _jieba = None

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_WORD = re.compile(r"[a-z0-9]+", re.I)

# 只过滤明显无检索意义的虚词/疑问词；数字、单位、否定词一律保留
_STOPWORDS = frozenset({
    "的", "了", "吗", "呢", "吧", "啊", "呀", "么", "是", "在", "和", "与",
    "及", "或", "把", "被", "给", "对", "从", "也", "就", "都", "而", "且",
    "请", "问", "我", "你", "他", "她", "它", "这", "那", "什么", "怎么",
    "如何", "多少", "一下", "一个", "一些", "可以", "需要", "应该", "关于",
    "请问", "帮我", "想", "要", "会", "能", "有", "个", "些", "中", "上",
    "下", "以", "为", "之", "其", "并", "但", "the", "a", "an", "of", "to",
    "is", "are", "for", "and", "with", "how", "what", "please",
})


def _fallback_tokens(text):
    tokens = []
    for run in _CJK_RUN.findall(text):
        tokens.extend(run)
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    tokens.extend(m.group(0).lower() for m in _ASCII_WORD.finditer(text))
    return tokens


def tokenize(text):
    """把文本切成检索用的词列表。"""
    text = (text or "").lower()
    if not text:
        return []
    if _jieba is not None:
        raw = _jieba.cut_for_search(text)
    else:
        raw = _fallback_tokens(text)
    return [t for t in raw if t and t.strip() and t not in _STOPWORDS]


def engine_name():
    return "jieba" if _jieba is not None else "builtin-unigram+bigram"

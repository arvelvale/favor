"""中文分词：固定使用纯标准库的「单字 + 双字」切分。

对中文检索够用：查询「菠菜补铁」与语料「非血红素铁」可通过单字「铁」命中，
双字则让「菠菜」「补铁」这类词整体匹配，减少噪声。

为什么不自动启用 jieba：BM25 分数的量级取决于分词方式（同一题内置分词约 14 分，
jieba 约 5 分），而拒答门槛 RAG_MIN_ABS_SCORE=10.0 是按内置分词评测出来的。
若「装了就用」，服务器上碰巧装了 jieba 就会让正常问题被判为无依据（Recall@4 100%→62%）。
要换分词器，必须同时用 python -m rag.evaluate 重新标定门槛，并改这里的实现。
"""
import re

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
    return [t for t in _fallback_tokens(text) if t and t.strip() and t not in _STOPWORDS]


def engine_name():
    return "builtin-unigram+bigram"

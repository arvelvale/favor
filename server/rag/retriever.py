"""A 档检索器：两阶段检索（BM25 召回 + 字段信号重排）。

阶段①：用纯 BM25 分数 + 绝对/相对门槛决定「有没有可靠依据」，这一步
       与安全判定完全等价，保证用药/无关问题仍会老实拒答。
阶段②：只对已过门槛的候选，按查询词命中「标题/小标题/标签」的程度重新
       排序，让最相关的资料排第一；只换顺序，不改命中集合。

检索完全在本地内存完成，不调用任何外部 API；语料规模在百篇以内时
启动时重建索引只需毫秒级，因此不落盘索引文件，避免索引与语料不同步。
"""
import logging

from . import settings
from .bm25 import BM25Index
from .corpus import load_chunks
from .glossary import expand_query
from .tokenizer import tokenize

logger = logging.getLogger(__name__)

_CHUNKS = None
_INDEX = None
_FIELD_TOKENS = None


def reload_corpus():
    """清空缓存，语料改动后调用即可生效。"""
    global _CHUNKS, _INDEX, _FIELD_TOKENS
    _CHUNKS = None
    _INDEX = None
    _FIELD_TOKENS = None


def load_corpus():
    global _CHUNKS
    if _CHUNKS is None:
        _CHUNKS = load_chunks()
    return _CHUNKS


def build_index():
    global _INDEX
    if _INDEX is None:
        chunks = load_corpus()
        _INDEX = BM25Index([tokenize(" ".join([c.text, c.title, c.heading] + list(c.tags)))
                            for c in chunks])
    return _INDEX


def field_tokens():
    """每个片段的 (标题词集, 小标题词集, 标签词集)，用于阶段②重排。"""
    global _FIELD_TOKENS
    if _FIELD_TOKENS is None:
        _FIELD_TOKENS = [
            (set(tokenize(c.title)), set(tokenize(c.heading)), set(tokenize(" ".join(c.tags))))
            for c in load_corpus()
        ]
    return _FIELD_TOKENS


def is_enabled():
    return bool(settings.RAG_ENABLED)


def search(query, top_k=None):
    """返回命中的片段列表（dict），已带 1 起始的 citation 编号；无命中返回 []。

    两阶段：① 纯 BM25 + 门槛判定有无依据（安全底线）；
            ② 仅在合格候选池内用标题/小标题/标签信号重排，只改顺序。
    """
    if not is_enabled():
        return []
    chunks = load_corpus()
    if not chunks or not (query or "").strip():
        return []

    query_tokens = tokenize(expand_query(query))
    scores = build_index().scores(query_tokens)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    best = scores[ranked[0]] if ranked else 0.0
    # 阶段①：绝对门槛——低于此值说明只是零散单字碰巧命中，视为无可引用依据。
    # 注意：这里必须用未经任何加分的原始 BM25 分数，否则无关问题会被顶过门槛。
    if best <= 0 or best < settings.RAG_MIN_ABS_SCORE:
        return []

    threshold = best * settings.RAG_MIN_REL_SCORE
    limit = top_k if top_k is not None else settings.RAG_TOP_K

    # 阶段①候选池：过相对门槛的片段（放宽到 limit×倍数，给重排留选择空间）。
    candidates = []
    for i in ranked:
        if scores[i] <= 0 or scores[i] < threshold:
            break
        candidates.append(i)
        if len(candidates) >= limit * settings.RAG_RERANK_POOL_MULT:
            break

    # 阶段②：用查询词与「标题/小标题/标签」的交集给候选加分并重排。
    # 只在候选内部改变顺序，不新增也不删除任何片段。
    query_set = set(query_tokens)
    fields = field_tokens()
    candidates.sort(
        key=lambda i: (
            scores[i]
            + len(query_set & fields[i][0]) * settings.RAG_TITLE_BOOST
            + len(query_set & fields[i][1]) * settings.RAG_HEADING_BOOST
            + len(query_set & fields[i][2]) * settings.RAG_TAG_BOOST,
            scores[i],
        ),
        reverse=True,
    )

    per_doc = {}
    hits = []
    for i in candidates:
        chunk = chunks[i]
        if per_doc.get(chunk.doc_id, 0) >= 2:
            continue
        per_doc[chunk.doc_id] = per_doc.get(chunk.doc_id, 0) + 1
        item = {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "title": chunk.title,
            "heading": chunk.heading,
            "text": chunk.text,
            "publisher": chunk.publisher,
            "published": chunk.published,
            "url": chunk.source_url,
            "evidence_level": chunk.evidence_level,
            "audience": chunk.audience,
            "score": round(float(scores[i]), 4),
            "citation": len(hits) + 1,
        }
        hits.append(item)
        if len(hits) >= limit:
            break
    return hits

"""A 档检索器：两阶段检索（BM25 召回 + 字段信号重排）。

阶段①：用纯 BM25 分数 + 绝对/相对门槛决定「有没有可靠依据」，这一步
       与安全判定完全等价，保证用药/无关问题仍会老实拒答。
阶段②：只对已过门槛的候选，按查询词命中「标题/小标题/标签」的程度重新
       排序，让最相关的资料排第一；只换顺序，不改命中集合。

检索完全在本地内存完成，不调用任何外部 API；语料规模在百篇以内时
启动时重建索引只需毫秒级，因此不落盘索引文件，避免索引与语料不同步。
"""
import logging
import math

from . import settings
from .bm25 import BM25Index
from .corpus import load_chunks
from .glossary import expand_query
from .tokenizer import STOPWORD_RESIDUAL_SINGLES, tokenize

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


def _rerank_query_terms(query_tokens):
    """阶段②专用的查询词集：去掉停用词残片单字，且单字词不再单独重复计。

    tokenizer 把中文切成「单字 + 相邻双字」，停用词（多少/需要/什么…）虽被
    整词过滤，但其组成单字（少/需/么…）会作为单字残留下来。这些残字会在
    「青少年」的「少」这类场景里制造假命中，把无关文档顶到重排前列。

    注意：只用于阶段②的字段交集计数。阶段①的 BM25 打分为保持拒答门槛
    （RAG_MIN_ABS_SCORE 按含残字的原分词标定）继续用完整 query_tokens，绝不动。
    """
    return {t for t in query_tokens
            if not (len(t) == 1 and t in STOPWORD_RESIDUAL_SINGLES)}


def _field_boost(query_set, fields_i):
    """阶段②字段命中加分：标题命中数开平方，抑制长标题堆词虚高。

    中文双字切分会让「每天/摄入/推荐」这类通用词在长标题上堆出很高命中数，
    把真正相关的短标题压下去（实测 Q03 烹调油被奶类文档顶掉）。开平方后
    「命中 9 个词」只当 3 个算，保留「命中标题词多更相关」的信号，又避免堆词霸榜。
    """
    title_hits = len(query_set & fields_i[0])
    return (math.sqrt(title_hits) * settings.RAG_TITLE_BOOST
            + len(query_set & fields_i[1]) * settings.RAG_HEADING_BOOST
            + len(query_set & fields_i[2]) * settings.RAG_TAG_BOOST)


def _chunk_item(chunk, score, citation):
    """把 Chunk 转成给模型/前端用的 dict。"""
    return {
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
        "score": round(float(score), 4),
        "citation": citation,
    }


def _cap_per_doc(indices, chunks, limit):
    """按给定顺序取片段，每篇最多 2 段，最多 limit 个，返回 (index, 原分数) 列表。"""
    picked = []
    per_doc = {}
    for i, score in indices:
        chunk = chunks[i]
        if per_doc.get(chunk.doc_id, 0) >= 2:
            continue
        per_doc[chunk.doc_id] = per_doc.get(chunk.doc_id, 0) + 1
        picked.append((i, score))
        if len(picked) >= limit:
            break
    return picked


def search(query, top_k=None):
    """返回命中的片段列表（dict），已带 1 起始的 citation 编号；无命中返回 []。

    两阶段：① 纯 BM25 + 门槛判定有无依据（安全底线）；
            ② 仅在合格候选池内用标题/小标题/标签信号重排，只改顺序。

    这是单说法路径，评测量产线与不需要多说法扩展的调用都走这里，行为保持不变。
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
    query_set = _rerank_query_terms(query_tokens)
    fields = field_tokens()
    candidates.sort(
        key=lambda i: (scores[i] + _field_boost(query_set, fields[i]), scores[i]),
        reverse=True,
    )

    picked = _cap_per_doc([(i, scores[i]) for i in candidates], chunks, limit)
    return [_chunk_item(chunks[i], score, n)
            for n, (i, score) in enumerate(picked, start=1)]


def _rank_for_fusion(query, chunks, limit):
    """为 RRF 融合准备一条说法的排名列表：[(chunk_index, raw_score), ...]。

    复用 search 的两阶段逻辑与同一条绝对门槛：不过门槛的说法直接返回空列表，
    不会给融合贡献任何候选，也不会拉低其他说法的判定。
    """
    if not (query or "").strip():
        return []
    query_tokens = tokenize(expand_query(query))
    scores = build_index().scores(query_tokens)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    best = scores[ranked[0]] if ranked else 0.0
    if best <= 0 or best < settings.RAG_MIN_ABS_SCORE:
        return []

    threshold = best * settings.RAG_MIN_REL_SCORE
    candidates = []
    for i in ranked:
        if scores[i] <= 0 or scores[i] < threshold:
            break
        candidates.append((i, scores[i]))
        if len(candidates) >= limit * settings.RAG_RERANK_POOL_MULT:
            break

    query_set = _rerank_query_terms(query_tokens)
    fields = field_tokens()
    candidates.sort(
        key=lambda pair: (pair[1] + _field_boost(query_set, fields[pair[0]]), pair[1]),
        reverse=True,
    )
    return candidates


def search_multi(queries, top_k=None):
    """多条同义说法分别检索，用 RRF（倒数排名融合）合并成一份结果。

    安全底线（最重要的是别写反）：
    - 每条说法各自过绝对门槛；不过门槛的说法不贡献候选。
    - 只要有一条说法过线，就认为「有可靠依据」，正常作答。
    - 只有全部说法都没过线，才返回 [] 触发拒答。

    RRF 只按名次融合、不按分数相加（BM25 分数在不同说法间不可直接比较），
    某片段得分 = Σ 1/(k + 名次)，名次从 1 开始，k = settings.RAG_RRF_K。
    """
    if not is_enabled():
        return []
    chunks = load_corpus()
    if not chunks:
        return []
    limit = top_k if top_k is not None else settings.RAG_TOP_K
    queries = [q for q in (queries or []) if isinstance(q, str) and q.strip()]
    if not queries:
        return []

    rrf_scores = {}   # chunk_index -> 融合分
    raw_scores = {}   # chunk_index -> 原始 BM25 分（仅用于展示/排序平局打破）
    for query in queries:
        for rank, (i, raw) in enumerate(_rank_for_fusion(query, chunks, limit), start=1):
            rrf_scores[i] = rrf_scores.get(i, 0.0) + 1.0 / (settings.RAG_RRF_K + rank)
            # 展示用原始分取各路最大值；注意融合排序完全由 rrf_scores 决定，
            # raw 只作同分时的次要键，不参与「是否有依据」判定。
            if raw > raw_scores.get(i, 0.0):
                raw_scores[i] = raw

    # 全部说法都没过门槛 → 无依据，拒答。
    if not rrf_scores:
        return []

    ranked = sorted(rrf_scores, key=lambda i: (rrf_scores[i], raw_scores.get(i, 0.0)), reverse=True)
    picked = _cap_per_doc([(i, raw_scores.get(i, 0.0)) for i in ranked], chunks, limit)
    return [_chunk_item(chunks[i], score, n)
            for n, (i, score) in enumerate(picked, start=1)]

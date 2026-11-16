"""Flavor Fusion 轻量 RAG 知识库（A 档：BM25 关键词检索）。

- 纯标准库可运行；jieba 若已安装会自动启用，未安装则回退内置分词。
- 不依赖 config.py / Flask / MySQL，命令行可在没有 .env 时独立自测。
- 通过环境变量 RAG_ENABLED=false 可一键回退到原有生成流程。
"""
from .retriever import search, build_index, load_corpus, reload_corpus, is_enabled
from .prompts import (
    build_rag_context,
    sources_payload,
    detect_risk_terms,
    verify_citations,
    level_badge,
    DISCLAIMER,
    HIGH_RISK_TERMS,
)
from .tokenizer import engine_name

__all__ = [
    "search", "build_index", "load_corpus", "reload_corpus", "is_enabled",
    "build_rag_context", "sources_payload", "detect_risk_terms",
    "verify_citations", "level_badge",
    "DISCLAIMER", "HIGH_RISK_TERMS", "engine_name",
]

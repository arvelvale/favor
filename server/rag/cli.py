"""命令行自测工具（不需要 .env、不启动 Flask）。

在 aifood/aifood3/aifood 目录下执行：
    python -m rag.cli ingest                     # 语料体检：文档数、片段数、元数据问题
    python -m rag.cli search "每天吃多少蔬菜"     # 查看命中片段与 BM25 分数
    python -m rag.cli prompt "孕妇能吃生鱼片吗"   # 预览注入 system 的约束文本
    python -m rag.cli sources "菠菜补铁吗"        # 预览前端引用卡片数据
"""
import argparse
import json
import sys

from . import settings
from .corpus import validate_documents
from .prompts import build_rag_context, sources_payload
from .retriever import load_corpus, search
from .tokenizer import engine_name


def cmd_ingest(args):
    problems, doc_count = validate_documents()
    chunks = load_corpus()
    print(f"知识库目录: {settings.KB_DIR}")
    print(f"分词引擎  : {engine_name()}")
    print(f"文档数    : {doc_count}")
    print(f"片段数    : {len(chunks)}")
    print(f"开关      : RAG_ENABLED={settings.RAG_ENABLED}, TOP_K={settings.RAG_TOP_K}, "
          f"相对阈值={settings.RAG_MIN_REL_SCORE}")
    if problems:
        print("语料问题  :")
        for problem in problems:
            print("  - " + problem)
    else:
        print("语料问题  : 无")
    return 0


def cmd_search(args):
    hits = search(args.query, top_k=args.top_k)
    print(f"查询: {args.query}")
    print(f"命中: {len(hits)} 条")
    for hit in hits:
        print(f"\n[{hit['citation']}] {hit['title']} · {hit['heading']}  (score={hit['score']})")
        print(f"    来源: {hit['publisher']} {hit['published']} {hit['url']}")
        print("    " + hit["text"].replace("\n", " / ")[:180])
    return 0


def cmd_prompt(args):
    hits = search(args.query)
    print(build_rag_context(hits, query=args.query))
    return 0


def cmd_sources(args):
    hits = search(args.query)
    print(json.dumps(sources_payload(hits, query=args.query),
                     ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Favor RAG 知识库命令行自测")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ingest", help="语料体检").set_defaults(func=cmd_ingest)
    p_search = sub.add_parser("search", help="检索测试")
    p_search.add_argument("query")
    p_search.add_argument("--top-k", type=int, default=None)
    p_search.set_defaults(func=cmd_search)
    p_prompt = sub.add_parser("prompt", help="预览注入 Prompt 的约束")
    p_prompt.add_argument("query")
    p_prompt.set_defaults(func=cmd_prompt)
    p_sources = sub.add_parser("sources", help="预览前端引用数据")
    p_sources.add_argument("query")
    p_sources.set_defaults(func=cmd_sources)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

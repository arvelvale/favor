"""RAG A 档离线检索评测（纯标准库，不需要 .env / 数据库 / API Key）。

在 server 目录下执行：
    python -m rag.evaluate                      # 跑评测并打印 Markdown 成绩表
    python -m rag.evaluate --md 报告路径.md      # 同时写入文件

指标口径：
- Recall@k：每题在 top-k 命中 expected_docs 中任意一个即算命中（题级命中率）。
- 无依据拒答率：expect_no_evidence 题检索结果为空的比例。
- 误报率：非无依据题却检索为空的比例。
- 平均检索耗时：只计 search() 本身，不含建索引首次开销。
"""
import argparse
import json
import sys
import time
from pathlib import Path

from . import settings
from .retriever import reload_corpus, search

QUESTIONS_PATH = Path(__file__).resolve().parent / "eval" / "questions.json"


def load_questions(path=QUESTIONS_PATH):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["questions"]


def evaluate(top_k=None):
    """返回 (逐题结果, 汇总指标)。"""
    reload_corpus()
    k = top_k if top_k is not None else settings.RAG_TOP_K
    questions = load_questions()
    rows = []
    timings = []

    for i, q in enumerate(questions):
        start = time.perf_counter()
        hits = search(q["query"], top_k=k)
        timings.append((time.perf_counter() - start) * 1000)

        hit_ids = [h["doc_id"] for h in hits]
        expect_none = bool(q.get("expect_no_evidence"))
        if expect_none:
            correct = not hits
            criterion = "应无命中"
        else:
            expected = set(q.get("expected_docs", []))
            correct = bool(expected.intersection(hit_ids))
            criterion = "或".join(expected)

        # 排序质量：首位是否就是期望来源（仅对有依据题有意义）
        first_hit_ok = (not expect_none) and bool(hit_ids) and hit_ids[0] in expected
        foreign = (not expect_none) and sum(1 for doc in hit_ids if doc not in expected)
        rows.append({
            "id": q["id"],
            "query": q["query"],
            "note": q.get("note", ""),
            "expect_none": expect_none,
            "criterion": criterion,
            "hit_ids": hit_ids,
            "top_score": hits[0]["score"] if hits else 0.0,
            "correct": correct,
            "first_hit_ok": first_hit_ok,
            "foreign": foreign,
        })

    positive = [r for r in rows if not r["expect_none"]]
    negative = [r for r in rows if r["expect_none"]]
    n = len(rows)
    summary = {
        "top_k": k,
        "total": n,
        "positive": len(positive),
        "negative": len(negative),
        "recall_at_k": sum(r["correct"] for r in positive) / len(positive) if positive else 0.0,
        "refusal_rate": sum(r["correct"] for r in negative) / len(negative) if negative else 0.0,
        "false_empty_rate": sum(not r["correct"] for r in positive) / len(positive) if positive else 0.0,
        "precision_at_1": sum(r["first_hit_ok"] for r in positive) / len(positive) if positive else 0.0,
        "avg_foreign_docs": sum(r["foreign"] for r in positive) / len(positive) if positive else 0.0,
        "avg_ms": sum(timings) / len(timings) if timings else 0.0,
        "max_ms": max(timings) if timings else 0.0,
    }
    return rows, summary


def render_markdown(rows, summary):
    lines = [
        "# RAG A 档检索评测成绩表",
        "",
        "评测方式：纯本地 BM25 检索，不调用大模型；`Recall@k` 按题级命中统计。",
        "",
        "| 指标 | 数值 | 判定 |",
        "|---|---|---|",
        f"| 总题数 | {summary['total']} | 有依据题 {summary['positive']}，无依据对照 {summary['negative']} |",
        f"| 检索深度 top-k | {summary['top_k']} | 与 RAG_TOP_K 一致 |",
        f"| Recall@{summary['top_k']} | {summary['recall_at_k']:.0%} | ≥80% 算可用；60~80% 需查切块/语料；<60% 别调生成 |",
        f"| 无依据拒答率 | {summary['refusal_rate']:.0%} | 对照题应检索为空，越高越好 |",
        f"| 有依据题误空率 | {summary['false_empty_rate']:.0%} | 越低越好 |",
        f"| 首位命中率 P@1 | {summary['precision_at_1']:.0%} | 最相关的资料排第一，越高越好 |",
        f"| 平均无关片段数 | {summary['avg_foreign_docs']:.2f} 条/题 | top-k 中非期望来源，越低越好 |",
        f"| 平均检索耗时 | {summary['avg_ms']:.2f} ms | 仅检索环节 |",
        f"| 最慢检索耗时 | {summary['max_ms']:.2f} ms | 仅检索环节 |",
        "",
        "## 逐题明细",
        "",
        "| 编号 | 问题 | 期望来源 | 实际命中 | 首位 | 判定 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        expected = "应无命中" if r["expect_none"] else r["criterion"]
        actual = "、".join(r["hit_ids"]) if r["hit_ids"] else "（空）"
        first = "—" if r["expect_none"] else ("✓" if r["first_hit_ok"] else "✗")
        mark = "通过" if r["correct"] else "未通过"
        lines.append(f"| {r['id']} | {r['query']} | {expected} | {actual} | {first} | {mark} |")
    lines.extend([
        "",
        "## 说明",
        "",
        "- 本表只评估「检索是否把正确资料交给模型」，不评估模型最终回答质量。",
        "- P@1（首位命中率）衡量排序质量：正确的资料是否排在第一条；Recall@k 只要求出现在 top-k 任意位置。",
        "- 排序用两阶段实现：先用原始 BM25 分数判定有无依据（安全底线），再在合格候选内按标题/小标题/标签命中重排。",
        "- 端到端的「无 RAG / 有 RAG」回答对照需要 `.env` 与 API Key，不属于离线评测范围。",
        "- 对照题（N01~N03）故意选取知识库不覆盖的用药、行情、疾病治疗问题；检索命中即为缺陷。",
        "- 语料已覆盖糖尿病/高血压等慢病「饮食原则」，但未覆盖用药剂量与治疗方案；"
        "此类问题若命中饮食资料属检索层正常行为，由 Prompt 高风险词规则强制追加「请咨询医生」兜底。",
        "- 绝对分数门槛 RAG_MIN_ABS_SCORE 默认值 10.0 来自本次实测分界；语料规模变化后需重跑本脚本复核。",
        "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="RAG A 档离线检索评测")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--md", default=None, help="把成绩表写入指定 Markdown 文件")
    args = parser.parse_args(argv)

    rows, summary = evaluate(args.top_k)
    report = render_markdown(rows, summary)
    print(report)
    if args.md:
        path = Path(args.md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        print(f"已写入: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

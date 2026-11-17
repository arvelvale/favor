"""RAG 知识库回归测试：语料体检、检索命中与拒答、引用自检、工具接入与开关。

运行（需 server 依赖）：python -m unittest discover -s tests -p 'test_rag.py' -v
检索相关用例不访问网络、不需要 .env / API Key。
"""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from rag import prompts as rag_prompts  # noqa: E402
from rag import retriever as rag_retriever  # noqa: E402
from rag import settings as rag_settings  # noqa: E402
from rag.cli import cmd_ingest  # noqa: E402
from rag.corpus import keyword_menu, load_chunks, validate_documents  # noqa: E402
from rag.glossary import expand_query, tool_description  # noqa: E402
from rag.tokenizer import tokenize  # noqa: E402


class CorpusTests(unittest.TestCase):
    def test_documents_have_required_metadata(self):
        problems, count = validate_documents()
        self.assertEqual(problems, [], f"语料元数据问题: {problems}")
        self.assertGreaterEqual(count, 20, "语料文档数不应少于 20 篇")

    def test_chunk_count_and_no_placeholder(self):
        chunks = load_chunks()
        self.assertGreaterEqual(len(chunks), 39)
        for chunk in chunks:
            self.assertTrue(chunk.text.strip())
            self.assertNotIn("【待补充】", chunk.text)

    def test_absolute_score_threshold_configured(self):
        self.assertGreaterEqual(rag_settings.RAG_MIN_ABS_SCORE, 10.0,
                                "绝对分数门槛过低会让无关问题误命中")

    def test_keyword_menu_from_corpus(self):
        """关键词菜单从语料自动生成：含高频标签、滤掉数字噪声。"""
        menu = keyword_menu()
        self.assertGreaterEqual(len(menu), 50, "菜单词数过少，词表提取可能失效")
        self.assertTrue({"蛋白质", "全谷物", "蔬菜", "膳食纤维"}.issubset(menu),
                        "核心高频词应自动进入菜单")
        for noise in ("12种", "25种"):
            self.assertNotIn(noise, menu, "纯数字/单位噪声不应进入菜单")

    def test_tool_description_contains_menu(self):
        """search_nutrition 的工具描述里带上了语料用词菜单。"""
        desc = tool_description()
        self.assertIn("检索时请优先使用知识库实际用词", desc)
        self.assertIn("1-3 种不同说法", desc)
        self.assertIn("番茄" if "番茄" in keyword_menu() else "蛋白质", desc)


class RetrievalTests(unittest.TestCase):
    def test_vegetable_question_hits_national_guide(self):
        hits = rag_retriever.search("每天应该吃多少蔬菜")
        self.assertTrue(hits)
        self.assertTrue(any("指南" in h["evidence_level"] or "政府" in h["evidence_level"] for h in hits))
        self.assertEqual(hits[0]["citation"], 1)

    def test_pagoda_numeric_value_present(self):
        hits = rag_retriever.search("蔬菜每天摄入量 300g")
        joined = " ".join(h["text"] for h in hits)
        self.assertIn("300", joined)

    def test_government_source_retrievable(self):
        hits = rag_retriever.search("减盐 低钠盐 慎用人群")
        self.assertTrue(any("卫生健康委员会" in (h.get("publisher") or "")
                            or "nhc.gov.cn" in (h.get("url") or "") for h in hits))

    def test_noise_question_refused(self):
        self.assertEqual(rag_retriever.search("qwertyuiop12345"), [])

    def test_out_of_scope_question_refused(self):
        self.assertEqual(rag_retriever.search("今天沪深股市大盘行情"), [])

    def test_citation_numbers_sequential(self):
        hits = rag_retriever.search("每天吃多少奶制品")
        self.assertEqual([h["citation"] for h in hits], list(range(1, len(hits) + 1)))

    def test_chinese_tokenizer_and_glossary(self):
        self.assertIn("铁", tokenize("菠菜补铁"))
        expanded = expand_query("tomato egg")
        self.assertIn("番茄", expanded)
        self.assertIn("鸡蛋", expanded)

    def test_tokenizer_ignores_installed_jieba(self):
        """门槛 10.0 按内置分词标定；即使环境里装了 jieba，分词结果也不能变。"""
        import importlib
        from rag import tokenizer as tok
        before = tok.tokenize("每天应该吃多少蔬菜")
        fake = NS(cut_for_search=lambda text: ["每天", "蔬菜"])
        saved = sys.modules.get("jieba")
        sys.modules["jieba"] = fake
        try:
            importlib.reload(tok)
            self.assertEqual(tok.engine_name(), "builtin-unigram+bigram")
            self.assertEqual(tok.tokenize("每天应该吃多少蔬菜"), before)
        finally:
            if saved is None:
                sys.modules.pop("jieba", None)
            else:
                sys.modules["jieba"] = saved
            importlib.reload(tok)


class MultiQueryTests(unittest.TestCase):
    """方案2：多说法检索 + RRF 融合的核心不变量。"""

    def test_single_query_matches_search(self):
        """只有一个说法时，融合结果必须和单查询 search 完全一致（退化一致性）。"""
        for q in ("每天应该吃多少蔬菜", "成年人每天食盐不超过多少", "阿司匹林的用法用量"):
            self.assertEqual([h["doc_id"] for h in rag_retriever.search(q)],
                             [h["doc_id"] for h in rag_retriever.search_multi([q])], q)

    def test_multi_query_refusal_safety(self):
        """安全底线：对照题即使拆成多个说法，也必须全部拒答。"""
        cases = [
            ["阿司匹林的用法用量", "阿司匹林吃多少片", "阿司匹林怎么服用"],
            ["股票代码600519今天涨跌", "贵州茅台股价", "今天大盘行情"],
            ["左甲状腺素钠片一片多少毫克", "优甲乐剂量", "甲状腺药物用法"],
        ]
        for queries in cases:
            self.assertEqual(rag_retriever.search_multi(queries), [], queries)

    def test_multi_query_fuses_synonyms(self):
        """多说法融合：同义问法应把正确资料带进结果，且不破坏 citation 编号。"""
        hits = rag_retriever.search_multi(["西红柿有什么营养", "番茄的营养价值", "深色蔬菜的好处"])
        self.assertTrue(hits, "同义说法应能命中资料")
        self.assertEqual([h["citation"] for h in hits], list(range(1, len(hits) + 1)))
        self.assertTrue(any(h["doc_id"].startswith("cdg2022") for h in hits),
                        "应命中膳食指南类资料")

    def test_multi_query_citation_numbers_sequential(self):
        hits = rag_retriever.search_multi(["每天吃多少蔬菜", "蔬菜摄入量建议"])
        self.assertEqual([h["citation"] for h in hits], list(range(1, len(hits) + 1)))


class PromptSafetyTests(unittest.TestCase):
    def test_no_evidence_context_forbids_numbers(self):
        text = rag_prompts.build_rag_context([], query="糖尿病胰岛素剂量")
        self.assertIn("暂无可靠依据", text)
        self.assertIn("咨询医生", text)

    def test_risk_terms_detected(self):
        terms = rag_prompts.detect_risk_terms("孕妇能吃生鱼片吗")
        self.assertIn("孕妇", terms)

    def test_evidence_badge_falls_back_safely(self):
        css_class, label = rag_prompts.level_badge("未知等级")
        self.assertEqual(css_class, "popular")

    def test_verify_citations_catches_fabricated_number(self):
        sources = [{"citation": 1}, {"citation": 2}]
        audit = rag_prompts.verify_citations("根据资料 [1][9] 来看", sources)
        self.assertEqual(audit["invalid"], [9])
        self.assertEqual(audit["level"], "error")
        self.assertFalse(audit["ok"])

    def test_verify_citations_levels(self):
        sources = [{"citation": 1}, {"citation": 2}]
        self.assertEqual(rag_prompts.verify_citations("结论 [1][2]", sources)["level"], "ok")
        self.assertEqual(rag_prompts.verify_citations("结论 [1]", sources)["level"], "warn")  # 漏引
        self.assertEqual(rag_prompts.verify_citations("没有编号", sources)["level"], "warn")  # 未标注

    def test_verify_citations_ok(self):
        sources = [{"citation": 1}, {"citation": 2}]
        audit = rag_prompts.verify_citations("结论是 [1][2]", sources)
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["cited"], [1, 2])

    def test_sources_payload_shape(self):
        hits = rag_retriever.search("每天吃多少蔬菜")
        payload = rag_prompts.sources_payload(hits, query="每天吃多少蔬菜")
        self.assertFalse(payload["no_evidence"])
        self.assertTrue(payload["sources"])
        self.assertIn("evidence_label", payload["sources"][0])


class ToolIntegrationTests(unittest.TestCase):
    """工具层需要 flask，由 test_server.py 的运行环境（venv）覆盖。"""

    def test_search_nutrition_registered_and_schema(self):
        from agent import tools
        self.assertIn("search_nutrition", tools.TOOLS)
        schemas = tools.schemas(image_enabled=False, rag_enabled=True)
        names = [s["function"]["name"] for s in schemas]
        self.assertIn("search_nutrition", names)
        self.assertNotIn("generate_food_image", names)

    def test_schema_hides_rag_when_disabled(self):
        from agent import tools
        names = [s["function"]["name"] for s in tools.schemas(rag_enabled=False)]
        self.assertNotIn("search_nutrition", names)

    def test_schema_queries_is_array(self):
        """方案2：工具参数改为 queries 字符串数组，引导模型给多种说法。"""
        from agent import tools
        schemas = tools.schemas(image_enabled=False, rag_enabled=True)
        fn = next(s["function"] for s in schemas if s["function"]["name"] == "search_nutrition")
        self.assertIn("queries", fn["parameters"]["properties"])
        self.assertEqual(fn["parameters"]["properties"]["queries"]["type"], "array")
        self.assertIn("queries", fn["parameters"]["required"])

    def test_tool_accepts_queries_array(self):
        """新调用：传 queries 数组，正常返回引用。"""
        from agent import tools
        ctx = tools.ToolContext(conn=NS(commit=lambda: None, rollback=lambda: None),
                                user_id=1, now=datetime.now())
        result, cards = tools.execute(ctx, "search_nutrition",
                                      json.dumps({"queries": ["每天吃多少蔬菜", "蔬菜摄入量建议"]}))
        self.assertTrue(result["ok"])
        self.assertGreater(result["hit_count"], 0)
        self.assertEqual(cards[0]["type"], "sources")

    def test_tool_still_accepts_legacy_query_string(self):
        """兼容：老的 query 单字符串调用行为不变（离线评测/旧测试依赖）。"""
        from agent import tools
        ctx = tools.ToolContext(conn=NS(commit=lambda: None, rollback=lambda: None),
                                user_id=1, now=datetime.now())
        result, _ = tools.execute(ctx, "search_nutrition", json.dumps({"query": "成年人每天食盐不超过多少"}))
        self.assertTrue(result["ok"])
        self.assertGreater(result["hit_count"], 0)

    def test_tool_returns_citations_and_card(self):
        from agent import tools
        ctx = tools.ToolContext(conn=NS(commit=lambda: None, rollback=lambda: None),
                                user_id=1, now=datetime.now())
        result, cards = tools.execute(ctx, "search_nutrition", json.dumps({"query": "每天吃多少蔬菜"}))
        self.assertTrue(result["ok"])
        self.assertGreater(result["hit_count"], 0)
        self.assertEqual(result["citation_numbers"], [1, 2, 3, 4][:result["hit_count"]])
        self.assertEqual(cards[0]["type"], "sources")
        self.assertIn("[1]", result["reference_material"])

    def test_second_search_in_same_turn_continues_numbering(self):
        """同一轮查两次资料，编号要接着排，否则两批 [1] 指向不同出处、自检也会混淆。"""
        from agent import tools
        ctx = tools.ToolContext(conn=NS(commit=lambda: None, rollback=lambda: None),
                                user_id=1, now=datetime.now())
        first, _ = tools.execute(ctx, "search_nutrition", json.dumps({"query": "每天吃多少蔬菜"}))
        second, cards = tools.execute(ctx, "search_nutrition", json.dumps({"query": "成年人每天食盐不超过多少"}))
        n1, n2 = first["citation_numbers"], second["citation_numbers"]
        self.assertTrue(n1 and n2)
        self.assertEqual(n2, list(range(len(n1) + 1, len(n1) + len(n2) + 1)))
        self.assertEqual([s["citation"] for s in cards[0]["sources"]], n2)
        self.assertIn(f"[{n2[0]}]", second["reference_material"])
        self.assertNotIn("[1] ", second["reference_material"])

    def test_tool_no_evidence_card(self):
        from agent import tools
        ctx = tools.ToolContext(conn=NS(commit=lambda: None, rollback=lambda: None),
                                user_id=1, now=datetime.now())
        result, cards = tools.execute(ctx, "search_nutrition", json.dumps({"query": "qwertyuiop12345"}))
        self.assertEqual(result["hit_count"], 0)
        self.assertTrue(cards[0]["no_evidence"])


class EvalBaselineTests(unittest.TestCase):
    """评测安全网：语料或检索逻辑变动后，跑测试即可发现成绩退化。"""

    def test_recall_and_false_empty_baseline(self):
        from rag.evaluate import evaluate
        rows, summary = evaluate()
        self.assertGreaterEqual(summary["recall_at_k"], 0.8,
                                f"Recall@{summary['top_k']} 退化到 {summary['recall_at_k']:.0%}")
        self.assertEqual(summary["false_empty_rate"], 0.0,
                         "有依据题不应检索为空")

    def test_ranking_and_refusal_baseline(self):
        """排序质量与拒答底线：标题重排只能提升 P@1，绝不能破坏拒答。"""
        from rag.evaluate import evaluate
        rows, summary = evaluate()
        self.assertGreaterEqual(summary["precision_at_1"], 0.85,
                                f"首位命中率退化到 {summary['precision_at_1']:.0%}")
        self.assertLessEqual(summary["avg_foreign_docs"], 1.5,
                             f"无关片段过多：{summary['avg_foreign_docs']:.2f} 条/题")
        self.assertEqual(summary["refusal_rate"], 1.0,
                         "无依据对照题必须全部拒答——标题加分若误入判定阶段会破坏此底线")

    def test_report_baseline_exists(self):
        report = ROOT / "server" / "rag" / "eval" / "report.md"
        self.assertTrue(report.exists(),
                        "缺少评测基线成绩单，先跑 python -m rag.evaluate --md rag/eval/report.md")

    def test_adversarial_questions_all_pass(self):
        """对抗题（错别字/口语/多意图 + 超范围拒答）必须逐题通过，防止题库被改坏。"""
        from rag.evaluate import evaluate
        rows, _ = evaluate()
        def is_adversarial(rid):
            if not rid[1:].isdigit():
                return False
            num = int(rid[1:])
            return (rid.startswith("Q") and num >= 43) or (rid.startswith("N") and num >= 4)
        adversarial = [r for r in rows if is_adversarial(r["id"])]
        self.assertGreaterEqual(len(adversarial), 12, "对抗题数量不足，题库可能被误删")
        failed = [r["id"] + " " + r["query"] for r in adversarial if not r["correct"]]
        self.assertEqual(failed, [], "对抗题出现未通过：" + "、".join(failed))


if __name__ == "__main__":
    unittest.main(verbosity=2)

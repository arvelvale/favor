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


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""把检索片段拼成 Prompt 约束，并生成给前端的引用数据。

医学/营养安全规则集中放在这里，方便单独审阅与测试。
"""
import re

DISCLAIMER = "以上营养信息为科普参考，不构成医疗建议；如有疾病或特殊情况，请咨询医生或临床营养师。"

# 命中这些词时，回答必须额外给出就医提示
HIGH_RISK_TERMS = (
    "孕妇", "乳母", "哺乳", "备孕", "婴幼儿", "婴儿", "新生儿", "儿童",
    "老人", "糖尿病", "肾病", "高血压", "痛风", "高尿酸", "过敏", "术后",
    "服药", "用药", "药物", "剂量", "处方", "化疗", "肝病", "心血管", "慢性病", "疾病", "治疗",
    "减肥", "节食", "贫血", "妊娠",
)

_RULES = """检索资料使用规则（必须严格遵守）：
1. 营养数值、推荐摄入量、健康结论只能来自下面列出的片段，不得凭记忆补充或推算。
2. 每一条涉及营养或健康的结论后面用 [编号] 标注对应片段，例如 [1]。
3. 引用编号只能使用下面片段实际给出的编号；不得写出 [编号] 列表中不存在的编号；同一结论可引多个编号，如 [1][3]。
4. 片段不足以回答时，明确写「知识库暂无可靠依据」，不要编造数值或结论，也不要写任何 [编号]。
5. 只做科普参考，不做诊断、用药、剂量或治疗方案建议。
6. 涉及孕妇、婴幼儿、慢性病、过敏等特殊人群时，必须提示咨询医生或临床营养师。
7. 食谱的烹饪步骤、摆盘、口味描述可以正常发挥，不受上述限制；食材用量属于烹饪细节，无需标注引用。"""

_NO_EVIDENCE = """[知识库检索结果]
本次提问未检索到可引用的资料片段。
必须遵守：不得给出任何具体营养数值、摄入量或医学结论；若用户的问题涉及营养或健康，
明确回答「知识库暂无可靠依据，建议咨询医生或临床营养师」。
食谱的烹饪步骤、摆盘、口味描述仍可正常生成。"""


def detect_risk_terms(text):
    """返回按 HIGH_RISK_TERMS 顺序命中的词列表。"""
    text = text or ""
    return [term for term in HIGH_RISK_TERMS if term in text]


# 证据等级 → 前端样式类与中文标签
EVIDENCE_LEVELS = {
    "国家级学会指南": ("guide", "国家级学会指南"),
    "政府公开文件": ("gov", "政府公开文件"),
    "同行评议文献": ("paper", "同行评议文献"),
    "科普整理": ("popular", "科普整理 · 非临床指南"),
}


def level_badge(evidence_level):
    """返回 (样式类, 中文标签)；未知等级按科普处理，避免冒充权威。"""
    return EVIDENCE_LEVELS.get(evidence_level or "", ("popular", "证据等级未标注"))


_CITATION_RE = re.compile(r"\[(\d+)\]")


def verify_citations(answer, sources):
    """核对答案里的 [n] 是否都能在本次 sources 中找到出处。

    这是格式层校验：抓「编造编号」和「有依据却完全不引用」，
    不判断引用内容是否真的支撑结论（那属于语义层，仍需人工核对）。
    """
    answer = answer or ""
    sources = sources or []
    valid = {int(s["citation"]) for s in sources if str(s.get("citation", "")).isdigit()}
    cited = sorted({int(n) for n in _CITATION_RE.findall(answer)})
    invalid = [n for n in cited if n not in valid]
    uncited = sorted(valid - set(cited))

    if invalid:
        level = "error"
        notice = ("答案中出现本次资料里不存在的引用编号：" +
                  "、".join(f"[{n}]" for n in invalid) +
                  "。这些编号没有对应出处，请勿采信相关结论。")
    elif valid and not cited:
        level = "warn"
        notice = "本次检索到了可引用资料，但答案未标注任何引用编号，营养相关结论请人工核对。"
    elif uncited:
        level = "warn"
        notice = "引用编号均有效；另有资料提供了依据但答案未引用：" + "、".join(f"[{n}]" for n in uncited)
    elif not valid:
        level = "warn"
        notice = "本次无可引用资料；若答案含营养数值或结论，请谨慎对待。"
    else:
        level = "ok"
        notice = "答案中的引用编号均可在下方资料中找到对应出处。"

    return {
        "cited": cited,
        "valid": sorted(valid),
        "invalid": invalid,
        "uncited": uncited,
        "ok": not invalid and bool(cited) if valid else not invalid,
        "level": level,
        "notice": notice,
    }


def build_rag_context(hits, query=""):
    """生成注入 system message 的中文约束文本；hits 为空时走拒答约束。"""
    if not hits:
        parts = [_NO_EVIDENCE]
        risk_terms = detect_risk_terms(query)
        if risk_terms:
            parts.append("本次提问涉及特殊人群或健康风险词（" + "、".join(risk_terms) +
                         "），回答中必须提示咨询医生或临床营养师。")
        parts.append("通用免责声明：" + DISCLAIMER)
        return "\n".join(parts)

    lines = ["[知识库检索结果] 以下片段是本次回答唯一可用的营养/健康依据：", ""]
    for hit in hits:
        lines.append(
            "[{n}] {title} · {heading}（{publisher}，{published}）\n{text}".format(
                n=hit["citation"],
                title=hit.get("title", ""),
                heading=hit.get("heading", ""),
                publisher=hit.get("publisher", ""),
                published=hit.get("published", ""),
                text=hit.get("text", ""),
            )
        )
        lines.append("")
    lines.append(_RULES)
    risk_terms = detect_risk_terms(query)
    if risk_terms:
        lines.append("本次提问涉及特殊人群或健康风险词（" + "、".join(risk_terms) +
                     "），回答中必须提示咨询医生或临床营养师。")
    lines.append("通用免责声明：" + DISCLAIMER)
    return "\n".join(lines)


def sources_payload(hits, query=""):
    """前端引用卡片所需的数据，结构稳定，便于单测。"""
    sources = []
    for hit in hits:
        snippet = (hit.get("text") or "").replace("\n", " ")
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        level_class, level_label = level_badge(hit.get("evidence_level"))
        sources.append({
            "citation": hit["citation"],
            "title": hit.get("title", ""),
            "heading": hit.get("heading", ""),
            "publisher": hit.get("publisher", ""),
            "published": hit.get("published", ""),
            "url": hit.get("url", ""),
            "snippet": snippet,
            "score": hit.get("score", 0),
            "evidence_level": hit.get("evidence_level", ""),
            "evidence_class": level_class,
            "evidence_label": level_label,
            "audience": hit.get("audience", ""),
        })
    risk_terms = detect_risk_terms(query)
    return {
        "sources": sources,
        "no_evidence": len(sources) == 0,
        "risk_terms": risk_terms,
        "risk_notice": ("检测到特殊人群或健康风险相关提问，请咨询医生或临床营养师。"
                        if risk_terms else ""),
        "disclaimer": DISCLAIMER,
    }

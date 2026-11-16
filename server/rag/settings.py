"""RAG 模块配置。

只读取环境变量与路径，不 import config.py / Flask，
这样在没有 .env 的机器上也能用命令行跑检索自测。
"""
import os
from pathlib import Path

# 知识库目录，可用 RAG_KB_DIR 覆盖。
# 注意：.env 里写 RAG_KB_DIR= 空值时，os.getenv 返回 "" 而非默认值，
# 必须用 or 兜底，否则目录会退化成当前目录、语料全部丢失。
KB_DIR = Path(os.getenv("RAG_KB_DIR") or str(Path(__file__).resolve().parent / "kb"))

# 总开关：出问题时设为 false 即可完整回退到原来的生成流程
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

# 注入 Prompt 的最大片段数
RAG_TOP_K = max(1, int(os.getenv("RAG_TOP_K", "4")))

# 相对得分阈值：只保留不低于最高分这一比例的片段，避免把无关内容塞进 Prompt
RAG_MIN_REL_SCORE = min(1.0, max(0.0, float(os.getenv("RAG_MIN_REL_SCORE", "0.55"))))

# 绝对得分门槛：最高分低于此值即视为「知识库无可靠依据」。
# 默认值 10.0 来自 28 题离线评测的实测分界（正常题最低 11.68，无关题 3.43/7.12）。
# 语料规模大幅变化后应重跑 python -m rag.evaluate 复核此值。
RAG_MIN_ABS_SCORE = max(0.0, float(os.getenv("RAG_MIN_ABS_SCORE", "10.0")))

# 单个片段最大字符数
RAG_CHUNK_CHARS = max(120, int(os.getenv("RAG_CHUNK_CHARS", "420")))

# 阶段②重排权重：查询词命中「文档标题 / 小标题 / 标签」时给片段的加分。
# 关键：这些加分只用于给已通过门槛的候选重新排序，绝不参与「是否有依据」的判定，
# 否则用药/无关问题会被加分冲过绝对门槛，导致拒答率崩塌（实测 100%→33%）。
# 用 or 兜底空值，避免 .env 里写 KEY= 时 os.getenv 返回 "" 而非默认值。
RAG_TITLE_BOOST = float(os.getenv("RAG_TITLE_BOOST") or "2.0")
RAG_HEADING_BOOST = float(os.getenv("RAG_HEADING_BOOST") or "0.8")
RAG_TAG_BOOST = float(os.getenv("RAG_TAG_BOOST") or "0.8")
# 重排候选池放大倍数：候选数 = top_k × 此值，放大后才不会把该排前面的片段挡在池外。
RAG_RERANK_POOL_MULT = max(1, int(os.getenv("RAG_RERANK_POOL_MULT") or "3"))

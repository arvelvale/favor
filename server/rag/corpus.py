"""知识库语料加载：解析 Markdown front-matter 元数据并切成检索片段。

语料规范见 rag/kb/README.md。含【待补充】的段落不会进入索引，
避免出现「看起来有依据、其实是空占位」的情况。
"""
from dataclasses import dataclass, field
from pathlib import Path

from . import settings

REQUIRED_META = ("title", "source", "publisher", "published", "url", "evidence_level")


@dataclass
class Document:
    doc_id: str
    meta: dict
    body: str
    path: str


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    heading: str
    text: str
    publisher: str
    published: str
    source_url: str
    evidence_level: str
    audience: str = ""
    tags: list = field(default_factory=list)


def parse_front_matter(text):
    """解析极简 YAML front-matter（只支持 key: value 单行）。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:])
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return {}, text


def load_documents(kb_dir=None):
    """读取 kb 目录下全部 .md（README.md 不作为语料）。"""
    root = Path(kb_dir) if kb_dir else settings.KB_DIR
    docs = []
    if not root.is_dir():
        return docs
    for path in sorted(root.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(text)
        docs.append(Document(
            doc_id=path.stem,
            meta=meta,
            body=body,
            path=str(path),
        ))
    return docs


def validate_documents(docs=None):
    """返回 (问题列表, 文档数)，供 CLI 的 ingest 命令做语料体检。"""
    docs = load_documents() if docs is None else docs
    problems = []
    for doc in docs:
        missing = [key for key in REQUIRED_META if not doc.meta.get(key)]
        if missing:
            problems.append(f"{doc.doc_id}: 缺少元数据 {', '.join(missing)}")
        if "【待补充】" in doc.body and not doc.body.replace("【待补充】", "").strip("-\n "):
            problems.append(f"{doc.doc_id}: 正文为空占位，仅作结构示例")
    return problems, len(docs)


def _flush(buf, heading, doc, chunks):
    if not buf:
        return
    text = "\n".join(buf).strip()
    if not text:
        return
    chunks.append(Chunk(
        chunk_id=f"{doc.doc_id}#{len(chunks) + 1}",
        doc_id=doc.doc_id,
        title=doc.meta.get("title", doc.doc_id),
        heading=heading,
        text=text,
        publisher=doc.meta.get("publisher", ""),
        published=doc.meta.get("published", ""),
        source_url=doc.meta.get("url", ""),
        evidence_level=doc.meta.get("evidence_level", ""),
        audience=doc.meta.get("audience", ""),
        tags=[t.strip() for t in doc.meta.get("tags", "").split(",") if t.strip()],
    ))
    buf.clear()


def load_chunks(kb_dir=None):
    """把全部文档切成片段；长段落按字符上限切，标题作为上下文保留在 heading。"""
    docs = load_documents(kb_dir)
    chunks = []
    max_chars = settings.RAG_CHUNK_CHARS
    for doc in docs:
        heading = doc.meta.get("title", doc.doc_id)
        buf = []
        size = 0
        for raw_line in doc.body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "【待补充】" in line:
                continue
            if line.startswith("#"):
                _flush(buf, heading, doc, chunks)
                heading = line.lstrip("#").strip() or heading
                size = 0
                continue
            if size + len(line) > max_chars and buf:
                _flush(buf, heading, doc, chunks)
                size = 0
            buf.append(line)
            size += len(line)
        _flush(buf, heading, doc, chunks)
    return chunks

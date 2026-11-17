"""Document ingestion: load -> extract text -> chunk -> save chunks.json.

Supported inputs in data/docs/:
  * .txt / .md  - optional front-matter block:
        ---
        scheme: pm-kisan
        title: PM-KISAN operational guidelines
        url: https://pmkisan.gov.in
        lang: en
        ---
  * .pdf        - text extracted with PyMuPDF (page numbers kept).
        Metadata comes from data/docs/sources.json (filename -> fields).

Run:  python -m app.ingest
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from . import config


@dataclass
class Chunk:
    id: str
    scheme: str
    title: str
    url: str
    lang: str
    page: int | None
    text: str


_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def _parse_front_matter(raw: str) -> tuple[dict, str]:
    m = _FRONT.match(raw)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta, raw[m.end():]


def _clean(text: str) -> str:
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_words(text: str, size: int, overlap: int) -> list[str]:
    """Split on paragraph boundaries first, then pack into ~size-word chunks."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for p in paras:
        words = p.split()
        if len(words) > size:  # very long paragraph: hard split
            if cur:
                chunks.append(" ".join(cur))
                cur, cur_len = [], 0
            step = max(1, size - overlap)
            for i in range(0, len(words), step):
                chunks.append(" ".join(words[i : i + size]))
                if i + size >= len(words):
                    break
            continue
        if cur_len + len(words) > size and cur:
            chunks.append(" ".join(cur))
            tail = " ".join(cur).split()[-overlap:] if overlap else []
            cur, cur_len = tail[:], len(tail)
        cur.extend(words)
        cur_len += len(words)
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if len(c.split()) >= 8]


def _load_manifest() -> dict:
    path = config.DOCS_DIR / "sources.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _read_pdf(path: Path) -> list[tuple[int, str]]:
    import pymupdf  # lazy import

    pages = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            pages.append((i, page.get_text()))
    return pages


def build_chunks() -> list[Chunk]:
    manifest = _load_manifest()
    chunks: list[Chunk] = []
    for path in sorted(config.DOCS_DIR.iterdir()):
        if path.suffix.lower() not in {".txt", ".md", ".pdf"}:
            continue
        meta = dict(manifest.get(path.name, {}))
        pages: list[tuple[int | None, str]]
        if path.suffix.lower() == ".pdf":
            pages = _read_pdf(path)
        else:
            m, body = _parse_front_matter(path.read_text(encoding="utf-8"))
            meta = {**m, **meta}
            pages = [(None, body)]
        scheme = meta.get("scheme", path.stem)
        title = meta.get("title", path.stem.replace("_", " "))
        url = meta.get("url", "")
        lang = meta.get("lang", "en")
        n = 0
        for page_no, text in pages:
            for piece in chunk_words(_clean(text), config.CHUNK_WORDS, config.CHUNK_OVERLAP):
                chunks.append(
                    Chunk(
                        id=f"{path.stem}#{n}",
                        scheme=scheme,
                        title=title,
                        url=url,
                        lang=lang,
                        page=page_no,
                        text=piece,
                    )
                )
                n += 1
    return chunks


def main() -> None:
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    chunks = build_chunks()
    out = config.INDEX_DIR / "chunks.json"
    out.write_text(
        json.dumps([asdict(c) for c in chunks], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    schemes = sorted({c.scheme for c in chunks})
    print(f"Wrote {len(chunks)} chunks from {len(schemes)} schemes -> {out}")


if __name__ == "__main__":
    main()

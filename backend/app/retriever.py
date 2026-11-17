"""Retrievers. Default is TF-IDF (no model download). Optional dense + FAISS."""
from __future__ import annotations

import json
import re

import numpy as np

from . import config
from .ingest import Chunk, build_chunks

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

_TOKEN = re.compile(r"[\wऀ-ॿ]+", re.U)  # Latin + Devanagari

# Generic words that should never drive retrieval on their own.
_HI_STOP = {
    "है", "हैं", "में", "का", "की", "के", "को", "से", "और", "या", "कि", "क्या",
    "कितना", "कितने", "कितनी", "कैसे", "कौन", "पर", "ही", "भी", "एक", "यह", "वह",
    "लिए", "साल", "करें", "करना", "मिलता", "मिलती", "मिलते", "जा", "सकता", "सकते",
}
_GENERIC = {
    "scheme", "schemes", "yojana", "government", "govt", "india", "indian", "need", "needed", "apply",
    "does", "did", "doe", "rupee", "rupees", "rs",
}
STOP = set(ENGLISH_STOP_WORDS) | _HI_STOP | _GENERIC


def _stem(t: str) -> str:
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def content_tokens(text: str) -> list[str]:
    """Lower-case, drop stop-words, light plural stemming."""
    return [_stem(t) for t in (w.lower() for w in _TOKEN.findall(text)) if t not in STOP]


def _tokenize(text: str) -> list[str]:
    return content_tokens(text)


class Retriever:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []

    # -- to implement ------------------------------------------------
    def _scores(self, query: str) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    # -- shared ------------------------------------------------------
    def search(
        self,
        query: str,
        k: int | None = None,
        scheme: str | None = None,
        min_score: float | None = None,
    ) -> list[tuple[Chunk, float]]:
        k = k or config.TOP_K
        min_score = config.MIN_SCORE if min_score is None else min_score
        scores = self._scores(query)
        order = np.argsort(-scores)
        out: list[tuple[Chunk, float]] = []
        for i in order:
            ch = self.chunks[i]
            if scheme and ch.scheme != scheme:
                continue
            if scores[i] < min_score:
                break
            out.append((ch, float(scores[i])))
            if len(out) >= k:
                break
        return out

    def schemes(self) -> dict[str, dict]:
        info: dict[str, dict] = {}
        for c in self.chunks:
            d = info.setdefault(c.scheme, {"id": c.scheme, "titles": set(), "urls": set()})
            d["titles"].add(c.title)
            if c.url:
                d["urls"].add(c.url)
        return {
            k: {"id": k, "titles": sorted(v["titles"]), "urls": sorted(v["urls"])}
            for k, v in info.items()
        }


class TfidfRetriever(Retriever):
    def __init__(self, chunks: list[Chunk] | None = None) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        super().__init__()
        self.chunks = chunks if chunks is not None else _load_chunks()
        self.vec = TfidfVectorizer(
            tokenizer=_tokenize,
            token_pattern=None,
            lowercase=False,
            ngram_range=(1, 2),
            sublinear_tf=True,
            stop_words=None,
        )
        # Title is part of the searchable text so scheme names match strongly.
        corpus = [f"{c.title}. {c.text}" for c in self.chunks]
        self.matrix = self.vec.fit_transform(corpus)

    def _scores(self, query: str) -> np.ndarray:
        q = self.vec.transform([query])
        return (self.matrix @ q.T).toarray().ravel()


class DenseRetriever(Retriever):
    def __init__(self) -> None:
        import faiss
        from sentence_transformers import SentenceTransformer

        super().__init__()
        self.chunks = _load_chunks()
        self.model = SentenceTransformer(config.EMBED_MODEL)
        emb = self.model.encode(
            [f"{c.title}. {c.text}" for c in self.chunks],
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")
        self.index = faiss.IndexFlatIP(emb.shape[1])
        self.index.add(emb)
        self.n = len(self.chunks)

    def _scores(self, query: str) -> np.ndarray:
        q = self.model.encode([query], normalize_embeddings=True).astype("float32")
        sims, ids = self.index.search(q, self.n)
        out = np.zeros(self.n, dtype="float32")
        out[ids[0]] = sims[0]
        return out


def _load_chunks() -> list[Chunk]:
    path = config.INDEX_DIR / "chunks.json"
    if path.exists():
        return [Chunk(**d) for d in json.loads(path.read_text(encoding="utf-8"))]
    return build_chunks()


def get_retriever() -> Retriever:
    if config.RETRIEVER == "dense":
        return DenseRetriever()
    return TfidfRetriever()

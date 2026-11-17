"""RAG answer pipeline: contextualise -> retrieve -> gate -> generate -> verify -> (fallback)."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from . import config, eligibility, llm, web_search
from .retriever import _TOKEN, Retriever, TfidfRetriever, content_tokens
from .verifier import should_reject, verify

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
RUPEE = re.compile(r"(?:₹|Rs\.?|INR)\s?([\d,]+(?:\.\d+)?)(?:\s?(lakh|crore))?", re.I)

SYSTEM_PROMPT = """You are an assistant that explains Indian government schemes and public services.
Answer ONLY from the numbered SOURCES below. Rules:
1. Do not use outside knowledge. If the sources do not contain the answer, say you could not find it in the available documents.
2. Write short sentences with one fact each. End each factual sentence with the number of the source that supports it, like [1].
3. Copy numbers, amounts and ages exactly as written in the sources.
4. If sources disagree (for example different amounts or dates), say so and show both with their source numbers.
5. Never say a person is or is not eligible and never offer to apply for them. You may say which published conditions the person's details appear to match.
6. Use simple words. Reply in {language}.
7. Finish with one short reminder to confirm details on the official website."""

REWRITE_PROMPT = (
    "Rewrite the user's latest question as one standalone question, using the earlier "
    "questions only to fill in what 'it', 'this scheme' or similar words refer to. "
    "Keep the language of the latest question. Output only the question."
)


@dataclass
class Answer:
    answer: str
    sources: list[dict]
    warnings: list[str] = field(default_factory=list)
    mode: str = "extractive"  # "llm" | "extractive" | "none"
    grounded: bool = True
    verification: dict | None = None
    top_scheme: str | None = None
    standalone: str = ""
    origin: str = "library"  # "library" (verified documents) | "web" (official pages found live)
    translated_to: str | None = None  # regional language code when `answer` is a translation
    answer_en: str | None = None  # the verified English original of a translated answer


def detect_language(text: str) -> str:
    return "hi" if DEVANAGARI.search(text) else "en"


def _amounts(text: str) -> set[float]:
    vals = set()
    for num, unit in RUPEE.findall(text):
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        if unit.lower() == "lakh":
            v *= 1e5
        elif unit.lower() == "crore":
            v *= 1e7
        vals.add(v)
    return vals


def find_conflicts(hits: list[tuple]) -> list[str]:
    """Heuristic: same scheme, different documents, different rupee figures."""
    warnings = []
    by_scheme: dict[str, dict[str, set[float]]] = {}
    for ch, _ in hits:
        by_scheme.setdefault(ch.scheme, {}).setdefault(ch.title, set()).update(_amounts(ch.text))
    for scheme, docs in by_scheme.items():
        if len(docs) < 2:
            continue
        titles = list(docs)
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                a, b = docs[titles[i]], docs[titles[j]]
                if a and b and a != b:
                    warnings.append(
                        f"Sources may conflict on amounts for '{scheme}': "
                        f"'{titles[i]}' vs '{titles[j]}'. Check the official site for the latest figure."
                    )
    return warnings


def _highlight_terms(excerpt: str, q_terms: set[str]) -> list[str]:
    seen: dict[str, None] = {}
    for w in _TOKEN.findall(excerpt):
        if content_tokens(w) and content_tokens(w)[0] in q_terms:
            seen[w.lower()] = None
    return sorted(seen, key=len, reverse=True)[:12]


def _source_payload(hits: list[tuple], q_terms: set[str]) -> list[dict]:
    return [
        {
            "n": n,
            "scheme": ch.scheme,
            "title": ch.title,
            "url": ch.url,
            "page": ch.page,
            "lang": ch.lang,
            "origin": "web" if ch.scheme == "web" else "library",
            "domain": urlparse(ch.url).hostname or "",
            "excerpt": ch.text,
            "score": round(score, 3),
            "terms": _highlight_terms(ch.text, q_terms),
        }
        for n, (ch, score) in enumerate(hits, start=1)
    ]


def _extractive(hits: list[tuple], lang: str) -> str:
    lead = (
        "मुझे उपलब्ध दस्तावेज़ों में ये प्रासंगिक अंश मिले:"
        if lang == "hi"
        else "Here are the most relevant passages from the official documents:"
    )
    lines = [lead]
    for n, (ch, _) in enumerate(hits, start=1):
        snippet = ch.text if len(ch.text) < 450 else ch.text[:450].rsplit(" ", 1)[0] + "…"
        lines.append(f"[{n}] {snippet}")
    return "\n\n".join(lines)


# Languages beyond English and Hindi. The question is translated to English, answered and verified
# against the documents there, then the answer is translated back. Needs an LLM key.
REGIONAL = {
    "bn": "Bengali", "mr": "Marathi", "ta": "Tamil", "te": "Telugu", "gu": "Gujarati", "pa": "Punjabi",
}
LONG_QUESTION_WORDS = 22  # a spoken story, not a question

NO_EVIDENCE = {
    "en": "I could not find reliable information about this in the documents I have. "
    "Please check the official government portal or visit your nearest Common Service Centre (CSC).",
    "hi": "मुझे उपलब्ध दस्तावेज़ों में इसकी भरोसेमंद जानकारी नहीं मिली। "
    "कृपया आधिकारिक सरकारी पोर्टल देखें या नज़दीकी कॉमन सर्विस सेंटर (CSC) जाएँ।",
}


_ALIASES: dict[str, list[str]] | None = None


def detect_scheme(text: str) -> str | None:
    """Return a scheme id if the text names exactly one scheme (by name or alias)."""
    global _ALIASES
    if _ALIASES is None:
        _ALIASES = {
            sid: [a.lower() for a in meta.get("aliases", [])]
            for sid, meta in eligibility.load_criteria().items()
        }
    low = text.lower()
    found = [sid for sid, names in _ALIASES.items() if any(n in low for n in names)]
    return found[0] if len(found) == 1 else None


def contextualize(question: str, history: list[str]) -> str:
    """Turn a follow-up ('what documents do I need?') into a standalone question."""
    history = [h.strip() for h in history if h and h.strip()][-3:]
    if not history:
        return question
    if llm.available():
        try:
            prompt = "Earlier questions:\n" + "\n".join(f"- {h}" for h in history)
            prompt += f"\n\nLatest question: {question}"
            out = llm.chat(
                [{"role": "system", "content": REWRITE_PROMPT}, {"role": "user", "content": prompt}],
                max_tokens=80,
            ).strip().strip('"')
            if 3 <= len(out) <= 400:
                return out
        except Exception:
            pass
    # No LLM (or it failed): short follow-ups borrow the previous question's words.
    if len(content_tokens(question)) < 4:
        return f"{history[-1]} {question}"
    return question


def _coverage_ok(hits: list[tuple], q_terms: set[str]) -> bool:
    """Evidence gate: the best passage must contain most of the question's content words."""
    if not hits:
        return False
    if not q_terms:
        return True
    best = max(
        len(q_terms & set(content_tokens(f"{c.title} {c.text}"))) / len(q_terms) for c, _ in hits
    )
    return best >= config.MIN_COVERAGE


def _web_hits(query: str, q_terms: set[str]) -> list[tuple]:
    """Passages from official web pages, for a question the verified library cannot answer."""
    chunks = web_search.search(query)
    if not chunks:
        return []
    hits = TfidfRetriever(chunks).search(query, k=config.TOP_K, min_score=0.03)
    return hits if _coverage_ok(hits, q_terms) else []


def answer_question(
    retriever: Retriever,
    question: str,
    lang: str | None = None,
    scheme: str | None = None,
    history: list[str] | None = None,
    web_gate: Callable[[], bool] | None = None,
) -> Answer:
    """web_gate: called only when the library has no answer; return True to allow a web search
    (used for rate limiting). None means the web fallback is never used."""
    if lang in REGIONAL:
        return _answer_regional(retriever, question, lang, scheme, history, web_gate)
    lang = lang or detect_language(question)
    standalone = contextualize(question, history or [])
    # If the question names a scheme, search only that scheme's documents.
    named = scheme or detect_scheme(standalone)
    min_score = 0.03 if named else None

    queries = [standalone]
    condensed = None
    if llm.available() and len(standalone.split()) >= LONG_QUESTION_WORDS:
        try:
            condensed = llm.condense_to_query(standalone).strip()
        except Exception:
            condensed = None
    if condensed:
        # Search with the short query only; the rambling original would fail the evidence gate.
        queries = [condensed]
        named = named or detect_scheme(condensed)
        min_score = 0.03 if named else None
    elif lang == "hi" and llm.available():
        try:
            queries.append(llm.rewrite_query_to_english(standalone))
        except Exception:
            pass

    merged: dict[str, tuple] = {}
    for q in queries:
        for ch, score in retriever.search(q, k=config.TOP_K, scheme=named, min_score=min_score):
            if ch.id not in merged or score > merged[ch.id][1]:
                merged[ch.id] = (ch, score)
    hits = sorted(merged.values(), key=lambda x: -x[1])[: config.TOP_K]

    q_terms = {t for t in content_tokens(" ".join(queries)) if not t.isdigit()}
    # (The gate is skipped for dense retrieval, where similarity already captures meaning.)
    if hits and config.RETRIEVER == "tfidf" and not _coverage_ok(hits, q_terms):
        hits = []

    origin = "library"
    warnings: list[str] = []

    # Web fallback: only when the verified library has nothing, and only if allowed.
    if not hits and not scheme and web_gate is not None and web_search.enabled() and web_gate():
        try:
            hits = _web_hits(queries[-1], q_terms)
        except Exception as e:
            warnings.append(f"Web search was unavailable ({type(e).__name__}).")
            hits = []
        if hits:
            origin = "web"
            warnings.append(
                "This answer comes from official web pages found just now, not from the verified "
                "library. Open the linked pages to confirm it."
            )

    if not hits:
        return Answer(
            NO_EVIDENCE[lang], [], ["No supporting source was found."] + warnings, "none", False,
            standalone=standalone,
        )

    if origin == "library":
        warnings += find_conflicts(hits)
    sources = _source_payload(hits, q_terms)
    top_scheme = hits[0][0].scheme if origin == "library" else None
    quote_check = {"level": "quote", "supported": len(hits), "weak": 0, "unsupported": 0,
                   "total": len(hits), "claims": []}

    def done(text, mode, grounded, verification):
        return Answer(text, sources, warnings, mode, grounded, verification, top_scheme, standalone, origin)

    if not llm.available():
        warnings.append("Running without an LLM: showing source passages instead of a written answer.")
        return done(_extractive(hits, lang), "extractive", True, quote_check)

    context = "\n\n".join(
        f"[{n}] ({ch.title}) {ch.text}" for n, (ch, _) in enumerate(hits, start=1)
    )
    language = "Hindi (Devanagari)" if lang == "hi" else "English"
    try:
        text = llm.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT.format(language=language)},
                {"role": "user", "content": f"SOURCES:\n{context}\n\nQUESTION: {standalone}"},
            ]
        )
    except Exception as e:  # network / quota: degrade gracefully
        warnings.append(f"LLM unavailable ({type(e).__name__}); showing source passages instead.")
        return done(_extractive(hits, lang), "extractive", True, quote_check)

    check = verify(text, sources)
    if should_reject(check):
        warnings.append(
            "The written answer could not be matched to its sources, so the source passages are shown instead."
        )
        return done(_extractive(hits, lang), "extractive", True, quote_check)

    if check["unsupported"] or check["weak"]:
        warnings.append(
            "Some statements are only partly backed by the sources. Check the highlighted sentences."
        )
    if check["total"] == 0 and not re.search(r"\[\d+\]", text):
        warnings.append("The answer did not cite a source; treat it with caution.")
    grounded = check["total"] > 0 and check["unsupported"] == 0
    return done(text, "llm", grounded, check)


def _answer_regional(retriever, question, lang, scheme, history, web_gate) -> Answer:
    name = REGIONAL[lang]
    if not llm.available():
        a = answer_question(retriever, question, "en", scheme, history, web_gate)
        a.warnings.insert(0, f"{name} answers need the language model, so this answer is shown in English.")
        return a
    try:
        english_q = llm.rewrite_query_to_english(question)
    except Exception:
        a = answer_question(retriever, question, "en", scheme, history, web_gate)
        a.warnings.insert(0, f"The question could not be translated from {name}, so this answer is in English.")
        return a

    a = answer_question(retriever, english_q, "en", scheme, history, web_gate)
    a.standalone = english_q
    try:
        translated = llm.translate(a.answer, name)
    except Exception:
        a.warnings.insert(0, f"The answer could not be translated into {name}, so it is shown in English.")
        return a
    a.answer_en, a.answer, a.translated_to = a.answer, translated, lang
    # The verifier compared the English text with the sources. Its sentence highlights do not map onto
    # the translation, so they are only shown on the English original.
    return a

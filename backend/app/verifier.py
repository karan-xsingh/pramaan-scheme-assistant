"""Grounding verifier: checks a written answer against the passages it cites.

For every sentence of the answer it asks:
  1. Does each [n] point to a source that exists?
  2. Does every number in the sentence appear in the cited passage(s)?
  3. Do enough of the sentence's content words appear in the cited passage(s)?

It is a lexical check, not a proof of truth: it catches invented numbers, invented
citations and sentences that have nothing to do with their source. It cannot catch
a sentence that reuses the source's words but reverses its meaning.
"""
from __future__ import annotations

import re

from .retriever import content_tokens

CITE = re.compile(r"\[(\d+)\]")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
DEV = re.compile(r"[ऀ-ॿ]")
LIST_MARK = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Abbreviations that must not end a sentence. Replacement keeps string length equal
# so character offsets stay valid for the original text.
ABBREV = ("Rs.", "No.", "Sr.", "approx.", "e.g.", "i.e.", "etc.", "Dr.", "vs.")

# Sentences that are reminders or "not found" statements carry no checkable fact.
BOILERPLATE = re.compile(
    r"(confirm|verify|check)\b.*\b(official|website|portal|csc|common service)"
    r"|(could not|couldn.t|cannot|can.t|unable to) find"
    r"|not (?:available|mentioned|specified|covered) in"
    r"|आधिकारिक.*(पुष्टि|जाँच|जांच)|नहीं मिली|नहीं मिला",
    re.I,
)

CHECKED = ("supported", "weak", "unsupported")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    masked = text
    for ab in ABBREV:
        masked = masked.replace(ab, ab[:-1] + "\x00")
    spans, pos = [], 0
    for m in re.finditer(r"(?<=[.!?।])\s+|\n+", masked):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def numbers(text: str) -> set[float]:
    text = LIST_MARK.sub("", CITE.sub("", text)).translate(DEV_DIGITS)
    out = set()
    for raw in NUM.findall(text):
        try:
            out.add(float(raw.replace(",", "")))
        except ValueError:
            pass
    return out


def _terms(text: str) -> set[str]:
    return {t for t in content_tokens(CITE.sub("", text)) if not t.isdigit()}


def _overlap(
    sentence_terms: set[str], passage_terms: set[str], passage_text: str
) -> tuple[float | None, set[str]]:
    """Share of the sentence's words found in the passage, and the words compared.

    Ratio is None when the two cannot be compared (too few words, or Hindi vs English).
    """
    if any(DEV.search(t) for t in sentence_terms) and not DEV.search(passage_text):
        # Hindi sentence, English passage: words cannot be compared across scripts.
        sentence_terms = {t for t in sentence_terms if not DEV.search(t)}
    if len(sentence_terms) < 2:
        return None, sentence_terms
    return len(sentence_terms & passage_terms) / len(sentence_terms), sentence_terms


def verify(answer: str, sources: list[dict]) -> dict:
    by_n = {s["n"]: s["excerpt"] for s in sources}
    all_text = " ".join(by_n.values())
    all_nums = numbers(all_text)
    all_terms = _terms(all_text)

    claims = []
    for start, end in sentence_spans(answer):
        raw = answer[start:end]
        cites = [int(n) for n in CITE.findall(raw)]
        valid = list(dict.fromkeys(c for c in cites if c in by_n))
        bad = [c for c in cites if c not in by_n]
        nums = numbers(raw)
        terms = _terms(raw)
        status, reason = "unchecked", ""

        if bad:
            status, reason = "unsupported", f"Cites source {bad[0]}, which does not exist."
        elif BOILERPLATE.search(raw) and not nums:
            status, reason = "unchecked", "Reminder or not-found statement."
        elif valid:
            p_text = " ".join(by_n[c] for c in valid)
            missing = nums - numbers(p_text)
            if missing:
                if missing <= all_nums:
                    status, reason = "weak", "The number appears in a different source than the one cited."
                else:
                    status, reason = "unsupported", "A number in this sentence is not in any source."
            else:
                ratio, compared = _overlap(terms, _terms(p_text), p_text)
                novel = compared - all_terms  # words that appear in no retrieved source
                if ratio is None:
                    status = "supported" if nums else "unchecked"
                    reason = "Numbers match the cited source." if nums else "Too short to compare."
                elif ratio >= 0.5 and len(novel) / len(compared) >= 0.5:
                    status, reason = "weak", "Contains words that appear in no source."
                elif ratio >= 0.5:
                    status, reason = "supported", "Matches the cited source."
                elif ratio >= 0.3:
                    status, reason = "weak", "Only partly matches the cited source."
                else:
                    status, reason = "unsupported", "Little overlap with the cited source."
        elif nums:
            if nums <= all_nums:
                status, reason = "weak", "No citation, but the numbers appear in the sources."
            else:
                status, reason = "unsupported", "No citation and a number not found in any source."

        claims.append(
            {"start": start, "end": end, "status": status, "sources": valid, "reason": reason}
        )

    checked = [c for c in claims if c["status"] in CHECKED]
    sup = sum(c["status"] == "supported" for c in checked)
    weak = sum(c["status"] == "weak" for c in checked)
    uns = sum(c["status"] == "unsupported" for c in checked)
    total = len(checked)

    if total == 0:
        level = "unchecked"
    elif uns == 0 and weak == 0:
        level = "high"
    elif uns / total >= 0.34:
        level = "low"
    else:
        level = "medium"

    return {
        "level": level,
        "supported": sup,
        "weak": weak,
        "unsupported": uns,
        "total": total,
        "claims": claims,
    }


def should_reject(v: dict) -> bool:
    """True when the written answer is too poorly supported to show."""
    return v["total"] > 0 and v["unsupported"] / v["total"] >= 0.5

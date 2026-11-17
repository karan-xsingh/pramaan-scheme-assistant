import time

import pytest

from app import eligibility, rag
from app.ingest import chunk_words
from app.ratelimit import RateLimiter
from app.retriever import TfidfRetriever


@pytest.fixture(scope="module")
def retriever():
    return TfidfRetriever()


# ---------- chunking ----------
def test_chunking_respects_size_and_drops_tiny_pieces():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 40 for i in range(6))
    chunks = chunk_words(text, size=100, overlap=10)
    assert len(chunks) >= 2
    assert all(len(c.split()) <= 120 for c in chunks)
    assert chunk_words("too short", 100, 10) == []


# ---------- eligibility ----------
def test_eligibility_never_decides_and_reports_each_condition():
    out = eligibility.check("apy", {"age": 45, "has_bank_account": True})
    status = {r["id"]: r["status"] for r in out["rows"]}
    assert status == {"age": "does_not_appear_to_match", "bank": "appears_to_match", "tax": "cannot_tell"}
    assert "not an official eligibility decision" in out["disclaimer"].lower()


def test_eligibility_all_match():
    out = eligibility.check("ssy", {"gender": "female", "age": 6})
    assert {r["status"] for r in out["rows"]} == {"appears_to_match"}


def test_eligibility_unknown_scheme():
    with pytest.raises(KeyError):
        eligibility.check("nope", {})


# ---------- retrieval ----------
def test_scheme_name_restricts_retrieval(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    a = rag.answer_question(retriever, "Can I apply directly for PMAY-G?")
    assert a.sources and {s["scheme"] for s in a.sources} == {"pmay-g"}


def test_out_of_scope_question_is_refused(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    a = rag.answer_question(retriever, "How do I get a passport renewed?")
    assert a.mode == "none" and a.sources == []


def test_conflicting_amounts_raise_warning(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    a = rag.answer_question(retriever, "What is the financial support per connection under Ujjwala?")
    assert any("conflict" in w.lower() for w in a.warnings)


def test_hindi_question_finds_hindi_document(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    a = rag.answer_question(retriever, "पीएम किसान में साल में कितने रुपये मिलते हैं?")
    assert any("6,000" in s["excerpt"] for s in a.sources)


def test_followup_without_llm_borrows_previous_question(monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    q = rag.contextualize("what documents are needed?", ["How much does PM-KISAN pay?"])
    assert "PM-KISAN" in q


# ---------- LLM path with a fake model ----------
def test_llm_answer_is_verified_and_bad_answer_falls_back(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: True)

    monkeypatch.setattr("app.llm.chat", lambda *a, **k: "PM-KISAN pays Rs. 6,000 per year to farmer families [1].")
    good = rag.answer_question(retriever, "How much does PM-KISAN pay each year?")
    assert good.mode == "llm" and good.verification["level"] == "high"

    monkeypatch.setattr("app.llm.chat", lambda *a, **k: "PM-KISAN pays Rs. 99,000 per year [1]. It also gives a car [1].")
    bad = rag.answer_question(retriever, "How much does PM-KISAN pay each year?")
    assert bad.mode == "extractive"
    assert any("could not be matched" in w for w in bad.warnings)


def test_llm_failure_degrades_to_passages(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: True)

    def boom(*a, **k):
        raise TimeoutError

    monkeypatch.setattr("app.llm.chat", boom)
    a = rag.answer_question(retriever, "How much does PM-KISAN pay each year?")
    assert a.mode == "extractive" and a.sources


# ---------- rate limiter ----------
def test_rate_limiter_blocks_then_recovers():
    rl = RateLimiter(limit=2, window=60)
    assert rl.check("a", now=0) == 0
    assert rl.check("a", now=1) == 0
    assert rl.check("a", now=2) > 0
    assert rl.check("b", now=2) == 0  # other clients unaffected
    assert rl.check("a", now=61) == 0  # window passed

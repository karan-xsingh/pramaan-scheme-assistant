import pytest

from app import rag
from app.retriever import TfidfRetriever


@pytest.fixture(scope="module")
def retriever():
    return TfidfRetriever()


def fake_llm(monkeypatch, replies):
    monkeypatch.setattr("app.llm.available", lambda: True)
    monkeypatch.setattr("app.llm.rewrite_query_to_english", lambda q: "How much does PM-KISAN pay each year?")
    monkeypatch.setattr("app.llm.translate", lambda text, language: f"[{language}] " + text)
    monkeypatch.setattr("app.llm.chat", lambda *a, **k: replies)


def test_regional_answer_is_verified_in_english_then_translated(retriever, monkeypatch):
    fake_llm(monkeypatch, "PM-KISAN pays Rs. 6,000 per year to farmer families [1].")
    a = rag.answer_question(retriever, "பிஎம் கிசான் ஆண்டுக்கு எவ்வளவு?", "ta")
    assert a.translated_to == "ta" and a.answer.startswith("[Tamil]")
    assert a.answer_en.startswith("PM-KISAN pays") and a.verification["level"] in {"high", "medium"}
    assert a.sources and a.standalone.startswith("How much")


def test_regional_without_llm_falls_back_to_english(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    a = rag.answer_question(retriever, "How much does PM-KISAN pay each year?", "mr")
    assert a.translated_to is None and "Marathi" in a.warnings[0]


def test_translation_failure_keeps_english_answer(retriever, monkeypatch):
    fake_llm(monkeypatch, "PM-KISAN pays Rs. 6,000 per year to farmer families [1].")
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.llm.translate", boom)
    a = rag.answer_question(retriever, "x", "bn")
    assert a.translated_to is None and a.answer.startswith("PM-KISAN") and "Bengali" in a.warnings[0]


def test_long_spoken_story_is_condensed_before_search(retriever, monkeypatch):
    seen = {}
    monkeypatch.setattr("app.llm.available", lambda: True)
    def condense(story):
        seen["story"] = story
        return "PM-KISAN benefit per year"
    monkeypatch.setattr("app.llm.condense_to_query", condense)
    monkeypatch.setattr("app.llm.chat", lambda *a, **k: "PM-KISAN pays Rs. 6,000 per year to farmer families [1].")
    story = ("I am a small farmer with two acres of land near Dehradun and my crops failed this year so I am "
             "worried about money and my neighbour told me that the government gives some yearly payment to "
             "farmers, how much does PM-KISAN give me")
    a = rag.answer_question(retriever, story, "en")
    assert seen["story"] == story and a.mode == "llm" and a.sources
    assert {s["scheme"] for s in a.sources} == {"pm-kisan"}

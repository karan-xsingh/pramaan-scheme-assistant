import json

import pytest
from fastapi.testclient import TestClient

from app import config, ratelimit
from app.main import app
from app.ratelimit import RateLimiter


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    monkeypatch.setattr(ratelimit, "limiter", RateLimiter(1000))
    return TestClient(app)


def test_health_and_schemes(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["chunks"] > 0
    names = {s["id"]: s for s in client.get("/api/schemes").json()}
    assert {"pm-kisan", "pm-jay", "apy"} <= set(names)
    assert names["apy"]["has_checklist"] is True


def test_ask_returns_sources_and_quote_verification(client):
    r = client.post("/api/ask", json={"question": "How much does PM-KISAN pay each year?"}).json()
    assert r["sources"] and r["mode"] == "extractive"
    assert r["verification"]["level"] == "quote"
    assert r["top_scheme"] == "pm-kisan"
    assert r["latency_ms"] >= 0
    assert r["sources"][0]["terms"]


def test_ask_rejects_bad_input(client):
    assert client.post("/api/ask", json={"question": "x"}).status_code == 422
    assert client.post("/api/ask", json={"question": "ok question", "history": ["a"] * 9}).status_code == 422


def test_compare_and_unknown_scheme(client):
    ok = client.post("/api/compare", json={"schemes": ["pm-kisan", "pm-jay"]})
    assert ok.status_code == 200 and len(ok.json()["schemes"]) == 2
    assert client.post("/api/compare", json={"schemes": ["pm-kisan", "nope"]}).status_code == 404


def test_eligibility_endpoint(client):
    r = client.post("/api/eligibility", json={"scheme": "apy", "profile": {"age": 30}})
    assert r.status_code == 200 and r.json()["rows"]
    assert client.post("/api/eligibility", json={"scheme": "zzz", "profile": {}}).status_code == 404


def test_rate_limit_returns_429_with_retry_after(monkeypatch, client):
    monkeypatch.setattr(ratelimit, "limiter", RateLimiter(2))
    for _ in range(2):
        assert client.post("/api/ask", json={"question": "How much does PM-KISAN pay?"}).status_code == 200
    r = client.post("/api/ask", json={"question": "How much does PM-KISAN pay?"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_feedback_is_written_without_personal_data(client, monkeypatch, tmp_path):
    path = tmp_path / "fb.jsonl"
    monkeypatch.setattr(config, "FEEDBACK_FILE", path)
    r = client.post("/api/feedback", json={"question": "q?", "answer": "a", "rating": "up"})
    assert r.json() == {"ok": True}
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["rating"] == "up" and set(row) >= {"time", "question", "answer"}
    assert not {"ip", "user"} & set(row)
    assert client.post("/api/feedback", json={"question": "q", "answer": "a", "rating": "meh"}).status_code == 422


def test_evaluation_endpoint(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EVAL_RESULTS", tmp_path / "missing.json")
    assert client.get("/api/evaluation").status_code == 404
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"metrics": {}, "rows": []}))
    monkeypatch.setattr(config, "EVAL_RESULTS", f)
    assert client.get("/api/evaluation").status_code == 200

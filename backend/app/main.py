from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import compare as compare_mod
from . import config, eligibility, llm, rag, web_search
from .ratelimit import RateLimiter, client_key, rate_limit
from .retriever import get_retriever

app = FastAPI(title="Scheme Assistant API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = get_retriever()
_feedback_lock = threading.Lock()
# Web searches cost money and are slow, so they get a stricter limit of their own.
web_limiter = RateLimiter(max(config.WEB_RATE_LIMIT_PER_MIN, 1))


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    lang: Literal["en", "hi", "bn", "mr", "ta", "te", "gu", "pa"] | None = None
    scheme: str | None = None
    history: list[str] = Field(default_factory=list, max_length=4)  # earlier questions


class CompareRequest(BaseModel):
    schemes: list[str] = Field(min_length=2, max_length=3)


class EligibilityRequest(BaseModel):
    scheme: str
    profile: dict[str, Any]


class FeedbackRequest(BaseModel):
    question: str = Field(max_length=1000)
    answer: str = Field(max_length=4000)
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=500)
    mode: str | None = Field(default=None, max_length=30)
    level: str | None = Field(default=None, max_length=30)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "retriever": config.RETRIEVER,
        "llm_enabled": llm.available(),
        "chunks": len(retriever.chunks),
        "schemes": len(retriever.schemes()),
        "web_search": web_search.enabled(),
    }


@app.get("/api/schemes")
def list_schemes():
    criteria = eligibility.load_criteria()
    info = retriever.schemes()
    return [
        {
            "id": sid,
            "name": criteria.get(sid, {}).get("name", sid),
            "documents": info[sid]["titles"],
            "urls": info[sid]["urls"],
            "has_checklist": bool(criteria.get(sid, {}).get("criteria")),
        }
        for sid in sorted(info)
    ]


@app.post("/api/ask", dependencies=[Depends(rate_limit)])
def ask(req: AskRequest, request: Request):
    t0 = time.perf_counter()
    key = client_key(request)
    web_gate = lambda: config.WEB_RATE_LIMIT_PER_MIN <= 0 or web_limiter.check(key) == 0
    a = rag.answer_question(retriever, req.question, req.lang, req.scheme, req.history, web_gate)
    return {
        "answer": a.answer,
        "sources": a.sources,
        "warnings": a.warnings,
        "mode": a.mode,
        "grounded": a.grounded,
        "verification": a.verification,
        "top_scheme": a.top_scheme,
        "origin": a.origin,
        "translated_to": a.translated_to,
        "answer_en": a.answer_en,
        "standalone_question": a.standalone,
        "latency_ms": round((time.perf_counter() - t0) * 1000),
    }


@app.post("/api/compare")
def compare(req: CompareRequest):
    known = set(retriever.schemes())
    bad = [s for s in req.schemes if s not in known]
    if bad:
        raise HTTPException(404, f"Unknown scheme(s): {', '.join(bad)}")
    return compare_mod.compare(retriever, req.schemes)


@app.post("/api/eligibility")
def eligibility_check(req: EligibilityRequest):
    try:
        return eligibility.check(req.scheme, req.profile)
    except KeyError:
        raise HTTPException(404, f"No checklist for scheme '{req.scheme}'")


@app.post("/api/feedback", dependencies=[Depends(rate_limit)])
def feedback(req: FeedbackRequest):
    """Append a thumbs up/down to data/feedback.jsonl. No IP or user id is stored."""
    row = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **req.model_dump()}
    config.FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _feedback_lock, config.FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.get("/api/evaluation")
def evaluation():
    """Latest results written by `python -m eval.evaluate`."""
    if not config.EVAL_RESULTS.exists():
        raise HTTPException(404, "No evaluation results yet. Run: python -m eval.evaluate")
    return json.loads(config.EVAL_RESULTS.read_text(encoding="utf-8"))

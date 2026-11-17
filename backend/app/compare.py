"""Side-by-side scheme comparison built from retrieved passages (no LLM needed)."""
from __future__ import annotations

from .retriever import Retriever

ASPECTS = {
    "benefit": "benefit amount assistance provided",
    "eligibility": "who is eligible eligibility criteria exclusions",
    "documents": "documents required Aadhaar bank account",
    "how_to_apply": "how to apply registration procedure portal",
}


def compare(retriever: Retriever, scheme_ids: list[str]) -> dict:
    result = {"aspects": list(ASPECTS), "schemes": []}
    for sid in scheme_ids:
        entry = {"scheme": sid, "aspects": {}}
        for aspect, q in ASPECTS.items():
            hits = retriever.search(f"{sid} {q}", k=1, scheme=sid, min_score=0.0)
            entry["aspects"][aspect] = (
                {
                    "text": hits[0][0].text,
                    "title": hits[0][0].title,
                    "url": hits[0][0].url,
                    "page": hits[0][0].page,
                }
                if hits
                else None
            )
        result["schemes"].append(entry)
    return result

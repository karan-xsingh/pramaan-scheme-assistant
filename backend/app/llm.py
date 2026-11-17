"""Thin client for any OpenAI-compatible chat endpoint (Groq by default)."""
from __future__ import annotations

import httpx

from . import config


def available() -> bool:
    return bool(config.LLM_API_KEY)


def chat(messages: list[dict], temperature: float = 0.1, max_tokens: int = 700) -> str:
    resp = httpx.post(
        f"{config.LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        json={
            "model": config.LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=40,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def rewrite_query_to_english(query: str) -> str:
    """Used for Hindi / Hinglish questions so English documents can be matched."""
    return chat(
        [
            {
                "role": "system",
                "content": "Translate the user's question about Indian government schemes into "
                "a short English search query. Keep scheme names. Output only the query.",
            },
            {"role": "user", "content": query},
        ],
        max_tokens=60,
    )


def condense_to_query(story: str) -> str:
    """A person who speaks their whole situation gets a short English search query out of it."""
    return chat(
        [
            {
                "role": "system",
                "content": "The user describes their situation and needs in their own words (any Indian "
                "language). Reply with ONE short English search query (at most 15 words) naming the "
                "government benefit, scheme or service they are asking about. Keep scheme names. "
                "Do not add facts that are not in the text. Output only the query.",
            },
            {"role": "user", "content": story},
        ],
        max_tokens=60,
    )


def translate(text: str, language: str) -> str:
    """Translate into `language`. Keeps [1]-style source markers, numbers and scheme names unchanged."""
    return chat(
        [
            {
                "role": "system",
                "content": f"Translate the user's text into {language}. Keep every [n] source marker, every "
                "number and amount, and scheme names exactly as they are. Use simple everyday words. "
                "Do not add or remove information. Output only the translation.",
            },
            {"role": "user", "content": text},
        ],
        max_tokens=900,
    )

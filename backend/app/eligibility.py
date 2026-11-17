"""Rule-based eligibility *checklist*.

It compares details the user typed with criteria transcribed from published
guidelines. It never decides eligibility; each row is "appears to match",
"does not appear to match" or "cannot tell".
"""
from __future__ import annotations

import json
from typing import Any

from . import config

SCHEMES_FILE = config.BASE_DIR / "data" / "schemes.json"

MATCH, NO_MATCH, UNKNOWN = "appears_to_match", "does_not_appear_to_match", "cannot_tell"


def load_criteria() -> dict[str, dict]:
    data = json.loads(SCHEMES_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _eval(crit: dict, profile: dict[str, Any]) -> str:
    field, op, val = crit["field"], crit["op"], crit.get("value")
    v = profile.get(field)

    if op == "gte_or_flag":  # e.g. age >= 70 OR a boolean flag is true
        flag = profile.get(crit.get("flag", ""))
        if (v is not None and v >= val) or flag is True:
            return MATCH
        if v is None and flag is None:
            return UNKNOWN
        return NO_MATCH

    if v is None:
        return UNKNOWN
    try:
        if op == "eq":
            return MATCH if v == val else NO_MATCH
        if op == "gte":
            return MATCH if v >= val else NO_MATCH
        if op == "lt":
            return MATCH if v < val else NO_MATCH
        if op == "between":
            return MATCH if val[0] <= v <= val[1] else NO_MATCH
    except TypeError:
        return UNKNOWN
    return UNKNOWN


def check(scheme_id: str, profile: dict[str, Any]) -> dict:
    schemes = load_criteria()
    if scheme_id not in schemes or not schemes[scheme_id].get("criteria"):
        raise KeyError(scheme_id)
    s = schemes[scheme_id]
    rows = [
        {"id": c["id"], "criterion": c["text"], "status": _eval(c, profile)}
        for c in s["criteria"]
    ]
    statuses = {r["status"] for r in rows}
    if NO_MATCH in statuses:
        summary = "Some published conditions do not appear to match the details you entered."
    elif UNKNOWN in statuses:
        summary = "No mismatch found yet, but some details are missing."
    else:
        summary = "The details you entered appear to match the published conditions."
    return {
        "scheme": scheme_id,
        "name": s["name"],
        "rows": rows,
        "summary": summary,
        "disclaimer": "This is not an official eligibility decision. Confirm with the official "
        "portal or your nearest Common Service Centre before applying.",
    }

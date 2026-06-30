"""Confidence scoring.

We compute a per-field confidence score from source priority and corroboration,
then a weighted overall_confidence. Honest defaults: empty field = 0 contribution."""
from __future__ import annotations

from typing import Any

from .merge import SOURCE_PRIORITY

# Field weight in overall confidence (sum need not be 1; we normalize).
FIELD_WEIGHTS: dict[str, float] = {
    "full_name": 1.0,
    "emails": 1.0,
    "phones": 0.7,
    "location": 0.5,
    "headline": 0.4,
    "skills": 0.8,
    "experience": 0.8,
    "education": 0.5,
}

# Base score for top-priority single source. Corroboration boosts.
_BASE_SCORE = {5: 0.9, 4: 0.85, 3: 0.7, 2: 0.55, 1: 0.4, 0: 0.3}


def _field_score(rec: dict[str, Any], field: str) -> float:
    sources = {pv["source"] for pv in rec.get("provenance", []) if pv["field"].startswith(field)}
    if not sources:
        return 0.0
    pris = sorted({SOURCE_PRIORITY.get(s, 0) for s in sources}, reverse=True)
    score = _BASE_SCORE.get(pris[0], 0.3)
    # Each extra source raises score with diminishing returns.
    for _ in pris[1:]:
        score = 1 - (1 - score) * 0.6
    return min(score, 0.99)


def attach_confidence(rec: dict[str, Any]) -> dict[str, Any]:
    """Mutates and returns rec with overall_confidence populated.

    Coverage matters: the denominator is the sum of weights for ALL canonical
    fields, so a record with only 1 of 8 fields populated scores low (honest).
    Empty fields contribute 0 to the numerator, full weight to the denominator.
    """
    total_w = 0.0
    total = 0.0
    for field, w in FIELD_WEIGHTS.items():
        total_w += w  # always count the weight for coverage
        val = rec.get(field)
        if val in (None, "", [], {}):
            continue
        if field == "location" and not any((val.get("city"), val.get("region"), val.get("country"))):
            continue
        s = _field_score(rec, field)
        total += s * w
    rec["overall_confidence"] = round(total / total_w, 3) if total_w else 0.0
    return rec

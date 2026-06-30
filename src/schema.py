"""Canonical schema + JSON Schema for validation."""
from typing import Any

# Default canonical schema for a candidate profile.
DEFAULT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CanonicalCandidate",
    "type": "object",
    "required": [
        "candidate_id", "full_name", "emails", "phones", "location",
        "links", "skills", "experience", "education", "provenance",
        "overall_confidence",
    ],
    "properties": {
        "candidate_id": {"type": "string"},
        "full_name": {"type": "string"},
        "emails": {"type": "array", "items": {"type": "string"}},
        "phones": {"type": "array", "items": {"type": "string"}},
        "location": {
            "type": "object",
            "properties": {
                "city": {"type": ["string", "null"]},
                "region": {"type": ["string", "null"]},
                "country": {"type": ["string", "null"]},
            },
        },
        "links": {
            "type": "object",
            "properties": {
                "linkedin": {"type": ["string", "null"]},
                "github": {"type": ["string", "null"]},
                "portfolio": {"type": ["string", "null"]},
                "other": {"type": "array", "items": {"type": "string"}},
            },
        },
        "headline": {"type": ["string", "null"]},
        "years_experience": {"type": ["number", "null"]},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "confidence", "sources"],
                "properties": {
                    "name": {"type": "string"},
                    "confidence": {"type": "number"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": ["string", "null"]},
                    "title": {"type": ["string", "null"]},
                    "start": {"type": ["string", "null"]},
                    "end": {"type": ["string", "null"]},
                    "summary": {"type": ["string", "null"]},
                },
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": ["string", "null"]},
                    "degree": {"type": ["string", "null"]},
                    "field": {"type": ["string", "null"]},
                    "end_year": {"type": ["integer", "null"]},
                },
            },
        },
        "provenance": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["field", "source", "method"],
                "properties": {
                    "field": {"type": "string"},
                    "source": {"type": "string"},
                    "method": {"type": "string"},
                },
            },
        },
        "overall_confidence": {"type": "number"},
    },
}


def empty_profile(candidate_id: str = "") -> dict[str, Any]:
    """Return a fresh profile with safe defaults (no invented values)."""
    return {
        "candidate_id": candidate_id,
        "full_name": "",
        "emails": [],
        "phones": [],
        "location": {"city": None, "region": None, "country": None},
        "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
        "headline": None,
        "years_experience": None,
        "skills": [],
        "experience": [],
        "education": [],
        "provenance": [],
        "overall_confidence": 0.0,
    }

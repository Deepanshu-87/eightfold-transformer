"""Recruiter free-text notes (.txt). One file = one candidate (filename
without extension is used as a hint key). Extracts emails, phones, and
mentioned skills via dictionary lookup."""
from __future__ import annotations

import os
import re
from typing import Any

from ..normalize import (
    extract_emails, extract_phones, normalize_skill,
)
from ..schema import empty_profile

SOURCE = "recruiter_notes"

# Hint phrases preceding a name e.g. "Candidate: Jane Doe", "Name - Jane Doe"
_NAME_HINT = re.compile(
    r"(?:^|\n)\s*(?:candidate|name)\s*[:\-]\s*(?P<n>[A-Z][a-zA-Z'.\- ]{1,60})",
    re.I,
)

# Skills we will look for as whole-word matches (case-insensitive).
_SKILL_VOCAB = {
    "python", "javascript", "typescript", "react", "node", "node.js",
    "go", "golang", "rust", "java", "c++", "c#", "ruby", "rails",
    "django", "flask", "fastapi", "kubernetes", "k8s", "docker",
    "aws", "gcp", "azure", "postgresql", "postgres", "mysql",
    "mongodb", "redis", "kafka", "spark", "graphql", "rest",
    "tensorflow", "pytorch", "pandas", "numpy", "sklearn",
    "scikit-learn", "machine learning", "deep learning",
    "nlp", "ai", "sql", "git", "linux", "ci/cd", "terraform",
}


def _find_skills(text: str) -> list[str]:
    found = []
    low = text.lower()
    for kw in _SKILL_VOCAB:
        # Word-boundary match; allow + and . in tokens like c++, node.js.
        pat = r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])"
        if re.search(pat, low):
            n = normalize_skill(kw)
            if n and n not in found:
                found.append(n)
    return found


def extract_one(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    prof = empty_profile()
    prov = []

    m = _NAME_HINT.search(text)
    if m:
        prof["full_name"] = m.group("n").strip()
        prov.append({"field": "full_name", "source": SOURCE, "method": "notes_hint"})

    emails = extract_emails(text)
    if emails:
        prof["emails"] = emails
        prov.append({"field": "emails", "source": SOURCE, "method": "regex_email"})

    phones = extract_phones(text)
    if phones:
        prof["phones"] = phones
        prov.append({"field": "phones", "source": SOURCE, "method": "regex_phone_e164"})

    skills = []
    for n in _find_skills(text):
        # Recruiter notes are noisy → lower confidence.
        skills.append({"name": n, "confidence": 0.55, "sources": [SOURCE]})
    if skills:
        prof["skills"] = skills
        prov.append({"field": "skills", "source": SOURCE, "method": "vocab_match"})

    cid = emails[0] if emails else os.path.splitext(os.path.basename(path))[0]
    prof["candidate_id"] = f"{SOURCE}:{cid}"
    prof["provenance"] = prov
    return prof


def extract(path: str) -> list[dict[str, Any]]:
    if os.path.isdir(path):
        out = []
        for fn in sorted(os.listdir(path)):
            if fn.lower().endswith(".txt"):
                out.append(extract_one(os.path.join(path, fn)))
        return out
    if os.path.isfile(path):
        return [extract_one(path)]
    return []

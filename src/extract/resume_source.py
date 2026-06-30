"""Resume text files → partial profile per file.

Lightweight rules-based extraction; assumes plain-text resumes
(produced from PDF/DOCX upstream). Reads .txt files."""
from __future__ import annotations

import os
import re
from typing import Any

from ..normalize import (
    extract_emails, extract_phones, normalize_country, normalize_date,
    normalize_skill,
)
from ..schema import empty_profile

SOURCE = "resume"

# Top of the resume usually has the name on the first non-empty line.
_NAME_BAD = re.compile(r"@|\d|http|linkedin|github|resume|curriculum", re.I)

_SECTIONS = [
    "experience", "work experience", "professional experience",
    "education", "skills", "summary", "objective", "projects",
]


def _split_sections(text: str) -> dict[str, str]:
    """Roughly slice resume by headers. Returns lowercase header -> body."""
    lines = text.splitlines()
    sec: dict[str, list[str]] = {"_top": []}
    cur = "_top"
    for ln in lines:
        s = ln.strip().lower().rstrip(":")
        if s in _SECTIONS:
            cur = s
            sec.setdefault(cur, [])
            continue
        sec.setdefault(cur, []).append(ln)
    return {k: "\n".join(v).strip() for k, v in sec.items()}


def _guess_name(top: str) -> str | None:
    for ln in top.splitlines():
        s = ln.strip()
        if not s:
            continue
        if _NAME_BAD.search(s):
            continue
        words = s.split()
        if 1 < len(words) <= 5 and all(w[0].isupper() for w in words if w[0].isalpha()):
            return s
    return None


def _extract_skills(skills_block: str) -> list[str]:
    if not skills_block:
        return []
    raw = re.split(r"[,\n•·\u2022;|]", skills_block)
    return [r.strip() for r in raw if r.strip() and len(r.strip()) < 40]


_EXP_LINE = re.compile(
    r"^(?P<title>[^|@\-]+?)\s*[\|@\-]\s*(?P<company>[^|@\-]+?)\s*[\|@\-]\s*"
    r"(?P<start>[A-Za-z0-9 ,/.\-]+?)\s*[-–to]+\s*(?P<end>[A-Za-z0-9 ,/.\-]+)$",
    re.I,
)


def _extract_experience(block: str) -> list[dict[str, Any]]:
    out = []
    for ln in block.splitlines():
        m = _EXP_LINE.match(ln.strip())
        if not m:
            continue
        out.append({
            "company": m.group("company").strip() or None,
            "title": m.group("title").strip() or None,
            "start": normalize_date(m.group("start").strip()),
            "end": normalize_date(m.group("end").strip()),
            "summary": None,
        })
    return out


_EDU_LINE = re.compile(
    r"^(?P<degree>[^,|]+),\s*(?P<field>[^,|]+?)\s*[-–,|]\s*"
    r"(?P<inst>[^,|]+?)(?:\s*[-–,|]\s*(?P<year>\d{4}))?$",
    re.I,
)


def _extract_education(block: str) -> list[dict[str, Any]]:
    out = []
    for ln in block.splitlines():
        m = _EDU_LINE.match(ln.strip())
        if not m:
            continue
        yr = m.group("year")
        out.append({
            "institution": m.group("inst").strip() or None,
            "degree": m.group("degree").strip() or None,
            "field": m.group("field").strip() or None,
            "end_year": int(yr) if yr else None,
        })
    return out


def extract_one(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    prof = empty_profile()
    prov = []
    sec = _split_sections(text)
    name = _guess_name(sec.get("_top", ""))
    if name:
        prof["full_name"] = name
        prov.append({"field": "full_name", "source": SOURCE, "method": "resume_header"})

    emails = extract_emails(text)
    if emails:
        prof["emails"] = emails
        prov.append({"field": "emails", "source": SOURCE, "method": "regex_email"})

    phones = extract_phones(text)
    if phones:
        prof["phones"] = phones
        prov.append({"field": "phones", "source": SOURCE, "method": "regex_phone_e164"})

    # Country guess from top block.
    for tok in re.split(r"[,\n]", sec.get("_top", "")):
        c = normalize_country(tok.strip())
        if c:
            prof["location"]["country"] = c
            prov.append({"field": "location.country", "source": SOURCE, "method": "resume_header"})
            break

    skills_raw = _extract_skills(sec.get("skills", ""))
    skills = []
    for s in skills_raw:
        n = normalize_skill(s)
        if n and not any(sk["name"].lower() == n.lower() for sk in skills):
            skills.append({"name": n, "confidence": 0.7, "sources": [SOURCE]})
    if skills:
        prof["skills"] = skills
        prov.append({"field": "skills", "source": SOURCE, "method": "resume_skills_section"})

    exp_block = sec.get("experience") or sec.get("work experience") or sec.get("professional experience") or ""
    exp = _extract_experience(exp_block)
    if exp:
        prof["experience"] = exp
        prov.append({"field": "experience", "source": SOURCE, "method": "resume_lines"})

    edu = _extract_education(sec.get("education", ""))
    if edu:
        prof["education"] = edu
        prov.append({"field": "education", "source": SOURCE, "method": "resume_lines"})

    # candidate_id: prefer first email; else file stem
    cid = emails[0] if emails else os.path.splitext(os.path.basename(path))[0]
    prof["candidate_id"] = f"{SOURCE}:{cid}"
    prof["provenance"] = prov
    return prof


def extract(path: str) -> list[dict[str, Any]]:
    """Path may be a directory of .txt resumes or a single .txt file."""
    if os.path.isdir(path):
        out = []
        for fn in sorted(os.listdir(path)):
            if fn.lower().endswith((".txt", ".md")):
                out.append(extract_one(os.path.join(path, fn)))
        return out
    if os.path.isfile(path):
        return [extract_one(path)]
    return []

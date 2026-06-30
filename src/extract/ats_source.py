"""ATS JSON → partial profiles.

ATS uses its own field names that don't match ours. Common shape:
{
  "candidates": [
    {"id":"...", "personal":{"firstName":"...","lastName":"...","emailAddr":"...",
        "mobile":"...", "country":"...", "city":"..."},
     "professional":{"headline":"...","yearsOfExp":3,
        "positions":[{"org":"...","role":"...","from":"...","to":"...","desc":"..."}]},
     "education":[{"school":"...","degree":"...","major":"...","graduationYear":2022}],
     "skillsList":["..."], "social":{"linkedinUrl":"...","githubUrl":"..."}}
  ]
}
"""
from __future__ import annotations

import json
from typing import Any

from ..normalize import (
    normalize_country, normalize_date, normalize_email,
    normalize_phone, normalize_skill,
)
from ..schema import empty_profile

SOURCE = "ats_json"


def _yrs_to_end(start: str | None, end: str | None) -> tuple[str | None, str | None]:
    return normalize_date(start) if start else None, normalize_date(end) if end else None


def extract(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict) and "candidates" in data:
        rows = data.get("candidates") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = [data]

    out: list[dict[str, Any]] = []
    for i, c in enumerate(rows):
        if not isinstance(c, dict):
            continue
        prof = empty_profile()
        prov = []
        personal = c.get("personal") or {}
        prof_data = c.get("professional") or {}

        first = personal.get("firstName") or personal.get("first_name") or ""
        last = personal.get("lastName") or personal.get("last_name") or ""
        full = (first + " " + last).strip() or personal.get("fullName") or ""
        if full:
            prof["full_name"] = full
            prov.append({"field": "full_name", "source": SOURCE, "method": "ats_join_names"})

        emails: list[str] = []
        for k in ("emailAddr", "email", "primaryEmail"):
            ev = normalize_email(personal.get(k, "") or "")
            if ev and ev not in emails:
                emails.append(ev)
        for ev in (personal.get("emails") or []):
            n = normalize_email(ev)
            if n and n not in emails:
                emails.append(n)
        if emails:
            prof["emails"] = emails
            prov.append({"field": "emails", "source": SOURCE, "method": "ats_field"})

        region = personal.get("country") or personal.get("countryCode") or ""
        default_region = "IN" if region.lower() in {"india", "in"} else "US"
        phones: list[str] = []
        for k in ("mobile", "phone", "primaryPhone"):
            p = normalize_phone(personal.get(k, "") or "", default_region=default_region)
            if p and p not in phones:
                phones.append(p)
        for p in (personal.get("phones") or []):
            n = normalize_phone(p, default_region=default_region)
            if n and n not in phones:
                phones.append(n)
        if phones:
            prof["phones"] = phones
            prov.append({"field": "phones", "source": SOURCE, "method": "ats_e164"})

        country = normalize_country(region)
        city = personal.get("city") or None
        regn = personal.get("state") or personal.get("region") or None
        if city or regn or country:
            prof["location"] = {"city": city, "region": regn, "country": country}
            prov.append({"field": "location", "source": SOURCE, "method": "ats_iso"})

        headline = prof_data.get("headline") or prof_data.get("title")
        if headline:
            prof["headline"] = headline
            prov.append({"field": "headline", "source": SOURCE, "method": "ats_field"})

        yrs = prof_data.get("yearsOfExp") or prof_data.get("years_experience")
        if isinstance(yrs, (int, float)):
            prof["years_experience"] = float(yrs)
            prov.append({"field": "years_experience", "source": SOURCE, "method": "ats_field"})

        exp_list = []
        for p in (prof_data.get("positions") or []):
            if not isinstance(p, dict):
                continue
            s, e = _yrs_to_end(p.get("from") or p.get("start"), p.get("to") or p.get("end"))
            exp_list.append({
                "company": p.get("org") or p.get("company") or None,
                "title": p.get("role") or p.get("title") or None,
                "start": s, "end": e,
                "summary": p.get("desc") or p.get("summary") or None,
            })
        if exp_list:
            prof["experience"] = exp_list
            prov.append({"field": "experience", "source": SOURCE, "method": "ats_positions"})

        edu_list = []
        for ed in (c.get("education") or []):
            if not isinstance(ed, dict):
                continue
            yr = ed.get("graduationYear") or ed.get("endYear") or ed.get("end_year")
            try:
                yr = int(yr) if yr is not None else None
            except (TypeError, ValueError):
                yr = None
            edu_list.append({
                "institution": ed.get("school") or ed.get("institution") or None,
                "degree": ed.get("degree") or None,
                "field": ed.get("major") or ed.get("field") or None,
                "end_year": yr,
            })
        if edu_list:
            prof["education"] = edu_list
            prov.append({"field": "education", "source": SOURCE, "method": "ats_education"})

        skills_in = c.get("skillsList") or c.get("skills") or []
        skills: list[dict[str, Any]] = []
        for s in skills_in:
            if isinstance(s, dict):
                s = s.get("name") or ""
            n = normalize_skill(s) if isinstance(s, str) else None
            if n and not any(sk["name"].lower() == n.lower() for sk in skills):
                skills.append({"name": n, "confidence": 0.8, "sources": [SOURCE]})
        if skills:
            prof["skills"] = skills
            prov.append({"field": "skills", "source": SOURCE, "method": "ats_canonical"})

        social = c.get("social") or {}
        if social.get("linkedinUrl") or social.get("linkedin"):
            prof["links"]["linkedin"] = social.get("linkedinUrl") or social.get("linkedin")
            prov.append({"field": "links.linkedin", "source": SOURCE, "method": "ats_field"})
        if social.get("githubUrl") or social.get("github"):
            prof["links"]["github"] = social.get("githubUrl") or social.get("github")
            prov.append({"field": "links.github", "source": SOURCE, "method": "ats_field"})

        prof["candidate_id"] = str(c.get("id") or f"{SOURCE}:{i}")
        prof["provenance"] = prov
        out.append(prof)
    return out

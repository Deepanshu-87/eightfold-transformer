"""Recruiter CSV → list of partial profiles.

Expected (flexible) columns: name, email, phone, current_company, title,
location, city, country, linkedin, github, skills (comma-separated)."""
from __future__ import annotations

import csv
from typing import Any

from ..normalize import (
    extract_emails, normalize_country, normalize_email,
    normalize_phone, normalize_skill,
)
from ..schema import empty_profile

SOURCE = "recruiter_csv"


def _split_skills(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def extract(path: str) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            prof = empty_profile()
            prov = []
            name = row.get("name") or row.get("full_name") or ""
            if name:
                prof["full_name"] = name
                prov.append({"field": "full_name", "source": SOURCE, "method": "csv_column"})
            email = normalize_email(row.get("email", "")) or None
            if not email:
                email = next(iter(extract_emails(row.get("email", ""))), None)
            if email:
                prof["emails"] = [email]
                prov.append({"field": "emails", "source": SOURCE, "method": "csv_column"})
            phone = normalize_phone(row.get("phone", ""), default_region="US")
            if phone:
                prof["phones"] = [phone]
                prov.append({"field": "phones", "source": SOURCE, "method": "csv_normalize_e164"})
            company = row.get("current_company") or row.get("company")
            title = row.get("title") or row.get("current_title")
            if company or title:
                prof["experience"] = [{
                    "company": company or None,
                    "title": title or None,
                    "start": None, "end": None, "summary": None,
                }]
                prov.append({"field": "experience", "source": SOURCE, "method": "csv_column"})
            if title:
                prof["headline"] = title
                prov.append({"field": "headline", "source": SOURCE, "method": "csv_column"})
            country = normalize_country(row.get("country", ""))
            city = row.get("city") or None
            region = row.get("region") or row.get("state") or None
            if city or region or country:
                prof["location"] = {"city": city, "region": region, "country": country}
                prov.append({"field": "location", "source": SOURCE, "method": "csv_normalize_iso"})
            if row.get("linkedin"):
                prof["links"]["linkedin"] = row["linkedin"]
                prov.append({"field": "links.linkedin", "source": SOURCE, "method": "csv_column"})
            if row.get("github"):
                prof["links"]["github"] = row["github"]
                prov.append({"field": "links.github", "source": SOURCE, "method": "csv_column"})
            sk_raw = row.get("skills") or ""
            skills = []
            for s in _split_skills(sk_raw):
                ns = normalize_skill(s)
                if ns:
                    skills.append({"name": ns, "confidence": 0.85, "sources": [SOURCE]})
            if skills:
                prof["skills"] = skills
                prov.append({"field": "skills", "source": SOURCE, "method": "csv_canonical"})
            prof["candidate_id"] = row.get("candidate_id") or f"{SOURCE}:{i}"
            prof["provenance"] = prov
            profiles.append(prof)
    return profiles

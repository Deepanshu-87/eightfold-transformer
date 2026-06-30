"""Identity resolution + merge across sources.

Match keys (in order): normalized email → normalized phone → normalized
full name. The first match wins; merging is symmetric, conflict resolution
is by source priority.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

# Higher = trusted more.
SOURCE_PRIORITY: dict[str, int] = {
    "ats_json": 5,
    "recruiter_csv": 4,
    "resume": 3,
    "recruiter_notes": 2,
    "github": 4,
    "linkedin": 4,
}


def _norm_name(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def _winning_source(prof: dict[str, Any]) -> str:
    # Any provenance entry's source; default unknown.
    if prof.get("provenance"):
        return prof["provenance"][0]["source"]
    return "unknown"


def _group_candidates(profiles: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Union-find by shared email/phone/normalized-name."""
    n = len(profiles)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_email: dict[str, list[int]] = defaultdict(list)
    by_phone: dict[str, list[int]] = defaultdict(list)
    by_name: dict[str, list[int]] = defaultdict(list)

    for i, p in enumerate(profiles):
        for e in p.get("emails") or []:
            by_email[e.lower()].append(i)
        for ph in p.get("phones") or []:
            by_phone[ph].append(i)
        nm = _norm_name(p.get("full_name"))
        if nm:
            by_name[nm].append(i)

    for buckets in (by_email, by_phone, by_name):
        for _, ids in buckets.items():
            for j in range(1, len(ids)):
                union(ids[0], ids[j])

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for i, p in enumerate(profiles):
        groups[find(i)].append(p)
    return list(groups.values())


def _merge_scalar(field: str, group: list[dict[str, Any]]) -> tuple[Any, str | None]:
    """Pick the winning scalar by source priority; ties → first non-empty."""
    best_val = None
    best_pri = -1
    best_src = None
    for p in group:
        v = p.get(field)
        if v in (None, "", []):
            continue
        src = _winning_source(p)
        pri = SOURCE_PRIORITY.get(src, 0)
        if pri > best_pri:
            best_pri, best_val, best_src = pri, v, src
    return best_val, best_src


def _merge_location(group: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    out = {"city": None, "region": None, "country": None}
    prov = []
    for field in ("city", "region", "country"):
        best_val, best_src = None, None
        best_pri = -1
        for p in group:
            loc = p.get("location") or {}
            v = loc.get(field)
            if not v:
                continue
            src = _winning_source(p)
            pri = SOURCE_PRIORITY.get(src, 0)
            if pri > best_pri:
                best_pri, best_val, best_src = pri, v, src
        out[field] = best_val
        if best_val:
            prov.append({"field": f"location.{field}", "source": best_src or "unknown",
                         "method": "priority_winner"})
    return out, prov


def _merge_lists_unique(group: list[dict[str, Any]], field: str, key=lambda x: x) -> list[Any]:
    seen = set()
    out = []
    for p in group:
        for v in p.get(field) or []:
            k = key(v)
            if k in seen:
                continue
            seen.add(k)
            out.append(v)
    return out


def _merge_skills(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for p in group:
        for s in p.get("skills") or []:
            key = s["name"].lower()
            if key not in by_name:
                by_name[key] = {"name": s["name"], "confidence": s["confidence"],
                                "sources": list(s.get("sources") or [])}
                continue
            cur = by_name[key]
            # Boost confidence with diminishing returns when corroborated.
            cur["confidence"] = min(0.99, 1 - (1 - cur["confidence"]) * (1 - s["confidence"]))
            for src in s.get("sources") or []:
                if src not in cur["sources"]:
                    cur["sources"].append(src)
    # Stable order: confidence desc, then alpha.
    return sorted(by_name.values(), key=lambda x: (-x["confidence"], x["name"].lower()))


def _merge_links(group: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    out = {"linkedin": None, "github": None, "portfolio": None, "other": []}
    prov = []
    for k in ("linkedin", "github", "portfolio"):
        best_val, best_src = None, None
        best_pri = -1
        for p in group:
            v = (p.get("links") or {}).get(k)
            if not v:
                continue
            src = _winning_source(p)
            pri = SOURCE_PRIORITY.get(src, 0)
            if pri > best_pri:
                best_pri, best_val, best_src = pri, v, src
        out[k] = best_val
        if best_val:
            prov.append({"field": f"links.{k}", "source": best_src or "unknown",
                         "method": "priority_winner"})
    seen = set()
    for p in group:
        for v in (p.get("links") or {}).get("other") or []:
            if v in seen:
                continue
            seen.add(v)
            out["other"].append(v)
    return out, prov


def _make_candidate_id(group: list[dict[str, Any]]) -> str:
    # Prefer the lowest email alphabetically (deterministic).
    emails = []
    for p in group:
        emails.extend(p.get("emails") or [])
    if emails:
        return sorted(set(emails))[0]
    # Else first phone.
    for p in group:
        if p.get("phones"):
            return p["phones"][0]
    # Else first non-empty name.
    for p in group:
        if p.get("full_name"):
            return _norm_name(p["full_name"]).replace(" ", "_")
    return group[0].get("candidate_id") or "unknown"


def merge_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group by identity and merge each group into one canonical record."""
    merged_out: list[dict[str, Any]] = []
    for group in _group_candidates(profiles):
        rec: dict[str, Any] = {
            "candidate_id": _make_candidate_id(group),
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
        prov: list[dict[str, str]] = []

        for field in ("full_name", "headline", "years_experience"):
            val, src = _merge_scalar(field, group)
            if val not in (None, ""):
                rec[field] = val
                prov.append({"field": field, "source": src or "unknown",
                             "method": "priority_winner"})

        rec["emails"] = _merge_lists_unique(group, "emails", key=lambda x: x.lower())
        if rec["emails"]:
            srcs = sorted({_winning_source(p) for p in group if p.get("emails")})
            for s in srcs:
                prov.append({"field": "emails", "source": s, "method": "union"})

        rec["phones"] = _merge_lists_unique(group, "phones")
        if rec["phones"]:
            srcs = sorted({_winning_source(p) for p in group if p.get("phones")})
            for s in srcs:
                prov.append({"field": "phones", "source": s, "method": "union"})

        loc, loc_prov = _merge_location(group)
        rec["location"] = loc
        prov.extend(loc_prov)

        links, links_prov = _merge_links(group)
        rec["links"] = links
        prov.extend(links_prov)

        rec["skills"] = _merge_skills(group)
        if rec["skills"]:
            prov.append({"field": "skills", "source": "merged",
                         "method": "union_confidence_boost"})

        # experience / education: dedupe by (company,title,start,end) / (inst,degree,year)
        rec["experience"] = _merge_lists_unique(
            group, "experience",
            key=lambda x: (x.get("company"), x.get("title"), x.get("start"), x.get("end")),
        )
        if rec["experience"]:
            prov.append({"field": "experience", "source": "merged", "method": "dedup_union"})

        rec["education"] = _merge_lists_unique(
            group, "education",
            key=lambda x: (x.get("institution"), x.get("degree"), x.get("end_year")),
        )
        if rec["education"]:
            prov.append({"field": "education", "source": "merged", "method": "dedup_union"})

        rec["provenance"] = prov
        merged_out.append(rec)
    return merged_out

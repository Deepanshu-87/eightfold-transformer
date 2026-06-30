"""Normalizers: dates -> YYYY-MM, phones -> E.164, country -> ISO-3166 alpha-2,
skills -> canonical names. Deterministic, no external services."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# ---- Phones (E.164) ----

# Minimal country dialing code map for ambiguous bare numbers.
DEFAULT_DIAL_CODE = "+1"  # used only when number has no country indicator

_PHONE_KEEP = re.compile(r"[^\d+]")


def normalize_phone(raw: str, default_region: str = "US") -> Optional[str]:
    """Convert a raw phone string to E.164. Returns None if not parseable."""
    if not raw or not isinstance(raw, str):
        return None
    s = _PHONE_KEEP.sub("", raw.strip())
    if not s:
        return None
    # Handle 00 international prefix -> +
    if s.startswith("00"):
        s = "+" + s[2:]
    # If already starts with +, validate and return.
    if s.startswith("+"):
        digits = s[1:]
        if 8 <= len(digits) <= 15 and digits.isdigit():
            return "+" + digits
        return None
    # Bare digits: assume default region.
    region_codes = {"US": "+1", "IN": "+91", "GB": "+44", "CA": "+1"}
    cc = region_codes.get(default_region, DEFAULT_DIAL_CODE)
    # If US-like 10 digits, prepend +1; if 11 starting with 1, prepend +.
    if default_region in ("US", "CA"):
        if len(s) == 10:
            return cc + s
        if len(s) == 11 and s.startswith("1"):
            return "+" + s
    if 8 <= len(s) <= 15:
        return cc + s
    return None


# ---- Dates (YYYY-MM) ----

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def normalize_date(raw: str) -> Optional[str]:
    """Return YYYY-MM. Accepts many shapes; returns None for unparseable.
    Treats 'present', 'current', 'now' as None (caller decides what to do)."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s or s in {"present", "current", "now", "today", "ongoing"}:
        return None
    # Try ISO-ish: YYYY-MM, YYYY/MM, YYYY.MM, YYYY-MM-DD
    m = re.match(r"^(\d{4})[-/.](\d{1,2})(?:[-/.]\d{1,2})?$", s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    # MM/YYYY or M-YYYY
    m = re.match(r"^(\d{1,2})[-/.](\d{4})$", s)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    # Year only
    m = re.match(r"^(\d{4})$", s)
    if m:
        return f"{int(m.group(1)):04d}-01"
    # "Jan 2021", "January 2021", "Jan, 2021"
    m = re.match(r"^([a-z]+)[\s,]+(\d{4})$", s)
    if m and m.group(1) in _MONTHS:
        return f"{int(m.group(2)):04d}-{_MONTHS[m.group(1)]:02d}"
    # "2021 Jan"
    m = re.match(r"^(\d{4})[\s,]+([a-z]+)$", s)
    if m and m.group(2) in _MONTHS:
        return f"{int(m.group(1)):04d}-{_MONTHS[m.group(2)]:02d}"
    # Try datetime fallback
    for fmt in ("%b %Y", "%B %Y", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return f"{dt.year:04d}-{dt.month:02d}"
        except (ValueError, TypeError):
            continue
    return None


# ---- Country (ISO-3166 alpha-2) ----

_COUNTRY_MAP = {
    "united states": "US", "usa": "US", "u.s.a": "US", "u.s.": "US",
    "us": "US", "america": "US",
    "united kingdom": "GB", "uk": "GB", "u.k.": "GB", "great britain": "GB",
    "england": "GB", "britain": "GB",
    "india": "IN", "bharat": "IN",
    "canada": "CA", "ca": "CA",
    "germany": "DE", "deutschland": "DE",
    "france": "FR",
    "australia": "AU",
    "singapore": "SG",
    "ireland": "IE",
    "netherlands": "NL", "holland": "NL",
    "spain": "ES",
    "italy": "IT",
    "japan": "JP",
    "china": "CN",
    "brazil": "BR",
    "mexico": "MX",
}


def normalize_country(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip().lower().rstrip(".")
    if not s:
        return None
    # Already 2-letter?
    if len(s) == 2 and s.isalpha():
        return s.upper()
    return _COUNTRY_MAP.get(s)


# ---- Skills (canonical) ----

_SKILL_CANON = {
    "js": "JavaScript", "javascript": "JavaScript", "ecmascript": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "py": "Python", "python": "Python", "python3": "Python",
    "py3": "Python",
    "golang": "Go", "go": "Go",
    "c++": "C++", "cpp": "C++", "cplusplus": "C++",
    "c#": "C#", "csharp": "C#",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "react": "React", "reactjs": "React", "react.js": "React",
    "angular": "Angular", "angularjs": "Angular",
    "vue": "Vue.js", "vuejs": "Vue.js", "vue.js": "Vue.js",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "tf": "Terraform", "terraform": "Terraform",
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP", "google cloud platform": "GCP",
    "azure": "Azure", "microsoft azure": "Azure",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "psql": "PostgreSQL",
    "mongo": "MongoDB", "mongodb": "MongoDB",
    "mysql": "MySQL",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "dl": "Deep Learning", "deep learning": "Deep Learning",
    "ai": "Artificial Intelligence",
    "nlp": "NLP",
    "docker": "Docker",
    "sql": "SQL",
    "java": "Java",
    "rust": "Rust",
    "ruby": "Ruby", "ror": "Ruby on Rails", "rails": "Ruby on Rails",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring", "spring boot": "Spring Boot",
    "tensorflow": "TensorFlow", "tf2": "TensorFlow",
    "pytorch": "PyTorch", "torch": "PyTorch",
    "pandas": "pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn",
    "git": "Git",
    "linux": "Linux",
    "redis": "Redis",
    "kafka": "Kafka",
    "spark": "Apache Spark", "apache spark": "Apache Spark", "pyspark": "Apache Spark",
    "graphql": "GraphQL", "gql": "GraphQL",
    "rest": "REST", "restful": "REST",
    "ci/cd": "CI/CD", "cicd": "CI/CD",
}


def normalize_skill(raw: str) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if not s:
        return None
    if s in _SKILL_CANON:
        return _SKILL_CANON[s]
    # Title-case fallback preserves unknown skills without inventing.
    return raw.strip()


# ---- Email ----

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def normalize_email(raw: str) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    return s if _EMAIL_RE.fullmatch(s) else None


def extract_emails(text: str) -> list[str]:
    if not text:
        return []
    return [m.group(0).lower() for m in _EMAIL_RE.finditer(text)]


# ---- Phone extraction from prose ----

_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")


def extract_phones(text: str, default_region: str = "US") -> list[str]:
    if not text:
        return []
    out = []
    for m in _PHONE_RE.finditer(text):
        p = normalize_phone(m.group(0), default_region)
        if p and p not in out:
            out.append(p)
    return out

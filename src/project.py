"""Projection layer: reshape a canonical record into a custom shape per config.

Config shape (example):
{
  "fields": [
    {"path": "full_name", "type": "string", "required": true},
    {"path": "primary_email", "from": "emails[0]", "type": "string", "required": true},
    {"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"},
    {"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"}
  ],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null"   # one of: null | omit | error
}
"""
from __future__ import annotations

import re
from typing import Any

from .normalize import normalize_phone, normalize_skill


class ProjectionError(ValueError):
    pass


_PATH_TOKEN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+|\])\])?")


def _resolve(record: Any, expr: str) -> Any:
    """Resolve a dotted path with optional [N] or [] segments. Returns
    None if any step is missing. '[]' means: collect from each list item."""
    if expr is None:
        return record
    cur: Any = record
    for raw in expr.split("."):
        for tok in _PATH_TOKEN.finditer(raw):
            key = tok.group(1)
            idx = tok.group(2)
            if isinstance(cur, list):
                # Map operation across list items.
                cur = [item.get(key) if isinstance(item, dict) else None for item in cur]
            elif isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
            if idx is None:
                continue
            if idx == "]":
                # Already a list; nothing else to do.
                if cur is None:
                    return None
                continue
            i = int(idx)
            if isinstance(cur, list) and 0 <= i < len(cur):
                cur = cur[i]
            else:
                return None
    return cur


def _normalize_value(val: Any, kind: str | None) -> Any:
    if val is None or kind is None:
        return val
    if kind == "E164":
        if isinstance(val, list):
            return [normalize_phone(v) or v for v in val]
        return normalize_phone(val) or val
    if kind == "canonical":
        if isinstance(val, list):
            return [normalize_skill(v) or v for v in val]
        return normalize_skill(val) or val
    return val


def _coerce_type(val: Any, typ: str | None) -> Any:
    if val is None or typ is None:
        return val
    if typ == "string":
        return str(val) if not isinstance(val, list) else val
    if typ == "string[]":
        if isinstance(val, list):
            return [str(v) for v in val if v is not None]
        return [str(val)]
    if typ == "number":
        try:
            return float(val) if not isinstance(val, (list, dict)) else val
        except (TypeError, ValueError):
            return None
    return val


def _set_path(out: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = out
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def project(record: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Apply config to a canonical record. Raises ProjectionError if
    required field is missing under on_missing='error'."""
    on_missing = (config.get("on_missing") or "null").lower()
    out: dict[str, Any] = {}

    for spec in config.get("fields") or []:
        path = spec["path"]
        src_expr = spec.get("from") or path
        val = _resolve(record, src_expr)
        val = _normalize_value(val, spec.get("normalize"))
        val = _coerce_type(val, spec.get("type"))
        if val is None or val == [] or val == "":
            if spec.get("required") and on_missing == "error":
                raise ProjectionError(f"Required field missing: {path}")
            if on_missing == "omit":
                continue
            # else null
            val = None
        _set_path(out, path, val)

    if config.get("include_confidence"):
        out["overall_confidence"] = record.get("overall_confidence")
    if config.get("include_provenance"):
        out["provenance"] = record.get("provenance")
    return out

"""End-to-end pipeline: detect → extract → normalize → merge → confidence →
project-to-output → validate."""
from __future__ import annotations

import json
import os
from typing import Any

from .confidence import attach_confidence
from .extract import ats_source, csv_source, notes_source, resume_source
from .merge import merge_profiles
from .project import project
from .schema import DEFAULT_SCHEMA
from .validate import validate


def detect_and_extract(inputs: dict[str, str | None]) -> list[dict[str, Any]]:
    """Given a mapping of source → path, return all partial profiles.
    Missing or malformed sources are skipped gracefully (no crash)."""
    profiles: list[dict[str, Any]] = []

    def safe(fn, path):
        if not path:
            return []
        if not os.path.exists(path):
            print(f"[warn] source path not found, skipping: {path}")
            return []
        try:
            return fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] failed to parse {path}: {e!r} — skipping")
            return []

    profiles += safe(csv_source.extract, inputs.get("csv"))
    profiles += safe(ats_source.extract, inputs.get("ats"))
    profiles += safe(resume_source.extract, inputs.get("resumes"))
    profiles += safe(notes_source.extract, inputs.get("notes"))
    return profiles


def run(
    inputs: dict[str, str | None],
    config: dict[str, Any] | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Run the full pipeline. Returns {'records':[...], 'errors':[...]}.

    - inputs: {csv, ats, resumes, notes} → paths
    - config: projection config; if None, default canonical schema is emitted.
    - strict: raise on validation errors.
    """
    partials = detect_and_extract(inputs)
    merged = merge_profiles(partials)
    for r in merged:
        attach_confidence(r)

    errors: list[str] = []
    output: list[dict[str, Any]] = []
    for rec in merged:
        if config:
            shaped = project(rec, config)
            output.append(shaped)
        else:
            output.append(rec)
            errs = validate(rec, DEFAULT_SCHEMA)
            if errs:
                errors.extend(errs)

    if strict and errors:
        raise ValueError("Schema validation failed:\n" + "\n".join(errors))

    return {"records": output, "errors": errors, "count": len(output)}


def write_json(obj: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=False)

"""Tiny JSON-Schema-ish validator. Only the subset we need:
type checks (string/number/integer/array/object/null + unions), required,
items, properties. Returns list of error strings (empty => valid)."""
from __future__ import annotations

from typing import Any

_TYPE_FN = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def _check_type(val: Any, typ) -> bool:
    types = typ if isinstance(typ, list) else [typ]
    return any(_TYPE_FN.get(t, lambda v: True)(val) for t in types)


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errs: list[str] = []
    typ = schema.get("type")
    if typ and not _check_type(instance, typ):
        errs.append(f"{path}: expected type {typ}, got {type(instance).__name__}")
        return errs
    if isinstance(instance, dict):
        for req in schema.get("required") or []:
            if req not in instance:
                errs.append(f"{path}.{req}: required")
        for k, sub in (schema.get("properties") or {}).items():
            if k in instance:
                errs.extend(validate(instance[k], sub, f"{path}.{k}"))
    elif isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(instance):
                errs.extend(validate(item, item_schema, f"{path}[{i}]"))
    return errs

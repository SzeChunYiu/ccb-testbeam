"""Record validation against the JSON schemas.

Uses the ``jsonschema`` package when importable. Falls back to a compact
in-house checker (required keys + hex/enum patterns + basic types) that is
sufficient for the three CCB schemas so provenance validation never hard-fails
merely because ``jsonschema`` is absent.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

__all__ = ["validate_record", "load_schema", "HAVE_JSONSCHEMA"]

try:  # pragma: no cover - import guard
    import jsonschema  # type: ignore

    HAVE_JSONSCHEMA = True
except Exception:  # pragma: no cover
    jsonschema = None  # type: ignore
    HAVE_JSONSCHEMA = False


def load_schema(schema_path: str | os.PathLike[str]) -> dict[str, Any]:
    p = os.fspath(schema_path)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"schema not found: {p!r}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def validate_record(record: dict[str, Any], schema_path: str | os.PathLike[str]) -> list[str]:
    """Validate *record* against the schema at *schema_path*.

    Returns a list of human-readable error strings; an empty list means the
    record is valid.
    """
    schema = load_schema(schema_path)
    if HAVE_JSONSCHEMA:
        return _validate_jsonschema(record, schema)
    return _validate_minimal(record, schema)


def _validate_jsonschema(record: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)  # type: ignore[attr-defined]
    errors = []
    for err in sorted(validator.iter_errors(record), key=lambda e: list(e.path)):
        loc = "/".join(str(x) for x in err.path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors


# --------------------------------------------------------------------------
# Minimal fallback validator
# --------------------------------------------------------------------------
_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
}


def _matches_type(value: Any, type_spec: Any) -> bool:
    if type_spec is None:
        return True
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for t in types:
        if t == "null":
            if value is None:
                return True
            continue
        py = _TYPE_MAP.get(t)
        if py is None:
            return True  # unknown type name -> don't block
        # bool is a subclass of int; keep them distinct.
        if t == "integer" and isinstance(value, bool):
            continue
        if t == "number" and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return True
    return False


def _check_value(value: Any, subschema: dict[str, Any], loc: str, errors: list[str]) -> None:
    if "enum" in subschema and value not in subschema["enum"]:
        errors.append(
            f"{loc}: {value!r} is not one of {subschema['enum']}"
        )
    if "type" in subschema and not _matches_type(value, subschema["type"]):
        errors.append(f"{loc}: {value!r} is not of type {subschema['type']}")
    if "pattern" in subschema and isinstance(value, str):
        if not re.search(subschema["pattern"], value):
            errors.append(
                f"{loc}: {value!r} does not match pattern {subschema['pattern']!r}"
            )
    if "minLength" in subschema and isinstance(value, str):
        if len(value) < subschema["minLength"]:
            errors.append(f"{loc}: string shorter than minLength {subschema['minLength']}")
    if "minItems" in subschema and isinstance(value, list):
        if len(value) < subschema["minItems"]:
            errors.append(f"{loc}: array shorter than minItems {subschema['minItems']}")
    # Recurse into array items and object properties (with $ref resolution).
    if isinstance(value, list) and "items" in subschema:
        item_schema = _resolve(subschema["items"], _ROOT_SCHEMA)
        for i, item in enumerate(value):
            _check_value(item, item_schema, f"{loc}[{i}]", errors)
    if isinstance(value, dict):
        _check_object(value, subschema, loc, errors)


def _resolve(subschema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    if isinstance(subschema, dict) and "$ref" in subschema:
        ref = subschema["$ref"]
        if ref.startswith("#/"):
            node: Any = root
            for part in ref[2:].split("/"):
                node = node.get(part, {})
            return node
    return subschema


def _check_object(obj: dict[str, Any], schema: dict[str, Any], loc: str, errors: list[str]) -> None:
    required = schema.get("required", [])
    prefix = "" if loc == "<root>" else f"{loc}."
    for key in required:
        if key not in obj:
            errors.append(f"{prefix}{key}: required property is missing")
    props = schema.get("properties", {})
    for key, subschema in props.items():
        if key in obj:
            resolved = _resolve(subschema, _ROOT_SCHEMA)
            _check_value(obj[key], resolved, f"{prefix}{key}", errors)


# Module-global root schema, set per-call so $ref can resolve against $defs.
_ROOT_SCHEMA: dict[str, Any] = {}


def _validate_minimal(record: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    global _ROOT_SCHEMA
    _ROOT_SCHEMA = schema
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"<root>: expected object, got {type(record).__name__}"]
    _check_object(record, schema, "<root>", errors)
    return errors

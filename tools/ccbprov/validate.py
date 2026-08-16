"""Record validation against the JSON schemas (PROV-003).

``jsonschema`` is a HARD dependency for production provenance validation. An
absent or broken ``jsonschema`` import is a fail-closed error: ``validate_record``
raises ``RuntimeError`` rather than silently falling back to a hand-rolled
checker. A partial reimplementation of the JSON Schema semantics (the old
``_validate_minimal`` path) silently accepts malformed provenance records, which
defeats the entire purpose of the provenance gate — so it has been removed.

Install with::

    pip install -e ".[dev]"

(jsonschema lives in the ``dev`` extra).

Concurrency safety
------------------
The previous fallback path mutated a module-global ``_ROOT_SCHEMA`` on every
call so ``$ref`` could resolve against ``$defs``. That made concurrent
validation in multiple threads unsafe (calls clobbered each other's root). The
``jsonschema`` validator is now constructed per call from an immutable schema
dict, so there is no shared mutable state and validation is thread-safe by
construction.
"""

from __future__ import annotations

import json
import os
from typing import Any

__all__ = ["validate_record", "load_schema", "require_jsonschema", "HAVE_JSONSCHEMA"]

try:  # pragma: no cover - import guard
    import jsonschema  # type: ignore

    HAVE_JSONSCHEMA = True
    _JSONSCHEMA_IMPORT_ERROR: BaseException | None = None
except Exception as exc:  # pragma: no cover
    jsonschema = None  # type: ignore
    _JSONSCHEMA_IMPORT_ERROR = exc
    HAVE_JSONSCHEMA = False


def require_jsonschema() -> None:
    """Fail-closed: ``jsonschema`` is mandatory for production validation.

    Raises ``RuntimeError`` (an unignorable, non-permissive error) if
    ``jsonschema`` is not importable. We intentionally do NOT fall back to a
    hand-rolled checker: an incomplete reimplementation silently accepts
    malformed provenance records, which is worse than failing loudly.
    """
    if not HAVE_JSONSCHEMA:
        err = _JSONSCHEMA_IMPORT_ERROR
        detail = f"{type(err).__name__}: {err}" if err is not None else "import returned None"
        raise RuntimeError(
            "jsonschema is required for provenance validation but could not be "
            f"imported ({detail}). This is a fail-closed error: install jsonschema "
            "(e.g. `pip install -e '.[dev]'`) before validating records."
        )


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

    Uses ``jsonschema`` exclusively (no permissive fallback). Thread-safe: the
    validator is constructed per call from the freshly-loaded, immutable schema
    dict, so concurrent validations cannot share or clobber schema state.
    """
    require_jsonschema()
    schema = load_schema(schema_path)
    # Per-call validator: no module-global mutable root schema (PROV-003).
    validator = jsonschema.Draft202012Validator(schema)  # type: ignore[union-attr]
    errors: list[str] = []
    for err in sorted(validator.iter_errors(record), key=lambda e: list(e.path)):
        loc = "/".join(str(x) for x in err.path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors

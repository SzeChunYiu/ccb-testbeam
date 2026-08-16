"""Strict typed boolean parsing for scientific configuration (#1076).

Python ``bool("false")`` is ``True``. Response-defining switches must never use
arbitrary truthiness. This module defines one accepted grammar and fails closed
on ambiguous values.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

from ccb_mc_validation.exceptions import ConfigurationError

PARSER_VERSION = "2026.0-waveB-lane03-strict-bool-v1"

# Canonical accepted spellings (case-insensitive for strings).
_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off"})


def parse_strict_bool(
    value: Any,
    *,
    field: str,
    default: Optional[bool] = None,
    allow_default_on_missing: bool = True,
) -> bool:
    """Parse a scientific boolean.

    Accepted:
      - native ``bool``
      - ``int`` 0 / 1 only
      - strings in {_TRUE} / {_FALSE} (case-insensitive, stripped)

    Rejected (raise ConfigurationError):
      - typos / unknown strings (e.g. ``"flase"``)
      - other numbers (e.g. 2, -1, 0.5)
      - empty string
      - lists / dicts / None when no default is permitted
    """
    if value is None:
        if allow_default_on_missing and default is not None:
            return bool(default)
        raise ConfigurationError(
            f"{field}: boolean value is missing/None; "
            f"set an explicit true/false (parser {PARSER_VERSION})"
        )

    if isinstance(value, bool):
        return value

    if isinstance(value, int) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        raise ConfigurationError(
            f"{field}: integer boolean must be 0 or 1, got {value!r} "
            f"(parser {PARSER_VERSION})"
        )

    if isinstance(value, str):
        s = value.strip().lower()
        if not s:
            raise ConfigurationError(
                f"{field}: empty string is not a valid boolean "
                f"(parser {PARSER_VERSION})"
            )
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
        raise ConfigurationError(
            f"{field}: unrecognized boolean spelling {value!r}; "
            f"accepted strings are "
            f"{sorted(_TRUE | _FALSE)} (parser {PARSER_VERSION})"
        )

    raise ConfigurationError(
        f"{field}: cannot parse boolean from type {type(value).__name__} "
        f"value {value!r} (parser {PARSER_VERSION})"
    )


def resolve_bool_field(
    config: Mapping[str, Any],
    key: str,
    *,
    default: bool = False,
) -> dict:
    """Return requested/effective provenance for a boolean config field."""
    if key not in config:
        effective = parse_strict_bool(
            None, field=key, default=default, allow_default_on_missing=True
        )
        return {
            "key": key,
            "requested": None,
            "requested_present": False,
            "effective": effective,
            "parser_version": PARSER_VERSION,
            "default_applied": default,
        }
    requested = config[key]
    effective = parse_strict_bool(
        requested, field=key, default=None, allow_default_on_missing=False
    )
    return {
        "key": key,
        "requested": requested,
        "requested_present": True,
        "effective": effective,
        "parser_version": PARSER_VERSION,
        "default_applied": None,
    }

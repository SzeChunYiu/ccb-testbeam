"""Strict typed parsing for digitizer response-defining config.

Fail-closed: never use Python truthiness (`bool("false") is True`) or silent
clamps to project invalid scalars into a nearby physical model.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Accepted boolean spellings for DigitizerPipeline scientific switches.
# Native bool always accepted. String forms are case-insensitive and stripped.
_TRUE_STRINGS = frozenset({"true", "1", "yes", "on"})
_FALSE_STRINGS = frozenset({"false", "0", "no", "off"})


def parse_strict_bool(value: Any, *, field_name: str) -> bool:
    """Parse a response-defining boolean without Python truthiness.

    Accepted:
      - native ``True`` / ``False``
      - integers ``0`` / ``1`` (not other ints)
      - strings in {_TRUE_STRINGS | _FALSE_STRINGS} (case-insensitive)

    Rejected: arbitrary nonempty strings (e.g. ``"flase"``), empty string,
    ``None``, lists, floats, and any other type.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        if int(value) == 0:
            return False
        if int(value) == 1:
            return True
        raise ValueError(
            f"{field_name}: integer booleans must be 0 or 1, got {value!r}"
        )
    if isinstance(value, str):
        key = value.strip().lower()
        if key in _TRUE_STRINGS:
            return True
        if key in _FALSE_STRINGS:
            return False
        raise ValueError(
            f"{field_name}: ambiguous/invalid boolean string {value!r}; "
            f"accepted string spellings: "
            f"{sorted(_TRUE_STRINGS | _FALSE_STRINGS)}"
        )
    raise ValueError(
        f"{field_name}: expected boolean (bool/0/1/true|false|yes|no|on|off), "
        f"got {type(value).__name__}={value!r}"
    )


def require_finite_float(value: Any, *, field_name: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: not coercible to float: {value!r}") from exc
    if not np.isfinite(f):
        raise ValueError(f"{field_name}: must be finite, got {f!r}")
    return float(f)


def require_positive_float(value: Any, *, field_name: str) -> float:
    f = require_finite_float(value, field_name=field_name)
    if f <= 0.0:
        raise ValueError(f"{field_name}: must be > 0, got {f}")
    return f


def require_nonnegative_float(value: Any, *, field_name: str) -> float:
    f = require_finite_float(value, field_name=field_name)
    if f < 0.0:
        raise ValueError(f"{field_name}: must be >= 0, got {f}")
    return f


def require_positive_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name}: boolean is not a valid integer cardinality")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{field_name}: expected integer, got non-integer float {value!r}")
        value = int(value)
    try:
        i = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: not coercible to int: {value!r}") from exc
    if isinstance(value, str) and str(value).strip() != str(i):
        # reject "3.5", "1e1" style accidental truncations via int("3.5")
        try:
            if float(value) != float(i):
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"{field_name}: expected integer literal, got {value!r}") from exc
    if i != value and not isinstance(value, (int, np.integer, str)):
        pass
    if isinstance(value, str):
        # int("08") works; int("3.0") fails — already handled
        if "." in value or "e" in value.lower():
            raise ValueError(f"{field_name}: expected integer literal, got {value!r}")
    if i < 1:
        raise ValueError(f"{field_name}: must be >= 1, got {i}")
    return int(i)


STAGE_GRAPH_SCHEMA = "digitizer-stage-graph/1"

# Per-hit stages that may appear in the requested stage list.
ALLOWED_PER_HIT_STAGES: tuple[str, ...] = (
    "birks",
    "scintillation",
    "transport",
    "sampling",
)

# Canonical dependency order for per-hit stages (subset order must respect this).
_STAGE_ORDER = {name: i for i, name in enumerate(ALLOWED_PER_HIT_STAGES)}

# Final channel-level DAQ observation is always applied by DigitizerPipeline.run
# and is NOT a toggleable per-hit stage. Listing "electronics" in stages is a
# proven provenance trap (#1077) and is rejected.
MANDATORY_FINAL_ELECTRONICS = "daq_observation_once"


def resolve_stage_graph(requested: list[str] | None) -> dict[str, Any]:
    """Resolve requested stages to an explicit effective per-hit graph.

    Contract (``digitizer-stage-graph/1``):
      - unknown / duplicate stages -> reject
      - ``electronics`` as a stage -> reject (final DAQ observation is mandatory
        and always applied once after hit summation; it is not an ablation toggle)
      - ``sampling`` is mandatory for the ADC observation model; if omitted it is
        inserted into the effective graph and recorded under ``mandatory_inserted``
      - stage order must respect the physical dependency order
    """
    if requested is None:
        req = list(ALLOWED_PER_HIT_STAGES)
    else:
        req = list(requested)

    if "electronics" in req:
        raise ValueError(
            "stage graph rejects 'electronics' as a per-hit stage (#1077): "
            "final gain/pedestal/noise/quantisation is always applied once by "
            f"run() as {MANDATORY_FINAL_ELECTRONICS!r} and cannot be toggled by "
            "the stages list. Remove 'electronics' from stages."
        )

    unknown = [s for s in req if s not in ALLOWED_PER_HIT_STAGES]
    if unknown:
        raise ValueError(
            f"unknown digitizer stage(s) {unknown!r}; "
            f"allowed per-hit stages: {list(ALLOWED_PER_HIT_STAGES)}"
        )

    if len(req) != len(set(req)):
        raise ValueError(f"duplicate digitizer stages are not allowed: {req!r}")

    # Order must be a subsequence of the canonical dependency order.
    order_idx = [_STAGE_ORDER[s] for s in req]
    if order_idx != sorted(order_idx):
        raise ValueError(
            f"digitizer stages out of physical order: {req!r}; "
            f"required order subsequence of {list(ALLOWED_PER_HIT_STAGES)}"
        )

    mandatory_inserted: list[str] = []
    effective = list(req)
    if "sampling" not in effective:
        effective.append("sampling")
        mandatory_inserted.append("sampling")

    return {
        "schema": STAGE_GRAPH_SCHEMA,
        "requested_stages": req,
        "effective_stages": effective,
        "mandatory_inserted": mandatory_inserted,
        "mandatory_final": MANDATORY_FINAL_ELECTRONICS,
    }

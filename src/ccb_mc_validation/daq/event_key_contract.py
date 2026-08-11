"""Canonical DAQ event-identity contract (#961).

Evidence from the existing run inventory
(`reports/.../daq_event_key_inventory.csv`) shows:

* ``EVENTNO`` is unique within each inspected raw ROOT run (duplicate_EVENTNO=0)
  but resets across runs / restart boundaries.
* ``EVT`` wraps at 16383 and has massive within-run duplication; it is NOT a
  physical event identity.
* ``NO`` / local row indices are not yet source-traced through ucesb/hrdSorter.

Therefore the provisional repository-level composite key is ``(run, EVENTNO)``
with schema version ``daq-event-key/1``. Joins that use ``EVT`` alone, or that
treat ``EVENTNO`` as globally unique across runs, are fail-closed.

Full wrap/reset forensic closure across raw→ucesb→sorted→parquet remains
required before authorising physics merges that depend on absolute event
identity across pipeline products (#957/#953).
"""

from __future__ import annotations

from typing import Any, Sequence


SCHEMA = "daq-event-key/1"
CANONICAL_EVENT_KEY: tuple[str, ...] = ("run", "EVENTNO")
PROVISIONAL_STATUS = "PROVISIONAL_PENDING_PIPELINE_DOMAIN_CLOSURE"
BANNED_SOLE_KEYS = frozenset({"EVT", "evt", "NO", "event_idx", "EVENTNO", "eventno"})


class EventKeyContractError(RuntimeError):
    """Raised when a join/bootstrap key violates the DAQ event-key contract."""


def event_key_contract_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "issue": 961,
        "canonical_key": list(CANONICAL_EVENT_KEY),
        "status": PROVISIONAL_STATUS,
        "field_semantics": {
            "run": "Beam-run number; required for uniqueness because EVENTNO resets.",
            "EVENTNO": (
                "DAQ event counter unique within inspected raw ROOT runs; "
                "NOT globally unique across runs; wrap/reset forensic incomplete."
            ),
            "EVT": (
                "Local/sub-event counter; observed wrap at 16383 with heavy "
                "within-run duplication. Forbidden as sole join key."
            ),
            "NO": "Local counter; origin through unpacker/sorter not yet proven.",
            "event_idx": "Analysis-local row index; never a DAQ identity.",
        },
        "banned_sole_keys": sorted(BANNED_SOLE_KEYS),
        "acceptance_gap": (
            "Exact key-set/domain checks across raw, ucesb, sorted, and parquet "
            "products (#957) are still required before retiring PROVISIONAL status."
        ),
    }


def validate_join_keys(keys: Sequence[str]) -> tuple[str, ...]:
    """Return normalised join keys or raise if the contract is violated."""
    normalised = tuple(str(k) for k in keys)
    if not normalised:
        raise EventKeyContractError("join key list is empty")
    lowered = {k.lower() for k in normalised}
    if normalised == CANONICAL_EVENT_KEY or tuple(k.lower() for k in normalised) == (
        "run",
        "eventno",
    ):
        return ("run", "EVENTNO")
    if len(normalised) == 1 and normalised[0] in BANNED_SOLE_KEYS:
        raise EventKeyContractError(
            f"sole key {normalised[0]!r} is banned by {SCHEMA}; "
            f"use {CANONICAL_EVENT_KEY}"
        )
    if "run" not in lowered:
        raise EventKeyContractError(
            f"join keys {normalised} must include run under {SCHEMA}"
        )
    if "eventno" not in lowered and "EVENTNO" not in normalised:
        # Allow explicit justified alternatives only when documented by caller
        # via a different schema; default path is fail-closed.
        raise EventKeyContractError(
            f"join keys {normalised} are not the canonical {CANONICAL_EVENT_KEY}; "
            f"EVT-based or local-index joins are forbidden without an explicit "
            f"alternate contract (issue #961)."
        )
    return ("run", "EVENTNO")

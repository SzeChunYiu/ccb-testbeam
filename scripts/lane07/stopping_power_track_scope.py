"""Track-scope contract for stopping-power estimators (issue #1007).

Legacy Geant4 ``track_len_scint_mm`` / ``edep_scint_*`` accumulate *all*
non-optical tracks in the scintillator. That event-total ratio is not the
same measurand as NIST PSTAR single-particle stopping power.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

SCOPE_PRIMARY_PROJECTILE = "PRIMARY_PROJECTILE"
SCOPE_EVENT_TOTAL_NON_OPTICAL = "EVENT_TOTAL_NON_OPTICAL"
SCOPE_LEGACY_UNDECLARED = "LEGACY_UNDECLARED_EVENT_TOTAL_NON_OPTICAL"
SCOPE_SECONDARIES_ONLY = "SECONDARIES_ONLY"

PSTAR_COMPARABLE_SCOPES = frozenset({SCOPE_PRIMARY_PROJECTILE})
KNOWN_SCOPES = frozenset(
    {
        SCOPE_PRIMARY_PROJECTILE,
        SCOPE_EVENT_TOTAL_NON_OPTICAL,
        SCOPE_LEGACY_UNDECLARED,
        SCOPE_SECONDARIES_ONLY,
    }
)


class TrackScopeError(ValueError):
    """Invalid or missing track-scope declaration."""


def normalize_track_scope(raw: Any, *, missing_is_legacy: bool = True) -> str:
    if raw is None or str(raw).strip() == "":
        if missing_is_legacy:
            return SCOPE_LEGACY_UNDECLARED
        raise TrackScopeError("track_scope is required")
    key = str(raw).strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "PRIMARY": SCOPE_PRIMARY_PROJECTILE,
        "PRIMARY_PROJECTILE": SCOPE_PRIMARY_PROJECTILE,
        "PRIMARY_TRACK": SCOPE_PRIMARY_PROJECTILE,
        "EVENT_TOTAL": SCOPE_EVENT_TOTAL_NON_OPTICAL,
        "EVENT_TOTAL_NON_OPTICAL": SCOPE_EVENT_TOTAL_NON_OPTICAL,
        "EVENT_TOTAL_ALL_NON_OPTICAL": SCOPE_EVENT_TOTAL_NON_OPTICAL,
        "ALL_NON_OPTICAL": SCOPE_EVENT_TOTAL_NON_OPTICAL,
        "LEGACY": SCOPE_LEGACY_UNDECLARED,
        "LEGACY_UNDECLARED": SCOPE_LEGACY_UNDECLARED,
        "LEGACY_UNDECLARED_EVENT_TOTAL_NON_OPTICAL": SCOPE_LEGACY_UNDECLARED,
        "SECONDARIES": SCOPE_SECONDARIES_ONLY,
        "SECONDARIES_ONLY": SCOPE_SECONDARIES_ONLY,
    }
    if key not in aliases:
        raise TrackScopeError(f"unknown track_scope {raw!r}; known={sorted(KNOWN_SCOPES)}")
    return aliases[key]


def pstar_scope_comparable(scope: str) -> bool:
    return normalize_track_scope(scope, missing_is_legacy=False) in PSTAR_COMPARABLE_SCOPES


def resolve_table_track_scope(
    summary: Mapping[str, Any],
    *,
    explicit: Optional[str] = None,
) -> dict[str, Any]:
    if explicit is not None:
        raw = explicit
        source = "explicit_override"
    elif summary.get("track_scope") is not None and str(summary.get("track_scope")).strip() != "":
        raw = summary.get("track_scope")
        source = "table_or_summary"
    elif summary.get("track_length_scope") is not None and str(summary.get("track_length_scope")).strip() != "":
        raw = summary.get("track_length_scope")
        source = "inferred_from_track_length_scope"
    else:
        raw = None
        source = "column_absent_default_legacy_event_total"
    if raw is None:
        scope = SCOPE_LEGACY_UNDECLARED
    else:
        scope = normalize_track_scope(raw, missing_is_legacy=True)
    comparable = scope in PSTAR_COMPARABLE_SCOPES
    return {
        "track_scope": scope,
        "track_scope_source": source,
        "primary_pstar_scope_comparable": comparable,
        "measurand": (
            "primary_local_stopping_power"
            if comparable
            else "event_total_or_undeclared_non_primary_ratio"
        ),
        "pstar_acceptance_gate": (
            "OPEN_FOR_SCOPE" if comparable else "BLOCKED_NON_PRIMARY_OR_UNDECLARED_SCOPE"
        ),
    }

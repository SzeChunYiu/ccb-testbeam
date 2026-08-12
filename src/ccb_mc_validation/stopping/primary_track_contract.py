"""Primary vs event-total track-length identity for PSTAR comparisons (#1007).

``track_len_scint_mm`` historically summed *all* non-optical scintillator steps.
PSTAR is a single-particle stopping-power reference; event-total path length is
a different measurand once secondaries contribute.
"""

from __future__ import annotations

from typing import Iterable

from ccb_mc_validation.exceptions import DataContractError, StudyBlockedError

PRIMARY_SCOPE = "PRIMARY_TRACK"
EVENT_TOTAL_SCOPE = "EVENT_TOTAL_ALL_NON_OPTICAL"

PRIMARY_TRACK_MM_ALIASES = (
    "primary_track_len_scint_mm",
    "primary_track_length_scint_mm",
)
PRIMARY_TRACK_CM_ALIASES = (
    "primary_track_length_scint_cm",
    "primary_track_len_scint_cm",
)
PRIMARY_RAW_EDEP_ALIASES = (
    "primary_edep_scint_raw_MeV",
    "primary_edep_raw_MeV",
)

EVENT_TRACK_MM_ALIASES = ("track_len_scint_mm", "track_length_scint_mm")
EVENT_TRACK_CM_ALIASES = ("track_length_scint_cm", "track_len_scint_cm")
EVENT_RAW_EDEP_ALIASES = ("edep_scint_raw_MeV", "edep_raw_MeV")


def _populated(columns: Iterable[str], aliases: Iterable[str]) -> list[str]:
    cols = set(columns)
    return [a for a in aliases if a in cols]


def classify_track_length_scope(columns: Iterable[str]) -> str:
    """Return PRIMARY_SCOPE if primary columns present, else EVENT_TOTAL_SCOPE."""
    cols = list(columns)
    primary = _populated(cols, PRIMARY_TRACK_MM_ALIASES + PRIMARY_TRACK_CM_ALIASES)
    if primary:
        return PRIMARY_SCOPE
    event = _populated(cols, EVENT_TRACK_MM_ALIASES + EVENT_TRACK_CM_ALIASES)
    if event:
        return EVENT_TOTAL_SCOPE
    raise DataContractError(
        "stopping-power table has no track-length column "
        f"(primary aliases={PRIMARY_TRACK_MM_ALIASES}; "
        f"event-total aliases={EVENT_TRACK_MM_ALIASES})"
    )


def require_primary_scope_for_pstar(
    columns: Iterable[str],
    *,
    authorizing: bool = True,
    allow_event_total_diagnostic: bool = False,
) -> str:
    """Fail closed for authorizing PSTAR claims on event-total track length."""
    scope = classify_track_length_scope(columns)
    if scope == PRIMARY_SCOPE:
        raw = _populated(columns, PRIMARY_RAW_EDEP_ALIASES)
        if not raw and authorizing:
            # Primary path without primary raw edep is incomplete for PSTAR.
            raise DataContractError(
                "primary track-length columns present but primary raw edep "
                f"aliases missing ({PRIMARY_RAW_EDEP_ALIASES}); #1007"
            )
        return scope
    if authorizing and not allow_event_total_diagnostic:
        raise StudyBlockedError(
            "PSTAR proton stopping-power comparison requested with "
            f"{EVENT_TOTAL_SCOPE} track_len/edep columns (#1007). "
            "Persist and select primary_track_len_scint_mm / "
            "primary_edep_scint_raw_MeV (ParentID==0) before authorizing. "
            "Event-total mixtures include secondaries and are a different measurand."
        )
    if not allow_event_total_diagnostic:
        raise DataContractError(
            f"event-total track-length scope is not PSTAR-comparable (#1007); "
            "pass allow_event_total_diagnostic=True only for labelled diagnostics"
        )
    return scope

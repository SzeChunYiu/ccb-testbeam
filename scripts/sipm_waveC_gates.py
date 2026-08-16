#!/usr/bin/env python3
"""Lane 01 Wave C fail-closed gates for polarity / fibre / attenuation / WLS yield.

Refs: #954 #987 #1033 #1088 #1218. No auto-close keywords.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]

AUTHORISING_POLARITY_STATUSES = {
    "LOCKED_FROM_DUPLICATE_READOUT_CONVENTION",
    "LOCKED_FROM_MEASUREMENT",
    # Measured 33-run unanimous two-estimator map (#954, channel_polarity_v2);
    # same authority class as LOCKED_FROM_MEASUREMENT. Added so the S00
    # B-pulse builder amplitude path can run under the v2 map — the 8x16
    # builder allowlisted this status in #1382; this gate had not been updated.
    "MEASURED_202608_RUNS31_65_UNANIMOUS_BOTH_ESTIMATORS",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def polarity_authorisation_report(
    polarity_status: str,
    channel_diagnostics: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fail closed unless polarity map is locked and no channel is ambiguous."""
    blocked_reasons: list[str] = []
    if polarity_status not in AUTHORISING_POLARITY_STATUSES:
        blocked_reasons.append(f"polarity_status={polarity_status!r} is not a locked authorising status")
    if channel_diagnostics:
        for ch, diag in channel_diagnostics.items():
            st = str(diag.get("status", ""))
            if st in {"AMBIGUOUS", "UNMEASURED_LOW_SNR", "UNKNOWN"}:
                blocked_reasons.append(f"channel {ch} diagnostic status={st}")
    authorising = not blocked_reasons
    return {
        "audit_issue": 954,
        "authorising_waveform_amplitude_claims": authorising,
        "polarity_status": polarity_status,
        "blocked_reasons": blocked_reasons,
    }


def fibre_count_gate(path: Path | None = None) -> dict[str, Any]:
    target = path or (ROOT / "configs" / "stave_hardware_fibre_count_v1.json")
    payload = load_json(target)
    status = str(payload.get("status", "UNKNOWN"))
    authorising = bool(payload.get("authorising_light_collection_claims", False)) and status == "RESOLVED"
    if status != "RESOLVED":
        authorising = False
    return {
        "audit_issue": 987,
        "version": payload.get("version"),
        "hrd_fibre_count_status": status,
        "authorising_light_collection_claims": authorising,
        "path": str(target),
    }


def attenuation_gate(path: Path | None = None) -> dict[str, Any]:
    target = path or (ROOT / "configs" / "light_collection_attenuation_gate_v1.json")
    payload = load_json(target)
    status = str(payload.get("attenuation_identifiability_status", "UNKNOWN"))
    authorising = bool(payload.get("authorising_attenuation_claims", False)) and status == "RESOLVED"
    if status != "RESOLVED":
        authorising = False
    return {
        "audit_issue": 1033,
        "version": payload.get("version"),
        "attenuation_identifiability_status": status,
        "authorising_attenuation_claims": authorising,
        "blocked_on_issues": list(payload.get("blocked_on_issues", [])),
        "path": str(target),
    }


def wls_fluorescence_yield_gate(status: str = "ASSUMPTION_UNIT_YIELD") -> dict[str, Any]:
    """Absolute light-yield claims stay non-authorising under unit-yield assumption (#1088)."""
    authorising_statuses = {"MEASURED_YIELD_SPECTRUM", "SOURCE_BOUND_YIELD"}
    return {
        "audit_issue": 1088,
        "wls_fluorescence_status": status,
        "authorising_absolute_light_yield_claims": status in authorising_statuses,
        "adr": "docs/adr/ADR-WLS-FLUORESCENCE-YIELD-UNVERIFIED.md",
    }


def require_non_authorising_light_collection() -> dict[str, Any]:
    """Composite gate used by light-collection / attenuation producers."""
    fibre = fibre_count_gate()
    atten = attenuation_gate()
    wls = wls_fluorescence_yield_gate()
    authorising = (
        fibre["authorising_light_collection_claims"]
        and atten["authorising_attenuation_claims"]
        and wls["authorising_absolute_light_yield_claims"]
    )
    return {
        "authorising_light_collection_claims": authorising,
        "fibre": fibre,
        "attenuation": atten,
        "wls_fluorescence_yield": wls,
    }


def refuse_authorising_attenuation_export(*, authorising: bool) -> None:
    """Raise if a caller requests an authorising attenuation artifact."""
    gate = require_non_authorising_light_collection()
    if authorising and not gate["authorising_light_collection_claims"]:
        raise PermissionError(
            "attenuation/light-collection export requested authorising=true but "
            "Wave C gates are fail-closed "
            f"(fibre={gate['fibre']['hrd_fibre_count_status']}, "
            f"attenuation={gate['attenuation']['attenuation_identifiability_status']}, "
            f"wls={gate['wls_fluorescence_yield']['wls_fluorescence_status']}). "
            "Refs #987 #1033 #1088."
        )

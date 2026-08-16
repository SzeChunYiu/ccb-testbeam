"""Offline checks for Geant4 run-sidecar completeness expectations (#997/#998)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_ACTION = REPO / "geant4" / "single_stave" / "src" / "RunAction.cc"
MAIN_CC = REPO / "geant4" / "single_stave" / "src" / "main.cc"


REQUIRED_SIDECAR_FIELDS = [
    "hit_x_cm",
    "hit_y_cm",
    "theta_deg",
    "phi_deg",
    "wls_time_profile",
    "strict_optical",
    "sipm_overvoltage_V",
    "gpu_optical",
    "optical_out",
    "macro",
]


def test_run_sidecar_emits_response_defining_fields_and_is_fail_closed():
    text = RUN_ACTION.read_text(encoding="utf-8")
    assert "ccb-stave-run-meta/2" in text
    for field in REQUIRED_SIDECAR_FIELDS:
        assert field in text, field
    assert "fatal: cannot write provenance sidecar" in text
    assert "runtime_error" in text


def test_main_applycommand_fail_closed():
    text = MAIN_CC.read_text(encoding="utf-8")
    assert "apply_required" in text
    assert "Geant4 UI command failed" in text
    assert "return 4" in text
    assert "processed event count" in text
    assert text.index("apply_required") < text.index("CCB_STAVE_END")

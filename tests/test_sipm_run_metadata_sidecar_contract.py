"""Geant4 run sidecar must expose effective ccb-sipm-core/electronics config (#977)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ACTION = ROOT / "geant4" / "single_stave" / "src" / "RunAction.cc"

REQUIRED_DIGITIZER_FIELDS = (
    "validation_status",
    "requested_operating_point",
    "effective_operating_point",
    "operating_point_physics_mapping_status",
    "response_surface_id",
    "ccb_sipm_core_commit",
    "digitizer_config_sha256",
    "core_run_metadata_json",
    "impulse_response_status",
    "measured_impulse_source_hash",
    "effective_kernel_hash",
    "authorising_measured_electronics_claims",
    "delayed_crosstalk_probability",
    "dead_time_ns",
    "sptr_sigma_ns",
    "electronics_noise_sigma_pe",
    "shaper_integrator_stages",
    "pulse_decay_ns",
    "candidate_limit_hits",
)


def test_run_action_sidecar_serializes_effective_digitizer_contract() -> None:
    text = RUN_ACTION.read_text(encoding="utf-8")
    assert "WriteMetadataSidecar" in text
    assert "probe.run_metadata()" in text
    assert "core_run_metadata_json" in text
    for field in REQUIRED_DIGITIZER_FIELDS:
        assert field in text, f"missing digitizer sidecar field {field!r}"


def test_operating_point_physics_remains_fail_closed() -> None:
    text = RUN_ACTION.read_text(encoding="utf-8")
    assert "BLOCKED_ADR_SIPM_OPERATING_POINT_H1" in text
    assert "authorising_measured_electronics_claims" in text
    assert "false" in text.split("authorising_measured_electronics_claims", 1)[1][:40]

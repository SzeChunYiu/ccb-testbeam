"""Lane 05 Wave C contracts: #1079 #1095 #1007 #986 #1064."""

from __future__ import annotations

from pathlib import Path

import pytest

from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.exceptions import ConfigurationError, DataContractError, StudyBlockedError
from ccb_mc_validation.geometry.provenance_hashes import digests_for_nominal
from ccb_mc_validation.step_convergence import (
    REGISTRY_VERSION,
    list_profile_ids,
    load_registry_index,
    require_step_convergence_profile,
)
from ccb_mc_validation.stopping.primary_track_contract import (
    EVENT_TOTAL_SCOPE,
    PRIMARY_SCOPE,
    classify_track_length_scope,
    require_primary_scope_for_pstar,
)
from ccb_mc_validation.timing.template_grid_contract import (
    assert_authorizing_resolution_compatible,
    grid_step_ns,
)
from tools.audit.validate_stopping_power_sim_table import read_validated_simulation_table

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# #1079 Birks parameter contract
# ---------------------------------------------------------------------------
def test_1079_apply_birks_requires_explicit_kb():
    with pytest.raises(ValueError, match="birks_kB_cm_per_MeV"):
        DigitizerPipeline(apply_birks=True).run(
            [{"edep_mev": 1.0, "time_ns": 0.0, "step_length_cm": 1.0}],
            event_id=1,
        )


def test_1079_from_config_requires_unit_tagged_kb_when_enabled():
    with pytest.raises(ValueError, match="birks_kB_cm_per_MeV or birks_kB_mm_per_MeV"):
        DigitizerPipeline.from_config({"apply_birks": True})


def test_1079_rejects_unlabelled_kb_key():
    with pytest.raises(ValueError, match="unlabelled Birks"):
        DigitizerPipeline.from_config({"apply_birks": True, "kB": 0.008})


def test_1079_mm_unit_converts_to_cm():
    pipe = DigitizerPipeline.from_config(
        {
            "apply_birks": True,
            "birks_kB_mm_per_MeV": 0.126,  # Geant4 world
            "transport_sigma_ns": 0.0,
            "noise_adc_rms": 0.0,
            "gain_adc_per_mev": 1.0,
            "pedestal_adc": 0.0,
        }
    )
    assert pipe.birks_kB_cm_per_MeV == pytest.approx(0.0126)
    out = pipe.run(
        [{"edep_mev": 1.0, "time_ns": 0.0, "step_length_cm": 1.0}],
        event_id=2,
    )
    assert out["adc"].shape[0] > 0


def test_1079_python_and_geant4_kb_worlds_disagree():
    # Document the factor-of-safety: H2 vs H3 are not the same number.
    python_default_cm = 0.008
    geant4_default_mm = 0.126
    geant4_as_cm = geant4_default_mm * 0.1
    assert python_default_cm != pytest.approx(geant4_as_cm)


# ---------------------------------------------------------------------------
# #1095 step convergence BLOCKED registry
# ---------------------------------------------------------------------------
def test_1095_registry_fail_closed_defaults():
    idx = load_registry_index(REPO)
    assert idx["registry_version"] == REGISTRY_VERSION
    assert idx["default_step_convergence_profile_id"] is None
    assert idx["fail_closed_when_unset"] is True
    assert list_profile_ids(REPO)


def test_1095_unset_profile_raises():
    with pytest.raises(ConfigurationError, match="step_convergence_profile_id is unset"):
        require_step_convergence_profile({}, repo_root=REPO)


def test_1095_hypothesis_blocks_authorizing_claims():
    with pytest.raises(StudyBlockedError, match="claims_authorized=false"):
        require_step_convergence_profile(
            {
                "step_convergence_profile_id": (
                    "hyp_physicslist_default_step_policy_unvalidated"
                )
            },
            repo_root=REPO,
            authorizing=True,
        )


def test_1095_hypothesis_readable_for_non_authorizing():
    p = require_step_convergence_profile(
        {
            "step_convergence_profile_id": (
                "hyp_physicslist_default_step_policy_unvalidated"
            )
        },
        repo_root=REPO,
        authorizing=False,
    )
    assert p.status == "HYPOTHESIS"
    assert p.claims_authorized is False
    assert p.parameters.get("convergence_study") == "absent"


# ---------------------------------------------------------------------------
# #1007 primary vs event-total
# ---------------------------------------------------------------------------
def test_1007_classify_event_total_vs_primary():
    assert classify_track_length_scope(["track_len_scint_mm"]) == EVENT_TOTAL_SCOPE
    assert (
        classify_track_length_scope(["primary_track_len_scint_mm"]) == PRIMARY_SCOPE
    )


def test_1007_authorizing_pstar_rejects_event_total():
    with pytest.raises(StudyBlockedError, match="EVENT_TOTAL"):
        require_primary_scope_for_pstar(["track_len_scint_mm", "edep_scint_raw_MeV"])


def test_1007_primary_requires_primary_raw_edep_when_authorizing():
    with pytest.raises(DataContractError, match="primary raw edep"):
        require_primary_scope_for_pstar(["primary_track_len_scint_mm"])


def test_1007_validator_prefers_primary_columns(tmp_path: Path):
    csv_path = tmp_path / "prim.csv"
    csv_path.write_text(
        "particle,ke_MeV,primary_edep_scint_raw_MeV,primary_track_len_scint_mm\n"
        "proton,100,2.0,10.0\n"
    )
    rows, summary = read_validated_simulation_table(csv_path)
    assert summary["track_length_scope"] == PRIMARY_SCOPE
    assert summary["pstar_primary_identity_ok"] is True
    assert rows[0][2] == pytest.approx(2.0)
    assert rows[0][3] == pytest.approx(10.0)


def test_1007_validator_marks_event_total_not_primary_identity(tmp_path: Path):
    csv_path = tmp_path / "evt.csv"
    csv_path.write_text(
        "particle,ke_MeV,edep_scint_raw_MeV,track_len_scint_mm\n"
        "proton,100,2.0,10.0\n"
    )
    _, summary = read_validated_simulation_table(csv_path)
    assert summary["track_length_scope"] == EVENT_TOTAL_SCOPE
    assert summary["pstar_primary_identity_ok"] is False


# ---------------------------------------------------------------------------
# #986 geometry vs physics hash
# ---------------------------------------------------------------------------
def test_986_birks_change_does_not_change_geometry_hash():
    a = digests_for_nominal({"birks_kB_mm_per_MeV": 0.126})
    b = digests_for_nominal({"birks_kB_mm_per_MeV": 0.0})
    assert a["geometry_hash"] == b["geometry_hash"]
    assert a["physics_hash"] != b["physics_hash"]


def test_986_far_end_mode_changes_geometry_hash():
    a = digests_for_nominal({"far_end_mode": "instrumented"})
    b = digests_for_nominal({"far_end_mode": "mirror"})
    assert a["geometry_hash"] != b["geometry_hash"]
    assert a["physics_hash"] == b["physics_hash"]


def test_986_coating_thickness_changes_geometry_hash():
    a = digests_for_nominal({"kCoatingThk_mm": 0.25})
    b = digests_for_nominal({"kCoatingThk_mm": 0.50})
    assert a["geometry_hash"] != b["geometry_hash"]


def test_986_canonical_includes_schema_and_named_fields():
    d = digests_for_nominal()
    assert d["geometry_canonical"].startswith("schema_version=2.0.0;")
    assert "coating_thk_mm=" in d["geometry_canonical"]
    assert "far_end_mode=" in d["geometry_canonical"]
    assert "birks_kB" not in d["geometry_canonical"]
    assert "schema=physics_v1" in d["physics_canonical"]
    assert "birks_kB_mm_per_MeV=" in d["physics_canonical"]


# ---------------------------------------------------------------------------
# #1064 template grid quantization
# ---------------------------------------------------------------------------
def test_1064_grid_step_ns_nominal():
    assert grid_step_ns() == pytest.approx(0.5)


def test_1064_rejects_sub_grid_authorizing_claim():
    with pytest.raises(StudyBlockedError, match="finer than the discrete template grid"):
        assert_authorizing_resolution_compatible(0.2)


def test_1064_allows_claim_at_or_coarser_than_grid():
    c = assert_authorizing_resolution_compatible(0.5)
    assert c.claims_authorized is True
    assert c.interpolation == "none"


def test_1064_unimplemented_interpolation_blocked():
    with pytest.raises(StudyBlockedError, match="not an implemented"):
        assert_authorizing_resolution_compatible(
            0.2, config={"template_phase_interpolation": "local_parabola"}
        )

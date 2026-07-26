from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "studies" / "mv3_selection_matched.py"
AUDIT_PATH = Path(__file__).parents[1] / "tools" / "audit" / "audit_mv3_chi2_support.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load(MODULE_PATH, "mv3_selection_matched")
AUDIT = _load(AUDIT_PATH, "audit_mv3_chi2_support")


def test_exact_four_bin_profile():
    value, ndf, per_ndf = MOD._chi2(
        dict(B2=0.50, B4=0.30, B6=0.15, B8=0.05),
        dict(B2=50, B4=30, B6=15, B8=5),
    )
    assert value == 0.0
    assert ndf == 3
    assert per_ndf == 0.0


def test_empty_unsupported_categories_are_omitted():
    result = MOD._chi2(
        dict(B2=0.50, B4=0.50, B6=0.0, B8=0.0),
        dict(B2=50, B4=50, B6=0, B8=0),
    )
    assert result == (0.0, 1, 0.0)


def test_observed_mass_outside_support_is_rejected():
    with pytest.raises(
        MOD.ContractError,
        match="CHI2_OBSERVED_OUTSIDE_MODEL_SUPPORT:staves=B6",
    ):
        MOD._chi2(
            dict(B2=0.50, B4=0.50, B6=0.0, B8=0.0),
            dict(B2=45, B4=45, B6=10, B8=0),
        )


def test_nonunit_profile_is_rejected():
    with pytest.raises(MOD.ContractError, match="CHI2_PROFILE_NOT_NORMALIZED"):
        MOD._chi2(
            dict(B2=0.45, B4=0.45, B6=0.05, B8=0.0),
            dict(B2=45, B4=45, B6=10, B8=0),
        )


def test_exact_category_contract_is_required():
    with pytest.raises(MOD.ContractError, match="CHI2_MODEL_KEYS_MISMATCH"):
        MOD._chi2(
            dict(B2=0.50, B4=0.50, B6=0.0),
            dict(B2=50, B4=50, B6=0, B8=0),
        )


def test_exact_source_audit_is_zero_finding():
    payload = AUDIT.audit(MODULE_PATH)
    assert payload["status"] == "VALIDATED"
    assert payload["finding_count"] == 0


def test_summary_records_both_source_snapshots(tmp_path):
    mc_file = tmp_path / "mc.root"
    pulse_file = tmp_path / "pulses.csv"
    mc_file.write_bytes(b"synthetic-mc")
    pulse_file.write_text("synthetic-pulse\n", encoding="utf-8")
    mc = {
        "unselected": {
            "stop_depth_frac": dict(B2=0.50, B4=0.30, B6=0.15, B8=0.05),
            "sum_w": 100.0,
            "sum_w2": 100.0,
            "effective_sample_size": 100.0,
        },
        "sample_i": {
            "stop_depth_frac": dict(B2=0.50, B4=0.30, B6=0.15, B8=0.05),
        },
    }
    data = {
        "sample_i": {
            "stop_depth_counts": dict(B2=50, B4=30, B6=15, B8=5),
            "stop_depth_frac": dict(B2=0.50, B4=0.30, B6=0.15, B8=0.05),
        }
    }
    summary = MOD.build_summary(
        mc_path=mc_file,
        pulse_path=pulse_file,
        event_path=None,
        output_dir=tmp_path,
        source_commit="0" * 40,
        mc=mc,
        data=data,
        command="synthetic",
    )
    contract = summary["pearson_chi2_contract"]
    assert contract["out_of_support_observations"] == "REJECTED"
    assert summary["schema"] == "ccb-mv3-selection-matched/3"
    provenance = summary["provenance"]
    assert len(provenance["script_sha256"]) == 64
    assert len(provenance["implementation_sha256"]) == 64
    assert provenance["implementation_snapshot"] == "SINGLE_READ_EXACT_BYTES"

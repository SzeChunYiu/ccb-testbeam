from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).parents[1]
BRIDGE_PATH = ROOT / "scripts" / "single_stave" / "deltaE_E_data_bridge.py"
AUDIT_PATH = ROOT / "tools" / "audit" / "audit_deltae_net_input_integrity.py"
STRICT_PATH = ROOT / "scripts" / "single_stave" / "deltaE_E_data_bridge_strict.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIDGE = _load(BRIDGE_PATH, "deltae_bridge_remediation")
AUDIT = _load(AUDIT_PATH, "deltae_net_audit_remediation")
STRICT = _load(STRICT_PATH, "deltae_strict_remediation")


def _pulses(value: object) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run": [1, 1],
            "evt": [10, 10],
            "eventno": [100, 100],
            "stave": ["B2", "B4"],
            "median_amp_adc": [value, 300.0],
        }
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "bad"])
def test_net_amplitude_rows_fail_before_aggregation(value: object) -> None:
    with pytest.raises(ValueError, match="net amplitude input requires finite numeric values"):
        BRIDGE.build_event_table(
            _pulses(value),
            source_file_id="fixture",
            threshold_adc=200.0,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
        )


def test_finite_net_rows_keep_missing_layer_zero_semantics() -> None:
    wide, result = BRIDGE.build_event_table(
        _pulses(250.0),
        source_file_id="fixture",
        threshold_adc=200.0,
        amplitude_column="median_amp_adc",
        amplitude_convention="net",
    )

    assert wide.loc[0, "amp_B2"] == 250.0
    assert wide.loc[0, "amp_B4"] == 300.0
    assert wide.loc[0, "amp_B6"] == 0.0
    assert wide.loc[0, "amp_B8"] == 0.0
    assert result["amplitude_validation"] == (
        "FINITE_NUMERIC_NET_HEIGHT_VALIDATED_BEFORE_AGGREGATION"
    )
    assert result["missing_layer_policy"] == (
        "ZERO_FILL_ONLY_AFTER_FINITE_ROW_VALIDATION_AND_EVENT_STAVE_AGGREGATION"
    )


def test_existing_audit_accepts_corrected_canonical_bridge() -> None:
    payload = AUDIT.audit_source(BRIDGE_PATH)

    assert payload["status"] == "VALIDATED"
    assert payload["issue_count"] == 0
    assert payload["synthetic_controls"]["finite"]["rejected"] is False
    assert payload["synthetic_controls"]["nan"]["rejected"] is True
    assert payload["synthetic_controls"]["positive_infinity"]["rejected"] is True
    assert payload["source_indicators"]["direct_net_assignment_present"] is False
    assert payload["source_indicators"]["net_finite_validation_language_present"] is True


def test_strict_runner_rejects_nonfinite_source_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "pulses.csv"
    _pulses(float("nan")).to_csv(input_path, index=False)
    digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
    commit = "1" * 40
    monkeypatch.setattr(
        STRICT,
        "git_provenance",
        lambda root: {
            "repository_root": str(Path(root).resolve()),
            "commit": commit,
            "tracked_worktree_clean": True,
            "status_policy": "TEST_FIXTURE",
        },
    )

    with pytest.raises(
        ValueError, match="net amplitude input requires finite numeric values"
    ):
        STRICT.run_strict_bridge(
            input_path=input_path,
            output_dir=tmp_path / "out",
            expected_input_sha256=digest,
            expected_repo_commit=commit,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
            amplitude_polarity=None,
            threshold_adc=200.0,
            source_file_id="fixture",
            overwrite=False,
            command="fixture",
            bridge_path=BRIDGE_PATH,
            repository_root=tmp_path,
        )
    assert not (tmp_path / "out").exists()

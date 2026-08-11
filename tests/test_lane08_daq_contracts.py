"""Lane 08 Wave A DAQ/S00 contract tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from ccb_mc_validation.daq.adc_saturation_registry import (
    AdcSaturationContractError,
    authorising_saturation_threshold,
    diagnostic_saturation_flag,
    registry_snapshot,
)
from ccb_mc_validation.daq.event_key_contract import (
    EventKeyContractError,
    event_key_contract_snapshot,
    validate_join_keys,
)
from ccb_mc_validation.daq.raw_sorted_closure import (
    adversarial_fixtures,
    closure_report,
    compare_waveform_words,
)
from ccb_mc_validation.daq.run_ledger import (
    RunLedgerError,
    assert_no_role_contradiction,
    load_run_ledger,
    reconcile_sample_ii_calibration,
    sample_ii_calibration_runs,
)


REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "configs" / "daq" / "run_ledger.yaml"


def test_adc_registry_fail_closed_for_authorising_threshold():
    snap = registry_snapshot()
    assert snap["status"] == "BLOCKED_HARDWARE_EVIDENCE"
    assert snap["authorising_threshold"] is None
    assert {w["world_id"] for w in snap["worlds"]} == {"A", "B", "C"}
    with pytest.raises(AdcSaturationContractError, match="1073"):
        authorising_saturation_threshold()


def test_diagnostic_saturation_flag_is_explicitly_non_authorising():
    flags, meta = diagnostic_saturation_flag([16382, 16383, 20000], world_id="A")
    assert meta["authorising"] is False
    assert meta["threshold"] == 16383
    assert list(flags.astype(int)) == [0, 1, 1]


def test_event_key_contract_canonical_and_bans_evt_alone():
    assert validate_join_keys(["run", "EVENTNO"]) == ("run", "EVENTNO")
    assert validate_join_keys(["run", "eventno"]) == ("run", "EVENTNO")
    with pytest.raises(EventKeyContractError):
        validate_join_keys(["EVT"])
    with pytest.raises(EventKeyContractError):
        validate_join_keys(["run", "evt"])
    snap = event_key_contract_snapshot()
    assert snap["canonical_key"] == ["run", "EVENTNO"]


def test_raw_sorted_word_closure_pass_and_adversarial_failures():
    base = np.arange(2 * 8 * 4, dtype=np.int16).reshape(2, 8, 4)
    ok = compare_waveform_words(base, base.copy())
    assert ok["equal"] is True
    assert closure_report(word_closure=ok, scalar_proxy_used=False)["authorising"]

    for name, (raw, sorted_arr) in adversarial_fixtures().items():
        result = compare_waveform_words(raw, sorted_arr)
        assert result["equal"] is False, name
        assert result["n_mismatched_words"] >= 1, name

    incomplete = closure_report(word_closure=None, scalar_proxy_used=True)
    assert incomplete["authorising"] is False
    assert incomplete["gate_state"] == "INCOMPLETE_SCALAR_PROXY"


def test_run_ledger_resolves_61_vs_64():
    ledger = load_run_ledger(LEDGER)
    assert sample_ii_calibration_runs(ledger) == [64]
    decision = reconcile_sample_ii_calibration(ledger)
    assert decision["canonical_run"] == 64
    assert decision["rejected_run"] == 61
    assert_no_role_contradiction(ledger)
    assert ledger["runs"][61]["purpose"] == "analysis"
    assert ledger["runs"][64]["purpose"] == "calibration"


def test_run_ledger_detects_role_overlap(tmp_path):
    payload = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    payload["study_roles"]["bad"] = {
        "calibration": [64],
        "independent_validation": [64],
    }
    path = tmp_path / "bad_ledger.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(RunLedgerError, match="both"):
        assert_no_role_contradiction(load_run_ledger(path))


def test_adr_and_contracts_exist():
    required = [
        "docs/contracts/ADR-DAQ-HARDWARE-SAMPLING-1014.md",
        "docs/contracts/ADC_SATURATION_WORLD_REGISTRY.md",
        "docs/contracts/DAQ_EVENT_KEY_CONTRACT.md",
        "docs/contracts/RUN_LEDGER.md",
        "docs/contracts/RAW_SORTED_WORD_CLOSURE.md",
        "docs/contracts/S00_VERIFIED_READ_CONTRACT.md",
        "configs/daq/run_ledger.yaml",
    ]
    for rel in required:
        path = REPO / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        if "ADR-DAQ-HARDWARE" in rel:
            assert "BLOCKED" in text
            assert "Do not invent hardware" in text or "Do not invent" in text

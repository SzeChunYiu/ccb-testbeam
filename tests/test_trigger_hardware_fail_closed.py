"""Hardware-trigger fail-closed / BLOCKED+ADR gate (#1045)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.trigger import (
    TRIGGER_EVIDENCE_STATE,
    TRIGGER_LABEL,
    assert_not_hardware_trigger_claim,
    classify_event,
    trigger_provenance,
)

REPO = Path(__file__).resolve().parents[1]


def test_provenance_is_blocked_proxy():
    prov = trigger_provenance()
    assert prov["evidence_state"] == "BLOCKED"
    assert prov["label"] == "MC_TRIGGER_PROXY"
    assert prov["hardware_definition_status"] == "UNKNOWN_EXTERNAL"
    assert TRIGGER_EVIDENCE_STATE == "BLOCKED"
    assert TRIGGER_LABEL == "MC_TRIGGER_PROXY"


def test_proxy_classifier_still_works():
    flags = classify_event(True, True, 0.0, 5.0, 15.0)
    assert flags["sample_I"] is True
    assert flags["sample_II"] is True


def test_forbidden_hardware_claim_fails_closed():
    with pytest.raises(DataContractError, match="forbidden hardware-trigger claim"):
        assert_not_hardware_trigger_claim("This is hardware-trigger reproduction.")


def test_contract_and_adr_validator():
    script = REPO / "tools/audit/validate_trigger_hardware_schema.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--repo-root", str(REPO)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    contract = json.loads(
        (REPO / "docs/contracts/TRIGGER_HARDWARE_RESPONSE.json").read_text(encoding="utf-8")
    )
    assert contract["evidence_state"] == "BLOCKED"

"""Hardware-trigger fail-closed gate (#1045; ADR-0002 -> ADR-1045).

evidence_state was bumped BLOCKED -> MIGRATION_VALIDATED (ADR-1045) after the
#1045 phase-4 corrected joint matrix. Real-data hardware-trigger claims stay
forbidden; production Sample I/II membership keeps the MC_TRIGGER_PROXY
classifier. The contract's headline migration numbers are pinned here against
the committed report so the contract cannot silently drift.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.trigger import (
    TRIGGER_EVIDENCE_STATE,
    TRIGGER_HARDWARE_DEFINITION_STATUS,
    TRIGGER_LABEL,
    assert_not_hardware_trigger_claim,
    classify_event,
    trigger_provenance,
)

REPO = Path(__file__).resolve().parents[1]


def test_provenance_is_migration_validated_proxy():
    prov = trigger_provenance()
    assert prov["evidence_state"] == "MIGRATION_VALIDATED"
    assert prov["label"] == "MC_TRIGGER_PROXY"
    assert prov["hardware_definition_status"] == "GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED"
    assert TRIGGER_EVIDENCE_STATE == "MIGRATION_VALIDATED"
    assert TRIGGER_LABEL == "MC_TRIGGER_PROXY"
    assert TRIGGER_HARDWARE_DEFINITION_STATUS == "GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED"


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
    assert contract["evidence_state"] == "MIGRATION_VALIDATED"
    assert "MC_TRIGGER_PROXY" in contract["admissible_labels"]
    assert "MC_TRIGGER_MIGRATION" in contract["admissible_labels"]
    assert contract["forbidden_labels_until_validated"]


def test_migration_study_artifacts_and_pinned_numbers():
    contract = json.loads(
        (REPO / "docs/contracts/TRIGGER_HARDWARE_RESPONSE.json").read_text(encoding="utf-8")
    )
    study = contract["hardware_response_study"]
    for key in ("joint_matrix", "report", "adr"):
        assert (REPO / study[key]).is_file(), study[key]
    assert (REPO / study["geometry"]["receipt"]).is_file()
    for fig in study["figures"]:
        assert (REPO / fig).is_file(), fig

    # Pinned ground truth: phase-4 corrected per-event joint matrix @1.0 MeV/15 ns
    # (reports/paper_1045_trigger_migration_20260817T013155Z). Editing either the
    # contract or the report without the other must fail here.
    report = json.loads((REPO / study["report"]).read_text(encoding="utf-8"))
    ref = report["reference"]
    assert (ref["both"], ref["proxy_only"], ref["hardware_only"]) == (165, 389, 195)
    assert ref["proxy_total"] == 554
    assert abs(ref["retention"] - 165 / 554) < 5e-4
    assert study["reference_point"]["both"] == ref["both"]
    assert study["reference_point"]["proxy_only"] == ref["proxy_only"]
    assert study["reference_point"]["hardware_only"] == ref["hardware_only"]
    assert abs(study["retention"] - ref["retention"]) < 5e-4
    assert study["n_events"] == report["n_events"] == 1_000_000

"""Claim ledger generation tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.claim_ledger import generate_claim_ledger
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.run_summary import generate_run_summary


def _seed_run(run: Path) -> None:
    run.mkdir()
    validation = {
        "run_id": "run-claims",
        "status": "PASS",
        "study_metrics": {
            "MV1": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"hgb_auc": 0.9}},
            "MV2": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10}, "metrics": {"proton_ekin_recon_res68": 0.1}},
            "MV3": {"status": "PRODUCTION", "cutflow": {"n_tracks": 10, "n_sample_I": 1, "n_sample_II": 2}, "metrics": {}},
        },
    }
    (run / "VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")
    generate_run_summary(run)
    generate_release_audit(run)


def test_claim_ledger_writes_supported_and_blocked_claims(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _seed_run(run)

    ledger = generate_claim_ledger(run)

    assert ledger["status"] == "PASS"
    assert ledger["release_claims_allowed"] is False
    claim_status = {claim["id"]: claim["status"] for claim in ledger["claims"]}
    assert claim_status["CLAIM-MV1-SUMMARY"] == "SUPPORTED"
    assert claim_status["CLAIM-MV4-RELEASE"] == "BLOCKED"
    assert claim_status["CLAIM-FINAL-RELEASE"] == "BLOCKED"
    out = run / "reports" / "mc_validation" / "claims"
    assert (out / "CLAIM_LEDGER.json").is_file()
    text = (out / "CLAIM_LEDGER.md").read_text(encoding="utf-8")
    assert "Release claims allowed" in text
    assert "CLAIM-FINAL-RELEASE" in text

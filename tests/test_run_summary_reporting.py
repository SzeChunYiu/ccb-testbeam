"""Run summary report generation tests."""

from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.run_summary import generate_run_summary


def test_generate_run_summary_writes_tables_and_markdown(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    validation = {
        "run_id": "run",
        "status": "PASS",
        "job_state": {"job_id": "123", "state": "COMPLETED", "exit_code": "0:0"},
        "study_metrics": {
            "MV1": {"status": "PRODUCTION", "cutflow": {"n_tracks": 100}, "metrics": {"hgb_auc": 0.99, "hgb_purity_at_90eff": 0.98}},
            "MV2": {"status": "PRODUCTION", "cutflow": {"n_tracks": 100}, "metrics": {"proton_ekin_recon_res68": 0.1, "deuteron_ekin_recon_res68": 0.2}},
            "MV3": {"status": "PRODUCTION", "cutflow": {"n_tracks": 100, "n_sample_I": 10, "n_sample_II": 20}, "metrics": {}},
        },
    }
    (run / "VALIDATION.json").write_text(json.dumps(validation), encoding="utf-8")

    artifacts = generate_run_summary(run)

    assert Path(artifacts["metrics_table"]).is_file()
    md = Path(artifacts["markdown"])
    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert "MC Validation Run Summary" in text
    assert "MV1" in text

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "paper_a09_heldout_edep_reconstruction"


def test_paper_a09_result_schema_and_headline_metrics() -> None:
    result = json.loads((REPORT / "result.json").read_text(encoding="utf-8"))
    assert result["schema"] == "ccb-paper-a09-heldout-edep/1"
    assert result["status_label"] == "MC_MODEL_DEPENDENT"
    assert result["issue"] == "#1297"
    assert len(result["input_bindings"]) == 5
    for binding in result["input_bindings"]:
        assert binding["sha256"]
        assert binding["bytes"] > 0

    summary = result["summary"]
    assert summary["train_runs"] == ["deuteron_70", "proton_100", "proton_140"]
    assert summary["heldout_runs"] == ["deuteron_110", "proton_60"]
    assert summary["n_train"] == 600
    assert summary["n_heldout"] == 400
    assert abs(summary["heldout_median_bias_fraction"] - 0.1012) < 0.001
    assert abs(summary["heldout_sigma68_fraction"] - 0.0887) < 0.001
    assert abs(summary["heldout_tail_fraction"] - 0.15) < 0.001


def test_paper_a09_summary_table_matches_result() -> None:
    table = pd.read_csv(REPORT / "heldout_energy_reconstruction_summary.csv")
    assert len(table) == 2
    assert set(table["run_id"]) == {"deuteron_110", "proton_60"}
    assert (table["n_heldout"] == 200).all()

    source = pd.read_csv(
        ROOT / "docs/figures/paper/source_tables/edep_reconstruction_heldout_source.csv"
    )
    pd.testing.assert_frame_equal(table.reset_index(drop=True), source.reset_index(drop=True))


def test_paper_a09_figure_artifacts_exist() -> None:
    for name in (
        "edep_reconstruction_heldout.png",
        "edep_reconstruction_heldout.pdf",
    ):
        path = ROOT / "docs/figures/paper" / name
        assert path.is_file(), name
        assert path.stat().st_size > 1000

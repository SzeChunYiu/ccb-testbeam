from __future__ import annotations

import csv
from pathlib import Path


EXPECTED_HEADER = [
    "claim_id",
    "chapter",
    "section",
    "claim_text",
    "current_value",
    "unit",
    "stat_unc",
    "syst_unc",
    "total_unc",
    "ci_low",
    "ci_high",
    "ci_level",
    "ci_method",
    "bootstrap_unit",
    "n_events",
    "n_runs",
    "n_data",
    "n_mc",
    "numerator",
    "denominator",
    "p_value",
    "effect_size",
    "baseline_value",
    "baseline_unc",
    "delta_vs_baseline",
    "delta_ci_low",
    "delta_ci_high",
    "truth_type",
    "status",
    "allowed_status_validated",
    "source_report",
    "source_script",
    "source_data",
    "source_config",
    "source_manifest",
    "figure_ids",
    "table_ids",
    "source_commit",
    "link_validated",
    "ci_status",
    "blocked_by",
    "supersedes",
    "notes",
]


def test_cl015_is_exact_width_and_gated_by_winner_instability() -> None:
    path = Path("docs/claim_ledger.csv")
    rows = list(csv.reader(path.open(encoding="utf-8", newline="")))
    assert rows[0] == EXPECTED_HEADER
    matches = [row for row in rows[1:] if row and row[0] == "CL-015"]
    assert len(matches) == 1
    row = matches[0]
    assert len(row) == len(EXPECTED_HEADER) == 43
    record = dict(zip(EXPECTED_HEADER, row, strict=True))
    assert record["status"] == "GATED"
    assert record["truth_type"] == "data_external_duplicate_readout"
    assert record["current_value"] == "0.03902452880489024"
    assert record["ci_low"] == "0.03566372530746706"
    assert record["ci_high"] == "0.042719761350795714"
    assert record["n_events"] == "100107"
    assert record["n_runs"] == "8"
    assert record["baseline_value"] == "0.07854122474166687"
    assert record["delta_vs_baseline"] == "-0.03951669593677663"
    assert record["ci_status"] == "CI_AVAILABLE_SELECTION_GATE_UNSTABLE"
    assert record["blocked_by"] == "BLK-P04P-001"
    assert "lower-95%-bound sensitivity gate changes" in record["notes"]

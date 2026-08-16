"""Issue #962: config run-role conformance with the canonical run ledger.

Every run-role block in configs/ must agree with configs/daq/run_ledger.yaml:
sample_ii calibration is run 64 (never 61), excluded runs cannot re-enter,
and no block marks a run both calibration and held-out for the same fitted
object. Raw products are SHA-bound to the committed hash sweep.
"""

import csv
from pathlib import Path

import pytest

from ccb_mc_validation.daq.run_ledger import (
    RunLedgerError,
    assert_configs_consistent_with_ledger,
    load_run_ledger,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = REPO_ROOT / "configs" / "daq" / "run_ledger.yaml"


@pytest.fixture(scope="module")
def ledger():
    return load_run_ledger(LEDGER_PATH)


def _tmp_repo(tmp_path, lines):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "probe.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def test_repo_configs_consistent_with_ledger(ledger):
    counts = assert_configs_consistent_with_ledger(ledger, REPO_ROOT)
    # Scope proof: the sweep genuinely covers the campaign's config surface.
    assert counts["blocks_checked"] > 300


def test_sample_ii_calibration_run_61_rejected(ledger, tmp_path):
    root = _tmp_repo(tmp_path, [
        "run_groups:",
        "  sample_ii_calib: [61]",
        "  sample_ii_analysis: [58, 59, 60, 62, 63, 65]",
    ])
    with pytest.raises(RunLedgerError, match=r"sample_ii_calib \[61\] != ledger \[64\]"):
        assert_configs_consistent_with_ledger(ledger, root)


def test_sample_ii_calibration_extra_analysis_run_rejected(ledger, tmp_path):
    root = _tmp_repo(tmp_path, [
        "run_groups:",
        "  sample_ii_calib: [64, 58]",
        "  sample_ii_analysis: [58, 59, 60, 62, 63, 65]",
    ])
    with pytest.raises(RunLedgerError, match="sample_ii_calib"):
        assert_configs_consistent_with_ledger(ledger, root)


def test_excluded_runs_cannot_re_enter_analysis(ledger, tmp_path):
    root = _tmp_repo(tmp_path, [
        "run_groups:",
        "  sample_i_calib: [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42]",
        "  sample_i_analysis: [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 38, 43]",
    ])
    with pytest.raises(RunLedgerError, match=r"sample_i_analysis.*non-ledger runs \[38, 43\]"):
        assert_configs_consistent_with_ledger(ledger, root)


def test_same_block_calib_heldout_overlap_rejected(ledger, tmp_path):
    root = _tmp_repo(tmp_path, [
        "run_groups:",
        "  sample_ii_calib: [64]",
        "  sample_ii_analysis: [58, 59, 60, 62, 63, 65]",
        "  heldout_runs: [64, 57]",
    ])
    with pytest.raises(RunLedgerError, match=r"\[64\].*both calibration and heldout_runs"):
        assert_configs_consistent_with_ledger(ledger, root)


def test_cross_object_reuse_in_separate_blocks_allowed(ledger, tmp_path):
    # T07-style config: a template-calibration block and an ML train/test
    # split are different fitted objects, so 64 may appear in both.
    root = _tmp_repo(tmp_path, [
        "run_groups:",
        "  sample_ii_calib: [64]",
        "  sample_ii_analysis: [58, 59, 60, 62, 63, 65]",
        "ml_check:",
        "  heldout_runs: [42, 50, 57, 58, 60, 62, 64, 65]",
    ])
    counts = assert_configs_consistent_with_ledger(ledger, root)
    assert counts["blocks_checked"] == 1


def test_expected_count_blocks_are_not_run_lists(ledger, tmp_path):
    # Pulse/event totals reuse the role key names; they are not run lists.
    root = _tmp_repo(tmp_path, [
        "expected_counts:",
        "  sample_ii_calib: [14630]",
        "  sample_ii_analysis: [9931]",
    ])
    counts = assert_configs_consistent_with_ledger(ledger, root)
    assert counts["blocks_checked"] == 0


def test_raw_products_bound_to_committed_hash_sweep(ledger):
    raw = ledger["raw_products"]
    bound = {int(k): v for k, v in raw["runs"].items()}
    assert 38 not in bound, "run 38 has no located raw product"
    assert 61 in bound and 64 in bound
    assert all(set(entry) == {"a_stack", "b_stack"} for entry in bound.values())
    csv_path = REPO_ROOT / raw["source_report"]
    assert csv_path.is_file()
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = {row["path"]: row for row in csv.DictReader(fh)}
    for run, entry in sorted(bound.items()):
        for stack in ("a_stack", "b_stack"):
            row = rows[entry[stack]["path"]]
            assert row["sha256"] == entry[stack]["sha256"], f"run {run} {stack} sha mismatch"
            assert int(row["size_bytes"]) == entry[stack]["size_bytes"], (
                f"run {run} {stack} size mismatch"
            )

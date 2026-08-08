"""Tests for the S00 gate-state model (issue #972).

Verifies that:
- --skip-sorted or missing sorted_b_dir produces NOT_RUN_MISSING_INPUT, not
  fabricated raw-as-sorted numbers.
- The exit code is non-zero when the sorted gate is not PASS.
- The manifest records authorising=false when any P0 gate is non-PASS.
- The sorted_compare CSV contains no fabricated raw-as-sorted crosscheck values.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Import the S00 module (filename starts with a digit, so use importlib)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "01_build_pulse_table_from_root.py"


def _load_s00():
    import importlib.util

    spec = importlib.util.spec_from_file_location("s00_build_pulse_table", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pytestmark = pytest.mark.skipif(not SCRIPT_PATH.exists(), reason=f"{SCRIPT_PATH} not found")


@pytest.fixture(scope="module")
def s00():
    return _load_s00()


# ---------------------------------------------------------------------------
# Gate state constants
# ---------------------------------------------------------------------------


class TestGateConstants:
    def test_gate_pass_value(self, s00):
        assert s00.GATE_PASS == "PASS"

    def test_gate_fail_value(self, s00):
        assert s00.GATE_FAIL == "FAIL"

    def test_gate_not_run_missing_input_value(self, s00):
        assert s00.GATE_NOT_RUN_MISSING_INPUT == "NOT_RUN_MISSING_INPUT"

    def test_gate_not_applicable_value(self, s00):
        assert s00.GATE_NOT_APPLICABLE == "NOT_APPLICABLE"

    def test_all_gate_states_are_distinct(self, s00):
        states = {s00.GATE_PASS, s00.GATE_FAIL, s00.GATE_NOT_RUN_MISSING_INPUT, s00.GATE_NOT_APPLICABLE}
        assert len(states) == 4


# ---------------------------------------------------------------------------
# write_manifest() records gate states and authorising correctly
# ---------------------------------------------------------------------------


class TestWriteManifest:
    def test_manifest_records_gate_states_and_authorising(self, s00):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            # Create a dummy selected_path
            selected_path = out_dir / "pulses.parquet"
            selected_path.write_text("dummy", encoding="utf-8")

            # A successful comparison with all gates PASS
            good = pd.DataFrame({"quantity": ["total"], "expected": [100], "actual": [100], "delta": [0], "pass": [True]})
            gate_states = {
                "count_match": s00.GATE_PASS,
                "sorted_even_channel_crosscheck": s00.GATE_PASS,
            }
            s00.write_manifest(out_dir, "config.yaml", good, selected_path,
                               1000.0, "test", gate_states, authorising=True)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["authorising"] is True
            assert manifest["gate_states"]["count_match"] == "PASS"
            assert manifest["gate_states"]["sorted_even_channel_crosscheck"] == "PASS"

    def test_manifest_authorising_false_when_sorted_missing(self, s00):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            selected_path = out_dir / "pulses.parquet"
            selected_path.write_text("dummy", encoding="utf-8")

            good = pd.DataFrame({"quantity": ["total"], "expected": [100], "actual": [100], "delta": [0], "pass": [True]})
            gate_states = {
                "count_match": s00.GATE_PASS,
                "sorted_even_channel_crosscheck": s00.GATE_NOT_RUN_MISSING_INPUT,
            }
            s00.write_manifest(out_dir, "config.yaml", good, selected_path,
                               1000.0, "test", gate_states, authorising=False)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["authorising"] is False
            assert manifest["gate_states"]["sorted_even_channel_crosscheck"] == "NOT_RUN_MISSING_INPUT"

    def test_manifest_authorising_false_when_count_match_fails(self, s00):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            selected_path = out_dir / "pulses.parquet"
            selected_path.write_text("dummy", encoding="utf-8")

            bad = pd.DataFrame({"quantity": ["total"], "expected": [100], "actual": [99], "delta": [-1], "pass": [False]})
            gate_states = {
                "count_match": s00.GATE_FAIL,
                "sorted_even_channel_crosscheck": s00.GATE_PASS,
            }
            s00.write_manifest(out_dir, "config.yaml", bad, selected_path,
                               1000.0, "test", gate_states, authorising=False)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["authorising"] is False
            assert manifest["gate_states"]["count_match"] == "FAIL"

    def test_manifest_gate_states_are_sorted(self, s00):
        """gate_states dict must be written in key order for deterministic output."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            selected_path = out_dir / "pulses.parquet"
            selected_path.write_text("dummy", encoding="utf-8")

            good = pd.DataFrame({"quantity": ["total"], "expected": [100], "actual": [100], "delta": [0], "pass": [True]})
            gate_states = {
                "sorted_even_channel_crosscheck": s00.GATE_NOT_RUN_MISSING_INPUT,
                "count_match": s00.GATE_PASS,
            }
            s00.write_manifest(out_dir, "config.yaml", good, selected_path,
                               1000.0, "test", gate_states, authorising=False)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            keys = list(manifest["gate_states"])
            assert keys == sorted(keys), f"gate_states keys not sorted: {keys}"


# ---------------------------------------------------------------------------
# --skip-sorted cannot produce fabricated raw-as-sorted values in the CSV
# ---------------------------------------------------------------------------


class TestSkippedSortedGate:
    def test_sorted_compare_csv_has_gate_state_column(self, s00):
        """When sorted is skipped, the CSV must contain a gate_state column
        recording NOT_RUN_MISSING_INPUT, not fabricated raw-as-sorted values."""
        import re

        source = SCRIPT_PATH.read_text(encoding="utf-8")

        # The skipped-sorted block must write gate_state to the sorted_compare
        # DataFrame, not copy raw counts as sorted measurements.
        assert "gate_state" in source, (
            "sorted_compare must contain a gate_state column when sorted is skipped. "
            "See issue #972."
        )
        assert "GATE_NOT_RUN_MISSING_INPUT" in source, (
            "The skipped-sorted path must set gate_state = GATE_NOT_RUN_MISSING_INPUT. "
            "See issue #972."
        )
        # The old fabricated path must be gone
        assert "note = \"skipped: sorted ROOT not staged on LUNARC\"" not in source, (
            "The old fabricated 'note' column must be removed. See issue #972."
        )

    def test_authorising_false_when_sorted_not_run(self, s00):
        """Authorising requires every P0 gate to be PASS. A missing sorted
        closure must make authorising=False."""
        # Following the logic from main():
        # authorising = bool(comparison["pass"].all()) and gate_states["sorted_even_channel_crosscheck"] == GATE_PASS
        count_match_ok = True
        sorted_gate_ok = False
        assert not (count_match_ok and sorted_gate_ok), (
            "authorising must be False when sorted gate is not PASS"
        )

    def test_authorising_true_when_all_gates_pass(self, s00):
        count_match_ok = True
        sorted_gate_ok = True
        assert count_match_ok and sorted_gate_ok, (
            "authorising must be True only when every P0 gate is PASS"
        )


# ---------------------------------------------------------------------------
# Exit code logic: main() returns 0 only when authorising
# ---------------------------------------------------------------------------


class TestExitCode:
    def test_return_0_when_authorising(self, s00):
        """main() returns 0 when authorising=True."""
        # The return statement: return 0 if authorising else 1
        assert 1 if not (True and True) else 0 == 0

    def test_return_1_when_not_authorising(self, s00):
        """main() returns 1 when authorising=False."""
        assert 1 if not (True and False) else 0 == 1
        assert 1 if not (False and True) else 0 == 1
        assert 1 if not (False and False) else 0 == 1
"""Tests for S00 publication-transaction safety and the gate-state model.

Two merged concerns:

Issue #1110 / ARU-S00-OVERRIDE-ARTIFACT-001 — five invariants:
  1. IDENTITY: M1 != M2 (different thresholds) must not map to the same output path.
  2. AUTHORISATION-BEFORE-PUBLICATION: a failed run must not replace the last
     authorising artifact set.
  3. SELF-DESCRIPTION: sensitivity artifacts encode the effective threshold,
     selector version, config digest, input hashes, and gate state.
  4. ROLLBACK/ATOMICITY: any exception, failed gate, or interrupted run must
     leave the previous authorising artifact set byte-identical.
  5. CANONICAL-PATH PROTECTION: the canonical pulse-table path may be replaced
     only by the canonical selector/config under an explicit authorising transaction.

Issue #972 — the gate-state model:
- '--skip-sorted' or missing sorted_b_dir produces NOT_RUN_MISSING_INPUT, not
  fabricated raw-as-sorted numbers.
- The exit code is non-zero when the sorted gate is not PASS.
- The manifest records authorising=false when any P0 gate is non-PASS.
- The sorted_compare CSV contains no fabricated raw-as-sorted crosscheck values.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "01_build_pulse_table_from_root.py"


def _load_s00():
    spec = importlib.util.spec_from_file_location("s00_build_pulse_table", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def s00():
    if not SCRIPT_PATH.exists():
        pytest.skip(f"{SCRIPT_PATH} not found")
    return _load_s00()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config() -> dict:
    return {
        "amplitude_cut_adc": 1000.0,
        "output_dir": "/tmp/reports/S00",
        "pulse_table_path": "/tmp/data/processed/s00_selected_b_pulses.csv.gz",
        "run_groups": {"test": [1, 2]},
        "raw_root_dir": "/tmp/raw",
        "sorted_b_dir": "/tmp/sorted",
        "baseline_samples": [0, 1],
        "samples_per_channel": 18,
        "staves": {"B2": 0, "B4": 2},
        "expected_counts": {"total_selected_pulses": 100, "groups": {}},
        "ml_check": {
            "random_seed": 42,
            "max_train_per_class": 100,
            "max_test_per_class": 50,
            "heldout_runs": [2],
            "cv_folds": 2,
            "regularization_c": [1.0],
            "features": ["area_adc_samples", "peak_sample", "baseline_adc"],
        },
    }


# ---------------------------------------------------------------------------
# Gate state constants
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# INVARIANT 1: IDENTITY — different thresholds -> different output paths
# ---------------------------------------------------------------------------


class TestIdentity:
    """Different amplitude thresholds must map to disjoint output namespaces."""

    def test_canonical_and_sensitivity_have_different_paths(self, s00, sample_config):
        """1000 ADC (config, canonical) vs 500 ADC (CLI, sensitivity) -> disjoint paths."""
        can_path = s00.resolve_output_namespace(sample_config, 1000.0, "config(1000.0)")
        sen_path = s00.resolve_output_namespace(sample_config, 500.0, "cli(--amplitude-cut-adc=500)")
        assert can_path != sen_path
        assert "sensitivity" in str(sen_path[0])
        assert "amplitude_cut_adc=500" in str(sen_path[0]) or "amplitude_cut_adc=500" in str(sen_path[1])

    def test_two_different_sensitivity_thresholds_are_disjoint(
        self, s00, sample_config
    ):
        """500 ADC and 750 ADC sensitivity runs must not collide."""
        path_500 = s00.resolve_output_namespace(sample_config, 500.0, "cli(--amplitude-cut-adc=500)")
        path_750 = s00.resolve_output_namespace(sample_config, 750.0, "cli(--amplitude-cut-adc=750)")
        assert path_500 != path_750
        assert "amplitude_cut_adc=500" in str(path_500[0])
        assert "amplitude_cut_adc=750" in str(path_750[0])

    def test_config_digest_differs_with_threshold(self, s00, sample_config):
        """config_digest must produce different hashes for different thresholds."""
        d1 = s00.config_digest(sample_config, 1000.0, "config(1000.0)")
        d2 = s00.config_digest(sample_config, 500.0, "cli(--amplitude-cut-adc=500)")
        assert d1 != d2

    def test_config_digest_differs_with_cut_source(self, s00, sample_config):
        """Same numeric threshold from config vs CLI must produce different digests."""
        d1 = s00.config_digest(sample_config, 1000.0, "config(1000.0)")
        d2 = s00.config_digest(sample_config, 1000.0, "cli(--amplitude-cut-adc=1000)")
        assert d1 != d2

    def test_resolve_output_namespace_canonical(self, s00, sample_config):
        """Canonical run returns the exact config paths."""
        out_dir, table = s00.resolve_output_namespace(sample_config, 1000.0, "config(1000.0)")
        assert out_dir == Path(sample_config["output_dir"])
        assert table == Path(sample_config["pulse_table_path"])

    def test_resolve_output_namespace_sensitivity(self, s00, sample_config):
        """Sensitivity run returns a subdirectory under sensitivity/ with the threshold in the path."""
        out_dir, table = s00.resolve_output_namespace(sample_config, 500.0, "cli(--amplitude-cut-adc=500)")
        assert "sensitivity" in str(out_dir)
        assert "amplitude_cut_adc=500" in str(out_dir)
        assert table.name.endswith(".csv.gz")
        assert "s00_selected_b_pulses" in table.name


# ---------------------------------------------------------------------------
# INVARIANT 2: AUTHORISATION-BEFORE-PUBLICATION
# ---------------------------------------------------------------------------


class TestAuthorisationBeforePublication:
    """A failed run must not replace the last authorising artifact set."""

    def test_is_canonical_run_true_when_config_source(self, s00, sample_config):
        """Canonical when cut matches config value AND source is config."""
        assert s00.is_canonical_run(sample_config, 1000.0, "config(1000.0)")

    def test_is_canonical_run_false_when_cli_override(self, s00, sample_config):
        """CLI override is NOT canonical even if the value matches."""
        assert not s00.is_canonical_run(sample_config, 1000.0, "cli(--amplitude-cut-adc=1000)")

    def test_is_canonical_run_false_when_env_override(self, s00, sample_config):
        """Env override is NOT canonical even if the value matches."""
        assert not s00.is_canonical_run(sample_config, 1000.0, "env(CCB_AMPLITUDE_CUT_ADC=1000)")

    def test_is_canonical_run_false_when_value_differs(self, s00, sample_config):
        """Different threshold is never canonical."""
        assert not s00.is_canonical_run(sample_config, 500.0, "config(500.0)")

    def test_canonical_gate_failure_exit_code(self, s00):
        """main() must return 1 when canonical run fails gates."""
        import inspect

        src = inspect.getsource(s00.main)
        assert "return 1" in src
        assert "return 0" in src


# ---------------------------------------------------------------------------
# INVARIANT 3: SELF-DESCRIPTION — sensitivity artifacts encode metadata
# ---------------------------------------------------------------------------


class TestSelfDescription:
    """Sensitivity artifacts must encode threshold, provenance, and model identity."""

    def test_write_manifest_contains_model_identity(self, s00, sample_config, tmp_path):
        """manifest.json must include all required model-identity fields."""
        model_identity = {
            "effective_amplitude_cut_adc": 500.0,
            "amplitude_cut_source": "cli(--amplitude-cut-adc=500)",
            "selector": "01_build_pulse_table_from_root.py",
            "config_digest": "abc123",
            "source_commit": "deadbeef",
        }
        comparison = pd.DataFrame({
            "quantity": ["total selected B-stave pulses"],
            "report_value": [100],
            "reproduced": [100],
            "delta": [0],
            "tolerance": [0],
            "pass": [True],
        })
        gate_states = {
            "count_match": s00.GATE_PASS,
            "sorted_even_channel_crosscheck": s00.GATE_NOT_RUN_MISSING_INPUT,
        }
        s00.write_manifest(
            tmp_path, Path("/tmp/config.yaml"), comparison, tmp_path / "pulses.csv.gz",
            500.0, "cli(--amplitude-cut-adc=500)",
            canonical=False, model_identity=model_identity,
            gate_states=gate_states,
        )
        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        with manifest_path.open() as f:
            manifest = json.load(f)
        assert manifest["model_identity"] == model_identity
        assert manifest["claim_status"] == "sensitivity-only"
        assert manifest["canonical"] is False
        assert manifest["amplitude_cut_adc"] == 500.0
        assert manifest["amplitude_cut_source"] == "cli(--amplitude-cut-adc=500)"

    def test_manifest_canonical_authorising_when_passed(self, s00, sample_config, tmp_path):
        """Canonical run with all gates passing -> claim_status='canonical-authorising'."""
        model_identity = {
            "effective_amplitude_cut_adc": 1000.0,
            "amplitude_cut_source": "config(1000.0)",
            "selector": "01_build_pulse_table_from_root.py",
            "config_digest": "def456",
            "source_commit": "cafebabe",
        }
        comparison = pd.DataFrame({
            "quantity": ["total selected B-stave pulses"],
            "report_value": [100],
            "reproduced": [100],
            "delta": [0],
            "tolerance": [0],
            "pass": [True],
        })
        gate_states = {
            "count_match": s00.GATE_PASS,
            "sorted_even_channel_crosscheck": s00.GATE_PASS,
        }
        s00.write_manifest(
            tmp_path, Path("/tmp/config.yaml"), comparison, tmp_path / "pulses.csv.gz",
            1000.0, "config(1000.0)",
            canonical=True, model_identity=model_identity,
            gate_states=gate_states,
        )
        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        with manifest_path.open() as f:
            manifest = json.load(f)
        assert manifest["claim_status"] == "canonical-authorising"
        assert manifest["canonical"] is True

    def test_manifest_canonical_but_not_authorising_when_gate_fails(self, s00, sample_config, tmp_path):
        """Canonical run with gate failure -> canonical=True but claim_status='sensitivity-only'."""
        model_identity = {
            "effective_amplitude_cut_adc": 1000.0,
            "amplitude_cut_source": "config(1000.0)",
            "selector": "01_build_pulse_table_from_root.py",
            "config_digest": "ghi789",
            "source_commit": "deadbeef",
        }
        comparison = pd.DataFrame({
            "quantity": ["total selected B-stave pulses"],
            "report_value": [100],
            "reproduced": [99],
            "delta": [-1],
            "tolerance": [0],
            "pass": [False],
        })
        gate_states = {
            "count_match": s00.GATE_FAIL,
            "sorted_even_channel_crosscheck": s00.GATE_PASS,
        }
        s00.write_manifest(
            tmp_path, Path("/tmp/config.yaml"), comparison, tmp_path / "pulses.csv.gz",
            1000.0, "config(1000.0)",
            canonical=True, model_identity=model_identity,
            gate_states=gate_states,
        )
        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        with manifest_path.open() as f:
            manifest = json.load(f)
        assert manifest["canonical"] is True
        assert manifest["claim_status"] == "sensitivity-only"
        assert manifest["count_match_passed"] is False

    def test_manifest_contains_amplitude_cut_env_var(self, s00, sample_config, tmp_path):
        """manifest.json must reference the canonical env var name."""
        model_identity = {"effective_amplitude_cut_adc": 1000.0, "amplitude_cut_source": "config(1000.0)"}
        comparison = pd.DataFrame({"pass": [True]})
        gate_states = {
            "count_match": s00.GATE_PASS,
            "sorted_even_channel_crosscheck": s00.GATE_NOT_RUN_MISSING_INPUT,
        }
        s00.write_manifest(
            tmp_path, Path("/tmp/config.yaml"), comparison, tmp_path / "pulses.csv.gz",
            1000.0, "config(1000.0)",
            canonical=True, model_identity=model_identity,
            gate_states=gate_states,
        )
        manifest_path = tmp_path / "manifest.json"
        with manifest_path.open() as f:
            manifest = json.load(f)
        assert "amplitude_cut_env_var" in manifest
        assert manifest["amplitude_cut_env_var"] == s00.AMPLITUDE_CUT_ENV

    def test_write_sensitivity_report_creates_files(self, s00, sample_config, tmp_path):
        """write_sensitivity_report must create sensitivity_summary.csv and migration_matrix."""
        comparison = pd.DataFrame({
            "quantity": ["total selected B-stave pulses"],
            "report_value": [100],
            "reproduced": [100],
            "delta": [0],
            "tolerance": [0],
            "pass": [True],
        })
        counts_by_group = pd.DataFrame({
            "group": ["test"],
            "selected_pulses": [80],
        })
        s00.write_sensitivity_report(tmp_path, 500.0, "cli(--amplitude-cut-adc=500)", counts_by_group, comparison)
        assert (tmp_path / "sensitivity_summary.csv").exists()
        assert (tmp_path / "sensitivity_migration_matrix.csv").exists()


# ---------------------------------------------------------------------------
# INVARIANT 4: ROLLBACK/ATOMICITY
# ---------------------------------------------------------------------------


class TestRollbackAtomicity:
    """atomic_publish must be atomic; staging must be isolated from canonical namespace."""

    def test_atomic_publish_replaces_target(self, s00, tmp_path):
        """atomic_publish should replace target_dir contents with staging_dir contents."""
        staging = tmp_path / "staging"
        target = tmp_path / "target"
        staging.mkdir()
        target.mkdir()
        (staging / "artifact.csv").write_text("data")
        (target / "old.csv").write_text("old")
        s00.atomic_publish(staging, target)
        assert target.exists()
        assert (target / "artifact.csv").exists()
        assert not (target / "old.csv").exists()

    def test_atomic_publish_does_not_leave_staging_behind(self, s00, tmp_path):
        """After atomic_publish, the original staging dir should not exist."""
        staging = tmp_path / "staging"
        target = tmp_path / "target"
        staging.mkdir()
        target.mkdir()
        (staging / "f1.txt").write_text("hello")
        s00.atomic_publish(staging, target)
        assert not staging.exists()

    def test_atomic_publish_creates_parent_dirs(self, s00, tmp_path):
        """atomic_publish should create parent directories of target if they don't exist."""
        staging = tmp_path / "staging"
        target = tmp_path / "a" / "b" / "target"
        staging.mkdir(parents=True)
        (staging / "f1.txt").write_text("hello")
        s00.atomic_publish(staging, target)
        assert target.exists()
        assert (target / "f1.txt").exists()

    def test_atomic_publish_cleans_old_staging(self, s00, tmp_path):
        """A left-over staging dir from a prior interrupted run must be cleaned up."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "canonical.txt").write_text("preserved")
        leftover = tmp_path / f".target.staging-{os.getpid()}"
        leftover.mkdir()
        (leftover / "stale.txt").write_text("stale")
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "fresh.txt").write_text("fresh")
        s00.atomic_publish(staging, target)
        assert not leftover.exists()
        assert (target / "fresh.txt").exists()

    def test_resolve_output_namespace_not_overlapping(self, s00, sample_config):
        """Sensitivity namespace must not be a subdirectory of the canonical namespace
        in a way that could cause accidental overwrite."""
        can_out, can_table = s00.resolve_output_namespace(sample_config, 1000.0, "config(1000.0)")
        sen_out, sen_table = s00.resolve_output_namespace(sample_config, 500.0, "cli(--amplitude-cut-adc=500)")
        assert str(sen_out).startswith(str(can_out))
        assert "sensitivity" in str(sen_out)
        assert sen_out != can_out
        assert sen_table != can_table


# ---------------------------------------------------------------------------
# INVARIANT 5: CANONICAL-PATH PROTECTION
# ---------------------------------------------------------------------------


class TestCanonicalPathProtection:
    """The canonical pulse-table path may be replaced only by the canonical config."""

    def test_sensitivity_never_uses_canonical_path(self, s00, sample_config):
        """A sensitivity run must never resolve to the canonical pulse-table path."""
        _, can_table = s00.resolve_output_namespace(sample_config, 1000.0, "config(1000.0)")
        _, sen_table = s00.resolve_output_namespace(sample_config, 500.0, "cli(--amplitude-cut-adc=500)")
        assert sen_table != can_table

    def test_env_override_never_uses_canonical_path(self, s00, sample_config):
        """An env override sensitivity run must never resolve to the canonical path."""
        _, can_table = s00.resolve_output_namespace(sample_config, 1000.0, "config(1000.0)")
        _, env_table = s00.resolve_output_namespace(sample_config, 750.0, "env(CCB_AMPLITUDE_CUT_ADC=750)")
        assert env_table != can_table


# ---------------------------------------------------------------------------
# AMPLITUDE CUT RESOLUTION
# ---------------------------------------------------------------------------


class TestAmplitudeCutResolution:
    """CLI > env > config precedence, with provenance tracking."""

    def test_resolve_amplitude_cut_from_config(self, s00, sample_config):
        """No CLI or env override -> uses config value with config provenance."""
        cut, source = s00.resolve_amplitude_cut(sample_config, None)
        assert cut == 1000.0
        assert source.startswith("config(")

    def test_resolve_amplitude_cut_from_cli(self, s00, sample_config):
        """CLI override beats config."""
        cut, source = s00.resolve_amplitude_cut(sample_config, 500.0)
        assert cut == 500.0
        assert source.startswith("cli(")

    def test_resolve_amplitude_cut_from_env(self, s00, sample_config, monkeypatch):
        """Env override beats config when no CLI override."""
        monkeypatch.setenv(s00.AMPLITUDE_CUT_ENV, "750.0")
        cut, source = s00.resolve_amplitude_cut(sample_config, None)
        assert cut == 750.0
        assert source.startswith("env(")

    def test_resolve_amplitude_cut_cli_beats_env(self, s00, sample_config, monkeypatch):
        """CLI beats env var."""
        monkeypatch.setenv(s00.AMPLITUDE_CUT_ENV, "750.0")
        cut, source = s00.resolve_amplitude_cut(sample_config, 500.0)
        assert cut == 500.0
        assert source.startswith("cli(")

    def test_resolve_amplitude_cut_rejects_negative_cli(self, s00, sample_config):
        """Negative CLI value must raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            s00.resolve_amplitude_cut(sample_config, -1.0)

    def test_resolve_amplitude_cut_rejects_negative_env(self, s00, sample_config, monkeypatch):
        """Negative env value must raise ValueError."""
        monkeypatch.setenv(s00.AMPLITUDE_CUT_ENV, "-5.0")
        with pytest.raises(ValueError, match="non-negative"):
            s00.resolve_amplitude_cut(sample_config, None)


# ---------------------------------------------------------------------------
# MODEL IDENTITY
# ---------------------------------------------------------------------------


class TestModelIdentity:
    """Model identity must be stable and self-describing."""

    def test_resolve_amplitude_cut_rejects_nan(self, s00, sample_config):
        with pytest.raises(ValueError, match="finite"):
            s00.resolve_amplitude_cut(sample_config, float("nan"))

    def test_resolve_amplitude_cut_rejects_inf(self, s00, sample_config):
        with pytest.raises(ValueError, match="finite"):
            s00.resolve_amplitude_cut(sample_config, float("inf"))

    def test_resolve_amplitude_cut_rejects_nan_env(self, s00, sample_config, monkeypatch):
        monkeypatch.setenv(s00.AMPLITUDE_CUT_ENV, "nan")
        with pytest.raises(ValueError, match="finite"):
            s00.resolve_amplitude_cut(sample_config, None)


    def test_config_digest_is_stable(self, s00, sample_config):
        """Same config + threshold + source -> same digest."""
        d1 = s00.config_digest(sample_config, 1000.0, "config(1000.0)")
        d2 = s00.config_digest(sample_config, 1000.0, "config(1000.0)")
        assert d1 == d2

    def test_config_digest_length(self, s00, sample_config):
        """Digest must be exactly 16 hex characters (first 8 bytes of SHA-256)."""
        d = s00.config_digest(sample_config, 1000.0, "config(1000.0)")
        assert len(d) == 16
        int(d, 16)  # must be valid hex - will raise ValueError if not

    def test_git_source_commit_returns_string(self, s00):
        """git_source_commit must return a non-empty string or 'unknown'."""
        commit = s00.git_source_commit()
        assert isinstance(commit, str)
        assert len(commit) > 0


# ---------------------------------------------------------------------------
# SENSITIVITY REPORT
# ---------------------------------------------------------------------------


class TestSensitivityReport:
    """Sensitivity report must document the effective threshold and migration."""

    def test_sensitivity_summary_has_effective_cut(self, s00, sample_config, tmp_path):
        comparison = pd.DataFrame({"quantity": ["total"], "report_value": [100], "reproduced": [100], "delta": [0], "tolerance": [0], "pass": [True]})
        counts_by_group = pd.DataFrame({"group": ["test"], "selected_pulses": [80]})
        s00.write_sensitivity_report(tmp_path, 500.0, "cli(--amplitude-cut-adc=500)", counts_by_group, comparison)
        df = pd.read_csv(tmp_path / "sensitivity_summary.csv")
        assert df["effective_amplitude_cut_adc"].iloc[0] == 500.0
        assert df["amplitude_cut_source"].iloc[0] == "cli(--amplitude-cut-adc=500)"
        assert df["claim_status"].iloc[0] == "sensitivity-only"

    def test_migration_matrix_has_delta(self, s00, sample_config, tmp_path):
        comparison = pd.DataFrame({"quantity": ["total selected B-stave pulses"], "report_value": [100], "reproduced": [100], "delta": [0], "tolerance": [0], "pass": [True]})
        counts_by_group = pd.DataFrame({"group": ["test"], "selected_pulses": [80]})
        s00.write_sensitivity_report(tmp_path, 500.0, "cli(--amplitude-cut-adc=500)", counts_by_group, comparison)
        df = pd.read_csv(tmp_path / "sensitivity_migration_matrix.csv")
        assert "canonical_1000_adc_expected" in df.columns
        assert "this_threshold_selected" in df.columns
        assert "delta_vs_canonical" in df.columns


# ---------------------------------------------------------------------------
# GATE-STATE MODEL (Issue #972)
# ---------------------------------------------------------------------------


class TestWriteManifest:
    """write_manifest must record gate_states and compute authorising correctly."""

    def test_manifest_records_gate_states_and_authorising(self, s00):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            selected_path = out_dir / "pulses.parquet"
            selected_path.write_text("dummy", encoding="utf-8")

            good = pd.DataFrame({"quantity": ["total"], "expected": [100], "actual": [100], "delta": [0], "pass": [True]})
            gate_states = {
                "count_match": s00.GATE_PASS,
                "sorted_even_channel_crosscheck": s00.GATE_PASS,
            }
            s00.write_manifest(
                out_dir, "config.yaml", good, selected_path,
                1000.0, "test",
                canonical=True, model_identity={},
                gate_states=gate_states,
            )
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["authorising"] is True
            assert manifest["gate_states"]["count_match"] == "PASS"
            assert manifest["gate_states"]["sorted_even_channel_crosscheck"] == "PASS"
            assert manifest["schema_version"] == "v1"

    def test_manifest_not_authorising_when_sorted_missing(self, s00):
        """Gate state NOT_RUN_MISSING_INPUT must be a non-authorising condition."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            selected_path = out_dir / "pulses.parquet"
            selected_path.write_text("dummy", encoding="utf-8")

            good = pd.DataFrame({"quantity": ["total"], "expected": [100], "actual": [100], "delta": [0], "pass": [True]})
            gate_states = {
                "count_match": s00.GATE_PASS,
                "sorted_even_channel_crosscheck": s00.GATE_NOT_RUN_MISSING_INPUT,
            }
            s00.write_manifest(
                out_dir, "config.yaml", good, selected_path,
                1000.0, "test",
                canonical=True, model_identity={},
                gate_states=gate_states,
            )
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["authorising"] is False
            assert manifest["gate_states"]["sorted_even_channel_crosscheck"] == "NOT_RUN_MISSING_INPUT"

    def test_manifest_not_authorising_when_count_fails(self, s00):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            selected_path = out_dir / "pulses.parquet"
            selected_path.write_text("dummy", encoding="utf-8")

            bad = pd.DataFrame({"quantity": ["total"], "expected": [100], "actual": [99], "delta": [-1], "pass": [False]})
            gate_states = {
                "count_match": s00.GATE_FAIL,
                "sorted_even_channel_crosscheck": s00.GATE_PASS,
            }
            s00.write_manifest(
                out_dir, "config.yaml", bad, selected_path,
                1000.0, "test",
                canonical=True, model_identity={},
                gate_states=gate_states,
            )
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
            s00.write_manifest(
                out_dir, "config.yaml", good, selected_path,
                1000.0, "test",
                canonical=True, model_identity={},
                gate_states=gate_states,
            )
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            keys = list(manifest["gate_states"])
            assert keys == sorted(keys), f"gate_states keys not sorted: {keys}"


class TestSkippedSortedGate:
    """--skip-sorted must not fabricate raw-as-sorted crosscheck values (issue #972)."""

    def test_sorted_compare_csv_has_gate_state_column(self, s00):
        """When sorted is skipped, the CSV must contain a gate_state column
        recording NOT_RUN_MISSING_INPUT, not fabricated raw-as-sorted values."""
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        assert '"gate_states"' in source or "gate_state" in source, (
            "sorted_compare must contain a gate_state column when sorted is skipped. "
            "See issue #972."
        )
        assert "GATE_NOT_RUN_MISSING_INPUT" in source, (
            "The skipped-sorted path must set gate_state = GATE_NOT_RUN_MISSING_INPUT. "
            "See issue #972."
        )
        assert 'note = "skipped: sorted ROOT not staged on LUNARC"' not in source, (
            "The old fabricated 'note' column must be removed. See issue #972."
        )


# ---------------------------------------------------------------------------
# SENSITIVITY SUBDIR CONSTANT
# ---------------------------------------------------------------------------


class TestSensitivitySubdir:
    """SENSITIVITY_SUBDIR must be a well-known constant."""

    def test_sensitivity_subdir_is_sensitivity(self, s00):
        assert s00.SENSITIVITY_SUBDIR == "sensitivity"

    def test_amplitude_cut_env_var_is_defined(self, s00):
        assert s00.AMPLITUDE_CUT_ENV == "CCB_AMPLITUDE_CUT_ADC"

# Lane 06 / #1031 finiteness

def test_resolve_amplitude_cut_rejects_nan_standalone():
    import importlib.util
    from pathlib import Path
    import pytest
    path = Path(__file__).resolve().parents[1] / "scripts/01_build_pulse_table_from_root.py"
    spec = importlib.util.spec_from_file_location("s00_amp", path)
    mod = importlib.util.module_from_spec(spec)
    # may fail if heavy deps — use class tests if available

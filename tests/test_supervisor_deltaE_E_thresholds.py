"""Tests for supervisor_deltaE_E.py threshold handling (#1038, #1039).

Verifies:
- deepest_edep_layer() implements the requested D(T) = max{k : E_k > T}
  family with an explicit NO_LAYER_PASSES sentinel.
- A tiny downstream deposit cannot move the inferred depth beyond its
  threshold, and monotonic reach fractions decrease as threshold rises.
- The DATA per-threshold reach uses args.data_thresholds (not a hard-coded
  1000 ADC cut).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "supervisor_deltaE_E.py"


def _load():
    spec = importlib.util.spec_from_file_location("supervisor_deltaE_E", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pytestmark = pytest.mark.skipif(not SCRIPT_PATH.exists(), reason=f"{SCRIPT_PATH} not found")


@pytest.fixture(scope="module")
def m():
    return _load()


# ---------------------------------------------------------------------------
# deepest_edep_layer()
# ---------------------------------------------------------------------------


class TestDeepestEdepLayer:
    def test_deepest_layer_above_threshold(self, m):
        # 10 MeV in B2 (layer 0), 1 eV in B8 (layer 7). D(0.02) must be 0, not 7.
        el = {0: 10.0, 7: 0.001}
        assert m.deepest_edep_layer(el, 0.02) == 0

    def test_tiny_deepest_deposit_below_threshold(self, m):
        # deposit at layer 5 = 0.01, below 0.02 threshold -> layer 5 not reached
        el = {0: 5.0, 5: 0.01}
        assert m.deepest_edep_layer(el, 0.02) == 0

    def test_exactly_threshold_strict_greater(self, m):
        # strict=True uses '>', so a deposit exactly equal to threshold does not
        # pass the layer.
        el = {3: 0.02}
        assert m.deepest_edep_layer(el, 0.02, strict=True) == -1
        assert m.deepest_edep_layer(el, 0.02, strict=False) == 3

    def test_no_layer_passes_sentinel(self, m):
        el = {0: 0.001, 2: 0.005}
        assert m.deepest_edep_layer(el, 0.02) == -1

    def test_empty_deposits(self, m):
        assert m.deepest_edep_layer({}, 0.02) == -1

    def test_deeper_layer_wins(self, m):
        el = {0: 1.0, 3: 0.5, 6: 2.0}
        assert m.deepest_edep_layer(el, 0.02) == 6

    def test_secondary_only_downstream_deposit(self, m):
        # deposit only in a downstream layer from a secondary; the primary leaves
        # nothing above threshold in B2.
        el = {0: 0.0, 4: 3.0}
        assert m.deepest_edep_layer(el, 0.02) == 4


# ---------------------------------------------------------------------------
# Monotonic reach vs threshold (discriminating test from #1039)
# ---------------------------------------------------------------------------


class TestMonotonicReach:
    def test_reach_fraction_decreases_with_threshold(self, m):
        # Synthetic layer-deposit maps. As threshold rises, deep reach must fall.
        maps = [
            {0: 3.0, 1: 0.5, 2: 0.1},
            {0: 2.0, 1: 0.03, 2: 0.0},
            {0: 1.0, 1: 0.01, 2: 0.0},
            {0: 0.5, 1: 0.0, 2: 0.0},
        ]
        reaches = []
        for th in (0.0, 0.02, 0.05, 0.1, 0.5):
            deep = np.array([m.deepest_edep_layer(el, th) for el in maps])
            reach_b6 = float((deep >= 2).mean())
            reaches.append(reach_b6)
        # Non-increasing as threshold rises.
        assert all(a >= b for a, b in zip(reaches, reaches[1:])), reaches


# ---------------------------------------------------------------------------
# DATA per-threshold reach uses args.data_thresholds (not hard-coded 1000)
# ---------------------------------------------------------------------------


def test_data_thresholds_used_in_source(m):
    """The DATA reach computation must reference args.data_thresholds, not a
    hard-coded 1000 constant."""
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "args.data_thresholds" in src, (
        "DATA reach must loop over args.data_thresholds (#1038)"
    )
    # The old hard-coded 1000 cut must be gone from the reach computation.
    assert ">1000" not in src, (
        "hard-coded 1000 ADC cut must be removed from DATA reach (#1038)"
    )


def test_stop_thresholds_used_in_source(m):
    """The MC stop-layer computation must use args.stop_thresholds."""
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "args.stop_thresholds" in src, (
        "MC stop_layer must loop over args.stop_thresholds (#1039)"
    )
    assert "deepest_edep_layer" in src, (
        "MC stop_layer must call deepest_edep_layer (#1039)"
    )


# ---------------------------------------------------------------------------
# #1040: DATA event-set anchor — union of B-staves
# ---------------------------------------------------------------------------


class TestDataEventSetAnchor:
    def test_require_b2_flag_exists(self, m):
        """The --require-b2 flag must be present in argparse."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "--require-b2" in src, (
            "--require-b2 flag must be present in argparse (#1040)"
        )

    def test_union_of_eventno_across_staves(self, m):
        """DATA analysis must use eventno union across all B-staves."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        # The default (without --require-b2) uses set(sub["eventno"].unique())
        # which is the union across all staves.
        assert 'set(sub["eventno"].unique())' in src, (
            "Default event set must be the union of all B-stave eventnos (#1040)"
        )

    def test_n_events_without_B2_recorded(self, m):
        """The data_summary must include n_events_without_B2 and estimand."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "n_events_without_B2" in src, (
            "data_summary must record n_events_without_B2 (#1040)"
        )
        assert "estimand" in src, (
            "data_summary must record the estimand (#1040)"
        )


# ---------------------------------------------------------------------------
# #1041: MC per-event aggregation (not per-track)
# ---------------------------------------------------------------------------


class TestMCPerEventAggregation:
    def test_mc_event_id_across_chunks(self, m):
        """MC must use a global event counter across iterate() chunks."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "mc_event_counter" in src, (
            "MC must use a global mc_event_counter across iterate() chunks (#1041)"
        )
        assert "mc_event_id" in src, (
            "MC must track mc_event_id per event (#1041)"
        )

    def test_no_trackid_grouping(self, m):
        """MC must NOT use Sci_bar_TrackID for grouping."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        # Sci_bar_TrackID must only appear in the branches list definition
        # (which may span multiple lines).  Any line with Sci_bar_TrackID
        # outside the branches list would be a grouping key, which is banned.
        for i, line in enumerate(src.splitlines()):
            if "Sci_bar_TrackID" in line and "branches" not in line:
                # Continuation lines of the branches list start with a quoted
                # string (e.g. '              "Sci_bar_EDep", ...').
                assert line.strip().startswith('"'), (
                    f"Sci_bar_TrackID outside branches list: line {i+1}: {line.strip()}"
                )

    def test_primary_pdg_by_largest_b2_deposit(self, m):
        """Primary PDG must be determined by the largest B2 energy deposit."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "b2_by_pdg" in src, (
            "MC must aggregate B2 deposits per PDG to find the primary (#1041)"
        )
        assert "max(b2_by_pdg, key=b2_by_pdg.get)" in src, (
            "Primary PDG must be the one with the largest B2 deposit (#1041)"
        )


# ---------------------------------------------------------------------------
# #1042: Fail-closed atomic publication
# ---------------------------------------------------------------------------


class TestAtomicPublication:
    def test_pub_dir_used_for_all_savefig(self, m):
        """All savefig calls must write to pub_dir, not args.out."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        # Count savefig calls targeting args.out
        out_savefigs = [l for l in src.splitlines() if "savefig" in l and "args.out" in l]
        assert len(out_savefigs) == 0, (
            f"savefig calls must use pub_dir, not args.out: {out_savefigs}"
        )

    def test_artifact_names_defined(self, m):
        """ARTIFACT_NAMES must be defined with all expected artifacts."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "ARTIFACT_NAMES" in src, (
            "ARTIFACT_NAMES must be defined (#1042)"
        )

    def test_manifest_json_generated(self, m):
        """manifest.json must be generated with SHA-256 checksums."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "manifest.json" in src, (
            "manifest.json must be generated (#1042)"
        )
        assert "sha256" in src.lower(), (
            "manifest must use SHA-256 checksums (#1042)"
        )

    def test_atomic_publication(self, m):
        """Artifacts must be published atomically via os.replace."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "os.replace" in src, (
            "Artifacts must be published via os.replace (atomic) (#1042)"
        )

    def test_staging_directory_cleaned(self, m):
        """Staging directory must be removed after publication."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "shutil.rmtree" in src, (
            "Staging directory must be removed via shutil.rmtree (#1042)"
        )

    def test_missing_artifact_exits(self, m):
        """Missing artifact must cause sys.exit(1)."""
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "sys.exit(1)" in src, (
            "Missing artifact must cause sys.exit(1) (#1042)"
        )
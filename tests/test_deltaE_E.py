"""Tests for the canonical dE-E analysis module (audit A-002 / item #8).

Covers EVERY "Required test" from the dE-E data contract:
  1. duplicate event numbers in different runs NEVER join;
  2. missing downstream bars map to zero only AFTER event-key validation;
  3. all-zero / downstream events get an explicit category label;
  4. increasing the stopping threshold changes cumulative reach MONOTONICALLY;
  5. Sample I/II inclusive & exclusive counts reported + subset relationship;
  6. saturation flags propagated into outputs;
plus: unit labels present and ADC never relabeled MeV, and a full CLI run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# The dE-E module reads/writes parquet event tables (the analysis format on
# LUNARC/local). Skip cleanly where no parquet engine is installed (e.g. CI).
pytest.importorskip("pyarrow")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.single_stave import deltaE_E as de  # noqa: E402
from scripts.single_stave import make_deltaE_fixture as fix  # noqa: E402


# --------------------------------------------------------------------------- #
# builders
# --------------------------------------------------------------------------- #

def _data_row(run, eid, amps, sample="II", sat=None):
    a2, a4, a6, a8 = amps
    sat = sat or {}
    return {
        "source_file_id": "sf0", "run_id": run, "event_id": eid,
        "amp_B2": a2, "amp_B4": a4, "amp_B6": a6, "amp_B8": a8,
        "saturation_B2": sat.get("B2", False), "saturation_B4": sat.get("B4", False),
        "saturation_B6": sat.get("B6", False), "saturation_B8": sat.get("B8", False),
        "threshold_pass_B2": a2 >= 20, "threshold_pass_B4": a4 >= 20,
        "threshold_pass_B6": a6 >= 20, "threshold_pass_B8": a8 >= 20,
        "sample": sample, "trigger_definition": "beam_v1",
    }


def _mc_row(run, eid, edeps, weight=1.0):
    e2, e4, e6, e8 = edeps
    return {
        "source_file_id": "sf0", "run_id": run, "event_id": eid,
        "edep_B2": e2, "edep_B4": e4, "edep_B6": e6, "edep_B8": e8,
        "edep_B10": 0.0, "edep_B12": 0.0,
        "PrimaryWeight": weight,
        "sample": "II", "trigger_definition": "beam_v1",
    }


# --------------------------------------------------------------------------- #
# 1. composite key: duplicate event numbers in different runs NEVER join
# --------------------------------------------------------------------------- #

def test_composite_key_prevents_cross_run_collision():
    data = pd.DataFrame([
        _data_row("runA", 5, (2000, 800, 400, 60)),
        _data_row("runB", 5, (1900, 750, 300, 40)),
        _data_row("runA", 6, (2100, 810, 420, 70)),
    ])
    mc = pd.DataFrame([
        _mc_row("runA", 5, (1.6, 0.6, 0.3, 0.05)),
        _mc_row("runB", 5, (1.5, 0.55, 0.25, 0.03)),
        _mc_row("runA", 6, (1.7, 0.62, 0.31, 0.06)),
    ])

    merged = de.composite_merge(data, mc)
    # event_id 5 must survive as TWO separate rows, one per run.
    eid5 = merged[merged["event_id"] == 5]
    assert len(eid5) == 2
    assert set(eid5["run_id"]) == {"runA", "runB"}
    # every merged row matched on all three key columns (no cross-run mixing)
    assert (merged["_merge"] == "both").all()

    # The historical BUG: joining on event_id ALONE is a many-to-many blowup.
    with pytest.raises(pd.errors.MergeError):
        data.merge(mc, on="event_id", validate="one_to_one")


def test_join_report_flags_no_cross_run_collision():
    data = pd.DataFrame([
        _data_row("runA", 5, (2000, 800, 400, 60)),
        _data_row("runB", 5, (1900, 750, 300, 40)),
    ])
    mc = pd.DataFrame([
        _mc_row("runA", 5, (1.6, 0.6, 0.3, 0.05)),
        _mc_row("runB", 5, (1.5, 0.55, 0.25, 0.03)),
    ])
    rep = de.join_report(data, mc, de.composite_merge(data, mc))
    assert rep["event_ids_shared_across_runs"] == 1
    assert rep["n_matched"] == 2
    assert rep["cross_run_collision"] is False


def test_duplicate_composite_key_rejected():
    data = pd.DataFrame([
        _data_row("runA", 5, (2000, 800, 400, 60)),
        _data_row("runA", 5, (1, 1, 1, 1)),  # exact composite-key duplicate
    ])
    with pytest.raises(de.EventKeyError):
        de.validate_event_keys(data, "DATA")


# --------------------------------------------------------------------------- #
# 2. missing downstream bars -> 0 ONLY AFTER event-key validation
# --------------------------------------------------------------------------- #

def test_missing_downstream_bar_filled_after_validation():
    data = pd.DataFrame([
        _data_row("runA", 1, (2000, 800, 400, 60)),
        _data_row("runB", 1, (1900, 700, 300, 50)),
    ]).drop(columns=["amp_B8"])          # downstream bar absent
    assert "amp_B8" not in data.columns

    prepared = de.prepare_data_side(data)   # validates keys, THEN fills
    assert "amp_B8" in prepared.columns
    assert (prepared["amp_B8"] == 0).all()
    # E is still computed (with the missing bar contributing 0)
    assert "E_data_adc" in prepared.columns
    assert np.isclose(prepared.iloc[0]["E_data_adc"], 800 + 400 + 0)


def test_bad_key_raises_before_any_fill():
    # Same missing bar, but ALSO a broken composite key (dup). The pipeline must
    # raise at validation and never reach the fill step.
    data = pd.DataFrame([
        _data_row("runA", 1, (2000, 800, 400, 60)),
        _data_row("runA", 1, (10, 10, 10, 10)),
    ]).drop(columns=["amp_B8"])
    with pytest.raises(de.EventKeyError):
        de.prepare_data_side(data)

    # Ordering proof: the fill helper itself is agnostic (would not raise),
    # so the guard is the validation step, not the fill.
    filled = de.fill_missing_layers(data, de.FILLABLE_DATA_LAYERS)
    assert (filled["amp_B8"] == 0).all()
    with pytest.raises(de.EventKeyError):
        de.validate_event_keys(data, "DATA")


def test_missing_key_column_rejected():
    data = pd.DataFrame([_data_row("runA", 1, (2000, 800, 400, 60))]).drop(columns=["run_id"])
    with pytest.raises(de.EventKeyError):
        de.validate_event_keys(data, "DATA")


# --------------------------------------------------------------------------- #
# 3. all-zero / downstream events -> explicit category label
# --------------------------------------------------------------------------- #

def test_all_zero_event_gets_explicit_category():
    df = pd.DataFrame([
        {"amp_B2": 0.0, "amp_B4": 0.0, "amp_B6": 0.0, "amp_B8": 0.0},   # empty
        {"amp_B2": 500.0, "amp_B4": 0.0, "amp_B6": 0.0, "amp_B8": 0.0}, # stops in B2
        {"amp_B2": 500.0, "amp_B4": 300.0, "amp_B6": 200.0, "amp_B8": 90.0},  # punch
    ])
    cols = [f"amp_{b}" for b in de.DATA_LAYERS]
    cats = de.assign_stop_category(df, cols, de.DATA_LAYERS, threshold=20.0)
    assert cats.iloc[0] == de.NO_REACH_CATEGORY
    assert cats.iloc[1] == "B2"
    assert cats.iloc[2] == "B8"

    dist = de.stopping_distribution(df, cols, de.DATA_LAYERS, threshold=20.0)
    assert de.NO_REACH_CATEGORY in dist["stop_category_fractions"]
    assert dist["n_no_layer_passes"] == 1


# --------------------------------------------------------------------------- #
# 4. stopping threshold monotonicity
# --------------------------------------------------------------------------- #

def test_reach_monotonic_in_threshold():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "amp_B2": rng.uniform(0, 1000, 400),
        "amp_B4": rng.uniform(0, 1000, 400),
        "amp_B6": rng.uniform(0, 1000, 400),
        "amp_B8": rng.uniform(0, 1000, 400),
    })
    cols = [f"amp_{b}" for b in de.DATA_LAYERS]
    thresholds = [20.0, 100.0, 400.0]
    dists = [de.stopping_distribution(df, cols, de.DATA_LAYERS, t) for t in thresholds]
    # per-layer cumulative reach non-increasing as threshold rises
    for lo, hi in zip(dists, dists[1:]):
        for layer in de.DATA_LAYERS:
            assert hi["reach_by_layer"][layer] <= lo["reach_by_layer"][layer] + 1e-12
    assert de.check_monotonic_reach(dists) is True


def test_check_monotonic_reach_detects_violation():
    good = {"threshold": 1.0, "reach_by_layer": {"B2": 0.9}}
    bad = {"threshold": 2.0, "reach_by_layer": {"B2": 0.95}}  # went UP -> violation
    assert de.check_monotonic_reach([good, bad]) is False


# --------------------------------------------------------------------------- #
# 5. Sample I/II inclusive & exclusive + subset relationship
# --------------------------------------------------------------------------- #

def test_sample_counts_subset_true():
    data = pd.DataFrame([
        _data_row("runA", 1, (500, 0, 0, 0), sample="I;II"),
        _data_row("runA", 2, (500, 0, 0, 0), sample="II"),
        _data_row("runA", 3, (500, 0, 0, 0), sample="II"),
        _data_row("runA", 4, (500, 0, 0, 0), sample=""),
    ])
    c = de.sample_counts(data)
    assert c["sample_I_inclusive"] == 1
    assert c["sample_II_inclusive"] == 3
    assert c["sample_I_exclusive"] == 0
    assert c["sample_II_exclusive"] == 2
    assert c["in_both"] == 1
    assert c["sample_I_subset_of_II"] is True


def test_sample_counts_subset_false_counterexample():
    # An event in Sample I but NOT Sample II must flip the subset flag.
    data = pd.DataFrame([
        _data_row("runA", 1, (500, 0, 0, 0), sample="I"),   # I only
        _data_row("runA", 2, (500, 0, 0, 0), sample="II"),
    ])
    c = de.sample_counts(data)
    assert c["sample_I_exclusive"] == 1
    assert c["sample_I_subset_of_II"] is False


# --------------------------------------------------------------------------- #
# 6. saturation flags propagated
# --------------------------------------------------------------------------- #

def test_saturation_flags_propagated():
    data = pd.DataFrame([
        _data_row("runA", 1, (3500, 800, 400, 60), sat={"B2": True}),
        _data_row("runB", 1, (1000, 800, 400, 60)),
    ])
    prepared = de.prepare_data_side(data)
    for b in de.DATA_LAYERS:
        assert f"saturation_{b}" in prepared.columns
    assert "saturated_any" in prepared.columns
    assert bool(prepared.iloc[0]["saturated_any"]) is True
    assert bool(prepared.iloc[1]["saturated_any"]) is False


def test_saturation_flags_default_false_when_absent():
    data = pd.DataFrame([
        _data_row("runA", 1, (500, 0, 0, 0)),
    ]).drop(columns=[f"saturation_{b}" for b in de.DATA_LAYERS])
    prepared = de.prepare_data_side(data)   # keys valid -> flags default False
    assert bool(prepared.iloc[0]["saturated_any"]) is False


# --------------------------------------------------------------------------- #
# unit labels present; ADC never relabeled MeV
# --------------------------------------------------------------------------- #

def test_unit_labels_keep_adc_and_mev_distinct():
    assert de.UNIT_LABELS["deltaE_data_adc"] == "ADC"
    assert de.UNIT_LABELS["E_data_adc"] == "ADC"
    assert de.UNIT_LABELS["deltaE_mc_mev"] == "MeV"
    assert de.UNIT_LABELS["E_mc_4layer_mev"] == "MeV"
    # data-side derived columns are ADC-suffixed, never *_mev
    data = de.derive_data_columns(de.fill_missing_flags(
        de.fill_missing_layers(pd.DataFrame([_data_row("runA", 1, (500, 300, 200, 90))]),
                               de.FILLABLE_DATA_LAYERS),
        de.DATA_SAT_COLS))
    assert "deltaE_data_adc" in data.columns and "E_data_adc" in data.columns
    assert not any(c.endswith("_mev") for c in ["deltaE_data_adc", "E_data_adc"])
    # mc-side derived columns are MeV-suffixed, never *_adc
    mc = de.derive_mc_columns(pd.DataFrame([_mc_row("runA", 1, (1.5, 0.6, 0.3, 0.05))]))
    assert "deltaE_mc_mev" in mc.columns and "E_mc_4layer_mev" in mc.columns
    assert "E_mc_full_mev" in mc.columns
    assert not any("adc" in c for c in ["deltaE_mc_mev", "E_mc_4layer_mev", "E_mc_full_mev"])


def test_mc_full_includes_deep_layers():
    mc = pd.DataFrame([{
        "source_file_id": "sf0", "run_id": "runA", "event_id": 1,
        "edep_B2": 1.5, "edep_B4": 0.6, "edep_B6": 0.3, "edep_B8": 0.1,
        "edep_B10": 0.4, "edep_B12": 0.2,
    }])
    out = de.derive_mc_columns(mc)
    assert np.isclose(out.iloc[0]["E_mc_4layer_mev"], 0.6 + 0.3 + 0.1)
    assert np.isclose(out.iloc[0]["E_mc_full_mev"], 0.6 + 0.3 + 0.1 + 0.4 + 0.2)


# --------------------------------------------------------------------------- #
# fixture + end-to-end analyze()  and  CLI
# --------------------------------------------------------------------------- #

def test_fixture_has_cross_run_and_empty_event():
    data, mc = fix.build_tables(n_per_run=50, seed=123)
    # event_id 5 exists in both runs (cross-run reuse)
    runs_for_5 = set(data.loc[data["event_id"] == 5, "run_id"])
    assert runs_for_5 == {"runA", "runB"}
    # composite key unique though event_id repeats
    assert not data.duplicated(list(de.KEY_COLS)).any()
    # known all-zero event present
    empty = data[(data["run_id"] == "runA") & (data["event_id"] == 0)]
    assert (empty[[f"amp_{b}" for b in de.DATA_LAYERS]].to_numpy() < 20).all()
    # fixture is deterministic
    data2, _ = fix.build_tables(n_per_run=50, seed=123)
    pd.testing.assert_frame_equal(data, data2)


def test_analyze_end_to_end_invariants():
    data, mc = fix.build_tables(n_per_run=400, seed=7)
    bundle = de.analyze(
        data, mc,
        stop_thresholds=(0.05, 0.15, 0.30),
        data_thresholds=(20.0, 40.0, 80.0),
        sample="all", seed=7,
    )
    r = bundle["result"]
    assert r["status"] == "PASS"
    assert r["stopping"]["data_adc"]["monotonic_reach"] is True
    assert r["stopping"]["mc_mev"]["monotonic_reach"] is True
    assert r["sample_counts"]["sample_I_subset_of_II"] is True
    assert r["join_cardinality"]["cross_run_collision"] is False
    assert r["join_cardinality"]["n_matched"] == len(data)
    assert r["saturation"]["any_saturation_events"] >= 1
    # all-zero downstream event resolves to explicit no-reach category
    assert r["stopping"]["data_adc"]["distributions"][0]["n_no_layer_passes"] >= 1
    assert de.NO_REACH_CATEGORY in bundle["data"]["deepest_active_stave"].values


def test_cli_full_run(tmp_path):
    # generate fixture via its CLI
    fdir = tmp_path / "fixture"
    rc = fix.main(["--out-dir", str(fdir), "--n-per-run", "300", "--seed", "9"])
    assert rc == 0
    data_tbl = fdir / "deltaE_data.parquet"
    mc_tbl = fdir / "deltaE_mc.parquet"

    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/single_stave/deltaE_E.py"),
         "--data-table", str(data_tbl), "--mc-table", str(mc_tbl),
         "--out", str(out), "--stop-thresholds", "0.05,0.15,0.30",
         "--data-thresholds", "20,40,80", "--seed", "9"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr

    for rel in [
        "deltaE_E_events_data.parquet", "deltaE_E_events_mc.parquet",
        "result.json", "manifest.json",
        "figures/deltaE_E_data_adc.png", "figures/deltaE_E_data_adc.pdf",
        "figures/deltaE_E_mc_mev.png", "figures/deltaE_E_mc_mev.pdf",
        "tables/deltaE_E_data_adc_profile.csv", "tables/deltaE_E_mc_mev_profile.csv",
    ]:
        assert (out / rel).exists(), f"missing output {rel}"

    result = json.loads((out / "result.json").read_text())
    assert result["status"] == "PASS"
    assert result["unit_labels"]["deltaE_data_adc"] == "ADC"
    assert result["unit_labels"]["deltaE_mc_mev"] == "MeV"
    assert result["sample_counts"]["sample_I_subset_of_II"] is True
    assert result["join_cardinality"]["cross_run_collision"] is False

    # written data event table carries ADC units + saturation flags, no MeV column
    dtbl = pd.read_parquet(out / "deltaE_E_events_data.parquet")
    assert "deltaE_data_adc" in dtbl.columns and "E_data_adc" in dtbl.columns
    assert "saturated_any" in dtbl.columns
    assert not any(c.endswith("_mev") for c in dtbl.columns)
    mtbl = pd.read_parquet(out / "deltaE_E_events_mc.parquet")
    assert "E_mc_full_mev" in mtbl.columns
    assert not any(c.endswith("_adc") for c in mtbl.columns)


def test_cli_nonzero_exit_on_bad_table(tmp_path):
    # data table missing a required column (amp_B2) -> nonzero exit
    bad = tmp_path / "bad.csv"
    pd.DataFrame([{
        "source_file_id": "sf0", "run_id": "runA", "event_id": 1,
        "sample": "II", "trigger_definition": "t",
    }]).to_csv(bad, index=False)
    good_mc = tmp_path / "mc.csv"
    pd.DataFrame([_mc_row("runA", 1, (1.5, 0.6, 0.3, 0.05))]).to_csv(good_mc, index=False)

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/single_stave/deltaE_E.py"),
         "--data-table", str(bad), "--mc-table", str(good_mc), "--out", str(tmp_path / "o")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert proc.returncode != 0


def test_cli_help_runs():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/single_stave/deltaE_E.py"), "--help"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "--stop-thresholds" in proc.stdout
    assert "--data-thresholds" in proc.stdout



# --------------------------------------------------------------------------- #
# Wave A / Lane 06: #1022 #1024 #1025 #1028 #1030 #1048
# --------------------------------------------------------------------------- #

def test_sample_tokens_rejects_lstrip_charset_false_positives():
    # Former bug: lstrip("SAMPLE") turned P1/L2 into I/II.
    assert de.sample_tokens("P1") == set()
    assert de.sample_tokens("L2") == set()
    assert de.sample_tokens("SAMPLE3") == set()
    assert de.sample_tokens("I") == {"I"}
    assert de.sample_tokens("II") == {"II"}
    assert de.sample_tokens("Sample I") == {"I"}
    assert de.sample_tokens("sample-II") == {"II"}
    assert de.sample_tokens("1") == {"I"}
    assert de.sample_tokens("2") == {"II"}
    assert de.sample_tokens("I;II") == {"I", "II"}


def test_parse_bool_flag_rejects_truthiness_trap():
    assert de.parse_bool_flag(False) is False
    assert de.parse_bool_flag("False") is False
    assert de.parse_bool_flag("false") is False
    assert de.parse_bool_flag("0") is False
    assert de.parse_bool_flag(True) is True
    assert de.parse_bool_flag("true") is True
    assert de.parse_bool_flag(1) is True
    assert de.parse_bool_flag(0) is False
    with pytest.raises(ValueError):
        de.parse_bool_flag("maybe")
    with pytest.raises(ValueError):
        de.parse_bool_flag("anything")
    df = pd.DataFrame({"saturation_B2": ["False", "true", 0, 1]})
    out = de.fill_missing_flags(df, ["saturation_B2"])
    assert out["saturation_B2"].tolist() == [False, True, False, True]


def test_parse_thresholds_rejects_nonfinite():
    with pytest.raises(ValueError, match="finite"):
        de.parse_thresholds("nan")
    with pytest.raises(ValueError, match="finite"):
        de.parse_thresholds("inf")
    with pytest.raises(ValueError, match="finite"):
        de.parse_thresholds("1,inf,2")
    with pytest.raises(ValueError, match="finite"):
        de.parse_thresholds("1e309")  # overflows to inf
    assert de.parse_thresholds("0,20,40") == (0.0, 20.0, 40.0)


def test_threshold_comparison_is_strict_greater():
    values = np.array([[20.0, 0.0, 0.0, 0.0]])
    # Exact equality must NOT pass under unified ">" rule (#1048).
    assert de.stopping_layers(values, 20.0)[0] == -1
    assert de.stopping_layers(values, 19.0)[0] == 0
    assert de.passes_threshold(20.0, 20.0) == False
    assert bool(de.passes_threshold(20.1, 20.0)) is True


def test_deepest_active_stave_naming():
    data = pd.DataFrame([_data_row("runA", 1, (500, 0, 0, 0))])
    mc = pd.DataFrame([_mc_row("runA", 1, (1.0, 0.0, 0.0, 0.0))])
    bundle = de.analyze(data, mc, (0.05,), (20.0,), "all", 1)
    assert "deepest_active_stave" in bundle["data"].columns
    assert "deepest_edep_layer" in bundle["mc"].columns
    assert "stop_layer" not in bundle["data"].columns
    assert "stop_layer" not in bundle["mc"].columns
    assert bundle["result"]["measurand_names"]["data_deepest_proxy"] == "deepest_active_stave"


def test_mc_weights_change_reach_fractions():
    # Two events: only the second reaches B8. Heavy weight on the second must
    # dominate weighted reach (#1022).
    data = pd.DataFrame([
        _data_row("runA", 1, (500, 0, 0, 0)),
        _data_row("runA", 2, (500, 300, 200, 100)),
    ])
    mc = pd.DataFrame([
        _mc_row("runA", 1, (1.0, 0.0, 0.0, 0.0), weight=1.0),
        _mc_row("runA", 2, (1.0, 0.5, 0.4, 0.3), weight=100.0),
    ])
    bundle = de.analyze(data, mc, (0.05,), (20.0,), "all", 1)
    wdiag = bundle["result"]["mc_weights"]
    assert wdiag["sum_w"] == pytest.approx(101.0)
    assert wdiag["weight_variable"] == "PrimaryWeight"
    reach_b8 = bundle["result"]["stopping"]["mc_mev"]["distributions"][0]["reach_by_layer"]["B8"]
    # Unweighted would be 0.5; weighted ≈ 100/101.
    assert reach_b8 == pytest.approx(100.0 / 101.0)
    # Equal weights recover the unweighted fraction.
    mc2 = mc.copy()
    mc2["PrimaryWeight"] = 1.0
    bundle2 = de.analyze(data, mc2, (0.05,), (20.0,), "all", 1)
    reach2 = bundle2["result"]["stopping"]["mc_mev"]["distributions"][0]["reach_by_layer"]["B8"]
    assert reach2 == pytest.approx(0.5)


def test_mc_negative_weight_rejected():
    data = pd.DataFrame([_data_row("runA", 1, (500, 0, 0, 0))])
    mc = pd.DataFrame([_mc_row("runA", 1, (1.0, 0.0, 0.0, 0.0), weight=-1.0)])
    with pytest.raises(SystemExit, match="negative"):
        de.prepare_mc_side(mc)


def test_mc_missing_weight_rejected():
    data = pd.DataFrame([_data_row("runA", 1, (500, 0, 0, 0))])
    mc = pd.DataFrame([_mc_row("runA", 1, (1.0, 0.0, 0.0, 0.0))])
    mc = mc.drop(columns=["PrimaryWeight"])
    with pytest.raises(SystemExit, match="weight"):
        de.prepare_mc_side(mc)

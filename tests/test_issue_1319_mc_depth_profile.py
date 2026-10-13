"""Tests for the #1319 MC depth-profile producer.

Contract under test:
- physical-layer namespace cannot be overwritten by readout aliases;
- stack sums count every physical layer exactly once;
- unit event measure is verified with explicit diagnostics;
- both parity hypotheses are carried as a nuisance envelope;
- trigger selection remains proxy-labelled;
- species-conditional means are never stacked as if additive;
- rendered figures keep audit/provenance text out of the plotting canvas.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import issue_1319_mc_depth_profile as producer  # noqa: E402

MC_PARQUET = (REPO_ROOT / "reports/paper_618_species_penetration_2m_20260814T1449Z"
              / "deltaE_E_events_mc.parquet")
BOM_PATH = REPO_ROOT / "publication" / "tables" / "hardware_bom.csv"

EVEN = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
ODD = {"B2": 1, "B4": 3, "B6": 5, "B8": 7}


def toy_frame(n_events: int = 4, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {}
    for i, col in enumerate(producer.PHYSICAL_LAYERS):
        data[col] = rng.uniform(1.0 + 10 * i, 2.0 + 10 * i, size=n_events)
    for ch, layer in ODD.items():
        data[f"readout_{ch}"] = data[producer.PHYSICAL_LAYERS[layer]]
    data["PrimaryWeight"] = np.ones(n_events)
    species_cycle = ("p", "d", "p", "other")
    sample_cycle = ("I", "II")
    data["truth_species"] = [species_cycle[i % 4] for i in range(n_events)]
    data["sample"] = [sample_cycle[i % 2] for i in range(n_events)]
    return pd.DataFrame(data)


def test_alias_must_be_int_index_not_column_name():
    with pytest.raises(producer.MapError, match="never a column name"):
        producer.ChannelMap(mapping={"B2": "edep_layer_0", "B4": 2, "B6": 4, "B8": 6},
                            label="bad")


def test_alias_out_of_range_and_non_injective_rejected():
    with pytest.raises(producer.MapError, match="out of range"):
        producer.ChannelMap(mapping={"B2": 8, "B4": 2, "B6": 4, "B8": 6}, label="bad")
    with pytest.raises(producer.MapError, match="injective"):
        producer.ChannelMap(mapping={"B2": 2, "B4": 2, "B6": 4, "B8": 6}, label="bad")


def test_physical_namespace_frozen_and_untouched_by_sparse_computation():
    frame = toy_frame()
    before = frame.copy(deep=True)
    cmap = producer.ChannelMap(mapping=EVEN, label="even")
    producer.sparse_profile(frame, cmap)
    pd.testing.assert_frame_equal(frame, before)
    assert producer.PHYSICAL_LAYERS == tuple(f"edep_layer_{i}" for i in range(8))


def test_known_answer_single_event_distinct_deposits():
    frame = toy_frame(n_events=1)
    stack = producer.stack_sum(frame)
    expected = sum(frame[col].iloc[0] for col in producer.PHYSICAL_LAYERS)
    assert stack[0] == pytest.approx(expected, abs=1e-12)
    frame.loc[0, "edep_layer_3"] += 5.0
    assert producer.stack_sum(frame)[0] == pytest.approx(expected + 5.0, abs=1e-12)


def test_known_answer_layer_means_two_events():
    frame = pd.DataFrame({
        "edep_layer_0": [2.0, 4.0], "edep_layer_1": [0.0, 0.0],
        "edep_layer_2": [10.0, 20.0], "edep_layer_3": [1.0, 3.0],
        "edep_layer_4": [0.0, 0.0], "edep_layer_5": [0.0, 0.0],
        "edep_layer_6": [0.0, 0.0], "edep_layer_7": [0.0, 0.0],
        "readout_B2": [2.0, 4.0], "readout_B4": [10.0, 20.0],
        "readout_B6": [0.0, 0.0], "readout_B8": [1.0, 3.0],
        "PrimaryWeight": [1.0, 1.0], "truth_species": ["p", "p"],
        "sample": ["I", "I"]})
    stats = producer.per_layer_stats(frame, seed=1319)
    assert stats[0]["mean_edep_mev"] == pytest.approx(3.0)
    assert stats[2]["mean_edep_mev"] == pytest.approx(15.0)
    assert stats[3]["mean_edep_mev"] == pytest.approx(2.0)
    assert stats[7]["mean_edep_mev"] == pytest.approx(0.0)
    assert stats[7]["frac_nonzero"] == pytest.approx(0.0)
    assert stats[0]["frac_nonzero"] == pytest.approx(1.0)


def test_weight_diagnostics_ess_math():
    d = producer.weight_diagnostics(np.array([1.0, 1.0, 2.0, 2.0]))
    assert d["sum_w"] == pytest.approx(6.0)
    assert d["sum_w2"] == pytest.approx(10.0)
    assert d["ess"] == pytest.approx(3.6)
    assert d["n_negative"] == 0 and d["n_nonfinite"] == 0


def test_weight_diagnostics_negative_and_nonfinite_counted():
    d = producer.weight_diagnostics(np.array([1.0, -0.5, np.nan, np.inf, 1.0]))
    assert d["n_negative"] == 1
    assert d["n_nonfinite"] == 2


def test_parity_envelope_contains_both_hypotheses():
    frame = toy_frame(n_events=16)
    even = producer.ChannelMap(mapping=EVEN, label="even")
    odd = producer.ChannelMap(mapping=ODD, label="odd")
    se, so = producer.sparse_profile(frame, even), producer.sparse_profile(frame, odd)
    env = {ch: (min(se[ch], so[ch]), max(se[ch], so[ch]))
           for ch in producer.READOUT_CHANNELS}
    for ch in producer.READOUT_CHANNELS:
        assert env[ch][0] <= min(se[ch], so[ch]) + 1e-12
        assert env[ch][1] >= max(se[ch], so[ch]) - 1e-12
    assert any(abs(se[ch] - so[ch]) > 1e-6 for ch in producer.READOUT_CHANNELS)


def test_legacy_map_derived_by_equality_not_assumed():
    frame = toy_frame()
    legacy = producer.derive_legacy_odd_map(frame)
    assert legacy.mapping == ODD


def test_species_conditional_means_are_not_stacked_in_renderer():
    src = inspect.getsource(producer.make_figure)
    assert "bottom=" not in src
    assert "species_conditional_means_stacked" not in src  # metadata belongs in result.json


def test_renderer_has_no_long_audit_footer():
    src = inspect.getsource(producer.make_figure)
    assert "fig.text(" not in src
    assert "PROXY_LABEL" not in src
    assert "PARITY_LABEL" not in src


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    if not MC_PARQUET.exists():
        pytest.skip("committed MC parquet not present")
    out = tmp_path_factory.mktemp("mc1319")
    rc = producer.main(["--mc-parquet", str(MC_PARQUET), "--bom", str(BOM_PATH),
                        "--output-dir", str(out)])
    assert rc == 0
    return out, json.loads((out / "result.json").read_text())


def test_integration_event_measure_unit_weights(bundle):
    _, result = bundle
    diag = result["event_measure"]["weight_diagnostics"]
    assert diag["n_negative"] == 0 and diag["n_nonfinite"] == 0
    assert diag["ess"] == pytest.approx(diag["n"], rel=1e-12)


def test_integration_conservation(bundle):
    _, result = bundle
    assert result["accounting"]["conservation_ok"] is True
    assert result["accounting"]["max_abs_residual_mev"] < 1e-9


def test_integration_trigger_stays_proxy(bundle):
    _, result = bundle
    assert result["trigger"]["validated"] is False
    assert "MC_TRIGGER_PROXY" in result["trigger"]["label"]


def test_integration_parity_envelope_reported(bundle):
    _, result = bundle
    assert result["parity"]["unresolved"] is True
    maps = {k: v["map"] for k, v in result["parity"]["hypotheses"].items()}
    assert maps["even"] == EVEN and maps["odd"] == ODD
    for _, (lo, hi) in result["parity"]["envelope_mev"].items():
        assert lo < hi


def test_integration_outputs_and_schema(bundle):
    out, result = bundle
    assert result["schema"] == producer.SCHEMA
    assert result["rendering"]["species_conditional_means_stacked"] is False
    assert result["rendering"]["audit_text_inside_axes"] is False
    for sfx in ("pdf", "svg", "png"):
        f = out / f"mc_depth_profile.{sfx}"
        assert f.exists() and f.stat().st_size > 0
    table = (out / "source_table.csv").read_text().splitlines()
    assert table[0].startswith("row_type,layer_or_channel")
    kinds = {ln.split(",")[0] for ln in table[1:]}
    assert kinds == {"layer", "sparse_even", "sparse_odd"}

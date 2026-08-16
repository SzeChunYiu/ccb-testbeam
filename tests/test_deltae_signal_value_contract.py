from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reload_module():
    for name in [
        "scripts.single_stave.deltaE_E",
        "scripts.single_stave._deltaE_E_core",
    ]:
        sys.modules.pop(name, None)
    return importlib.import_module("scripts.single_stave.deltaE_E")


def _data(**updates):
    row = {
        "source_file_id": "001",
        "run_id": "runA",
        "event_id": "1",
        "amp_B2": 100.0,
        "amp_B4": 40.0,
        "amp_B6": 20.0,
        "amp_B8": 10.0,
        "sample": "II",
        "trigger_definition": "beam_v1",
    }
    row.update(updates)
    return pd.DataFrame([row])


def _mc(**updates):
    row = {
        "source_file_id": "001",
        "run_id": "runA",
        "event_id": "1",
        "edep_B2": 1.0,
        "edep_B4": 0.4,
        "edep_B6": 0.2,
        "edep_B8": 0.1,
        "edep_B10": 0.05,
        # Unit PrimaryWeight required by ΔE–E MC weight contract (#880/#1022).
        "PrimaryWeight": 1.0,
    }
    row.update(updates)
    return pd.DataFrame([row])


@pytest.mark.parametrize("bad", ["bad", None, np.nan, np.inf, -np.inf])
def test_present_data_signal_cells_fail_closed(bad):
    de = _reload_module()
    with pytest.raises(de.SignalValueError, match="amp_B4"):
        de.prepare_data_side(_data(amp_B4=bad))


@pytest.mark.parametrize("column,bad", [
    ("edep_B2", "bad"),
    ("edep_B8", np.nan),
    ("edep_B10", np.inf),
    ("edep_B10", -np.inf),
])
def test_every_present_mc_layer_fails_closed(column, bad):
    de = _reload_module()
    with pytest.raises(de.SignalValueError, match=column):
        de.prepare_mc_side(_mc(**{column: bad}))


def test_wholly_absent_supported_layer_is_still_zero_filled():
    de = _reload_module()
    data = de.prepare_data_side(_data().drop(columns=["amp_B8"]))
    mc = de.prepare_mc_side(_mc().drop(columns=["edep_B8"]))
    assert data.loc[0, "amp_B8"] == 0.0
    assert mc.loc[0, "edep_B8"] == 0.0
    assert data.loc[0, "E_data_adc"] == 60.0
    assert mc.loc[0, "E_mc_4layer_mev"] == pytest.approx(0.6)


def test_finite_numeric_strings_are_coerced_without_changing_values():
    de = _reload_module()
    data = de.prepare_data_side(_data(amp_B2="100.5", amp_B4="40.25"))
    mc = de.prepare_mc_side(_mc(edep_B2="1.25", edep_B10="0.125"))
    assert data.loc[0, "deltaE_data_adc"] == 100.5
    assert data.loc[0, "amp_B4"] == 40.25
    assert mc.loc[0, "deltaE_mc_mev"] == 1.25
    assert mc.loc[0, "edep_B10"] == 0.125


def test_contract_is_published_in_result_and_manifest(tmp_path):
    de = _reload_module()
    bundle = de.analyze(_data(), _mc(), [0.05], [20.0], "all", 7)
    contract = bundle["result"]["input_reader_contract"]
    assert contract["signal_value_policy"] == de.SIGNAL_VALUE_POLICY
    assert contract["missing_layer_policy"] == de.MISSING_LAYER_POLICY

    data_path = tmp_path / "data.csv"
    mc_path = tmp_path / "mc.csv"
    data_path.write_text("x\n1\n", encoding="utf-8")
    mc_path.write_text("x\n1\n", encoding="utf-8")
    de._retain_snapshot(
        data_path,
        data_path.read_bytes(),
        table_format="csv",
        snapshot_policy=de.CSV_SNAPSHOT_POLICY,
    )
    de._retain_snapshot(
        mc_path,
        mc_path.read_bytes(),
        table_format="csv",
        snapshot_policy=de.CSV_SNAPSHOT_POLICY,
    )
    out = tmp_path / "out"
    out.mkdir()
    args = type(
        "Args",
        (),
        {
            "data_table": data_path,
            "mc_table": mc_path,
            "out": out,
            "stop_thresholds": "0.05",
            "data_thresholds": "20",
            "sample": "all",
            "seed": 7,
            "bins": 16,
        },
    )()
    de.write_manifest(out, args, [data_path, mc_path])
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["input_reader_contract"]["signal_value_policy"] == de.SIGNAL_VALUE_POLICY
    assert manifest["input_reader_contract"]["missing_layer_policy"] == de.MISSING_LAYER_POLICY


def test_core_production_hooks_are_replaced():
    de = _reload_module()
    assert de._core.fill_missing_layers is de.fill_missing_layers
    assert de._core.prepare_data_side is de.prepare_data_side
    assert de._core.prepare_mc_side is de.prepare_mc_side


def test_error_reports_count_and_first_row_indices():
    de = _reload_module()
    data = pd.concat(
        [
            _data(amp_B4="bad"),
            _data(amp_B4=np.inf).assign(event_id="2"),
        ],
        ignore_index=True,
    )
    with pytest.raises(de.SignalValueError) as caught:
        de.prepare_data_side(data)
    text = str(caught.value)
    assert "2 nonnumeric or nonfinite value(s)" in text
    assert "['0', '1']" in text

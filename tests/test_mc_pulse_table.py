"""Tests for scripts/mc02_build_mc_pulse_table.py (Phase 1 MC pulse table).

Synthetic fixture: two events with hits in two staves each. Asserts
per-(event, stave) grouping, the DATA sign convention (positive amplitude
after baseline subtraction), sample_I/II flag propagation, both LayerID
mappings, and that zero-signal records carry noise-scale amplitudes.
"""

from __future__ import annotations

import gzip
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mc02 = _load_script("mc02_build_mc_pulse_table", ROOT / "scripts" / "mc02_build_mc_pulse_table.py")

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline, load_digitizer_card

CARD = load_digitizer_card(ROOT / "configs" / "mc_validation" / "digitizer_card.yaml")


def _jag(*event_lists, dtype):
    return np.array([np.asarray(e, dtype=dtype) for e in event_lists], dtype=object)


@pytest.fixture()
def two_event_chunk():
    """Event 0: proton in B2 (layers 0+1) and B4 (layer 2), A+B coincidence
    (sample I and II). Event 1: deuteron entering at layer 0 (B2) and
    depositing in B6 (layer 5) and B8 (layer 6), B-only (sample II, not I).
    A-arm rows use LayerID1=2 and restart LayerID at 0."""
    return {
        # ev0: B layers 0,1,2 + A layer 0 (coincident, t within 15 ns)
        # ev1: B layers 0,5,6 (charged layer-0 entry -> sample II)
        "Sci_bar_LayerID": _jag([0, 1, 2, 0], [0, 5, 6], dtype=np.int32),
        "Sci_bar_LayerID1": _jag([1, 1, 1, 2], [1, 1, 1], dtype=np.int32),
        "Sci_bar_PDG": _jag(
            [2212, 2212, 2212, 2212],
            [1000010020, 1000010020, 1000010020],
            dtype=np.int64,
        ),
        "Sci_bar_EDep": _jag([12.0, 8.0, 5.0, 2.0], [15.0, 20.0, 6.0], dtype=np.float64),
        "Sci_bar_Time": _jag([0.0, 1.0, 2.0, 3.0], [0.0, 4.0, 5.5], dtype=np.float64),
        "Sci_bar_TrackID": _jag([1, 1, 1, 1], [1, 1, 1], dtype=np.int64),
    }


def _rows(chunk, mapping="paired", offset=0):
    pipelines = mc02.build_stave_pipelines(CARD)
    return mc02.process_truth_chunk(chunk, event_offset=offset, pipelines=pipelines, mapping=mapping)


def test_per_stave_grouping(two_event_chunk):
    rows = _rows(two_event_chunk)
    keyed = {(r[2], r[4]): r for r in rows}
    # ev0 -> B2 (layers 0+1 summed) and B4 (layer 2);
    # ev1 -> B2 (entry), B6 (layer 5) and B8 (layer 6)
    assert set(keyed) == {(0, "B2"), (0, "B4"), (1, "B2"), (1, "B6"), (1, "B8")}
    # pair-summed edep in B2 = 12 + 8
    assert keyed[(0, "B2")][11] == pytest.approx(20.0)
    assert keyed[(0, "B4")][11] == pytest.approx(5.0)
    assert keyed[(1, "B6")][11] == pytest.approx(20.0)
    # channels follow the data even-channel convention
    assert keyed[(0, "B2")][5] == 0
    assert keyed[(1, "B8")][5] == 6


def test_sign_convention_amplitude_positive(two_event_chunk):
    rows = _rows(two_event_chunk)
    noise = float(CARD["digitizer"]["noise_adc_rms"])
    for r in rows:
        baseline, amplitude = r[6], r[7]
        # baseline sits at the hardware pedestal, amplitude is net-positive
        assert amplitude > 10 * noise, f"{r[4]}: amplitude {amplitude} not signal-like"
        assert abs(baseline - CARD["digitizer"]["pedestal_adc"]) < 10 * noise
        # area positive, peak inside the window and after the baseline samples
        assert r[9] > 0
        assert 3 < r[8] < CARD["digitizer"]["n_samples"]


def test_sample_flags_propagate(two_event_chunk):
    rows = _rows(two_event_chunk)
    by_event = {}
    for r in rows:
        by_event.setdefault(r[2], set()).add((r[13], r[14]))
    # event 0: charged B entry + coincident A entry -> sample I and II
    assert by_event[0] == {(1, 1)}
    # event 1: B entry, no A -> sample II only
    assert by_event[1] == {(0, 1)}


def test_truth_columns(two_event_chunk):
    rows = _rows(two_event_chunk)
    keyed = {(r[2], r[4]): r for r in rows}
    assert keyed[(0, "B2")][10] == 2212
    assert keyed[(1, "B6")][10] == 1000010020
    # stop_layer / contained are event-level
    assert keyed[(0, "B2")][12] == 2 and keyed[(0, "B2")][16] == 1
    assert keyed[(1, "B8")][12] == 6 and keyed[(1, "B8")][16] == 1
    # n_tracks per stave
    assert all(r[15] == 1 for r in rows)
    # s00 schema constants
    assert all(r[0] == 0 and r[1] == "mc" for r in rows)


def test_event_offset_and_seed_determinism(two_event_chunk):
    rows_a = _rows(two_event_chunk, offset=0)
    rows_b = _rows(two_event_chunk, offset=0)
    assert rows_a == rows_b  # per-channel (event, stave-index) seeding is reproducible
    rows_c = _rows(two_event_chunk, offset=1000)
    assert [r[2] for r in rows_c] == [r[2] + 1000 for r in rows_a]
    # different event ids -> different noise realisations
    assert rows_c[0][6:10] != rows_a[0][6:10]


def test_odd_mapping_drops_odd_layers(two_event_chunk):
    rows = _rows(two_event_chunk, mapping="odd")
    keyed = {(r[2], r[4]): r for r in rows}
    # ev0: layer 1 dropped -> B2 sees only 12 MeV; ev1: layer 5 dropped -> no B6 row
    assert set(keyed) == {(0, "B2"), (0, "B4"), (1, "B2"), (1, "B8")}
    assert keyed[(0, "B2")][11] == pytest.approx(12.0)


def test_zero_signal_records_are_noise_scale(tmp_path):
    out = tmp_path / "zero.csv.gz"
    n_samples = int(CARD["digitizer"]["n_samples"])
    meta = mc02.generate_zero_signal(CARD, 64, out, n_samples)
    assert meta["n_records"] == 64
    noise = float(CARD["digitizer"]["noise_adc_rms"])
    lo, hi = mc02.ZERO_SIGNAL_PED_RANGE
    with gzip.open(out, "rt", encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        assert header[:6] == ["record_id", "stave", "channel", "pedestal_true_adc", "baseline_adc", "amplitude_adc"]
        assert len(header) == 6 + n_samples
        amplitudes, peds = [], []
        for line in handle:
            parts = line.strip().split(",")
            peds.append(float(parts[3]))
            amplitudes.append(float(parts[5]))
    assert len(amplitudes) == 64
    amplitudes = np.asarray(amplitudes)
    # amplitude ~ noise scale: positive-ish max of 18 noise samples, << any signal
    assert np.median(amplitudes) < 5 * noise
    assert np.all(amplitudes < 12 * noise)
    assert all(lo <= p <= hi for p in peds)


def test_from_config_reads_card_per_stave():
    for stave, tau in (("B2", 56.7), ("B4", 51.7), ("B6", 49.4), ("B8", 50.1)):
        pipe = DigitizerPipeline.from_config(CARD, stave=stave)
        assert pipe.tau_decay_ns == pytest.approx(tau)
        assert pipe.tau_rise_ns == pytest.approx(2.5)
        assert pipe.electronics.pedestal_adc == pytest.approx(6752.0)
        assert pipe.electronics.noise_adc_rms == pytest.approx(8.0)
        assert pipe.electronics.adc_ceiling == 21247
    with pytest.raises(KeyError):
        DigitizerPipeline.from_config(CARD, stave="B99")


# --------------------------------------------------------------------------
# Phase 4: A-arm digitization and per-hit dE/dx (Birks) wiring
# --------------------------------------------------------------------------

def test_a_arm_rows(two_event_chunk):
    pipelines = mc02.build_stave_pipelines(CARD, mc02.A_STAVES)
    rows = mc02.process_truth_chunk(
        two_event_chunk, event_offset=0, pipelines=pipelines, mapping="paired", arm="A"
    )
    keyed = {(r[2], r[4]): r for r in rows}
    # only event 0 has an A-arm deposit (LayerID1==2, LayerID 0 -> A1)
    assert set(keyed) == {(0, "A1")}
    r = keyed[(0, "A1")]
    assert r[5] == 0                      # A1 channel convention
    assert r[11] == pytest.approx(2.0)    # A-arm edep only
    assert r[12] == 0                     # deepest A layer
    assert r[16] == 1                     # contained (stop_layer < 3)
    # sample flags are event-level and unchanged by the arm
    assert (r[13], r[14]) == (1, 1)


def test_a_arm_card_has_default_tau():
    for stave in mc02.A_STAVES:
        pipe = DigitizerPipeline.from_config(CARD, stave=stave)
        assert pipe.tau_decay_ns == pytest.approx(50.0)  # DEFAULT, no data fit


@pytest.fixture()
def dedx_chunk():
    """One event: a through-going proton (cumulative TrackLength ~112 cm,
    2 cm steps) and a locally created C12 recoil (TrackLength = its ~20 um
    range) in the same B2 stave."""
    return {
        "Sci_bar_LayerID": _jag([0, 0, 1], dtype=np.int32),
        "Sci_bar_LayerID1": _jag([1, 1, 1], dtype=np.int32),
        "Sci_bar_PDG": _jag([2212, 1000060120, 2212], dtype=np.int64),
        "Sci_bar_EDep": _jag([4.0, 3.0, 4.0], dtype=np.float64),
        "Sci_bar_Time": _jag([0.0, 0.5, 1.0], dtype=np.float64),
        "Sci_bar_TrackID": _jag([1, 2, 1], dtype=np.int64),
        # proton: cumulative 112 -> 114 cm (step 2 cm -> dE/dx = 2 MeV/cm);
        # C12 recoil: born in the bar, cumulative length 0.002 cm = its step
        "Sci_bar_TrackLength": _jag([112.0, 0.002, 114.0], dtype=np.float64),
        # GeV/c momenta: proton 0.55 GeV/c ~ 150 MeV ekin; C12 slow recoil
        "Sci_bar_Momentum_X": _jag([0.55, 0.26, 0.50], dtype=np.float64),
        "Sci_bar_Momentum_Y": _jag([0.0, 0.0, 0.0], dtype=np.float64),
        "Sci_bar_Momentum_Z": _jag([0.0, 0.0, 0.0], dtype=np.float64),
    }


def test_per_hit_dedx_step_lengths(dedx_chunk):
    pipelines = mc02.build_stave_pipelines(CARD)
    rows = mc02.process_truth_chunk(
        dedx_chunk, event_offset=0, pipelines=pipelines, mapping="paired"
    )
    assert len(rows) == 1
    r = rows[0]
    # dedx_max column: C12 recoil dominates = 3.0 MeV / 0.002 cm = 1500 MeV/cm
    assert r[17] == pytest.approx(1500.0, rel=1e-6)


def test_per_hit_dedx_first_hit_of_long_track_uses_lookup():
    # single proton hit with cumulative TrackLength 112 cm (> FIRST_STEP_MAX_CM):
    # the raw length is NOT a step; the species+energy lookup must be used
    trk = np.array([1]); tl = np.array([112.0])
    edep = np.array([4.0]); pdg = np.array([2212])
    ekin = np.array([150.0])
    dedx = mc02.per_hit_dedx(trk, tl, edep, pdg, ekin)
    from ccb_mc_validation.digitizer.birks import dedx_polystyrene_mev_per_cm
    assert dedx[0] == pytest.approx(dedx_polystyrene_mev_per_cm(2212, 150.0))


def test_quenching_suppresses_c12_amplitude(dedx_chunk):
    import copy
    card_on = copy.deepcopy(CARD)
    card_on["digitizer"]["apply_birks"] = True
    card_off = copy.deepcopy(CARD)
    card_off["digitizer"]["apply_birks"] = False
    row_on = mc02.process_truth_chunk(
        dedx_chunk, event_offset=0, pipelines=mc02.build_stave_pipelines(card_on),
        mapping="paired",
    )[0]
    row_off = mc02.process_truth_chunk(
        dedx_chunk, event_offset=0, pipelines=mc02.build_stave_pipelines(card_off),
        mapping="paired",
    )[0]
    # same seeds/noise -> the only difference is the quench; ON must be smaller
    assert row_on[7] < row_off[7]


def test_backward_compat_without_tracklength(two_event_chunk):
    # no TrackLength/momentum branches: species-lookup fallback, no crash,
    # dedx_max column still populated and finite
    pipelines = mc02.build_stave_pipelines(CARD)
    rows = mc02.process_truth_chunk(
        two_event_chunk, event_offset=0, pipelines=pipelines, mapping="paired"
    )
    assert all(np.isfinite(r[17]) and r[17] > 0 for r in rows)

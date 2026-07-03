"""Smoke tests for scripts/s21_sample12_trigger_truth_comparison.py.

Synthetic jagged fixture exercising the script's record-building and
sample-routing logic:
  * Sample I is a subset of Sample II (inclusive definitions);
  * a pd-pair event (proton enters A layer 0, deuteron enters B layer 0
    within 15 ns) lands in BOTH samples;
  * a B-only event lands only in Sample II;
  * the deuteron fraction in B2 is computed correctly per sample.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import s21_sample12_trigger_truth_comparison as s21  # noqa: E402
from ccb_mc_validation.truth.trigger import process_chunk  # noqa: E402

PROTON = 2212
DEUTERON = 1000010020
COINC_NS = 15.0


def _jag(rows):
    out = np.empty(len(rows), dtype=object)
    for i, r in enumerate(rows):
        out[i] = np.asarray(r)
    return out


def _fixture_chunk() -> dict:
    """Three events:

    ev0 (pd pair): deuteron enters B layer 0 at t=10 ns depositing 110 MeV,
        proton enters A layer 0 at t=5 ns (|dt|=5 < 15) -> Samples I and II.
        Deuteron momentum 0.65 GeV/c -> ekin ~ 109.4 MeV (GeV->MeV check),
        so edep_tot=110 >= 0.8*ekin -> contained.
    ev1 (B only): proton enters B layer 0 (20 MeV) and reaches layer 3
        -> Sample II only.
    ev2 (A only): proton enters A layer 0 -> neither sample.
    """
    rows = {
        # (layer, arm, pdg, edep, time, tid, px, py, pz)
        "Sci_bar_LayerID": [[0, 0], [0, 3], [0]],
        "Sci_bar_LayerID1": [[1, 2], [1, 1], [2]],
        "Sci_bar_PDG": [[DEUTERON, PROTON], [PROTON, PROTON], [PROTON]],
        "Sci_bar_EDep": [[110.0, 30.0], [20.0, 15.0], [25.0]],
        "Sci_bar_Time": [[10.0, 5.0], [8.0, 9.0], [7.0]],
        "Sci_bar_TrackID": [[1, 2], [1, 1], [1]],
        "Sci_bar_Momentum_X": [[0.65, 0.4], [0.5, 0.3], [0.4]],
        "Sci_bar_Momentum_Y": [[0.0, 0.0], [0.0, 0.0], [0.0]],
        "Sci_bar_Momentum_Z": [[0.0, 0.0], [0.0, 0.0], [0.0]],
    }
    return {k: _jag(v) for k, v in rows.items()}


def _flags(chunk):
    return process_chunk(
        chunk["Sci_bar_LayerID"],
        chunk["Sci_bar_LayerID1"],
        chunk["Sci_bar_PDG"],
        chunk["Sci_bar_Time"],
        COINC_NS,
    )


def test_sample_i_is_subset_of_sample_ii() -> None:
    flags = _flags(_fixture_chunk())
    assert np.all(~flags["sample_I"] | flags["sample_II"])


def test_pd_pair_event_lands_in_both_samples() -> None:
    flags = _flags(_fixture_chunk())
    assert bool(flags["sample_I"][0]) and bool(flags["sample_II"][0])


def test_b_only_event_lands_only_in_sample_ii() -> None:
    flags = _flags(_fixture_chunk())
    assert not flags["sample_I"][1]
    assert flags["sample_II"][1]
    # A-only event is in neither
    assert not flags["sample_I"][2]
    assert not flags["sample_II"][2]


def test_record_building_and_deuteron_fraction() -> None:
    chunk = _fixture_chunk()
    flags = _flags(chunk)
    acc_i = s21.SampleAccumulator()
    acc_ii = s21.SampleAccumulator()
    s21.process_chunk_events(chunk, flags, acc_i, acc_ii)

    assert acc_i.n_events == 1
    assert acc_ii.n_events == 2
    # Sample I sees only the deuteron B track; Sample II sees d + p
    assert acc_i.n_tracks == {"p": 0, "d": 1, "other": 0}
    assert acc_ii.n_tracks == {"p": 1, "d": 1, "other": 0}

    # deuteron fraction in B2 (stave 0): I -> 1/1, II -> 1/2
    key = s21.build_key_table(acc_i, acc_ii)
    b2 = key["staves"]["B2"]
    assert b2["sample_I"]["k_d"] == 1 and b2["sample_I"]["n"] == 1
    assert b2["sample_II"]["k_d"] == 1 and b2["sample_II"]["n"] == 2
    assert b2["sample_I"]["fraction"] == 1.0
    assert b2["sample_II"]["fraction"] == 0.5
    assert b2["enrichment_I_over_II_inclusive"]["ratio"] == 2.0

    # entry ekin uses GeV/c -> MeV/c conversion: |p|=650 MeV/c, m_d=1875.613
    tracks = s21.build_b_tracks(
        chunk["Sci_bar_LayerID"][0],
        chunk["Sci_bar_LayerID1"][0],
        chunk["Sci_bar_PDG"][0],
        chunk["Sci_bar_EDep"][0],
        chunk["Sci_bar_TrackID"][0],
        chunk["Sci_bar_Momentum_X"][0],
        chunk["Sci_bar_Momentum_Y"][0],
        chunk["Sci_bar_Momentum_Z"][0],
    )
    assert len(tracks) == 1
    d = tracks[0]
    assert d["species"] == "d"
    # sqrt(650^2 + 1875.613^2) - 1875.613 = 109.437 MeV
    assert abs(d["ekin"] - 109.44) < 0.05
    assert d["contained"] is True  # 110 >= 0.8 * 109.44
    assert d["deepest"] == 0

    # ev1 proton: deepest layer 3 (stave B4), occupies B2 and B4
    assert acc_ii.deepest["p"][3] == 1
    assert acc_ii.stave_occ["p"][0] == 1  # B2 (layer 0)
    assert acc_ii.stave_occ["p"][1] == 1  # B4 (layer 3)

    # pd-pair mechanism table: Sample I event is d into B, p into A
    assert acc_i.pair_table == {"d|p": 1}

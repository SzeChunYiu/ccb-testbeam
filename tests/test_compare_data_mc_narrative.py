"""Tests that compare_data_mc narrative is derived from fields (#1002)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import compare_data_mc as cmc


def test_narrative_tracks_input_fields():
    a = cmc._build_deltaE_E_narrative({
        "sampleI_d_fraction": 0.735,
        "sampleII_d_fraction": 0.20,
        "sampleI_mean_stop_layer": 0.8,
        "sampleII_mean_stop_layer": 4.3,
        "sampleI_pearson_r": 0.07,
        "sampleII_pearson_r": 0.50,
        "open_blockers": ["#956"],
    })
    assert a["causal_claim_authorised"] is False
    assert "0.070" in a["prose"] or "0.07" in a["prose"]
    assert "DIAGNOSTIC_ONLY" in a["prose"]
    assert "physics effect, not an analysis artifact" not in a["prose"]

    b = cmc._build_deltaE_E_narrative({
        "sampleI_d_fraction": 0.10,
        "sampleII_d_fraction": 0.90,
        "sampleI_mean_stop_layer": 3.0,
        "sampleII_mean_stop_layer": 1.0,
        "sampleI_pearson_r": 0.42,
        "sampleII_pearson_r": 0.11,
        "open_blockers": ["#956"],
    })
    assert "0.420" in b["prose"] or "0.42" in b["prose"]
    assert a["prose"] != b["prose"]


def test_source_has_no_hardcoded_causal_sentence():
    src = (REPO / "scripts/compare_data_mc.py").read_text(encoding="utf-8")
    assert "This is a physics effect, not an analysis artifact." not in src

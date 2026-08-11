"""Tests for frozen MV0 digitizer identity (#1078)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import validate_mv0_model_identity as v


def test_executable_matches_frozen_identity():
    assert v.validate(REPO) == []


def test_pipeline_model_identity_keys():
    sys.path.insert(0, str(REPO / "src"))
    from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
    ident = DigitizerPipeline().model_identity()
    assert ident["model_id"] == "MV0_EXECUTABLE_DEFAULT_V1"
    assert ident["electronics"]["gain_adc_per_mev"] == 120.0
    assert ident["transport"]["position_attenuation"] is False

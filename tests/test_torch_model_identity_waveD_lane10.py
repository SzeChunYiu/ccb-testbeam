"""Wave D Lane 10: lock #1126 fail-closed torch method-identity (no MLP/GBT alias)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def p04p():
    import importlib.util

    path = ROOT / "scripts/p04p_1781046824_725_569d120d_duplicate_harm_labels.py"
    spec = importlib.util.spec_from_file_location("p04p_waveD", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_p04p_source_has_no_silent_torch_identity_fallback() -> None:
    text = (ROOT / "scripts/p04p_1781046824_725_569d120d_duplicate_harm_labels.py").read_text(
        encoding="utf-8"
    )
    assert "never alias MLP/GBT predictions as CNN/ResNet" in text
    assert 'fold["prob_cnn_1d"] = fold["prob_mlp"]' not in text
    assert 'fold["prob_wavegate_resnet"] = fold["prob_gradient_boosted_trees"]' not in text
    assert "FAILED_MODEL_EXECUTION" in text


def test_p04q_source_has_no_silent_torch_identity_fallback() -> None:
    text = (
        ROOT / "scripts/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.py"
    ).read_text(encoding="utf-8")
    assert 'fold["prob_cnn_1d"] = fold["prob_mlp"]' not in text
    assert 'fold["prob_wavegate_resnet"] = fold["prob_gradient_boosted_trees"]' not in text
    assert "FAILED_MODEL_EXECUTION" in text


def test_summarize_method_marks_failed_torch_probs(p04p) -> None:
    summary = p04p.summarize_method(
        pd.DataFrame(
            {
                "harm_label": [0, 1],
                "flag_cnn_1d": [False, False],
                "prob_cnn_1d": [np.nan, np.nan],
                "prod_charge_frac_error": [0.0, 0.0],
                "prod_time_resid_ns": [0.0, 0.0],
                "run": [1, 1],
            }
        ),
        "cnn_1d",
        reps=2,
        rng=np.random.default_rng(0),
    )
    assert summary["execution_state"] == "FAILED_MODEL_EXECUTION"
    assert summary.get("eligible_for_ranking") is False

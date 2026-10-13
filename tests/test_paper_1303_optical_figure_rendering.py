"""Publication-rendering regressions for the #1303 optical producer."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "single_stave"))

import paper_1303_optical_stage_accounting as producer  # noqa: E402


def test_stage_figure_has_no_repeated_efficiency_textboxes() -> None:
    src = inspect.getsource(producer.stage_accounting_figure)
    assert "bbox=" not in src
    assert "ax.text(" not in src
    assert "fig.suptitle" not in src


def test_primary_pe_per_mev_figure_omits_superseded_history_overlay() -> None:
    src = inspect.getsource(producer.pe_per_mev_figure)
    assert "HISTORICAL_SUPERSEDED" not in src
    assert "SUPERSEDED" not in src
    assert "MC_MODEL_DEPENDENT" not in src


def test_calibration_figure_keeps_fit_metrics_out_of_legend() -> None:
    src = inspect.getsource(producer.pooled_cal)
    assert "r2=" not in src
    assert "PE/MeV" not in src
    assert "MC_MODEL_DEPENDENT" not in src


def test_summary_retains_history_and_rendering_contract() -> None:
    # History is removed from the artwork, not erased from scientific provenance.
    src = inspect.getsource(producer.main)
    assert "superseded_july_values" in src
    assert "status_text_inside_figures" in src
    assert "per_panel_efficiency_textboxes" in src
    assert "historical_superseded_points_in_primary_figure" in src

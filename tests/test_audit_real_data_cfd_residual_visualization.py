from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "tools"
    / "audit"
    / "audit_real_data_cfd_residual_visualization.py"
)
SPEC = importlib.util.spec_from_file_location("audit_real_data_cfd_visualization", MODULE_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _result_payload() -> dict:
    return {
        "sample_II": {
            "evaluation": [
                {
                    "method": "t_cfd10",
                    "n": 1888,
                    "median_ns": 59.60530122976422,
                    "sigma68_ns": 0.8985129399585929,
                },
                {
                    "method": "t_cfd20",
                    "n": 1888,
                    "median_ns": 63.55902020874973,
                    "sigma68_ns": 15.433838062158472,
                },
            ]
        },
        "task_runs": {
            "evaluation": [
                {
                    "method": "t_cfd10",
                    "n": 675,
                    "median_ns": -31.827483483483483,
                    "sigma68_ns": 3.5480843306636647,
                },
                {
                    "method": "t_cfd20",
                    "n": 675,
                    "median_ns": -28.576323232323233,
                    "sigma68_ns": 6.72995931053074,
                },
            ]
        },
    }


def _write_inputs(tmp_path: Path, source: str) -> tuple[Path, Path]:
    source_path = tmp_path / "source.py"
    result_path = tmp_path / "result.json"
    source_path.write_text(source, encoding="utf-8")
    result_path.write_text(json.dumps(_result_payload()), encoding="utf-8")
    return source_path, result_path


def test_current_fixed_raw_range_fails_with_quantitative_bounds(tmp_path: Path) -> None:
    source, result = _write_inputs(
        tmp_path,
        """
def make_figures(v, ax):
    ax.hist(v, bins=80, range=(-10, 10))
    label = sigma68(v)
    return label
""",
    )
    payload = AUDIT.audit_contract(source, result)
    assert payload["status"] == "FLAWED"
    codes = [item["code"] for item in payload["findings"]]
    assert codes.count("CENTRAL_RESIDUAL_MASS_GUARANTEED_OUTSIDE_PLOT") == 4
    assert "RAW_RESIDUAL_HISTOGRAM_USES_FIXED_MINUS10_TO10_RANGE" in codes
    assert "PLOT_LABEL_AND_VISIBLE_HISTOGRAM_USE_DIFFERENT_SUPPORT" in codes
    bounds = payload["reported_distribution_coverage_bounds"]
    assert bounds["sample_II"]["t_cfd10"]["q16_lower_bound_ns"] > 10.0
    assert bounds["task_runs"]["t_cfd20"]["q84_upper_bound_ns"] < -10.0


def test_centered_residual_plot_validates(tmp_path: Path) -> None:
    source, result = _write_inputs(
        tmp_path,
        """
import numpy as np

def make_figures(v, ax):
    centered = v - np.median(v)
    ax.hist(centered, bins=80, range=(-10, 10))
""",
    )
    payload = AUDIT.audit_contract(source, result)
    assert payload["status"] == "VALIDATED"
    assert payload["finding_count"] == 0


def test_dynamic_range_validates(tmp_path: Path) -> None:
    source, result = _write_inputs(
        tmp_path,
        """
def make_figures(v, ax):
    ax.hist(v, bins=80)
""",
    )
    payload = AUDIT.audit_contract(source, result)
    assert payload["status"] == "VALIDATED"


def test_duplicate_method_record_is_controlled_input_error(tmp_path: Path) -> None:
    source, result = _write_inputs(
        tmp_path,
        """
def make_figures(v, ax):
    ax.hist(v, bins=80, range=(-10, 10))
""",
    )
    payload = _result_payload()
    payload["sample_II"]["evaluation"].append(
        dict(payload["sample_II"]["evaluation"][0])
    )
    result.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AUDIT.AuditInputError, match="exactly one"):
        AUDIT.audit_contract(source, result)


def test_invalid_utf8_and_alias_fail_closed(tmp_path: Path, capsys) -> None:
    source, result = _write_inputs(
        tmp_path,
        """
def make_figures(v, ax):
    ax.hist(v, bins=80, range=(-10, 10))
""",
    )
    source.write_bytes(b"\xff")
    assert AUDIT.main([str(source), str(result)]) == 2
    assert "strict UTF-8" in capsys.readouterr().err

    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    assert AUDIT.main([str(source), str(result), "--output", str(result)]) == 2
    assert "aliases" in capsys.readouterr().err


def test_atomic_json_failure_preserves_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "audit.json"
    target.write_text("previous\n", encoding="utf-8")

    def fail_replace(src, dst):
        raise OSError("injected")

    monkeypatch.setattr(AUDIT.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        AUDIT._atomic_write_json(target, {"status": "VALIDATED"})
    assert target.read_text(encoding="utf-8") == "previous\n"
    assert list(tmp_path.glob(".audit.json.*.tmp")) == []

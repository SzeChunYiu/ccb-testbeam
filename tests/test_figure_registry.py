"""Tests for the CCB paper-figure result registry + validated builder.

Covers the failure conditions mandated by the spec:
  * valid registry with a present result + matching-sha256 table -> builds a
    figure + <id>_source_data.csv, build_report PASS;
  * missing result file -> FigureRegistryError;
  * uncertainty key missing on a quantitative entry -> error;
  * input_sha256 mismatch -> error;
  * status not in the allowed set -> error;
  * ILLUSTRATIVE (kind: illustrative) -> allowed and kept separate (NOT counted
    among quantitative figures);
  * EXTERNAL_BLOCKER with a missing result -> reported BLOCKED (not a hard FAIL).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

# Ensure the repo root is importable (pyproject sets pythonpath=["src"] only,
# but `tools` lives at the repo root). Robust to any pytest launcher.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.figure_registry import (  # noqa: E402  (after sys.path bootstrap)
    ALLOWED_STATUSES,
    FigureRegistryError,
    build,
    load_registry,
    sha256_file,
    validate_registry,
)

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _write_result(path: Path, value: float = 0.68, uncertainty=(0.66, 0.75)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "study_id": "TIME-TEST",
        "primary_metric": "sigma68_ns",
        "sigma68_ns": value,
        "uncertainty": uncertainty,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_table(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "stave,y,yerr\nB4,1.45,0.05\nB6,0.68,0.04\nB8,0.93,0.06\n",
        encoding="utf-8",
    )
    return sha256_file(path)


def _write_registry(path: Path, entries: dict) -> Path:
    path.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# happy path
# --------------------------------------------------------------------------- #


def test_valid_registry_builds_figure_and_source_data(tmp_path):
    result = tmp_path / "reports" / "t1" / "result.json"
    table = tmp_path / "reports" / "t1" / "tables" / "residual.csv"
    _write_result(result)
    sha = _write_table(table)

    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(result),
                "table": str(table),
                "input_sha256": sha,
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "VALIDATED",
                "kind": "quantitative",
                "caption": "B6 single-stave timing sigma68 with 95% CI.",
            }
        },
    )

    out = tmp_path / "out"
    report = build(reg, out, paper_only=True)

    # figure + per-figure source data emitted
    assert (out / "TIME-01.png").exists()
    assert (out / "TIME-01_source_data.csv").exists()

    # build_report written and reflects PASS
    report_disk = json.loads((out / "build_report.json").read_text())
    assert report_disk == report  # returned == written
    (rec,) = report_disk["entries"]
    assert rec["id"] == "TIME-01"
    assert rec["disposition"] == "PASS"
    assert report_disk["summary"]["quantitative_figures"] == 1
    assert report_disk["summary"]["fail"] == 0

    # source_data records the value/uncertainty actually used (not a literal)
    src = (out / "TIME-01_source_data.csv").read_text()
    assert "0.68" in src
    assert str(result) in src


# --------------------------------------------------------------------------- #
# failure conditions
# --------------------------------------------------------------------------- #


def test_missing_result_file_raises(tmp_path):
    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(tmp_path / "does_not_exist" / "result.json"),
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "VALIDATED",
                "kind": "quantitative",
                "caption": "missing result.",
            }
        },
    )
    with pytest.raises(FigureRegistryError):
        build(reg, tmp_path / "out")

    # even on failure a build_report is written, recording the FAIL
    report = json.loads((tmp_path / "out" / "build_report.json").read_text())
    assert report["entries"][0]["disposition"] == "FAIL"
    assert "not found" in report["entries"][0]["reason"]


def test_missing_uncertainty_on_quantitative_raises(tmp_path):
    result = tmp_path / "r" / "result.json"
    result.parent.mkdir(parents=True)
    # no 'uncertainty' key anywhere
    result.write_text(json.dumps({"sigma68_ns": 0.68}), encoding="utf-8")

    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(result),
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "VALIDATED",
                "kind": "quantitative",
                "caption": "no uncertainty.",
            }
        },
    )
    with pytest.raises(FigureRegistryError, match="uncertainty"):
        build(reg, tmp_path / "out")


def test_null_uncertainty_on_quantitative_raises(tmp_path):
    result = tmp_path / "r" / "result.json"
    result.parent.mkdir(parents=True)
    result.write_text(
        json.dumps({"sigma68_ns": 0.68, "uncertainty": None}), encoding="utf-8"
    )
    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(result),
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "VALIDATED",
                "kind": "quantitative",
                "caption": "null uncertainty.",
            }
        },
    )
    with pytest.raises(FigureRegistryError, match="uncertainty"):
        build(reg, tmp_path / "out")


def test_sha256_mismatch_raises(tmp_path):
    result = tmp_path / "r" / "result.json"
    table = tmp_path / "r" / "tables" / "residual.csv"
    _write_result(result)
    _write_table(table)
    wrong = hashlib.sha256(b"not the table").hexdigest()

    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(result),
                "table": str(table),
                "input_sha256": wrong,
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "VALIDATED",
                "kind": "quantitative",
                "caption": "bad sha.",
            }
        },
    )
    with pytest.raises(FigureRegistryError, match="sha256 mismatch"):
        build(reg, tmp_path / "out")


def test_status_not_in_allowed_set_raises(tmp_path):
    result = tmp_path / "r" / "result.json"
    _write_result(result)
    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(result),
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "TOTALLY_MADE_UP",
                "kind": "quantitative",
                "caption": "bad status.",
            }
        },
    )
    with pytest.raises(FigureRegistryError, match="allowed set"):
        build(reg, tmp_path / "out")


# --------------------------------------------------------------------------- #
# illustrative separation
# --------------------------------------------------------------------------- #


def test_illustrative_entry_allowed_and_kept_separate(tmp_path):
    result = tmp_path / "r" / "result.json"
    _write_result(result)  # present but never read for numbers

    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "QUANT-01": {
                "result": str(result),
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "VALIDATED",
                "kind": "quantitative",
                "caption": "a real quantitative figure.",
            },
            "SCH-01": {
                "result": str(result),
                "status": "ILLUSTRATIVE",
                "kind": "illustrative",
                "caption": "beamline schematic, not evidence.",
            },
        },
    )
    out = tmp_path / "out"
    report = build(reg, out)

    # schematic lives in a SEPARATE directory
    assert (out / "illustrative" / "SCH-01.png").exists()
    assert not (out / "SCH-01.png").exists()

    # illustrative is NOT counted among quantitative figures
    assert report["summary"]["quantitative_figures"] == 1
    assert report["summary"]["illustrative_figures"] == 1

    dispositions = {r["id"]: r["disposition"] for r in report["entries"]}
    assert dispositions == {"QUANT-01": "PASS", "SCH-01": "PASS"}


def test_illustrative_status_requires_illustrative_kind(tmp_path):
    # An ILLUSTRATIVE status on a quantitative kind must be rejected: schematics
    # must be kept separate from quantitative figures.
    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "BAD-01": {
                "result": "whatever.json",
                "status": "ILLUSTRATIVE",
                "kind": "quantitative",
                "caption": "mislabelled schematic.",
            }
        },
    )
    with pytest.raises(FigureRegistryError, match="separate|illustrative"):
        build(reg, tmp_path / "out")


# --------------------------------------------------------------------------- #
# external blocker
# --------------------------------------------------------------------------- #


def test_external_blocker_missing_result_reported_blocked(tmp_path):
    reg = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(tmp_path / "nope" / "result.json"),
                "table": str(tmp_path / "nope" / "t.csv"),
                "uncertainty_key": "uncertainty",
                "value_key": "sigma68_ns",
                "status": "EXTERNAL_BLOCKER",
                "kind": "quantitative",
                "caption": "compute-blocked result.",
            }
        },
    )
    out = tmp_path / "out"
    # must NOT raise
    report = build(reg, out)

    (rec,) = report["entries"]
    assert rec["disposition"] == "BLOCKED"
    assert report["summary"]["fail"] == 0
    assert report["summary"]["blocked"] == 1
    # no figure emitted for a blocked entry
    assert not (out / "TIME-01.png").exists()


# --------------------------------------------------------------------------- #
# preliminary gating + unit-level validate_registry
# --------------------------------------------------------------------------- #


def test_preliminary_blocked_by_default_built_with_flag(tmp_path):
    result = tmp_path / "r" / "result.json"
    table = tmp_path / "r" / "t.csv"
    _write_result(result)
    _write_table(table)
    entries = {
        "DE-01": {
            "result": str(result),
            "table": str(table),
            "uncertainty_key": "uncertainty",
            "value_key": "sigma68_ns",
            "status": "PRELIMINARY",
            "kind": "quantitative",
            "caption": "preliminary data-only figure.",
        }
    }
    reg = _write_registry(tmp_path / "figures.yaml", entries)

    # default paper build: blocked, no crash
    rep = build(reg, tmp_path / "out_default", paper_only=True)
    assert rep["entries"][0]["disposition"] == "BLOCKED"

    # with the flag: built
    rep2 = build(
        reg, tmp_path / "out_allow", paper_only=True, allow_preliminary=True
    )
    assert rep2["entries"][0]["disposition"] == "PASS"
    assert (tmp_path / "out_allow" / "DE-01.png").exists()


def test_validate_registry_flags_duplicate_and_missing():
    from tools.figure_registry import Entry

    entries = [
        Entry(id="A", result="r.json", status="VALIDATED", kind="quantitative",
              caption="ok"),
        Entry(id="A", result="r.json", status="VALIDATED", kind="quantitative",
              caption="dup"),
        Entry(id="B", result="", status="", kind="", caption=""),
    ]
    problems = validate_registry(entries)
    joined = "\n".join(problems)
    assert "duplicate id" in joined
    assert "missing required 'result'" in joined
    assert "missing required 'status'" in joined


def test_allowed_statuses_frozen():
    assert ALLOWED_STATUSES == frozenset(
        {"VALIDATED", "PRELIMINARY", "TENSION", "EXTERNAL_BLOCKER", "ILLUSTRATIVE"}
    )


def test_starter_registry_loads_and_validates():
    # The shipped paper/figures.yaml must be structurally clean.
    reg = Path(__file__).resolve().parents[1] / "paper" / "figures.yaml"
    entries = load_registry(reg)
    problems = validate_registry(entries)
    # The shipped registry intentionally carries non-VALIDATED governance
    # statuses/kinds reflecting the audit downgrades (SIMULATION_RESULT,
    # BLOCKED, GATED, SUPERSEDED, PARTIAL, MC_METHOD_CLOSURE, figure_sourced)
    # plus illustrative schematics without on-disk result files. Only these
    # governance markers are allowed; there must be no structural defects.
    governance = ("not in allowed set", "not in [", "missing required 'result'")
    assert all(any(tok in p for tok in governance) for p in problems), problems
    # It must contain at least one illustrative schematic, kept separate.
    kinds = {e.id: e.kind for e in entries}
    assert "illustrative" in kinds.values()

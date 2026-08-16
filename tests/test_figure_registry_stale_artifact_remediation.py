from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tools.audit import audit_figure_registry_stale_artifacts as stale_audit
from tools.figure_registry import builder


def _write_registry(path: Path, entries: dict) -> Path:
    path.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    return path


def _quantitative(result: Path, status: str = "VALIDATED") -> dict:
    item = {
        "status": status,
        "kind": "quantitative",
        "caption": "managed lifecycle control",
    }
    if status in {"VALIDATED", "PRELIMINARY", "TENSION"}:
        item["result"] = str(result)
    return item


def _result(path: Path, value: float = 1.0) -> Path:
    path.write_text(
        json.dumps({"value": value, "uncertainty": [value - 0.1, value + 0.1]})
        + "\n",
        encoding="utf-8",
    )
    return path


def test_pass_to_blocked_removes_prior_managed_artifacts(tmp_path: Path) -> None:
    result = _result(tmp_path / "result.json")
    registry = _write_registry(tmp_path / "figures.yaml", {"Q": _quantitative(result)})
    output = tmp_path / "out"
    builder.build(registry, output)
    assert (output / "Q.png").exists()
    assert (output / "Q_source_data.csv").exists()

    _write_registry(registry, {"Q": _quantitative(result, "BLOCKED")})
    report = builder.build(registry, output)

    assert report["entries"][0]["disposition"] == "QUARANTINED"
    assert report["entries"][0]["managed_artifacts"] == []
    assert report["cleanup"]["removed_count"] == 2
    assert not (output / "Q.png").exists()
    assert not (output / "Q_source_data.csv").exists()


def test_pass_to_failure_removes_prior_and_partial_outputs(tmp_path: Path) -> None:
    result = _result(tmp_path / "result.json")
    registry = _write_registry(tmp_path / "figures.yaml", {"Q": _quantitative(result)})
    output = tmp_path / "out"
    builder.build(registry, output)

    result.unlink()
    with pytest.raises(builder.FigureRegistryError, match="failed to build"):
        builder.build(registry, output)

    report = json.loads((output / "build_report.json").read_text(encoding="utf-8"))
    assert report["entries"][0]["disposition"] == "FAIL"
    assert report["entries"][0]["managed_artifacts"] == []
    assert not (output / "Q.png").exists()
    assert not (output / "Q_source_data.csv").exists()


def test_removed_entry_is_reconciled_from_previous_report(tmp_path: Path) -> None:
    result = _result(tmp_path / "result.json")
    registry = _write_registry(tmp_path / "figures.yaml", {"Q": _quantitative(result)})
    output = tmp_path / "out"
    builder.build(registry, output)

    _write_registry(registry, {})
    report = builder.build(registry, output)

    assert report["summary"]["n_entries"] == 0
    assert report["cleanup"]["removed_count"] == 2
    assert not (output / "Q.png").exists()
    assert not (output / "Q_source_data.csv").exists()


def test_kind_suffix_change_removes_old_artifact(tmp_path: Path) -> None:
    first = tmp_path / "source.png"
    second = tmp_path / "source.pdf"
    first.write_bytes(b"png-v1")
    second.write_bytes(b"pdf-v2")
    registry = _write_registry(
        tmp_path / "figures.yaml",
        {
            "Q": {
                "source_figure": str(first),
                "status": "VALIDATED",
                "kind": "figure_sourced",
                "caption": "source control",
            }
        },
    )
    output = tmp_path / "out"
    builder.build(registry, output)
    assert (output / "source" / "Q.png").read_bytes() == b"png-v1"

    _write_registry(
        registry,
        {
            "Q": {
                "source_figure": str(second),
                "status": "VALIDATED",
                "kind": "figure_sourced",
                "caption": "source control",
            }
        },
    )
    report = builder.build(registry, output)

    assert not (output / "source" / "Q.png").exists()
    assert (output / "source" / "Q.pdf").read_bytes() == b"pdf-v2"
    assert report["entries"][0]["managed_artifacts"] == [
        "source/Q.pdf",
        "source/Q_source_data.csv",
    ]


def test_unsafe_prior_report_path_is_rejected_without_deletion(tmp_path: Path) -> None:
    result = _result(tmp_path / "result.json")
    registry = _write_registry(
        tmp_path / "figures.yaml", {"Q": _quantitative(result, "BLOCKED")}
    )
    output = tmp_path / "out"
    output.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"do-not-delete")
    report_path = output / "build_report.json"
    previous = {
        "entries": [
            {
                "id": "Q",
                "figure": str(outside),
                "source_data": None,
            }
        ]
    }
    report_path.write_text(json.dumps(previous), encoding="utf-8")

    with pytest.raises(builder.FigureRegistryError, match="escapes output directory"):
        builder.build(registry, output)

    assert outside.read_bytes() == b"do-not-delete"
    assert json.loads(report_path.read_text(encoding="utf-8")) == previous


def test_report_publication_failure_rolls_back_managed_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path / "result.json", 1.0)
    registry = _write_registry(tmp_path / "figures.yaml", {"Q": _quantitative(result)})
    output = tmp_path / "out"
    builder.build(registry, output)
    old_figure = (output / "Q.png").read_bytes()
    old_source = (output / "Q_source_data.csv").read_bytes()
    old_report = (output / "build_report.json").read_bytes()
    _result(result, 2.0)

    def fail_report(path: Path, payload: dict) -> None:
        raise OSError("injected report failure")

    monkeypatch.setattr(builder, "_atomic_write_json", fail_report)
    with pytest.raises(builder.FigureRegistryError, match="coherent build state"):
        builder.build(registry, output)

    assert (output / "Q.png").read_bytes() == old_figure
    assert (output / "Q_source_data.csv").read_bytes() == old_source
    assert (output / "build_report.json").read_bytes() == old_report


def test_unmanifested_removed_candidate_fails_closed(tmp_path: Path) -> None:
    result = _result(tmp_path / "result.json")
    registry = _write_registry(
        tmp_path / "figures.yaml", {"Q": _quantitative(result, "BLOCKED")}
    )
    output = tmp_path / "out"
    output.mkdir()
    (output / "OLD.png").write_bytes(b"unmanifested")

    with pytest.raises(builder.FigureRegistryError, match="cannot be attributed"):
        builder.build(registry, output)
    assert (output / "OLD.png").read_bytes() == b"unmanifested"


def test_exact_source_stale_artifact_audit_is_zero_finding() -> None:
    snapshot = stale_audit._read_source(Path(builder.__file__))
    payload = stale_audit.audit_source(snapshot)
    assert payload["status"] == "VALIDATED"
    assert payload["findings"] == []


def test_unsafe_entry_id_cannot_escape_output_directory(tmp_path: Path) -> None:
    result = _result(tmp_path / "result.json")
    registry = _write_registry(
        tmp_path / "figures.yaml",
        {"../ESCAPE": _quantitative(result)},
    )
    output = tmp_path / "out"

    with pytest.raises(builder.FigureRegistryError, match="safe output paths"):
        builder.build(registry, output)
    assert not (tmp_path / "ESCAPE.png").exists()

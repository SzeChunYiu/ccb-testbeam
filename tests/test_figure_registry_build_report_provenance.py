"""Regression tests for content-addressed figure-registry build reports."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.figure_registry import builder  # noqa: E402
from tools.figure_registry.builder import FigureRegistryError, build, main  # noqa: E402
from tools.figure_registry.registry import REGISTRY_SNAPSHOT_METHOD  # noqa: E402


def _quarantined_registry(entry_id: str = "Q") -> bytes:
    return (
        f"{entry_id}:\n"
        "  status: BLOCKED\n"
        "  kind: quantitative\n"
        "  caption: quarantined diagnostic\n"
    ).encode("utf-8")


def test_build_report_binds_exact_registry_snapshot(tmp_path):
    registry = tmp_path / "figures.yaml"
    output = tmp_path / "out"
    raw = _quarantined_registry()
    registry.write_bytes(raw)

    report = build(registry, output)
    provenance = report["registry_provenance"]

    assert report["registry"] == str(registry)
    assert provenance == {
        "path": str(registry),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "snapshot_method": REGISTRY_SNAPSHOT_METHOD,
        "entry_count": 1,
    }
    assert report["summary"]["quarantined"] == 1
    assert json.loads((output / "build_report.json").read_text()) == report


def test_path_replacement_after_snapshot_does_not_change_report_identity(
    tmp_path,
    monkeypatch,
):
    registry = tmp_path / "figures.yaml"
    output = tmp_path / "out"
    original = _quarantined_registry("ORIGINAL")
    replacement = _quarantined_registry("REPLACEMENT")
    registry.write_bytes(original)
    real_validate = builder.validate_registry

    def replace_then_validate(entries):
        registry.write_bytes(replacement)
        return real_validate(entries)

    monkeypatch.setattr(builder, "validate_registry", replace_then_validate)
    report = build(registry, output)

    assert [record["id"] for record in report["entries"]] == ["ORIGINAL"]
    assert report["registry_provenance"]["sha256"] == hashlib.sha256(
        original
    ).hexdigest()
    assert report["registry_provenance"]["size_bytes"] == len(original)
    assert registry.read_bytes() == replacement


def test_duplicate_key_cli_failure_is_controlled_without_traceback(tmp_path, capsys):
    registry = tmp_path / "figures.yaml"
    output = tmp_path / "out"
    registry.write_bytes(_quarantined_registry() + _quarantined_registry())

    status = main(["--registry", str(registry), "--out", str(output)])
    captured = capsys.readouterr()

    assert status == 1
    assert captured.out == ""
    assert captured.err.startswith("FigureRegistryError: registry format error:")
    assert "duplicate YAML key 'Q'" in captured.err
    assert "Traceback" not in captured.err
    assert not (output / "build_report.json").exists()


def test_invalid_utf8_cli_failure_is_controlled_without_traceback(tmp_path, capsys):
    registry = tmp_path / "figures.yaml"
    output = tmp_path / "out"
    registry.write_bytes(b"Q:\n  caption: \xff\n")

    status = main(["--registry", str(registry), "--out", str(output)])
    captured = capsys.readouterr()

    assert status == 1
    assert "FigureRegistryError: registry format error:" in captured.err
    assert "not strict UTF-8" in captured.err
    assert "Traceback" not in captured.err


def test_structural_invalid_report_retains_snapshot_provenance(tmp_path):
    registry = tmp_path / "figures.yaml"
    output = tmp_path / "out"
    raw = b"Q:\n  status: VALIDATED\n  kind: quantitative\n  result: result.json\n"
    registry.write_bytes(raw)

    with pytest.raises(FigureRegistryError, match="registry failed validation"):
        build(registry, output)

    report = json.loads((output / "build_report.json").read_text())
    assert report["summary"] == {"status": "INVALID_REGISTRY", "n_problems": 1}
    assert report["validation_problems"] == ["Q: missing required 'caption'"]
    assert report["registry_provenance"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["registry_provenance"]["entry_count"] == 1


def test_registry_path_is_read_once_during_quarantined_build(tmp_path, monkeypatch):
    registry = tmp_path / "figures.yaml"
    output = tmp_path / "out"
    registry.write_bytes(_quarantined_registry())
    real_read_bytes = Path.read_bytes
    reads = 0

    def count_registry_reads(self: Path) -> bytes:
        nonlocal reads
        if self == registry:
            reads += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", count_registry_reads)
    build(registry, output)

    assert reads == 1

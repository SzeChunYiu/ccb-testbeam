from __future__ import annotations

import csv
import hashlib
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.figure_registry import builder
from tools.audit import audit_figure_registry_snapshot_provenance as snapshot_audit


def _write_registry(path: Path, entries: dict) -> Path:
    path.write_text(yaml.safe_dump(entries, sort_keys=False), encoding="utf-8")
    return path


def _csv_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def test_result_replacement_after_snapshot_cannot_change_provenance(tmp_path, monkeypatch):
    result = tmp_path / "result.json"
    original = b'{"value": 0.68, "uncertainty": [0.66, 0.75]}\n'
    replacement = b'{"value": 99.0, "uncertainty": [98.0, 100.0]}\n'
    result.write_bytes(original)
    registry = _write_registry(
        tmp_path / "figures.yaml",
        {
            "TIME-01": {
                "result": str(result),
                "status": "VALIDATED",
                "kind": "quantitative",
                "caption": "snapshot race control",
            }
        },
    )

    original_reader = builder._read_file_snapshot
    replaced = False

    def read_then_replace(path: Path, *, entry_id: str, label: str):
        nonlocal replaced
        snapshot = original_reader(path, entry_id=entry_id, label=label)
        if Path(path) == result and label == "result JSON" and not replaced:
            result.write_bytes(replacement)
            replaced = True
        return snapshot

    monkeypatch.setattr(builder, "_read_file_snapshot", read_then_replace)
    report = builder.build(registry, tmp_path / "out")

    row = _csv_row(tmp_path / "out" / "TIME-01_source_data.csv")
    assert report["entries"][0]["disposition"] == "PASS"
    assert row["central_value"] == "0.68"
    assert row["result_sha256"] == hashlib.sha256(original).hexdigest()
    assert row["result_size_bytes"] == str(len(original))
    assert row["result_snapshot_method"] == "SINGLE_READ_STRICT_UTF8_EXACT_BYTES"
    assert result.read_bytes() == replacement


def test_source_replacement_after_snapshot_cannot_change_published_artifact(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.bin"
    original = b"source-artifact-v1"
    replacement = b"source-artifact-v2-with-different-size"
    source.write_bytes(original)
    registry = _write_registry(
        tmp_path / "figures.yaml",
        {
            "SRC-01": {
                "source_figure": str(source),
                "status": "VALIDATED",
                "kind": "figure_sourced",
                "caption": "source snapshot race control",
            }
        },
    )

    original_reader = builder._read_file_snapshot
    replaced = False

    def read_then_replace(path: Path, *, entry_id: str, label: str):
        nonlocal replaced
        snapshot = original_reader(path, entry_id=entry_id, label=label)
        if Path(path) == source and label == "source artifact" and not replaced:
            source.write_bytes(replacement)
            replaced = True
        return snapshot

    monkeypatch.setattr(builder, "_read_file_snapshot", read_then_replace)
    report = builder.build(registry, tmp_path / "out")

    target = tmp_path / "out" / "source" / "SRC-01.bin"
    row = _csv_row(tmp_path / "out" / "source" / "SRC-01_source_data.csv")
    digest = hashlib.sha256(original).hexdigest()
    assert report["entries"][0]["disposition"] == "PASS"
    assert target.read_bytes() == original
    assert row["source_sha256"] == digest
    assert row["published_target_sha256"] == digest
    assert row["source_size_bytes"] == str(len(original))
    assert row["published_target_size_bytes"] == str(len(original))
    assert row["publication"] == "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE"
    assert source.read_bytes() == replacement


def test_atomic_snapshot_publication_preserves_previous_target_on_failure(
    tmp_path, monkeypatch
):
    target = tmp_path / "target.bin"
    target.write_bytes(b"previous")
    raw = b"replacement"
    snapshot = builder.ByteSnapshot(
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
    )

    def fail_replace(_source, _target):
        raise OSError("injected replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(builder.FigureRegistryError, match="injected replacement failure"):
        builder._atomic_publish_snapshot(target, snapshot)
    assert target.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".target.bin.*.tmp"))


def test_source_output_alias_fails_closed(tmp_path):
    out = tmp_path / "out"
    source = out / "source" / "SRC-01.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original")
    registry = _write_registry(
        tmp_path / "figures.yaml",
        {
            "SRC-01": {
                "source_figure": str(source),
                "status": "VALIDATED",
                "kind": "figure_sourced",
                "caption": "alias control",
            }
        },
    )
    with pytest.raises(builder.FigureRegistryError, match="aliases source artifact"):
        builder.build(registry, out)
    assert source.read_bytes() == b"original"


def test_exact_source_removes_split_snapshot_patterns():
    result = snapshot_audit.audit_source(Path(builder.__file__))
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0
    text = Path(builder.__file__).read_text(encoding="utf-8")
    assert "sha256_file(entry.result)" not in text
    assert "shutil.copy2(source, target)" not in text
    assert "sha256_file(source)" not in text
    assert "source.stat().st_size" not in text
    assert "SINGLE_READ_STRICT_UTF8_EXACT_BYTES" in text
    assert "published_target_sha256" in text

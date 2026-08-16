"""Regression tests for lossless paper-figure registry YAML identity."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.figure_registry.registry import (  # noqa: E402
    REGISTRY_SNAPSHOT_METHOD,
    RegistryFormatError,
    load_registry,
    load_registry_snapshot,
    validate_registry,
)


def _valid_entry(status: str = "VALIDATED") -> str:
    return (
        f"  status: {status}\n"
        "  kind: quantitative\n"
        "  result: result.json\n"
        "  caption: exact result\n"
    )


def test_pyyaml_negative_control_silently_keeps_last_top_level_key():
    text = "Q:\n" + _valid_entry("VALIDATED") + "Q:\n" + _valid_entry("BLOCKED")
    parsed = yaml.safe_load(text)
    assert list(parsed) == ["Q"]
    assert parsed["Q"]["status"] == "BLOCKED"


def test_duplicate_top_level_figure_id_fails_closed(tmp_path):
    path = tmp_path / "figures.yaml"
    path.write_text(
        "Q:\n" + _valid_entry("VALIDATED") + "Q:\n" + _valid_entry("BLOCKED"),
        encoding="utf-8",
    )
    with pytest.raises(RegistryFormatError, match=r"duplicate YAML key 'Q'.*first defined"):
        load_registry(path)


def test_duplicate_nested_status_fails_closed(tmp_path):
    path = tmp_path / "figures.yaml"
    path.write_text(
        "Q:\n"
        "  status: VALIDATED\n"
        "  status: BLOCKED\n"
        "  kind: quantitative\n"
        "  result: result.json\n"
        "  caption: exact result\n",
        encoding="utf-8",
    )
    with pytest.raises(
        RegistryFormatError,
        match=r"duplicate YAML key 'status'.*first defined",
    ):
        load_registry(path)


def test_snapshot_binds_entries_hash_size_and_policy_to_one_read(tmp_path, monkeypatch):
    path = tmp_path / "figures.yaml"
    original = ("Q:\n" + _valid_entry()).encode("utf-8")
    replacement = ("R:\n" + _valid_entry("BLOCKED")).encode("utf-8")
    path.write_bytes(original)
    real_read_bytes = Path.read_bytes

    def replace_after_read(self: Path) -> bytes:
        raw = real_read_bytes(self)
        self.write_bytes(replacement)
        return raw

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    snapshot = load_registry_snapshot(path)

    assert [entry.id for entry in snapshot.entries] == ["Q"]
    assert snapshot.raw == original
    assert snapshot.sha256 == hashlib.sha256(original).hexdigest()
    assert snapshot.size_bytes == len(original)
    assert snapshot.snapshot_method == REGISTRY_SNAPSHOT_METHOD
    assert path.read_bytes() == replacement


def test_invalid_utf8_is_controlled_registry_error(tmp_path):
    path = tmp_path / "figures.yaml"
    path.write_bytes(b"Q:\n  caption: \xff\n")
    with pytest.raises(RegistryFormatError, match="not strict UTF-8"):
        load_registry(path)


def test_valid_registry_still_loads_and_validates(tmp_path):
    path = tmp_path / "figures.yaml"
    path.write_text("Q:\n" + _valid_entry(), encoding="utf-8")
    entries = load_registry(path)
    assert [entry.id for entry in entries] == ["Q"]
    assert validate_registry(entries) == []

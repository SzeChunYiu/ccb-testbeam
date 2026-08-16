from __future__ import annotations

import importlib
import os
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    target = importlib.import_module("scripts.single_stave.deltaE_E")
    target._INPUT_SNAPSHOTS.clear()
    return target


def test_parquet_success_is_atomic_and_records_contract(module, tmp_path, monkeypatch):
    frame = pd.DataFrame({"x": [1, 2]})
    calls = []

    def fake_to_parquet(self, path, index=False):
        assert index is False
        path = Path(path)
        assert path.parent == tmp_path
        assert path.name.startswith(".events.")
        assert path.name.endswith(".tmp.parquet")
        path.write_bytes(b"PARQUET")
        calls.append(path)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fake_to_parquet)
    result = module._write_table(frame, tmp_path / "events")

    assert result == tmp_path / "events.parquet"
    assert result.read_bytes() == b"PARQUET"
    assert not (tmp_path / "events.csv.gz").exists()
    assert calls and not calls[0].exists()
    assert module._event_table_output_contract() == {
        "policy": module.EVENT_TABLE_OUTPUT_POLICY,
        "publication": "SAME_DIRECTORY_TEMP_FSYNC_OS_REPLACE",
        "parquet_fallback": "CSV_GZIP_ONLY_WHEN_PARQUET_ENGINE_UNAVAILABLE",
        "stale_alternate_format": "REJECT",
    }


def test_only_engine_unavailability_allows_csv_fallback(module, tmp_path, monkeypatch):
    frame = pd.DataFrame({"x": [1, 2]})

    def unavailable(self, path, index=False):
        raise ImportError("Unable to find a usable engine; tried using: pyarrow, fastparquet")

    def fake_to_csv(self, path, index=False, compression=None):
        assert index is False
        assert compression == "gzip"
        Path(path).write_bytes(b"GZIP")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", unavailable)
    monkeypatch.setattr(pd.DataFrame, "to_csv", fake_to_csv)
    result = module._write_table(frame, tmp_path / "events")

    assert result == tmp_path / "events.csv.gz"
    assert result.read_bytes() == b"GZIP"
    assert not (tmp_path / "events.parquet").exists()


def test_arbitrary_parquet_failure_does_not_fallback(module, tmp_path, monkeypatch):
    frame = pd.DataFrame({"x": [1]})
    fallback_called = False

    def broken(self, path, index=False):
        Path(path).write_bytes(b"partial")
        raise PermissionError("permission denied")

    def fake_to_csv(self, path, index=False, compression=None):
        nonlocal fallback_called
        fallback_called = True

    monkeypatch.setattr(pd.DataFrame, "to_parquet", broken)
    monkeypatch.setattr(pd.DataFrame, "to_csv", fake_to_csv)

    with pytest.raises(
        module.EventTableOutputError,
        match="Parquet event-table publication failed",
    ):
        module._write_table(frame, tmp_path / "events")

    assert fallback_called is False
    assert not (tmp_path / "events.parquet").exists()
    assert not list(tmp_path.glob(".*.tmp.parquet"))


def test_previous_final_is_preserved_when_replacement_fails(module, tmp_path, monkeypatch):
    frame = pd.DataFrame({"x": [1]})
    final = tmp_path / "events.parquet"
    final.write_bytes(b"OLD")

    def broken(self, path, index=False):
        Path(path).write_bytes(b"NEW-PARTIAL")
        raise RuntimeError("serialization failed")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", broken)
    with pytest.raises(module.EventTableOutputError):
        module._write_table(frame, tmp_path / "events")

    assert final.read_bytes() == b"OLD"
    assert not list(tmp_path.glob(".*.tmp.parquet"))


def test_output_aliases_validated_input_fail_closed(module, tmp_path, monkeypatch):
    source = tmp_path / "events.parquet"
    source.write_bytes(b"INPUT")
    module._INPUT_SNAPSHOTS[source.resolve()] = {"sha256": "x"}
    frame = pd.DataFrame({"x": [1]})

    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda *args, **kwargs: pytest.fail("writer must not be called"),
    )
    with pytest.raises(module.EventTableOutputError, match="aliases validated input"):
        module._write_table(frame, tmp_path / "events")
    assert source.read_bytes() == b"INPUT"


def test_symlink_alias_and_stale_alternate_fail_closed(module, tmp_path, monkeypatch):
    real_input = tmp_path / "real.parquet"
    real_input.write_bytes(b"INPUT")
    alias = tmp_path / "events.parquet"
    try:
        alias.symlink_to(real_input)
    except OSError:
        pytest.skip("symlink creation unavailable")
    module._INPUT_SNAPSHOTS[real_input.resolve()] = {"sha256": "x"}
    frame = pd.DataFrame({"x": [1]})

    with pytest.raises(module.EventTableOutputError, match="aliases validated input"):
        module._write_table(frame, tmp_path / "events")

    alias.unlink()
    stale = tmp_path / "events.csv.gz"
    stale.write_bytes(b"STALE")
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda *args, **kwargs: pytest.fail("writer must not be called"),
    )
    with pytest.raises(module.EventTableOutputError, match="stale alternate-format"):
        module._write_table(frame, tmp_path / "events")
    assert stale.read_bytes() == b"STALE"


def test_result_contract_is_bound_to_analysis(module, monkeypatch):
    monkeypatch.setattr(module, "_CORE_ANALYZE", lambda *args: {"result": {}})
    bundle = module.analyze(None, None, (), (), "all", 1)
    contract = bundle["result"]["event_table_output_contract"]
    assert contract["policy"] == module.EVENT_TABLE_OUTPUT_POLICY


def test_os_replace_failure_cleans_temp_and_preserves_final(module, tmp_path, monkeypatch):
    frame = pd.DataFrame({"x": [1]})
    final = tmp_path / "events.parquet"
    final.write_bytes(b"OLD")

    def fake_to_parquet(self, path, index=False):
        Path(path).write_bytes(b"NEW")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fake_to_parquet)
    monkeypatch.setattr(os, "replace", lambda *args: (_ for _ in ()).throw(OSError("replace")))
    with pytest.raises(module.EventTableOutputError):
        module._write_table(frame, tmp_path / "events")
    assert final.read_bytes() == b"OLD"
    assert not list(tmp_path.glob(".*.tmp.parquet"))

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import uproot

from ccb_mc_validation.raw_input_authorization import RawInputAuthorizationError
from ccb_mc_validation.raw_uproot_authorization import RawManifestIndexError


def _load_module(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "studies" / "data_side_real_beam.py"
    spec = importlib.util.spec_from_file_location("data_side_real_beam_authorized_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_root(path: Path, event: int = 123) -> None:
    waveform = np.zeros((1, 128), dtype=np.int16)
    waveform[0, 2 * 16 + 5] = 2100
    waveform[0, 4 * 16 + 6] = 2200
    with uproot.recreate(path) as root_file:
        root_file["h101"] = {
            "EVENTNO": np.array([event], dtype=np.int32),
            "HRDv": waveform,
        }


def _manifest_row(path: Path, run: int = 31) -> dict[str, object]:
    payload = path.read_bytes()
    info = path.stat()
    return {
        "run": run,
        "file": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "source_dev": int(info.st_dev),
        "source_ino": int(info.st_ino),
        "source_nlink": int(info.st_nlink),
        "source_mtime_ns": int(info.st_mtime_ns),
        "source_ctime_ns": int(info.st_ctime_ns),
    }


def _canon(run: int = 31, event: int = 123) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"run": run, "eventno": event, "stave": "B4"},
            {"run": run, "eventno": event, "stave": "B6"},
        ]
    )


def test_timing_consumes_manifest_authorized_root(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    source = raw_dir / "hrdb_run_0031.root"
    _write_root(source)
    row = _manifest_row(source)
    module.RAW_DIR = raw_dir
    module.OUT = tmp_path / "out"
    module.OUT.mkdir()

    result = module.timing(_canon(), {"raw_input_sha256": [row]})

    assert result["n_B4B6_with_times"] == 1
    assert result["raw_input_authorization"] == "manifest-bound-same-open-stream-v1"
    assert result["raw_runs_authorized"] == [31]
    assert (module.OUT / "VIS-TIM-DATA_sampling_limited.png").exists()


def test_timing_missing_manifest_row_fails_before_raw_open(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    source = raw_dir / "hrdb_run_0031.root"
    _write_root(source)
    module.RAW_DIR = raw_dir
    module.OUT = tmp_path / "out"
    module.OUT.mkdir()

    opened = False

    def forbidden_open(*args, **kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("raw open must not occur without a manifest row")

    monkeypatch.setattr(module, "open_verified_uproot", forbidden_open)
    with pytest.raises(RawManifestIndexError, match="missing required runs: 31"):
        module.timing(_canon(), {"raw_input_sha256": []})
    assert opened is False


def test_timing_rejects_replaced_raw_file(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    source = raw_dir / "hrdb_run_0031.root"
    replacement = raw_dir / "replacement.root"
    _write_root(source, event=123)
    row = _manifest_row(source)
    _write_root(replacement, event=999)
    replacement.replace(source)
    module.RAW_DIR = raw_dir
    module.OUT = tmp_path / "out"
    module.OUT.mkdir()

    with pytest.raises(RawInputAuthorizationError, match="identity does not match"):
        module.timing(_canon(), {"raw_input_sha256": [row]})

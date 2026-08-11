from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import uproot

from ccb_mc_validation.raw_input_authorization import RawInputAuthorizationError
from ccb_mc_validation.raw_uproot_authorization import (
    RawManifestIndexError,
    manifest_rows_by_run,
    open_verified_uproot,
    require_manifest_rows,
)


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


def _write_root(path: Path, event: int = 123) -> None:
    waveform = np.zeros((1, 128), dtype=np.int16)
    waveform[0, 2 * 16 + 5] = 2100
    waveform[0, 4 * 16 + 6] = 2200
    with uproot.recreate(path) as root_file:
        # Explicit TTree path: dict-assignment (`root_file["h101"] = {...}`)
        # forces the RNTuple write path, which in uproot 5.6.9 hits a circular
        # self-import (`_cascade.add_rntuple -> _cascadentuple -> import uproot`)
        # that leaves a SimpleNamespace in sys.modules and then
        # `AttributeError: no attribute 'writing'`. mktree + extend avoids it.
        root_file.mktree("h101", {
            "EVENTNO": np.dtype("int32"),
            "HRDv": np.dtype(("int16", (128,))),
        })
        root_file["h101"].extend({
            "EVENTNO": np.array([event], dtype=np.int32),
            "HRDv": waveform,
        })


def test_verified_uproot_reads_manifest_bound_root_stream(tmp_path):
    source = tmp_path / "hrdb_run_0031.root"
    _write_root(source)
    row = _manifest_row(source)

    with open_verified_uproot(source, row, block_size=17) as root_file:
        tree = root_file["h101"]
        arrays = tree.arrays(["EVENTNO", "HRDv"], library="np")
        assert arrays["EVENTNO"].tolist() == [123]
        assert arrays["HRDv"].shape == (1, 128)
        assert int(arrays["HRDv"][0, 2 * 16 + 5]) == 2100


def test_uproot_receives_file_like_stream_not_path(monkeypatch, tmp_path):
    source = tmp_path / "hrdb_run_0031.root"
    _write_root(source)
    row = _manifest_row(source)

    import ccb_mc_validation.raw_uproot_authorization as module

    real_open = module.uproot.open
    seen: list[object] = []

    def spy_open(target, *args, **kwargs):
        seen.append(target)
        assert hasattr(target, "read")
        assert hasattr(target, "seek")
        assert not isinstance(target, (str, Path))
        return real_open(target, *args, **kwargs)

    monkeypatch.setattr(module.uproot, "open", spy_open)
    with open_verified_uproot(source, row) as root_file:
        assert root_file["h101"].num_entries == 1
    assert len(seen) == 1


def test_path_replacement_during_uproot_lifetime_fails_closed(tmp_path):
    source = tmp_path / "hrdb_run_0031.root"
    replacement = tmp_path / "replacement.root"
    _write_root(source, event=123)
    _write_root(replacement, event=999)
    row = _manifest_row(source)

    with pytest.raises(
        RawInputAuthorizationError, match="consumer held authorized stream"
    ):
        with open_verified_uproot(source, row) as root_file:
            assert root_file["h101"]["EVENTNO"].array(library="np").tolist() == [123]
            replacement.replace(source)


def test_replacement_before_open_is_rejected(tmp_path):
    source = tmp_path / "hrdb_run_0031.root"
    replacement = tmp_path / "replacement.root"
    _write_root(source, event=123)
    row = _manifest_row(source)
    _write_root(replacement, event=999)
    replacement.replace(source)

    with pytest.raises(RawInputAuthorizationError, match="identity does not match"):
        with open_verified_uproot(source, row):
            pytest.fail("Uproot must not receive a replaced raw source")


def test_manifest_run_index_is_unique_and_complete(tmp_path):
    source = tmp_path / "hrdb_run_0031.root"
    _write_root(source)
    row = _manifest_row(source)
    indexed = require_manifest_rows([row], [31])
    assert indexed[31] is row

    with pytest.raises(RawManifestIndexError, match="missing required runs: 32"):
        require_manifest_rows([row], [31, 32])
    with pytest.raises(RawManifestIndexError, match="duplicate raw manifest row"):
        manifest_rows_by_run([row, dict(row)])


def test_manifest_run_identifier_rejects_bool_and_noninteger(tmp_path):
    source = tmp_path / "hrdb_run_0031.root"
    _write_root(source)
    row = _manifest_row(source)
    for bad in (True, 31.0, "31", -1):
        malformed = dict(row)
        malformed["run"] = bad
        with pytest.raises(RawManifestIndexError, match="nonnegative integer"):
            manifest_rows_by_run([malformed])

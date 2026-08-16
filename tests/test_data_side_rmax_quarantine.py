from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import types
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = Path(__file__).parents[1] / "scripts/studies/data_side_real_beam.py"


def load_module():
    sys.modules.setdefault("uproot", types.SimpleNamespace())
    spec = importlib.util.spec_from_file_location("data_side_real_beam", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rmax_is_blocked_and_reports_only_model_sensitivity(tmp_path):
    module = load_module()
    module.OUT = tmp_path
    selected = pd.DataFrame(
        {
            "run": [31, 31, 31, 32, 32],
            "eventno": [1, 1, 2, 1, 1],
        }
    )

    result = module.rmax(selected)

    assert result["rmax_authorized"] is False
    assert result["rmax_status"] == "BLOCKED"
    assert result["accepted_rmax_mhz"] is None
    assert result["blocked_by"] == "S-STAT-003"
    assert result["measured_occupancy_role"] == (
        "DESCRIPTIVE_SELECTED_PULSE_MULTIPLICITY_ONLY"
    )
    expected = 0.38 / (124.79018394263471e-9) / 1e6
    assert math.isclose(
        result["model_sensitivity_only_mhz"], expected, rel_tol=0, abs_tol=1e-15
    )
    assert (tmp_path / "VIS-PU-DATA_occupancy_rmax.png").is_file()


def test_producer_contains_no_data_derived_rmax_authorization():
    text = SCRIPT.read_text(encoding="utf-8")
    prohibited = (
        "Rmax from real occupancy",
        "tau_eff_ns = ACQ_WINDOW_NS - 30.0",
        "Rmax_data_derived_Hz",
        "Rmax(data-derived)",
        "Rmax_derived=",
    )
    assert all(phrase not in text for phrase in prohibited)


def test_raw_digest_collection_is_complete_for_available_inputs(tmp_path):
    module = load_module()
    payloads = {31: b"run31", 33: b"run33", 34: b"run34"}
    for run, payload in payloads.items():
        (tmp_path / f"hrdb_run_{run:04d}.root").write_bytes(payload)

    digests, missing = module.collect_raw_input_digests([31, 32, 33, 34], tmp_path)

    assert [row["run"] for row in digests] == [31, 33, 34]
    assert missing == [32]
    assert [row["sha256"] for row in digests] == [
        hashlib.sha256(payloads[run]).hexdigest() for run in (31, 33, 34)
    ]
    assert [row["bytes"] for row in digests] == [5, 5, 5]
    assert all(int(row["source_ino"]) > 0 for row in digests)
    assert all(int(row["source_nlink"]) >= 1 for row in digests)


def test_legacy_separate_hash_then_stat_can_serialize_mixed_versions(tmp_path):
    module = load_module()
    source = tmp_path / "raw.root"
    payload_a = b"AAAA"
    payload_b = b"BBBBBBBBBB"
    source.write_bytes(payload_a)

    digest_a = module.sha256_file(source)
    source.write_bytes(payload_b)
    later_size = source.stat().st_size

    assert digest_a == hashlib.sha256(payload_a).hexdigest()
    assert later_size == len(payload_b)
    assert later_size != len(payload_a)


def test_same_open_stream_rejects_path_replacement_during_read(tmp_path, monkeypatch):
    module = load_module()
    source = tmp_path / "raw.root"
    replacement = tmp_path / "replacement.root"
    payload_a = b"abcdef"
    payload_b = b"replacement-is-longer"
    source.write_bytes(payload_a)
    replacement.write_bytes(payload_b)

    real_read = module.os.read
    swapped = False

    def replacing_read(descriptor, size):
        nonlocal swapped
        block = real_read(descriptor, size)
        if block and not swapped:
            replacement.replace(source)
            swapped = True
        return block

    monkeypatch.setattr(module.os, "read", replacing_read)
    with pytest.raises(module.RawInputProvenanceError, match="changed while being digested"):
        module.digest_raw_input(source, block_size=2)

    assert swapped is True
    assert source.read_bytes() == payload_b


def test_same_open_stream_rejects_path_vanish_mid_read(tmp_path, monkeypatch):
    """A mid-read unlink (no replacement) must also be caught: nlink
    drops to 0 even on filesystems where the unlinked inode's timestamps
    never advance."""
    module = load_module()
    source = tmp_path / "raw.root"
    source.write_bytes(b"abcdef")

    real_read = module.os.read
    vanished = False

    def unlinking_read(descriptor, size):
        nonlocal vanished
        block = real_read(descriptor, size)
        if block and not vanished:
            source.unlink()
            vanished = True
        return block

    monkeypatch.setattr(module.os, "read", unlinking_read)
    with pytest.raises(module.RawInputProvenanceError, match="changed while being digested"):
        module.digest_raw_input(source, block_size=2)


def test_same_open_stream_rejects_in_place_mutation_during_read(tmp_path, monkeypatch):
    module = load_module()
    source = tmp_path / "raw.root"
    source.write_bytes(b"abcdefgh")

    real_read = module.os.read
    mutated = False

    def mutating_read(descriptor, size):
        nonlocal mutated
        block = real_read(descriptor, size)
        if block and not mutated:
            with source.open("ab") as handle:
                handle.write(b"Z")
            mutated = True
        return block

    monkeypatch.setattr(module.os, "read", mutating_read)
    with pytest.raises(module.RawInputProvenanceError, match="changed while being digested"):
        module.digest_raw_input(source, block_size=2)
    assert mutated is True


def test_raw_digest_rejects_final_component_symlink(tmp_path):
    module = load_module()
    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("platform does not expose O_NOFOLLOW")
    target = tmp_path / "target.root"
    link = tmp_path / "raw.root"
    target.write_bytes(b"beam-bytes")
    link.symlink_to(target)

    with pytest.raises(module.RawInputProvenanceError, match="symlink"):
        module.digest_raw_input(link)


def test_raw_digest_rejects_nonregular_input_and_invalid_block_size(tmp_path):
    module = load_module()
    source = tmp_path / "raw.root"
    source.write_bytes(b"beam-bytes")

    with pytest.raises(ValueError, match="block_size must be positive"):
        module.digest_raw_input(source, block_size=0)
    with pytest.raises(module.RawInputProvenanceError, match="not a regular file"):
        module.digest_raw_input(tmp_path)


def test_data_provenance_never_truncates_digest_manifest(tmp_path):
    module = load_module()
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    runs = [31, 32, 33, 34]
    for run in runs:
        (raw_dir / f"hrdb_run_{run:04d}.root").write_bytes(f"run-{run}".encode())

    canon_path = tmp_path / "canon.csv"
    pd.DataFrame(
        {
            "run": runs,
            "eventno": [1, 1, 1, 1],
            "stave": ["B2", "B2", "B2", "B2"],
        }
    ).to_csv(canon_path, index=False)

    module.RAW_DIR = raw_dir
    module.CANON = canon_path
    module.REBUILT = tmp_path / "absent-rebuilt.csv"
    module.OUT = tmp_path / "out"
    module.OUT.mkdir()

    record, _ = module.data_provenance()
    persisted = json.loads((module.OUT / "provenance.json").read_text())

    assert record["raw_input_sha256_count"] == len(runs)
    assert len(record["raw_input_sha256"]) == len(runs)
    assert [row["run"] for row in record["raw_input_sha256"]] == runs
    assert record["raw_input_missing_runs"] == []
    assert record["raw_input_sha256_complete"] is True
    assert record["raw_input_digest_schema"] == "same-open-stream-v1"
    assert "one O_NOFOLLOW descriptor" in record["raw_input_digest_contract"]
    assert persisted["raw_input_sha256"] == record["raw_input_sha256"]
    assert persisted["raw_input_sha256_count"] == len(persisted["raw_input_sha256"])
    assert persisted["raw_input_digest_schema"] == "same-open-stream-v1"

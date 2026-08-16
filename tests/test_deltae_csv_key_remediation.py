"""Regression tests for the canonical DeltaE CSV composite-key remediation."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.single_stave import deltaE_E as de  # noqa: E402
from tools.audit.audit_deltae_csv_key_identity import audit_source  # noqa: E402


def _write_csv(path: Path, header: str, rows: list[str]) -> bytes:
    raw = (header + "\n" + "\n".join(rows) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


def test_reader_preserves_all_three_composite_key_tokens(tmp_path):
    data_path = tmp_path / "data.csv"
    mc_path = tmp_path / "mc.csv"
    _write_csv(
        data_path,
        "source_file_id,run_id,event_id,amp_B2,sample,trigger_definition",
        ["001,0007,0009,120,I,beam_v1"],
    )
    _write_csv(
        mc_path,
        "source_file_id,run_id,event_id,edep_B2",
        ["1,7,9,1.5"],
    )

    data = de.read_table(data_path)
    mc = de.read_table(mc_path)

    assert data.loc[0, "source_file_id"] == "001"
    assert data.loc[0, "run_id"] == "0007"
    assert data.loc[0, "event_id"] == "0009"
    assert all(str(data[column].dtype) == "string" for column in de.KEY_COLS)
    assert len(data.merge(mc, on=list(de.KEY_COLS), how="inner")) == 0


def test_reader_rejects_invalid_utf8(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_bytes(b"source_file_id,run_id,event_id\n001,7,\xff\n")
    with pytest.raises(SystemExit, match="not valid UTF-8"):
        de.read_table(path)


def test_manifest_reuses_exact_csv_snapshot(tmp_path):
    path = tmp_path / "data.csv"
    original = _write_csv(
        path,
        "source_file_id,run_id,event_id,amp_B2,sample,trigger_definition",
        ["001,7,9,120,I,beam_v1"],
    )
    de.read_table(path)
    path.write_text(
        "source_file_id,run_id,event_id,amp_B2,sample,trigger_definition\n"
        "CHANGED,7,9,120,I,beam_v1\n",
        encoding="utf-8",
    )

    out = tmp_path / "out"
    out.mkdir()
    args = argparse.Namespace(
        data_table=path,
        mc_table=path,
        out=out,
        stop_thresholds="0.05",
        data_thresholds="20",
        sample="all",
        seed=1,
        bins=4,
    )
    de.write_manifest(out, args, [path])
    record = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["inputs"][0]

    assert record["bytes"] == len(original)
    assert record["sha256"] == hashlib.sha256(original).hexdigest()
    assert record["snapshot_policy"] == de.CSV_SNAPSHOT_POLICY
    assert record["key_dtypes"] == de.CSV_KEY_DTYPES


def test_current_source_audit_returns_zero_findings():
    payload = audit_source(ROOT / "scripts/single_stave/deltaE_E.py")
    assert payload["status"] == "VALIDATED"
    assert payload["findings"] == []


def test_direct_cli_preserves_distinct_exact_keys(tmp_path):
    data_path = tmp_path / "data.csv"
    mc_path = tmp_path / "mc.csv"
    data_rows = [
        f"001,0007,{event:04d},{120 + event},20,10,5,I,beam_v1"
        for event in range(12)
    ]
    mc_rows = [
        f"1,7,{event},1.5,0.6,0.3,0.1,1.0"
        for event in range(12)
    ]
    data_raw = _write_csv(
        data_path,
        "source_file_id,run_id,event_id,amp_B2,amp_B4,amp_B6,amp_B8,"
        "sample,trigger_definition",
        data_rows,
    )
    mc_raw = _write_csv(
        mc_path,
        "source_file_id,run_id,event_id,edep_B2,edep_B4,edep_B6,edep_B8,PrimaryWeight",
        mc_rows,
    )
    out = tmp_path / "out"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/single_stave/deltaE_E.py"),
            "--data-table",
            str(data_path),
            "--mc-table",
            str(mc_path),
            "--out",
            str(out),
            "--bins",
            "4",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert result["join_cardinality"]["n_matched"] == 0
    assert result["input_reader_contract"]["csv_key_policy"] == de.CSV_KEY_POLICY
    assert manifest["inputs"][0]["sha256"] == hashlib.sha256(data_raw).hexdigest()
    assert manifest["inputs"][1]["sha256"] == hashlib.sha256(mc_raw).hexdigest()
    assert all(item["snapshot_policy"] == de.CSV_SNAPSHOT_POLICY for item in manifest["inputs"])

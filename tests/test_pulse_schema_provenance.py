#!/usr/bin/env python3
"""Regression tests for pulse-schema validation provenance."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / "tools" / "audit"
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

import validate_pulse_schema  # noqa: E402


def test_compressed_csv_records_immutable_input_provenance(tmp_path):
    frame = pd.DataFrame(
        {
            "run": [1, 1],
            "evt": [10, 11],
            "stave": [0, 0],
            "baseline_adc": [500.0, 501.0],
            "peak_height_adc": [1200.0, 1300.0],
        }
    )
    table = tmp_path / "pulse.csv.gz"
    frame.to_csv(table, index=False, compression="gzip")
    output = tmp_path / "validation.json"

    with pytest.raises(SystemExit) as exc:
        validate_pulse_schema.main(
            [
                str(table),
                "--out",
                str(output),
                "--schema-version",
                "v1",
            ]
        )

    assert exc.value.code == 0
    result = json.loads(output.read_text())
    provenance = result["provenance"]
    assert result["rows"] == 2
    assert provenance["input_path"] == str(table)
    assert provenance["input_size_bytes"] == table.stat().st_size
    assert provenance["input_sha256"] == hashlib.sha256(table.read_bytes()).hexdigest()
    assert provenance["tool"] == "tools/audit/validate_pulse_schema.py"
    assert provenance["tool_version"] == "1.1.0"

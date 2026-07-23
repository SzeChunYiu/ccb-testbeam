from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

REFERENCE_SHA256 = "b" * 64


def write_table(path: Path) -> str:
    pd.DataFrame({
        "amplitude_adc": [100.0, 200.0, 300.0],
        "baseline_adc": [6752.0, 6752.0, 6752.0],
    }).to_csv(path, index=False)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_cli_rejects_evidence_without_reference(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    digest = write_table(table)
    evidence.write_text(json.dumps({digest: {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference_sha256": REFERENCE_SHA256,
    }}), encoding="utf-8")

    with pytest.raises(ValueError, match="evidence_reference"):
        MODULE.main([
            str(table), "--output", str(output), "--evidence-map", str(evidence)
        ])


def test_programmatic_audit_rejects_untraceable_map(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    digest = write_table(table)

    with pytest.raises(ValueError, match="evidence_reference"):
        MODULE.audit(table, None, 3500.0, 5000.0, {digest: {
            "convention": "NET",
            "evidence_basis": "PRODUCER_CODE_PROVENANCE",
            "evidence_reference_sha256": REFERENCE_SHA256,
        }})


def test_programmatic_audit_rejects_unbound_reference(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    digest = write_table(table)

    with pytest.raises(ValueError, match="evidence_reference_sha256"):
        MODULE.audit(table, None, 3500.0, 5000.0, {digest: {
            "convention": "NET",
            "evidence_basis": "PRODUCER_CODE_PROVENANCE",
            "evidence_reference": "docs/contracts/PULSE_TABLE_CONTRACT.md",
        }})


def test_traceable_map_is_normalized_and_exposed(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    digest = write_table(table)
    reference = "docs/contracts/PULSE_TABLE_CONTRACT.md#amplitude-semantics"
    evidence.write_text(json.dumps({digest: {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": f"  {reference}  ",
        "evidence_reference_sha256": REFERENCE_SHA256,
    }}), encoding="utf-8")

    assert MODULE.main([
        str(table), "--output", str(output), "--evidence-map", str(evidence)
    ]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    row = payload["tables"][0]
    assert row["physics_acceptance"] == "ACCEPTABLE"
    assert row["physics_evidence_reference"] == reference
    assert row["evidence_record"]["evidence_reference_sha256"] == REFERENCE_SHA256
    assert row["evidence_record"]["sha256"] == digest

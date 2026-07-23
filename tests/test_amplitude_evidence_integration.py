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


def write_reference(path: Path) -> str:
    path.write_text("producer contract v1\namplitude is net\n", encoding="utf-8")
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
            "evidence_reference": "producer_contract.md",
        }})


def test_raw_programmatic_map_cannot_authorize_unverified_reference_bytes(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    digest = write_table(table)
    result = MODULE.audit(table, None, 3500.0, 5000.0, {digest: {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": "producer_contract.md",
        "evidence_reference_sha256": REFERENCE_SHA256,
    }})
    assert result["evidence_record"]["evidence_reference_verified"] is False
    assert result["physics_acceptance"] == "UNVERIFIED"
    assert result["physics_convention"] is None
    assert result["physics_evidence_reference_verified"] is False
    assert "EVIDENCE_REFERENCE_BYTES_UNVERIFIED" in result["warnings"]


def test_traceable_map_is_normalized_verified_and_exposed(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    reference_file = tmp_path / "producer_contract.md"
    digest = write_table(table)
    reference_digest = write_reference(reference_file)
    reference = f"{reference_file.name}#L2"
    evidence.write_text(json.dumps({digest: {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": f"  {reference}  ",
        "evidence_reference_sha256": reference_digest,
    }}), encoding="utf-8")

    assert MODULE.main([
        str(table), "--output", str(output), "--evidence-map", str(evidence)
    ]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    row = payload["tables"][0]
    assert row["physics_acceptance"] == "ACCEPTABLE"
    assert row["physics_evidence_reference"] == reference
    assert row["physics_evidence_reference_sha256"] == reference_digest
    assert row["physics_evidence_reference_verified"] is True
    assert row["evidence_record"]["evidence_reference_verified"] is True
    assert row["evidence_record"]["evidence_reference_fragment_verified"] is True
    assert row["evidence_record"]["evidence_reference_line_start"] == 2
    assert row["evidence_record"]["evidence_reference_line_end"] == 2
    assert row["evidence_record"]["evidence_reference_measured_sha256"] == reference_digest
    assert row["evidence_record"]["sha256"] == digest


def test_cli_rejects_non_line_fragment(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    reference_file = tmp_path / "producer_contract.md"
    digest = write_table(table)
    reference_digest = write_reference(reference_file)
    evidence.write_text(json.dumps({digest: {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": f"{reference_file.name}#amplitude-semantics",
        "evidence_reference_sha256": reference_digest,
    }}), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical line fragment"):
        MODULE.main([
            str(table), "--output", str(output), "--evidence-map", str(evidence)
        ])


def test_cli_rejects_mutated_supporting_artifact(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    reference_file = tmp_path / "producer_contract.md"
    digest = write_table(table)
    reference_digest = write_reference(reference_file)
    evidence.write_text(json.dumps({digest: {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": reference_file.name,
        "evidence_reference_sha256": reference_digest,
    }}), encoding="utf-8")
    reference_file.write_text("producer contract v2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="evidence_reference_sha256 mismatch"):
        MODULE.main([
            str(table), "--output", str(output), "--evidence-map", str(evidence)
        ])

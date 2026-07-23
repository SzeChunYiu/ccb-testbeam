from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_table(path: Path, amplitude: list[float], baseline: list[float]) -> str:
    pd.DataFrame({"amplitude_adc": amplitude, "baseline_adc": baseline}).to_csv(path, index=False)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_baseline_column_alone_does_not_accept_physics_convention(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    write_table(path, [6700, 6750, 6800], [6752, 6752, 6752])

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["heuristic_convention"] == "ABSOLUTE"
    assert result["physics_acceptance"] == "UNVERIFIED"
    assert result["physics_subtract_baseline_correct"] is None
    assert "NO_HASH_BOUND_CONVENTION_EVIDENCE" in result["warnings"]


def test_hash_bound_evidence_accepts_exact_table(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    digest = write_table(path, [100, 200, 300], [6752, 6752, 6752])
    evidence = {
        digest: {
            "convention": "NET",
            "evidence_basis": "PRODUCER_CODE_PROVENANCE",
            "citation": "producer emits baseline-subtracted peak height",
        }
    }

    result = MODULE.audit(path, None, 3500.0, 5000.0, evidence)

    assert result["physics_convention"] == "NET"
    assert result["physics_acceptance"] == "ACCEPTABLE"
    assert result["physics_subtract_baseline_correct"] is False
    assert result["physics_convention_evidence"] == "PRODUCER_CODE_PROVENANCE"


def test_evidence_does_not_transfer_after_file_change(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    digest = write_table(path, [6700, 6750, 6800], [6752, 6752, 6752])
    evidence = {
        digest: {
            "convention": "ABSOLUTE",
            "evidence_basis": "INDEPENDENTLY_REVIEWED_PEDESTAL_EVIDENCE",
        }
    }
    pd.DataFrame({"amplitude_adc": [100, 200], "baseline_adc": [6752, 6752]}).to_csv(path, index=False)

    result = MODULE.audit(path, None, 3500.0, 5000.0, evidence)

    assert result["physics_acceptance"] == "UNVERIFIED"
    assert result["physics_subtract_baseline_correct"] is None


def test_main_fails_without_evidence_and_passes_with_exact_evidence(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    output = tmp_path / "audit.json"
    evidence_path = tmp_path / "evidence.json"
    digest = write_table(path, [6700, 6750, 6800], [6752, 6752, 6752])

    assert MODULE.main([str(path), "--output", str(output)]) == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["n_unverified_conventions"] == 1

    evidence_path.write_text(json.dumps({digest: {
        "convention": "ABSOLUTE",
        "evidence_basis": "EXPLICIT_SCHEMA_METADATA",
    }}), encoding="utf-8")
    assert MODULE.main([
        str(path), "--output", str(output), "--evidence-map", str(evidence_path)
    ]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["n_unverified_conventions"] == 0


def test_invalid_evidence_basis_is_rejected(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps({"a" * 64: {
        "convention": "NET", "evidence_basis": "RAW_MEDIAN"
    }}), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid evidence_basis"):
        MODULE.load_evidence_map(evidence_path)

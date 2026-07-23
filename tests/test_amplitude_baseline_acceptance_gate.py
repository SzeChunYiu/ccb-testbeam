from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path: Path, **columns: list[float]) -> None:
    pd.DataFrame(columns).to_csv(path, index=False)


def write_reference(tmp_path: Path) -> tuple[str, str]:
    reference = tmp_path / "pulse_contract.md"
    reference.write_text("amplitude convention contract v1\n", encoding="utf-8")
    return reference.name, hashlib.sha256(reference.read_bytes()).hexdigest()


def evidence_record(
    convention: str,
    basis: str,
    reference: str,
    reference_sha256: str,
) -> dict[str, str]:
    return {
        "convention": convention,
        "evidence_basis": basis,
        "evidence_reference": reference,
        "evidence_reference_sha256": reference_sha256,
    }


def test_absolute_tables_with_unresolved_baselines_fail_gate(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    multiple = tmp_path / "multiple.csv"
    output = tmp_path / "audit.json"
    write(missing, amplitude_adc=[6700, 6750, 6800])
    write(
        multiple,
        amplitude_adc=[6700, 6750, 6800],
        baseline_adc=[6752, 6752, 6752],
        baseline_mean_adc=[6751, 6751, 6751],
    )
    code = MODULE.main([str(missing), str(multiple), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 1
    assert payload["n_unresolved_absolute_baselines"] == 2
    assert [row["baseline_resolution"] for row in payload["tables"]] == [
        "MISSING",
        "AMBIGUOUS",
    ]


def test_unique_pedestal_still_requires_hash_bound_evidence(tmp_path: Path) -> None:
    path = tmp_path / "resolved.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    write(
        path,
        amplitude_adc=[6700, 6750, 6800],
        baseline_adc=[6752, 6752, 6752],
    )
    assert MODULE.main([str(path), "--output", str(output)]) == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["n_unverified_conventions"] == 1
    assert payload["tables"][0]["baseline_resolution"] == "RESOLVED"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    reference, reference_sha256 = write_reference(tmp_path)
    evidence.write_text(json.dumps({digest: evidence_record(
        "ABSOLUTE", "EXPLICIT_SCHEMA_METADATA", reference, reference_sha256
    )}), encoding="utf-8")
    assert MODULE.main([
        str(path), "--output", str(output), "--evidence-map", str(evidence)
    ]) == 0


def test_net_table_requires_hash_bound_evidence(tmp_path: Path) -> None:
    path = tmp_path / "net.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    write(path, amplitude_adc=[100, 200, 300])
    assert MODULE.main([str(path), "--output", str(output)]) == 1
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    reference, reference_sha256 = write_reference(tmp_path)
    evidence.write_text(json.dumps({digest: evidence_record(
        "NET", "PRODUCER_CODE_PROVENANCE", reference, reference_sha256
    )}), encoding="utf-8")
    assert MODULE.main([
        str(path), "--output", str(output), "--evidence-map", str(evidence)
    ]) == 0

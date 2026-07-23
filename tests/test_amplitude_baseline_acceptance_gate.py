from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path: Path, **columns: list[float]) -> None:
    pd.DataFrame(columns).to_csv(path, index=False)


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
    evidence.write_text(json.dumps({digest: {
        "convention": "ABSOLUTE",
        "evidence_basis": "EXPLICIT_SCHEMA_METADATA",
    }}), encoding="utf-8")
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
    evidence.write_text(json.dumps({digest: {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
    }}), encoding="utf-8")
    assert MODULE.main([
        str(path), "--output", str(output), "--evidence-map", str(evidence)
    ]) == 0

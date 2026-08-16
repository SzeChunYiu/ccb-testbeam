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


def verified_evidence_for(
    tmp_path: Path,
    path: Path,
    convention: str,
) -> dict[str, dict[str, object]]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    reference = tmp_path / "producer_contract.md"
    reference.write_text("producer code provenance v1\n", encoding="utf-8")
    reference_digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps({digest: {
        "convention": convention,
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": reference.name,
        "evidence_reference_sha256": reference_digest,
    }}), encoding="utf-8")
    return MODULE.load_evidence_map(evidence_path)


def test_hash_bound_absolute_requires_unique_pedestal_column(tmp_path: Path) -> None:
    path = tmp_path / "absolute.csv"
    pd.DataFrame({"amplitude_adc": [6700, 6750, 6800]}).to_csv(path, index=False)
    evidence = verified_evidence_for(tmp_path, path, "ABSOLUTE")
    result = MODULE.audit(path, None, 3500.0, 5000.0, evidence)
    assert result["physics_convention"] == "ABSOLUTE"
    assert result["physics_acceptance"] == "BASELINE_SCHEMA_UNRESOLVED"
    assert result["physics_subtract_baseline_correct"] is None
    assert "HASH_BOUND_ABSOLUTE_WITHOUT_UNIQUE_BASELINE" in result["warnings"]


def test_hash_bound_absolute_requires_complete_pedestal_data(tmp_path: Path) -> None:
    path = tmp_path / "absolute.csv"
    pd.DataFrame({
        "amplitude_adc": [6700, 6750, 6800],
        "baseline_adc": [6752, None, 6752],
    }).to_csv(path, index=False)
    evidence = verified_evidence_for(tmp_path, path, "ABSOLUTE")
    result = MODULE.audit(path, None, 3500.0, 5000.0, evidence)
    assert result["physics_acceptance"] == "BASELINE_DATA_INVALID"
    assert result["physics_subtract_baseline_correct"] is None
    assert "HASH_BOUND_ABSOLUTE_WITH_INVALID_BASELINE_DATA" in result["warnings"]


def test_hash_bound_net_does_not_require_optional_pedestal_data(tmp_path: Path) -> None:
    path = tmp_path / "net.csv"
    pd.DataFrame({
        "amplitude_adc": [100, 200, 300],
        "baseline_adc": [6752, None, 6752],
    }).to_csv(path, index=False)
    output = tmp_path / "audit.json"
    evidence_path = tmp_path / "evidence.json"
    evidence = verified_evidence_for(tmp_path, path, "NET")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    result = MODULE.audit(path, None, 3500.0, 5000.0, evidence)
    assert result["physics_acceptance"] == "ACCEPTABLE"
    assert result["physics_subtract_baseline_correct"] is False
    assert MODULE.main([
        str(path), "--output", str(output), "--evidence-map", str(evidence_path)
    ]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["n_nonaccepted_physics_conventions"] == 0

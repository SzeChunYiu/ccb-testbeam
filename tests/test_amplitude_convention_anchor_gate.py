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


def write(path: Path, amplitude: list[float], baseline: list[float] | None = None) -> None:
    data = {"amplitude_adc": amplitude}
    if baseline is not None:
        data["baseline_adc"] = baseline
    pd.DataFrame(data).to_csv(path, index=False)


def test_raw_median_net_label_without_pedestal_is_non_accepting(tmp_path: Path) -> None:
    path = tmp_path / "unanchored_net.csv"
    output = tmp_path / "audit.json"
    write(path, [2600.0, 2625.0, 2650.0])
    result = MODULE.audit(path, None, 3500.0, 5000.0)
    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result["convention"] == "NET"
    assert result["convention_evidence"] == "RAW_MEDIAN_HEURISTIC"
    assert result["convention_acceptance"] == "UNANCHORED"
    assert result["physics_acceptance"] == "UNVERIFIED"
    assert result["physics_subtract_baseline_correct"] is None
    assert payload["n_unanchored_conventions"] == 1
    assert payload["n_unverified_conventions"] == 1
    assert code == 1


def test_raw_median_absolute_label_without_pedestal_is_non_accepting(tmp_path: Path) -> None:
    path = tmp_path / "unanchored_absolute.csv"
    output = tmp_path / "audit.json"
    write(path, [6700.0, 6750.0, 6800.0])
    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["tables"][0]["convention"] == "ABSOLUTE"
    assert payload["tables"][0]["physics_acceptance"] == "UNVERIFIED"
    assert payload["n_unresolved_absolute_baselines"] == 1
    assert payload["n_unverified_conventions"] == 1
    assert code == 1


def test_unique_pedestal_is_diagnostic_not_convention_proof(tmp_path: Path) -> None:
    path = tmp_path / "anchored.csv"
    output = tmp_path / "audit.json"
    evidence = tmp_path / "evidence.json"
    reference = tmp_path / "pulse_contract.md"
    reference.write_text("explicit amplitude schema metadata\n", encoding="utf-8")
    reference_digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    write(path, [6700.0, 6750.0, 6800.0], [6752.0, 6752.0, 6752.0])
    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    result = payload["tables"][0]
    assert result["convention_evidence"] == "PEDESTAL_ANCHORED"
    assert result["convention_acceptance"] == "ACCEPTABLE"
    assert result["physics_acceptance"] == "UNVERIFIED"
    assert result["baseline_resolution"] == "RESOLVED"
    assert payload["n_unverified_conventions"] == 1
    assert code == 1
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    evidence.write_text(json.dumps({digest: {
        "convention": "ABSOLUTE",
        "evidence_basis": "INDEPENDENTLY_REVIEWED_PEDESTAL_EVIDENCE",
        "evidence_reference": reference.name,
        "evidence_reference_sha256": reference_digest,
    }}), encoding="utf-8")
    assert MODULE.main([
        str(path), "--output", str(output), "--evidence-map", str(evidence)
    ]) == 0

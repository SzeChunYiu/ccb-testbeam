from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "validate_amplitude_evidence_map.py"
SPEC = importlib.util.spec_from_file_location("validate_amplitude_evidence_map", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

DIGEST = "a" * 64


def valid_record() -> dict[str, str]:
    return {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": "src/pulse_builder.py@0123456789abcdef",
    }


def test_accepts_traceable_hash_bound_record(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "validated.json"
    evidence.write_text(json.dumps({DIGEST: valid_record()}), encoding="utf-8")

    assert MODULE.main([str(evidence), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    record = result["records"][DIGEST]
    assert record["sha256"] == DIGEST
    assert record["evidence_reference"] == "src/pulse_builder.py@0123456789abcdef"


def test_rejects_record_without_evidence_reference() -> None:
    record = valid_record()
    del record["evidence_reference"]
    with pytest.raises(ValueError, match="evidence_reference"):
        MODULE.validate_payload({DIGEST: record})


@pytest.mark.parametrize("digest", ["A" * 64, "g" * 64, "a" * 63])
def test_rejects_noncanonical_digest_keys(digest: str) -> None:
    with pytest.raises(ValueError, match="lowercase 64-character hexadecimal"):
        MODULE.validate_payload({digest: valid_record()})


def test_rejects_mismatched_embedded_digest() -> None:
    record = valid_record()
    record["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="mismatched sha256"):
        MODULE.validate_payload({DIGEST: record})


def test_rejects_invalid_basis() -> None:
    record = valid_record()
    record["evidence_basis"] = "RAW_MEDIAN"
    with pytest.raises(ValueError, match="invalid evidence_basis"):
        MODULE.validate_payload({DIGEST: record})

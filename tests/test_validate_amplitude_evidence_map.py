from __future__ import annotations

import hashlib
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
REFERENCE_DIGEST = "b" * 64


def valid_record(
    reference: str = "producer_contract.md",
    reference_digest: str = REFERENCE_DIGEST,
) -> dict[str, str]:
    return {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": reference,
        "evidence_reference_sha256": reference_digest,
    }


def test_accepts_and_verifies_traceable_hash_bound_record(tmp_path: Path) -> None:
    reference = tmp_path / "producer_contract.md"
    reference.write_text("producer contract v1\n", encoding="utf-8")
    reference_digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "validated.json"
    evidence.write_text(
        json.dumps({DIGEST: valid_record(reference.name, reference_digest)}),
        encoding="utf-8",
    )

    assert MODULE.main([str(evidence), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    record = result["records"][DIGEST]
    assert record["sha256"] == DIGEST
    assert record["evidence_reference"] == reference.name
    assert record["evidence_reference_sha256"] == reference_digest
    assert record["evidence_reference_measured_sha256"] == reference_digest
    assert record["evidence_reference_verified"] is True
    assert record["evidence_reference_resolved_path"] == str(reference.resolve())
    assert result["n_verified_references"] == 1


def test_schema_only_validation_cannot_claim_reference_verification() -> None:
    record = MODULE.validate_payload({DIGEST: valid_record()})[DIGEST]
    assert record["evidence_reference_verified"] is False
    assert "evidence_reference_measured_sha256" not in record


def test_rejects_record_without_evidence_reference() -> None:
    record = valid_record()
    del record["evidence_reference"]
    with pytest.raises(ValueError, match="evidence_reference"):
        MODULE.validate_payload({DIGEST: record})


def test_rejects_record_without_evidence_reference_digest() -> None:
    record = valid_record()
    del record["evidence_reference_sha256"]
    with pytest.raises(ValueError, match="evidence_reference_sha256"):
        MODULE.validate_payload({DIGEST: record})


@pytest.mark.parametrize("reference_digest", ["B" * 64, "z" * 64, "b" * 63])
def test_rejects_noncanonical_evidence_reference_digest(reference_digest: str) -> None:
    record = valid_record(reference_digest=reference_digest)
    with pytest.raises(ValueError, match="evidence_reference_sha256"):
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


def test_rejects_declared_digest_that_does_not_match_reference_bytes(tmp_path: Path) -> None:
    reference = tmp_path / "producer_contract.md"
    reference.write_text("actual bytes\n", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence_reference_sha256 mismatch"):
        MODULE.validate_payload(
            {DIGEST: valid_record(reference.name, "b" * 64)},
            evidence_root=tmp_path,
        )


def test_rejects_missing_reference_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="references missing file"):
        MODULE.validate_payload(
            {DIGEST: valid_record("missing.md", "b" * 64)},
            evidence_root=tmp_path,
        )


def test_rejects_reference_path_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-reference.md"
    outside.write_text("outside\n", encoding="utf-8")
    outside_digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    try:
        with pytest.raises(ValueError, match="escapes the configured evidence root"):
            MODULE.validate_payload(
                {DIGEST: valid_record(f"../{outside.name}", outside_digest)},
                evidence_root=tmp_path,
            )
    finally:
        outside.unlink(missing_ok=True)

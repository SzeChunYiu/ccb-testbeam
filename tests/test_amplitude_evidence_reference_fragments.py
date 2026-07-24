from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "validate_amplitude_evidence_map.py"
SPEC = importlib.util.spec_from_file_location("validate_amplitude_evidence_map", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

DIGEST = "a" * 64


def record(reference: str, reference_sha256: str = "b" * 64) -> dict[str, str]:
    return {
        "convention": "NET",
        "evidence_basis": "PRODUCER_CODE_PROVENANCE",
        "evidence_reference": reference,
        "evidence_reference_sha256": reference_sha256,
    }


def test_verifies_exact_supporting_line_range(tmp_path: Path) -> None:
    reference = tmp_path / "producer_contract.md"
    reference.write_text("header\namplitude is net\nlimitations\n", encoding="utf-8")
    reference_digest = hashlib.sha256(reference.read_bytes()).hexdigest()

    normalized = MODULE.validate_payload(
        {DIGEST: record(f"{reference.name}#L2-L3", reference_digest)},
        evidence_root=tmp_path,
    )[DIGEST]

    expected_fragment = b"amplitude is net\nlimitations\n"
    assert normalized["evidence_reference_scope"] == "LINE_RANGE"
    assert normalized["evidence_reference_line_start"] == 2
    assert normalized["evidence_reference_line_end"] == 3
    assert normalized["evidence_reference_line_count"] == 3
    assert normalized["evidence_reference_fragment_verified"] is True
    assert normalized["evidence_reference_fragment_size_bytes"] == len(expected_fragment)
    assert normalized["evidence_reference_fragment_nonblank_lines"] == 2
    assert normalized["evidence_reference_fragment_sha256"] == hashlib.sha256(
        expected_fragment
    ).hexdigest()
    assert normalized["evidence_validator_version"] == "1.4.0"


def test_rejects_whitespace_only_supporting_line(tmp_path: Path) -> None:
    reference = tmp_path / "producer_contract.md"
    reference.write_bytes(b"header\n \t \nactual statement\n")
    reference_digest = hashlib.sha256(reference.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="only blank or whitespace"):
        MODULE.validate_payload(
            {DIGEST: record(f"{reference.name}#L2", reference_digest)},
            evidence_root=tmp_path,
        )


@pytest.mark.parametrize(
    "reference",
    [
        "producer_contract.md#",
        "producer_contract.md#amplitude-semantics",
        "producer_contract.md#L0",
        "producer_contract.md#L2-L1",
        "producer_contract.md#L1-L2-extra",
    ],
)
def test_rejects_unverifiable_or_reversed_fragments(reference: str) -> None:
    with pytest.raises(ValueError, match="fragment|line range"):
        MODULE.validate_payload({DIGEST: record(reference)})


def test_rejects_line_range_beyond_supporting_artifact(tmp_path: Path) -> None:
    reference = tmp_path / "producer_contract.md"
    reference.write_text("one line\n", encoding="utf-8")
    reference_digest = hashlib.sha256(reference.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="only 1 lines"):
        MODULE.validate_payload(
            {DIGEST: record(f"{reference.name}#L2", reference_digest)},
            evidence_root=tmp_path,
        )

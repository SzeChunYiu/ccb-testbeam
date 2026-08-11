from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.audit.repository_content_transfer import (
    SCHEMA,
    _digest_body,
    create_receipt,
    git_blob_sha1,
    verify_receipt,
)


def test_git_blob_sha1_matches_git_object_definition() -> None:
    data = b"test content\n"
    expected = hashlib.sha1(b"blob 13\x00" + data).hexdigest()
    assert git_blob_sha1(data) == expected


def test_nominal_byte_exact_transfer_passes(tmp_path: Path) -> None:
    authoring = tmp_path / "authoring.py"
    committed = tmp_path / "committed.py"
    payload = b"print('alpha')\n"
    authoring.write_bytes(payload)
    committed.write_bytes(payload)
    receipt = create_receipt(
        authoring_file=authoring,
        repository_path="tools/example.py",
    )
    result = verify_receipt(
        receipt=receipt,
        committed_file=committed,
        observed_repository_path="tools/example.py",
        observed_github_blob_sha=git_blob_sha1(payload),
    )
    assert result["status"] == "PASS"
    assert result["committed"]["sha256"] == hashlib.sha256(payload).hexdigest()


def test_truncation_fails(tmp_path: Path) -> None:
    authoring = tmp_path / "a"
    committed = tmp_path / "c"
    authoring.write_bytes(b"abcdef")
    committed.write_bytes(b"abc")
    receipt = create_receipt(authoring_file=authoring, repository_path="x")
    with pytest.raises(ValueError, match="differ"):
        verify_receipt(
            receipt=receipt,
            committed_file=committed,
            observed_repository_path="x",
        )


def test_same_size_corruption_fails(tmp_path: Path) -> None:
    authoring = tmp_path / "a"
    committed = tmp_path / "c"
    authoring.write_bytes(b"abcdef")
    committed.write_bytes(b"abcdeg")
    receipt = create_receipt(authoring_file=authoring, repository_path="x")
    with pytest.raises(ValueError, match="differ"):
        verify_receipt(
            receipt=receipt,
            committed_file=committed,
            observed_repository_path="x",
        )


def test_newline_normalization_is_not_silently_equivalent(tmp_path: Path) -> None:
    authoring = tmp_path / "a"
    committed = tmp_path / "c"
    authoring.write_bytes(b"a\r\nb\r\n")
    committed.write_bytes(b"a\nb\n")
    receipt = create_receipt(authoring_file=authoring, repository_path="x")
    with pytest.raises(ValueError, match="differ"):
        verify_receipt(
            receipt=receipt,
            committed_file=committed,
            observed_repository_path="x",
        )


def test_wrong_repository_path_fails(tmp_path: Path) -> None:
    authoring = tmp_path / "a"
    committed = tmp_path / "c"
    authoring.write_bytes(b"x")
    committed.write_bytes(b"x")
    receipt = create_receipt(authoring_file=authoring, repository_path="right")
    with pytest.raises(ValueError, match="repository path mismatch"):
        verify_receipt(
            receipt=receipt,
            committed_file=committed,
            observed_repository_path="wrong",
        )


def test_wrong_github_blob_sha_fails(tmp_path: Path) -> None:
    authoring = tmp_path / "a"
    committed = tmp_path / "c"
    authoring.write_bytes(b"x")
    committed.write_bytes(b"x")
    receipt = create_receipt(authoring_file=authoring, repository_path="x")
    with pytest.raises(ValueError, match="GitHub blob SHA differs"):
        verify_receipt(
            receipt=receipt,
            committed_file=committed,
            observed_repository_path="x",
            observed_github_blob_sha="0" * 40,
        )


def test_tampered_receipt_fails(tmp_path: Path) -> None:
    authoring = tmp_path / "a"
    committed = tmp_path / "c"
    authoring.write_bytes(b"x")
    committed.write_bytes(b"x")
    receipt = create_receipt(authoring_file=authoring, repository_path="x")
    receipt["authoring"]["bytes"] = 999
    with pytest.raises(ValueError, match="receipt digest mismatch"):
        verify_receipt(
            receipt=receipt,
            committed_file=committed,
            observed_repository_path="x",
        )


def test_receipt_schema_and_digest_are_stable(tmp_path: Path) -> None:
    authoring = tmp_path / "a"
    authoring.write_bytes(b"\x00\xff\n")
    receipt = create_receipt(authoring_file=authoring, repository_path="binary.dat")
    assert receipt["schema"] == SCHEMA
    body = dict(receipt)
    digest = body.pop("receipt_sha256")
    assert digest == _digest_body(body)

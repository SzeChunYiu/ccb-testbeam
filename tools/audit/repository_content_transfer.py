#!/usr/bin/env python3
"""Create and verify byte-exact authoring-to-repository transfer receipts.

This utility is a repository-provenance primitive. It distinguishes:
1. authoring bytes measured before a write/commit;
2. the Git blob object identity expected for those exact bytes; and
3. committed/fetched bytes observed after transfer.

SHA-256 is the primary content identity. Git's SHA-1 blob object ID is recorded
only as a repository-object cross-check for SHA-1 repositories / GitHub's
current file-content API representation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

SCHEMA = "ccb_repository_content_transfer_receipt_v1"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest_body(body: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(body)).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _read_stable_regular_file(path: Path, *, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"cannot open {label} {path}: {exc}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file: {path}")
        chunks: list[bytes] = []
        offset = 0
        while offset < before.st_size:
            try:
                block = os.pread(fd, min(1024 * 1024, before.st_size - offset), offset)
            except OSError as exc:
                raise ValueError(
                    f"cannot read {label} {path} at offset {offset}: {exc}"
                ) from exc
            if not block:
                raise ValueError(f"short read while reading {label}: {path}")
            chunks.append(block)
            offset += len(block)
        after = os.fstat(fd)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after:
            raise ValueError(f"{label} changed while being read: {path}")
        if offset != before.st_size:
            raise ValueError(f"byte-count mismatch while reading {label}: {path}")
        return b"".join(chunks)
    finally:
        os.close(fd)


def create_receipt(*, authoring_file: Path, repository_path: str) -> dict[str, Any]:
    if not repository_path or repository_path.startswith("/") or "\x00" in repository_path:
        raise ValueError("repository_path must be a non-empty relative repository path")
    data = _read_stable_regular_file(authoring_file, label="authoring file")
    body = {
        "schema": SCHEMA,
        "status": "MEASURED_AUTHORING_BYTES",
        "repository_path": repository_path,
        "authoring": {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": git_blob_sha1(data),
        },
        "semantics": "BYTE_EXACT_NO_CANONICALIZATION",
        "limitations": [
            "DOES_NOT_PROVE_REMOTE_COMMIT_UNTIL_VERIFICATION_PASSES",
            "GIT_FILTER_OR_EOL_TRANSFORMATION_IS_A_MISMATCH_UNLESS_SEPARATELY_DECLARED",
            "GIT_BLOB_SHA1_IS_REPOSITORY_OBJECT_CROSSCHECK_NOT_PRIMARY_CONTENT_HASH",
        ],
    }
    result = dict(body)
    result["receipt_sha256"] = _digest_body(body)
    return result


def verify_receipt(
    *,
    receipt: dict[str, Any],
    committed_file: Path,
    observed_repository_path: str,
    observed_github_blob_sha: str | None = None,
) -> dict[str, Any]:
    if receipt.get("schema") != SCHEMA:
        raise ValueError("unsupported receipt schema")
    if receipt.get("status") != "MEASURED_AUTHORING_BYTES":
        raise ValueError("receipt is not an authoring measurement")
    receipt_digest = receipt.get("receipt_sha256")
    if not isinstance(receipt_digest, str):
        raise ValueError("receipt missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if _digest_body(body) != receipt_digest:
        raise ValueError("receipt digest mismatch")

    expected_path = receipt.get("repository_path")
    if observed_repository_path != expected_path:
        raise ValueError(
            f"repository path mismatch: expected {expected_path!r}, "
            f"observed {observed_repository_path!r}"
        )
    expected = receipt.get("authoring")
    if not isinstance(expected, dict):
        raise ValueError("receipt missing authoring identity")
    expected_bytes = expected.get("bytes")
    expected_sha256 = expected.get("sha256")
    expected_blob = expected.get("git_blob_sha1")
    if (
        not isinstance(expected_bytes, int)
        or expected_bytes < 0
        or not isinstance(expected_sha256, str)
        or not isinstance(expected_blob, str)
    ):
        raise ValueError("receipt authoring identity is incomplete")

    data = _read_stable_regular_file(committed_file, label="committed file")
    observed = {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob_sha1": git_blob_sha1(data),
    }
    expected_identity = {
        "bytes": expected_bytes,
        "sha256": expected_sha256,
        "git_blob_sha1": expected_blob,
    }
    if observed != expected_identity:
        raise ValueError(
            "committed bytes differ from measured authoring bytes: "
            f"expected={expected_identity}, observed={observed}"
        )

    if observed_github_blob_sha is not None:
        if not isinstance(observed_github_blob_sha, str) or not observed_github_blob_sha:
            raise ValueError("observed GitHub blob SHA is invalid")
        if observed_github_blob_sha != observed["git_blob_sha1"]:
            raise ValueError(
                "GitHub blob SHA differs from byte-derived Git blob SHA-1: "
                f"reported={observed_github_blob_sha}, "
                f"derived={observed['git_blob_sha1']}"
            )

    result_body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_authoring_receipt_sha256": receipt_digest,
        "repository_path": observed_repository_path,
        "committed": observed,
        "observed_github_blob_sha": observed_github_blob_sha,
        "semantics": "BYTE_EXACT_NO_CANONICALIZATION",
    }
    result = dict(result_body)
    result["receipt_sha256"] = _digest_body(result_body)
    return result


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load receipt JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("receipt JSON must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--authoring-file", type=Path, required=True)
    create.add_argument("--repository-path", required=True)
    create.add_argument("--output-json", type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--receipt-json", type=Path, required=True)
    verify.add_argument("--committed-file", type=Path, required=True)
    verify.add_argument("--repository-path", required=True)
    verify.add_argument("--github-blob-sha")

    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create_receipt(
                authoring_file=args.authoring_file,
                repository_path=args.repository_path,
            )
        else:
            result = verify_receipt(
                receipt=_load_json_object(args.receipt_json),
                committed_file=args.committed_file,
                observed_repository_path=args.repository_path,
                observed_github_blob_sha=args.github_blob_sha,
            )
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.command == "create" and args.output_json is not None:
        args.output_json.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

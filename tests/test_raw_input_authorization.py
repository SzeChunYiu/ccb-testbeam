from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import pytest

from ccb_mc_validation.raw_input_authorization import (
    RawInputAuthorizationError,
    verified_raw_input_stream,
)


def manifest_row(path: Path) -> dict[str, object]:
    info = path.stat()
    payload = path.read_bytes()
    return {
        "run": 31,
        "file": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "source_dev": int(info.st_dev),
        "source_ino": int(info.st_ino),
        "source_nlink": int(info.st_nlink),
        "source_mtime_ns": int(info.st_mtime_ns),
        "source_ctime_ns": int(info.st_ctime_ns),
    }


def test_verified_raw_stream_consumes_manifest_bound_bytes(tmp_path):
    source = tmp_path / "raw.root"
    payload = b"authorized-root-bytes"
    source.write_bytes(payload)
    row = manifest_row(source)

    with verified_raw_input_stream(source, row, block_size=3) as stream:
        assert stream.read(4) == payload[:4]
        stream.seek(0)
        assert stream.read() == payload


def test_independent_path_reopen_can_consume_replacement_after_manifest(tmp_path):
    source = tmp_path / "raw.root"
    replacement = tmp_path / "replacement.root"
    source.write_bytes(b"authorized")
    row = manifest_row(source)
    replacement.write_bytes(b"different-scientific-bytes")
    replacement.replace(source)

    assert source.read_bytes() != b"authorized"
    assert hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"]


def test_same_content_replacement_is_rejected_by_descriptor_identity(tmp_path):
    source = tmp_path / "raw.root"
    replacement = tmp_path / "replacement.root"
    payload = b"same-content-new-inode"
    source.write_bytes(payload)
    row = manifest_row(source)
    replacement.write_bytes(payload)
    replacement.replace(source)

    with pytest.raises(RawInputAuthorizationError, match="identity does not match"):
        with verified_raw_input_stream(source, row):
            pass


def test_different_content_replacement_is_rejected_before_consumer(tmp_path):
    source = tmp_path / "raw.root"
    replacement = tmp_path / "replacement.root"
    source.write_bytes(b"authorized")
    row = manifest_row(source)
    replacement.write_bytes(b"replacement")
    replacement.replace(source)

    with pytest.raises(RawInputAuthorizationError, match="identity does not match"):
        with verified_raw_input_stream(source, row):
            pass


def test_path_replacement_during_consumption_fails_closed(tmp_path):
    source = tmp_path / "raw.root"
    replacement = tmp_path / "replacement.root"
    original = b"authorized-open-inode"
    source.write_bytes(original)
    row = manifest_row(source)
    replacement.write_bytes(b"replacement")

    with pytest.raises(
        RawInputAuthorizationError, match="consumer held authorized stream"
    ):
        with verified_raw_input_stream(source, row) as stream:
            replacement.replace(source)
            stream.seek(0)
            assert stream.read() == original


def test_in_place_mutation_during_consumption_fails_closed(tmp_path):
    source = tmp_path / "raw.root"
    source.write_bytes(b"authorized")
    row = manifest_row(source)

    with pytest.raises(
        RawInputAuthorizationError, match="consumer held authorized stream"
    ):
        with verified_raw_input_stream(source, row) as stream:
            with source.open("ab") as handle:
                handle.write(b"-mutated")
            stream.seek(0)
            stream.read()


def test_hardlink_alias_change_during_consumption_fails_closed(tmp_path):
    source = tmp_path / "raw.root"
    alias = tmp_path / "alias.root"
    source.write_bytes(b"authorized")
    row = manifest_row(source)

    with pytest.raises(
        RawInputAuthorizationError, match="consumer held authorized stream"
    ):
        with verified_raw_input_stream(source, row) as stream:
            os.link(source, alias)
            assert stream.read(4) == b"auth"


def test_manifest_content_mismatch_fails_before_yield(tmp_path):
    source = tmp_path / "raw.root"
    source.write_bytes(b"authorized")
    row = manifest_row(source)
    row["sha256"] = hashlib.sha256(b"wrong").hexdigest()

    with pytest.raises(RawInputAuthorizationError, match="content does not match"):
        with verified_raw_input_stream(source, row):
            pytest.fail("consumer must not receive a mismatched stream")


def test_manifest_path_and_schema_are_strict(tmp_path):
    source = tmp_path / "raw.root"
    source.write_bytes(b"authorized")
    row = manifest_row(source)

    wrong_path = dict(row)
    wrong_path["file"] = str(tmp_path / "elsewhere.root")
    with pytest.raises(RawInputAuthorizationError, match="path does not match"):
        with verified_raw_input_stream(source, wrong_path):
            pass

    uppercase = dict(row)
    uppercase["sha256"] = str(row["sha256"]).upper()
    with pytest.raises(RawInputAuthorizationError, match="lowercase hexadecimal"):
        with verified_raw_input_stream(source, uppercase):
            pass

    boolean_size = dict(row)
    boolean_size["bytes"] = True
    with pytest.raises(RawInputAuthorizationError, match="bytes must be an integer"):
        with verified_raw_input_stream(source, boolean_size):
            pass


def test_symlink_and_invalid_block_size_fail_closed(tmp_path):
    source = tmp_path / "raw.root"
    source.write_bytes(b"authorized")
    row = manifest_row(source)

    with pytest.raises(ValueError, match="block_size must be positive"):
        with verified_raw_input_stream(source, row, block_size=0):
            pass

    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("platform does not expose O_NOFOLLOW")
    target = tmp_path / "target.root"
    link = tmp_path / "link.root"
    target.write_bytes(b"authorized")
    link.symlink_to(target)
    link_row = manifest_row(target)
    link_row["file"] = str(link)
    with pytest.raises(RawInputAuthorizationError, match="symlink"):
        with verified_raw_input_stream(link, link_row):
            pass


def test_manifest_ctime_mismatch_alone_still_authorizes(tmp_path):
    """No-alarm case: ctime is kernel-set and environment-dependent. A source
    whose metadata was legitimately touched after manifesting (backup/restore,
    ACL or ownership fixups -- new ctime, same inode, same bytes) must still
    authorize; content is separately sha256-bound in the same transaction."""
    source = tmp_path / "raw.root"
    payload = b"authorized-root-bytes"
    source.write_bytes(payload)
    row = manifest_row(source)
    row["source_ctime_ns"] = int(row["source_ctime_ns"]) + 1

    with verified_raw_input_stream(source, row, block_size=3) as stream:
        assert stream.read() == payload


def test_ctime_change_during_consumption_fails_closed(tmp_path):
    """Intra-transaction ctime is stable on one host and stays enforced: a
    metadata mutation on the held descriptor (chmod changes only ctime) must
    fail the transaction closed."""
    source = tmp_path / "raw.root"
    payload = b"authorized-open-inode"
    source.write_bytes(payload)
    row = manifest_row(source)

    with pytest.raises(
        RawInputAuthorizationError, match="consumer held authorized stream"
    ):
        with verified_raw_input_stream(source, row) as stream:
            # chmod bumps ctime, but inode timestamps can be coarse-grained
            # (same tick for the whole transaction): poll until it observably
            # moves so final != verified is guaranteed on any filesystem.
            c0 = os.stat(source).st_ctime_ns
            mode = 0o400
            deadline = time.monotonic() + 5.0
            while os.stat(source).st_ctime_ns == c0:
                if time.monotonic() > deadline:
                    pytest.fail("ctime did not change after chmod within 5s")
                # creation and the first chmod can land in the same coarse
                # timestamp tick: keep issuing fresh metadata ops until the
                # inode clock observably advances.
                os.chmod(source, mode)
                mode = 0o600 if mode == 0o400 else 0o400
                time.sleep(0.05)
            stream.seek(0)

"""Deterministic same-bytes read tests for S00 provenance atom #1149."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from ccb_mc_validation.s00_publication import (
    S00PublicationError,
    create_staging_directory,
    publish_generation,
    read_publication_pointer,
)
from ccb_mc_validation.s00_verified_read import verified_artifact_snapshot


LOGICAL_NAME = "selected_pulse_table"
RELATIVE_PATH = "data/processed/s00_selected_b_pulses.csv.gz"


def _publish(
    generation_root: Path,
    pointer_path: Path,
    *,
    generation_id: str,
    payload: bytes,
) -> Path:
    staging = create_staging_directory(generation_root, token=generation_id)
    artifact = staging / RELATIVE_PATH
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(payload)
    publish_generation(
        staging,
        generation_root,
        pointer_path,
        generation_id=generation_id,
        artifacts={LOGICAL_NAME: RELATIVE_PATH},
        model_identity={"model_id": generation_id},
    )
    return generation_root / generation_id / RELATIVE_PATH


def test_snapshot_yields_exact_authorised_bytes_and_cleans_up(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    payload = b"run,event,stave\n44,1,B2\n"
    source = _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=payload,
    )

    snapshot_path = None
    with verified_artifact_snapshot(
        pointer_path,
        generation_root,
        LOGICAL_NAME,
        scratch_dir=tmp_path,
    ) as snapshot:
        snapshot_path = snapshot.path
        assert snapshot.path.exists()
        assert snapshot.path.name.endswith(".csv.gz")
        assert snapshot.path.read_bytes() == payload
        assert snapshot.sha256 == hashlib.sha256(payload).hexdigest()
        assert snapshot.pointer.generation_id == "g1"
        source_stat = source.stat()
        assert snapshot.source_device == source_stat.st_dev
        assert snapshot.source_inode == source_stat.st_ino
        assert snapshot.source_size == len(payload)

    assert snapshot_path is not None
    assert not snapshot_path.exists()


def test_tamper_before_snapshot_fails_closed(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    source = _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=b"authorised",
    )
    source.write_bytes(b"tampered")

    with pytest.raises(S00PublicationError, match="content hash mismatch"):
        with verified_artifact_snapshot(
            pointer_path,
            generation_root,
            LOGICAL_NAME,
            scratch_dir=tmp_path,
        ):
            pass


def test_tamper_after_snapshot_cannot_change_consumed_bytes(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    authorised = b"authorised-by-pointer"
    source = _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=authorised,
    )

    with verified_artifact_snapshot(
        pointer_path,
        generation_root,
        LOGICAL_NAME,
        scratch_dir=tmp_path,
    ) as snapshot:
        source.write_bytes(b"mutated-after-verification")
        assert source.read_bytes() != authorised
        assert snapshot.path.read_bytes() == authorised
        assert hashlib.sha256(snapshot.path.read_bytes()).hexdigest() == snapshot.sha256


def test_hard_link_alias_mutation_after_snapshot_isolated(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    authorised = b"hard-link-authorised"
    source = _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=authorised,
    )
    alias = tmp_path / "external-hard-link.bin"
    os.link(source, alias)
    assert source.stat().st_nlink >= 2

    with verified_artifact_snapshot(
        pointer_path,
        generation_root,
        LOGICAL_NAME,
        scratch_dir=tmp_path,
    ) as snapshot:
        assert snapshot.source_nlink >= 2
        alias.write_bytes(b"mutated-through-hard-link")
        assert source.read_bytes() != authorised
        assert snapshot.path.read_bytes() == authorised


def test_hard_link_alias_mutation_before_snapshot_fails_closed(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    source = _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=b"authorised",
    )
    alias = tmp_path / "external-hard-link.bin"
    os.link(source, alias)
    alias.write_bytes(b"changed-before-copy")

    with pytest.raises(S00PublicationError, match="content hash mismatch"):
        with verified_artifact_snapshot(
            pointer_path,
            generation_root,
            LOGICAL_NAME,
            scratch_dir=tmp_path,
        ):
            pass


def test_pointer_swap_after_snapshot_keeps_one_complete_old_generation(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    old_payload = b"old-authority"
    new_payload = b"new-authority"
    _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=old_payload,
    )

    with verified_artifact_snapshot(
        pointer_path,
        generation_root,
        LOGICAL_NAME,
        scratch_dir=tmp_path,
    ) as snapshot:
        _publish(
            generation_root,
            pointer_path,
            generation_id="g2",
            payload=new_payload,
        )
        assert read_publication_pointer(pointer_path).generation_id == "g2"
        assert snapshot.pointer.generation_id == "g1"
        assert snapshot.path.read_bytes() == old_payload


def test_unknown_logical_name_fails_before_snapshot_creation(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=b"authorised",
    )

    before = set(tmp_path.glob(".s00-verified-*"))
    with pytest.raises(S00PublicationError, match="unknown logical artifact"):
        with verified_artifact_snapshot(
            pointer_path,
            generation_root,
            "not-present",
            scratch_dir=tmp_path,
        ):
            pass
    after = set(tmp_path.glob(".s00-verified-*"))
    assert after == before


@pytest.mark.parametrize("block_size", [0, -1, 1.5, True])
def test_invalid_block_size_fails_closed(tmp_path, block_size):
    with pytest.raises(S00PublicationError, match="positive integer"):
        with verified_artifact_snapshot(
            tmp_path / "CURRENT.json",
            tmp_path / "generations",
            LOGICAL_NAME,
            block_size=block_size,
        ):
            pass


def test_missing_scratch_directory_fails_closed(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    _publish(
        generation_root,
        pointer_path,
        generation_id="g1",
        payload=b"authorised",
    )

    with pytest.raises(S00PublicationError, match="scratch_dir"):
        with verified_artifact_snapshot(
            pointer_path,
            generation_root,
            LOGICAL_NAME,
            scratch_dir=tmp_path / "does-not-exist",
        ):
            pass

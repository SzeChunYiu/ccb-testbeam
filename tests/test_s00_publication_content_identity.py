from __future__ import annotations

import json
from pathlib import Path

import pytest

from ccb_mc_validation import s00_publication as pub


def _stage_regular(tmp_path: Path, token: str, value: bytes = b"stable") -> tuple[Path, Path, Path]:
    root = tmp_path / "generations"
    pointer = tmp_path / "CURRENT.json"
    staging = pub.create_staging_directory(root, token=token)
    (staging / "manifest.json").write_bytes(value)
    (staging / "selected.csv.gz").write_bytes(value + b"-selected")
    return root, pointer, staging


def _publish_regular(tmp_path: Path, token: str = "gen1") -> tuple[Path, Path, pub.S00PublicationPointer]:
    root, pointer, staging = _stage_regular(tmp_path, token)
    result = pub.publish_generation(
        staging,
        root,
        pointer,
        generation_id=token,
        artifacts={
            "manifest": "manifest.json",
            "selected_pulse_table": "selected.csv.gz",
        },
        model_identity={"selector_id": "v1_first_four_median"},
    )
    return root, pointer, result


def test_pointer_binds_sha256_for_every_authoritative_artifact(tmp_path: Path) -> None:
    root, pointer_path, pointer = _publish_regular(tmp_path)

    assert set(pointer.artifact_sha256) == set(pointer.artifacts)
    assert all(len(value) == 64 for value in pointer.artifact_sha256.values())
    payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert payload["schema"] == pub.POINTER_SCHEMA
    assert payload["artifact_sha256"] == pointer.artifact_sha256

    for logical_name in pointer.artifacts:
        assert pub.resolve_artifact(pointer_path, root, logical_name).is_file()


@pytest.mark.parametrize("logical_name", ["manifest", "selected_pulse_table"])
def test_post_publication_byte_mutation_fails_closed(
    tmp_path: Path,
    logical_name: str,
) -> None:
    root, pointer_path, pointer = _publish_regular(tmp_path)
    artifact = root / pointer.generation_id / pointer.artifacts[logical_name]
    artifact.write_bytes(artifact.read_bytes() + b"-tampered")

    with pytest.raises(pub.S00PublicationError, match="content hash mismatch"):
        pub.resolve_artifact(pointer_path, root, logical_name)


def test_external_symlink_artifact_is_rejected_before_authority_change(tmp_path: Path) -> None:
    root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    old_root, old_pointer, _ = _publish_regular(tmp_path, "old")
    assert old_root == root
    assert old_pointer == pointer_path
    old_pointer_bytes = pointer_path.read_bytes()

    outside = tmp_path / "outside.json"
    outside.write_text("outside\n", encoding="utf-8")
    staging = pub.create_staging_directory(root, token="new")
    (staging / "manifest.json").symlink_to(outside)

    with pytest.raises(pub.S00PublicationError, match="symlink components"):
        pub.publish_generation(
            staging,
            root,
            pointer_path,
            generation_id="new",
            artifacts={"manifest": "manifest.json"},
            model_identity={},
        )

    assert pointer_path.read_bytes() == old_pointer_bytes
    assert pub.read_publication_pointer(pointer_path).generation_id == "old"
    assert not (root / "new").exists()


def test_symlinked_parent_component_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    staging = pub.create_staging_directory(root, token="gen1")
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "manifest.json").write_text("outside\n", encoding="utf-8")
    (staging / "payload").symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(pub.S00PublicationError, match="symlink components"):
        pub.publish_generation(
            staging,
            root,
            pointer_path,
            generation_id="gen1",
            artifacts={"manifest": "payload/manifest.json"},
            model_identity={},
        )

    assert not pointer_path.exists()
    assert not (root / "gen1").exists()


def test_resolver_rejects_symlink_substitution_after_publication(tmp_path: Path) -> None:
    root, pointer_path, pointer = _publish_regular(tmp_path)
    artifact = root / pointer.generation_id / pointer.artifacts["manifest"]
    outside = tmp_path / "replacement.json"
    outside.write_text("stable\n", encoding="utf-8")
    artifact.unlink()
    artifact.symlink_to(outside)

    with pytest.raises(pub.S00PublicationError, match="symlink components"):
        pub.resolve_artifact(pointer_path, root, "manifest")


@pytest.mark.parametrize(
    "digest",
    ["", "abc", "A" * 64, "g" * 64, "0" * 63, "0" * 65, None],
)
def test_pointer_parser_rejects_invalid_sha256_values(
    tmp_path: Path,
    digest: object,
) -> None:
    pointer_path = tmp_path / "CURRENT.json"
    payload = {
        "schema": pub.POINTER_SCHEMA,
        "generation_id": "gen1",
        "artifacts": {"manifest": "manifest.json"},
        "artifact_sha256": {"manifest": digest},
        "model_identity": {},
    }
    pointer_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(pub.S00PublicationError, match="invalid SHA-256 digest"):
        pub.read_publication_pointer(pointer_path)


def test_pointer_parser_rejects_missing_digest_map(tmp_path: Path) -> None:
    pointer_path = tmp_path / "CURRENT.json"
    pointer_path.write_text(
        json.dumps(
            {
                "schema": pub.POINTER_SCHEMA,
                "generation_id": "gen1",
                "artifacts": {"manifest": "manifest.json"},
                "model_identity": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(pub.S00PublicationError, match="artifact_sha256 must be a mapping"):
        pub.read_publication_pointer(pointer_path)


def test_pointer_parser_rejects_digest_key_mismatch(tmp_path: Path) -> None:
    pointer_path = tmp_path / "CURRENT.json"
    pointer_path.write_text(
        json.dumps(
            {
                "schema": pub.POINTER_SCHEMA,
                "generation_id": "gen1",
                "artifacts": {"manifest": "manifest.json"},
                "artifact_sha256": {"other": "0" * 64},
                "model_identity": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(pub.S00PublicationError, match="keys must exactly match"):
        pub.read_publication_pointer(pointer_path)

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ccb_mc_validation import s00_publication as pub


def _stage(tmp_path: Path, token: str, *, value: str) -> tuple[Path, Path, Path]:
    root = tmp_path / "generations"
    pointer = tmp_path / "CURRENT.json"
    staging = pub.create_staging_directory(root, token=token)
    (staging / "manifest.json").write_text(
        json.dumps({"value": value}) + "\n", encoding="utf-8"
    )
    (staging / "s00_selected_b_pulses.csv.gz").write_bytes(value.encode("utf-8"))
    return root, pointer, staging


def _publish(tmp_path: Path, token: str, *, value: str) -> pub.S00PublicationPointer:
    root, pointer, staging = _stage(tmp_path, token, value=value)
    return pub.publish_generation(
        staging,
        root,
        pointer,
        generation_id=token,
        artifacts={
            "manifest": "manifest.json",
            "selected_pulse_table": "s00_selected_b_pulses.csv.gz",
        },
        model_identity={"value": value},
    )


def test_publish_generation_commits_one_pointer_to_immutable_generation(tmp_path: Path) -> None:
    result = _publish(tmp_path, "gen1", value="one")
    pointer = tmp_path / "CURRENT.json"
    root = tmp_path / "generations"

    assert result.generation_id == "gen1"
    assert (root / "gen1" / "manifest.json").is_file()
    assert pub.read_publication_pointer(pointer) == result
    selected = pub.resolve_artifact(pointer, root, "selected_pulse_table")
    assert selected.read_bytes() == b"one"


def test_second_publication_preserves_old_generation_and_moves_authority(tmp_path: Path) -> None:
    _publish(tmp_path, "gen1", value="one")
    old_manifest = (tmp_path / "generations" / "gen1" / "manifest.json").read_bytes()

    _publish(tmp_path, "gen2", value="two")

    root = tmp_path / "generations"
    pointer = tmp_path / "CURRENT.json"
    assert (root / "gen1" / "manifest.json").read_bytes() == old_manifest
    assert (root / "gen2" / "manifest.json").is_file()
    assert pub.read_publication_pointer(pointer).generation_id == "gen2"
    assert pub.resolve_artifact(pointer, root, "selected_pulse_table").read_bytes() == b"two"


def test_pointer_commit_failure_leaves_previous_authority_byte_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _publish(tmp_path, "gen1", value="one")
    pointer = tmp_path / "CURRENT.json"
    old_pointer = pointer.read_bytes()
    root, _, staging = _stage(tmp_path, "gen2", value="two")

    real_replace = os.replace
    calls = 0

    def fail_second_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected pointer-commit failure")
        real_replace(src, dst)

    monkeypatch.setattr(pub.os, "replace", fail_second_replace)
    with pytest.raises(OSError, match="injected pointer-commit failure"):
        pub.publish_generation(
            staging,
            root,
            pointer,
            generation_id="gen2",
            artifacts={
                "manifest": "manifest.json",
                "selected_pulse_table": "s00_selected_b_pulses.csv.gz",
            },
            model_identity={"value": "two"},
        )

    assert pointer.read_bytes() == old_pointer
    assert pub.read_publication_pointer(pointer).generation_id == "gen1"
    assert (root / "gen1").is_dir()
    assert (root / "gen2").is_dir()  # orphaned but explicitly non-authoritative


def test_missing_required_artifact_cannot_change_authority(tmp_path: Path) -> None:
    _publish(tmp_path, "gen1", value="one")
    pointer = tmp_path / "CURRENT.json"
    old_pointer = pointer.read_bytes()
    root = tmp_path / "generations"
    staging = pub.create_staging_directory(root, token="gen2")
    (staging / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(pub.S00PublicationError, match="required artifact"):
        pub.publish_generation(
            staging,
            root,
            pointer,
            generation_id="gen2",
            artifacts={
                "manifest": "manifest.json",
                "selected_pulse_table": "s00_selected_b_pulses.csv.gz",
            },
            model_identity={"value": "two"},
        )

    assert pointer.read_bytes() == old_pointer
    assert not (root / "gen2").exists()
    assert staging.is_dir()


def test_existing_generation_is_immutable_and_never_overwritten(tmp_path: Path) -> None:
    _publish(tmp_path, "gen1", value="one")
    root, pointer, staging = _stage(tmp_path, "retry", value="different")

    with pytest.raises(pub.S00PublicationError, match="immutable generation already exists"):
        pub.publish_generation(
            staging,
            root,
            pointer,
            generation_id="gen1",
            artifacts={"manifest": "manifest.json"},
            model_identity={"value": "different"},
        )

    assert (root / "gen1" / "s00_selected_b_pulses.csv.gz").read_bytes() == b"one"


@pytest.mark.parametrize(
    "generation_id",
    ["../escape", "/absolute", "", ".", "has space", "a/b"],
)
def test_generation_id_cannot_escape_generation_root(
    tmp_path: Path,
    generation_id: str,
) -> None:
    root = tmp_path / "generations"
    staging = pub.create_staging_directory(root, token="valid")
    (staging / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(pub.S00PublicationError, match="generation_id"):
        pub.publish_generation(
            staging,
            root,
            tmp_path / "CURRENT.json",
            generation_id=generation_id,
            artifacts={"manifest": "manifest.json"},
            model_identity={},
        )


@pytest.mark.parametrize(
    "artifact_path",
    ["../escape.csv", "/absolute.csv", "", "."],
)
def test_artifact_path_cannot_escape_generation(
    tmp_path: Path,
    artifact_path: str,
) -> None:
    root, pointer, staging = _stage(tmp_path, "gen1", value="one")
    with pytest.raises(pub.S00PublicationError, match="artifact path"):
        pub.publish_generation(
            staging,
            root,
            pointer,
            generation_id="gen1",
            artifacts={"selected": artifact_path},
            model_identity={},
        )


def test_staging_must_be_direct_child_of_generation_root(tmp_path: Path) -> None:
    root = tmp_path / "generations"
    root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    staging = elsewhere / "stage"
    staging.mkdir()
    (staging / "manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(pub.S00PublicationError, match="direct child"):
        pub.publish_generation(
            staging,
            root,
            tmp_path / "CURRENT.json",
            generation_id="gen1",
            artifacts={"manifest": "manifest.json"},
            model_identity={},
        )


def test_malformed_pointer_fails_closed(tmp_path: Path) -> None:
    pointer = tmp_path / "CURRENT.json"
    pointer.write_text('{"schema":"wrong"}\n', encoding="utf-8")
    with pytest.raises(pub.S00PublicationError, match="unsupported publication pointer schema"):
        pub.read_publication_pointer(pointer)


def test_resolver_fails_when_authoritative_artifact_is_missing(tmp_path: Path) -> None:
    _publish(tmp_path, "gen1", value="one")
    root = tmp_path / "generations"
    pointer = tmp_path / "CURRENT.json"
    (root / "gen1" / "manifest.json").unlink()

    with pytest.raises(pub.S00PublicationError, match="authoritative artifact missing"):
        pub.resolve_artifact(pointer, root, "manifest")

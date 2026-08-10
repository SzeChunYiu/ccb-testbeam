"""Negative control proving why a verified pathname is not a same-bytes read."""

from __future__ import annotations

import os
from pathlib import Path

from ccb_mc_validation.s00_publication import (
    create_staging_directory,
    publish_generation,
    resolve_artifact,
)


LOGICAL_NAME = "selected_pulse_table"
RELATIVE_PATH = "data/processed/s00_selected_b_pulses.csv.gz"


def test_resolved_path_can_be_mutated_after_verification(tmp_path):
    generation_root = tmp_path / "generations"
    pointer_path = tmp_path / "CURRENT.json"
    staging = create_staging_directory(generation_root, token="g1")
    staged_artifact = staging / RELATIVE_PATH
    staged_artifact.parent.mkdir(parents=True, exist_ok=True)
    staged_artifact.write_bytes(b"authorised")
    publish_generation(
        staging,
        generation_root,
        pointer_path,
        generation_id="g1",
        artifacts={LOGICAL_NAME: RELATIVE_PATH},
        model_identity={"model_id": "g1"},
    )

    verified_path = resolve_artifact(pointer_path, generation_root, LOGICAL_NAME)
    alias = tmp_path / "external-hard-link.bin"
    os.link(verified_path, alias)
    alias.write_bytes(b"mutated-after-resolve")

    # This is the hostile control: resolve_artifact() verified the source before
    # mutation, but a later pathname read sees different bytes. Authorising
    # consumers must therefore use verified_artifact_snapshot() instead.
    assert verified_path.read_bytes() == b"mutated-after-resolve"

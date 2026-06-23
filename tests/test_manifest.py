"""Manifest roundtrip tests."""

from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.manifest import (
    build_manifest_record,
    load_manifest,
    verify_manifest,
    write_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_manifest_roundtrip(tmp_path: Path) -> None:
    config_path = REPO_ROOT / "configs/mc_validation/base.yaml"
    out_dir = tmp_path / "mv1_run"
    out_dir.mkdir()
    (out_dir / "study_result.json").write_text("{}", encoding="utf-8")

    record = build_manifest_record(
        study_id="mv1",
        ticket="test-roundtrip",
        config_path=config_path,
        out_dir=out_dir,
        inputs={"config": config_path},
    )
    manifest_path = write_manifest(out_dir, record)

    payload = load_manifest(manifest_path)
    assert payload["study_id"] == "mv1"
    assert payload["ticket"] == "test-roundtrip"
    assert "manifest.json" not in payload["outputs"]
    assert verify_manifest(manifest_path, expected_study_id="mv1")

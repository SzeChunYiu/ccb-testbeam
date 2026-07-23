"""Manifest roundtrip tests."""

from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.manifest import (
    build_manifest_record,
    load_manifest,
    verify_manifest,
    write_manifest,
)
from ccb_mc_validation.exceptions import ManifestError

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
    out_names = [o["name"] for o in payload["outputs"]]
    assert "manifest.json" not in out_names
    assert all("sha256" in o and "size_bytes" in o for o in payload["outputs"])
    assert verify_manifest(manifest_path, expected_study_id="mv1")


def _make_manifest(tmp_path: Path):
    config_path = REPO_ROOT / "configs/mc_validation/base.yaml"
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    (out_dir / "result.json").write_text('{"a": 1}', encoding="utf-8")
    record = build_manifest_record(study_id="mv1", ticket="t", config_path=config_path, out_dir=out_dir)
    return out_dir, write_manifest(out_dir, record)


def test_output_records_carry_hash_and_size(tmp_path: Path) -> None:
    _out, mp = _make_manifest(tmp_path)
    payload = load_manifest(mp)
    rec = payload["outputs"][0]
    assert rec["name"] == "result.json"
    assert rec["size_bytes"] == len('{"a": 1}')
    assert len(rec["sha256"]) == 64
    assert verify_manifest(mp, expected_study_id="mv1")


def test_output_tamper_is_detected(tmp_path: Path) -> None:
    out, mp = _make_manifest(tmp_path)
    (out / "result.json").write_text('{"a": 999}', encoding="utf-8")  # alter after manifest build
    try:
        verify_manifest(mp)
        raise AssertionError("expected ManifestError for tampered output")
    except ManifestError as exc:
        assert "altered" in str(exc)


def test_missing_output_is_detected(tmp_path: Path) -> None:
    out, mp = _make_manifest(tmp_path)
    (out / "result.json").unlink()
    try:
        verify_manifest(mp)
        raise AssertionError("expected ManifestError for missing output")
    except ManifestError as exc:
        assert "missing" in str(exc)


def test_smoke_gate_aggregation_is_fail_closed() -> None:
    from ccb_mc_validation.execution.pipeline import PipelineOrchestrator
    agg = PipelineOrchestrator._aggregate_smoke_status
    assert agg({"MV1": {"status": "PASS"}, "MV2": {"status": "PASS"}}) == "PASS"
    assert agg({"MV1": {"status": "PASS"}, "MV2": {"status": "FAIL"}}) == "FAIL"
    assert agg({"MV1": {"status": "BLOCKED"}}) == "FAIL"
    assert agg({}) == "FAIL"  # no studies ran -> not PASS

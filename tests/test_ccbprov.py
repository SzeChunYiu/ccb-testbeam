"""Unit tests for the ccbprov provenance toolkit.

Run from the repo root::

    python -m pytest tests/test_ccbprov.py -q
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

# Ensure the repo root (parent of tests/) is importable so
# `import tools.ccbprov` works regardless of pytest's rootdir insertion.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.ccbprov import (  # noqa: E402
    ClosureRow,
    RunManifest,
    file_record,
    init_report_dir,
    sha256_file,
    validate_record,
    write_closure_matrix,
)

_SCHEMA_DIR = _REPO_ROOT / "schemas"
_RUN_MANIFEST_SCHEMA = str(_SCHEMA_DIR / "run_manifest.schema.json")

_FAKE_COMMIT = "a" * 40  # valid 40-hex
_FAKE_SHA = "b" * 64  # valid 64-hex


# --------------------------------------------------------------------------
# hashing
# --------------------------------------------------------------------------
def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    payload = b"CCB test-beam \x00\x01 deuteron enrichment"
    f = tmp_path / "blob.bin"
    f.write_bytes(payload)
    assert sha256_file(f) == hashlib.sha256(payload).hexdigest()


def test_file_record_shape(tmp_path: Path) -> None:
    payload = b"hello"
    f = tmp_path / "hello.txt"
    f.write_bytes(payload)
    rec = file_record(str(f))
    assert set(rec) == {"path", "sha256", "size_bytes"}
    assert rec["path"] == str(f)
    assert rec["sha256"] == hashlib.sha256(payload).hexdigest()
    assert rec["size_bytes"] == len(payload)


def test_sha256_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        sha256_file(tmp_path / "does-not-exist.bin")


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------
def _build_valid_manifest(tmp_path: Path) -> RunManifest:
    inp = tmp_path / "in.root"
    inp.write_bytes(b"raw")
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("seed: 1234\n")
    out = tmp_path / "out.parquet"
    out.write_bytes(b"result")

    m = RunManifest(
        task_id="TK-TEST",
        command=["python", "decode.py", "--run", "1"],
        git_commit=_FAKE_COMMIT,  # explicit -> no git dependency in the test
        seed_policy="default_rng(1234)",
    )
    m.start()
    m.add_input(inp)
    m.add_config(cfg)
    m.add_output(out)
    m.finish()
    return m


def test_manifest_to_dict_is_schema_valid(tmp_path: Path) -> None:
    m = _build_valid_manifest(tmp_path)
    d = m.to_dict()
    # sanity: hashes are 64-hex, commit is 40-hex
    assert len(d["git_commit"]) == 40
    assert all(len(rec["sha256"]) == 64 for rec in d["inputs"])
    errors = validate_record(d, _RUN_MANIFEST_SCHEMA)
    assert errors == [], f"expected valid manifest, got errors: {errors}"


def test_manifest_records_timestamps_and_env(tmp_path: Path) -> None:
    m = _build_valid_manifest(tmp_path)
    d = m.to_dict()
    # timezone-aware ISO-8601 UTC (offset present)
    assert d["started_utc"].endswith("+00:00")
    assert d["finished_utc"].endswith("+00:00")
    assert "python_version" in d["environment"]


def test_validate_rejects_bad_commit(tmp_path: Path) -> None:
    m = _build_valid_manifest(tmp_path)
    d = m.to_dict()
    d["git_commit"] = "not-a-real-commit-hash"  # fails ^[0-9a-f]{40}$
    errors = validate_record(d, _RUN_MANIFEST_SCHEMA)
    assert errors, "bad git_commit should produce errors"
    assert any("git_commit" in e for e in errors), errors


def test_validate_rejects_missing_required_key(tmp_path: Path) -> None:
    m = _build_valid_manifest(tmp_path)
    d = m.to_dict()
    del d["environment"]  # required key
    errors = validate_record(d, _RUN_MANIFEST_SCHEMA)
    assert errors, "missing required key should produce errors"
    assert any("environment" in e for e in errors), errors


# --------------------------------------------------------------------------
# closure matrix
# --------------------------------------------------------------------------
def test_write_closure_matrix_csv_and_json_roundtrip(tmp_path: Path) -> None:
    rows = [
        ClosureRow(
            task_id="TK-A",
            status="DONE",
            issue=None,
            dependencies=["TK-0", "TK-1"],
            evidence=["out/manifest.json"],
            acceptance=[
                {"criterion": "c1", "passed": True, "evidence": "fig1.png"},
                {"criterion": "c2", "passed": False, "evidence": None},
            ],
            notes="baseline",
        ),
        ClosureRow(task_id="TK-B", status="BLOCKED_COMPUTE"),
    ]
    csv_path = tmp_path / "closure_matrix.csv"
    json_path = tmp_path / "closure_matrix.json"
    write_closure_matrix(rows, csv_path, json_path)

    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == (
        "task_id,status,issue,dependencies,evidence,notes,n_acceptance,n_passed"
    )
    # dependencies joined with ';'
    body = csv_path.read_text(encoding="utf-8").splitlines()[1]
    assert "TK-0;TK-1" in body

    records = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(records) == 2
    a = next(r for r in records if r["task_id"] == "TK-A")
    assert a["status"] == "DONE"
    assert a["dependencies"] == ["TK-0", "TK-1"]
    assert len(a["acceptance"]) == 2
    assert a["acceptance"][0]["passed"] is True


def test_write_closure_matrix_invalid_status_raises(tmp_path: Path) -> None:
    rows = [ClosureRow(task_id="TK-X", status="NOT_A_STATUS")]
    with pytest.raises(ValueError):
        write_closure_matrix(
            rows, tmp_path / "c.csv", tmp_path / "c.json"
        )
    # nothing should have been written
    assert not (tmp_path / "c.csv").exists()
    assert not (tmp_path / "c.json").exists()


# --------------------------------------------------------------------------
# report dir
# --------------------------------------------------------------------------
def test_init_report_dir_creates_artifacts_and_no_overwrite(tmp_path: Path) -> None:
    stamp = "20260720T000000Z"
    d1 = init_report_dir(tmp_path, task_slug="proj", utc_stamp=stamp)
    assert d1.name == f"project_completion_{stamp}"
    for artifact in ("REPORT.md", "closure_matrix.csv", "manifest.json", "commands.log"):
        assert (d1 / artifact).is_file(), f"missing {artifact}"
    assert (d1 / "figures").is_dir()
    # empty per Definition of Done
    assert (d1 / "REPORT.md").read_text(encoding="utf-8") == ""

    # second call with the same stamp must not overwrite -> new dir
    d2 = init_report_dir(tmp_path, task_slug="proj", utc_stamp=stamp)
    assert d2 != d1
    assert d2.exists() and d1.exists()

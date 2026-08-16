from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit import audit_figure_registry_snapshot_provenance as audit


CURRENT_LIKE = '''
import shutil

def sha256_file(path):
    return "hash"

def _load_result(path, entry):
    return path.read_text(encoding="utf-8")

def _emit_quantitative(entry, result, out_dir):
    row = {"result_sha256": sha256_file(entry.result)}
    return row

def _emit_existing_artifact(entry, out_dir, subdirectory):
    source = Path(entry.source_figure)
    target = out_dir / entry.id
    shutil.copy2(source, target)
    row = {
        "source_sha256": sha256_file(source),
        "source_size_bytes": source.stat().st_size,
    }
    return row
'''

CORRECTED = '''
import hashlib

def _read_exact(path):
    raw = path.read_bytes()
    return raw, hashlib.sha256(raw).hexdigest(), len(raw)

def _load_result(path, entry):
    raw, digest, size = _read_exact(path)
    return raw.decode("utf-8"), digest, size

def _emit_quantitative(entry, result_snapshot, out_dir):
    return {"result_sha256": result_snapshot[1]}

def _emit_existing_artifact(entry, out_dir, subdirectory):
    raw, digest, size = _read_exact(entry.source_figure)
    target = out_dir / entry.id
    target.write_bytes(raw)
    return {"source_sha256": digest, "source_size_bytes": size}
'''


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_current_like_contract_is_flawed(tmp_path):
    result = audit.audit_source(_write(tmp_path / "builder.py", CURRENT_LIKE))
    assert result["status"] == "FLAWED"
    assert result["finding_count"] == 3
    codes = {item["code"] for item in result["findings"]}
    assert "RESULT_VALUE_AND_HASH_CAN_REFERENCE_DIFFERENT_BYTES" in codes
    assert "COPIED_SOURCE_AND_HASH_CAN_REFERENCE_DIFFERENT_BYTES" in codes
    assert "COPIED_SOURCE_AND_SIZE_CAN_REFERENCE_DIFFERENT_BYTES" in codes
    controls = result["behavioral_controls"]
    assert controls["result_path_replacement"]["numeric_value_used"] == 1.0
    assert not controls["result_path_replacement"]["later_hash_matches_used_bytes"]
    assert controls["result_path_replacement"]["corrected_hash_matches_used_bytes"]
    assert not controls["source_artifact_replacement"][
        "later_metadata_matches_copied_target"
    ]
    assert controls["source_artifact_replacement"][
        "corrected_metadata_matches_target"
    ]


def test_corrected_single_snapshot_fixture_validates(tmp_path):
    result = audit.audit_source(_write(tmp_path / "builder.py", CORRECTED))
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0


def test_invalid_utf8_is_controlled(tmp_path):
    source = tmp_path / "builder.py"
    source.write_bytes(b"\xff\xfe")
    with pytest.raises(audit.AuditInputError, match="strict UTF-8"):
        audit.audit_source(source)


def test_cli_rejects_destructive_alias(tmp_path, capsys):
    source = _write(tmp_path / "builder.py", CURRENT_LIKE)
    assert audit.main([str(source), "--output", str(source)]) == 2
    assert "aliases source" in capsys.readouterr().err


def test_atomic_publication_and_failure_preserves_previous(tmp_path, monkeypatch):
    source = _write(tmp_path / "builder.py", CORRECTED)
    output = tmp_path / "result.json"
    assert audit.main([str(source), "--output", str(output)]) == 0
    first = output.read_bytes()
    payload = json.loads(first)
    assert payload["status"] == "VALIDATED"

    def fail_replace(_source, _target):
        raise OSError("injected replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    assert audit.main([str(source), "--output", str(output)]) == 2
    assert output.read_bytes() == first
    assert not list(tmp_path.glob(".result.json.*.tmp"))

"""PROV-003 regression: jsonschema is mandatory; no permissive fallback; thread-safe."""
from __future__ import annotations
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ccbprov import validate as vmod  # noqa: E402
from tools.ccbprov import validate_record  # noqa: E402

_SCHEMA_DIR = REPO_ROOT / "schemas"
_RUN_MANIFEST_SCHEMA = str(_SCHEMA_DIR / "run_manifest.schema.json")

_FAKE_COMMIT = "a" * 40
_FAKE_SHA = "b" * 64


def _valid_manifest_dict() -> dict:
    return {
        "task_id": "TK-PROV",
        "command": ["python", "x.py"],
        "git_commit": _FAKE_COMMIT,
        "seed_policy": "default_rng(1)",
        "started_utc": "2026-01-01T00:00:00+00:00",
        "finished_utc": "2026-01-01T00:00:01+00:00",
        "environment": {"python_version": "3.11.5"},
        "inputs": [{"path": "/tmp/in.root", "sha256": _FAKE_SHA, "size_bytes": 1}],
        "outputs": [{"path": "/tmp/out.root", "sha256": _FAKE_SHA, "size_bytes": 1}],
        "configs": [],
        "status": "OK",
    }


def test_validate_record_raises_without_jsonschema(monkeypatch):
    """Fail-closed: an absent jsonschema import is a hard error, not a silent pass."""
    monkeypatch.setattr(vmod, "HAVE_JSONSCHEMA", False)
    with pytest.raises(RuntimeError, match="jsonschema is required"):
        validate_record(_valid_manifest_dict(), _RUN_MANIFEST_SCHEMA)


def test_invalid_record_is_rejected_not_silently_passed():
    """A genuinely invalid record must produce errors (never an empty pass)."""
    d = _valid_manifest_dict()
    d["git_commit"] = "not-a-real-commit-hash"  # violates ^[0-9a-f]{40}$
    errors = validate_record(d, _RUN_MANIFEST_SCHEMA)
    assert errors, "invalid record must NOT silently pass"
    assert any("git_commit" in e for e in errors)


def test_valid_record_passes():
    errors = validate_record(_valid_manifest_dict(), _RUN_MANIFEST_SCHEMA)
    assert errors == [], f"expected valid record, got: {errors}"


def test_concurrent_validation_is_safe():
    """No module-global mutable root schema: many threads must not clobber $defs."""
    good = _valid_manifest_dict()
    bad = _valid_manifest_dict()
    bad["git_commit"] = "zzz"  # invalid

    good_ok: list[bool] = []
    bad_rejected: list[bool] = []
    lock = threading.Lock()

    def worker():
        lok_good, lok_bad = [], []
        for _ in range(200):
            # Alternate records so the validator sees different payloads; with a
            # shared global root schema this would race and misreport.
            lok_good.append(len(validate_record(good, _RUN_MANIFEST_SCHEMA)) == 0)
            lok_bad.append(len(validate_record(bad, _RUN_MANIFEST_SCHEMA)) > 0)
        with lock:
            good_ok.extend(lok_good)
            bad_rejected.extend(lok_bad)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every good record validates AND every bad one is rejected — no races.
    assert all(good_ok), "a valid record was misrejected (race)"
    assert all(bad_rejected), "an invalid record was misaccepted (race)"

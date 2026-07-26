from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

AUDIT_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/audit/audit_deltae_table_output_contract.py"
)
SPEC = importlib.util.spec_from_file_location("deltae_output_audit", AUDIT_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_exact_proposed_source_validates():
    source = Path(__file__).resolve().parents[1] / "scripts/single_stave/deltaE_E.py"
    result = AUDIT.audit_source(source)
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0
    assert result["former_behavior_control"]["demonstrates_broad_fallback"] is True


def test_current_like_source_fails_closed(tmp_path):
    source = tmp_path / "front.py"
    source.write_text(
        "from pathlib import Path\n"
        "def analyze(*args): return {'result': {}}\n"
        "def write_manifest(*args): return None\n",
        encoding="utf-8",
    )
    result = AUDIT.audit_source(source)
    codes = {item["code"] for item in result["findings"]}
    assert result["status"] == "FLAWED"
    assert "MISSING_STRICT_WRITER" in codes
    assert "CORE_WRITER_NOT_OVERRIDDEN" in codes
    assert "MISSING_POLICY" in codes


def test_broad_writer_fixture_is_rejected(tmp_path):
    source = tmp_path / "front.py"
    source.write_text(
        f"POLICY={AUDIT.POLICY!r}\n"
        f"PUBLICATION={AUDIT.PUBLICATION!r}\n"
        f"FALLBACK={AUDIT.FALLBACK!r}\n"
        "def _event_table_output_contract(): return {'policy': POLICY}\n"
        "def _atomic_table_write(*args):\n"
        "    import os\n"
        "    os.fsync(1); os.replace('a','b')\n"
        "    temporary.unlink(missing_ok=True)\n"
        "def _write_table(df, base):\n"
        "    try: df.to_parquet(base)\n"
        "    except Exception: df.to_csv(base)\n"
        "def analyze(*args):\n"
        "    event_table_output_contract = _event_table_output_contract()\n"
        "def write_manifest(*args):\n"
        "    event_table_output_contract = _event_table_output_contract()\n"
        "_core._write_table = _write_table\n",
        encoding="utf-8",
    )
    result = AUDIT.audit_source(source)
    codes = {item["code"] for item in result["findings"]}
    assert "BROAD_FALLBACK_REMAINS" in codes
    assert "BROAD_OR_UNSCOPED_FALLBACK" in codes


def test_invalid_utf8_is_controlled(tmp_path):
    source = tmp_path / "bad.py"
    source.write_bytes(b"x=1\n\xff")
    with pytest.raises(AUDIT.AuditInputError):
        AUDIT.audit_source(source)


def test_cli_rejects_alias(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("x=1\n", encoding="utf-8")
    assert AUDIT.main([str(source), "--output", str(source)]) == 2


def test_atomic_json_publication(tmp_path):
    source = tmp_path / "front.py"
    source.write_text("x=1\n", encoding="utf-8")
    output = tmp_path / "audit.json"
    status = AUDIT.main([str(source), "--output", str(output)])
    assert status == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert not list(tmp_path.glob(".audit.json.*.tmp"))

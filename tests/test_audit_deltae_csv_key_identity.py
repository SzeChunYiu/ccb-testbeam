from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "audit" / "audit_deltae_csv_key_identity.py"
SPEC = importlib.util.spec_from_file_location("audit_deltae_csv_key_identity", MODULE_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

CURRENT_LIKE = '''
from pathlib import Path
import pandas as pd
KEY_COLS = ("source_file_id", "run_id", "event_id")
def read_table(path: Path):
    if not path.exists():
        raise SystemExit("missing")
    return pd.read_csv(path)
'''

CORRECTED = '''
from pathlib import Path
import io
import pandas as pd
POLICY = "DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT"
KEY_COLS = ("source_file_id", "run_id", "event_id")
CSV_KEY_DTYPES = {key: "string" for key in KEY_COLS}
def read_table(path: Path):
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    return pd.read_csv(io.StringIO(text), dtype=CSV_KEY_DTYPES)
'''


def write_source(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "source.py"
    path.write_text(text, encoding="utf-8")
    return path


def test_current_like_reader_fails_with_demonstrated_false_match(tmp_path: Path):
    result = AUDIT.audit_source(write_source(tmp_path, CURRENT_LIKE))
    assert result["status"] == "FLAWED"
    codes = {finding["code"] for finding in result["findings"]}
    assert "CSV_KEY_DTYPE_MISSING" in codes
    assert "DISTINCT_COMPOSITE_KEYS_COLLAPSE" in codes
    assert "FALSE_CROSS_FILE_MATCH" in codes
    assert result["controls"]["default_distinct_composite_keys"] == 1
    assert result["controls"]["lossless_distinct_composite_keys"] == 2
    assert result["controls"]["default_false_cross_file_matches"] == 1
    assert result["controls"]["lossless_cross_file_matches"] == 0


def test_corrected_reader_contract_validates(tmp_path: Path):
    result = AUDIT.audit_source(write_source(tmp_path, CORRECTED))
    assert result["status"] == "VALIDATED"
    assert result["findings"] == []


def test_dtype_without_single_read_still_fails(tmp_path: Path):
    source = CURRENT_LIKE.replace(
        "return pd.read_csv(path)",
        'return pd.read_csv(path, dtype={key: "string" for key in KEY_COLS})',
    ).replace(
        'KEY_COLS = ("source_file_id", "run_id", "event_id")',
        'POLICY = "DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT"\n'
        'KEY_COLS = ("source_file_id", "run_id", "event_id")',
    )
    result = AUDIT.audit_source(write_source(tmp_path, source))
    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "FLAWED"
    assert codes == {"CSV_NOT_SINGLE_READ_STRICT_UTF8"}


def test_invalid_utf8_is_controlled(tmp_path: Path):
    source = tmp_path / "source.py"
    source.write_bytes(b"def read_table(path):\n    return 1\n\xff")
    with pytest.raises(AUDIT.AuditInputError, match="invalid UTF-8"):
        AUDIT.audit_source(source)


def test_atomic_json_publication_and_alias_rejection(tmp_path: Path):
    source = write_source(tmp_path, CURRENT_LIKE)
    output = tmp_path / "result.json"
    payload = AUDIT.audit_source(source)
    AUDIT.atomic_write_json(output, payload, [source])
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "FLAWED"
    with pytest.raises(AUDIT.AuditInputError, match="aliases"):
        AUDIT.atomic_write_json(source, payload, [source])


def test_missing_read_table_is_controlled(tmp_path: Path):
    source = write_source(tmp_path, "x = 1\n")
    with pytest.raises(AUDIT.AuditInputError, match="read_table"):
        AUDIT.audit_source(source)

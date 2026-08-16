from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "tools" / "audit" / "audit_deltae_signal_value_contract.py"
SOURCE = ROOT / "scripts" / "single_stave" / "deltaE_E.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(AUDITOR), *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_exact_source_is_validated(tmp_path):
    output = tmp_path / "audit.json"
    proc = _run(SOURCE, "--output", output)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "VALIDATED"
    assert payload["finding_count"] == 0
    assert payload["synthetic_controls"]["former_malformed_cell_became_zero"] is True
    assert payload["synthetic_controls"]["former_infinity_remained_infinite"] is True


def test_missing_finite_gate_fails_closed(tmp_path):
    mutated = tmp_path / "deltaE_E.py"
    text = SOURCE.read_text(encoding="utf-8")
    mutated.write_text(
        text.replace(
            "invalid = ~np.isfinite(values)",
            "invalid = np.zeros(len(values), dtype=bool)",
        ),
        encoding="utf-8",
    )
    proc = _run(mutated)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert any(
        item["code"] == "MISSING_CONTRACT_TOKEN"
        for item in payload["findings"]
    )


def test_invalid_utf8_is_controlled_input_error(tmp_path):
    source = tmp_path / "bad.py"
    source.write_bytes(b"ok\n\xff\n")
    proc = _run(source)
    assert proc.returncode == 2
    assert "not strict UTF-8" in proc.stdout


def test_output_alias_is_rejected():
    proc = _run(SOURCE, "--output", SOURCE)
    assert proc.returncode == 2
    assert "must not alias" in proc.stdout


def test_json_publication_replaces_previous_file(tmp_path):
    output = tmp_path / "audit.json"
    output.write_text('{"stale": true}\n', encoding="utf-8")
    proc = _run(SOURCE, "--output", output)
    assert proc.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "stale" not in payload
    assert payload["status"] == "VALIDATED"
    assert not list(tmp_path.glob(".audit.json.*.tmp"))

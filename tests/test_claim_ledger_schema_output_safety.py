from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools/audit/validate_claim_ledger_schema.py"
SPEC = importlib.util.spec_from_file_location("validate_claim_ledger_schema", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_valid_ledger(path: Path) -> None:
    row = [""] * len(MODULE.EXPECTED_FIELDS)
    row[0] = "CL-TEST"
    row[1] = "Governance"
    row[2] = "schema"
    row[3] = "Synthetic output-safety control"
    row[27] = "software_validation"
    row[28] = "VALIDATED"
    row[29] = "NO"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(MODULE.EXPECTED_FIELDS)
        writer.writerow(row)


def test_json_output_cannot_alias_claim_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    _write_valid_ledger(ledger)
    before = ledger.read_bytes()

    status = MODULE.main([str(ledger), "--output", str(ledger)])

    assert status == 2
    assert ledger.read_bytes() == before


def test_svg_output_cannot_alias_claim_ledger_via_symlink(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    alias = tmp_path / "alias.svg"
    _write_valid_ledger(ledger)
    alias.symlink_to(ledger)
    before = ledger.read_bytes()

    status = MODULE.main([str(ledger), "--svg", str(alias)])

    assert status == 2
    assert ledger.read_bytes() == before


def test_json_and_svg_outputs_must_be_distinct(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "validation.out"
    _write_valid_ledger(ledger)

    status = MODULE.main([
        str(ledger),
        "--output",
        str(output),
        "--svg",
        str(output),
    ])

    assert status == 2
    assert not output.exists()


def test_atomic_write_preserves_previous_output_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "validation.json"
    _write_valid_ledger(ledger)
    output.write_text("previous\n", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(MODULE.os, "replace", fail_replace)
    status = MODULE.main([str(ledger), "--output", str(output)])

    assert status == 2
    assert output.read_text(encoding="utf-8") == "previous\n"
    assert list(tmp_path.glob(".validation.json.*.tmp")) == []


def test_atomic_writer_returns_content_provenance(tmp_path: Path) -> None:
    target = tmp_path / "artifact.txt"

    provenance = MODULE._atomic_write_text(target, "abc\n")

    assert target.read_text(encoding="utf-8") == "abc\n"
    assert provenance["bytes"] == 4
    assert len(provenance["sha256"]) == 64
    assert provenance["publication_method"] == (
        "SAME_DIRECTORY_TEMP_FSYNC_OS_REPLACE"
    )

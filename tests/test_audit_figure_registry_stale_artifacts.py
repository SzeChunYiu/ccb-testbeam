from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.audit import audit_figure_registry_stale_artifacts as audit


CURRENT_SOURCE = '''
def _process_entry(entry, out_dir, paper_only, allow_preliminary):
    record = {"disposition": None}
    disposition = entry.disposition
    if disposition == "BLOCKED":
        record["disposition"] = "BLOCKED"
        return record
    if disposition == "QUARANTINED":
        record["disposition"] = "QUARANTINED"
        return record
    return record


def build(entries, output):
    failures = []
    report = {"entries": []}
    for entry in entries:
        try:
            record = _process_entry(entry, output, True, False)
        except FigureRegistryError as exc:
            record = {"disposition": "FAIL", "reason": str(exc)}
            failures.append(str(exc))
        report["entries"].append(record)
    return report
'''


CORRECTED_SOURCE = '''
def _remove_managed_entry_outputs(entry, out_dir):
    return None


def _reconcile_registry_outputs(entries, out_dir):
    return None


def _process_entry(entry, out_dir, paper_only, allow_preliminary):
    _remove_managed_entry_outputs(entry, out_dir)
    record = {"disposition": None}
    disposition = entry.disposition
    if disposition == "BLOCKED":
        record["disposition"] = "BLOCKED"
        return record
    if disposition == "QUARANTINED":
        record["disposition"] = "QUARANTINED"
        return record
    return record


def build(entries, output):
    _reconcile_registry_outputs(entries, output)
    failures = []
    report = {"entries": []}
    for entry in entries:
        try:
            record = _process_entry(entry, output, True, False)
        except FigureRegistryError as exc:
            _remove_managed_entry_outputs(entry, output)
            record = {"disposition": "FAIL", "reason": str(exc)}
            failures.append(str(exc))
        report["entries"].append(record)
    return report
'''


def _snapshot(tmp_path: Path, text: str) -> audit.SourceSnapshot:
    source = tmp_path / "builder.py"
    source.write_text(text, encoding="utf-8")
    return audit._read_source(source)


def test_current_contract_is_flawed(tmp_path: Path) -> None:
    payload = audit.audit_source(_snapshot(tmp_path, CURRENT_SOURCE))
    assert payload["status"] == "FLAWED"
    codes = {finding["code"] for finding in payload["findings"]}
    assert codes == {
        "NO_ENTRY_OUTPUT_CLEANUP",
        "NONPASS_DISPOSITION_CAN_RETAIN_STALE_ARTIFACTS",
        "FAILED_ENTRY_CAN_RETAIN_STALE_ARTIFACTS",
        "REMOVED_ENTRY_CAN_RETAIN_STALE_ARTIFACTS",
    }
    controls = payload["controls"]["current_no_cleanup_model"]
    assert all(item["stale_count"] == 2 for item in controls.values())


def test_corrected_contract_is_validated(tmp_path: Path) -> None:
    payload = audit.audit_source(_snapshot(tmp_path, CORRECTED_SOURCE))
    assert payload["status"] == "VALIDATED"
    assert payload["findings"] == []
    controls = payload["controls"]["corrected_cleanup_model"]
    assert all(item["stale_count"] == 0 for item in controls.values())


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    source = tmp_path / "builder.py"
    source.write_bytes(b"\xff\xfe")
    with pytest.raises(audit.AuditInputError, match="strict UTF-8"):
        audit._read_source(source)


def test_source_output_alias_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "builder.py"
    source.write_text(CURRENT_SOURCE, encoding="utf-8")
    status = audit.main(
        ["--builder-source", str(source), "--output-json", str(source)]
    )
    assert status == 2
    assert "aliases builder source" in capsys.readouterr().err


def test_atomic_publication_preserves_previous_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "audit.json"
    output.write_text('{"previous": true}\n', encoding="utf-8")
    previous = output.read_bytes()

    def fail_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(audit.os, "replace", fail_replace)
    with pytest.raises(audit.AuditInputError, match="could not publish"):
        audit._atomic_write_json(output, {"new": True})
    assert output.read_bytes() == previous
    assert list(tmp_path.glob(".audit.json.*.tmp")) == []


def test_cli_writes_machine_readable_flawed_result(tmp_path: Path) -> None:
    source = tmp_path / "builder.py"
    output = tmp_path / "audit.json"
    source.write_text(CURRENT_SOURCE, encoding="utf-8")
    status = audit.main(
        ["--builder-source", str(source), "--output-json", str(output)]
    )
    assert status == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["policy"] == audit.POLICY
    assert payload["status"] == "FLAWED"

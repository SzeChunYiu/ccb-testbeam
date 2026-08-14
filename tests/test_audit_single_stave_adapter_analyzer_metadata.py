from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit"
    / "audit_single_stave_adapter_analyzer_metadata.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("adapter_metadata_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _analyzer() -> str:
    return '''
VERSION = "2.1.0"
POLICY = "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL_AND_DECLARE_EXPLICIT_ENERGY_TARGET"
OPTICAL_TOTAL = "n_optical_generated_total"
def generated_optical_denominator(df):
    contract = "CURRENT_COMPONENT_SUM"
    if contract == "CURRENT_COMPONENT_SUM":
        return OPTICAL_TOTAL, contract
    return "n_scint_generated", "LEGACY_SCINTILLATION_ONLY"
def collection_efficiency_frame(df):
    denominator, contract = generated_optical_denominator(df)
    selected = df.copy()
    selected["collection_efficiency"] = selected["n_end_selected"] / selected[denominator]
    return selected
'''


def _contract() -> str:
    return (
        "Analyzer version 2.1.0 preserves all components and uses the exact "
        "total-optical count for collection efficiency."
    )


def _corrected_adapter() -> str:
    return '''
def main():
    payload = {
        "analysis_compatibility": "SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE",
        "downstream_analyzer_contract": {
            "version": "2.1.0",
            "policy": "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL_AND_DECLARE_EXPLICIT_ENERGY_TARGET",
            "optical_generation_contract": "CURRENT_COMPONENT_SUM",
            "collection_efficiency_denominator": "n_optical_generated_total",
            "acceptance": "SOFTWARE_CONTRACT_VALIDATED_REAL_ROOT_PENDING",
        },
    }
    return payload
'''


def _stale_adapter() -> str:
    return '''
def main():
    payload = {
        "analysis_compatibility": "SCHEMA_ADAPTER_ONLY",
        "downstream_blocker": (
            "analyze_single_stave.py still validates arrivals against "
            "n_scint_generated alone; it must use n_optical_generated_total "
            "before direct current-ROOT analysis is scientifically accepted"
        ),
    }
    return payload
'''


def test_corrected_contract_validates():
    mod = _load()
    result = mod.audit_sources(_corrected_adapter(), _analyzer(), _contract())
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0


def test_stale_current_like_metadata_fails_closed():
    mod = _load()
    result = mod.audit_sources(_stale_adapter(), _analyzer(), _contract())
    assert result["status"] == "FLAWED"
    codes = [finding["code"] for finding in result["findings"]]
    assert "ADAPTER_COMPATIBILITY_STALE" in codes
    assert "STALE_ANALYZER_BLOCKER_PUBLISHED" in codes
    assert codes.count("ADAPTER_METADATA_TOKEN_MISSING") >= 3


def test_analyzer_without_total_denominator_is_rejected():
    mod = _load()
    mutated = _analyzer().replace(
        "return OPTICAL_TOTAL, contract", 'return "n_scint_generated", contract'
    )
    result = mod.audit_sources(_corrected_adapter(), mutated, _contract())
    assert result["status"] == "FLAWED"
    assert any(
        finding["code"] == "ANALYZER_TOTAL_DENOMINATOR_NOT_PROVEN"
        for finding in result["findings"]
    )


def test_contract_must_bind_version_and_total_semantics():
    mod = _load()
    result = mod.audit_sources(_corrected_adapter(), _analyzer(), "schema mapping only")
    codes = {finding["code"] for finding in result["findings"]}
    assert "CONTRACT_ANALYZER_VERSION_MISSING" in codes
    assert "CONTRACT_TOTAL_DENOMINATOR_MISSING" in codes


def test_wrapped_contract_prose_is_normalized():
    mod = _load()
    wrapped = (
        "Analyzer version\n2.0.0 preserves all components and uses the\n"
        "exact total-optical count for collection efficiency."
    )
    result = mod.audit_sources(_corrected_adapter(), _analyzer(), wrapped)
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0


def test_cli_writes_atomic_json_and_status_one_for_stale_fixture(tmp_path: Path):
    adapter = tmp_path / "adapter.py"
    analyzer = tmp_path / "analyzer.py"
    contract = tmp_path / "contract.md"
    output = tmp_path / "audit.json"
    adapter.write_text(_stale_adapter(), encoding="utf-8")
    analyzer.write_text(_analyzer(), encoding="utf-8")
    contract.write_text(_contract(), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--adapter",
            str(adapter),
            "--analyzer",
            str(analyzer),
            "--contract",
            str(contract),
            "--output-json",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert payload["inputs"]["adapter"]["sha256"]
    assert not list(tmp_path.glob(".audit.json.*"))


def test_invalid_utf8_and_output_alias_fail_closed(tmp_path: Path):
    adapter = tmp_path / "adapter.py"
    analyzer = tmp_path / "analyzer.py"
    contract = tmp_path / "contract.md"
    adapter.write_bytes(b"def main():\n\xff")
    analyzer.write_text(_analyzer(), encoding="utf-8")
    contract.write_text(_contract(), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--adapter",
            str(adapter),
            "--analyzer",
            str(analyzer),
            "--contract",
            str(contract),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "invalid UTF-8" in proc.stdout

    adapter.write_text(_corrected_adapter(), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--adapter",
            str(adapter),
            "--analyzer",
            str(analyzer),
            "--contract",
            str(contract),
            "--output-json",
            str(adapter),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "must not alias" in proc.stderr


def test_current_repository_sources_validate():
    root = Path(__file__).resolve().parents[1]
    adapter = root / "scripts" / "single_stave" / "adapt_geant4_events.py"
    analyzer = root / "scripts" / "single_stave" / "analyze_single_stave.py"
    contract = root / "scripts" / "single_stave" / "EVENT_CONTRACT.md"
    if not all(path.exists() for path in (adapter, analyzer, contract)):
        pytest.skip("full repository sources unavailable in isolated fixture")
    mod = _load()
    result = mod.audit_sources(
        adapter.read_text(encoding="utf-8"),
        analyzer.read_text(encoding="utf-8"),
        contract.read_text(encoding="utf-8"),
    )
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0

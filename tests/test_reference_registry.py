"""Reference registry tests."""
from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.reporting.reference_registry import generate_reference_registry


def test_generate_reference_registry_writes_blocked_bibliography(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()

    registry = generate_reference_registry(run)

    assert registry["status"] == "PASS"
    assert registry["scope"] == "reference-registry"
    assert registry["final_bibliography_status"] == "BLOCKED"
    ids = {record["id"] for record in registry["records"]}
    assert "REF-GEANT4-2003" in ids
    assert "REF-PDG-RPP-2024" in ids
    assert "REF-FINAL-BIBLIOGRAPHY-AUDIT" in ids
    assert registry["blocked_count"] == 1
    assert registry["blocked_count"] >= 1
    out = run / "reports" / "mc_validation" / "references"
    assert (out / "REFERENCE_REGISTRY.json").is_file()
    text = (out / "REFERENCE_REGISTRY.md").read_text(encoding="utf-8")
    assert "REF-RUNBOOK" in text
    assert "Do not invent references" in text

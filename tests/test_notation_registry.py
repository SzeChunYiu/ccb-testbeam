"""Notation registry tests."""
from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.reporting.notation_registry import generate_notation_registry


def test_generate_notation_registry_writes_equation_records(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()

    registry = generate_notation_registry(run)

    assert registry["status"] == "PASS"
    assert registry["scope"] == "notation-registry"
    assert registry["record_count"] >= 5
    out = run / "reports" / "mc_validation" / "notation"
    assert (out / "NOTATION_REGISTRY.json").is_file()
    text = (out / "NOTATION_REGISTRY.md").read_text(encoding="utf-8")
    assert "EQ-PID-EFF" in text
    assert "R_68" in text

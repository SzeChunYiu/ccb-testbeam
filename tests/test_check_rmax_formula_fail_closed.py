from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_rmax_formula.py"


def _module():
    spec = importlib.util.spec_from_file_location("check_rmax_formula_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_returns_failure_when_governance_is_flawed(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "evaluate",
        lambda root: {
            "governance_status": "FAIL",
            "scientific_acceptance": "BLOCKED",
            "issues": [{"code": "SYNTHETIC_COUNTEREXAMPLE"}],
        },
    )
    assert module.main([]) == 1


def test_main_returns_zero_only_for_consistent_blocked_governance(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "evaluate",
        lambda root: {
            "governance_status": "PASS",
            "scientific_acceptance": "BLOCKED",
            "issues": [],
        },
    )
    assert module.main([]) == 0


def test_no_accepted_rmax_is_hardcoded() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "accepted_rmax_mhz\": None" in text
    assert "REFERENCE_RATE_MHZ" not in text

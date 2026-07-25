from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "WIKI.md"
LEDGER = ROOT / "docs/claim_ledger.csv"


def _load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TAU = _load("wiki_tau_eff", "tools/audit/validate_wiki_tau_eff_public_binding.py")
FRONT = _load("wiki_front_door", "tools/audit/validate_wiki_claim_front_door.py")
CANONICAL = _load("wiki_canonical", "tools/audit/validate_wiki_canonical_results.py")


def test_current_wiki_passes_all_claim_gates() -> None:
    for module in (TAU, FRONT, CANONICAL):
        result = module.audit(WIKI, LEDGER)
        assert result["status"] == "VALIDATED", result["issues"]
        assert result["issues"] == []


def test_stale_tau_eff_row_fails_closed(tmp_path: Path) -> None:
    exact = (
        "| τeff (effective live-time) | 124.79018394263471 ns; "
        "run-bootstrap 95% CI [123.33094981246663, 126.35875117626817] ns "
        "| — | — | data_measurement | **DONE_DATA_ONLY** |"
    )
    stale = (
        "| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 | "
        "data + MC self-consistent | **VALIDATED** |"
    )
    text = WIKI.read_text(encoding="utf-8")
    assert text.count(exact) == 1
    mutated = tmp_path / "WIKI.md"
    mutated.write_text(text.replace(exact, stale), encoding="utf-8")

    result = TAU.audit(mutated, LEDGER)
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "FLAWED"
    assert "CANONICAL_ROW_UNSUPPORTED_COMPONENTS" in codes
    assert "CANONICAL_ROW_TRUTH_TYPE_MISMATCH" in codes
    assert "CANONICAL_ROW_STATUS_MISMATCH" in codes

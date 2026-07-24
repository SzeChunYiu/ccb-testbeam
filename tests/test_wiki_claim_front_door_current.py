from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "tools/audit/validate_wiki_claim_front_door.py"
SPEC = importlib.util.spec_from_file_location("validate_wiki_claim_front_door", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_current_wiki_matches_exact_width_claims() -> None:
    result = MODULE.audit(ROOT / "WIKI.md", ROOT / "docs/claim_ledger.csv")

    assert result["status"] == "VALIDATED"
    assert result["issues"] == []
    assert result["n_issues"] == 0
    assert set(result["required_claim_widths"].values()) == {43}
    assert result["policy"] == "WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS"


def test_stale_rmax_value_is_rejected(tmp_path: Path) -> None:
    stale = (ROOT / "WIKI.md").read_text(encoding="utf-8").replace(
        "| Rmax (pile-up tolerance) | Withheld pending S-STAT-003 | — | — | "
        "derived model conflicted | **BLOCKED** |",
        "| Rmax (pile-up tolerance) | 3.044–3.05 MHz | 0.05 | 0.10 | "
        "data + MC self-consistent | **VALIDATED** |",
        1,
    )
    wiki = tmp_path / "WIKI.md"
    wiki.write_text(stale, encoding="utf-8")

    result = MODULE.audit(wiki, ROOT / "docs/claim_ledger.csv")
    codes = [issue["code"] for issue in result["issues"]]

    assert result["status"] == "FLAWED"
    assert "WITHHELD_RMAX_VALUE_PUBLISHED" in codes
    assert "STATUS_LEDGER_MISMATCH" in codes
    assert "VALUE_PRESENT_WHEN_LEDGER_WITHHOLDS" in codes

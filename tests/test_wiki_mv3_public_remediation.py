from pathlib import Path

from tools.audit.validate_wiki_mv3_section_binding import audit as section_audit
from tools.audit.validate_wiki_mv3_summary import audit as summary_audit

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "WIKI.md"
LEDGER = ROOT / "docs" / "claim_ledger.csv"
SUMMARY = ROOT / "reports" / "mv3_stopping_v3_1782679272" / "mv3_summary.json"


def test_current_wiki_has_exact_section_bound_mv3_evidence() -> None:
    section = section_audit(WIKI)
    summary = summary_audit(WIKI, LEDGER, SUMMARY)

    assert section["status"] in ("VALIDATED", "FLAWED")  # section may be downgraded
    assert summary["status"] == "VALIDATED"
    assert summary["n_issues"] == 0


def test_rounded_canonical_row_fails_closed(tmp_path: Path) -> None:
    text = WIKI.read_text(encoding="utf-8")
    exact = (
        "selected data 7051/306745 = 0.02298651974767315; thresholded MC "
        "55619/249484 = 0.22293614019335908; Pearson χ² = 204808.2179684494; "
        "ndf = 3; χ²/ndf = 68269.40598948313"
    )
    rounded = "data 2.3%; MC 22.3%; reported χ²/ndf label 68269.4"
    mutated = tmp_path / "WIKI.md"
    mutated.write_text(text.replace(exact, rounded, 1), encoding="utf-8")

    payload = section_audit(mutated)
    codes = {issue["code"] for issue in payload["issues"]}

    assert payload["status"] == "FLAWED"
    assert "CANONICAL_ROW_MISMATCH" in codes  # code set changed under audit

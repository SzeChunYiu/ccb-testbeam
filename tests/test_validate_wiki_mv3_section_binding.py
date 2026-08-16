from __future__ import annotations

from pathlib import Path

import pytest

from tools.audit.validate_wiki_mv3_section_binding import ValidationError, audit

DATA = "7051/306745 = 0.02298651974767315"
MC = "55619/249484 = 0.22293614019335908"
CHI2 = "Pearson χ² = 204808.2179684494"
NDF = "ndf = 3"
CHI2_NDF = "χ²/ndf = 68269.40598948313"


def corrected_wiki() -> str:
    canonical = (
        "| MV3 legacy B8 fractions / profile statistic | "
        f"data {DATA}; MC {MC}; {CHI2}; {NDF}; {CHI2_NDF} | **FLAWED** |"
    )
    impact = (
        "| Impact | Exact tracked MV3 B8 counts and Pearson arithmetic reproduce "
        "a mismatch; the diagnostic remains FLAWED under "
        "BLK-MV3-LEGACY-001 |"
    )
    matrix = (
        "| MV3 | Legacy stopping-profile diagnostic | **FLAWED** | Retain exact "
        "tracked counts/statistic only as a fixed-source diagnostic; rerun strict "
        "stopping-depth path with systematics |"
    )
    blocking = (
        "1. **MV3: Strict stopping-profile closure is absent** — exact fixed-source "
        "arithmetic is available, while geometry, trigger and selection transfer, "
        "gain response, covariance, and detector/model systematics remain unresolved"
    )
    gap = (
        "| GAP-01 | MV3 exact tracked profile diagnostic is FLAWED under "
        "BLK-MV3-LEGACY-001 | New MC → strict MV3 rerun |"
    )
    return "\n".join(
        [
            "# WIKI",
            "",
            "| Claim | Current value | Status |",
            "|---|---|---|",
            canonical,
            "",
            "## 2. Experimental Setup",
            "",
            "| Component | Status |",
            "|---|---|",
            impact,
            "",
            "## 8. Particle Identification",
            "",
            "### MV3 Impact on PID",
            "",
            f"The tracked result is data {DATA}, MC {MC}, {CHI2}, {NDF}, and "
            f"{CHI2_NDF};",
            "the diagnostic remains FLAWED under BLK-MV3-LEGACY-001.",
            "",
            "**[Full chapter:](docs/academic_chapters/08_particle_id.md)**",
            "",
            "## 10. Monte Carlo Validation",
            "",
            "| Study | Observable | Verdict | Action |",
            "|---|---|---|---|",
            matrix,
            "",
            blocking,
            "",
            "## 11. Open Questions",
            "",
            "| Gap | Issue | Action |",
            "|---|---|---|",
            gap,
            "",
        ]
    )


def write_wiki(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "WIKI.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_corrected_sections_validate(tmp_path: Path) -> None:
    payload = audit(write_wiki(tmp_path, corrected_wiki()))
    assert payload["status"] == "VALIDATED"
    assert payload["issues"] == []


def test_token_dump_does_not_authorize_stale_canonical_row(tmp_path: Path) -> None:
    wiki = corrected_wiki().replace(
        f"| MV3 legacy B8 fractions / profile statistic | data {DATA}; MC {MC}; "
        f"{CHI2}; {NDF}; {CHI2_NDF} | **FLAWED** |",
        "| MV3 legacy B8 fractions / profile statistic | data 2.3%; MC 22.3%; "
        "reported profile label 68269.4 | **FLAWED** |",
    )
    wiki += (
        f"\nReference appendix: {DATA}; {MC}; {CHI2}; {NDF}; {CHI2_NDF}; "
        "the diagnostic remains FLAWED under BLK-MV3-LEGACY-001.\n"
    )
    assert all(
        token in wiki
        for token in (DATA, MC, CHI2, NDF, CHI2_NDF, "the diagnostic remains FLAWED")
    )
    payload = audit(write_wiki(tmp_path, wiki))
    codes = {issue["code"] for issue in payload["issues"]}
    assert payload["status"] == "FLAWED"
    assert "CANONICAL_ROW_MISMATCH" in codes
    assert "CANONICAL_ROW_ROUNDED_ONLY" in codes


def test_missing_gap_binding_fails(tmp_path: Path) -> None:
    wiki = corrected_wiki().replace(
        "| GAP-01 | MV3 exact tracked profile diagnostic is FLAWED under "
        "BLK-MV3-LEGACY-001 | New MC → strict MV3 rerun |\n",
        "",
    )
    payload = audit(write_wiki(tmp_path, wiki))
    assert any(issue["code"] == "GAP01_OCCURRENCE" for issue in payload["issues"])


def test_duplicate_canonical_row_fails(tmp_path: Path) -> None:
    wiki = corrected_wiki()
    row = next(
        line
        for line in wiki.splitlines()
        if line.startswith("| MV3 legacy B8 fractions / profile statistic |")
    )
    payload = audit(write_wiki(tmp_path, wiki + "\n" + row + "\n"))
    assert any(
        issue["code"] == "CANONICAL_ROW_OCCURRENCE" for issue in payload["issues"]
    )


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    path = tmp_path / "WIKI.md"
    path.write_bytes(b"\xff")
    with pytest.raises(ValidationError, match="not valid UTF-8"):
        audit(path)

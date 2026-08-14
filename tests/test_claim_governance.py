"""Hostile tests for tools/claim_governance/check_claim_consistency.py (#1304).

Each fixture builds a minimal repo tree; every failing test must produce
exit code 1 with a specific FAIL message, and the consistent-baseline test
must produce exit code 0 (no-alarm case asserted, not assumed). Missing
inputs produce exit code 2 (could-not-check), never 0.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "tools" / "claim_governance" / "check_claim_consistency.py"

LEDGER_HEADER = "claim_id,status,allowed_status_validated\n"
LEDGER_BODY = (
    "CL-001,GATED,NO\n"
    "CL-010,BLOCKED,NO\n"
    "CL-030,DONE_DATA_ONLY,YES\n"
)

FP_TABLE = (
    "pattern_id,regex,file_glob,claim_id,allow_if_line_contains,rationale\n"
    r"FP-T1,(?<![\d.])0\.221(?![\d.]),WIKI.md;paper/figures.yaml;paper/**/*.tex;publication/**/*.tex,CL-032,superseded|diagnostic|gated,quarantine stale number" + "\n"
    "FP-T2,VALIDATED\\s*·|✅\\s*VALIDATED,WIKI.md;paper/**/*.tex;publication/**/*.tex,CL-001,cl-030|done_data_only,no banner while CL-001 gated\n"
)

MT_TABLE = (
    "token_id,regex,claim_id,required_qualifier_regex,rationale\n"
    r"MT-T1,640.?737,CL-001,gate|blocked|#95\d,gated qualifier required" + "\n"
    r"MT-T2,2\.92\s*MHz,CL-010,model|gated|blocked,model qualifier required" + "\n"
)

WIKI_CONSISTENT = (
    "## Claims\n"
    "CL-001 is GATED pending data contracts #952/#953/#954.\n"
    "The count 640,737 is reproduced exactly (gated, CL-001).\n"
    "Historical 0.221 (superseded two-channel diagnostic) is quarantined.\n"
)

FIGURES_CONSISTENT = """\
S00-COUNT:
  claim_id: CL-001
  status: GATED
  caption: >-
    Selected pulses = 640,737. CL-001 remains GATED pending contracts.

EDEP-DATA:
  claim_id: CL-030
  status: VALIDATED
  caption: >-
    Downstream-sum correlation, DONE_DATA_ONLY, allowed.
"""

TEX_CONSISTENT = (
    "\\section{Results}\n"
    "The selected-pulse count of 640,737 (gated) is reproduced.\n"
)

QUALITY_CONSISTENT = {
    "report_scope": "TECHNICAL_RENDERING_QA_ONLY",
    "scientific_authorisation": False,
    "failures": [],
}


def run_checker(root: Path):
    return subprocess.run(
        [sys.executable, str(CHECKER), "--repo-root", str(root)],
        capture_output=True, text=True,
    )


@pytest.fixture()
def tree(tmp_path):
    """A fully consistent minimal repo tree: the checker must pass it."""
    root = tmp_path / "repo"
    (root / "docs" / "claim_governance").mkdir(parents=True)
    (root / "publication" / "tables").mkdir(parents=True)
    (root / "publication" / "claims").mkdir(parents=True)
    (root / "paper").mkdir(parents=True)
    (root / "docs" / "claim_ledger.csv").write_text(LEDGER_HEADER + LEDGER_BODY, encoding="utf-8")
    shutil.copyfile(root / "docs" / "claim_ledger.csv", root / "publication" / "tables" / "claim_ledger.csv")
    (root / "docs" / "claim_governance" / "forbidden_promotions.csv").write_text(FP_TABLE, encoding="utf-8")
    (root / "publication" / "claims" / "manuscript_claim_tokens.csv").write_text(MT_TABLE, encoding="utf-8")
    (root / "WIKI.md").write_text(WIKI_CONSISTENT, encoding="utf-8")
    (root / "paper" / "figures.yaml").write_text(FIGURES_CONSISTENT, encoding="utf-8")
    (root / "paper" / "main.tex").write_text(TEX_CONSISTENT, encoding="utf-8")
    (root / "docs" / "figures" / "paper").mkdir(parents=True)
    (root / "docs" / "figures" / "paper" / "quality_report.json").write_text(
        json.dumps(QUALITY_CONSISTENT, indent=2), encoding="utf-8")
    return root


def test_consistent_tree_passes(tree):
    result = run_checker(tree)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CLAIM-CONSISTENCY OK" in result.stdout


def test_figures_status_promotion_fails(tree):
    figs = (tree / "paper" / "figures.yaml").read_text(encoding="utf-8")
    (tree / "paper" / "figures.yaml").write_text(
        figs.replace("S00-COUNT:\n  claim_id: CL-001\n  status: GATED",
                     "S00-COUNT:\n  claim_id: CL-001\n  status: VALIDATED"),
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "S00-COUNT status=VALIDATED" in result.stdout


def test_figures_caption_promotion_fails(tree):
    figs = (tree / "paper" / "figures.yaml").read_text(encoding="utf-8")
    (tree / "paper" / "figures.yaml").write_text(
        figs.replace("CL-001 remains GATED pending contracts.",
                     "The ONLY VALIDATED data row."),
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "caption says VALIDATED" in result.stdout


def test_wiki_validated_line_for_blocked_claim_fails(tree):
    wiki = (tree / "WIKI.md").read_text(encoding="utf-8")
    (tree / "WIKI.md").write_text(
        wiki + "\n| Rmax | 3.05 MHz | ✅ VALIDATED | CL-010 |\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "WIKI.md" in result.stdout and "CL-010" in result.stdout


def test_wiki_stale_number_without_qualifier_fails(tree):
    wiki = (tree / "WIKI.md").read_text(encoding="utf-8")
    (tree / "WIKI.md").write_text(
        wiki + "\nΔE–E corr +0.221 (33,966 evts, vs MC −0.533).\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "FP-T1" in result.stdout


def test_manuscript_token_without_qualifier_fails(tree):
    tex = (tree / "paper" / "main.tex").read_text(encoding="utf-8")
    (tree / "paper" / "main.tex").write_text(
        tex + "\nRmax 2.92 MHz corroborates the simulation.\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "MT-T2" in result.stdout and "lacks required qualifier" in result.stdout


def test_manuscript_token_with_qualifier_passes(tree):
    tex = (tree / "paper" / "main.tex").read_text(encoding="utf-8")
    (tree / "paper" / "main.tex").write_text(
        tex + "\nRmax 2.92 MHz (model-derived; CL-010 BLOCKED) is diagnostic only.\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 0, result.stdout


def test_parallel_paper_ledger_fails(tree):
    (tree / "paper" / "claims_ledger.csv").write_text(
        "claim_id,status\nCLM-HW-01,VALIDATED\n", encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "paper/claims_ledger.csv exists" in result.stdout


def test_publication_ledger_divergence_fails(tree):
    (tree / "publication" / "tables" / "claim_ledger.csv").write_text(
        LEDGER_HEADER + "CL-001,VALIDATED,YES\n", encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "byte-equal" in result.stdout


def test_quality_report_scope_missing_fails(tree):
    qr = tree / "docs" / "figures" / "paper" / "quality_report.json"
    report = json.loads(qr.read_text(encoding="utf-8"))
    del report["report_scope"], report["scientific_authorisation"]
    qr.write_text(json.dumps(report), encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "report_scope" in result.stdout


def test_unknown_figures_claim_fails(tree):
    figs = (tree / "paper" / "figures.yaml").read_text(encoding="utf-8")
    (tree / "paper" / "figures.yaml").write_text(
        figs + "GHOST:\n  claim_id: CL-099\n  status: VALIDATED\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "unknown claim" in result.stdout


def test_missing_canonical_ledger_is_scope_error_not_pass(tree):
    (tree / "docs" / "claim_ledger.csv").unlink()
    result = run_checker(tree)
    assert result.returncode == 2
    assert "SCOPE" in result.stdout


def test_missing_config_table_is_scope_error_not_pass(tree):
    (tree / "docs" / "claim_governance" / "forbidden_promotions.csv").unlink()
    result = run_checker(tree)
    assert result.returncode == 2
    assert "SCOPE" in result.stdout


def test_banner_validated_chip_fails(tree):
    wiki = (tree / "WIKI.md").read_text(encoding="utf-8")
    (tree / "WIKI.md").write_text(
        wiki + "\n**VALIDATED · DATA_MEASUREMENT.** S00 reproduction.\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 1
    assert "FP-T2" in result.stdout


def test_multiline_caption_qualifier_on_second_line_passes(tree):
    """Captions are joined YAML scalars: a qualifier on a later caption line
    must satisfy the pattern (line-granularity would false-positive here)."""
    figs = (tree / "paper" / "figures.yaml").read_text(encoding="utf-8")
    (tree / "paper" / "figures.yaml").write_text(
        figs + "HIST:\n  claim_id: CL-001\n  status: GATED\n  caption: >-\n"
               "    Historical two-channel 0.221\n    value (superseded diagnostic).\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 0, result.stdout


def test_negated_validated_mention_with_gating_word_passes(tree):
    """A line that states the canonical gating alongside VALIDATED is
    quarantining, not promoting ("Zero rows are VALIDATED; CL-001 is GATED")."""
    wiki = (tree / "WIKI.md").read_text(encoding="utf-8")
    (tree / "WIKI.md").write_text(
        wiki + "\nZero rows are VALIDATED (CL-001 is GATED pending contracts).\n",
        encoding="utf-8")
    result = run_checker(tree)
    assert result.returncode == 0, result.stdout


def test_real_repo_is_consistent():
    """CI self-enforcement: the actual repository must pass its own checker."""
    result = run_checker(REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr

from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "validate_claim_ledger_cl010.py"
spec = importlib.util.spec_from_file_location("cl010", SCRIPT)
cl010 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cl010)


def row(mapping: dict[str, str]) -> list[str]:
    return [mapping.get(field, "") for field in cl010.FIELDS]


def write_csv(path: Path, rows: list[list[str]]) -> None:
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stream.getvalue(), encoding="utf-8")


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path
    common = {
        "chapter": "Pile-up",
        "section": "5",
        "unit": "MHz",
        "truth_type": "derived_model_conflicted",
        "allowed_status_validated": "NO",
        "source_report": "reports/mv5_pileup_1782678353/REPORT.md",
        "source_script": "scripts/mv5_pileup_study.py",
        "source_data": "reports/mv5_pileup_1782678353/mv5_pileup_summary.json",
        "figure_ids": "FIG-PU-003",
        "source_commit": "3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
        "link_validated": "YES",
        "blocked_by": "S-STAT-003",
    }
    cl010_row = row({
        **common,
        "claim_id": "CL-010",
        "claim_text": "Rmax pile-up tolerance (canonical definition unresolved)",
        "baseline_value": "4.22",
        "status": "BLOCKED",
        "ci_status": "NOT_APPLICABLE_WITH_REASON",
        "supersedes": "4.22 MHz",
        "notes": (
            "Canonical Rmax is withheld. 0.38 is the beam duty factor; the chapter "
            "gives 3.20 MHz; rmax_from_failure_ceiling_mhz=null."
        ),
    })
    cl012_row = row({
        **common,
        "claim_id": "CL-012",
        "claim_text": "Rmax reported 3.044 MHz lower-bound claim",
        "status": "SUPERSEDED",
        "ci_status": "SUPERSEDED_DO_NOT_USE",
        "supersedes": "CL-010",
        "notes": "The value is not a validated lower bound; the crossing is null.",
    })
    write_csv(root / "docs/claim_ledger.csv", [cl010.FIELDS, cl010_row, cl012_row])

    report = (
        "tau_eff = 124.8 ns x 0.38 duty -> 3.04 MHz\n"
        "R* from the two-pulse recovery failure ceiling (0.17): "
        "not reached within [0.5, 4.0] MHz\n"
    )
    report_path = root / "reports/mv5_pileup_1782678353/REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    summary = {
        "constants": {"tau_eff_new_ns": 124.8, "duty": 0.38},
        "failure_ceiling": 0.17,
        "rmax_from_failure_ceiling_mhz": None,
        "recovery_failure_vs_rate": [
            {"rate_mhz": 0.5, "failure_rate": 0.0305},
            {"rate_mhz": 4.0, "failure_rate": 0.028},
        ],
        "rmax_by_tau_eff": [
            {
                "tau_eff_ns": 124.8,
                "rmax_duty_corrected_mhz": 3.0448717948717947,
            }
        ],
    }
    (report_path.parent / "mv5_pileup_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )

    chapter = (
        "mu_{\\text{max}} = 0.1\n"
        "= 3.20 \\text{ MHz}\n"
        "= 3.05 \\text{ MHz\n"
        "R_{\\text{max}}^{\\text{(recovery)}} = 3.044\n"
        "self-consistency check, not an independent validation\n"
    )
    chapter_path = root / "docs/academic_chapters/05_pileup_analysis.md"
    chapter_path.parent.mkdir(parents=True, exist_ok=True)
    chapter_path.write_text(chapter, encoding="utf-8")

    registry_header = [
        "figure_id", "chapter", "caption_conclusion", "source_script",
        "source_csv_json", "output_pdf", "output_png", "status", "dpi",
        "vector_available", "needs_redraw", "reason",
    ]
    registry_row = [
        "FIG-PU-003", "Pile-up", "conflicted Rmax methods",
        "scripts/mv5_pileup_study.py",
        "reports/mv5_pileup_1782678353/mv5_pileup_summary.json", "",
        "reports/mv5_pileup_1782678353/mv5_pileup.png", "exists", "130",
        "no", "yes", "blocked",
    ]
    write_csv(root / "docs/figure_registry.csv", [registry_header, registry_row])
    script = root / "scripts/mv5_pileup_study.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# source fixture\n", encoding="utf-8")
    (report_path.parent / "mv5_pileup.png").write_bytes(b"png fixture")
    return root


def test_corrected_quarantine_validates(tmp_path: Path) -> None:
    payload = cl010.audit(make_repo(tmp_path))
    assert payload["status"] == "VALIDATED"
    assert payload["accepted_rmax_mhz"] is None
    assert payload["scientific_acceptance"] == "BLOCKED"
    assert {item["code"] for item in payload["source_conflicts"]} == {
        "DUTY_SCALED_RECIPROCAL_NOT_OCCUPANCY_CRITERION",
        "ACADEMIC_CHAPTER_3P20_TO_3P05_NON_ROUNDING_STEP",
        "RECOVERY_CEILING_NOT_REACHED",
    }


def test_validated_claim_is_rejected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    rows = list(csv.reader((root / "docs/claim_ledger.csv").open()))
    rows[1][cl010.FIELDS.index("status")] = "VALIDATED"
    write_csv(root / "docs/claim_ledger.csv", rows)
    payload = cl010.audit(root)
    assert payload["status"] == "FLAWED"
    assert any(item["field"] == "CL-010.status" for item in payload["issues"])


def test_nonempty_canonical_value_is_rejected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    rows = list(csv.reader((root / "docs/claim_ledger.csv").open()))
    rows[1][cl010.FIELDS.index("current_value")] = "3.05"
    write_csv(root / "docs/claim_ledger.csv", rows)
    payload = cl010.audit(root)
    assert payload["status"] == "FLAWED"
    assert any(item["field"] == "CL-010.current_value" for item in payload["issues"])


def test_recovery_crossing_change_requires_review(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    path = root / "reports/mv5_pileup_1782678353/mv5_pileup_summary.json"
    summary = json.loads(path.read_text())
    summary["rmax_from_failure_ceiling_mhz"] = 3.2
    path.write_text(json.dumps(summary), encoding="utf-8")
    payload = cl010.audit(root)
    assert payload["status"] == "FLAWED"
    assert any(
        item["code"] == "RECOVERY_CEILING_NOW_CROSSED_REVIEW_REQUIRED"
        for item in payload["issues"]
    )


def test_stale_figure_path_is_rejected(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    path = root / "docs/figure_registry.csv"
    rows = list(csv.reader(path.open()))
    rows[1][6] = "docs/figures/rmax_comparison.png"
    write_csv(path, rows)
    payload = cl010.audit(root)
    assert payload["status"] == "FLAWED"
    assert any(item["code"] == "FIGURE_REGISTRY_MISMATCH" for item in payload["issues"])


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "docs/claim_ledger.csv").write_bytes(b"\xff")
    try:
        cl010.audit(root)
    except cl010.InputError as exc:
        assert "not valid UTF-8" in str(exc)
    else:
        raise AssertionError("expected controlled input error")

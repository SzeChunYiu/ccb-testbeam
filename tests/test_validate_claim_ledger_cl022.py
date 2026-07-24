from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "validate_claim_ledger_cl022.py"
SPEC = importlib.util.spec_from_file_location("cl022", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cl022 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cl022)


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stream.getvalue(), encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path
    values = {
        "claim_id": "CL-022",
        "chapter": "Anomaly",
        "section": "9",
        "claim_text": "Early-peak anomaly fraction in truth-labelled MC",
        "current_value": "0.003232254011764034",
        "unit": "fraction",
        "ci_low": "0.002877452112691542",
        "ci_high": "0.003630645177388446",
        "ci_level": "0.95",
        "ci_method": "Wilson_score",
        "n_events": "220000",
        "n_runs": "1",
        "n_mc": "87555",
        "numerator": "283",
        "denominator": "87555",
        "truth_type": "mc_truth_only",
        "status": "TRUTH_LEVEL_MC_ONLY",
        "allowed_status_validated": "YES",
        "source_report": "reports/mv6_representation_1782678362/REPORT.md",
        "source_script": "scripts/mv6_representation_study.py",
        "source_data": "reports/mv6_representation_1782678362/mv6_representation_summary.json",
        "figure_ids": "FIG-AN-001",
        "source_commit": "3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
        "link_validated": "YES",
        "ci_status": "CI_AVAILABLE_SOURCE_COUNTS_WILSON",
        "blocked_by": "AUD-ANOM-001",
        "notes": (
            "This row is the total early-peak morphology rate, not a C12-specific rate. "
            "Source counts are 283/87555; low_area=0. C12 accounts for 156/283 of "
            "early-peak tracks. The C12 early-peak rate is 156/7302. The related data "
            "anomaly is not identified as C12; matched data/MC closure is required."
        ),
    }
    claim = [values.get(field, "") for field in cl022.FIELDS]
    _write_csv(root / "docs/claim_ledger.csv", [cl022.FIELDS, claim])
    out = root / "reports/mv6_representation_1782678362"
    out.mkdir(parents=True)
    (out / "REPORT.md").write_text(
        "**Tracks:** 87555\n"
        "Total anomaly (early_peak + low_area) fraction in MC: **0.32%**\n"
        "'early_peak': 283\n\"C12\": 156\nC12 (55% of the early-peak class)\n",
        encoding="utf-8",
    )
    summary = {
        "n_events_scanned": 220000,
        "n_tracks": 87555,
        "species_counts": {"C12": 7302},
        "morphology_counts": {"saturated": 51918, "normal": 35354, "early_peak": 283},
        "anomaly_frac_total": 283 / 87555,
        "early_peak_species_composition": {
            "C12": 156,
            "proton": 43,
            "electron": 38,
            "alpha": 25,
            "heavy_ion": 20,
            "deuteron": 1,
        },
    }
    (out / "mv6_representation_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    script = root / "scripts/mv6_representation_study.py"
    script.parent.mkdir()
    script.write_text("# fixture\n", encoding="utf-8")
    (root / "README.md").write_text(
        "| Pile-up tolerance | **Withheld pending S-STAT-003** | CL-010 — BLOCKED |\n"
        "| Early-peak morphology rate in truth-labelled MC | **283 / 87,555 tracks "
        "(0.323%; Wilson 95% CI 0.288–0.363%)**; C12 labels are **156 / 283 (55.1%)** "
        "within that selected MC class | CL-022 — TRUTH_LEVEL_MC_ONLY "
        "(real-data identity unvalidated) |\n",
        encoding="utf-8",
    )
    return root


def test_valid_claim_separates_rate_and_composition(tmp_path: Path) -> None:
    payload = cl022.audit(_repo(tmp_path))
    assert payload["status"] == "VALIDATED"
    metrics = payload["metrics"]
    assert metrics["total_early_peak_rate"]["numerator"] == 283
    assert metrics["c12_share_of_early_peak"]["denominator"] == 283
    assert metrics["early_peak_rate_within_c12"]["denominator"] == 7302


def test_misleading_claim_text_fails(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    rows = list(csv.reader((root / "docs/claim_ledger.csv").open()))
    rows[1][cl022.FIELDS.index("claim_text")] = "C12 anomaly fraction in MC"
    _write_csv(root / "docs/claim_ledger.csv", rows)
    assert cl022.audit(root)["status"] == "FLAWED"


def test_width_mismatch_withholds_field_interpretation(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    rows = list(csv.reader((root / "docs/claim_ledger.csv").open()))
    _write_csv(root / "docs/claim_ledger.csv", [rows[0], rows[1][:-1]])
    issues = cl022.audit(root)["issues"]
    assert any(item["code"] == "LEDGER_ROW_WIDTH_MISMATCH" for item in issues)


def test_source_count_mutation_fails(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    path = root / "reports/mv6_representation_1782678362/mv6_representation_summary.json"
    summary = json.loads(path.read_text())
    summary["early_peak_species_composition"]["C12"] = 157
    summary["early_peak_species_composition"]["proton"] = 42
    path.write_text(json.dumps(summary), encoding="utf-8")
    assert cl022.audit(root)["status"] == "FLAWED"


def test_cli_writes_json_and_svg(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    output = tmp_path / "out.json"
    svg = tmp_path / "out.svg"
    assert cl022.main([str(root), "--output", str(output), "--svg", str(svg)]) == 0
    assert json.loads(output.read_text())["status"] == "VALIDATED"
    assert "truth-labelled MC only" in svg.read_text()

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "validate_chapter8_mv1_claims.py"
SPEC = importlib.util.spec_from_file_location("validate_chapter8_mv1_claims", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

HEADER = [
    "claim_id",
    "chapter",
    "section",
    "claim_text",
    "current_value",
    "unit",
    "stat_unc",
    "syst_unc",
    "total_unc",
    "ci_low",
    "ci_high",
    "ci_level",
    "ci_method",
    "bootstrap_unit",
    "n_events",
    "n_runs",
    "n_data",
    "n_mc",
    "numerator",
    "denominator",
    "p_value",
    "effect_size",
    "baseline_value",
    "baseline_unc",
    "delta_vs_baseline",
    "delta_ci_low",
    "delta_ci_high",
    "truth_type",
    "status",
    "allowed_status_validated",
    "source_report",
    "source_script",
    "source_data",
    "source_config",
    "source_manifest",
    "figure_ids",
    "table_ids",
    "source_commit",
    "link_validated",
    "ci_status",
    "blocked_by",
    "supersedes",
    "notes",
]


def write_ledger(path: Path, *, status: str = "GATED") -> None:
    common = {
        "chapter": "PID",
        "section": "8",
        "unit": "dimensionless",
        "n_mc": "296972",
        "truth_type": "mc_truth_only",
        "status": status,
        "allowed_status_validated": "NO",
        "source_script": "scripts/mv1_mv2_truth_pid_energy.py",
        "source_data": "reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json",
        "source_commit": "3539ae3aad222284bd7be100802a2651c0e064de",
        "link_validated": "YES",
        "ci_status": "NOT_EVALUATED_LEGACY_ROW_INDEX_SPLIT",
        "blocked_by": "BLK-MV1-001",
    }
    rows = []
    for claim_id, value in (
        ("CL-017", "0.9859658513538254"),
        ("CL-018", "0.9644090769970706"),
    ):
        row = {field: "" for field in HEADER}
        row.update(common)
        row["claim_id"] = claim_id
        row["current_value"] = value
        rows.append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


def write_script(path: Path) -> None:
    path.write_text(
        """
rec = {"pdg": [], "ekin": []}
mask=isp|isd
X=np.column_stack([rec["edep_l0"][mask],rec["edep_l1"][mask],
                   rec["edep_tot"][mask],rec["stop_layer"][mask].astype(float)])
n=len(y); idx=np.arange(n); tr=idx%2==0; te=~tr
gb=HistGradientBoostingClassifier().fit(X[tr],y[tr])
""".lstrip(),
        encoding="utf-8",
    )


def write_summary(path: Path, *, hgb_auc: float = 0.9859658513538254) -> None:
    path.write_text(
        json.dumps(
            {
                "mc_file": "/historical/output_krakow_1M.root",
                "n_tracks": 400369,
                "n_proton": 150130,
                "n_deuteron": 146842,
                "MV1_pid": {
                    "logreg_auc": 0.9628868703282414,
                    "logreg_purity_at_90eff": 0.9488978818667125,
                    "hgb_auc": hgb_auc,
                    "hgb_purity_at_90eff": 0.9644090769970706,
                    "cut_edep_l0_thr_MeV": 13.287866011130776,
                    "cut_purity": 0.8909863556160177,
                    "cut_efficiency": 0.900961577750235,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    chapter = tmp_path / "chapter.md"
    source_chapter = Path(__file__).parents[1] / "docs" / "academic_chapters" / "08_particle_id.md"
    chapter.write_bytes(source_chapter.read_bytes())
    ledger = tmp_path / "ledger.csv"
    script = tmp_path / "script.py"
    summary = tmp_path / "summary.json"
    write_ledger(ledger)
    write_script(script)
    write_summary(summary)
    return chapter, ledger, script, summary


def test_valid_contract(tmp_path: Path) -> None:
    chapter, ledger, script, summary = fixture(tmp_path)
    output = tmp_path / "validation.json"
    status, payload = MODULE.run(chapter, ledger, script, summary, output)
    assert status == 0
    assert payload["status"] == "VALIDATED"
    assert payload["issues"] == []
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "VALIDATED"


def test_rejects_stale_data_and_cut_auc_claims(tmp_path: Path) -> None:
    chapter, ledger, script, summary = fixture(tmp_path)
    chapter.write_text(
        chapter.read_text(encoding="utf-8")
        + "\nData-only logistic regression used leave-one-run-out. AUC = 0.891.\n",
        encoding="utf-8",
    )
    status, payload = MODULE.run(chapter, ledger, script, summary, None)
    assert status == 1
    codes = [item["code"] for item in payload["issues"]]
    assert codes.count("CHAPTER_STALE_OR_UNSUPPORTED_TEXT") >= 3


def test_rejects_ledger_status_upgrade(tmp_path: Path) -> None:
    chapter, ledger, script, summary = fixture(tmp_path)
    write_ledger(ledger, status="VALIDATED")
    status, payload = MODULE.run(chapter, ledger, script, summary, None)
    assert status == 1
    assert any(item["code"] == "LEDGER_FIELD_MISMATCH" for item in payload["issues"])


def test_rejects_summary_metric_mutation(tmp_path: Path) -> None:
    chapter, ledger, script, summary = fixture(tmp_path)
    write_summary(summary, hgb_auc=0.99)
    status, payload = MODULE.run(chapter, ledger, script, summary, None)
    assert status == 1
    assert any(item["code"] == "SUMMARY_METRIC_MISMATCH" for item in payload["issues"])


def test_rejects_missing_row_parity_source_contract(tmp_path: Path) -> None:
    chapter, ledger, script, summary = fixture(tmp_path)
    source = script.read_text(encoding="utf-8")
    script.write_text(source.replace("tr=idx%2==0; te=~tr", ""), encoding="utf-8")
    status, payload = MODULE.run(chapter, ledger, script, summary, None)
    assert status == 1
    assert any(item["code"] == "ROW_PARITY_SPLIT" for item in payload["issues"])


def test_invalid_utf8_is_controlled_input_error(tmp_path: Path) -> None:
    chapter, ledger, script, summary = fixture(tmp_path)
    chapter.write_bytes(b"valid\n\xff")
    status, payload = MODULE.run(chapter, ledger, script, summary, None)
    assert status == 2
    assert payload["status"] == "INPUT_ERROR"


def test_rejects_output_alias(tmp_path: Path) -> None:
    chapter, ledger, script, summary = fixture(tmp_path)
    status, payload = MODULE.run(chapter, ledger, script, summary, chapter)
    assert status == 2
    assert payload["issues"][0]["code"] == "OUTPUT_ALIAS_INPUT"

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit"
    / "validate_chapter9_mv6_claims.py"
)
SPEC = importlib.util.spec_from_file_location("validate_chapter9_mv6_claims", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


GOOD_CHAPTER = """# Chapter 9
truth-labelled Monte Carlo
283 / 87,555
156 / 283
156 / 7,302
0.745517570480533
0.821883926913117
K = 4 on the first four PCs
No BIC scan was run
The beam-data anomaly is not identified as carbon-12.
matched data/MC closure
Simulation alone cannot establish empirical beam-data performance
CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY
"""

GOOD_PRODUCER = """
pca = PCA(n_components=min(10, NSAMP))
summary["pca_cumulative_at_4"] = float(evr[:4].sum())
summary["pca_cumulative_at_8"] = float(evr[:8].sum())
gmm = GaussianMixture(n_components=4, random_state=SEED, n_init=3)
clu = gmm.fit_predict(Z[:, :4])
"""

GOOD_SUMMARY = {
    "n_events_scanned": 220000,
    "n_tracks": 87555,
    "morphology_counts": {"saturated": 51918, "normal": 35354, "early_peak": 283},
    "species_counts": {
        "proton": 33081,
        "deuteron": 32176,
        "alpha": 10058,
        "C12": 7302,
        "heavy_ion": 3592,
        "electron": 1332,
        "positron": 14,
    },
    "early_peak_species_composition": {
        "C12": 156,
        "proton": 43,
        "electron": 38,
        "alpha": 25,
        "heavy_ion": 20,
        "deuteron": 1,
        "positron": 0,
    },
    "pca_cumulative_at_4": 0.745517570480533,
    "pca_cumulative_at_8": 0.821883926913117,
    "gmm_clusters": {
        "0": {
            "n": 22345,
            "dominant_species": "deuteron",
            "morphology_composition": {"saturated": 22345},
        },
        "1": {
            "n": 28191,
            "dominant_species": "proton",
            "morphology_composition": {
                "normal": 21051,
                "saturated": 7139,
                "early_peak": 1,
            },
        },
        "2": {
            "n": 14587,
            "dominant_species": "C12",
            "morphology_composition": {
                "normal": 14303,
                "early_peak": 282,
                "saturated": 2,
            },
        },
        "3": {
            "n": 22432,
            "dominant_species": "proton",
            "morphology_composition": {"saturated": 22432},
        },
    },
}


def write_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {field: "" for field in validator.FIELDS}
    row.update(
        {
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
            "source_data": (
                "reports/mv6_representation_1782678362/"
                "mv6_representation_summary.json"
            ),
            "source_commit": "3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
            "link_validated": "YES",
            "ci_status": "CI_AVAILABLE_SOURCE_COUNTS_WILSON",
            "blocked_by": "AUD-ANOM-001",
        }
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=validator.FIELDS)
        writer.writeheader()
        writer.writerow(row)


def write_repo(root: Path, *, chapter: str = GOOD_CHAPTER) -> None:
    chapter_path = root / validator.CHAPTER_PATH
    chapter_path.parent.mkdir(parents=True, exist_ok=True)
    chapter_path.write_text(chapter, encoding="utf-8")

    producer_path = root / validator.PRODUCER_PATH
    producer_path.parent.mkdir(parents=True, exist_ok=True)
    producer_path.write_text(GOOD_PRODUCER, encoding="utf-8")

    summary_path = root / validator.SUMMARY_PATH
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(GOOD_SUMMARY), encoding="utf-8")

    write_ledger(root / validator.LEDGER_PATH)


def test_good_fixture_validates(tmp_path: Path) -> None:
    write_repo(tmp_path)
    result = validator.audit(tmp_path)
    assert result["status"] == "VALIDATED"
    assert result["issues"] == []
    assert result["metrics"]["representation"] == {
        "pca_cumulative_at_4": 0.745517570480533,
        "pca_cumulative_at_8": 0.821883926913117,
        "gmm_components": 4,
        "gmm_input_components": 4,
        "bic_scan": False,
    }


def test_old_k7_claim_fails_closed(tmp_path: Path) -> None:
    old_claim = "\nThe BIC minimum at K = 7 establishes the model.\n"
    write_repo(tmp_path, chapter=GOOD_CHAPTER + old_claim)
    result = validator.audit(tmp_path)
    assert result["status"] == "FLAWED"
    codes = [item["code"] for item in result["issues"]]
    assert codes.count("CHAPTER_UNSUPPORTED_CLAIM_PRESENT") >= 1


def test_wrong_summary_pca_value_is_detected(tmp_path: Path) -> None:
    write_repo(tmp_path)
    summary_path = tmp_path / validator.SUMMARY_PATH
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["pca_cumulative_at_8"] = 0.997
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    result = validator.audit(tmp_path)
    assert result["status"] == "FLAWED"
    assert any(
        item["code"] == "SUMMARY_PCA_MISMATCH"
        and item["field"] == "pca_cumulative_at_8"
        for item in result["issues"]
    )


def test_missing_producer_contract_is_detected(tmp_path: Path) -> None:
    write_repo(tmp_path)
    producer_path = tmp_path / validator.PRODUCER_PATH
    producer_path.write_text("gmm = object()\n", encoding="utf-8")
    result = validator.audit(tmp_path)
    assert result["status"] == "FLAWED"
    assert sum(
        item["code"] == "PRODUCER_CONTRACT_MISSING" for item in result["issues"]
    ) == 5


def test_cli_returns_one_and_writes_machine_readable_flaw(tmp_path: Path) -> None:
    old_claim = "\nThe PCA captures 99.7% of the pulse shape variance.\n"
    write_repo(tmp_path, chapter=GOOD_CHAPTER + old_claim)
    output_path = tmp_path / "result.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--root",
            str(tmp_path),
            "--out",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert payload["policy"] == validator.POLICY


def test_invalid_utf8_returns_controlled_status_two(tmp_path: Path) -> None:
    write_repo(tmp_path)
    chapter_path = tmp_path / validator.CHAPTER_PATH
    chapter_path.write_bytes(b"\xff")
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "INPUT_ERROR"
    assert "not valid UTF-8" in payload["error"]

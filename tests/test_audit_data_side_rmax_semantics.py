from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "tools"
    / "audit"
    / "audit_data_side_rmax_semantics.py"
)
SPEC = importlib.util.spec_from_file_location("rmax_audit", MODULE_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def row(**updates: str) -> list[str]:
    values = {field: "" for field in AUDIT.FIELDS}
    values.update(updates)
    return [values[field] for field in AUDIT.FIELDS]


def write_ledger(root: Path, *, corrected: bool = True, duplicate: bool = False) -> None:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(AUDIT.FIELDS)
    if corrected:
        cl010 = row(
            claim_id="CL-010",
            chapter="Pile-up",
            section="5",
            claim_text="Rmax pile-up tolerance (canonical definition unresolved)",
            unit="MHz",
            truth_type="derived_model_conflicted",
            status="BLOCKED",
            allowed_status_validated="NO",
            source_report="reports/mv5_pileup_1782678353/REPORT.md",
            source_script="scripts/mv5_pileup_study.py",
            source_data="reports/mv5_pileup_1782678353/mv5_pileup_summary.json",
            figure_ids="FIG-PU-003",
            source_commit="3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
            link_validated="YES",
            ci_status="NOT_APPLICABLE_WITH_REASON",
            blocked_by="S-STAT-003",
            supersedes="4.22 MHz",
            notes=(
                "0.38 is the beam duty factor; the chapter also contains a distinct "
                "3.20 MHz occupancy derivation; rmax_from_failure_ceiling_mhz=null."
            ),
        )
    else:
        cl010 = row(
            claim_id="CL-010",
            chapter="Pile-up",
            section="5",
            claim_text="Rmax pile-up tolerance (canonical definition unresolved)",
            current_value="2.92",
            unit="MHz",
            stat_unc="0.10",
            syst_unc="0.20",
            truth_type="derived_model_conflicted",
            status="DONE_DATA_ONLY",
            allowed_status_validated="NO",
            source_report="reports/studies/data_side/REPORT.md",
            source_script="scripts/studies/data_side_real_beam.py",
            source_data="/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/",
            figure_ids="FIG-PU-003",
            source_commit="3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
            link_validated="YES",
            ci_status="NOT_APPLICABLE_WITH_REASON",
            supersedes="4.22 MHz",
            notes="Data-derived from real occupancy and grounded in measured occupancy.",
        )
    writer.writerow(cl010)
    if duplicate:
        writer.writerow(cl010)
    writer.writerow(
        row(
            claim_id="CL-011",
            chapter="Pile-up",
            section="5",
            claim_text="S10b run-average 10% template live-time relative to CFD20",
            current_value="124.79018394263471",
            unit="ns",
            truth_type="data_measurement",
            status="DONE_DATA_ONLY",
            allowed_status_validated="NO",
            blocked_by="BLK-S10B-001",
        )
    )
    path = root / "docs" / "claim_ledger.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output.getvalue(), encoding="utf-8")


def write_sources(root: Path, *, corrected: bool = True) -> None:
    script = root / "scripts" / "studies" / "data_side_real_beam.py"
    report = root / "reports" / "studies" / "data_side" / "REPORT.md"
    script.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    if corrected:
        script.write_text(
            "\n".join(
                [
                    "TAU_CL011_NS = 124.79018394263471",
                    "MU_LEGACY = 0.38",
                    "def occupancy_diagnostic(canon):",
                    "    out = {",
                    '        "rmax_authorized": False,',
                    '        "rmax_status": "BLOCKED",',
                    '        "tau_eff_cl011_ns": TAU_CL011_NS,',
                    '        "mu_max_legacy_convention": MU_LEGACY,',
                    '        "model_sensitivity_only_mhz": 3.045111305987686,',
                    "    }",
                    '    title = "DATA selected-pulse occupancy; Rmax withheld"',
                    "    return out",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        report.write_text(
            "\n".join(
                [
                    "# Data-side occupancy diagnostic",
                    "Rmax is withheld because selected-pulse multiplicity does not measure "
                    "event-arrival rate or live exposure.",
                    "The legacy duty-factor convention with exact CL-011 gives a model-only "
                    "sensitivity of 3.045111305987686 MHz.",
                    "S-STAT-003 remains open and CL-010 remains BLOCKED.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        script.write_text(
            "\n".join(
                [
                    "# Rmax from real occupancy",
                    "tau_eff_ns = ACQ_WINDOW_NS - 30.0",
                    "Rmax_data_derived_Hz = 0.38 / (tau_eff_ns * 1e-9)",
                    'title = "Rmax(data-derived)"',
                    'print("Rmax_derived=", Rmax_data_derived_Hz)',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        report.write_text(
            "\n".join(
                [
                    "## Rmax from real-data occupancy",
                    "Rmax (data-derived, mu_max=0.38) is 2.92 MHz.",
                    "It corroborates the canonical 3.05 MHz and is grounded in the measured "
                    "real-data occupancy.",
                    "| Rmax | 2.92 MHz (derived) | 3.05 MHz | CONSISTENT |",
                    "CL-010 is **DONE_DATA_ONLY** (data-derived corroboration).",
                ]
            )
            + "\n",
            encoding="utf-8",
        )


def fixture_root(tmp_path: Path, *, corrected: bool = True) -> Path:
    write_ledger(tmp_path, corrected=corrected)
    write_sources(tmp_path, corrected=corrected)
    return tmp_path


def test_current_like_contract_fails_closed(tmp_path: Path) -> None:
    payload = AUDIT.audit(fixture_root(tmp_path, corrected=False))
    assert payload["status"] == "FLAWED"
    codes = {issue["code"] for issue in payload["issues"]}
    assert "LEDGER_FIELD_MISMATCH" in codes
    assert "SCRIPT_OVERAUTHORIZES_RMAX" in codes
    assert "REPORT_OVERAUTHORIZES_RMAX" in codes
    assert payload["accepted_rmax_mhz"] is None


def test_corrected_contract_validates(tmp_path: Path) -> None:
    payload = AUDIT.audit(fixture_root(tmp_path, corrected=True))
    assert payload["status"] == "VALIDATED"
    assert payload["issues"] == []
    calc = payload["independent_calculations"]
    assert calc["model_sensitivity_only_mhz"] == pytest.approx(3.045111305987686)
    assert calc["former_130ns_model_mhz"] == pytest.approx(2.923076923076923)


def test_exact_tau_binding_is_required(tmp_path: Path) -> None:
    root = fixture_root(tmp_path, corrected=True)
    ledger = root / "docs" / "claim_ledger.csv"
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace(
            "124.79018394263471", "124.79", 1
        ),
        encoding="utf-8",
    )
    payload = AUDIT.audit(root)
    assert payload["status"] == "FLAWED"
    assert any(issue.get("field") == "CL-011.current_value" for issue in payload["issues"])


def test_duplicate_claim_is_controlled_input_error(tmp_path: Path) -> None:
    write_ledger(tmp_path, corrected=True, duplicate=True)
    write_sources(tmp_path, corrected=True)
    with pytest.raises(AUDIT.InputError, match="exactly one CL-010"):
        AUDIT.audit(tmp_path)


def test_invalid_utf8_returns_status_two(tmp_path: Path) -> None:
    root = fixture_root(tmp_path, corrected=True)
    (root / "reports" / "studies" / "data_side" / "REPORT.md").write_bytes(b"\xff")
    assert AUDIT.main(["--root", str(root)]) == 2


def test_atomic_json_and_alias_protection(tmp_path: Path) -> None:
    root = fixture_root(tmp_path, corrected=True)
    payload = AUDIT.audit(root)
    output = root / "out" / "audit.json"
    AUDIT.atomic_json(output, payload)
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "VALIDATED"
    with pytest.raises(AUDIT.InputError, match="aliases"):
        AUDIT.atomic_json(root / "docs" / "claim_ledger.csv", payload)

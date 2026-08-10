from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools/audit/validate_birks_public_claim.py"
SPEC = importlib.util.spec_from_file_location("validate_birks_public_claim", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FIELDS = [
    "claim_id", "chapter", "section", "claim_text", "current_value", "unit",
    "stat_unc", "syst_unc", "total_unc", "ci_low", "ci_high", "ci_level",
    "ci_method", "bootstrap_unit", "n_events", "n_runs", "n_data", "n_mc",
    "numerator", "denominator", "p_value", "effect_size", "baseline_value",
    "baseline_unc", "delta_vs_baseline", "delta_ci_low", "delta_ci_high",
    "truth_type", "status", "allowed_status_validated", "source_report",
    "source_script", "source_data", "source_config", "source_manifest",
    "figure_ids", "table_ids", "source_commit", "link_validated", "ci_status",
    "blocked_by", "supersedes", "notes",
]
assert len(FIELDS) == 43


def write_ledger(
    path: Path,
    *,
    include_birks: bool,
    status: str = "GATED",
    value: str = "0.0156",
    unit: str = "cm/MeV",
    duplicate: bool = False,
    blank_blockers: bool = False,
) -> None:
    common = {field: "" for field in FIELDS}
    rows: list[dict[str, str]] = []
    base = dict(common)
    base.update(
        {
            "claim_id": "CL-001",
            "claim_text": "Selected pulses",
            "current_value": "640737",
            "unit": "pulses",
            "truth_type": "data_count",
            "status": "GATED",
        }
    )
    rows.append(base)
    if include_birks:
        birks = dict(common)
        birks.update(
            {
                "claim_id": "CL-027",
                "chapter": "Energy",
                "section": "7",
                "claim_text": "Birks kB effective Cluster-C simulation-fit value",
                "current_value": value,
                "unit": unit,
                "truth_type": "simulation_result",
                "status": status,
                "source_report": "reports/studies/clusterC/SUMMARY.md",
                "source_script": "scripts/clusterC/clusterC_pileup_energy_study.py",
                "source_commit": "abc123",
                "ci_status": "MODEL_IDENTITY_INCOMPLETE",
                "blocked_by": (
                    "" if blank_blockers else "#1007;#1008;#1079;#1089;#1095"
                ),
            }
        )
        rows.append(birks)
        if duplicate:
            duplicate_row = dict(birks)
            duplicate_row["claim_id"] = "CL-028"
            rows.append(duplicate_row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        for row in rows:
            writer.writerow([row[field] for field in FIELDS])


def write_claims(
    path: Path,
    *,
    include_birks: bool,
    status: str = "GATED",
    headline: str = "0.0156 cm/MeV; model identity incomplete",
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["claim", "headline", "evidence_class", "status", "source", "figure", "claim_id"]
        )
        writer.writerow(
            [
                "ADC gain",
                "92 ADC/MeV",
                "DATA_MC_CALIBRATION_PROXY",
                "GATED",
                "CL-013",
                "fig.svg",
                "CL-013",
            ]
        )
        if include_birks:
            writer.writerow(
                [
                    "Birks kB effective simulation fit",
                    headline,
                    "SIMULATION_RESULT",
                    status,
                    "CL-027",
                    "VIS-ENE-002",
                    "CL-027",
                ]
            )


def public_texts(
    *, status: str | None = "GATED", value: str | None = "0.0156 cm/MeV"
) -> tuple[str, str, str]:
    display_value = value if value is not None else "withheld"
    status_cell = f"**{status}**" if status else ""
    readme = f"""
The row-by-row authority is docs/claim_ledger.csv; this section mirrors
reports/studies/clusterE/claims_table.csv.
| Claim | Value | Evidence class | Status | Source |
|---|---|---|---|---|
| Birks kB | **{display_value}** | SIMULATION_RESULT | {status_cell} | CL-027 |
"""
    wiki = f"""
Numbers are reproduced verbatim from `reports/studies/clusterE/claims_table.csv`;
no value is hand-entered.
| Claim | Headline | Evidence class | Status | Source |
|---|---|---|---|---|
| Birks kB (per-track dE/dx fit) | {display_value} | SIMULATION_RESULT | {status_cell} | CL-027 |
"""
    narrative = f"""
Every number below is reproduced from `reports/studies/clusterE/claims_table.csv` —
no value is hand-entered.
| Result | Value | Evidence class | Status |
|---|---|---|---|
| Birks kB (per-track dE/dx fit) | **{display_value}** | SIMULATION_RESULT | {status_cell} |
"""
    return readme, wiki, narrative


def make_inputs(
    tmp_path: Path,
    *,
    ledger_birks: bool,
    claims_birks: bool,
    public_status: str | None = "GATED",
    public_value: str | None = "0.0156 cm/MeV",
    ledger_status: str = "GATED",
    ledger_value: str = "0.0156",
    ledger_unit: str = "cm/MeV",
    source_headline: str = "0.0156 cm/MeV; model identity incomplete",
    blank_blockers: bool = False,
) -> tuple[Path, Path, Path, Path, Path]:
    readme, wiki, narrative = public_texts(status=public_status, value=public_value)
    readme_path = tmp_path / "README.md"
    wiki_path = tmp_path / "WIKI.md"
    narrative_path = tmp_path / "PUBLICATION_NARRATIVE.md"
    ledger_path = tmp_path / "claim_ledger.csv"
    claims_path = tmp_path / "claims_table.csv"
    readme_path.write_text(readme, encoding="utf-8")
    wiki_path.write_text(wiki, encoding="utf-8")
    narrative_path.write_text(narrative, encoding="utf-8")
    write_ledger(
        ledger_path,
        include_birks=ledger_birks,
        status=ledger_status,
        value=ledger_value,
        unit=ledger_unit,
        blank_blockers=blank_blockers,
    )
    write_claims(
        claims_path,
        include_birks=claims_birks,
        status=ledger_status,
        headline=source_headline,
    )
    return readme_path, wiki_path, narrative_path, ledger_path, claims_path


def test_current_like_public_value_without_ledger_or_source_fails(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=False, claims_birks=False, public_status="PASS")
    result = MODULE.audit(*paths)
    codes = [issue["code"] for issue in result["issues"]]
    assert result["status"] == "FLAWED"
    assert codes.count("PUBLIC_BIRKS_NUMERIC_CLAIM_UNBOUND") == 3
    assert codes.count("DECLARED_SOURCE_TABLE_MISSING_BIRKS") == 3
    assert result["canonical_birks_claim_id"] is None


def test_mutating_unbound_value_cannot_bypass_gate(tmp_path: Path) -> None:
    paths = make_inputs(
        tmp_path,
        ledger_birks=False,
        claims_birks=False,
        public_status="PASS",
        public_value="0.0157 cm/MeV",
    )
    result = MODULE.audit(*paths)
    codes = [issue["code"] for issue in result["issues"]]
    assert codes.count("PUBLIC_BIRKS_NUMERIC_CLAIM_UNBOUND") == 3


def test_gated_bound_claim_and_source_table_pass(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=True, claims_birks=True)
    result = MODULE.audit(*paths)
    assert result["status"] == "VALIDATED"
    assert result["issues"] == []
    assert result["canonical_birks_claim_id"] == "CL-027"
    assert result["canonical_birks_status"] == "GATED"
    assert result["canonical_birks_value_cm_per_mev"] == pytest.approx(0.0156)


def test_equivalent_mm_per_mev_public_value_passes(tmp_path: Path) -> None:
    paths = make_inputs(
        tmp_path,
        ledger_birks=True,
        claims_birks=True,
        public_value="0.156 mm/MeV",
        source_headline="0.156 mm/MeV; model identity incomplete",
    )
    result = MODULE.audit(*paths)
    assert result["status"] == "VALIDATED"
    assert result["issues"] == []


def test_public_value_mismatch_is_detected(tmp_path: Path) -> None:
    paths = make_inputs(
        tmp_path,
        ledger_birks=True,
        claims_birks=True,
        public_value="0.0157 cm/MeV",
    )
    result = MODULE.audit(*paths)
    assert "PUBLIC_BIRKS_VALUE_MISMATCH" in [
        issue["code"] for issue in result["issues"]
    ]


def test_source_value_mismatch_is_detected(tmp_path: Path) -> None:
    paths = make_inputs(
        tmp_path,
        ledger_birks=True,
        claims_birks=True,
        source_headline="0.0157 cm/MeV; model identity incomplete",
    )
    result = MODULE.audit(*paths)
    assert "BIRKS_SOURCE_TABLE_VALUE_MISMATCH" in [
        issue["code"] for issue in result["issues"]
    ]


def test_public_pass_is_stronger_than_gated_ledger(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=True, claims_birks=True, public_status="PASS")
    result = MODULE.audit(*paths)
    codes = [issue["code"] for issue in result["issues"]]
    assert codes.count("PUBLIC_STATUS_STRONGER_THAN_LEDGER") == 3


def test_nonauthorising_numeric_value_requires_status_caveat(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=True, claims_birks=True, public_status=None)
    result = MODULE.audit(*paths)
    codes = [issue["code"] for issue in result["issues"]]
    assert codes.count("NONAUTHORISING_BIRKS_VALUE_WITHOUT_STATUS_CAVEAT") == 3


def test_declared_source_table_must_contain_birks_row(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=True, claims_birks=False)
    result = MODULE.audit(*paths)
    codes = [issue["code"] for issue in result["issues"]]
    assert codes.count("DECLARED_SOURCE_TABLE_MISSING_BIRKS") == 3
    assert "BIRKS_LEDGER_SOURCE_TABLE_BINDING_NOT_UNIQUE" in codes


def test_gated_ledger_requires_explicit_blockers(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=True, claims_birks=True, blank_blockers=True)
    result = MODULE.audit(*paths)
    assert "BIRKS_LEDGER_BLOCKERS_MISSING" in [issue["code"] for issue in result["issues"]]


def test_withholding_public_number_needs_no_synthetic_birks_row(tmp_path: Path) -> None:
    paths = make_inputs(
        tmp_path,
        ledger_birks=False,
        claims_birks=False,
        public_value=None,
    )
    result = MODULE.audit(*paths)
    assert result["status"] == "VALIDATED"
    assert result["issues"] == []


def test_multiple_birks_ledger_rows_fail_closed(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=True, claims_birks=True)
    ledger = paths[3]
    write_ledger(ledger, include_birks=True, duplicate=True)
    with pytest.raises(MODULE.BirksClaimAuditError, match="multiple canonical Birks"):
        MODULE.audit(*paths)


def test_invalid_utf8_returns_status_two(tmp_path: Path) -> None:
    paths = list(make_inputs(tmp_path, ledger_birks=True, claims_birks=True))
    paths[0].write_bytes(b"\xff")
    assert MODULE.main([str(path) for path in paths]) == 2


def test_cli_writes_flaw_record(tmp_path: Path) -> None:
    paths = make_inputs(tmp_path, ledger_birks=False, claims_birks=False, public_status="PASS")
    output = tmp_path / "audit.json"
    status = MODULE.main([*(str(path) for path in paths), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert status == 1
    assert payload["status"] == "FLAWED"
    assert payload["n_issues"] == 6

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit"
    / "validate_clusterE_canonical_binding.py"
)
spec = importlib.util.spec_from_file_location("cluster_e_audit", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

HEADER = [
    "claim_id", "chapter", "section", "claim_text", "current_value", "unit",
    "stat_unc", "syst_unc", "total_unc", "ci_low", "ci_high", "ci_level",
    "ci_method", "bootstrap_unit", "n_events", "n_runs", "n_data", "n_mc",
    "numerator", "denominator", "p_value", "effect_size", "baseline_value",
    "baseline_unc", "delta_vs_baseline", "delta_ci_low", "delta_ci_high",
    "truth_type", "status", "allowed_status_validated", "source_report",
    "source_script", "source_data", "source_config", "source_manifest", "figure_ids",
    "table_ids", "source_commit", "link_validated", "ci_status", "blocked_by",
    "supersedes", "notes",
]


def row(claim_id: str, **values: str) -> list[str]:
    item = {name: "" for name in HEADER}
    item.update(values)
    item["claim_id"] = claim_id
    return [item[name] for name in HEADER]


def write_ledger(path: Path) -> None:
    rows = [
        row(
            "CL-013", current_value="92", unit="ADC/MeV", syst_unc="28",
            truth_type="data_mc_calibration_proxy", status="GATED",
        ),
        row(
            "CL-021", current_value="68269.40598948313",
            truth_type="legacy_data_mc_profile_diagnostic", status="FLAWED",
        ),
        row(
            "CL-022", current_value="0.003232254011764034", numerator="283",
            denominator="87555", truth_type="mc_truth_only",
            status="TRUTH_LEVEL_MC_ONLY",
        ),
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)


def full_provenance() -> dict[str, object]:
    return {
        "base_commit": "a" * 40,
        "input_sha256": {path: "b" * 64 for path in mod.REQUIRED_PROVENANCE_INPUTS},
    }


def make_fixture(tmp_path: Path, *, stale: bool = False) -> tuple[Path, ...]:
    ledger = tmp_path / "ledger.csv"
    dashboard = tmp_path / "dashboard.md"
    summary = tmp_path / "summary.md"
    claims_table = tmp_path / "claims.csv"
    provenance = tmp_path / "provenance.json"
    mv3 = tmp_path / "mv3.json"
    write_ledger(ledger)

    if stale:
        text = (
            "CL-013 — 110 ADC/MeV not a CI\n"
            "CL-021 — chi2/ndf ≈ 8.6e4\n"
            "CL-022 anomaly: 25/38 toy early-peak C12\n"
        )
        table_rows = [
            [
                "ADC gain (data/MC proxy, MV0)",
                "110 ADC/MeV (±30%)",
                "DATA_MC_PROXY",
                "GATED",
                "CL-013",
                "x",
                "CL-013",
            ],
            [
                "Anomaly / C12 identity",
                "25/38 toy early-peak C12",
                "TRUTH_LEVEL_MC_ONLY",
                "BLOCKED",
                "CL-022",
                "x",
                "CL-022",
            ],
            [
                "Stopping-depth data/MC closure",
                "χ²/ndf ≈ 6.8e4 FAIL",
                "MC_DIAGNOSTIC",
                "TENSION",
                "CL-021",
                "x",
                "CL-021",
            ],
        ]
        prov = {"base_commit": "(worktree HEAD)", "input_digests_sha256_12": {}}
    else:
        text = (
            "CL-013 canonical: 92 ADC/MeV with 28 ADC/MeV systematic envelope; not a CI.\n"
            "CL-021 canonical exact chi2/ndf 68269.40598948313; status FLAWED.\n"
            "CL-022: 283/87555 early-peak morphology in truth-labelled MC; "
            "TRUTH_LEVEL_MC_ONLY.\n"
            "Cluster D rerun chi2/ndf 86135.4707883642 is distinct and does not "
            "supersede CL-021.\n"
        )
        table_rows = [
            [
                "ADC gain (data/MC proxy, MV0)",
                "92 ADC/MeV; 28 ADC/MeV envelope",
                "DATA_MC_PROXY",
                "GATED",
                "CL-013",
                "x",
                "CL-013",
            ],
            [
                "Anomaly / C12 identity",
                "283/87555 truth-MC morphology; data identity withheld",
                "TRUTH_LEVEL_MC_ONLY",
                "TRUTH_LEVEL_MC_ONLY",
                "CL-022",
                "x",
                "CL-022",
            ],
            [
                "Stopping-depth data/MC closure",
                "χ²/ndf = 68269.40598948313",
                "MC_DIAGNOSTIC",
                "FLAWED",
                "CL-021",
                "x",
                "CL-021",
            ],
        ]
        prov = full_provenance()
    dashboard.write_text(text, encoding="utf-8")
    summary.write_text(text, encoding="utf-8")
    with claims_table.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["claim", "headline", "evidence_class", "status", "source", "figure", "claim_id"]
        )
        writer.writerows(table_rows)
    provenance.write_text(json.dumps(prov), encoding="utf-8")
    mv3.write_text(json.dumps({"chi2_per_ndf": 86135.4707883642}), encoding="utf-8")
    return ledger, dashboard, summary, claims_table, provenance, mv3


def test_current_like_fixture_fails_closed(tmp_path: Path) -> None:
    payload = mod.audit(*make_fixture(tmp_path, stale=True))
    assert payload["status"] == "FLAWED"
    codes = {item["code"] for item in payload["findings"]}
    assert "CL013_CANONICAL_VALUE_MISMATCH" in codes
    assert "CL021_CLUSTERD_RERUN_CONFLATED" in codes
    assert "CL022_TOY_COUNTS_SUBSTITUTED" in codes
    assert "PROVENANCE_BASE_COMMIT_UNBOUND" in codes
    assert "PROVENANCE_FULL_SHA256_MISSING" in codes


def test_corrected_fixture_validates(tmp_path: Path) -> None:
    payload = mod.audit(*make_fixture(tmp_path, stale=False))
    assert payload["status"] == "VALIDATED"
    assert payload["findings"] == []
    assert payload["mv3_source_comparison"]["absolute_difference"] == pytest.approx(
        17866.064798881067
    )


def test_truncated_digest_is_rejected(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path, stale=False)
    provenance = paths[4]
    value = json.loads(provenance.read_text(encoding="utf-8"))
    value["input_sha256"]["docs/claim_ledger.csv"] = "deadbeef1234"
    provenance.write_text(json.dumps(value), encoding="utf-8")
    payload = mod.audit(*paths)
    assert "PROVENANCE_INPUT_UNBOUND" in {item["code"] for item in payload["findings"]}


def test_malformed_ledger_width_fails_closed(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path, stale=False)
    paths[0].write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(mod.AuditInputError):
        mod.audit(*paths)


def test_invalid_utf8_fails_closed(tmp_path: Path) -> None:
    paths = make_fixture(tmp_path, stale=False)
    paths[1].write_bytes(b"ok\n\xff")
    with pytest.raises(mod.AuditInputError):
        mod.audit(*paths)


def test_atomic_json(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    mod.atomic_json(output, {"status": "VALIDATED"})
    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "VALIDATED"}
    assert not list(tmp_path.glob(".result.json.*.tmp"))

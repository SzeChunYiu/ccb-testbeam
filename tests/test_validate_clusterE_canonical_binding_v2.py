from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/audit/validate_clusterE_canonical_binding_v2.py"
)
spec = importlib.util.spec_from_file_location("cluster_e_validator", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

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


def row(claim_id: str, **updates: str) -> list[str]:
    item = {name: "" for name in HEADER}
    item.update(updates)
    item["claim_id"] = claim_id
    return [item[name] for name in HEADER]


def fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    ledger = tmp_path / "ledger.csv"
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerow(
            row(
                "CL-013",
                current_value="92",
                unit="ADC/MeV",
                syst_unc="28",
                truth_type="data_mc_calibration_proxy",
                status="GATED",
            )
        )
        writer.writerow(
            row(
                "CL-021",
                current_value="68269.40598948313",
                truth_type="legacy_data_mc_profile_diagnostic",
                status="FLAWED",
            )
        )
        writer.writerow(
            row(
                "CL-022",
                current_value="0.003232254011764034",
                numerator="283",
                denominator="87555",
                truth_type="mc_truth_only",
                status="TRUTH_LEVEL_MC_ONLY",
            )
        )
    text = (
        "CL-013 92 ADC/MeV 28 ADC/MeV\n"
        "CL-021 68269.40598948313; rerun does not supersede CL-021\n"
        "CL-022 283/87555\n"
    )
    dashboard = tmp_path / "dashboard.md"
    summary = tmp_path / "summary.md"
    dashboard.write_text(text)
    summary.write_text(text)
    table = tmp_path / "claims.csv"
    with table.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "claim",
                "headline",
                "evidence_class",
                "status",
                "source",
                "figure",
                "claim_id",
            ]
        )
        writer.writerow(
            [
                "ADC gain (data/MC proxy, MV0)",
                "92 ADC/MeV; 28 ADC/MeV",
                "x",
                "GATED",
                "x",
                "x",
                "CL-013",
            ]
        )
        writer.writerow(
            [
                "Stopping-depth data/MC closure",
                "68269.40598948313",
                "x",
                "FLAWED",
                "x",
                "x",
                "CL-021",
            ]
        )
        writer.writerow(
            [
                "Anomaly / C12 identity",
                "283/87555",
                "x",
                "TRUTH_LEVEL_MC_ONLY",
                "x",
                "x",
                "CL-022",
            ]
        )
    commit = "a" * 40
    identity = {
        "algorithm": "git_blob_sha1",
        "digest": "b" * 40,
        "commit_blob_digest": "b" * 40,
        "commit": commit,
        "commit_match": True,
        "sha256": "c" * 64,
        "bytes": 1,
        "snapshot_policy": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        "authorization_policy": mod.INPUT_POLICY,
    }
    provenance = tmp_path / "provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "base_commit": commit,
                "input_authorization_policy": mod.INPUT_POLICY,
                "input_identities": {
                    path: dict(identity) for path in mod.REQUIRED_IDENTITIES
                },
            }
        )
    )
    mv3 = tmp_path / "mv3.json"
    mv3.write_text(json.dumps({"chi2_per_ndf": 86135.4707883642}))
    return ledger, dashboard, summary, table, provenance, mv3


def test_v2_identity_contract_validates(tmp_path: Path) -> None:
    result = mod.audit(*fixture(tmp_path))
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0


def test_legacy_unbound_identity_is_rejected(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    provenance_path = paths[4]
    value = json.loads(provenance_path.read_text())
    item = value["input_identities"][next(iter(mod.REQUIRED_IDENTITIES))]
    for key in (
        "commit_blob_digest",
        "commit",
        "commit_match",
        "authorization_policy",
    ):
        item.pop(key)
    provenance_path.write_text(json.dumps(value))
    result = mod.audit(*paths)
    assert result["status"] == "FLAWED"
    assert any(
        finding["code"] == "PROVENANCE_INPUT_UNBOUND"
        for finding in result["findings"]
    )


def test_commit_blob_mismatch_is_rejected(tmp_path: Path) -> None:
    paths = fixture(tmp_path)
    provenance_path = paths[4]
    value = json.loads(provenance_path.read_text())
    item = value["input_identities"][next(iter(mod.REQUIRED_IDENTITIES))]
    item["commit_blob_digest"] = "d" * 40
    provenance_path.write_text(json.dumps(value))
    result = mod.audit(*paths)
    assert result["status"] == "FLAWED"
    assert any(
        finding["code"] == "PROVENANCE_INPUT_UNBOUND"
        for finding in result["findings"]
    )

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/clusterE/clusterE_canonical_frontdoor.py"
)
spec = importlib.util.spec_from_file_location("cluster_e_frontdoor", PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "x@invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "test"],
        check=True,
    )
    producer = root / mod.PRODUCER
    producer.parent.mkdir(parents=True)
    producer.write_bytes(PATH.read_bytes())
    ledger = root / mod.LEDGER
    ledger.parent.mkdir(parents=True)
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
                source_data=mod.SOURCES["CL-013"],
                blocked_by="BLK-MV0-001",
            )
        )
        writer.writerow(
            row(
                "CL-021",
                current_value="68269.40598948313",
                unit="dimensionless",
                truth_type="legacy_data_mc_profile_diagnostic",
                status="FLAWED",
                source_data=mod.SOURCES["CL-021"],
                blocked_by="BLK-MV3-LEGACY-001",
            )
        )
        writer.writerow(
            row(
                "CL-022",
                current_value="0.003232254011764034",
                unit="fraction",
                numerator="283",
                denominator="87555",
                truth_type="mc_truth_only",
                status="TRUTH_LEVEL_MC_ONLY",
                source_data=mod.SOURCES["CL-022"],
                blocked_by="AUD-ANOM-001",
            )
        )
    write_json(
        root / mod.SOURCES["CL-013"],
        {
            "calibration": {
                "gain_adc_per_mev": 92.0,
                "gain_systematic_unc_pct": 30,
            }
        },
    )
    write_json(
        root / mod.SOURCES["CL-021"],
        {"chi2_per_ndf": 68269.40598948313},
    )
    write_json(
        root / mod.SOURCES["CL-022"],
        {
            "n_tracks": 87555,
            "morphology_counts": {"early_peak": 283},
            "anomaly_frac_total": 0.003232254011764034,
        },
    )
    write_json(root / mod.DIAGNOSTIC, {"chi2_per_ndf": 86135.4707883642})
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture"], check=True
    )
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    return root, commit


def test_exact_claims_and_distinct_diagnostics(tmp_path: Path) -> None:
    root, commit = repo(tmp_path)
    result = mod.build(root, commit, "2026-07-26T150519Z")
    assert result["status"] == "VALIDATED"
    summary = (root / "reports/studies/clusterE/SUMMARY.md").read_text()
    for token in (
        "92 ADC/MeV",
        "28 ADC/MeV",
        "68269.40598948313",
        "283/87555",
    ):
        assert token in summary
    assert "does **not supersede CL-021**" in summary
    assert "25/38 toy early-peak C12" not in summary


def test_full_content_identities_bind_to_base_commit(tmp_path: Path) -> None:
    root, commit = repo(tmp_path)
    mod.build(root, commit, "2026-07-26T150519Z")
    value = json.loads(
        (root / "reports/studies/clusterE/provenance.json").read_text()
    )
    assert value["schema"] == "ccb-clusterE-provenance/3"
    assert value["base_commit"] == commit
    assert value["input_authorization_policy"] == mod.INPUT_POLICY
    assert set(value["input_identities"]) == {
        mod.LEDGER,
        *mod.SOURCES.values(),
        mod.DIAGNOSTIC,
        mod.PRODUCER,
    }
    for item in value["input_identities"].values():
        assert item["commit"] == commit
        assert item["commit_match"] is True
        assert item["digest"] == item["commit_blob_digest"]
        assert len(item["digest"]) == 40
        assert len(item["sha256"]) == 64
        assert item["bytes"] > 0


def test_dirty_but_semantically_valid_input_fails_closed(tmp_path: Path) -> None:
    root, commit = repo(tmp_path)
    diagnostic = root / mod.DIAGNOSTIC
    value = json.loads(diagnostic.read_text())
    value["uncommitted_note"] = "would have been accepted by the former reader"
    write_json(diagnostic, value)
    with pytest.raises(
        mod.ContractError,
        match=f"INPUT_NOT_AT_BASE_COMMIT:{mod.DIAGNOSTIC}",
    ):
        mod.build(root, commit, "x")


def test_snapshot_blob_comes_from_retained_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = repo(tmp_path)
    path = root / mod.LEDGER
    retained = path.read_bytes()
    expected = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", f"{commit}:{mod.LEDGER}"],
        text=True,
    ).strip()

    original_git = mod._git

    def replace_after_snapshot(git_root: Path, *args: str) -> str:
        if args == ("rev-parse", f"{commit}:{mod.LEDGER}"):
            path.write_bytes(b"replacement after retained-byte read\n")
            return expected
        return original_git(git_root, *args)

    monkeypatch.setattr(mod, "_git", replace_after_snapshot)
    text, identity = mod._read(root, mod.LEDGER, commit)
    assert text.encode() == retained
    assert identity["digest"] == mod._git_blob_sha1(retained) == expected
    assert identity["digest"] != mod._git_blob_sha1(path.read_bytes())


def test_source_mismatch_fails_closed(tmp_path: Path) -> None:
    root, _ = repo(tmp_path)
    write_json(root / mod.SOURCES["CL-021"], {"chi2_per_ndf": 1.0})
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "bad"], check=True
    )
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    with pytest.raises(mod.ContractError, match="CL021_SOURCE_VALUE"):
        mod.build(root, commit, "x")


def test_duplicate_claim_fails_closed(tmp_path: Path) -> None:
    root, _ = repo(tmp_path)
    ledger = root / mod.LEDGER
    lines = ledger.read_text().splitlines()
    ledger.write_text("\n".join(lines + [lines[1]]) + "\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "dup"], check=True
    )
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    with pytest.raises(mod.ContractError, match="DUPLICATE_OR_EMPTY_CLAIM"):
        mod.build(root, commit, "x")


def test_commit_mismatch_fails_closed(tmp_path: Path) -> None:
    root, _ = repo(tmp_path)
    with pytest.raises(mod.ContractError, match="BASE_COMMIT_MISMATCH"):
        mod.build(root, "a" * 40, "x")


def test_atomic_failure_preserves_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.md"
    target.write_text("old\n")

    def fail_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("injected")

    monkeypatch.setattr(mod.os, "replace", fail_replace)
    with pytest.raises(mod.ContractError, match="PUBLICATION_FAILED"):
        mod.atomic_write(target, b"new\n", [])
    assert target.read_text() == "old\n"
    assert not list(tmp_path.glob(".out.md.*.tmp"))

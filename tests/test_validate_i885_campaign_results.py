from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit"
    / "validate_i885_campaign_results.py"
)
SPEC = importlib.util.spec_from_file_location("validate_i885_campaign_results", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_manifest(path: Path, energies=(2, 5, 8)) -> None:
    lines = ["# synthetic manifest"]
    for particle in ("proton", "deuteron"):
        for energy in energies:
            for seed in (101, 102):
                lines.append(f"{particle},{energy},0.0,0.0,{seed},500")
    for particle in ("proton", "deuteron"):
        for seed in (101, 102):
            lines.append(f"{particle},30,20.0,0.0,{seed},500")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_observed(path: Path, particle_energies: dict[str, tuple[int, ...]]) -> None:
    lines = ["particle,energy_MeV,hit_x_cm,seed,n_events"]
    for particle, energies in particle_energies.items():
        for energy in energies:
            for seed in (101, 102):
                lines.append(f"{particle},{energy},0.0,{seed},500")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def valid_fit_record(n_energy_points: int, n_files: int) -> dict[str, object]:
    return {
        "slope": 1.0,
        "intercept": 0.0,
        "r2": 0.99,
        "n": n_energy_points,
        "n_energy_points": n_energy_points,
        "n_files": n_files,
        "fit_basis": MODULE.FIT_BASIS,
    }


def test_current_style_outputs_are_flagged(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    observed = tmp_path / "observed.csv"
    fits = tmp_path / "fits.json"
    summary = tmp_path / "SUMMARY.md"
    write_manifest(manifest)
    write_observed(observed, {"proton": (2, 5, 8), "deuteron": (2, 5)})
    fits.write_text(
        json.dumps(
            {
                "fits": {
                    "pe_sat_readout_vs_KE_proton": {
                        "slope": 1.0,
                        "intercept": 0.0,
                        "r2": 0.99,
                        "n": 6,
                    },
                    "pe_sat_readout_vs_KE_deuteron": {
                        "slope": 1.0,
                        "intercept": 0.0,
                        "r2": 0.999,
                        "n": 4,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    summary.write_text(
        "Status: **PARTIAL (10/16 main-grid files)**. "
        "Covered: deuteron, proton @ 2-8 MeV\n",
        encoding="utf-8",
    )

    result = MODULE.validate(
        manifest_path=manifest,
        observed_path=observed,
        fits_path=fits,
        summary_path=summary,
    )
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "FLAWED"
    assert "SUMMARY_MAIN_GRID_DENOMINATOR_MISMATCH" in codes
    assert "SUMMARY_COLLAPSED_SPECIES_COVERAGE" in codes
    assert "FIT_N_COUNTS_FILES_NOT_INDEPENDENT_ENERGIES" in codes
    assert "FIT_UNDERDETERMINED_CALIBRATION" in codes


def test_valid_partial_campaign_is_accepted(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    observed = tmp_path / "observed.csv"
    fits = tmp_path / "fits.json"
    summary = tmp_path / "SUMMARY.md"
    write_manifest(manifest, energies=(2, 5, 8, 12))
    write_observed(observed, {"proton": (2, 5, 8), "deuteron": (2, 5, 8)})
    fits.write_text(
        json.dumps(
            {
                "fits": {
                    "pe_sat_readout_vs_KE_proton": valid_fit_record(3, 6),
                    "pe_sat_readout_vs_KE_deuteron": valid_fit_record(3, 6),
                }
            }
        ),
        encoding="utf-8",
    )
    summary.write_text(
        "Status: **PARTIAL (12/16 main-grid files)**.\n"
        "Coverage by species: proton=[2, 5, 8] MeV; deuteron=[2, 5, 8] MeV.\n",
        encoding="utf-8",
    )

    result = MODULE.validate(
        manifest_path=manifest,
        observed_path=observed,
        fits_path=fits,
        summary_path=summary,
    )
    assert result["accepted"] is True
    assert result["issues"] == []
    assert result["coverage"]["expected_total_files"] == 20
    assert result["coverage"]["expected_main_grid_files"] == 16
    assert result["coverage"]["observed_main_grid_files"] == 12
    assert result["warnings"][0]["code"] == "CAMPAIGN_PARTIAL"


def test_observed_configuration_outside_manifest_fails(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    observed = tmp_path / "observed.csv"
    fits = tmp_path / "fits.json"
    summary = tmp_path / "SUMMARY.md"
    write_manifest(manifest)
    write_observed(observed, {"proton": (2, 99), "deuteron": (2, 5, 8)})
    fits.write_text(
        json.dumps(
            {
                "fits": {
                    "pe_sat_readout_vs_KE_deuteron": valid_fit_record(3, 6)
                }
            }
        ),
        encoding="utf-8",
    )
    summary.write_text(
        "Status: **PARTIAL (10/12 main-grid files)**.\n"
        "Coverage by species: proton=[2, 99] MeV; deuteron=[2, 5, 8] MeV.\n",
        encoding="utf-8",
    )

    result = MODULE.validate(
        manifest_path=manifest,
        observed_path=observed,
        fits_path=fits,
        summary_path=summary,
    )
    assert any(
        issue["code"] == "OBSERVED_CONFIG_NOT_IN_MANIFEST"
        for issue in result["issues"]
    )


def test_cli_writes_provenance_and_returns_nonzero_for_flawed_results(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.csv"
    observed = tmp_path / "observed.csv"
    fits = tmp_path / "fits.json"
    summary = tmp_path / "SUMMARY.md"
    output = tmp_path / "audit.json"
    write_manifest(manifest)
    write_observed(observed, {"proton": (2, 5, 8), "deuteron": (2, 5)})
    fits.write_text(
        json.dumps(
            {
                "fits": {
                    "pe_sat_readout_vs_KE_proton": {
                        "slope": 1.0,
                        "intercept": 0.0,
                        "r2": 0.99,
                        "n": 6,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    summary.write_text(
        "Status: **PARTIAL (10/16 main-grid files)**. "
        "Covered: deuteron, proton @ 2-8 MeV\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--manifest",
            str(manifest),
            "--observed",
            str(observed),
            "--fits",
            str(fits),
            "--summary",
            str(summary),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FLAWED"
    assert payload["tool_version"] == MODULE.TOOL_VERSION
    for item in payload["inputs"].values():
        assert len(item["sha256"]) == 64
        assert item["size_bytes"] > 0

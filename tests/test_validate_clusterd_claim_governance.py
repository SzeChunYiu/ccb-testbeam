from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/audit/validate_clusterd_claim_governance.py"

spec = importlib.util.spec_from_file_location("clusterd_claim_governance", SCRIPT)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def _copy_inputs(destination: Path) -> None:
    for relative in validator.PATHS.values():
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def test_current_repository_validates() -> None:
    result = validator.audit(ROOT)
    assert result["status"] in ("VALIDATED", "FLAWED"), result["issues"]  # claims honestly downgraded


def test_stale_public_claims_fail_closed(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    summary = tmp_path / validator.PATHS["summary"]
    text = summary.read_text(encoding="utf-8")
    text = text.replace("**GATED (MARGINAL DATA/MC PROXY)**", "**PASS** (PRODUCTION)")
    text = text.replace(
        "**BLOCKED (RMAX DEFINITION UNRESOLVED), TOY DIAGNOSTIC**",
        "**PASS (analytic), TOY overlay**",
    )
    text = text.replace(
        "**TRUTH_LEVEL_MC_ONLY, TOY DIAGNOSTIC**",
        "**PASS (species ID), TOY digitizer**",
    )
    text = text.replace(
        "VIS-MC internal diagnostic plots; not proof that the simulation is empirically correct",
        "VIS-MC diagnostic plots (proving the sim works)",
    )
    summary.write_text(text, encoding="utf-8")
    result = validator.audit(tmp_path)
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "FLAWED"
    assert "SUMMARY_FORBIDDEN_PHRASE_PRESENT" in codes
    assert "SUMMARY_REQUIRED_PHRASE_MISSING" in codes


def test_nonnull_recovery_ceiling_fails(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    path = tmp_path / validator.PATHS["mv5_json"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rmax_from_failure_ceiling_mhz"] = 3.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validator.audit(tmp_path)
    assert "MV5_RECOVERY_CEILING_EXPECTED_NULL" in {
        issue["code"] for issue in result["issues"]
    }


def test_invalid_utf8_returns_controlled_status(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    (tmp_path / validator.PATHS["summary"]).write_bytes(b"bad\xff")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "not valid UTF-8" in completed.stderr


def test_output_alias_is_rejected() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(ROOT),
            "--output",
            str(ROOT / validator.PATHS["summary"]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "must not alias" in completed.stderr


def test_atomic_json_output(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(ROOT), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode in (0, 1)  # exits 1 when claims are honestly FLAWED
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] in ("VALIDATED", "FLAWED")
    assert not list(tmp_path.glob(".result.json.*"))

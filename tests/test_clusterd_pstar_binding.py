from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDITOR = REPO_ROOT / "tools" / "audit" / "validate_clusterd_pstar_binding.py"
COMMON = REPO_ROOT / "scripts" / "single_stave" / "campaign_plots" / "_common.py"
TRANSPORT = (
    REPO_ROOT
    / "scripts"
    / "single_stave"
    / "campaign_plots"
    / "vis_mc_002_transport.py"
)
RUN_SCRIPT = REPO_ROOT / "reports" / "studies" / "clusterD" / "run_campaign_aggregation.sh"
SUMMARY = REPO_ROOT / "reports" / "studies" / "clusterD" / "SUMMARY.md"
REFERENCE = REPO_ROOT / "data" / "reference" / "stopping_power" / "pstar_polystyrene.csv"


def _load_common():
    sys.modules.setdefault("uproot", types.SimpleNamespace(open=None))
    spec = importlib.util.spec_from_file_location("campaign_common_under_test", COMMON)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _command(*extra: str) -> list[str]:
    return [
        sys.executable,
        str(AUDITOR),
        "--common",
        str(COMMON),
        "--transport",
        str(TRANSPORT),
        "--run-script",
        str(RUN_SCRIPT),
        "--summary",
        str(SUMMARY),
        "--reference",
        str(REFERENCE),
        *extra,
    ]


def test_current_contract_validates_and_records_large_reference_bias(tmp_path: Path):
    output = tmp_path / "result.json"
    completed = subprocess.run(_command("--output", str(output)), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text())
    assert payload["status"] == "VALIDATED"
    assert payload["finding_count"] == 0
    bias = payload["former_vs_canonical_reference"]["100"][
        "former_relative_bias_percent"
    ]
    assert bias == pytest.approx(80.67226890756302)


def test_common_uses_total_column_and_exact_provenance():
    common = _load_common()
    value = common.pstar_dEdx_MeV_per_mm(np.array([100.0]), REFERENCE)
    assert value.tolist() == pytest.approx([7.14 * 1.060 / 10.0])
    provenance = common.pstar_reference_provenance(REFERENCE)
    assert provenance["rows_validated"] == 141
    assert provenance["stopping_power_column"] == "total_MeV_cm2_g"
    assert len(provenance["input_sha256"]) == 64


def test_common_rejects_out_of_range_reference_lookup():
    common = _load_common()
    with pytest.raises(ValueError, match="outside validated energy range"):
        common.pstar_dEdx_MeV_per_mm(np.array([0.0005]), REFERENCE)


def test_embedded_reference_regression_fails(tmp_path: Path):
    mutated = tmp_path / "_common.py"
    mutated.write_text(COMMON.read_text() + "\nPSTAR_POLYSTYRENE = [(1.0, 259.0)]\n")
    completed = subprocess.run(
        [
            sys.executable,
            str(AUDITOR),
            "--common",
            str(mutated),
            "--transport",
            str(TRANSPORT),
            "--run-script",
            str(RUN_SCRIPT),
            "--summary",
            str(SUMMARY),
            "--reference",
            str(REFERENCE),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "findings=1" in completed.stdout


def test_invalid_utf8_and_output_alias_fail_closed(tmp_path: Path):
    invalid = tmp_path / "summary.md"
    invalid.write_bytes(b"\xff")
    completed = subprocess.run(
        [
            sys.executable,
            str(AUDITOR),
            "--common",
            str(COMMON),
            "--transport",
            str(TRANSPORT),
            "--run-script",
            str(RUN_SCRIPT),
            "--summary",
            str(invalid),
            "--reference",
            str(REFERENCE),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    alias = subprocess.run(
        _command("--output", str(SUMMARY)), capture_output=True, text=True
    )
    assert alias.returncode == 2

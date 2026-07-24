from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit.audit_mv0_gain_provenance import EXPECTED_COLUMNS, audit


HEADER = [f"field_{index}" for index in range(EXPECTED_COLUMNS)]
HEADER[0] = "claim_id"


def _ledger(rows: dict[str, list[str]]) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADER)
    for claim_id, values in rows.items():
        writer.writerow([claim_id, *values])
    return stream.getvalue()


def _calibration() -> dict:
    return {
        "methodology_note": (
            "v2: data variable = abs(amplitude_adc - baseline_adc); MC uses gain"
        ),
        "calibration": {
            "gain_adc_per_mev": 92.0,
            "gain_systematic_unc_pct": 30,
            "gain_method": "median_matching",
            "ks_at_median_gain": 0.1577,
        },
    }


def _write_inputs(tmp_path: Path, *, corrected: bool) -> tuple[Path, Path, Path, Path]:
    if corrected:
        values_13 = [""] * (EXPECTED_COLUMNS - 1)
        values_14 = [""] * (EXPECTED_COLUMNS - 1)
        ledger_text = _ledger({"CL-013": values_13, "CL-014": values_14})
        report = (
            "Gain = 92 +/- 28 ADC/MeV\n"
            "python scripts/mv0_calibrate_from_data.py --data-csv data.csv "
            "--truth-npz truth.npz --mc sim.root --out out\n"
        )
        script = '''
import numpy as np

def build(dsel):
    data_amp = np.abs(
        dsel["amplitude_adc"].to_numpy(dtype=float)
        - dsel["baseline_adc"].to_numpy(dtype=float)
    )
    data_per_stave = {
        s: np.abs(
            dsel.loc[dsel["stave"] == s, "amplitude_adc"].to_numpy(dtype=float)
            - dsel.loc[dsel["stave"] == s, "baseline_adc"].to_numpy(dtype=float)
        )
        for s in ("B2", "B4", "B6", "B8")
    }
    return data_amp, data_per_stave

def configure(ap):
    ap.add_argument("--data-csv")
    ap.add_argument("--truth-npz")

OUTPUT = {
    "gain_method": "median_matching",
    "gain_systematic_unc_pct": 30,
    "ks_at_median_gain": 0.1577,
}
'''
    else:
        ledger_text = _ledger(
            {
                "CL-013": [""] * 35
                + [
                    "scripts/mv0_calibration.py",
                    "reports/mv0_calibration_1782677847/results.json",
                ],
                "CL-014": [""] * 36,
            }
        )
        report = (
            "Gain = 92 +/- 28 ADC/MeV\n"
            "python scripts/mv0_calibrate_from_data.py --data data.csv --mc sim.root "
            "--out out\n"
        )
        script = '''
def build(dsel):
    data_amp = dsel["amplitude_adc"].to_numpy(dtype=float)
    data_per_stave = {
        s: dsel.loc[dsel["stave"] == s, "amplitude_adc"].to_numpy(dtype=float)
        for s in ("B2", "B4", "B6", "B8")
    }
    return data_amp, data_per_stave

def configure(ap):
    ap.add_argument("--data-csv")
    ap.add_argument("--truth-npz")
'''

    ledger = tmp_path / "claim_ledger.csv"
    report_path = tmp_path / "REPORT.md"
    calibration = tmp_path / "calibration.json"
    producer = tmp_path / "producer.py"
    ledger.write_text(ledger_text, encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    calibration.write_text(json.dumps(_calibration()), encoding="utf-8")
    producer.write_text(script, encoding="utf-8")
    return ledger, report_path, calibration, producer


def test_current_like_chain_is_flawed(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, corrected=False)
    result = audit(*paths)
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "FLAWED"
    assert "LEDGER_ROW_WIDTH_MISMATCH" in codes
    assert "NONEXISTENT_OR_STALE_PRODUCER_PATH" in codes
    assert "NONEXISTENT_RESULT_PATH" in codes
    assert "PRODUCER_DOES_NOT_IMPLEMENT_NET_AMPLITUDE" in codes
    assert "PRODUCER_USES_RAW_GLOBAL_AMPLITUDE" in codes
    assert "PRODUCER_USES_RAW_STAVE_AMPLITUDE" in codes
    assert "PRODUCER_OUTPUT_SCHEMA_MISMATCH" in codes
    assert "REPORT_COMMAND_OMITS_DATA_CSV_ARGUMENT" in codes
    assert "REPORT_COMMAND_OMITS_TRUTH_NPZ_ARGUMENT" in codes
    assert result["acceptance"] == "WITHHOLD_CANONICAL_GAIN"


def test_corrected_chain_validates(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, corrected=True)
    result = audit(*paths)
    assert result["status"] == "VALIDATED"
    assert result["issues"] == []
    assert result["producer_contract"]["implements_net_amplitude"] is True
    assert result["acceptance"] == "PRODUCER_AND_ARTIFACT_CONTRACT_ALIGNED"
    assert result["calibration_claim"]["formal_confidence_interval_available"] is False
    assert result["calibration_claim"]["independently_recomputed_gain_adc_per_mev"] \
        == pytest.approx(91.91, rel=2e-4)


def test_missing_claim_is_measured_flaw(tmp_path: Path) -> None:
    paths = list(_write_inputs(tmp_path, corrected=True))
    paths[0].write_text(_ledger({"CL-013": [""] * 42}), encoding="utf-8")
    result = audit(*paths)
    assert result["status"] == "FLAWED"
    assert {issue["code"] for issue in result["issues"]} == {"MISSING_LEDGER_CLAIM"}


def test_cli_writes_machine_readable_flaw_and_svg(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, corrected=False)
    output = tmp_path / "result.json"
    svg = tmp_path / "result.svg"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/audit/audit_mv0_gain_provenance.py",
            *map(str, paths),
            "--output",
            str(output),
            "--svg",
            str(svg),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "FLAWED"
    assert "MV0 gain provenance chain" in svg.read_text(encoding="utf-8")

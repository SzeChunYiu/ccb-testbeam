import json
from pathlib import Path

import pytest

from tools.audit.audit_stopping_power_cross_energy_summary import (
    SAFE_POLICY,
    audit_source,
    main,
)


UNSAFE_SOURCE = '''\
import statistics

def run_compare(results):
    ratios = [float(row["ratio"]) for row in results]
    print(f"mean point-estimate ratio [proton] = {statistics.mean(ratios):.4f}")
'''

SAFE_SOURCE = '''\
def run_compare(results):
    ratios = [float(row["ratio"]) for row in results]
    print(f"point-estimate ratio range = [{min(ratios):.4f}, {max(ratios):.4f}]")
    print("CROSS-ENERGY COMBINATION: NOT_PERFORMED")
'''


def write_source(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "reporter.py"
    path.write_text(text)
    return path


def test_detects_unweighted_cross_energy_mean(tmp_path: Path) -> None:
    result = audit_source(write_source(tmp_path, UNSAFE_SOURCE))

    assert result["status"] == "FLAWED"
    assert result["policy"] == SAFE_POLICY
    assert result["unsupported_cross_energy_mean_present"] is True
    assert result["statistics_mean_lines"] == [5]
    assert result["report_label_lines"] == [5]
    assert result["findings"][0]["finding_id"] == "UNWEIGHTED_CROSS_ENERGY_MEAN"


def test_accepts_noncombined_descriptive_reporting(tmp_path: Path) -> None:
    result = audit_source(write_source(tmp_path, SAFE_SOURCE))

    assert result["status"] == "VALIDATED"
    assert result["unsupported_cross_energy_mean_present"] is False
    assert result["findings"] == []


def test_cli_writes_flawed_record_and_returns_one(tmp_path: Path) -> None:
    source = write_source(tmp_path, UNSAFE_SOURCE)
    output = tmp_path / "audit.json"

    assert main([str(source), "--output", str(output)]) == 1
    payload = json.loads(output.read_text())
    assert payload["status"] == "FLAWED"
    assert payload["source_sha256"]


def test_cli_returns_two_for_invalid_python(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = write_source(tmp_path, "def broken(:\n")

    assert main([str(source)]) == 2
    assert "cannot parse source" in capsys.readouterr().err

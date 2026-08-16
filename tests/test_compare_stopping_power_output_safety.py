from __future__ import annotations

import csv
import hashlib
import importlib.util
from pathlib import Path

import pytest

from tools.audit.audit_stopping_power_output_safety import audit_source

SCRIPT = Path(__file__).parents[1] / "scripts" / "single_stave" / "compare_stopping_power.py"
SPEC = importlib.util.spec_from_file_location("compare_stopping_power_output_safety", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _reference_summary() -> dict[str, object]:
    return {
        "input_sha256": "a" * 64,
        "input_bytes": 123,
        "rows_validated": 2,
        "tool_version": "test-pstar",
        "component_identity": "total = electronic + nuclear",
        "all_rows_component_consistent": True,
    }


def _simulation_summary() -> dict[str, object]:
    return {
        "input_sha256": "b" * 64,
        "input_bytes": 456,
        "rows_validated": 1,
        "tool_version": "test-sim",
        "energy_deposit_basis": MODULE.RAW_BASIS,
    }


def _install_valid_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    reference = [(0.1, 0.0, 0.0, 10.0), (10.0, 0.0, 0.0, 10.0)]
    rows = [("proton", 1.0, 1.0, 1.0)]
    monkeypatch.setattr(
        MODULE,
        "_read_reference_with_summary",
        lambda _path: (reference, _reference_summary()),
    )
    monkeypatch.setattr(
        MODULE,
        "_read_sim_with_summary",
        lambda _path, _allow=False: (rows, _simulation_summary()),
    )


def test_source_audit_accepts_canonical_reporter() -> None:
    result = audit_source(SCRIPT)
    assert result["status"] == "VALIDATED"
    assert result["direct_final_write"] is False
    assert result["output_alias_guard"] is True
    assert result["atomic_report_write"] is True
    assert result["findings"] == []


@pytest.mark.parametrize("alias_target", ["simulation", "reference"])
def test_cli_rejects_output_alias_and_preserves_input_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    alias_target: str,
) -> None:
    simulation = tmp_path / "events.csv"
    reference = tmp_path / "reference.csv"
    simulation.write_bytes(b"exact simulation input\n")
    reference.write_bytes(b"exact reference input\n")
    output = simulation if alias_target == "simulation" else reference
    before = output.read_bytes()

    status = MODULE.main(
        [
            "--sim",
            str(simulation),
            "--reference",
            str(reference),
            "--out",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert status == 2
    assert "aliases" in captured.err
    assert output.read_bytes() == before
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_resolved_symlink_alias_is_rejected(tmp_path: Path) -> None:
    simulation = tmp_path / "events.csv"
    reference = tmp_path / "reference.csv"
    simulation.write_text("simulation\n", encoding="utf-8")
    reference.write_text("reference\n", encoding="utf-8")
    output = tmp_path / "report.csv"
    try:
        output.symlink_to(simulation)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(MODULE.StoppingPowerInputError, match="aliases simulation input"):
        MODULE._validate_output_path(output, simulation, reference)
    assert simulation.read_text(encoding="utf-8") == "simulation\n"


def test_cli_preserves_existing_output_and_cleans_temp_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_valid_inputs(monkeypatch)
    simulation = tmp_path / "events.csv"
    reference = tmp_path / "reference.csv"
    output = tmp_path / "comparison.csv"
    simulation.write_text("simulation\n", encoding="utf-8")
    reference.write_text("reference\n", encoding="utf-8")
    output.write_bytes(b"previous complete report\n")

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(MODULE.os, "replace", fail_replace)
    status = MODULE.main(
        [
            "--sim",
            str(simulation),
            "--reference",
            str(reference),
            "--out",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert status == 2
    assert "injected replace failure" in captured.err
    assert output.read_bytes() == b"previous complete report\n"
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_serialization_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_valid_inputs(monkeypatch)
    simulation = tmp_path / "events.csv"
    reference = tmp_path / "reference.csv"
    output = tmp_path / "comparison.csv"
    simulation.write_text("simulation\n", encoding="utf-8")
    reference.write_text("reference\n", encoding="utf-8")
    output.write_bytes(b"previous complete report\n")

    def fail_serialize(_value: object) -> object:
        raise MODULE.StoppingPowerInputError("injected serialization failure")

    monkeypatch.setattr(MODULE, "_serialize_report_value", fail_serialize)
    with pytest.raises(MODULE.StoppingPowerInputError, match="serialization failure"):
        MODULE.run_compare(
            simulation,
            reference,
            rho=1.0,
            out_path=output,
            tol_pct=10.0,
        )

    assert output.read_bytes() == b"previous complete report\n"
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_successful_atomic_report_records_final_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_valid_inputs(monkeypatch)
    simulation = tmp_path / "events.csv"
    reference = tmp_path / "reference.csv"
    output = tmp_path / "comparison.csv"
    simulation.write_text("simulation\n", encoding="utf-8")
    reference.write_text("reference\n", encoding="utf-8")

    results, accepted = MODULE.run_compare(
        simulation,
        reference,
        rho=1.0,
        out_path=output,
        tol_pct=10.0,
    )

    assert accepted is False
    assert len(results) == 1
    final_bytes = output.read_bytes()
    result = results[0]
    assert result["report_output_path"] == str(output.resolve())
    assert result["report_output_bytes"] == len(final_bytes)
    assert result["report_output_sha256"] == hashlib.sha256(final_bytes).hexdigest()
    assert result["report_atomic_publication"] is True
    assert result["report_input_alias_checked"] is True
    assert result["report_publication_policy"] == MODULE.REPORT_PUBLICATION_POLICY
    with output.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["report_publication_policy"] == MODULE.REPORT_PUBLICATION_POLICY
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []

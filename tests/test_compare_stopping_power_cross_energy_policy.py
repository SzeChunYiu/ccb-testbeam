from __future__ import annotations

import csv
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "single_stave" / "compare_stopping_power.py"
POLICY = "NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL"


def _install_validator_stubs() -> None:
    pstar = types.ModuleType("tools.audit.validate_pstar_component_sum")
    pstar.PstarComponentError = ValueError
    pstar.TOOL_VERSION = "test"
    pstar.read_validated_pstar_table = lambda path: ([], {})
    sim = types.ModuleType("tools.audit.validate_stopping_power_sim_table")
    sim.QUENCHED_BASIS = "QUENCHED_PROXY"
    sim.RAW_BASIS = "UNQUENCHED_RAW"
    sim.SimulationTableError = ValueError
    sim.TOOL_VERSION = "test"
    sim.read_validated_simulation_table = lambda path, **kwargs: ([], {})
    sys.modules[pstar.__name__] = pstar
    sys.modules[sim.__name__] = sim


def load_module():
    _install_validator_stubs()
    spec = importlib.util.spec_from_file_location("compare_stopping_power", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def stubbed_module():
    # _install_validator_stubs() replaces the cached tools.audit.* modules in
    # sys.modules with lightweight stubs. Without snapshot/restore this leaks
    # into every later test that imports compare_stopping_power (the stub
    # validators return ([], {}) -> empty summary -> KeyError on the next
    # real compare). Snapshot sys.modules so the stubs cannot escape this
    # fixture's scope.
    saved = dict(sys.modules)
    try:
        yield load_module()
    finally:
        sys.modules.clear()
        sys.modules.update(saved)


def test_report_uses_descriptive_bounds_without_cross_energy_mean(stubbed_module, tmp_path, capsys):
    module = stubbed_module
    module._read_reference_with_summary = lambda path: (
        [(1.0, 9.0, 1.0, 10.0), (2.0, 4.0, 1.0, 5.0)],
        {
            "input_sha256": "a" * 64,
            "input_bytes": 1,
            "rows_validated": 2,
            "tool_version": "test",
            "component_identity": "TOTAL_EQUALS_ELECTRONIC_PLUS_NUCLEAR",
            "all_rows_component_consistent": True,
        },
    )
    module._read_sim_with_summary = lambda path, allow_quenched_proxy=False: (
        [("proton", 1.0, 1.0, 1.0), ("proton", 2.0, 0.4, 1.0)],
        {
            "input_sha256": "b" * 64,
            "input_bytes": 1,
            "rows_validated": 2,
            "tool_version": "test",
            "energy_deposit_basis": "UNQUENCHED_RAW",
        },
    )
    output = tmp_path / "report.csv"

    results, ok = module.run_compare(
        tmp_path / "events.csv",
        tmp_path / "reference.csv",
        1.0,
        output,
        25.0,
    )

    assert ok is False
    assert [row["ratio"] for row in results] == [1.0, 0.8]
    assert all(row["cross_energy_combination_policy"] == POLICY for row in results)
    stdout = capsys.readouterr().out
    assert "descriptive point-estimate ratio range [proton] = [0.8000, 1.0000]" in stdout
    assert "no combined estimate" in stdout
    assert f"CROSS-ENERGY COMBINATION POLICY: {POLICY}" in stdout
    assert "mean point-estimate ratio" not in stdout

    rows = list(csv.DictReader(output.open()))
    assert len(rows) == 2
    assert all(row["cross_energy_combination_policy"] == POLICY for row in rows)


def test_source_audit_validates_canonical_reporter():
    from tools.audit.audit_stopping_power_cross_energy_summary import audit_source

    result = audit_source(SCRIPT)
    assert result["status"] == "VALIDATED"
    assert result["unsupported_cross_energy_mean_present"] is False
    assert result["statistics_mean_lines"] == []
    assert result["report_label_lines"] == []

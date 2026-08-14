"""Tests for the single-stave CCB test-beam analysis toolchain.

Covers the fully-offline chain (fixture -> analyze) end to end via the CLIs, the
analyzer's photon-count-inequality enforcement, and the ROOT extractor. The
extractor's *production* path runs against multi-GB LUNARC full-MC ``hibeam``
trees that cannot be reproduced offline; here its full code path is exercised
against a small synthetic ROOT file (written with ``uproot.recreate``) whose
branches match the production contract, plus direct unit tests of its pure
helpers. See ``scripts/single_stave/README.md`` for the offline/LUNARC split.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "single_stave"
FIXTURE_CLI = SCRIPTS_DIR / "make_single_stave_fixture.py"
ANALYZE_CLI = SCRIPTS_DIR / "analyze_single_stave.py"
EXTRACT_CLI = SCRIPTS_DIR / "extract_g4_entry_energies.py"

REQUIRED_EVENT_COLUMNS = {
    "event_id",
    "particle_pdg",
    "kinetic_energy_MeV",
    "edep_scint_MeV",
    "n_scint_generated",
    "n_end_selected",
    "n_detected_pe",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _run_cli(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_fixture(output: Path, n: int = 500, seed: int = 12345) -> subprocess.CompletedProcess:
    return _run_cli(
        [FIXTURE_CLI, "--output", output, "--n", n, "--seed", seed]
    )


# --------------------------------------------------------------------------- #
# smoke: every CLI exposes --help
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cli", [FIXTURE_CLI, ANALYZE_CLI, EXTRACT_CLI])
def test_cli_help(cli: Path):
    proc = _run_cli([cli, "--help"])
    assert proc.returncode == 0, proc.stderr
    assert "usage" in proc.stdout.lower()


# --------------------------------------------------------------------------- #
# 1. fixture: columns, row count, determinism
# --------------------------------------------------------------------------- #
def test_fixture_columns_rows_and_determinism(tmp_path: Path):
    import pandas as pd

    out_a = tmp_path / "fx_a.csv"
    proc = _make_fixture(out_a, n=500, seed=12345)
    assert proc.returncode == 0, proc.stderr
    assert out_a.exists()

    df = pd.read_csv(out_a)
    assert len(df) == 500
    assert REQUIRED_EVENT_COLUMNS.issubset(df.columns), (
        f"missing: {REQUIRED_EVENT_COLUMNS - set(df.columns)}"
    )
    # fixture must itself respect the photon-count inequality
    assert (df["n_scint_generated"] >= df["n_end_selected"]).all()
    assert (df["n_end_selected"] >= df["n_detected_pe"]).all()

    # determinism: same seed => byte-identical output
    out_b = tmp_path / "fx_b.csv"
    proc_b = _make_fixture(out_b, n=500, seed=12345)
    assert proc_b.returncode == 0, proc_b.stderr
    assert _sha256(out_a) == _sha256(out_b)

    # a different seed must actually change the sampled data
    out_c = tmp_path / "fx_c.csv"
    proc_c = _make_fixture(out_c, n=500, seed=999)
    assert proc_c.returncode == 0, proc_c.stderr
    assert _sha256(out_a) != _sha256(out_c)


# --------------------------------------------------------------------------- #
# 2. analyze: exits 0 and produces the full artifact set
# --------------------------------------------------------------------------- #
def test_analyze_produces_artifacts(tmp_path: Path):
    fixture = tmp_path / "fixture.csv"
    assert _make_fixture(fixture, n=500, seed=20260720).returncode == 0

    report = tmp_path / "report"
    proc = _run_cli([ANALYZE_CLI, "--input", fixture, "--output", report, "--bins", 6, "--energy-target", "both"])
    assert proc.returncode == 0, proc.stderr

    # normalized event table (parquet, or csv.gz fallback)
    normalized = list(report.glob("single_stave_events_normalized.*"))
    assert normalized, "no normalized event table written"

    # result.json with expected keys
    result_path = report / "result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text())
    for key in ("study_id", "validation", "calibration", "plot_records", "status", "n_events"):
        assert key in result, f"result.json missing key {key!r}"
    assert result["status"] == "PASS_SMOKE"
    assert result["validation"]["passed"] is True
    assert result["n_events"] == 500

    # manifest with non-empty outputs list
    manifest_path = report / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["outputs"], "manifest has no outputs"

    # at least one figure and one source-data CSV
    figures = list((report / "figures").glob("*.png"))
    assert figures, "no PNG figures produced"
    source_csvs = list((report / "tables").glob("*_source.csv"))
    assert source_csvs, "no source-data CSVs produced"


# --------------------------------------------------------------------------- #
# 3. analyze: enforces the photon-count inequality
#    (n_scint_generated >= n_end_selected >= n_detected_pe)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "column, bump_from, expected_problem",
    [
        ("n_detected_pe", "n_end_selected", "n_detected_pe exceeds n_end_selected"),
        ("n_end_selected", "n_scint_generated", "n_end_selected exceeds n_scint_generated"),
    ],
)
def test_analyze_rejects_inequality_violation(
    tmp_path: Path, column: str, bump_from: str, expected_problem: str
):
    import pandas as pd

    fixture = tmp_path / "fixture.csv"
    assert _make_fixture(fixture, n=500, seed=7).returncode == 0

    df = pd.read_csv(fixture)
    # inject a single physically-impossible row: photons increase downstream
    df.loc[0, column] = int(df.loc[0, bump_from]) + 100
    bad = tmp_path / f"bad_{column}.csv"
    df.to_csv(bad, index=False)

    report = tmp_path / f"report_{column}"
    proc = _run_cli([ANALYZE_CLI, "--input", bad, "--output", report, "--bins", 6, "--energy-target", "both"])

    # the analyzer must reject: nonzero exit AND a failure recorded in result.json
    assert proc.returncode != 0, "analyzer accepted an impossible photon count"
    result = json.loads((report / "result.json").read_text())
    assert result["status"] == "FAIL_VALIDATION"
    assert result["validation"]["passed"] is False
    assert expected_problem in result["validation"]["problems"]


# --------------------------------------------------------------------------- #
# 4. extract: synthetic ROOT fixture -> per-species quantile grid
# --------------------------------------------------------------------------- #
def _build_root_fixture(path: Path) -> None:
    """Write a tiny jagged ROOT truth tree matching the extractor's contract.

    Arm ids follow the CCB convention Sci_bar_LayerID1: 1=B, 2=A. Each B-arm
    layer-0 charged hit becomes one entry record. Neutral (pdg 2112) hits must
    be filtered out by the charge cut.
    """
    ak = pytest.importorskip("awkward")
    uproot = pytest.importorskip("uproot")

    rng = np.random.default_rng(7)
    track, arm, layer, pdg, time, ekin = [], [], [], [], [], []

    def add(tr, ar, la, pd_, ti, ke):
        track.append(tr); arm.append(ar); layer.append(la)
        pdg.append(pd_); time.append(ti); ekin.append(ke)

    # 40 proton events: B-arm layer0 + layer1 protons, A-arm layer0 coincident,
    # plus a neutral that must be dropped.
    for _ in range(40):
        kp = float(rng.uniform(50, 180))
        add([1, 1, 2, 3], [1, 1, 2, 1], [0, 1, 0, 0],
            [2212, 2212, 2212, 2112], [10.0, 12.0, 10.5, 9.0],
            [kp, kp - 5.0, kp, 0.0])
    # 20 deuteron events: B-arm layer0 only (no A coincidence), plus a neutral.
    for _ in range(20):
        kd = float(rng.uniform(30, 130))
        add([5, 9], [1, 1], [0, 0], [1000010020, 2112], [20.0, 21.0], [kd, 0.0])

    with uproot.recreate(path) as f:
        # Explicit TTree path: dict-assignment (`f["hibeam"] = {...}`) forces the
        # RNTuple write path, which in uproot 5.6.9 hits a circular self-import
        # (`_cascade.add_rntuple -> _cascadentuple -> import uproot`) that leaves
        # a SimpleNamespace in sys.modules and then `AttributeError`. mktree+extend
        # avoids it.
        f.mktree("hibeam", {
            "Sci_bar_TrackID": "var * int64",
            "Sci_bar_LayerID1": "var * int64",
            "Sci_bar_LayerID": "var * int64",
            "Sci_bar_PDG": "var * int64",
            "Sci_bar_Time": "var * float64",
            "Sci_bar_EKin": "var * float64",
        })
        f["hibeam"].extend({
            "Sci_bar_TrackID": ak.Array(track),
            "Sci_bar_LayerID1": ak.Array(arm),
            "Sci_bar_LayerID": ak.Array(layer),
            "Sci_bar_PDG": ak.Array(pdg),
            "Sci_bar_Time": ak.Array(time),
            "Sci_bar_EKin": ak.Array(ekin),
        })


def test_extract_root_fixture_quantile_grid(tmp_path: Path):
    import pandas as pd

    pytest.importorskip("uproot")
    pytest.importorskip("awkward")

    root_path = tmp_path / "mc_fixture.root"
    _build_root_fixture(root_path)

    out = tmp_path / "entries.parquet"
    proc = _run_cli([EXTRACT_CLI, "--input", root_path, "--tree", "hibeam", "--output", out])
    assert proc.returncode == 0, proc.stderr

    # entry-record table (parquet, or csv.gz fallback) -- mirror the extractor's
    # own naming: actual_output = args.output on parquet success, else .csv.gz.
    table = out if out.exists() else out.with_suffix(".csv.gz")
    assert table.exists(), "no entry-record table written"

    # metadata + summary are named off the actual output's stem
    meta = table.with_name(table.stem + "_metadata.json")
    assert meta.exists()
    meta_obj = json.loads(meta.read_text())
    assert meta_obj["branch_contract"]["arm"] == "Sci_bar_LayerID1"
    assert meta_obj["n_rows"] > 0

    # per-species quantile-grid summary
    summary = table.with_name(table.stem + "_summary.csv")
    assert summary.exists(), f"summary not found at {summary}"

    sdf = pd.read_csv(summary)
    grid_cols = {"ke_p05_MeV", "ke_p16_MeV", "ke_median_MeV", "ke_p84_MeV", "ke_p95_MeV"}
    assert grid_cols.issubset(sdf.columns), (
        f"missing quantile-grid columns: {grid_cols - set(sdf.columns)}"
    )
    # both injected species present (proton + deuteron), neutrals excluded
    species = set(sdf["particle_pdg"].tolist())
    assert 2212 in species and 1000010020 in species
    assert 2112 not in species
    # quantile grid is monotonic non-decreasing per row
    for _, r in sdf.iterrows():
        assert (
            r["ke_p05_MeV"] <= r["ke_p16_MeV"] <= r["ke_median_MeV"]
            <= r["ke_p84_MeV"] <= r["ke_p95_MeV"]
        )


# --------------------------------------------------------------------------- #
# 5. extract: pure-function unit tests (import the module directly)
# --------------------------------------------------------------------------- #
def test_extract_pure_functions():
    mod = _load_module(EXTRACT_CLI, "extract_g4_entry_energies")

    # charge(): proton and deuteron are Z=1 charged; neutron is neutral.
    assert mod.charge(2212) == 1
    assert mod.charge(1000010020) == 1  # deuteron nucleus Z=1
    assert mod.charge(2112) == 0        # neutron

    # kinetic_from_momentum(): relativistic KE for a known mass.
    p = 100.0
    m = mod.MASS_MEV[2212]
    expected = (p * p + m * m) ** 0.5 - m
    assert abs(mod.kinetic_from_momentum(2212, 0.0, 0.0, p) - expected) < 1e-6
    assert np.isnan(mod.kinetic_from_momentum(99999999, 1.0, 1.0, 1.0))  # unknown mass

    # first_index_by_time(): earliest hit per (track, arm, layer) key.
    track = np.array([1, 1, 2])
    arm = np.array([1, 1, 1])
    layer = np.array([0, 0, 0])
    time = np.array([5.0, 2.0, 9.0])
    idxs = sorted(mod.first_index_by_time(track, arm, layer, time))
    assert idxs == [1, 2]  # index 1 (t=2) wins over index 0 (t=5) for track 1

    # select_branch(): found / missing-required / ambiguous.
    keys = {"Sci_bar_TrackID", "Sci_bar_Time"}
    assert mod.select_branch(keys, "track", required=True) == "Sci_bar_TrackID"
    with pytest.raises(SystemExit):
        mod.select_branch(set(), "track", required=True)
    with pytest.raises(SystemExit):
        mod.select_branch({"Sci_bar_EKin", "Sci_bar_Ekin"}, "ekin", required=False)

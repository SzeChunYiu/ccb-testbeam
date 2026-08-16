from __future__ import annotations

import csv
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_cl001", ROOT / "tools/audit/validate_claim_ledger_cl001.py"
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def copy_fixture(tmp_path: Path) -> Path:
    for relative in (
        "docs/claim_ledger.csv",
        "docs/figure_registry.csv",
        # Old S00 artifacts: still referenced by the FIG-GL-001 registry row.
        "configs/s00_reproduction.yaml",
        "reports/S00_data_integrity_pipeline_reproduction/REPORT.md",
        "reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv",
        "reports/S00_data_integrity_pipeline_reproduction/manifest.json",
        "reports/S00_data_integrity_pipeline_reproduction/fig_counts_by_group_stave.png",
        "scripts/01_build_pulse_table_from_root.py",
        # Corrected-staging authorising chain (CL-001 ledger row sources).
        "configs/data_side_s00_rebuild.yaml",
        "reports/studies/data_side/REPORT.md",
        "reports/studies/data_side/s00_rebuild/count_match_table.csv",
        "reports/studies/data_side/s00_rebuild/manifest.json",
        "reports/studies/data_side/s00_rebuild/s00_selected_b_pulses.csv.gz",
        "reports/studies/data_side/s00_rebuild/fig_counts_by_group_stave.png",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


def rewrite_csv(path: Path, mutate) -> None:
    rows = list(csv.reader(io.StringIO(path.read_text()), strict=True))
    mutate(rows)
    with path.open("w", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def test_valid_current_fixture(tmp_path: Path) -> None:
    payload = MOD.audit(copy_fixture(tmp_path))
    assert payload["status"] == "VALIDATED"
    assert payload["expected_count"] == 640737
    assert payload["configured_runs"] == 33
    assert payload["n_issues"] == 0


def test_short_cl001_row_fails_closed(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    rewrite_csv(root / "docs/claim_ledger.csv", lambda rows: rows.__setitem__(1, rows[1][:-1]))
    payload = MOD.audit(root)
    assert payload["status"] == "FLAWED"
    assert payload["issues"][0]["code"] == "LEDGER_ROW_WIDTH_MISMATCH"


def test_count_mismatch_is_rejected(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)

    def mutate(rows):
        rows[1][4] = "640736"

    rewrite_csv(root / "docs/claim_ledger.csv", mutate)
    payload = MOD.audit(root)
    assert "LEDGER_FIELD_MISMATCH" in {issue["code"] for issue in payload["issues"]}


def test_stale_figure_registry_is_rejected(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)

    def mutate(rows):
        rows[1][3] = "scripts/s00_selector.py"

    rewrite_csv(root / "docs/figure_registry.csv", mutate)
    payload = MOD.audit(root)
    assert "FIGURE_REGISTRY_MISMATCH" in {issue["code"] for issue in payload["issues"]}


def test_cli_writes_json_and_accessible_svg(tmp_path: Path) -> None:
    root = copy_fixture(tmp_path)
    out = tmp_path / "result.json"
    svg = tmp_path / "result.svg"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/audit/validate_claim_ledger_cl001.py"),
         "--repo-root", str(root), "--output", str(out), "--svg", str(svg)],
        text=True, capture_output=True, check=False,
    )
    assert proc.returncode == 0
    assert json.loads(out.read_text())["status"] == "VALIDATED"
    text = svg.read_text()
    assert 'role="img"' in text
    assert "CL-001 exact-count traceability" in text

"""Tests for selection-flow DAG (#970)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import validate_selection_flow_dag as v


def test_dag_contract_pass():
    assert v.validate(REPO) == []


def test_bound_method_leak_detected(tmp_path: Path):
    (tmp_path / "docs/contracts").mkdir(parents=True)
    shutil.copy(REPO / "docs/contracts/SELECTION_FLOW_DAG.json", tmp_path / "docs/contracts/SELECTION_FLOW_DAG.json")
    (tmp_path / "docs/academic_chapters").mkdir(parents=True)
    (tmp_path / "docs/academic_chapters/04_timing_analysis.md").write_text(
        "bad <bound method NDFrame.sample of ...>\n", encoding="utf-8"
    )
    errs = v.validate(tmp_path)
    assert any(e.startswith("LEAKED_BOUND_METHOD") for e in errs)

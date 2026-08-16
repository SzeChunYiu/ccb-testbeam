from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "geant4" / "single_stave" / "tests" / "test_optical_table_schema.py"
OPT = ROOT / "geant4" / "single_stave" / "optical"


def _load():
    spec = importlib.util.spec_from_file_location("optical_schema_waveA", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_shipped_optical_tables_pass_semantic_schema():
    mod = _load()
    mod.assert_shipped_ok(OPT)
    assert (OPT / "optical_constants_ledger.conf").is_file()


def test_semantic_schema_rejects_unit_and_range_defects():
    mod = _load()
    mod.assert_negative_cases(OPT)

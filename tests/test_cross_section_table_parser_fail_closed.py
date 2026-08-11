from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "audit" / "parse_cross_section_table.py"
CPP = ROOT / "geant4" / "src_patch" / "ScatteringGenerator.cc"
TABLE = ROOT / "geant4" / "src_patch" / "sigma_pd_cm_190.txt"

spec = importlib.util.spec_from_file_location("parse_cross_section_table", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_production_table_parses_under_fail_closed_contract():
    table = mod.parse_cross_section_table_file(TABLE)
    assert table.n_rows == 28
    assert table.angles_rad[0] == pytest.approx(math.radians(26.49))
    assert table.angles_rad[-1] == pytest.approx(math.radians(169.78))
    assert all(s >= 0.0 for s in table.sigma)


def test_scattering_generator_source_is_fail_closed():
    mod.assert_scattering_generator_fail_closed_parser(CPP.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "text, code",
    [
        ("26.49\n", "CCB_CS_PARSE"),
        ("nan 1.0\n30.0 1.0\n", "CCB_CS_DOMAIN"),
        ("26.49 -1.0\n30.0 1.0\n", "CCB_CS_DOMAIN"),
        ("0.0 1.0\n30.0 1.0\n", "CCB_CS_DOMAIN"),
        ("180.0 1.0\n30.0 1.0\n", "CCB_CS_DOMAIN"),
        ("30.0 1.0\n26.49 1.0\n", "CCB_CS_ORDER"),
        ("26.49 1.0\n26.49 2.0\n", "CCB_CS_ORDER"),
        ("26.49 1.0\n", "CCB_CS_CARDINALITY"),
    ],
)
def test_malformed_tables_fail_closed(text: str, code: str):
    with pytest.raises(mod.CrossSectionTableError, match=code):
        mod.parse_cross_section_table_text(text)

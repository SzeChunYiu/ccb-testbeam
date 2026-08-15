"""Format invariants of the #1296 hardware truth surface.

Row 40 of publication/tables/hardware_bom.csv shipped on main with an
unquoted comma inside its notes field (12 fields vs the 9-column header),
which breaks every strict csv.DictReader consumer. No strict parser
existed, so the defect went unseen. These tests pin the format.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOM_COLUMNS = ["component", "quantity", "value", "unit", "status",
               "evidence_path", "evidence_sha", "claim_ids", "notes"]
ALLOWED_STATUS = {"MEASURED", "DESIGN_SPEC", "SIM_CONFIG", "UNKNOWN_EXTERNAL"}
BOM_PATHS = (REPO_ROOT / "publication" / "tables" / "hardware_bom.csv",
             REPO_ROOT / "paper" / "hardware_bom.csv")


def _rows(path: Path):
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        return next(reader), [r for r in reader]


def test_bom_rows_have_exact_header_width():
    for path in BOM_PATHS:
        header, rows = _rows(path)
        assert header == BOM_COLUMNS, (path.name, header)
        for i, row in enumerate(rows, 2):
            assert len(row) == len(header), (
                f"{path.name} row {i} ({row[0]}): "
                f"{len(row)} fields, expected {len(header)}")


def test_status_vocabulary_is_closed():
    for path in BOM_PATHS:
        _, rows = _rows(path)
        for row in rows:
            assert row[4] in ALLOWED_STATUS, (path.name, row[0], row[4])


def test_component_names_unique():
    for path in BOM_PATHS:
        _, rows = _rows(path)
        comps = [r[0] for r in rows]
        assert len(comps) == len(set(comps)), path.name


def test_evidence_sha_wellformed_when_present():
    for path in BOM_PATHS:
        _, rows = _rows(path)
        for row in rows:
            sha = row[6]
            assert sha == "" or re.fullmatch(r"[0-9a-f]{64}", sha), (
                path.name, row[0], sha)

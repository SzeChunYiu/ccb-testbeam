from __future__ import annotations

from pathlib import Path

import pytest

from tools.audit.validate_single_stave_known_issues import ValidationError, audit


RESULTS = """# Geant4 Single-Stave Validation Results

**Build:** Geant4 11.2.2 (GCC 12.3.0) on LUNARC GPU node (hpua40)
**Particle:** 100 MeV proton, 500 events per run
- 27/27 branches exact equal across all 500 events
- 1,170,091 photon records in both runs
- All 6 fields (detected, event, path_len_mm, sensor, time_ns, wavelength_nm) exact equal
- Cross-seed mean optical yield: 178.3 PE (RSE = 0.48%)
| 1 | 177.1 | 20.5 | 176.0 |
| 2 | 178.0 | 22.6 | 177.0 |
| 3 | 179.5 | 30.4 | 176.0 |
| 4 | 178.5 | 35.4 | 174.5 |
"""

KNOWN = """# Single-stave simulation
- **Implementation/runtime status:** VALIDATED
- Canonical: docs/validation/G4_VALIDATION_RESULTS.md
Geant4 11.2.2 with GCC 12.3.0; 500 events per run.
27/27 branches exact equal; 1,170,091 records and all 6 stored fields exact equal.
Mean 178.3 PE/event with RSE 0.48%; seed means 177.1, 178.0, 179.5, 178.5.
BLK-G4-SP-001 remains open. This is not a detector calibration.
PR #868 remains closed and unmerged.
"""


def write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    known = tmp_path / "KNOWN_ISSUES.md"
    results = tmp_path / "G4_VALIDATION_RESULTS.md"
    known.write_text(KNOWN, encoding="utf-8")
    results.write_text(RESULTS, encoding="utf-8")
    return known, results


def test_valid_contract(tmp_path: Path) -> None:
    known, results = write_inputs(tmp_path)
    payload = audit(known, results)
    assert payload["status"] == "VALIDATED"
    assert payload["issues"] == []
    assert payload["reconstructed"]["photon_records"] == 1_170_091


def test_stale_open_issue_fails(tmp_path: Path) -> None:
    known, results = write_inputs(tmp_path)
    known.write_text(KNOWN + "\n## Open issue A\n", encoding="utf-8")
    payload = audit(known, results)
    assert payload["status"] == "FLAWED"
    assert any(
        issue["code"] == "STALE_RESOLVED_ISSUE_NARRATIVE"
        for issue in payload["issues"]
    )


def test_missing_scientific_boundary_fails(tmp_path: Path) -> None:
    known, results = write_inputs(tmp_path)
    known.write_text(KNOWN.replace("BLK-G4-SP-001", "BLK-CLOSED"), encoding="utf-8")
    payload = audit(known, results)
    assert payload["status"] == "FLAWED"
    assert any(issue.get("name") == "stopping_power_boundary" for issue in payload["issues"])


def test_altered_result_requires_matching_status(tmp_path: Path) -> None:
    known, results = write_inputs(tmp_path)
    results.write_text(RESULTS.replace("178.3 PE", "179.3 PE"), encoding="utf-8")
    payload = audit(known, results)
    assert payload["status"] == "FLAWED"
    assert any(issue.get("name") == "mean_yield" for issue in payload["issues"])


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    known, results = write_inputs(tmp_path)
    known.write_bytes(b"\xff")
    with pytest.raises(ValidationError, match="not valid UTF-8"):
        audit(known, results)

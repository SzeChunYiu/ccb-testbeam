"""Offline unit test for the geometry-report parser/validator.

Exercises check_geometry_report.py without a compiled Geant4 executable by
feeding it golden-correct and deliberately-broken report text. The live ctest
(ccb_stave_geometry_report_python) covers the real executable on LUNARC.
"""
import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_geometry_report", _HERE / "check_geometry_report.py"
)
cgr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cgr)

GOLDEN = """\
CCB_STAVE_START particle=proton
GEOMETRY_REPORT_BEGIN
stave_length_cm 50
stave_width_cm 5.18
stave_thickness_cm 2
normal_path_cm 2
fibre_diameter_mm 1.8
hole_diameter_mm 2
fibre_separation_cm 2
fibre_within_hole 1
fibre_protrudes_for_readout 1
holes_contained_y 1
holes_contained_z 1
geometry_hash deadbeef
GEOMETRY_REPORT_END
GEOMETRY_SELFCHECK_PASS
"""


def test_golden_report_passes():
    report = cgr.parse_report(GOLDEN)
    assert report["_selfcheck_pass"] is True
    assert cgr.check_report(report) == []


def test_wrong_thickness_is_flagged():
    # The classic prototype defect: primary along the 50 cm axis => 50 cm path.
    broken = GOLDEN.replace("normal_path_cm 2\n", "normal_path_cm 50\n")
    problems = cgr.check_report(cgr.parse_report(broken))
    assert any("normal_path_cm" in p for p in problems)


def test_fibre_outside_hole_is_flagged():
    broken = GOLDEN.replace("fibre_within_hole 1\n", "fibre_within_hole 0\n")
    problems = cgr.check_report(cgr.parse_report(broken))
    assert any("fibre_within_hole" in p for p in problems)


def test_fibre_not_protruding_is_flagged():
    # Fibres must protrude past the bar so sensors read out externally.
    broken = GOLDEN.replace("fibre_protrudes_for_readout 1\n",
                            "fibre_protrudes_for_readout 0\n")
    problems = cgr.check_report(cgr.parse_report(broken))
    assert any("fibre_protrudes_for_readout" in p for p in problems)


def test_selfcheck_fail_token_is_flagged():
    broken = GOLDEN.replace("GEOMETRY_SELFCHECK_PASS", "GEOMETRY_SELFCHECK_FAIL")
    report = cgr.parse_report(broken)
    assert report["_selfcheck_pass"] is False
    assert any("SELFCHECK" in p for p in cgr.check_report(report))


def test_geant4_overlap_message_is_flagged():
    # Geant4's real CheckOverlaps message must fail the report (fixes the old
    # false-PASS where the internal check ignored actual overlaps).
    broken = GOLDEN + "\n          Overlap is detected for volume Sensor_F1_PlusX\n"
    report = cgr.parse_report(broken)
    assert report.get("_g4_overlap") is True
    assert any("Overlap is detected" in p for p in cgr.check_report(report))


def test_missing_key_is_flagged():
    broken = GOLDEN.replace("fibre_separation_cm 2\n", "")
    problems = cgr.check_report(cgr.parse_report(broken))
    assert any("fibre_separation_cm" in p for p in problems)

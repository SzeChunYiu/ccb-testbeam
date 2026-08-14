#!/usr/bin/env python3
"""Regression test for issue #1303 (inner/outer cladding material alias defect).

Proves that inner and outer cladding are DISTINCT G4Material/MPT objects with
intended RINDEX values (n≈1.49 inner, n≈1.42 outer). The historical defect at
commit 0005ed0c used shared G4_PLEXIGLASS with one overwriting the other's MPT.

This test parses the GEOMETRY_REPORT output which now includes:
  * clad_inner_rindex: refractive index of inner cladding (PMMA, n≈1.49)
  * clad_outer_rindex: refractive index of outer cladding (fluorinated PMMA, n≈1.42)

The test asserts:
  1. Both values are present in the report
  2. They are numerically distinct (not aliased to the same material)
  3. Each is within expected bounds for its material type
  4. inner > outer (PMMA > fluorinated PMMA, as designed)
"""

import argparse
import subprocess
import sys
from pathlib import Path


# Expected refractive indices from AppConfig.hh defaults
EXPECTED_INNER_RINDEX = 1.49  # PMMA
EXPECTED_OUTER_RINDEX = 1.42  # Fluorinated PMMA
# Tolerance for floating point comparison
TOL = 1e-3


def parse_geometry_report(text: str) -> dict:
    """Extract key/value pairs from the geometry report."""
    report: dict = {}
    inside = False
    for line in text.splitlines():
        s = line.strip()
        if s == "GEOMETRY_REPORT_BEGIN":
            inside = True
            continue
        if s == "GEOMETRY_REPORT_END":
            inside = False
            continue
        if inside and s:
            parts = s.split()
            if len(parts) >= 2:
                key = parts[0]
                try:
                    report[key] = float(parts[1])
                except ValueError:
                    report[key] = parts[1]
    return report


def run_simulation(exe: Path, optical_dir: Path, macro: Path) -> str:
    """Run ccb_stave_sim with the geometry-check macro."""
    cmd = [
        str(exe),
        "--physics-list", "QGSP_BIC",
        "--neutron-timecut-policy-id", "pin_qgsp_bic_default_10us",
        "--macro", str(macro),
        "--optical-dir", str(optical_dir),
        "--output", "/dev/null"  # We only need stdout
    ]
    print(f"RUN: {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError(f"ccb_stave_sim exited {proc.returncode}")
    return proc.stdout + "\n" + proc.stderr


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", required=True, type=Path, help="ccb_stave_sim executable")
    ap.add_argument("--optical-dir", required=True, type=Path, help="optical tables directory")
    ap.add_argument("--macro", type=Path, default=Path("macros/geometry_check.mac"))
    args = ap.parse_args()

    # Run simulation and parse geometry report
    report_text = run_simulation(args.exe, args.optical_dir, args.macro)
    report = parse_geometry_report(report_text)

    # Extract cladding RINDEX values
    if "clad_inner_rindex" not in report:
        print("FAIL: clad_inner_rindex not found in geometry report", file=sys.stderr)
        print("Available keys:", sorted(report.keys()), file=sys.stderr)
        return 1
    if "clad_outer_rindex" not in report:
        print("FAIL: clad_outer_rindex not found in geometry report", file=sys.stderr)
        print("Available keys:", sorted(report.keys()), file=sys.stderr)
        return 1

    inner = report["clad_inner_rindex"]
    outer = report["clad_outer_rindex"]

    print(f"clad_inner_rindex: {inner}", file=sys.stderr)
    print(f"clad_outer_rindex: {outer}", file=sys.stderr)

    # Assertion 1: Inner and outer are distinct (not aliased)
    if abs(inner - outer) < TOL:
        print(
            f"FAIL: Inner and outer cladding have identical RINDEX ({inner} ≈ {outer}). "
            f"This indicates the material alias defect (issue #1303) has regressed.",
            file=sys.stderr,
        )
        return 1

    # Assertion 2: Inner > outer (PMMA > fluorinated PMMA)
    if inner <= outer:
        print(
            f"FAIL: Inner cladding RINDEX ({inner}) should be > outer ({outer}) "
            f"for the PMMA/fluorinated-PMMA design.",
            file=sys.stderr,
        )
        return 1

    # Assertion 3: Values are within expected bounds
    if abs(inner - EXPECTED_INNER_RINDEX) > TOL:
        print(
            f"FAIL: clad_inner_rindex ({inner}) differs from expected {EXPECTED_INNER_RINDEX}",
            file=sys.stderr,
        )
        return 1

    if abs(outer - EXPECTED_OUTER_RINDEX) > TOL:
        print(
            f"FAIL: clad_outer_rindex ({outer}) differs from expected {EXPECTED_OUTER_RINDEX}",
            file=sys.stderr,
        )
        return 1

    print(
        f"PASS: Inner and outer cladding are distinct materials with correct RINDEX "
        f"(inner={inner}, outer={outer}).",
        file=sys.stderr,
    )
    print("CLADDING_DISTINCTION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

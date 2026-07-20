#!/usr/bin/env python3
"""Validate the CCB single-stave geometry report.

Two modes:
  * live   : run the built executable with the geometry-check macro and parse
             its stdout (used by ctest; requires a compiled ccb_stave_sim).
  * offline: parse a captured report file (used by the offline pytest so the
             parser/assertions are exercised without Geant4).

Exit code 0 iff every geometry invariant holds and OVERLAP_CHECK_PASS is present.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# Expected geometry (cm / mm), from the confirmed detector parameters.
EXPECTED = {
    "stave_length_cm": 50.0,
    "stave_width_cm": 5.18,
    "stave_thickness_cm": 2.0,
    "normal_path_cm": 2.0,
    "fibre_diameter_mm": 1.8,
    "hole_diameter_mm": 2.0,
    "fibre_separation_cm": 2.0,
}
FLAGS_MUST_BE_ONE = [
    "fibre_within_hole",
    "fibre_protrudes_for_readout",
    "holes_contained_y",
    "holes_contained_z",
]
TOL = 1e-3


def parse_report(text: str) -> dict:
    """Extract key/value pairs between GEOMETRY_REPORT_BEGIN/END plus the flag."""
    out: dict = {}
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
                    out[key] = float(parts[1])
                except ValueError:
                    out[key] = parts[1]
        if s == "GEOMETRY_SELFCHECK_PASS":
            out["_selfcheck_pass"] = True
        if s == "GEOMETRY_SELFCHECK_FAIL":
            out["_selfcheck_pass"] = False
        # Geant4's authoritative overlap detection (pSurfChk / geometry test).
        if "Overlap is detected" in line:
            out["_g4_overlap"] = True
    return out


def check_report(report: dict) -> list[str]:
    """Return a list of problems; empty means the geometry is valid."""
    problems: list[str] = []
    for key, want in EXPECTED.items():
        if key not in report:
            problems.append(f"missing key: {key}")
            continue
        got = report[key]
        if abs(float(got) - want) > TOL:
            problems.append(f"{key}: got {got}, expected {want}")
    for flag in FLAGS_MUST_BE_ONE:
        if report.get(flag) != 1.0:
            problems.append(f"{flag} != 1 (got {report.get(flag)})")
    if not report.get("_selfcheck_pass", False):
        problems.append("GEOMETRY_SELFCHECK_PASS not found")
    if report.get("_g4_overlap", False):
        problems.append("Geant4 reported 'Overlap is detected'")
    return problems


def run_live(exe: str, macro: str, optical_dir: str, output: str) -> str:
    cmd = [exe, "--macro", macro, "--optical-dir", optical_dir, "--output", output]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return proc.stdout + "\n" + proc.stderr


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", help="path to compiled ccb_stave_sim (live mode)")
    ap.add_argument("--macro", default="macros/geometry_check.mac")
    ap.add_argument("--optical-dir", default="optical")
    ap.add_argument("--output", default="geometry_smoke.root")
    ap.add_argument("--report-file", help="parse a captured report (offline mode)")
    args = ap.parse_args(argv)

    if args.report_file:
        with open(args.report_file, "r", encoding="utf-8") as fh:
            text = fh.read()
    elif args.exe:
        text = run_live(args.exe, args.macro, args.optical_dir, args.output)
    else:
        ap.error("provide --exe (live) or --report-file (offline)")
        return 2

    report = parse_report(text)
    problems = check_report(report)
    if problems:
        print("GEOMETRY_REPORT_CHECK: FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print("GEOMETRY_REPORT_CHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""SIPM-P0-002: verify the four --far-end modes are accepted, recorded in
RUN_CONFIG metadata, and produce a valid geometry (no overlaps).

Runs the compiled ccb_stave_sim once per mode with the geometry-check macro,
parses stdout for the RUN_CONFIG line and the geometry self-check / overlap
tokens.  Exit 0 iff every mode passes all assertions.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

MODES = ("absorb", "open", "mirror", "instrumented")


def run_mode(exe: str, mode: str, macro: str, optical_dir: str,
             work_dir: str) -> str:
    """Run the sim for one far-end mode and return combined stdout+stderr."""
    out_root = os.path.join(work_dir, f"far_end_{mode}.root")
    cmd = [
        exe,
        "--far-end", mode,
        "--macro", macro,
        "--optical-dir", optical_dir,
        "--output", out_root,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return proc.stdout + "\n" + proc.stderr


def check_mode(text: str, mode: str) -> list[str]:
    """Return list of problems for this mode; empty means pass."""
    problems: list[str] = []
    # RUN_CONFIG must contain the configured mode.
    if f"far_end={mode}" not in text:
        problems.append(f"RUN_CONFIG does not contain far_end={mode}")
    # Geometry self-check must pass.
    if "GEOMETRY_SELFCHECK_PASS" not in text:
        problems.append("GEOMETRY_SELFCHECK_PASS not found")
    if "GEOMETRY_SELFCHECK_FAIL" in text:
        problems.append("GEOMETRY_SELFCHECK_FAIL present")
    # Geant4 overlap detection must not flag anything.
    if "Overlap is detected" in text:
        problems.append("Geant4 reported 'Overlap is detected'")
    # No fatal exceptions.
    if "FatalException" in text or "G4Exception" in text:
        problems.append("G4Exception present in output")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", required=True, help="path to ccb_stave_sim")
    ap.add_argument("--macro", required=True, help="geometry-check macro")
    ap.add_argument("--optical-dir", required=True)
    ap.add_argument("--work-dir", default=".")
    args = ap.parse_args(argv)

    os.makedirs(args.work_dir, exist_ok=True)

    all_ok = True
    for mode in MODES:
        text = run_mode(args.exe, mode, args.macro, args.optical_dir,
                        args.work_dir)
        problems = check_mode(text, mode)
        if problems:
            all_ok = False
            print(f"FAIL  far_end={mode}:")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"PASS  far_end={mode}")

    if all_ok:
        print("ALL FAR-END MODES PASSED")
        return 0
    print("SOME FAR-END MODES FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Integration regression for strict SiPM environment overrides.

Run from CTest or manually after building ccb_stave_sim.  The test verifies two
scientific invariants introduced by AF-027/AF-028:

1. zero-valued DCR/crosstalk/afterpulse controls are actually effective;
2. malformed/out-of-domain digitizer settings fail before an authorising run.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def run(exe: Path, optical_dir: Path, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_overrides)
    with tempfile.TemporaryDirectory(prefix="ccb_sipm_env_") as tmp:
        out = Path(tmp) / "test.root"
        cmd = [
            str(exe),
            "--particle",
            "proton",
            "--energy",
            "100",
            "--nevents",
            "1",
            "--seed",
            "7",
            "--threads",
            "1",
            "--optical-dir",
            str(optical_dir),
            "--strict-optical",
            "--output",
            str(out),
        ]
        return subprocess.run(cmd, env=env, text=True, capture_output=True, check=False)


def combined(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def assert_zero_controls(exe: Path, optical_dir: Path) -> None:
    proc = run(
        exe,
        optical_dir,
        {
            "CCB_SIPM_DARK_COUNT_RATE_HZ": "0",
            "CCB_SIPM_CROSSTALK_PROB": "0",
            "CCB_SIPM_AFTERPULSE_FAST_PROB": "0",
        },
    )
    text = combined(proc)
    if proc.returncode != 0:
        raise AssertionError(f"zero-control run failed with rc={proc.returncode}\n{text}")
    line = next((ln for ln in text.splitlines() if ln.startswith("SIPM_CONFIG")), "")
    for token in ("dcr_hz=0", "crosstalk=0", "afterpulse_fast=0"):
        if token not in line:
            raise AssertionError(f"effective config does not contain {token!r}: {line!r}")


def assert_rejected(exe: Path, optical_dir: Path, name: str, value: str) -> None:
    proc = run(exe, optical_dir, {name: value})
    text = combined(proc)
    if proc.returncode == 0:
        raise AssertionError(
            f"invalid override {name}={value!r} completed successfully; output:\n{text}"
        )
    # The exact C++/Geant exception wrapper is platform-dependent; require the
    # offending environment-variable name to remain visible for operator audit.
    if name not in text:
        raise AssertionError(
            f"failure for {name}={value!r} did not identify the setting; output:\n{text}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--optical-dir", type=Path, required=True)
    args = ap.parse_args()

    if not args.exe.is_file():
        raise SystemExit(f"executable not found: {args.exe}")
    if not args.optical_dir.is_dir():
        raise SystemExit(f"optical directory not found: {args.optical_dir}")

    assert_zero_controls(args.exe, args.optical_dir)
    assert_rejected(args.exe, args.optical_dir, "CCB_SIPM_CROSSTALK_PROB", "0junk")
    assert_rejected(args.exe, args.optical_dir, "CCB_SIPM_CROSSTALK_PROB", "1")
    assert_rejected(args.exe, args.optical_dir, "CCB_SIPM_ADC_BITS", "0")
    assert_rejected(args.exe, args.optical_dir, "CCB_SIPM_SAMPLE_DT_NS", "nan")
    assert_rejected(args.exe, args.optical_dir, "CCB_SIPM_OVERVOLTAGE_V", "5")
    assert_rejected(args.exe, args.optical_dir, "CCB_SIPM_TEMPERATURE_C", "0")
    print("SIPM_ENV_FAIL_CLOSED_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

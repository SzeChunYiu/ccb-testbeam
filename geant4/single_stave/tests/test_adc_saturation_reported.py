#!/usr/bin/env python3
"""ADC clipping must be reported, never silent (issue #1623).

`ResponseSimulator` clamps every waveform sample to the ADC ceiling, and
`EventAction` then reports `peak - baseline`. At the shipped placeholder gain
(12 bits, baseline 200, 0.01 pe/LSB) that leaves only ~39 pe of PEAK headroom,
so a CCB stave deposit above roughly 18 MeV pinned `adc_readout` at exactly 3895
with nothing in the output distinguishing a ceiling from a measurement. Four
fifths of the events in the #1623 campaign sat there.

This test does NOT assert that the placeholder gain is correct -- there is no
DAQ number to assert against. It asserts the invariant that makes the placeholder
safe to ship: a run that clips SAYS SO, and widening the range clears it.

  1. a deposit large enough to clip reports saturated_fraction > 0 and warns;
  2. the same point with a wider --adc-lsb-pe reports saturated_fraction == 0;
  3. the reported headroom tracks the configured range;
  4. a small deposit that fits does not report saturation.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED = [
    "--physics-list", "QGSP_BIC",
    "--neutron-timecut-policy-id", "pin_qgsp_bic_default_10us",
]


def run(exe: Path, optical_dir: Path, energy: float, nevents: int,
        lsb: float | None) -> str:
    with tempfile.TemporaryDirectory(prefix="ccb_adc_sat_") as tmp:
        cmd = [str(exe), *REQUIRED,
               "--mode", "optical", "--strict-optical",
               "--particle", "proton", "--energy", str(energy),
               "--nevents", str(nevents), "--seed", "5", "--threads", "1",
               "--hit-x", "0", "--hit-y", "0",
               "--no-photon-ntuple",
               "--optical-max-time-ns", "1000", "--optical-max-steps", "200000",
               "--optical-dir", str(optical_dir),
               "--output", str(Path(tmp) / "adc.root")]
        if lsb is not None:
            cmd += ["--adc-lsb-pe", str(lsb)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            print(proc.stdout[-4000:])
            print(proc.stderr[-4000:], file=sys.stderr)
            raise RuntimeError(f"ccb_stave_sim exited {proc.returncode}")
        return proc.stdout + "\n" + proc.stderr


def field(text: str, key: str) -> float:
    m = re.search(rf"CCB_ADC_SATURATION[^\n]*\b{key}=([0-9.eE+-]+)", text)
    if not m:
        raise AssertionError(f"CCB_ADC_SATURATION line has no {key}=; got:\n"
                             + "\n".join(l for l in text.splitlines()
                                         if "CCB_ADC_SATURATION" in l) or "<no line at all>")
    return float(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", required=True, type=Path)
    ap.add_argument("--optical-dir", required=True, type=Path)
    ap.add_argument("--nevents", type=int, default=6)
    args = ap.parse_args()

    problems: list[str] = []

    # 1. a clipping deposit must report it, on stdout and as a warning
    big = run(args.exe, args.optical_dir, 46.0, args.nevents, None)
    frac_big = field(big, "saturated_fraction")
    head_big = field(big, "headroom_pe")
    print(f"[clip]   46 MeV, default gain: saturated_fraction={frac_big:.3f} "
          f"headroom_pe={head_big:.2f}")
    if frac_big <= 0.0:
        problems.append("a 46 MeV deposit did not report ADC saturation at the "
                        "placeholder gain; either the gain changed (update this "
                        "test deliberately) or the reporting path regressed")
    if "clipped lower bounds" not in big:
        problems.append("saturating run printed no warning about clipped ADC values")

    # 2. widening the range must clear it
    wide = run(args.exe, args.optical_dir, 46.0, args.nevents, 0.20)
    frac_wide = field(wide, "saturated_fraction")
    head_wide = field(wide, "headroom_pe")
    print(f"[wide]   46 MeV, --adc-lsb-pe 0.20: saturated_fraction={frac_wide:.3f} "
          f"headroom_pe={head_wide:.2f}")
    if frac_wide != 0.0:
        problems.append(f"widening the ADC range left saturated_fraction={frac_wide}")

    # 3. the reported headroom must follow the configured range
    if head_wide <= head_big:
        problems.append(f"headroom did not grow with --adc-lsb-pe "
                        f"({head_big} -> {head_wide})")

    # 4. a deposit that fits must not report saturation
    small = run(args.exe, args.optical_dir, 5.0, args.nevents, None)
    frac_small = field(small, "saturated_fraction")
    print(f"[fits]    5 MeV, default gain: saturated_fraction={frac_small:.3f}")
    if frac_small != 0.0:
        problems.append(f"a 5 MeV deposit reported saturation ({frac_small}); "
                        "the ceiling test is firing spuriously")

    print()
    if problems:
        print("ADC_SATURATION_REPORTING_FAIL")
        for p in problems:
            print("  FAIL:", p)
        return 1
    print("ADC_SATURATION_REPORTING_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

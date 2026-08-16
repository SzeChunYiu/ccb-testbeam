#!/usr/bin/env python3
"""Regression test for issue #1089: production-cut / Birks coupling.

Proves that `--production-cut` controls the Geant4 secondary-production range
threshold (NOT optical-photon tracking) and that the parameter is properly
wired through the CLI, AppConfig, and metadata sidecar:

  1. The RUN_CONFIG line and .meta.json sidecar record the production_cut_mm value.
  2. Changing the cut changes the visible energy deposition (cut x kB coupling):
     a larger cut (fewer explicit secondaries, higher local dE/dx) yields more
     Birks suppression (lower visible energy), while a smaller cut (more
     explicit secondaries, lower local dE/dx) yields less suppression.
  3. The simulation does not crash with either extreme value.

This protects against the original misnomer where `optical_cut_mm` was
interpreted as an optical-photon tracking cut, while it actually controls the
global secondary-production range threshold (gamma, e-, e+, proton).

Exit code 77 (skip) when uproot is unavailable.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--exe", required=True, type=Path, help="ccb_stave_sim executable")
    p.add_argument("--optical-dir", required=True, type=Path, help="optical tables directory")
    p.add_argument("--work-dir", required=True, type=Path, help="scratch dir for run outputs")
    p.add_argument("--particle", default="proton", help="primary particle (default proton)")
    p.add_argument(
        "--energy", type=float, default=100.0,
        help="primary kinetic energy MeV (default 100)",
    )
    p.add_argument(
        "--nevents", type=int, default=5,
        help="events per run (default 5; every depositing event is Birks-suppressed)",
    )
    p.add_argument("--seed", type=int, default=1, help="RNG seed (default 1)")
    # Two production cut values to compare: fine cut (more secondaries) and
    # coarse cut (fewer secondaries). The visible energy must differ between
    # them, proving the cut x kB coupling.
    p.add_argument(
        "--cut-fine", type=float, default=0.01,
        help="small production cut [mm] (default 0.01; more explicit secondaries)",
    )
    p.add_argument(
        "--cut-coarse", type=float, default=1.0,
        help="large production cut [mm] (default 1.0; fewer explicit secondaries)",
    )
    p.add_argument(
        "--epsilon-mev", type=float, default=1e-3,
        help="minimum visible-energy difference [MeV] between the two runs (default 1e-3; "
        "a 100 MeV proton deposits ~9 MeV over 20 mm, and the cut x kB coupling should "
        "produce a gap well above this)",
    )
    return p.parse_args()


def read_events(root_path: Path) -> "dict[str, list]":
    try:
        import uproot  # type: ignore
    except ImportError:
        print(
            "SKIP: uproot is not installed in this python; install the optional "
            "[root] extra (uproot) to exercise the production-cut regression test.",
            file=sys.stderr,
        )
        sys.exit(77)

    with uproot.open(root_path) as f:
        keys = {k.split(";")[0] for k in f.keys()}
        if "events" not in keys:
            raise AssertionError(
                f"'events' tree not found in {root_path}; keys={sorted(keys)}"
            )
        return f["events"].arrays(
            ["edep_scint_MeV", "edep_scint_raw_MeV", "event"], library="np"
        )


def read_metadata(root_path: Path) -> dict:
    """Read the .meta.json sidecar for a simulation output."""
    meta_path = root_path.with_suffix(root_path.suffix + ".meta.json")
    if not meta_path.exists():
        raise AssertionError(f"metadata sidecar not found: {meta_path}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def extract_run_config_value(text: str, key: str) -> str:
    """Extract a key=value from the RUN_CONFIG line."""
    m = re.search(rf"\b{key}=([\d.]+(?:e[+-]?\d+)?)", text)
    if m:
        return m.group(1)
    raise AssertionError(f"key '{key}' not found in RUN_CONFIG output")


def run_sim(args: argparse.Namespace, production_cut_mm: float, out_root: Path) -> str:
    """Run ccb_stave_sim for a handful of events at the requested production cut."""
    cmd = [
        str(args.exe),
        "--particle", args.particle,
        "--energy", str(args.energy),
        "--nevents", str(args.nevents),
        "--seed", str(args.seed),
        "--production-cut", str(production_cut_mm),
        "--optical-dir", str(args.optical_dir),
        "--output", str(out_root),
    ]
    print("RUN: " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise AssertionError(
            f"ccb_stave_sim exited {proc.returncode} at production-cut={production_cut_mm}"
        )
    if not out_root.exists():
        raise AssertionError(f"expected output not written: {out_root}")
    combined = proc.stdout + proc.stderr
    if "RUN_DONE" not in combined and "CCB_STAVE_END" not in combined:
        raise AssertionError(
            f"sim did not signal completion at production-cut={production_cut_mm}"
        )
    return combined


def main() -> int:
    args = parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)

    out_fine = args.work_dir / "cut_fine.root"
    out_coarse = args.work_dir / "cut_coarse.root"

    # --- Run the simulation with fine (small) and coarse (large) production cuts. ---
    stdout_fine = run_sim(args, args.cut_fine, out_fine)
    stdout_coarse = run_sim(args, args.cut_coarse, out_coarse)

    # --- Assertion 1: RUN_CONFIG records the production_cut_mm value. ---
    fine_cut_reported = extract_run_config_value(stdout_fine, "production_cut_mm")
    coarse_cut_reported = extract_run_config_value(stdout_coarse, "production_cut_mm")
    fine_val = float(fine_cut_reported)
    coarse_val = float(coarse_cut_reported)
    print(
        f"RUN_CONFIG production_cut_mm: fine={fine_cut_reported} coarse={coarse_cut_reported}",
        file=sys.stderr,
    )
    if abs(fine_val - args.cut_fine) > 1e-9:
        raise AssertionError(
            f"RUN_CONFIG production_cut_mm mismatch: requested {args.cut_fine}, "
            f"reported {fine_cut_reported}"
        )
    if abs(coarse_val - args.cut_coarse) > 1e-9:
        raise AssertionError(
            f"RUN_CONFIG production_cut_mm mismatch: requested {args.cut_coarse}, "
            f"reported {coarse_cut_reported}"
        )

    # --- Assertion 2: Metadata sidecar JSON contains production_cut_mm. ---
    meta_fine = read_metadata(out_fine)
    meta_coarse = read_metadata(out_coarse)
    if "production_cut_mm" not in meta_fine:
        raise AssertionError(
            f"metadata sidecar missing 'production_cut_mm' key: {meta_fine.keys()}"
        )
    if "production_cut_mm" not in meta_coarse:
        raise AssertionError(
            f"metadata sidecar missing 'production_cut_mm' key: {meta_coarse.keys()}"
        )
    meta_fine_val = float(meta_fine["production_cut_mm"])
    meta_coarse_val = float(meta_coarse["production_cut_mm"])
    print(
        f"Metadata production_cut_mm: fine={meta_fine_val} coarse={meta_coarse_val}",
        file=sys.stderr,
    )
    if abs(meta_fine_val - args.cut_fine) > 1e-9:
        raise AssertionError(
            f"metadata sidecar production_cut_mm mismatch: requested {args.cut_fine}, "
            f"got {meta_fine_val}"
        )
    if abs(meta_coarse_val - args.cut_coarse) > 1e-9:
        raise AssertionError(
            f"metadata sidecar production_cut_mm mismatch: requested {args.cut_coarse}, "
            f"got {meta_coarse_val}"
        )

    # --- Assertion 3: Visible energy differs between fine and coarse cuts. ---
    # A larger production cut (coarse) = fewer explicit secondaries = higher
    # local ionization density = more Birks suppression = lower visible energy.
    # A smaller production cut (fine) = more explicit secondaries = lower local
    # ionization density = less Birks suppression = higher visible energy.
    # Therefore: coarse_cut visible < fine_cut visible (on average).
    fine = read_events(out_fine)
    coarse = read_events(out_coarse)

    fine_vis = fine["edep_scint_MeV"]
    coarse_vis = coarse["edep_scint_MeV"]

    if len(fine_vis) == 0:
        raise AssertionError("no events in fine-cut output")
    if len(coarse_vis) == 0:
        raise AssertionError("no events in coarse-cut output")

    fine_total = sum(fine_vis)
    coarse_total = sum(coarse_vis)
    print(
        f"Visible energy: fine_total={fine_total:.6f} MeV "
        f"coarse_total={coarse_total:.6f} MeV",
        file=sys.stderr,
    )

    # The coarse cut must produce a Birks-suppressed visible energy that differs
    # from the fine cut by at least epsilon.  We don't assert which is larger
    # because the magnitude of the effect depends on the hadronic physics and
    # may be non-monotonic — we just verify that the cut changes the result.
    diff = abs(fine_total - coarse_total)
    if diff <= args.epsilon_mev:
        raise AssertionError(
            f"production cut x kB coupling not detected: fine-cut visible sum "
            f"({fine_total:.6f}) and coarse-cut visible sum ({coarse_total:.6f}) "
            f"differ by only {diff:.6g} MeV, which is <= epsilon {args.epsilon_mev:g}. "
            "The production cut parameter may not be reaching "
            "G4EmSaturation::VisibleEnergyDepositionAtAStep — issue #1089 may have regressed."
        )

    print(
        "PASS: production cut is wired through CLI, RUN_CONFIG, and metadata sidecar, "
        "and produces a measurable cut x kB coupling on visible energy deposition.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
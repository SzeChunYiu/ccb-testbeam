#!/usr/bin/env python3
"""Regression test for review defect 2 (Birks visible-energy branch).

Proves that `edep_scint_MeV` (Birks-visible via G4EmSaturation) and
`edep_scint_raw_MeV` (unquenched GetTotalEnergyDeposit) are NOT silently
identical when a Birks constant is configured:

  * with --birks-kB > 0, at least one event must satisfy
    edep_scint_raw_MeV > edep_scint_MeV + epsilon  (visible < raw);
  * with --birks-kB 0, the two branches must agree to tolerance.

This protects against the original bug where both branches were filled from
GetTotalEnergyDeposit and were therefore exactly equal regardless of Birks.

The script runs `ccb_stave_sim` twice (few events) and parses the `events`
ntuple with uproot. It is intentionally self-contained so ctest can drive it.
Exit code 77 (skip) is returned when uproot is unavailable so the test degrades
gracefully on python builds without the optional ROOT reader.
"""
from __future__ import annotations

import argparse
import math
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
        "--energy",
        type=float,
        default=100.0,
        help="primary kinetic energy MeV (default 100; matches the smoke config)",
    )
    p.add_argument(
        "--nevents",
        type=int,
        default=3,
        help="events per run (default 3; every depositing event is Birks-suppressed "
        "so this is plenty while keeping the two-run ctest fast)",
    )
    p.add_argument(
        "--birks-on",
        type=float,
        default=0.126,
        help="enabled Birks kB [mm/MeV] (default 0.126; polystyrene, AppConfig.hh default)",
    )
    p.add_argument(
        "--birks-off",
        type=float,
        default=0.0,
        help="disabled Birks kB [mm/MeV] (default 0; visible==raw by construction)",
    )
    p.add_argument(
        "--epsilon-mev",
        type=float,
        default=1e-4,
        help="min raw-visible gap [MeV] for the Birks-on assertion (default 1e-4; "
        "a 100 MeV proton deposits ~9 MeV over 20 mm with ~5%% Birks suppression, "
        "so the gap is ~0.5 MeV >> epsilon)",
    )
    p.add_argument(
        "--equal-atol",
        type=float,
        default=1e-9,
        help="absolute tolerance [MeV] for the Birks-off equality assertion",
    )
    p.add_argument(
        "--equal-rtol",
        type=float,
        default=1e-7,
        help="relative tolerance for the Birks-off equality assertion",
    )
    p.add_argument("--seed", type=int, default=1, help="RNG seed (default 1)")
    return p.parse_args()


def read_events(root_path: Path) -> "dict[str, list]":
    try:
        import uproot  # type: ignore
    except ImportError:
        print(
            "SKIP: uproot is not installed in this python; install the optional "
            "[root] extra (uproot) to exercise the Birks regression test.",
            file=sys.stderr,
        )
        sys.exit(77)

    with uproot.open(root_path) as f:
        keys = {k.split(";")[0] for k in f.keys()}
        if "events" not in keys:
            raise AssertionError(f"'events' tree not found in {root_path}; keys={sorted(keys)}")
        return f["events"].arrays(["edep_scint_MeV", "edep_scint_raw_MeV"], library="np")


def run_sim(args: argparse.Namespace, birks_kB: float, out_root: Path) -> None:
    """Run ccb_stave_sim for a handful of events at the requested Birks kB."""
    cmd = [
        str(args.exe),
        "--particle", args.particle,
        "--energy", str(args.energy),
        "--nevents", str(args.nevents),
        "--seed", str(args.seed),
        "--birks-kB", str(birks_kB),
        "--optical-dir", str(args.optical_dir),
        "--output", str(out_root),
    ]
    print("RUN: " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise AssertionError(f"ccb_stave_sim exited {proc.returncode} at birks-kB={birks_kB}")
    if not out_root.exists():
        raise AssertionError(f"expected output not written: {out_root}")
    combined = proc.stdout + proc.stderr
    if "RUN_DONE" not in combined and "CCB_STAVE_END" not in combined:
        raise AssertionError(f"sim did not signal completion at birks-kB={birks_kB}")


def main() -> int:
    args = parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)

    out_on = args.work_dir / "birks_on.root"
    out_off = args.work_dir / "birks_off.root"
    run_sim(args, args.birks_on, out_on)
    run_sim(args, args.birks_off, out_off)

    on = read_events(out_on)
    off = read_events(out_off)

    raw_on = on["edep_scint_raw_MeV"]
    vis_on = on["edep_scint_MeV"]
    raw_off = off["edep_scint_raw_MeV"]
    vis_off = off["edep_scint_MeV"]

    n_on = len(raw_on)
    n_off = len(raw_off)
    if n_on == 0 or n_off == 0:
        raise AssertionError(f"no events parsed (on={n_on}, off={n_off})")

    # Consider only events that actually deposited (raw > 0).
    dep_on = [i for i in range(n_on) if raw_on[i] > 0]
    dep_off = [i for i in range(n_off) if raw_off[i] > 0]
    if not dep_on:
        raise AssertionError("no depositing events in the Birks-on run; cannot test suppression")
    if not dep_off:
        raise AssertionError("no depositing events in the Birks-off run; cannot test equality")

    # --- Assertion 1: with Birks ON, visible must be strictly below raw somewhere. ---
    gaps_on = [raw_on[i] - vis_on[i] for i in dep_on]
    max_gap = max(gaps_on)
    print(
        f"Birks ON  (kB={args.birks_on}): n={n_on} max(raw-visible)={max_gap:.6g} MeV "
        f"(epsilon={args.epsilon_mev:g})",
        file=sys.stderr,
    )
    if max_gap <= args.epsilon_mev:
        raise AssertionError(
            f"Birks is enabled (kB={args.birks_on}) but edep_scint_MeV never falls below "
            f"edep_scint_raw_MeV (max gap {max_gap:.6g} <= epsilon {args.epsilon_mev:g}). "
            "The visible-energy branch is not Birks-quenched — defect 2 has regressed."
        )

    # --- Assertion 2: with Birks OFF, visible and raw must agree to tolerance. ---
    max_diff_off = max(abs(raw_off[i] - vis_off[i]) for i in dep_off)
    worst = max(
        dep_off,
        key=lambda i: abs(raw_off[i] - vis_off[i]),
    )
    denom = max(abs(raw_off[worst]), 1e-30)
    rel_off = abs(raw_off[worst] - vis_off[worst]) / denom
    print(
        f"Birks OFF (kB={args.birks_off}): n={n_off} max|raw-visible|={max_diff_off:.6g} MeV "
        f"(worst rel={rel_off:.3g}, atol={args.equal_atol:g}, rtol={args.equal_rtol:g})",
        file=sys.stderr,
    )
    for i in dep_off:
        if not math.isclose(raw_off[i], vis_off[i], abs_tol=args.equal_atol, rel_tol=args.equal_rtol):
            raise AssertionError(
                f"with kB=0 the branches should agree, but event {i} differs: "
                f"raw={raw_off[i]:.10g} visible={vis_off[i]:.10g}"
            )

    print(
        "PASS: Birks visible branch is distinct from raw when kB>0 and equal when kB=0.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

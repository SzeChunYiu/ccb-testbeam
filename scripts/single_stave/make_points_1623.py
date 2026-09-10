#!/usr/bin/env python3
"""Build the issue #1623 light-vs-energy campaign point list.

Two samples per (species, energy):

  A  DISTRIBUTED  impact point uniform over the active stave area and incidence
     sampled isotropically inside a 10 deg cone -- the sample that carries the
     real spread in transverse distance to the WLS fibre, longitudinal distance
     to the SiPM, and path length through the scintillator.
  B  CENTRAL      x = y = 0, normal incidence -- the controlled reference the
     issue asks for alongside the distributed sample.

Energy grids are chosen from the stave geometry rather than round numbers:
the bar is 2.0 cm of polystyrene, so protons below roughly 50 MeV and deuterons
below roughly 66 MeV range out inside it (full-energy deposit), while higher
energies punch through and deposit only their dE/dx x path. Both regimes are
populated for p and d because the proton/deuteron compression the issue asks
about is a stopping-vs-punch-through comparison. Muons and charged pions at CCB
energies are near-minimum-ionizing and anchor the low-quenching end.
"""
from __future__ import annotations
import argparse

# Active-area sampling window. Stave half-extents are 25.0 cm (x, length) and
# 2.59 cm (y, width); the windows keep a margin so that a track tilted by the
# full cone half-angle still enters through the -z face (envelope preflight).
X_RANGE = (-22.0, 22.0)
Y_RANGE = (-2.20, 2.20)
THETA_SPREAD_DEG = 10.0

GRID = {
    # stopping regime below ~50 MeV, punch-through above
    "proton":   [5, 8, 12, 18, 25, 32, 40, 46, 55, 70, 90, 120, 160, 200],
    # stopping regime below ~66 MeV, punch-through above
    "deuteron": [6, 10, 16, 24, 32, 40, 48, 56, 62, 75, 90, 120, 160, 220],
    # near-minimum-ionizing anchors
    "mu-":      [20, 50, 100, 200, 500, 1000],
    "pi+":      [30, 60, 100, 200, 400],
    "pi-":      [30, 60, 100, 200, 400],
}

SEEDS_DISTRIBUTED = [1623, 1624]
SEEDS_CENTRAL = [1625]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nevents-distributed", type=int, default=4000)
    ap.add_argument("--nevents-central", type=int, default=2000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows: list[str] = []
    for part, energies in GRID.items():
        for e in energies:
            for seed in SEEDS_DISTRIBUTED:
                rows.append(
                    f"{part},{e},A,{X_RANGE[0]},{X_RANGE[1]},{Y_RANGE[0]},{Y_RANGE[1]},"
                    f"{THETA_SPREAD_DEG},{seed},{args.nevents_distributed}"
                )
            for seed in SEEDS_CENTRAL:
                rows.append(
                    f"{part},{e},B,0.0,0.0,0.0,0.0,0.0,{seed},{args.nevents_central}"
                )

    header = [
        "# issue #1623 single-stave light-vs-energy campaign",
        "# columns: particle,energy_MeV,sample,x_min_cm,x_max_cm,y_min_cm,y_max_cm,"
        "theta_spread_deg,seed,nevents",
        "# sample A = DISTRIBUTED (uniform over the active area, isotropic inside a "
        f"{THETA_SPREAD_DEG:g} deg cone)",
        "# sample B = CENTRAL controlled reference (x=y=0, normal incidence)",
        f"# active-area window x={X_RANGE} cm  y={Y_RANGE} cm "
        "(stave half-extents 25.0 / 2.59 cm)",
        "# readout end is +x at x = +25.0 cm; WLS fibres run along x at y = +/-1.0 cm",
        f"# points={len(rows)} events_distributed={args.nevents_distributed} "
        f"events_central={args.nevents_central}",
    ]
    with open(args.out, "w") as fh:
        fh.write("\n".join(header) + "\n")
        fh.write("\n".join(rows) + "\n")
    print(f"wrote {args.out}: {len(rows)} points")
    total = (len(rows) - sum(len(v) for v in GRID.values())) * args.nevents_distributed
    print(f"approx events: distributed={total} central="
          f"{sum(len(v) for v in GRID.values()) * args.nevents_central}")


if __name__ == "__main__":
    main()

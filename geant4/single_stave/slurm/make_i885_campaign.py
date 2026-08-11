#!/usr/bin/env python3
"""Generate the issue #885 / #1092 single-stave campaign points CSV.

Issue #885 (Dave): protons + deuterons at KE {2,5,8,12,20,30,50,80,120,150} MeV
at the default impact point, PLUS two representative energies (30, 80 MeV) per
particle repeated at entry points 5/10/30/45 cm from the readout end, to study
attenuation and timing. >=2 seeds per point for uncertainty.

Issue #1092: the two-fibre geometry has fibre centres at y=±1 cm. A campaign
that only samples y=0 measures the central-track response R(E,x,y=0), not a
stave-averaged response. This generator therefore adds an explicit transverse
y axis at {-1,0,+1} cm for representative energies at the default x.

Output columns match submit_calibration.sh:
    particle,energy_MeV,hit_x_cm,hit_y_cm,seed,nevents

Geometry convention (DetectorConstruction.hh):
  kStaveHalfX = 25 cm (stave x in [-25,+25]); the PHYSICAL READOUT SiPM is at
  the +x end (kReadout = Sensor_F1_PlusX). So an entry a distance d from the
  readout is at hit_x = READOUT_END_X_CM - d.
  Fibre centres at y = ±1 cm; active width y in [-2.59, +2.59] cm.

Phase-space support label:
  - main KE scan at (x=default, y=0) is a *central-track* response map;
  - transverse block states detector-response mapping over y, not a
    data-weighted stave average unless a measured p_data(y) is supplied.

Every value below is either dictated by the issue (energies/positions), a
documented geometry constant, or env-overridable (NEVENTS/SEEDS). No magic
numbers. Regenerate the CSV after editing:
    python3 slurm/make_i885_campaign.py --out slurm/points_i885_campaign.csv
"""
from __future__ import annotations
import argparse, os

# --- Issue-specified independent variables (not tunable engine params) ---
PARTICLES = ["proton", "deuteron"]
ENERGIES_MEV = [2, 5, 8, 12, 20, 30, 50, 80, 120, 150]
ATTENUATION_ENERGIES_MEV = [30, 80]          # representative energies per particle
DISTANCES_FROM_READOUT_CM = [5, 10, 30, 45]  # cm from +x readout end (issue spec)
# Issue #1092: fibre centres at ±1 cm; include y=0 central line for paired compare.
TRANSVERSE_Y_CM = [-1.0, 0.0, 1.0]
TRANSVERSE_ENERGIES_MEV = list(ATTENUATION_ENERGIES_MEV)

# --- Geometry constant (DetectorConstruction.hh kStaveHalfX; readout at +x) ---
READOUT_END_X_CM = float(os.environ.get("CCB_READOUT_END_X_CM", "25.0"))

# --- Campaign knobs (env-overridable) ---
DEFAULT_HIT_X_CM = float(os.environ.get("CCB_DEFAULT_HIT_X_CM", "0.0"))
DEFAULT_HIT_Y_CM = float(os.environ.get("CCB_DEFAULT_HIT_Y_CM", "0.0"))
NEVENTS = int(os.environ.get("CCB_I885_NEVENTS", os.environ.get("CCB_NEVENTS", "500")))
SEEDS = [int(s) for s in os.environ.get("CCB_I885_SEEDS", "101,102").split(",")]

PHASE_SPACE_SUPPORT = "central_track_plus_transverse_y_map"

# --- Angular phase space (#1093): explicit normal-incidence declaration ---
# PrimaryGeneratorAction supports theta_deg/phi_deg, but this campaign does not
# sweep them. submit_calibration.sh likewise omits --theta/--phi, so AppConfig
# defaults (0, 0) apply. Recorded here so undercoverage cannot be silent.
THETA_DEG = float(os.environ.get("CCB_I885_THETA_DEG", "0.0"))
PHI_DEG = float(os.environ.get("CCB_I885_PHI_DEG", "0.0"))
ANGULAR_COVERAGE = "NORMAL_INCIDENCE_ONLY"


def build_rows():
    rows = []
    seen = set()

    def add(row):
        key = row  # full tuple uniqueness
        if key in seen:
            return
        seen.add(key)
        rows.append(row)

    # (a) main KE scan at the default impact point (central-track y)
    for p in PARTICLES:
        for e in ENERGIES_MEV:
            for s in SEEDS:
                add((p, e, DEFAULT_HIT_X_CM, DEFAULT_HIT_Y_CM, s, NEVENTS))
    # (b) attenuation/timing: 2 energies x 4 distances-from-readout, per particle
    for p in PARTICLES:
        for e in ATTENUATION_ENERGIES_MEV:
            for d in DISTANCES_FROM_READOUT_CM:
                hx = READOUT_END_X_CM - d
                for s in SEEDS:
                    add((p, e, hx, DEFAULT_HIT_Y_CM, s, NEVENTS))
    # (c) transverse y map at default x for representative energies (#1092)
    for p in PARTICLES:
        for e in TRANSVERSE_ENERGIES_MEV:
            for hy in TRANSVERSE_Y_CM:
                for s in SEEDS:
                    add((p, e, DEFAULT_HIT_X_CM, float(hy), s, NEVENTS))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="slurm/points_i885_campaign.csv")
    ap.add_argument(
        "--allow-nonzero-angles-without-coverage-contract",
        action="store_true",
        help="escape hatch only; does NOT validate data angular phase space (#1093)",
    )
    args = ap.parse_args()
    if (THETA_DEG != 0.0 or PHI_DEG != 0.0) and not args.allow_nonzero_angles_without_coverage_contract:
        raise SystemExit(
            "I885 campaign is NORMAL_INCIDENCE_ONLY (#1093). Non-zero "
            f"CCB_I885_THETA_DEG/PHI_DEG ({THETA_DEG},{PHI_DEG}) require an explicit "
            "angular coverage contract plus --allow-nonzero-angles-without-coverage-contract "
            "(still does not claim data phase-space validation)."
        )
    rows = build_rows()
    with open(args.out, "w") as f:
        f.write("# issue #885/#1092 single-stave campaign. Columns: particle,energy_MeV,hit_x_cm,hit_y_cm,seed,nevents\n")
        f.write(f"# particles={PARTICLES} energies_MeV={ENERGIES_MEV}\n")
        f.write(f"# phase_space_support={PHASE_SPACE_SUPPORT}\n")
        f.write(
            f"# angular_coverage={ANGULAR_COVERAGE} theta_deg={THETA_DEG} phi_deg={PHI_DEG} "
            "(#1093; AppConfig defaults; submit_calibration does not pass --theta/--phi)\n"
        )
        f.write(
            "# claim_gate: angular/azimuth response from this campaign alone is BLOCKED / UNVALIDATED\n"
        )
        f.write(
            f"# central_track_default hit_x={DEFAULT_HIT_X_CM} hit_y={DEFAULT_HIT_Y_CM} cm "
            "(NOT automatically a stave-averaged response)\n"
        )
        f.write(
            f"# attenuation: distances_from_+x_readout_cm={DISTANCES_FROM_READOUT_CM} "
            f"-> hit_x=[{','.join(str(READOUT_END_X_CM-d) for d in DISTANCES_FROM_READOUT_CM)}] "
            f"at energies {ATTENUATION_ENERGIES_MEV} MeV per particle\n"
        )
        f.write(
            f"# transverse_y_cm={TRANSVERSE_Y_CM} at hit_x={DEFAULT_HIT_X_CM} "
            f"energies_MeV={TRANSVERSE_ENERGIES_MEV} "
            "(fibre centres at y=±1 cm; detector-response map, not data-weighted <R>)\n"
        )
        f.write(f"# seeds={SEEDS} nevents={NEVENTS} (readout at +x, READOUT_END_X_CM={READOUT_END_X_CM})\n")
        for p, e, hx, hy, s, n in rows:
            f.write(f"{p},{e},{hx},{hy},{s},{n}\n")
    n_main = len(PARTICLES) * len(ENERGIES_MEV) * len(SEEDS)
    n_att = len(PARTICLES) * len(ATTENUATION_ENERGIES_MEV) * len(DISTANCES_FROM_READOUT_CM) * len(SEEDS)
    # transverse unique beyond main: exclude y==DEFAULT already counted in main
    n_trans_unique = (
        len(PARTICLES)
        * len(TRANSVERSE_ENERGIES_MEV)
        * sum(1 for y in TRANSVERSE_Y_CM if float(y) != float(DEFAULT_HIT_Y_CM))
        * len(SEEDS)
    )
    print(
        f"wrote {args.out}: {len(rows)} points "
        f"(main={n_main} attenuation={n_att} transverse_unique={n_trans_unique} "
        f"phase_space_support={PHASE_SPACE_SUPPORT})"
    )


if __name__ == "__main__":
    main()

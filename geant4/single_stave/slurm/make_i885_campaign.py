#!/usr/bin/env python3
"""Generate the issue #885 single-stave campaign points CSV.

Issue #885 (Dave): protons + deuterons at KE {2,5,8,12,20,30,50,80,120,150} MeV
at the default impact point, PLUS two representative energies (30, 80 MeV) per
particle repeated at entry points 5/10/30/45 cm from the readout end, to study
attenuation and timing. >=2 seeds per point for uncertainty.

Output columns match submit_calibration.sh:
    particle,energy_MeV,hit_x_cm,hit_y_cm,seed,nevents

Angular phase space (#1093 / ARU-STAVE-ANGULAR-RESPONSE-001):
  This campaign is NORMAL_INCIDENCE_ONLY (theta_deg=0, phi_deg=0 via
  AppConfig defaults). It does NOT integrate over the real target-to-stave
  track angular distribution. Claims of angular/azimuth response closure
  from I885 alone are BLOCKED until a source-bound data angular map and
  theta/phi campaign coverage exist.

Geometry convention (DetectorConstruction.hh):
  kStaveHalfX = 25 cm (stave x in [-25,+25]); the PHYSICAL READOUT SiPM is at
  the +x end (kReadout = Sensor_F1_PlusX). So an entry a distance d from the
  readout is at hit_x = READOUT_END_X_CM - d.

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

# --- Geometry constant (DetectorConstruction.hh kStaveHalfX; readout at +x) ---
READOUT_END_X_CM = float(os.environ.get("CCB_READOUT_END_X_CM", "25.0"))

# --- Campaign knobs (env-overridable) ---
DEFAULT_HIT_X_CM = float(os.environ.get("CCB_DEFAULT_HIT_X_CM", "0.0"))
DEFAULT_HIT_Y_CM = float(os.environ.get("CCB_DEFAULT_HIT_Y_CM", "0.0"))
NEVENTS = int(os.environ.get("CCB_I885_NEVENTS", os.environ.get("CCB_NEVENTS", "500")))
SEEDS = [int(s) for s in os.environ.get("CCB_I885_SEEDS", "101,102").split(",")]

# --- Angular phase space (#1093): explicit normal-incidence declaration ---
# PrimaryGeneratorAction supports theta_deg/phi_deg, but this campaign does not
# sweep them. submit_calibration.sh likewise omits --theta/--phi, so AppConfig
# defaults (0, 0) apply. Recorded here so undercoverage cannot be silent.
THETA_DEG = float(os.environ.get("CCB_I885_THETA_DEG", "0.0"))
PHI_DEG = float(os.environ.get("CCB_I885_PHI_DEG", "0.0"))
ANGULAR_COVERAGE = "NORMAL_INCIDENCE_ONLY"


def build_rows():
    rows = []
    # (a) main KE scan at the default impact point
    for p in PARTICLES:
        for e in ENERGIES_MEV:
            for s in SEEDS:
                rows.append((p, e, DEFAULT_HIT_X_CM, DEFAULT_HIT_Y_CM, s, NEVENTS))
    # (b) attenuation/timing: 2 energies x 4 distances-from-readout, per particle
    for p in PARTICLES:
        for e in ATTENUATION_ENERGIES_MEV:
            for d in DISTANCES_FROM_READOUT_CM:
                hx = READOUT_END_X_CM - d
                for s in SEEDS:
                    rows.append((p, e, hx, DEFAULT_HIT_Y_CM, s, NEVENTS))
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
        f.write("# issue #885 single-stave campaign. Columns: particle,energy_MeV,hit_x_cm,hit_y_cm,seed,nevents\n")
        f.write(f"# particles={PARTICLES} energies_MeV={ENERGIES_MEV}\n")
        f.write(f"# default hit_x={DEFAULT_HIT_X_CM} hit_y={DEFAULT_HIT_Y_CM} cm\n")
        f.write(
            f"# angular_coverage={ANGULAR_COVERAGE} theta_deg={THETA_DEG} phi_deg={PHI_DEG} "
            "(#1093; AppConfig defaults; submit_calibration does not pass --theta/--phi)\n"
        )
        f.write(
            "# claim_gate: angular/azimuth response from this campaign alone is BLOCKED / UNVALIDATED\n"
        )
        f.write(f"# attenuation: distances_from_+x_readout_cm={DISTANCES_FROM_READOUT_CM} "
                f"-> hit_x=[{','.join(str(READOUT_END_X_CM-d) for d in DISTANCES_FROM_READOUT_CM)}] "
                f"at energies {ATTENUATION_ENERGIES_MEV} MeV per particle\n")
        f.write(f"# seeds={SEEDS} nevents={NEVENTS} (readout at +x, READOUT_END_X_CM={READOUT_END_X_CM})\n")
        for p, e, hx, hy, s, n in rows:
            f.write(f"{p},{e},{hx},{hy},{s},{n}\n")
    n_main = len(PARTICLES) * len(ENERGIES_MEV) * len(SEEDS)
    n_att = len(PARTICLES) * len(ATTENUATION_ENERGIES_MEV) * len(DISTANCES_FROM_READOUT_CM) * len(SEEDS)
    print(f"wrote {args.out}: {len(rows)} points (main={n_main} attenuation={n_att})")


if __name__ == "__main__":
    main()

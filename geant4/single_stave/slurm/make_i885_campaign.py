#!/usr/bin/env python3
"""Generate the issue #885 / #1092 / #1093 single-stave campaign points CSV.

Primary angular coverage is NORMAL_INCIDENCE_ONLY (#1093). Non-zero
CCB_I885_THETA_DEG/PHI_DEG fail closed unless an explicit escape hatch is
passed. An additional MC sensitivity angular probe grid is emitted as
8-column rows labelled DATA_ANGLE_DISTRIBUTION_UNKNOWN (not data truth).
"""
from __future__ import annotations

import argparse
import os

PARTICLES = ["proton", "deuteron"]
ENERGIES_MEV = [2, 5, 8, 12, 20, 30, 50, 80, 120, 150]
ATTENUATION_ENERGIES_MEV = [30, 80]
DISTANCES_FROM_READOUT_CM = [5, 10, 30, 45]
TRANSVERSE_Y_CM = [-1.0, 0.0, 1.0]
FIBRE_Y_CM = (-1.0, 1.0)
TRANSVERSE_ENERGIES_MEV = list(ATTENUATION_ENERGIES_MEV)

READOUT_END_X_CM = float(os.environ.get("CCB_READOUT_END_X_CM", "25.0"))
DEFAULT_HIT_X_CM = float(os.environ.get("CCB_DEFAULT_HIT_X_CM", "0.0"))
DEFAULT_HIT_Y_CM = float(os.environ.get("CCB_DEFAULT_HIT_Y_CM", "0.0"))
NEVENTS = int(os.environ.get("CCB_I885_NEVENTS", os.environ.get("CCB_NEVENTS", "500")))
SEEDS = [int(s) for s in os.environ.get("CCB_I885_SEEDS", "101,102").split(",")]

PHASE_SPACE_SUPPORT = "central_track_plus_transverse_y_map"
THETA_DEG = float(os.environ.get("CCB_I885_THETA_DEG", "0.0"))
PHI_DEG = float(os.environ.get("CCB_I885_PHI_DEG", "0.0"))
ANGULAR_COVERAGE = "NORMAL_INCIDENCE_ONLY"

ANGULAR_PROBE_PARTICLE = "proton"
ANGULAR_PROBE_ENERGY_MEV = 30
ANGULAR_PROBE_THETA_DEG = (0.0, 10.0)
ANGULAR_PROBE_PHI_DEG = (0.0, 90.0)
ANGULAR_PROBE_STATUS = "MC_SENSITIVITY_GRID_DATA_ANGLE_UNKNOWN"


def build_rows():
    rows = []
    seen = set()

    def add(row):
        if row in seen:
            return
        seen.add(row)
        rows.append(row)

    for p in PARTICLES:
        for e in ENERGIES_MEV:
            for s in SEEDS:
                add((p, e, DEFAULT_HIT_X_CM, DEFAULT_HIT_Y_CM, s, NEVENTS))
    for p in PARTICLES:
        for e in ATTENUATION_ENERGIES_MEV:
            for d in DISTANCES_FROM_READOUT_CM:
                hx = READOUT_END_X_CM - d
                for s in SEEDS:
                    add((p, e, hx, DEFAULT_HIT_Y_CM, s, NEVENTS))
    for p in PARTICLES:
        for e in TRANSVERSE_ENERGIES_MEV:
            for hy in TRANSVERSE_Y_CM:
                for s in SEEDS:
                    add((p, e, DEFAULT_HIT_X_CM, float(hy), s, NEVENTS))
    for th in ANGULAR_PROBE_THETA_DEG:
        for ph in ANGULAR_PROBE_PHI_DEG:
            for s in SEEDS:
                add(
                    (
                        ANGULAR_PROBE_PARTICLE,
                        ANGULAR_PROBE_ENERGY_MEV,
                        DEFAULT_HIT_X_CM,
                        DEFAULT_HIT_Y_CM,
                        s,
                        NEVENTS,
                        th,
                        ph,
                    )
                )
    return rows


def main_with_out(out_path: str, allow_nonzero: bool = False) -> None:
    if (THETA_DEG != 0.0 or PHI_DEG != 0.0) and not allow_nonzero:
        raise SystemExit(
            "I885 campaign is NORMAL_INCIDENCE_ONLY (#1093). Non-zero "
            f"CCB_I885_THETA_DEG/PHI_DEG ({THETA_DEG},{PHI_DEG}) require an explicit "
            "angular coverage contract plus --allow-nonzero-angles-without-coverage-contract "
            "(still does not claim data phase-space validation)."
        )
    rows = build_rows()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(
            "# issue #885/#1092/#1093 single-stave campaign. "
            "Columns: particle,energy_MeV,hit_x_cm,hit_y_cm,seed,nevents[,theta_deg,phi_deg]\n"
        )
        f.write(f"# particles={PARTICLES} energies_MeV={ENERGIES_MEV}\n")
        f.write(f"# phase_space_support={PHASE_SPACE_SUPPORT}\n")
        f.write(
            f"# angular_coverage={ANGULAR_COVERAGE} theta_deg={THETA_DEG} phi_deg={PHI_DEG} "
            "(#1093; AppConfig defaults; submit_calibration does not pass --theta/--phi)\n"
        )
        f.write(
            "# claim_gate: angular/azimuth response from this campaign alone is "
            "BLOCKED / UNVALIDATED\n"
        )
        f.write(f"# default hit_x={DEFAULT_HIT_X_CM} hit_y={DEFAULT_HIT_Y_CM} cm\n")
        f.write(
            f"# attenuation: distances_from_+x_readout_cm={DISTANCES_FROM_READOUT_CM} "
            f"-> hit_x=[{','.join(str(READOUT_END_X_CM - d) for d in DISTANCES_FROM_READOUT_CM)}] "
            f"at energies {ATTENUATION_ENERGIES_MEV} MeV per particle\n"
        )
        f.write(
            f"# transverse_y (#1092): y={TRANSVERSE_Y_CM} cm at E={TRANSVERSE_ENERGIES_MEV} MeV; phase_space_status=MC_PHASE_SPACE_PROBE_DATA_Y_DISTRIBUTION_UNKNOWN\n"
        )
        f.write(
            f"# angular_probe (#1093): particle={ANGULAR_PROBE_PARTICLE} "
            f"E={ANGULAR_PROBE_ENERGY_MEV} MeV "
            f"theta_deg={list(ANGULAR_PROBE_THETA_DEG)} "
            f"phi_deg={list(ANGULAR_PROBE_PHI_DEG)}; "
            f"phase_space_status={ANGULAR_PROBE_STATUS}; "
            "DATA_ANGLE_DISTRIBUTION_UNKNOWN\n"
        )
        f.write(
            f"# seeds={SEEDS} nevents={NEVENTS} "
            f"(readout at +x, READOUT_END_X_CM={READOUT_END_X_CM})\n"
        )
        for row in rows:
            f.write(",".join(str(x) for x in row) + "\n")
    n6 = sum(1 for r in rows if len(r) == 6)
    n8 = sum(1 for r in rows if len(r) == 8)
    print(f"wrote {out_path}: {len(rows)} points (legacy6={n6} angular8={n8})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="slurm/points_i885_campaign.csv")
    ap.add_argument(
        "--allow-nonzero-angles-without-coverage-contract",
        action="store_true",
        help="escape hatch only; does NOT validate data angular phase space (#1093)",
    )
    args = ap.parse_args()
    main_with_out(args.out, args.allow_nonzero_angles_without_coverage_contract)


if __name__ == "__main__":
    main()

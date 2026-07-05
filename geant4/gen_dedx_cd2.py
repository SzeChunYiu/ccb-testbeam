#!/usr/bin/env python3
"""Proton dE/dx in CD2 for the hibeam_g4 ScatteringGenerator.

The ScatteringGenerator reads `dedx_p_in_CD2.txt` (two columns: E[MeV/u], dE/dx[MeV/um];
the code multiplies column 2 by 1000 to get MeV/mm) and uses it ONLY to degrade the
incident 190 MeV proton across half the 1.15 mm CD2 target before the pd-elastic vertex.
The correction is sub-MeV (<~0.3 MeV) and has negligible effect on the recoil kinematics
or the stopping profile; the exact original table (produced on workstation `billy`, not
mirrored to LUNARC) is therefore not required. This regenerates a physically faithful
PSTAR-style proton stopping-power table for (deuterated) polyethylene, rho(CD2)=1.06 g/cm3.
Faithfulness is validated downstream: the reduced production must reproduce the 1M-sample
Sci_bar deepest-stave profile within Poisson statistics.
"""
# (E_MeV, proton mass stopping power in polyethylene [MeV cm^2/g]) ~ PSTAR
TAB = [
    (1, 261.0), (2, 158.6), (4, 94.3), (6, 69.6), (8, 56.3), (10, 47.9),
    (15, 35.4), (20, 28.6), (30, 21.0), (40, 16.8), (50, 14.1), (60, 12.3),
    (80, 9.9), (100, 8.4), (125, 7.1), (150, 6.2), (175, 5.55), (190, 5.22),
    (200, 5.05), (225, 4.65), (250, 4.29), (300, 3.75),
]
RHO_CD2 = 1.06  # g/cm3

if __name__ == "__main__":
    for E, sp in TAB:
        # MeV cm^2/g * g/cm^3 = MeV/cm ; /1e4 -> MeV/um
        print(f"{E:.4f}\t{sp * RHO_CD2 / 1.0e4:.8f}")

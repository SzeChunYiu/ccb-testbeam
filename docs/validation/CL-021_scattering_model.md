# CL-021 — MV3 scattering-model (p+CD2 CM-angle cross-section weighting)

**Status: OPEN — hypothesis FALSIFIED, infrastructure delivered.**

The cross-section `sigma_pd_cm_190.txt` is correctly wired into
`ScatteringGenerator.cc` as an inverse-CDF sampler
(`p(theta) ~ sigma(theta)*sin(theta)`), replacing uniform-in-[0,pi].
Verified at truth level (lab-angle distribution forward-peaks as expected).

**The fix does NOT close the MV3 B2 gap — it widens it.**
B2: 0.475 (uniform) -> 0.253 (CS-weighted); data 0.933.
B8: 0.181 -> 0.414 (protons punch deeper; mean Ekin 105 -> 160 MeV).

Cause: forward p+d elastic kinematics produce HIGH-energy forward protons,
the opposite of the data low-energy-dominant B2 population. The uniform
sampler was accidentally closer to the data.

**Re-attribution**: the MV3 B2 deficit is NOT the angular sampler. It is the
elastic p+d SOURCE spectrum. Next lead: inelastic nuclear-reaction secondaries
and/or the recoil-deuteron channel, plus data Sample-I selection bias.

Recommendation: KEEP the CS-weighted sampler (physically correct). Do NOT mark
CL-021 resolved. See `reports/scatter_cl021/REPORT.md` for full numbers + plots.

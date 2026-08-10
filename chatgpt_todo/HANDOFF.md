# Latest Handoff

## Selected atom: source interpolation order on identical measured support (#1178)

Protected `main` at the branch point is `a1bcb6a68630845c31c0b8ebcd5b45de0cea1dd6`. The numerical inverse-CDF repair is on main, but #1178 remains open because compiled Geant4 closure, support physics, runtime fail-closed behavior (#1182), source uncertainty (#1179), manifest serialization, and downstream response propagation are unresolved.

### Contract and mechanism split

The exact source table is `geant4/src_patch/sigma_pd_cm_190.txt`, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, 28 rows over 26.49–169.78 deg CM. The physical polar density is proportional to `sigma(theta) sin(theta)`.

The current reference `linear_node_pdf_exact_inverse_v1` first forms tabulated polar-density nodes `g_i=sigma_i sin(theta_i)` and linearly interpolates `g`. The new comparison model `linear_cross_section_then_jacobian_v1` linearly interpolates the measured observable `sigma=dσ/dΩ` and only then multiplies by `sin(theta)`. Both pass exactly through every source node and use `measured_table_support_truncate_v1`, but they are not equivalent between nodes.

### Executed result

`tools/audit/research_sigma_cm_interpolation_sensitivity.py` analytically integrates both source laws and finds a maximum normalized-CDF difference `0.0010129801982659559` at `43.94458149140975 deg`. The alternative mean angle shifts by `-0.024267831224125052 deg`; the median shifts by `-0.05619069758156213 deg`; the 95th percentile shifts by `+0.13082849690529305 deg`.

The strongest falsifier is representation refinement. Inserting one midpoint per interval with `sigma_mid=(sigma_left+sigma_right)/2` is exactly redundant under sigma-linear interpolation: its normalized-CDF change is `1.4432899320127035e-15`. The same inserted source representation changes the current node-PDF-linear CDF by `0.000768558730840585`. Thus the two descriptions are distinct model classes, not duplicate parameterizations.

Local focused tests before push returned `4 passed in 0.05s`. An independent 500001-point dense numerical quadrature check agreed with the analytic normalization/mean to O(1e-11) and O(1e-9 deg), respectively. Machine-readable output is `results/research/sigma_cm_interpolation_sensitivity_v1.json`; the full equations, hypotheses, review votes and child atoms are archived in `chatgpt_todo/archive/2026-08-10T195100Z_ARU-MC-CS-INTERPOLATION.md`.

### Four review votes

- **Few-nucleon source physicist — REVISE:** retain the current interpolation as a named reference, not a uniquely source-authorized physical law.
- **Adversarial numerical reviewer — ACCEPT distinction / BLOCK hidden equivalence:** redundant-knot invariance sharply separates the model classes.
- **Independent statistics/UQ reviewer — ACCEPT deterministic sensitivity / BLOCK confidence language:** no probability law over interpolation families exists, so `0.001013` is not a one-sigma band.
- **Claims/provenance reviewer — BLOCK CL-021 promotion:** source/runtime/support/UQ/detector gates remain open.

### Parallel #1179 / PR #1186 state

PR #1186's first exact-head run `31422297344` had 1450 passing tests but failed enforcement because one new test searched for literal `Do not`, while the sidecar correctly expressed the same semantic boundary with `does not`. The test was repaired at head `4a2d1909b681517eee72389bf5f8d3604e4b8f54` to assert the substantive covariance/non-iid wording instead. Its replacement exact-head CI is still in progress; do not merge or call #1186 validated before that run succeeds.

### Next

Open/validate the interpolation-sensitivity PR and cross-link it to #1178; keep the current generator mode unchanged because this atom is sensitivity research, not a model-selection result. If compiled Geant4 becomes available, the highest-value next step is paired generator-only propagation of surviving interpolation/support models with exact seed/event/source provenance. Without compiled runtime, continue #1179 only after its repaired exact-head CI succeeds, and then investigate an independently source-justified interpolation/support family rather than tuning to detector agreement.

No beam ROOT data were opened, no production Geant4 campaign was run, and no B2/B8, PID, timing, penetration, energy, pile-up, ESS, p-value or detector-performance quantity was regenerated or promoted.

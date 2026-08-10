# Active Task

- **Task ID:** `ARU-MC-CS-UQ-INTERPOLATION-COMPAT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Branch-point protected main:** `af0c3989df0009fb74d5b820123e5c7cbcbce67f`; PR #1186 source-UQ sensitivity is merged after exact-head MC Validation run `31428708910` succeeded.
- **Selected atom:** cross-atom compatibility of the two surviving measured-support interpolation classes with the explicit nonprobabilistic ±3% Table-VI node box under #1179.
- **Input contract:** `geant4/src_patch/sigma_pd_cm_190.txt`, 640 bytes, 28 rows, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, 26.49–169.78 deg CM, `dσ/dΩ` in mb/sr with published row statistical uncertainties.
- **Competing worlds:** current `linear_node_pdf_exact_inverse_v1`; alternative `linear_cross_section_then_jacobian_v1`; each propagated through the same explicit `[0.97,1.03] sigma_i` box. No probability weights are assigned to interpolation classes or box corners.
- **Executed result:** the alternative central curve has zero violation of the current-mode 3% box on the 10,001-point grid, but the alternative **box image** extends beyond the current box by `0.0010650343985590949` upward at 39.586706 deg and `0.0002537872354466675` downward at 145.879228 deg. Therefore central-curve containment is not cross-model closure.
- **Union sensitivity:** relative to the current nominal source, the two-model/3%-box union reaches `+0.015299817076167732` CDF at 43.168956 deg and `-0.014380572923809676` at 46.951812 deg; mean-theta union is 56.02560085079668–57.5322672970398 deg. This is a deterministic sensitivity set, not a confidence band.
- **Conditional statistical reference:** max pointwise diagonal-row-statistical CDF standard uncertainty is `0.0004453566889758832` (current) versus `0.0004435837618530407` (alternative); these are conditional delta-method diagnostics and are not combined in quadrature with model-form/box sensitivities.
- **Implementation:** `tools/audit/research_sigma_cm_uq_interpolation_compatibility.py`, `tests/test_sigma_cm_uq_interpolation_compatibility.py`, `results/research/sigma_cm_uq_interpolation_compatibility_v1.json`, and immutable ARU archive on branch `research/mc-source-uq-interpolation-compat`.
- **Local validation:** Python 3.13.5, no RNG; focused equivalent regression returned `4 passed in 11.97s`. Exact-head repository CI is required before merge.
- **Claim state:** CL-021 remains `OPEN / GATED`; no production Geant4 or detector result was regenerated.
- **Open dependencies:** #1179 source covariance/decomposition; #1178 support-model sensitivity; #1182 compiled fail-closed runtime readiness; production manifest binding; generator-level propagation; full detector-response propagation.
- **Status:** `ACTIVE / CROSS_ATOM_SOURCE_SENSITIVITY_EXECUTED / EXACT_HEAD_CI_PENDING / SOURCE_COVARIANCE_BLOCKED / SUPPORT_PHYSICS_GATED / GEANT4_RUNTIME_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

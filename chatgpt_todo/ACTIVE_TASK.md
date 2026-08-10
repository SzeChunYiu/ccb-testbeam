# Active Task

- **Task ID:** `ARU-MC-CS-INTERPOLATION-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Branch-point protected main:** `a1bcb6a68630845c31c0b8ebcd5b45de0cea1dd6`.
- **Selected atom:** interpolation-order model form for the exact 190 MeV p-d source on the already-declared measured-support reference: `linear_node_pdf_exact_inverse_v1` versus `linear_cross_section_then_jacobian_v1`.
- **Input contract:** `geant4/src_patch/sigma_pd_cm_190.txt`, 640 bytes, 28 rows, SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, 26.49–169.78 deg CM, `dσ/dΩ` in mb/sr.
- **Exact result:** the two models agree at every tabulated cross-section node but differ between nodes because interpolation and multiplication by `sin(theta)` do not commute. Their normalized CDFs differ by at most `0.0010129801982659559` at `43.94458149140975 deg`; the alternative mean angle is lower by `0.024267831224125052 deg` and its median is lower by `0.05619069758156213 deg`.
- **Adversarial representation control:** inserting one exact sigma-linear midpoint per original interval changes the sigma-linear-then-Jacobian model by only `1.4432899320127035e-15` in CDF but changes the current node-PDF-linear model by `0.000768558730840585`. They are therefore distinct model classes, not duplicate parameterizations.
- **Implementation:** `tools/audit/research_sigma_cm_interpolation_sensitivity.py`, focused regression tests, machine-readable result `results/research/sigma_cm_interpolation_sensitivity_v1.json`, and immutable ARU archive.
- **Local deterministic validation before push:** `python -m pytest -q tests/test_sigma_cm_interpolation_sensitivity.py` -> `4 passed in 0.05s`; an independent 500001-point dense quadrature check agreed with the analytic integrals to O(1e-11) normalization / O(1e-9 deg) mean-angle scale.
- **Parallel source-UQ lane:** PR #1186 initially failed only because a brittle test searched for literal `Do not` while the sidecar expressed the same boundary as `does not`; the branch was repaired at `4a2d1909b681517eee72389bf5f8d3604e4b8f54` with semantic assertions. Its new exact-head CI is still running and must pass before merge.
- **Claim state:** CL-021 remains `OPEN / GATED`. This result is deterministic source-model sensitivity, not a confidence band, not detector validation, and not evidence that either interpolation is uniquely physical.
- **Open dependencies:** #1178 support-model sensitivity + compiled generator closure; #1179 source covariance/UQ; #1182 fail-closed runtime readiness; production manifest binding; full detector-response propagation.
- **Status:** `ACTIVE / DETERMINISTIC_INTERPOLATION_SENSITIVITY_EXECUTED / PR_AND_EXACT_HEAD_CI_PENDING / GEANT4_RUNTIME_BLOCKED / SOURCE_UQ_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

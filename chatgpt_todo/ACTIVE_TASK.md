# Active Task

- **Task ID:** `ARU-MC-CS-UNCERTAINTY-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T185000Z`
- **Branch-point protected main:** `f5f96951c3f56986769a16cd53ab8e23dee3e287` (the exact-inverse measured-support central-value sampler from #1178 is already on main).
- **Selected atom:** Ermisch Table-VI uncertainty statements/third-column statistics -> explicit source nuisance/sensitivity contract -> normalized `theta_cm` source law -> CL-021/source-sensitive downstream claims.
- **Primary-source clarification:** at 190 MeV the paper reports 3% point-to-point systematic and total systematic <4.5%. Sec. IV D constructs the point-to-point term as an extra per-point error needed to obtain approximately unit chi-square for a high-order angular cross-section fit after discussing target-thickness variation and background-subtraction systematics. No row covariance matrix is published in the retained table; `3%` therefore does not uniquely identify iid Gaussian row nuisances.
- **Implemented deterministic research on `research/mc-source-uncertainty-envelope`:** `tools/audit/research_sigma_cm_source_uncertainty.py`, focused tests, `results/research/sigma_cm_source_uncertainty_v1.json`, source-sidecar clarification, CL-021 governance and immutable ARU record.
- **Exact central-value reference:** table SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`; interpolation `linear_node_pdf_exact_inverse_v1`; support `measured_table_support_truncate_v1`; nominal normalization `1.19776307651449`; mean `theta_cm=56.78396200051643 deg`.
- **Executed sensitivity:** fully common +4.5% source scale cancels normalized shape to `3.3306690738754696e-16`; a deliberately nonprobabilistic independent-node ±3% box gives CDF excursions `+0.01430729974634637/-0.014380572923809676` near 46.951812 deg and mean-angle range `56.050251002153615–57.5322672970398 deg`; alternating ±3% controls give only ~`0.001457` CDF sup shift, exposing correlation-model dependence.
- **Conditional statistical reference:** diagonal delta-method using the published row statistical errors gives max pointwise CDF standard uncertainty `0.0004453566889758832` near 49.488045 deg and mean-angle standard uncertainty `0.02252797870713097 deg`; this is conditional, not a systematic covariance reconstruction.
- **Validation:** independent local Python 3.13.5 deterministic execution; focused subset `4 passed` in 26.92 s. Repository exact-head CI remains mandatory before merge.
- **Claim state:** CL-021 remains `OPEN / GATED`. #1179 remains open because no unique systematic covariance is recovered; #1178 support sensitivity and #1182 compiled fail-closed source readiness remain separate blockers.
- **Status:** `ACTIVE / SOURCE_FACTS_BOUND / DETERMINISTIC_SENSITIVITY_IMPLEMENTED / COVARIANCE_UNIDENTIFIED / EXACT_HEAD_CI_PENDING / GEANT4_PROPAGATION_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

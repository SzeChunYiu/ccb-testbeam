# Active Task

- **Task ID:** AUD-DELTAE-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T060608Z
- **Initial remote main SHA:** `421aafd6894b6ba3b92b98f616141084742b6812`
- **Scope completed:** remediate the canonical ΔE-E bridge so every present net-amplitude row is finite numeric before event/stave aggregation, pivoting, or missing-layer zero filling.
- **Former source:** Git blob `7f50ce667a6cde07e94717d0187831da4d8459ac`; NaN B2 could disappear during pivot and become `amp_B2=0.0`, while positive infinity was retained.
- **Corrected source:** implementation commit `910efe6b37b3d16a31275e9c0502ee2bd5512ab9`; Git blob `2820c461508990d743cc53754c33ec2934a3c9ad`; exact SHA-256 `8295d117b068795ea48015c14cbd7531094dae5931283e5e9205121d5eaa8011`.
- **Correction:** `pd.to_numeric(errors="coerce")` plus `np.isfinite` rejection before aggregation; genuine absent layers remain zero-filled only after validation; result metadata records `amplitude_validation` and `missing_layer_policy`.
- **Validation:** focused `py_compile` passed; existing bridge suite plus remediation regression returned `17 passed in 0.31s`; executable audit returned `VALIDATED` with zero issues; JSON and SVG parsed; changed Python lines are at most 95 characters.
- **Evidence:** `docs/validation/deltae_net_input_integrity_audit.md`, JSON/SVG files, and immutable archive `chatgpt_todo/archive/2026-07-25T060608Z_AUD-DELTAE-003_NET_INPUT_REMEDIATION.md`.
- **Scientific boundary:** synthetic software/provenance validation only; no exact A-002 input, production rerun, stopping distribution, calibration, uncertainty budget, PID, or detector result.
- **Status:** COMPLETE for the net-input software remediation. A-002 scientific acceptance remains PARTIAL/BLOCKED under `BLK-AMP-001`, `AUD-DELTAE-001`, and `AUD-DELTAE-002`.

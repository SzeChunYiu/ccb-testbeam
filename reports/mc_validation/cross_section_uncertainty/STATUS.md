# Cross-Section Uncertainty Propagation Status (#1179)

## Current State: PARTIAL (contract declared, propagation not implemented)

### Completed (PR #1325)

1. Fail-closed contract declaration in ScatteringGenerator.cc:
   - uncertainty_contract=not_propagated_issue_1179
   - Sampler reads only 2 columns; 3rd column (stat) not consumed

2. Audit tool extension in tools/audit/research_sigma_cm_sampler_contract.py:
   - _statistical_uncertainty_audit(): per-node fractional uncertainty
   - _systematic_uncertainty_envelope_audit(): sinusoidal_taper model
   - audit_sampler() output includes uncertainty.propagation_status = OPEN_ISSUE_1179

### Not Yet Implemented

1. Stochastic reweighting variants: No sensitivity branches that sample from
   perturbed cross-section tables (statistical or systematic envelopes)

2. Fail-closed contract IDs: No mechanism to propagate uncertainty through
   the sampler with identifiable variant IDs

3. Downstream observable sensitivity: No documented effect on theta_cm
   distributions or other truth observables

### Source Uncertainty Components

- Statistical: Per-point values in Table VI column 3 (28 points)
- Systematic: 3% point-to-point + 4.5% total at 190 MeV
- Interpolation: Uncertainty outside measured support

### Implementation Plan (Future)

1. Add --uncertainty-mode CLI flag to sampler
2. Implement perturbation functions for stat and syst variants
3. Generate variant MC campaigns with separate output files
4. Compare theta_cm and truth observable distributions

## References

- Issue #1179
- PR #1325
- Ermisch et al., PRC 71 064004 (2005) Table VI

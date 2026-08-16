# Issue #1053: Legacy PrimaryWeight=σ(theta_lab) Retirement Closure Study

- **Ticket ID:** `${REPORT_ID}.1053_weight_closure`
- **Issue:** #1053
- **Date:** 2026-08-14
- **Git commit:** $(cd ccb-testbeam && git rev-parse HEAD 2>/dev/null || echo "worktree")
- **Depends on:** PR #1329 (legacy CM importance-weight adapter), PR #1354 (production receipt)

## Question

Does the current patched direct-CDF generator (unit event weight) produce the same generator-level physics as the legacy uniform-theta_cm generator with corrected analysis weight `w*(theta_cm) ∝ sigma_cm(theta_cm) * sin(theta_cm)`?

## Background

The historical generator used:
```
theta3cm = pi * G4UniformRand();  // Uniform proposal
particle->SetWeight(EvalWeight(theta3));  // Wrong: sigma(theta_lab)
```

S21b reconstructed the stored weight and found `PrimaryWeight = sigma(theta_lab)` with R²=1, which is NOT the intended CM importance weight.

The current patched source samples theta_cm directly from a `sigma*sin(theta)` CDF with unit event weight.

## Method

### Pure-Python Samplers

Three samplers were implemented in `tests/test_weight_closure_issue_1053.py`:

1. **DirectCDFSampler**: Matches the patched C++ `SampleThetaCM()` implementation
   - Builds CDF from `p(theta) ∝ sigma_cm(theta_cm) * sin(theta_cm)`
   - Uses trapezoidal integration and piecewise-linear inverse CDF
   - Restricted to measured support [26.49, 169.78] degrees

2. **LegacyUniformSampler**: Mimics the old generator
   - Uniform proposal `theta_cm ~ U[support_min, support_max]`
   - Corrected weight `w = sigma_cm(theta_cm) * sin(theta_cm)`

3. **UncorrectedLegacySampler**: Negative control
   - Same uniform proposal
   - WRONG weight `w = sigma_cm(theta_cm)` (missing sin factor)

### Statistical Tests

Two-sample Kolmogorov-Smirnov test with weighted ECDFs:
- 500 bootstrap iterations for p-value estimation
- Alpha = 0.05 for all tests
- Tested observables: `theta_cm`, `theta_lab` (generator-level only, no detector response)

## Results

### Closure Item 1: Direct-CDF vs Corrected-LLegacy

| Observable | KS Statistic | P-value | Verdict |
|------------|--------------|---------|---------|
| theta_cm | 0.0108 | 0.802 | PASS |
| theta_lab | 0.0108 | 0.802 | PASS |

**Interpretation**: Cannot reject the null hypothesis that both methods produce the same weighted distribution. The direct-CDF sampler and the legacy sampler with corrected weight are statistically equivalent on generator-level observables.

### Closure Item 2: Negative Control (Uncorrected Legacy)

| Observable | KS Statistic | P-value | Verdict |
|------------|--------------|---------|---------|
| theta_cm | 0.0886 | 0.000 | PASS (detects bug) |
| theta_lab | 0.0886 | 0.000 | PASS (detects bug) |

**Interpretation**: The test has power. The uncorrected weight (missing sin factor) produces a statistically different distribution, correctly identifying the legacy bug.

### Closure Item 3: Representation-Splitting Invariant

| Observable | KS Statistic | P-value | Verdict |
|------------|--------------|---------|---------|
| theta_cm | 1.6e-13 | 1.000 | PASS |
| theta_lab | 1.6e-13 | 1.000 | PASS |

**Interpretation**: Duplicating events with divided weight (k=3) produces identical normalized distributions. The representation-splitting invariant holds at machine precision.

### Supporting Tests

- **Sigma table contract**: 28 rows, support [26.49, 169.78] degrees, sigma in [0.126, 6.005] mb/sr
- **Sample size consistency**: Closure holds for N=100, 1000, 10000 events

## Equations

### Target Density

For differential cross section `dσ/dΩ = sigma_cm(theta_cm)`, the desired polar-angle density after integrating over azimuth is:

```
p(theta_cm) dθ_cm = [sigma_cm(theta_cm) * sin(theta_cm)] dθ_cm
```

### Legacy Proposal and Weight

```
q(theta_cm) = 1 / (support_max - support_min)  [uniform over measured support]
w*(theta_cm) = p(theta_cm) / q(theta_cm) ∝ sigma_cm(theta_cm) * sin(theta_cm)
```

### Direct-CDF Sampling

```
CDF(theta) = ∫_{support_min}^{theta} sigma_cm(θ') * sin(θ') dθ'
theta_cm = CDF^{-1}(U)  where U ~ Uniform(0, 1)
event_weight = 1.0
```

## Verdict

**PASS**. All three closure items are satisfied:

1. ✓ Direct-CDF and corrected-legacy produce statistically identical weighted distributions
2. ✓ Negative control correctly detects the missing sin(theta_cm) bug
3. ✓ Representation-splitting invariant holds

The legacy uniform-theta_cm generator with corrected analysis weight is equivalent to the current direct-CDF generator on generator-level observables within the measured support.

## Implications

- The patched `ScatteringGenerator.cc` (direct-CDF, unit weight) is the authoritative source
- Legacy ROOT files with `PrimaryWeight = sigma(theta_lab)` MUST be reweighted using the `legacy_cm_importance_weight` adapter (from PR #1329) for physics analysis
- The corrected weight formula `w ∝ sigma_cm(theta_cm) * sin(theta_cm)` is validated against the direct sampler

## Reproducibility

From the repository root:

```bash
cd ccb-testbeam/ccb-wt-1053
python -m pytest tests/test_weight_closure_issue_1053.py -v
```

All tests should pass with:
- `test_direct_vs_legacy_corrected_closure`: p > 0.05
- `test_negative_control_uncorrected_legacy`: p < 0.01
- `test_representation_splitting_invariant`: p ≈ 1.0

## Artifacts

- `REPORT.md` (this file)
- `result.json` (test summary)
- `tests/test_weight_closure_issue_1053.py` (pure-Python implementation, CI-enabled)

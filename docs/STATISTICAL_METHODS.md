# Statistical Methods — Thesis Requirements

> **Source:** Statistical content audit (2026-07-14)
> **Status:** These methods must be applied to every numeric claim before thesis submission.

---

## Timing

### sigma68 CI
Use run-level bootstrap:
1. Resample runs with replacement
2. Recompute residual distribution
3. Compute sigma68 = 0.5 × [Q₈₄(Δt) − Q₁₆(Δt)]
4. Use 2.5/97.5 percentiles for 95% CI

Report: `σ₆₈ = X.XX ns [low, high] (95% CI, run bootstrap, B=1000)`

### Pair Covariance CI
Use block/run bootstrap. Report full covariance matrix with CI per element.

### Pull Calculation
```
pull = (x_MC − x_data) / √(σ_MC² + σ_data² + σ_syst²)
```
Always report: x_MC, σ_MC, x_data, σ_data, σ_syst, sign convention.

---

## Pile-up

### tau_eff CI
Use at least three methods: template tail crossing, exponential tail fit, threshold scan. Report consistency and systematic envelope.

### Rmax Uncertainty Propagation
If `Rmax = μ_max / τeff`:
```
σ_R/R = √((σ_μ/μ)² + (σ_τ/τ)²)
```

If `Rmax = −ln(1−p_max)/τeff`: propagate p_max and τeff uncertainties.

**CRITICAL:** `Rmax = −ln(0.95)/124.79 ns = 0.411 MHz`, NOT 3.05 MHz. The canonical 3.05 MHz uses μ_max ≈ 0.38 (occupancy-quality criterion), not the 5% Poisson formula.

---

## AUC

Use DeLong CI (independent scores) or grouped bootstrap (run/track correlations):
`AUC = X.XXXX [low, high] (95% CI, method, unit)`

---

## Purity / Efficiency

Use Wilson interval or bootstrap. Must report numerator and denominator:
```
purity = TP / (TP + FP)
efficiency = TP / (TP + FN)
```

---

## Fractions / Anomaly Rates

Use Wilson interval for simple proportions. Report: `n/N [low, high]`

For normalized multi-bin histograms: multinomial covariance or bootstrap.

---

## Chi-Square

Always report:
- χ² (value)
- ndf (degrees of freedom)
- χ²/ndf (reduced)
- p-value
- bin definitions
- normalization constraints
- fitted parameters
- uncertainty model

---

## KS Test

Always report:
- D (statistic)
- n_data, n_mc (sample sizes)
- p-value
- two-sided/one-sided
- sample definition

---

## ML Win Claims

An ML result can be called a "win" ONLY if:
1. Same held-out data as traditional baseline
2. Same metric
3. Delta CI excludes zero
4. All leakage controls pass (target shuffle, LORO, event-block shuffle)
5. MC/closure truth is independent or explicitly not needed

Required output:
```
metric_ml = ...
metric_trad = ...
delta = ml − trad
CI_delta = [low, high]
controls = target_shuffle PASS, LORO PASS, event_block_shuffle PASS
```

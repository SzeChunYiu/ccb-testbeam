# MC weight policy (v2) — resolves P0 A-003 governance

**Problem (A-003, CONFIRMED):** the Krakow source samples the centre-of-mass
angle `theta_cm` **uniformly** and stores the lab-angle cross-section weight in
`PrimaryWeight`, but major downstream MC scripts do **not** consume
`PrimaryWeight`. Unweighted truth distributions are therefore **not** the
physical production distributions, and any model trained on them is biased.

## Analysis policy (fail-fast)

Every script that reads MC truth (`Sci_bar_*`, `hibeam`, `PrimaryPDG`,
`output_krakow*`) MUST do exactly one of:

1. **Consume weights** — apply `PrimaryWeight` (or a validated total weight
   including the CM→lab Jacobian) to every truth histogram, fit, metric, and
   training or validation sample; or
2. **Explicitly declare irrelevance** — set a documented marker
   `UNWEIGHTED_MC_JUSTIFICATION = "<reason>"` (or
   `weight_policy = "unweighted"`) with a written argument for why weighting
   cannot change the result. This is rare; an example is a per-event ratio in
   which the same weight cancels algebraically.

A script that reads MC truth with a **nontrivial** `PrimaryWeight` present but
neither consumed nor explicitly declared irrelevant is a **P0 defect**.
`tools/audit/audit_repository.py` flags this as `MC_WEIGHT_NOT_DECLARED`.

## Weight-vector validation policy

Before an effective sample size or weighted result may be reported,
`tools/audit/audit_mc_weight_usage.py` requires:

- exactly one recognized weight branch;
- one scalar weight per tree entry;
- no silent flattening, truncation, or filtering;
- finite, nonnegative cross-section weights;
- at least one positive weight and a positive finite sum of squared weights;
- exact input byte size and SHA-256 in the report;
- stable binary64 summation with `math.fsum`;
- atomic JSON publication to a path distinct from the input ROOT file.

A missing, ambiguous, malformed, nonfinite, negative, empty, misaligned, or
all-zero weight vector is a publication-blocking validation failure. The audit
reports weighted effective sample size
`ESS = (sum(w))^2 / sum(w^2)` only after all gates pass.

## Reporting requirements

- Publish the exact input path, byte size, SHA-256, tree, and weight branch.
- Publish entry count, weight count, sum of weights, sum of squared weights,
  ESS, ESS fraction, zero/positive counts, and summation method.
- Report the high-weight tail, including the 99th percentile, maximum, and
  maximum-to-mean ratio.
- Prefer correcting the generator and regenerating production samples over
  post-hoc reweighting when the ESS fraction is low.
- Distinguish a validated weight vector from demonstrated downstream weight
  consumption; branch validity alone does not prove an analysis used weights.

## Status

| item | status | blocker |
|---|---|---|
| Publish weight policy | **DONE** | — |
| `MC_WEIGHT_NOT_DECLARED` audit rule live | **DONE** | `tools/audit/audit_repository.py` |
| Strict weight-vector and ESS audit | **DONE** | `tools/audit/audit_mc_weight_usage.py` |
| ESS report per production sample | **BLOCKED_EXTERNAL** | needs exact production ROOT bytes on fs10 |
| Reweight/regenerate downstream MC | **BLOCKED_COMPUTE** | LUNARC |

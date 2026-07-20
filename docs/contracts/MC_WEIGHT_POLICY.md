# MC weight policy (v1) — resolves P0 A-003

**Problem (A-003, CONFIRMED):** the Krakow source samples the centre-of-mass
angle `theta_cm` **uniformly** and stores the lab-angle cross-section weight in
`PrimaryWeight`, but major downstream MC scripts do **not** consume
`PrimaryWeight`. Unweighted truth distributions are therefore **not** the
physical production distributions, and any model trained on them is biased.

## Policy (fail-fast)

Every script that reads MC truth (`Sci_bar_*`, `hibeam`, `PrimaryPDG`,
`output_krakow*`) MUST do exactly one of:

1. **Consume weights** — apply `PrimaryWeight` (or a validated total weight
   including the CM→lab Jacobian) to every truth histogram / fit / training set;
   OR
2. **Explicitly declare irrelevance** — set a documented marker
   `UNWEIGHTED_MC_JUSTIFICATION = "<reason>"` (or `weight_policy = "unweighted"`)
   with a written argument for why weighting cannot change the result (rare;
   e.g. a per-event ratio in which the weight cancels).

A script that reads MC truth with a **nontrivial** `PrimaryWeight` present but
neither consumed nor explicitly declared irrelevant is a **P0 defect**.
`tools/audit/audit_repository.py` flags this as `MC_WEIGHT_NOT_DECLARED`, and
`tools/audit/audit_mc_weight_usage.py` reports the weighted **effective sample
size** (ESS = (Σw)²/Σw²) and high-weight tails so the loss of statistical power
is visible.

## Reporting requirements

- Publish weighted ESS and ESS fraction for every production sample used.
- Report the high-weight tail (e.g. 99th percentile / max weight).
- **Prefer** correcting the generator and regenerating production samples over
  post-hoc reweighting when the ESS fraction is low.

## Status

| item | status | blocker |
|---|---|---|
| Publish weight policy | **DONE** (this file) | — |
| `MC_WEIGHT_NOT_DECLARED` audit rule live | **DONE** | `tools/audit/audit_repository.py` |
| ESS report per production sample | **BLOCKED_EXTERNAL** | needs production ROOT on fs10 |
| Reweight/regenerate downstream MC | **BLOCKED_COMPUTE** | LUNARC |

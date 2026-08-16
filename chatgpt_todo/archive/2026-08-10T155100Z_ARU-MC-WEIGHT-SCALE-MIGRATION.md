# ARU-MC-WEIGHT-SCALE-001 — repository migration of scale-invariant nonnegative event weights

Status: **ACTIVE / IMPLEMENTED ON BRANCH / CI PENDING**

Parent/dependencies: #1172, #1171, #880, #1053, #1164, #1049. This record is a software/numerical validation atom. It is not detector validation and does not resolve the generator `PrimaryWeight` carrier.

## Exact atom and scientific contract

Input: one already-derived one-dimensional finite nonnegative binary64 weight vector `w`, aligned one-to-one with the final generator-event statistical unit. Individual zero weights are allowed; a nonempty normalized measure must have positive mass.

Output: normalized probability/shape estimators and diagnostics. For any finite positive common scale `c` for which `c*w` remains finite,

`F_cw(x) = F_w(x)`,

`ESS(cw) = ESS(w)`,

`max(cw)/sum(cw) = max(w)/sum(w)`.

The authorising numerical state is inherited from `nonnegative_event_measure_v2`:

`m=max(w)>0`, `u_i=w_i/m`, `S1'=fsum(u_i)`, `S2'=fsum(u_i^2)`,

`ESS=S1'^2/S2'`, `d_max=1/S1'`.

Raw-unit `sum_w`, `sum_w2`, mean and dispersion are convenience provenance only when representable; they must not turn a valid scale-equivalent probability measure into a failure.

## Evidence inspected

- `src/ccb_mc_validation/truth/event_weight_population.py` on `main@b12cc42d54cdb649f81f8d9b1001c130f85f9afe`: validated package primitive, policy `nonnegative_event_measure_v2`.
- `tools/audit/audit_mc_weight_usage.py`: duplicated raw `fsum(w)` / `fsum(w*w)` gates and raw-moment ESS.
- `scripts/single_stave/strict_event_weights.py`: duplicated raw-moment validation/ESS plus normalized weighted mean, median, fraction and correlation that reopened the raw total after validation.
- `tools/audit/validate_mc_weights.py`: also uses raw moments but explicitly supports signed weights; it is not observationally equivalent to the nonnegative probability measure and is not silently migrated here.
- `scripts/mc01_trigger_split_truth.py`: legacy direct raw-weight arithmetic plus `PrimaryWeight[0]` and fallback-to-unit behavior. It cannot be repaired as a downstream numerical leaf before #880/#1053 define the source adapter; changing only its arithmetic would preserve the more serious carrier ambiguity.
- focused tests `tests/test_strict_event_weights.py` and `tests/test_audit_mc_weight_usage_strict.py`.

## Competing mechanisms and equivalence collapse

1. **H1 raw-unit moments.** Validate and calculate using raw `sum(w)`, `sum(w^2)`. Rejected: authorisation changes under common positive scale through overflow/underflow.
2. **H1a algebraic rearrangements / `math.fsum` only.** Collapsed into H1: stable summation cannot represent products that already overflow/underflow or totals outside binary64 range.
3. **H2 max-scaled nonnegative measure.** Survives. The already-validated package primitive supplies the one canonical implementation.
4. **H3 extended precision.** Rejected as canonical policy because it merely moves representation boundaries and adds platform-dependent semantics.
5. **H4 signed-weight measure.** Not equivalent to H2. Negative weights invalidate probability-CDF assumptions; preserve as a separate child universe rather than coercing it into the nonnegative primitive.
6. **H5 absolute-rate/yield normalization.** Not equivalent to a normalized shape/probability estimand. A future rate contract must retain physical normalization and dimensions rather than invoking scale invariance.

## Implementation executed on branch

Branch: `fix/weight-diagnostic-scale-invariance`, based on `main@b12cc42d54cdb649f81f8d9b1001c130f85f9afe`.

- `strict_event_weights.py` now delegates nonnegative population validity, ESS and scale-normalized moments to the package primitive. Normalized weighted mean/median/fraction/correlation use `w/max(w)` so accepting an extreme-scale vector cannot be followed by reopening a raw-total overflow path. Ordinary validator policy text is retained for compatibility, while `population_policy_id` and the package summation method identify the numerical contract.
- `summarize_weights()` retains raw `sum_w`, `sum_w2`, mean/std only when representable and publishes authorising `weight_scale`, `sum_w_over_scale`, `sum_w2_over_scale2`, ESS and max-weight fraction.
- `audit_mc_weight_usage.py` is version 3.0.0, delegates normalized diagnostics to the same primitive, serializes no NaN/Inf sentinels, and computes `max_over_mean = n * max_weight_fraction` without a raw mean denominator.
- Invalid nonfinite, negative, all-zero, non-vector and event-count-mismatch inputs remain fail-closed.

## Discriminating tests / negative controls

Repository fixtures added on branch:

- `[1,2,7]` and common scales `1`, `1e300`, `1e-300`: same ESS `100/54`, ESS fraction, max-weight fraction `0.7`; strict normalized mean/median/fraction/correlation also remain invariant.
- `[1e154,1e154]`, `[1e308,1e308]`, and two minimum-positive subnormals: normalized measure remains valid with ESS `2`, max-weight fraction `0.5`, scaled moments `(2,2)`; unrepresentable raw moments are explicit nulls.
- ordinary `[0.5,1.5,2]`: retained raw `sum_w=4`, `sum_w2=6.5`, ESS `16/6.5`.
- NaN/Inf, negative values, all-zero nonempty vectors, ambiguous branches, wrong shape and entry mismatch remain rejected.
- JSON publication uses `allow_nan=False` so representation failure cannot leak `Inf`/`NaN` into an ostensibly valid report.

No beam ROOT file, production MC ROOT file, or Geant4 job was used. These are deterministic numerical/software fixtures only.

## Cross-atom propagation

micro: binary64 weight representation and scaled summation
→ event: one source-authorized event weight per immutable generator event (#880/#1053)
→ meso/study: event/stave truth and legacy single-stave weighted summaries
→ inference: ESS/weighted EDF/null calibration (#1164/#1049)
→ claims: no detector-performance promotion until source carrier, detector response, statistical unit and null law all close.

The migration intentionally does not certify `scripts/mc01_trigger_split_truth.py`: its arbitrary first-primary/fallback-to-unit semantics are upstream blockers. It also does not certify signed-weight inference in `tools/audit/validate_mc_weights.py`.

## Four sequential AI review passes

### A. Domain / generator-statistical-unit lead — REVISE
Evidence inspected: package policy, #880/#1053 carrier state, legacy and strict single-stave helpers. Strongest counter-hypothesis: the generator defines a canonical raw normalization, so numerical rescaling is not scientifically meaningful. Attempted falsifier: every normalized probability/shape formula cancels a common positive factor; the fixed scale is not a detector observable. Residual uncertainty: absolute expected-yield estimands need a distinct dimensional normalization. **Vote: REVISE legacy normalized paths; do not generalize to absolute yield.**

### B. Adversarial numerical-mechanism reviewer — ACCEPT H2 / BLOCK H1
Evidence inspected: raw-moment code paths and extreme-scale fixtures. Strongest counter-hypothesis: `math.fsum` alone makes H1 robust. Attempted falsifier: `[1e308,1e308]` overflows the raw total, `1e154` weights overflow raw squares, and subnormal squares underflow before a stable sum can recover them. Residual uncertainty: large-integer-to-float coercion is separate if a real source supplies integers beyond exact binary64 range. **Vote: BLOCK raw-moment authorisation; ACCEPT max-scaled nonnegative primitive.**

### C. Independent statistics / validation reviewer — ACCEPT LOCAL / BLOCK INFERENCE
Evidence inspected: ESS/dominance invariants, ordinary-range compatibility and normalized estimator paths. Strongest counter-hypothesis: only ESS needs scale invariance; estimators may safely reopen raw weights. Attempted falsifier: a validator accepting `[1e308,1e308]` followed by raw-total median/fraction logic would still fail or silently fall back, so local composition would be inconsistent. Residual uncertainty: clustered-event ESS, weighted-null calibration and signed measures remain open. **Vote: ACCEPT local deterministic closure pending CI; BLOCK inferential promotion.**

### D. Claims / provenance reviewer — REVISE / BLOCK PROMOTION
Evidence inspected: #1172 acceptance criteria, legacy `mc01_trigger_split_truth.py`, package policy and todo coordination. Strongest counter-hypothesis: this is synthetic-only and has no claim consequence. Attempted falsifier: validity is a public software contract and must not depend on arbitrary units even if production weights happen to be moderate. Residual uncertainty: immutable production weight ranges and regenerated retained reports are unavailable. **Vote: REVISE helpers/docs; BLOCK any statement that historical physics numbers changed or are validated.**

## Residual children / handoff

1. `ARU-MC-WEIGHT-SIGNED-*`: signed-weight numerical/estimand contract for `tools/audit/validate_mc_weights.py`; do not use the nonnegative CDF primitive.
2. #880/#1053: immutable generator-mode evidence selecting the raw→event adapter.
3. Legacy `mc01_trigger_split_truth.py`: only migrate after source carrier semantics are fixed; its unit fallback is scientifically nonauthorising.
4. Real retained-report exposure: rerun on immutable production MC and record whether any stored ESS/tail diagnostic changes.

Merge only after exact-head CI passes. Until then this branch is implementation evidence, not validated remote-main state.

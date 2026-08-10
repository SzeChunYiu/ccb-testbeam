# Latest Handoff

## Session

- **Task ID:** `ARU-S00-SELECTOR-IDENTITY-REAUDIT`
- **Stamp:** `2026-08-10T030000Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial remote main:** `37ed6aa792fd409d1b2abdcf830ad76f4e7a52f2`
- **Branch:** `audit/s00-selector-identity-reaudit`
- **Parent:** #1109 (reopened)
- **Children:** #1135, #1136, #1137
- **Related:** #1073
- **Acceptance:** merged selector module is a useful partial implementation, but selector identity/model decomposition remain `FLAWED / BLOCKED`.

## Selected atom

`waveform -> selector identity -> pedestal map -> amplitude map -> threshold membership -> selected population -> CL-001/downstream claims`.

## Finding 1 — frozen v1 is not mechanically frozen

The documented historical selector is

```text
B_v1=(0,1,2,3)
b_v1=median(w[B_v1])
A_v1=max(w)-b_v1
```

but `estimate_pedestal_v1_batched(waveforms, baseline_indices)` accepts arbitrary indices and the production S00 scan forwards config `baseline_samples`.

Current checked-in YAML is still `[0,1,2,3]`, so the historical count is not numerically changed by this audit. The defect is that the same named selector ID can execute a different map.

### Deterministic falsifier executed

For one 18-sample waveform at `T=1000 ADC`:

```text
B=(0,1,2,3) -> pedestal=100,  amplitude=1700, selected=True
B=(2,3,4,5) -> pedestal=800,  amplitude=1000, selected=False
B=(4,5,6,7) -> pedestal=1550, amplitude=250,  selected=False
```

The scalar v1 also accepts fewer than four samples by taking a shorter-slice median. Nonfinite values can propagate NaN pedestal/amplitude into ordinary rejection. #1135 defines the fixed-domain/identity repair.

## Finding 2 — exact candidate equivalence

`dynamic_range` and `rolling_min` both compute

```text
pedestal = min(w)
amplitude = max(w)-min(w)
```

so their amplitude and threshold membership are algebraically identical for every finite waveform. A randomized 10,000-waveform control gave maximum absolute amplitude difference `0.0`; the source identity is the stronger proof.

Their only difference is validity-state metadata. Treat amplitude definition and validity policy as separate layers. Do not count the two method names as independent model support. #1136 owns this repair.

## Finding 3 — P10 candidate is not an early-window estimator

`early_robust_p10` computes the 10th percentile over the **full waveform**. It is permutation-invariant, so it contains no temporal evidence about whether a low sample is pre-trigger baseline or late undershoot.

For symmetric quiet noise, raw P10 is a lower noise quantile rather than the baseline location unless calibrated; negative undershoot/dropout/bipolar samples contaminate exactly the lower tail. #1137 owns naming, identifiability and validation.

## Cross-atom finding — saturation state inherits unresolved DAQ world

The new selector `_is_saturated(..., code_max=16383)` embeds the same unresolved ADC/full-scale world in #1073. It also treats upper and lower rails asymmetrically (`any >=16383` versus `all <=1`). #1073 was updated rather than duplicated.

## Four review passes

- **Detector/data-selection lead — REVISE:** current YAML matches historical v1, but fixed selector identity/domain must be enforced. Hardware validity of samples 0-3 remains parent #1109.
- **Adversarial reviewer — BLOCK:** baseline-index mutation flips membership under one method ID; exact candidate aliasing reduces the apparent model universe.
- **Validation/statistics reviewer — BLOCK:** add scalar/batch parity, hostile index/config mutations, short/nonfinite failures, alias property tests, and state-policy separation.
- **Claims/provenance reviewer — BLOCK:** CL-001 can bind a fixed historical selector only when formula, fixed tuple, input domain and source identity are mechanically bound.

## Repository actions

1. Reopened #1109 after PR #1133 had automatically closed it.
2. Opened #1135 for frozen v1 semantic identity and input-domain closure.
3. Opened #1136 for dynamic-range/rolling-min equivalence collapse.
4. Opened #1137 for the full-window P10 semantic/identifiability gap.
5. Added a post-merge scientific correction comment to PR #1133.
6. Added the new selector saturation dependency to existing #1073.
7. Reviewed PR #1134 changed files/diff and exact-head MC Validation CI (`success`).
8. Squash-merged #1134 to main as `37ed6aa792fd409d1b2abdcf830ad76f4e7a52f2`.
9. Added immutable archive `chatgpt_todo/archive/2026-08-10T030000Z_ARU-S00-SELECTOR-IDENTITY-REAUDIT.md` on this branch.

## Required implementation order

1. **#1135 first:** freeze `(0,1,2,3)` in code, fail closed on config mismatch before data/output access, validate finite/domain input, and prove scalar/batch parity.
2. **#1136:** expose unique amplitude maps separately from validity policies; regression-test exact alias equivalence.
3. **#1137:** rename/calibrate the full-window P10 candidate or implement a truly early-window estimator only after DAQ timing evidence.
4. **#1073:** selector saturation state must consume the eventual typed DAQ code-range contract.
5. Return to **#1109** for the still-unresolved real-waveform mechanism decomposition, threshold migrations and held-out downstream sensitivity.

## Scientific boundary

No raw ROOT waveform population was rescanned, no Monte Carlo was run, and no timing, PID, penetration, pile-up, energy calibration or detector-performance value was produced. The historical `640737` S00 count is not numerically invalidated by this audit; the implementation identity and physical completeness of the selected population remain unresolved.

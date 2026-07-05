# S25 — Measured inter-stave timing covariance & combined resolution (B-M4)

- Generated: 2026-07-05 08:53:10 UTC
- Git commit: `b85f11bc75f4d95e48a7037aad5c7939135262c3`
- Exploration runs (Sample II analysis): [58, 59, 60, 61, 62, 63, 65]
- Selection: rising-edge CFD20, A>1000 ADC, downstream B4/B6/B8 (B2 excluded, saturation);
  per-event triples (all three staves pass); amp-only timewalk correction fit LORO within
  Sample II; per-(stave,run) median centering.
- Bootstrap: whole-event resampling within run, 400 replicas (preserves
  the measured inter-stave correlation).

## Headline (replaces the WITHDRAWN 0.54-0.56 ns covariance number)

- **Combined sigma68 (A>1000, independence completion) = 0.490 ns [0.470, 0.508] (95% CI, correlation-aware)**
- Cauchy-Schwarz interval over the UNMEASURED intrinsic correlation: [0.000, 0.812] ns.
- Off-diagonal-equality (independence) bootstrap p = 0.615 (large p ⇒ the three off-diagonal covariances are consistent with a single common mode,
  i.e. the independence combination is not rejected; small p ⇒ structured inter-stave
  correlation biases it).

## Measured 3x3 covariance Cov(y) (ns^2, PSD-projected), A>1000

| | B4 | B6 | B8 |
|---|---|---|---|
| B4 | 259.457 | 270.386 | 274.895 |
| B6 | 270.386 | 288.141 | 287.406 |
| B8 | 274.895 | 287.406 | 295.394 |

Off-diagonal covariances (= Var(T_event) under independence; equal ⇒ pure common mode):
B4-B6 270.386, B4-B8 274.895, B6-B8 287.406 ns^2.

## Per-stave decomposition (triangle, propagated 95% CI)

| stave | sigma68 (ns) | 95% CI | neg-var flag |
|---|---|---|---|
| B4 | 1.521 | [1.482, 1.569] | False |
| B6 | 0.679 | [0.613, 0.744] | False |
| B8 | 0.799 | [0.739, 0.856] | False |

## High-amplitude subset (all three A>2000)

- Combined sigma68 = 0.460 ns [0.429, 0.477]; per-stave: B4 1.310, B6 0.632, B8 0.780 ns.
- Any sub-0.3 ns claim (per-stave or combined)? primary=False, high-amp=False.

## Confirmation partition (docs/CONFIRMATION_PARTITION.md)

- Reserved runs {64, 12-30}: **NOT staged** on this node (only analysis runs [58, 59, 60, 61, 62, 63, 65] present in /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/data/root/root). The one-shot held-out confirmation is therefore **BLOCKED — data unavailable**. Combined sigma68 sub-0.3 ns claim present? False. Per policy a sub-0.3 ns claim would require confirmation on the reserved runs before publication; here the combined value is > 0.3 ns and, regardless, cannot be confirmed this round. This is a first-class (blocked) result: the FIRST validated timing number is not achievable until the reserved raw runs are staged.

## Honest identifiability statement

- With THREE downstream staves and no external clock, only 3 pairwise variances constrain
  the 6-parameter intrinsic covariance: the inter-stave correlation is under-identified. The
  combined number above is the minimum-norm (independence) completion; the Cauchy-Schwarz
  interval is the honest bound.
- The off-diagonal-equality test is the strongest available check of the independence
  assumption; it is passed/failed as reported above, NOT a proof of independence.
- Common-mode (trigger/clock) jitter shared identically by all staves is invisible to
  inter-stave differences; it can only INFLATE an absolute-to-truth resolution. The combined
  sigma68 here is therefore a relative-timing resolution and a floor on the absolute one.
- This study reuses the Sample-II analysis runs (no fresh partition for exploration); see the
  confirmation section for the held-out status.

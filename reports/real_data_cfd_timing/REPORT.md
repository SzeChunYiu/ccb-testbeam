# Real-Data CFD Timing: Quarantined Legacy Output

## Acceptance status

**FLAWED / QUARANTINED.** The numerical bundle merged from PR #939 is retained for provenance, but it is not authorized as an accepted pair-resolution or individual-stave result.

Three demonstrated defects affect the merged output:

1. The producer pivoted and selected events by `event_id` alone while combining multiple ROOT runs. The collision-safe identity is `(run, event_id)`, so the published event counts and residual vectors require regeneration.
2. The published `0.635 ns` value was obtained by dividing the B6-B8 pair `sigma68` by `sqrt(2)`. A pair interquantile width does not identify either individual stave resolution without validated equal variances, zero covariance, and a demonstrated quadrature-deconvolution law.
3. The residual PNGs used uncentered values and a fixed `[-10, 10] ns` range even though the full-vector medians were far outside that window. The labels therefore described statistics that the visible histograms did not display.

## Historical values, not accepted results

The legacy output reported, for Sample-II runs 58-65:

- 1,888 selected B6-B8 rows under the legacy event-ID-only join;
- CFD10 pair `sigma68 = 0.8985129399585929 ns`;
- bootstrap interval `[0.8123935669551073, 1.0723601562332614] ns`;
- tail fraction beyond 5 ns of `0.15889830508474576`;
- full RMS `9.69875913667869 ns`.

These values remain in `result.json` as quarantined historical output. They must not be used to confirm `CL-002`, authorize a B6 or B8 single-stave value, or support detector-performance acceptance.

## Corrected production contract

Producer version `2.0.0` implements policy:

`REAL_DATA_CFD_REQUIRES_COMPOSITE_EVENT_KEYS_AND_PAIR_ONLY_INFERENCE`

The corrected contract:

- uses `(run, event_id)` for every selection and pivot;
- rejects duplicate `(run, event_id, stave)` rows;
- reports B6-B8 pair metrics only;
- emits `single_stave_inference.authorized = false`;
- centers residuals on their median;
- produces a full-range panel and a core panel;
- marks q16 and q84 and records displayed, underflow, and overflow counts;
- writes JSON and Markdown atomically and rejects non-standard NaN JSON.

## Required rerun

A scientifically reviewable replacement requires immutable ROOT file paths, byte counts, SHA-256 digests, producer commit, exact command, software environment, event-key closure, regenerated JSON/Markdown/PNGs, and independent review of the full-range and core residual diagnostics.

An individual-stave timing result additionally requires multi-pair or external-reference deconvolution, an explicit covariance/common-mode model, propagated uncertainty and assumption sensitivity, and closure or injection-recovery validation.

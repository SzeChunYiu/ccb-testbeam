# Latest Handoff

## Validated merge: scale-invariant derived event-weight population

Protected `main` is now `069b1d66f1a775003b284376d71c76673136f60a`. PR #1171 exact head `d6c08aefe8da25c890ec5e797511fa53a53e4802` passed MC Validation CI run `31403740933`: lint, unit tests, diagnostic upload and enforcement all completed successfully. The PR was squash-merged only after that exact-head result.

The merged package primitive is `ccb_mc_validation.truth.event_weight_population` policy `nonnegative_event_measure_v2`. It sits **after** a source-specific raw-weight adapter and does not decide the unresolved `PrimaryWeight` carrier under #880/#1053.

## Exact numerical contract

For one already-derived nonnegative event weight `w_i` per immutable generator event,

`F_w(x) = sum_i w_i I(X_i <= x) / sum_i w_i`,

`ESS(w) = (sum_i w_i)^2 / sum_i w_i^2`,

and `d_max(w)=max(w)/sum(w)`.

All three normalized quantities are invariant under a common positive factor. The rejected pre-merge mechanism nevertheless required the **raw-unit** binary64 first and second moments to remain finite, making validation depend on weight units/normalization.

The merged authorising representation is

`m = max(w) > 0`, `u_i = w_i/m`,

`S1' = math.fsum(u_i)`, `S2' = math.fsum(u_i^2)`,

`ESS = S1'^2/S2'`, `d_max = 1/S1'`.

The manifest-ready summary records `weight_scale=m`, `sum_w_over_scale=S1'`, `sum_w2_over_scale2=S2'`, ESS/fraction, zero/positive counts and dominance. Raw `sum_w` and `sum_w2` are convenience provenance only: they are finite values when faithfully representable and explicit null otherwise, never Inf/0 validity sentinels.

## Executed discriminators

Deterministic Python 3.13.5 / NumPy 2.3.5 fixtures established the defect before repair:

- `[1,2,7]` accepted by the raw path with ESS `1.8518518518518519`;
- the same relative weights scaled by `1e300` were rejected because raw `sum(w^2)=inf`, while max-scaling gives ESS `1.8518518518518516`, dominance `0.7`;
- scaling by `1e-300` was rejected because raw `sum(w^2)=0`, while max-scaling gives ESS `1.851851851851852`, dominance `0.7`;
- `[1e154,1e154]` overflowed the raw second-moment `fsum`, but scaled moments `(2,2)` give ESS `2`, dominance `0.5`;
- `[1e308,1e308]` overflowed the raw total, but scaled moments still give ESS `2`, dominance `0.5`;
- two minimum-positive subnormal equal weights underflowed in raw squares, while the scaled contract again gives ESS `2`, dominance `0.5`.

An isolated focused replica returned `24 passed in 0.09s`; exact-head GitHub CI then supplied the merge-authorising repository validation. No ROOT or Geant4 input was used for this numerical atom.

## Four sequential AI review votes

- **Generator/source-physics lead — REVISE.** Common positive normalization cancels for normalized shape/probability estimands; absolute expected-yield estimands remain a distinct future contract. Raw adapter/source mode remains unresolved.
- **Adversarial numerical-mechanism reviewer — BLOCK raw-unit moment validity.** Stable summation cannot recover products already overflowed/underflowed, and raw totals can themselves overflow for a finite vector.
- **Independent statistics/validation reviewer — ACCEPT the local max-scaled nonnegative contract / BLOCK inference.** The hostile scaling fixtures preserve ESS/dominance, but cluster-aware ESS, signed weights and the weighted-null law remain separate universes.
- **Claims/provenance reviewer — REVISE repository duplicates / no claim promotion.** A pass/fail boundary that changes only with arbitrary weight normalization is a software/provenance defect, but production ranges were not available and no historical physics result is declared numerically changed.

## Open child: #1172

Issue #1172 (`ARU-MC-WEIGHT-SCALE-001`) owns migration of the same rejected raw-moment validity mechanism still present on current main in at least:

- `tools/audit/validate_mc_weights.py`;
- `tools/audit/audit_mc_weight_usage.py`;
- `scripts/single_stave/strict_event_weights.py`;
- additional claim-bearing consumers found by repository search.

The migration must preserve ordinary-range outputs, remain invariant under positive common scaling, never serialize Inf/NaN, and not silently redefine signed-weight generators. A future absolute-rate/yield estimator must declare its own dimensional normalization rather than borrowing this probability-measure contract.

## Cross-atom dependency chain

PR #1169 remains blocked from treating arbitrary `weights[0]` as a validated raw carrier. The required chain remains:

`generator_measure_mode + immutable source provenance`

`-> versioned raw_weight_adapter_id`

`-> one derived event weight / immutable generator event`

`-> nonnegative_event_measure_v2 population validation`

`-> H3 event/stave truth diagnostic`

`-> quenching/optical/WLS/SiPM/electronics/digitizer/reconstruction`

`-> weighted DATA/MC inference only after #1049/#1052/#1164 gates`.

The #880 issue and #1169 PR now both carry the scale-invariance follow-up so their earlier raw-moment notes are not mistaken for current policy.

## Scientific boundary and next work

No production MC ROOT file, Geant4 campaign, beam ROOT file, real campaign ESS, weighted spectrum, p-value, PID, penetration, timing, calibration, pile-up, expected rate, or detector-performance quantity was regenerated or promoted.

Next highest-value work is source-dependent if immutable production MC bytes become accessible: measure per-event `PrimaryWeight` cardinality, sibling equality, PDG/TrackID order and generator mode under #880/#1053. If those bytes remain unavailable, execute #1172 as the strongest code-only leaf: migrate duplicate nonnegative event-weight diagnostics to the validated package primitive, retain signed-weight semantics separately, add extreme-scale/ordinary-range compatibility tests, and record whether any retained report changes.

# Latest Handoff

## Selected atom: positive-scale invariance of derived event weights

Current protected `main` is `dcb4c12a4d7714d2f420e5ca1a61d2fb6048edbe`, which includes the merged #1170 source-carrier audit. The raw `PrimaryWeight` representation -> one event-measure weight map remains scientifically unresolved under #880/#1053. This session stayed downstream of that source adapter and reviewed only the numerical probability-measure contract used once exactly one nonnegative derived weight exists per immutable generator event.

## Exact invariant and defect

For event observable `X_i` and weights `w_i`,

`F_w(x) = sum_i w_i I(X_i <= x) / sum_i w_i`,

`ESS(w) = (sum_i w_i)^2 / sum_i w_i^2`,

and `d_max(w)=max(w)/sum(w)`.

For any common positive factor `c`, these normalized quantities obey

`F_{cw}=F_w`, `ESS(cw)=ESS(w)`, and `d_max(cw)=d_max(w)`.

PR #1171 initially violated that invariant by requiring the **raw-unit** binary64 first and second moments to be finite. The test suite explicitly treated `[1e154,1e154]` second-moment overflow as an invalid measure. That makes software authorisation depend on weight units/normalization rather than the event measure itself.

## Executed discriminating fixtures

Python 3.13.5 / NumPy 2.3.5, deterministic analytical fixtures, no random seed:

- `[1,2,7]`: raw path accepts, ESS `1.8518518518518519`.
- `[1e300,2e300,7e300]`: same normalized measure; raw square sum becomes `inf` and the old path rejects. Max-scaled ESS `1.8518518518518516`, max fraction `0.7`.
- `[1e-300,2e-300,7e-300]`: same normalized measure; raw square sum becomes `0.0` and the old path rejects. Max-scaled ESS `1.851851851851852`, max fraction `0.7`.
- `[1e154,1e154]`: raw second-moment `math.fsum` raises intermediate overflow; max-scaled sums `(2,2)` give ESS `2`, dominance `0.5`.
- `[1e308,1e308]`: raw total `math.fsum` overflows even though normalized weights are `(1/2,1/2)`; max-scaled ESS remains `2`.
- two minimum-positive subnormal equal weights: raw square sum underflows to `0`; max-scaled ESS remains `2`.

These collapse the raw-moment algebraic rearrangements into one rejected mechanism. The surviving implementation is max-scaling:

`m=max(w)>0`, `u_i=w_i/m`, `S1'=fsum(u)`, `S2'=fsum(u^2)`,

`ESS=S1'^2/S2'`, `d_max=1/S1'`.

## Repository work completed on active PR #1171

The branch `fix/mc-event-weight-population-contract` was repaired in place rather than opening a competing implementation PR:

- `event_weight_population.py` now uses policy `nonnegative_event_measure_v2` and summation ID `python_math_fsum_max_scaled_binary64_v2`;
- it serializes authoritative `weight_scale`, `sum_w_over_scale`, and `sum_w2_over_scale2`;
- raw `sum_w` / `sum_w2` are convenience provenance only and become explicit `None` if binary64 cannot represent a positive finite raw moment;
- all-zero, negative, nonfinite, malformed, masked, or event-misaligned vectors still fail closed;
- empty diagnostics remain `measure_defined=false` with null ESS/dominance;
- regression coverage now includes extreme positive scale changes, total/second-moment overflow, subnormal underflow, ordinary-range equivalence, order stability, one-dominant-weight, and JSON-without-Inf/NaN semantics;
- `docs/contracts/MC_WEIGHT_POLICY.md` and the PR body were updated to remove the obsolete “raw overflow invalidates the measure” rule;
- immutable audit `chatgpt_todo/archive/2026-08-10T151500Z_ARU-MC-WEIGHT-SCALE-001.md` records derivation, failures, role votes and cross-atom propagation.

An isolated replica of the exact current module/tests returned `24 passed in 0.09s` with pytest exit code 0. The runtime printed an unrelated artifact-tool spreadsheet warmup timeout on stderr; that warning is recorded in the archive and was not produced by the MC test module. This local run is nonauthorising: only exact-head repository CI can authorize merge.

## New child #1172

Search found no existing open issue for this numerical universe, so issue #1172 now owns migration of the same raw-moment mechanism already present on current `main` in:

- `tools/audit/validate_mc_weights.py`;
- `tools/audit/audit_mc_weight_usage.py`;
- `scripts/single_stave/strict_event_weights.py`;
- any additional claim-bearing consumer found by repository search.

#1172 explicitly separates normalized probability/shape measures from future absolute-yield estimands and does not silently change signed-weight semantics.

## Four sequential review votes

- **Generator/source-physics lead — REVISE.** A common factor cancels from the normalized event measure, even though absolute expected-yield claims may need a different contract. Raw adapter/source mode remains unresolved.
- **Adversarial numerical reviewer — BLOCK raw-moment validity gate.** `math.fsum` cannot repair products that already overflow/underflow and can itself overflow on a finite total; exact scale-only counterexamples exist.
- **Independent statistics/validation reviewer — ACCEPT local max-scaled nonnegative contract pending CI / BLOCK inference.** ESS/dominance invariants survive the hostile fixtures, but clustered-event ESS, signed weights and null calibration remain separate universes.
- **Claims/provenance reviewer — REVISE repository helpers / no promotion.** The defect is a software/provenance contract even if current production weights do not reach extreme scales. No historical physics result is declared numerically changed without real input evidence.

## Dependency and claim boundary

PR #1169 remains blocked from treating arbitrary `weights[0]` as a validated raw adapter. The required chain remains:

`generator_measure_mode + immutable source provenance`

`-> versioned raw_weight_adapter_id`

`-> one derived event weight / immutable generator event`

`-> nonnegative_event_measure_v2 population validation`

`-> H3 event/stave truth diagnostic`

`-> quenching/optical/SiPM/electronics/digitizer/reconstruction`

`-> weighted DATA/MC inference only after #1049/#1052/#1164 gates`.

No production ROOT file or Geant4 campaign was available. No real campaign ESS, weighted spectrum, p-value, PID, penetration, timing, calibration, pile-up, rate, or detector-performance result changed.

## Next highest-value work

First inspect fresh exact-head CI for the fully updated #1171 branch; do not reuse older green runs from pre-scale-invariance heads. If the current head passes and remains mergeable, merge the bounded primitive/policy repair. Then take #1172 and migrate duplicate helpers to the package contract, with ordinary-range backward-compatibility and extreme-scale negative controls. If immutable representative production MC becomes available before that, source-carrier cardinality/equality measurement under #880/#1053 has higher physical information value and should pre-empt the code-only migration.

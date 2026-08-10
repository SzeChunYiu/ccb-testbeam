# Latest Handoff

## Active atom: scale-invariant nonnegative weight-helper migration (#1172)

Protected `main` inspected for this session is `b12cc42d54cdb649f81f8d9b1001c130f85f9afe`, after PR #1173 finalized the validated #1171 handoff. The package primitive `ccb_mc_validation.truth.event_weight_population` / `nonnegative_event_measure_v2` is already validated on main. This session migrates duplicate nonnegative consumers; it does not change raw generator carrier semantics.

Implementation branch: `fix/weight-diagnostic-scale-invariance`.

### Contract

For one source-authorized nonnegative event weight `w_i` per generator event,

`m=max(w)>0`, `u_i=w_i/m`, `S1'=fsum(u_i)`, `S2'=fsum(u_i^2)`,

`ESS=S1'^2/S2'`, `max(w)/sum(w)=1/S1'`.

Any normalized probability/shape estimator must be invariant under `w -> c w` for finite `c>0`; raw `sum_w` and `sum_w2` are nonauthorising convenience provenance and may be null when binary64 cannot represent them.

### Repository work in this branch

- `tools/audit/audit_mc_weight_usage.py` now delegates its nonnegative event-population diagnostics to `nonnegative_event_measure_v2`, publishes the population policy, scaled moments, ESS and max-weight fraction, and uses JSON `allow_nan=False`. It no longer rejects a valid scale-equivalent measure because raw `sum(w)` or `sum(w^2)` is unrepresentable.
- `scripts/single_stave/strict_event_weights.py` delegates validation and ESS to the same primitive. Weighted mean, median, fraction and correlation use max-scaled weights so a valid extreme-scale vector is not accepted by one layer and then broken by reopening a raw denominator in the next layer.
- Focused tests cover `[1,2,7]` at scales `1`, `1e300`, `1e-300`; `[1e154,1e154]`; `[1e308,1e308]`; equal minimum-positive subnormals; ordinary-range backward compatibility; and invalid NaN/negative/all-zero/shape/alignment cases.
- Full reasoning and four-role audit are in `chatgpt_todo/archive/2026-08-10T155100Z_ARU-MC-WEIGHT-SCALE-MIGRATION.md`.

### New child universe

Repository search confirmed that `tools/audit/validate_mc_weights.py` intentionally supports signed weights. Negative weights define a signed measure, not the nonnegative probability/CDF contract. Issue #1174 (`ARU-MC-WEIGHT-SIGNED-001`) now owns the signed source/estimand/numerical contract, including cancellation, absolute-vs-signed ESS-like diagnostics and scale stability. Do not silently take absolute values or reuse `nonnegative_event_measure_v2` there.

Legacy `scripts/mc01_trigger_split_truth.py` also carries raw weight arithmetic, but it still chooses `PrimaryWeight[0]` and falls back to unit weight. That is an upstream #880/#1053 carrier defect; changing only its numerical summation would not make its scientific measure authoritative.

### Four sequential AI reviewer votes

- **Generator/source-physics lead — REVISE:** common scaling cancels only for normalized shape/probability estimands; absolute yield/rate needs a separate dimensional contract.
- **Adversarial numerical reviewer — ACCEPT max-scaling / BLOCK raw moments:** `math.fsum` cannot rescue overflowed/underflowed products or an unrepresentable raw total.
- **Independent statistics reviewer — ACCEPT local deterministic closure / BLOCK inference:** composition requires all normalized downstream estimators to use the same scale-stable weight representation; event clustering, signed weights and null calibration remain open.
- **Claims/provenance reviewer — REVISE / BLOCK promotion:** software authorisation must not depend on arbitrary weight normalization, but immutable production weight ranges were unavailable and no historical physics result is declared changed or validated.

### Scientific boundary

No production MC ROOT file, Geant4 campaign, beam ROOT file, real campaign ESS, weighted spectrum, p-value, PID, penetration, timing, calibration, pile-up, expected rate, or detector-performance quantity was regenerated or promoted.

### Next gate

Open a focused PR from the implementation branch and require exact-head protected CI. If green, merge and update #1172; if CI exposes a regression, repair on the same branch and require a new exact-head run. After merge, the highest-information physical task remains immutable generator-mode evidence for #880/#1053. If source bytes remain unavailable, next code-only work is #1174 or the next detector-chain atom, not repeated nonnegative algebra.

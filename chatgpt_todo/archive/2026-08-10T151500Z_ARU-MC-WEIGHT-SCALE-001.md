# ARU-MC-WEIGHT-SCALE-001 — positive-scale invariance of nonnegative event measures

- Session UTC: 2026-08-10T15:15Z
- Main inspected: `dcb4c12a4d7714d2f420e5ca1a61d2fb6048edbe`
- Active implementation PR: #1171
- Parent atoms: #880, #1053, #1164
- Child/migration issue: #1172
- Status: `PARTIAL / IMPLEMENTED_PENDING_EXACT_HEAD_CI`
- Scientific boundary: numerical probability-measure contract only; no detector validation.

## Expert group and delegation

1. **Generator/source-physics lead** — background: importance sampling, generator
   source measures, cross-section weighting. Role: distinguish a physical change
   of measure from a harmless weight normalization/unit change.
2. **Adversarial numerical-mechanism reviewer** — background: IEEE-754 failure
   modes, stable reductions, hostile representation tests. Role: find
   transformations that leave the event measure unchanged but alter software
   authorisation.
3. **Independent statistics/validation reviewer** — background: weighted
   empirical processes, ESS diagnostics, invariant test oracles. Role: derive
   exact invariants and determine whether the repaired estimator preserves the
   intended statistical object.
4. **Claims/provenance reviewer** — background: scientific software
   traceability and claim gating. Role: identify every duplicated helper and
   prevent a local numerical repair from being promoted to generator/detector
   validation.

The passes were sequential. Disagreement is retained below.

## 1. Exact atom / input-output contract

Input: an already-derived event-aligned vector

`w = (w_1,...,w_n)`

with one finite nonnegative binary64 analysis weight per immutable generator
event. The raw `PrimaryWeight` carrier/adaptor is upstream and unresolved under
#880/#1053.

For an observable `X_i`, the normalized weighted empirical measure is

`F_w(x) = sum_i w_i I(X_i <= x) / sum_i w_i`.

Descriptive effective sample size and maximum-weight dominance are

`ESS(w) = (sum_i w_i)^2 / sum_i w_i^2`

and

`d_max(w) = max_i(w_i) / sum_i w_i`.

The values are dimensionless after normalization. A common positive factor can
represent a proposal normalization convention, cross-section unit conversion,
or another representation-only scaling.

Required invariants for every `c > 0` that keeps individual input weights finite:

`F_{c w}(x) = F_w(x)`

`ESS(c w) = ESS(w)`

`d_max(c w) = d_max(w)`.

Therefore pass/fail of the **normalized probability measure** must not depend
only on the numerical magnitude of `c`.

## 2. Triggering contradiction

PR #1171 initially required both raw binary64 moments

`S1 = math.fsum(w_i)`

and

`S2 = math.fsum(w_i * w_i)`

to be finite and positive. Its test suite explicitly required
`[1e154, 1e154]` to fail because the second moment overflows.

That rule is not equivalent to validity of the normalized event measure.
Current `main` also repeats the mechanism in:

- `tools/audit/validate_mc_weights.py`;
- `tools/audit/audit_mc_weight_usage.py`;
- `scripts/single_stave/strict_event_weights.py`.

Those main-branch duplicates are now child issue #1172; the bounded PR-local
primitive was repaired first.

## 3. Competing mathematical/numerical mechanisms

### H1 — raw first and second moments in original units

`S1 = fsum(w)`, `S2 = fsum(w^2)`, `ESS = S1^2/S2`.

Where all operations remain representable, this is mathematically correct.
Its validity gate is not representation invariant because squaring can
underflow/overflow and even `S1` can overflow for a finite vector.

**Eliminated as an authorising validity mechanism.**

Algebraic variants such as `S1/sqrt(S2)` before squaring only move the
overflow boundary. They collapse into H1 rather than constituting independent
hypotheses.

### H2 — max-scaled nonnegative moments

Let

`m = max(w) > 0`, `u_i = w_i/m`.

Then `0 <= u_i <= 1` and

`ESS = (sum u_i)^2 / sum u_i^2`

`d_max = 1 / sum u_i`.

The normalized moments are accumulated with `math.fsum`. Terms no longer
overflow from a common positive scale, and equal subnormal weights become
order-one scaled values.

**Survives and is implemented in #1171 as
`nonnegative_event_measure_v2`.**

### H3 — normalize by raw `sum(w)` before computing diagnostics

This is mathematically equivalent to H2 when the denominator is representable,
but `[1e308,1e308]` can overflow in the denominator before normalization.

**Collapsed into H2; max-scaling avoids needing the dangerous denominator.**

### H4 — use platform `long double`

This only moves numerical boundaries and can vary by platform.

**Rejected for the canonical cross-platform provenance contract.**

## 4. Exact executed falsifiers

Private runtime used only for deterministic software/math fixtures:

- Python `3.13.5`
- NumPy `2.3.5`
- Linux `6.18.35-x86_64`, glibc 2.41
- no random seed required;
- no detector data;
- no ROOT input;
- no Geant4.

Direct legacy-vs-scaled fixture output:

| vector | legacy raw-moment result | max-scaled result |
|---|---|---|
| `[1,2,7]` | accepted; ESS `1.8518518518518519` | ESS `1.851851851851852`, max fraction `0.7` |
| `[1e300,2e300,7e300]` | rejected: raw `sum(w^2)=inf` | ESS `1.8518518518518516`, max fraction `0.7` |
| `[1e-300,2e-300,7e-300]` | rejected: raw `sum(w^2)=0.0` | ESS `1.851851851851852`, max fraction `0.7` |
| `[1e154,1e154]` | `OverflowError` in second-moment `fsum` | scaled sums `(2,2)`, ESS `2`, max fraction `0.5` |
| `[1e308,1e308]` | `OverflowError` in total `fsum` | scaled sums `(2,2)`, ESS `2`, max fraction `0.5` |
| two minimum positive subnormals | raw square sum `0.0` | scaled sums `(2,2)`, ESS `2`, max fraction `0.5` |

The first three rows are the strongest discriminant: the relative weights are
identical, so the normalized empirical measure is identical, yet H1 changes
software authorisation.

## 5. Implementation repair

PR #1171 branch `fix/mc-event-weight-population-contract` was modified after the
adversarial review:

- policy ID bumped from pre-merge `nonnegative_event_measure_v1` to
  `nonnegative_event_measure_v2`;
- summation method is now
  `python_math_fsum_max_scaled_binary64_v2`;
- authoritative provenance adds:
  - `weight_scale = max(w)`;
  - `sum_w_over_scale = sum(w/max(w))`;
  - `sum_w2_over_scale2 = sum((w/max(w))^2)`;
- ESS and max-weight fraction derive only from those scale-normalized moments;
- raw `sum_w` and `sum_w2` remain convenience provenance if representable and
  become explicit `None` otherwise;
- negative, nonfinite, malformed, masked, misaligned and nonempty all-zero
  populations still fail closed;
- empty diagnostic products remain `measure_defined=false` with null
  inferential diagnostics.

The PR body and `docs/contracts/MC_WEIGHT_POLICY.md` were updated to remove the
obsolete “overflow is invalid measure” rule.

## 6. Local regression execution

An isolated replica was constructed containing the exact current module,
`DataContractError`, and focused tests.

Command form:

`python -m pytest -q <temporary>/test_event_weight_population.py`

Result:

`24 passed in 0.09s`

The Python startup environment also emitted an unrelated `artifact_tool`
spreadsheet-runtime warmup timeout to stderr. Pytest returned exit code 0 and
the warning did not come from the tested MC module. It is recorded rather than
silently omitted.

These local fixtures are **not merge authorisation**. Exact-head GitHub CI is
required after all branch updates.

## 7. Four sequential review passes

### A. Generator/source-physics lead — REVISE

Evidence inspected: #880/#1053 source-mode history; PR #1171 contract; existing
raw-moment helpers.

Strongest counter-hypothesis: a physical generator fixes an absolute
normalization, so extreme rescaling is not scientifically admissible.

Attempted falsifier: distinguish normalized shape/event-measure estimands from
absolute expected-yield estimands. For `F_w`, ESS, and dominance, a common
factor cancels exactly. An absolute yield is a different measurand and must not
reuse the normalized-probability contract.

Residual uncertainty: generator source mode and raw→event carrier remain
unresolved; absolute normalization could matter in a future rate claim.

Vote: **REVISE** numerical contract; do not infer source semantics.

### B. Adversarial numerical-mechanism reviewer — BLOCK H1

Evidence inspected: exact code, overflow test, three current-main duplicate
helpers.

Strongest counter-hypothesis: `math.fsum` is sufficiently stable that direct
moments are safe.

Attempted falsifier: common rescaling fixtures across overflow and underflow
boundaries. `fsum` cannot recover products already underflowed/overflowed and
can itself raise intermediate overflow.

Residual uncertainty: large integer-to-float exactness is a separate potential
child if a real adapter supplies integer weights above exact binary64 range.

Vote: **BLOCK** raw-unit moment finiteness as a probability-measure validity
condition.

### C. Independent statistics/validation reviewer — ACCEPT local H2 / BLOCK inference

Evidence inspected: scale identities, ESS bounds, one-dominant-weight and
permutation controls, isolated 24-test run.

Strongest counter-hypothesis: max-scaling changes ESS through rounding.

Attempted falsifier: base vs `1e300` and `1e-300` common factors reproduces ESS
and dominance within binary64 tolerance; equal extreme weights return ESS 2.

Residual uncertainty: event clustering, row splitting and signed-weight
generators require distinct inferential contracts.

Vote: **ACCEPT** the local nonnegative scale-invariant primitive pending
exact-head CI; **BLOCK** p-value or detector inference.

### D. Claims/provenance reviewer — REVISE

Evidence inspected: PR body/docs, #880 issue history, current main helper
duplication.

Strongest counter-hypothesis: extreme values are synthetic and therefore no
repository action is needed.

Attempted falsifier: this is an API validity contract. A pass/fail boundary
that changes with arbitrary units/normalization is itself a provenance defect
even if current campaigns do not reach the boundary.

Residual uncertainty: production weight ranges were unavailable, so no
historical report is declared numerically affected.

Vote: **REVISE** canonical helpers/docs; no public physics claim promotion.

## 8. Cross-atom propagation

Micro/numerical:
scale-normalized accumulation fixes the representation-only failure.

Event:
still requires exactly one validated event-measure weight per generator event.

Study:
weighted summaries may use the primitive only after source adapter identity and
event alignment pass.

Claim:
no p-value or detector-performance claim is promoted. #1049, #1052, #1164,
#880 and #1053 remain gates.

Cross-atom compatibility failure discovered:
older main-branch helpers still enforce H1. #1172 now owns migration after
#1171 reaches validated main.

## 9. Child atoms

- **#1172 / ARU-MC-WEIGHT-SCALE-001 migration:** replace duplicate H1 logic in
  canonical/legacy helpers and search claim-bearing consumers.
- **Potential child, not yet opened:** integer→binary64 exactness. Open only if
  repository or production evidence shows derived weights can arrive as large
  integer values where float coercion changes the measure.
- Signed-weight generators remain a separate pre-existing conceptual universe,
  not silently folded into this nonnegative contract.

## 10. Claim/wiki consequences and blockers

No production ROOT bytes were available and no Geant4 simulation was run.
No real ESS, spectrum, p-value, PID, penetration, timing, calibration,
pile-up, rate or detector-performance quantity was regenerated.

Blockers after this repair:

1. exact-head CI for the updated #1171 head;
2. source-mode/raw-adapter evidence under #880/#1053;
3. #1169 integration after a valid adapter;
4. #1172 migration of duplicate main helpers;
5. downstream event clustering, detector-response and null-calibration gates.

Next highest-value atom after #1171 CI is the #1172 helper migration if source
bytes remain unavailable; otherwise immutable production `PrimaryWeight`
cardinality/equality measurement remains more physically informative.

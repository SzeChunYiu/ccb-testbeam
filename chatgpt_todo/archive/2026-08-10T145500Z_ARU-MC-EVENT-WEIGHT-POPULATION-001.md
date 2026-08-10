# ARU-MC-EVENT-WEIGHT-POPULATION-001 — derived event-weight population validity

## Placement in dependency graph

Parent/source atoms: #880 (`PrimaryWeight` carrier), #1053 (generator measure mode), #1164 (event statistical unit). Active integration surface: PR #1169. Downstream: #1022 weighted event products, #1049 weighted-null calibration, DATA/MC comparison claims. This atom begins **after** a source-specific raw-weight adapter has produced exactly one derived nonnegative analysis weight per final generator-event row.

Current protected-main transition during this session: `d088b5a886e0c8891d7926af7015193db7a503b8` -> squash merge of validated audit PR #1170 -> `dcb4c12a4d7714d2f420e5ca1a61d2fb6048edbe`.

## Exact input/output contract

Input:

- one-dimensional derived `event_weight` vector `w=(w_1,...,w_n)`;
- units: dimensionless analysis/source-measure factor;
- statistical unit: one immutable generator event per row;
- event identity, sample membership, generator-measure mode and raw adapter provenance are required upstream but are not inferred by this numerical primitive.

For the nonnegative probability-measure world used by weighted histograms/ECDFs:

`w_i >= 0`, finite for every retained event.

If `n>0`, the normalized empirical measure exists only when

`S1 = sum_i w_i > 0`

and

`S2 = sum_i w_i^2 > 0`.

Then

`F_w(x) = sum_i w_i I(X_i <= x) / S1`

and the descriptive Kish-style effective sample size is

`N_eff = S1^2 / S2`.

For nonnegative weights with at least one positive value, Cauchy-Schwarz implies

`1 <= N_eff <= n`.

The implementation evaluates the same quantity as

`N_eff = (S1 / sqrt(S2))^2`

to avoid an unnecessary overflow from directly squaring `S1`.

An empty diagnostic population (`n=0`) is permitted as an empty product, but it does **not** define a weighted empirical probability measure; ESS/dominance are therefore `null`, not a fake numerical zero.

## Competing mechanisms / descriptions

H1 — accept finite nonnegative vectors, including all-zero nonempty populations, and report `ESS=0`. **Rejected.** `F_w` has zero denominator and is undefined.

H2 — compute provenance moments with ordinary/NumPy binary64 reduction. **Rejected as canonical provenance accounting.** A finite nonnegative dynamic-range fixture is representation-order dependent under the current PR #1169 `np.sum` rule.

H3 — use stable `math.fsum` for `S1` and `S2`, fail closed on overflow/nonfinite results, require positive total mass for nonempty populations, and derive ESS/dominance only afterwards. **Survives.**

H4 — silently delete zero-weight rows. **Collapsed for the normalized measure but rejected for product provenance.** Zero rows contribute no mass to `F_w`, but deleting them changes row cardinality/sample topology and can conceal event-selection behavior.

H5 — split one event into several rows with divided weight. **Not an equivalent statistical-unit representation.** It can preserve `F_w` but changes nominal row count and ESS if the fragments are treated as independent. Source-event identity/cluster membership therefore remains a separate required atom.

H6 — signed weights. **Separate universe.** Signed MC measures are not probability CDFs and are not accepted by `nonnegative_event_measure_v1`.

## Executed falsifiers

### F1 — all-zero mass

`w=[0,0,0]` gives `S1=0`; normalized weighted inference is mathematically undefined. New contract raises `DataContractError` for a nonempty all-zero population.

### F2 — reduction-order defect in the old mechanism

Finite nonnegative fixture:

`w_forward=[1e16,1,1]`

`w_reverse=[1,1,1e16]`.

Local Python/NumPy execution produced:

- `np.sum(w_forward,dtype=float64) = 1e16`
- `np.sum(w_reverse,dtype=float64) = 1.0000000000000002e16`
- `math.fsum(...) = 1.0000000000000002e16` in both orders.

Thus ordinary NumPy reduction can make serialized `sum_event_weight` depend on row representation order even though the event multiset is unchanged.

### F3 — one dominant weight

For `w=[1000,1,1,1]`:

- `S1=1003`
- `S2=1000003`
- `N_eff=1.006005981982054`
- `N_eff/n=0.2515014954955135`
- `max(w)/S1=0.9970089730807578`.

The nominal four-row population therefore carries information close to one equally weighted event; the dominance diagnostic is scientifically material.

### F4 — numerical-overflow failure path

`w=[1e154,1e154]` has finite individual binary64 weights and finite `S1`, but `S2` is outside finite binary64 range. `math.fsum` can raise `OverflowError`; the implementation catches that condition and converts it to a controlled `DataContractError` rather than publishing `Inf`/NaN provenance.

### Local isolated regression

A temporary isolated package replica of the new module plus focused tests returned `16 passed`. This is a code-level preflight only; exact repository integration remains subject to GitHub CI on the branch/PR head.

## Implementation

New package module:

`src/ccb_mc_validation/truth/event_weight_population.py`

Policy ID:

`nonnegative_event_measure_v1`

Summation ID:

`python_math_fsum_binary64_v1`

The module returns a typed JSON-ready summary with `n_rows`, positive/zero counts, `sum_w`, `sum_w2`, ESS, ESS fraction, maximum-weight fraction, and `measure_defined`.

Focused regression:

`tests/test_event_weight_population.py`

covers empty-vs-all-zero semantics, negative/nonfinite/malformed inputs, event alignment, equal-weight limit, zero-weight rows, scale invariance, permutation stability against the explicit NumPy negative control, one-dominant-weight behavior, second-moment overflow, and serialization policy identity.

`docs/contracts/MC_WEIGHT_POLICY.md` is upgraded from branch-name/scalar assumptions to a three-stage source-aware contract: raw generator representation -> versioned source adapter -> one derived event-weight population -> downstream consumption. It explicitly distinguishes scalar-event, common-replicated-primary and direct-sampled/unit-weight adapter classes and keeps arbitrary first-element collapse blocked.

## Four sequential AI review passes

### A. Generator/source-physics lead

Evidence inspected: #880 reopening evidence, #1053 generator modes, S17a jagged raw schema, active #1169 event product, existing strict weight helper.

Strongest counter-hypothesis: post-adapter gates should wait until the raw carrier is solved because no production weights are available.

Attempted falsifier: isolate properties that are independent of carrier choice. Any surviving source adapter that emits a nonnegative weighted empirical measure still requires positive total mass, stable moments and event-aligned ESS.

Residual uncertainty: source adapter identity remains unresolved for production campaigns; signed-weight future generators would require another policy.

Vote: **ACCEPT local post-adapter contract / REVISE integration**.

### B. Adversarial mechanism reviewer

Evidence inspected: exact #1169 `np.sum`/`ESS=0` implementation, permutation fixture, all-zero fixture, overflow fixture.

Strongest counter-hypothesis: NumPy reduction error is numerically negligible and therefore harmless.

Attempted falsifier: `[1e16,1,1]` versus reversed ordering changes serialized NumPy `sum_w` by exactly 2 in binary64 while `math.fsum` is order-stable for the fixture. All-zero population independently breaks the normalized-measure denominator.

Residual uncertainty: `math.fsum` is still binary64 and can overflow; controlled rejection is therefore required and implemented.

Vote: **ACCEPT fix / REJECT old population semantics**.

### C. Independent statistics/validation reviewer

Evidence inspected: weighted empirical-measure equation, ESS identity/bounds, dominant-weight fixture, row-splitting thought experiment.

Strongest counter-hypothesis: ESS alone can certify weighted inference quality.

Attempted falsifier: event splitting with divided weight can preserve `F_w` while altering statistical-unit representation and ESS; correlated/nested event structure remains upstream/downstream. ESS is diagnostic, not a calibrated uncertainty law.

Residual uncertainty: type-I error and null law under unequal weights, fitted nuisance parameters, sample nesting and detector ties remain #1049/#1164 atoms.

Vote: **ACCEPT numerical sufficient-statistic contract / BLOCK inferential promotion**.

### D. Claims/provenance reviewer

Evidence inspected: `MC_WEIGHT_POLICY.md`, #880/#1053/#1164, CL/coordination state and active #1169 manifest semantics.

Strongest counter-hypothesis: green #1169 CI already validates weight handling.

Attempted falsifier: current tests encode first-element collapse and all-zero acceptance, so green CI tests the old semantic world rather than this contract.

Residual uncertainty: no immutable production ROOT weights were inspected and no campaign result was regenerated.

Vote: **ACCEPT repository contract change / BLOCK detector or physics-claim promotion**.

## Cross-scale propagation

micro: raw generator weight representation remains #880/#1053.

meso: this atom validates the derived event-weight population only.

event: #1169 must consume this primitive after a source-authorized adapter and retain immutable event/sample identities.

study: #1022/#1049 may consume event weights only after statistical-unit and detector-measurand closure.

claim: no weighted p-value, PID, penetration, calibration or detector-performance claim is promoted by this change.

## Children / unresolved assumptions

1. `ARU-MC-WEIGHT-ADAPTER-*`: production-file discriminator for scalar-event vs common-replicated-primary vs direct-unit source modes (#880/#1053).
2. #1169 integration: import `summarize_event_weight_population`, replace `np.sum` moments/`ESS=0`, bind policy and adapter identity into manifest.
3. Signed-weight contract only if a real generator/product requires it.
4. Event-cluster/representation contract (#1164): one generator event must not become multiple independent statistical units.
5. Weighted null calibration (#1049): ESS does not define the p-value law.

## Scientific boundary

No production ROOT file or Geant4 campaign was executed in this atom. No real event-weight distribution, campaign ESS, weighted spectrum, DATA/MC discrepancy, p-value, timing, PID, penetration, energy calibration, pile-up metric or detector-performance number was produced. The work is a deterministic mathematical/software contract and governance repair.

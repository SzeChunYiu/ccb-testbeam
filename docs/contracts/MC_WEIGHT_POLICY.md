# MC weight policy (v3) — source-aware raw→event→analysis contract

**Problem (A-003 / #880 / #1053):** a branch named `PrimaryWeight` does not by
itself define the physical event measure. Repository history contains multiple
non-equivalent generator contracts. The legacy Krakow source sampled
`theta_cm` uniformly but stored a lab-angle cross-section field in
`PrimaryWeight`; current patched source code directly samples a
`sigma(theta_cm) * sin(theta_cm)` CDF and is a distinct unit-weight generation
world. Repository-resident schema evidence also shows that raw
`PrimaryWeight` can be a jagged `std::vector<double>` payload rather than an
intrinsic scalar ROOT branch.

Therefore raw branch representation, derived event weight, and downstream
weight consumption are separate contracts. No analysis may infer the correct
physical measure from the branch name alone.

## 1. Source/generator-measure contract

Every claim-bearing MC artifact MUST bind a versioned `generator_measure_mode`
and enough immutable provenance to derive the proposal→target measure:

- generator commit/configuration and input-table identity;
- source table SHA-256, frame, units and angular support when applicable;
- proposal density and target density/measure;
- raw weight branch name, ROOT typename/representation and schema;
- a versioned raw→event `weight_adapter_id`;
- explicit statement of whether a further analysis weight is required.

The supported adapter *classes* are conceptually distinct and must not be
silently interchanged:

1. **Scalar event weight.** Source provenance establishes one raw scalar event
   weight. The adapter requires exactly that scalar.
2. **Common replicated primary weight.** Source provenance establishes that a
   per-primary vector repeats one event weight. The adapter may collapse it
   only after proving every sibling value for the event is equal; disagreement
   is a hard failure. Primary-row permutation must not change the result.
3. **Direct-sampling/unit-weight mode.** The target source distribution is
   already encoded in generation. Unit analysis weight is allowed only when
   generator provenance establishes that mode; a stale legacy nonunit branch
   must not be consumed accidentally.

Arbitrary `weights[0]`, choose-any, mean, sum, product, truncation, flattening,
or filtering are **not** generic adapters. A first-primary carrier is allowed
only if a source-specific contract independently proves that exact carrier
semantics. Issue #1053 owns the legacy proposal/target derivation; issue #880
owns the campaign-wide raw→event carrier contract.

Signed-weight generators, if introduced, define a different measure and need a
separate policy. They must not be coerced into the nonnegative probability
measure below. Issue #1174 owns that signed-measure child universe.

## 2. Derived event-weight population contract

After the source-specific adapter, every final statistical row used by a
normalized weighted estimator must have exactly one aligned derived event
weight. For the current nonnegative probability-measure contract:

- the statistical unit must be explicit (normally one immutable generator
  event for MC truth/event products);
- the derived vector must be one-dimensional, event-aligned, finite and
  nonnegative;
- zero-valued individual event weights are allowed, but a **non-empty**
  selected population must contain at least one positive finite weight;
- an empty diagnostic population is not a weighted empirical measure and must
  not publish fake `ESS=0` as though inference were defined;
- the normalized measure must be invariant under any common positive rescaling
  `w_i -> c w_i`. Weight units or arbitrary normalization magnitude must not
  decide whether a mathematically identical measure is accepted;
- choose `m = max(w) > 0`, define `u_i = w_i / m`, and use stable binary64
  `math.fsum` accounting on `S1' = sum(u)` and `S2' = sum(u^2)`;
- define `ESS = S1'^2 / S2'` and `max(w)/sum(w) = 1/S1'`, with
  `1 <= ESS <= n_rows` for a non-empty nonnegative event population;
- serialize `m`, `S1'`, and `S2'` as the authorising scale-normalized moments;
- raw-unit `sum(w)` and `sum(w^2)` may be reported as convenience provenance
  only when each has a positive finite binary64 representation. If a valid
  measure's raw moment overflows or underflows binary64, serialize that raw
  convenience field as null rather than rejecting the scale-equivalent measure;
- report zero/positive counts, ESS fraction and maximum-weight fraction so
  dominant weights are visible.

For any `c > 0`,

`F_{c w}(x) = F_w(x)` and `ESS(cw) = ESS(w)`.

A validator that accepts `[1,2,7]` but rejects `[1e300,2e300,7e300]` solely
because the raw squared-weight sum overflows is therefore not validating the
probability measure; it is validating an arbitrary numerical representation.

The reusable package implementation is
`ccb_mc_validation.truth.event_weight_population` with policy ID
`nonnegative_event_measure_v2`. It deliberately accepts only **derived** event
weights; it does not decide which raw `PrimaryWeight` representation is
scientifically correct. It supplies the core probability-measure and ESS gates;
claim-bearing reports must additionally retain the high-weight-tail diagnostics
listed below.

Duplicating/splitting an event into multiple rows with divided weight can leave
a normalized weighted distribution unchanged while changing nominal row count
and ESS. Therefore representation-splitting is not an independence-preserving
operation: source-event identity/cluster membership must remain available and
one generator event must not be promoted to multiple independent statistical
units.

## 3. Downstream analysis policy (fail fast)

Every script that reads claim-bearing MC truth MUST do exactly one of:

1. consume the source-authorized derived event weight exactly once at the final
   statistical unit, including weighted summaries, fits, calibration/null
   machinery and train/validation/test metrics where applicable; or
2. explicitly declare why weighting is algebraically irrelevant for the
   specific estimand.

For a normalized nonnegative shape/probability estimator, successful population
validation is not enough if the estimator immediately reopens raw `sum(w)` or
raw weighted products that overflow/underflow only because of a common weight
scale. Such estimators must consume `w/max(w)` (or an algebraically equivalent
scale-normalized representation) so local contracts compose. Raw-unit moments
remain provenance, not hidden validity gates.

A downstream validator cannot repair a producer that already replaced missing
or invalid weights by `1.0`, dropped rows silently, or collapsed an ambiguous
raw vector. Data case-control/inclusion weights and MC physics/source weights
are distinct factors and must remain separately named before any mathematically
justified combination.

## Reporting requirements

- Publish exact input path/object identity, byte size, SHA-256 and tree/schema.
- Publish `generator_measure_mode`, raw representation and `weight_adapter_id`.
- Publish final event count, derived-weight count, the population-policy ID,
  `weight_scale`, `sum_w_over_scale`, `sum_w2_over_scale2`, ESS, ESS fraction,
  zero/positive counts, maximum-weight fraction and summation method.
- Publish raw-unit `sum(w)` and `sum(w^2)` when they are representable as
  positive finite binary64 values; otherwise publish null and retain the
  scale-normalized moments rather than an Inf/0 sentinel.
- Preserve the previous high-weight-tail requirement: report the 99th
  percentile, maximum, and maximum-to-mean ratio in addition to
  `max(w)/sum(w)`. The percentile estimator/convention must be named when it
  can affect a claim threshold.
- Bind sample/subsample inclusion rules and source-event IDs so event-level
  topology and clustering can be reconstructed.
- Prefer correcting the generator and regenerating production samples over
  post-hoc reweighting when the source measure is ambiguous or ESS is poor.
- Distinguish validated source semantics, validated event-weight population and
  demonstrated downstream consumption; none implies the other two.

## Status

| item | status | blocker |
|---|---|---|
| Repository-wide raw→event carrier semantics | **ACTIVE / PARTIAL** | #880 |
| Legacy proposal→target weight derivation | **BLOCKED / ACTIVE** | #1053 exact table/source provenance and production ROOT |
| Post-adapter nonnegative event-population primitive | **VALIDATED_ON_MAIN** | PR #1171 / policy `nonnegative_event_measure_v2` |
| Nonnegative helper scale-invariance migration | **VALIDATED_ON_MAIN / CROSS_CONSUMER_OPEN** | PR #1175 merged as `368ad62b`; #1172 still owns remaining claim-bearing consumer compatibility such as `compare_data_mc.py` |
| Signed-weight source/estimand/numerical contract | **PARTIAL / NUMERICAL_RESEARCH_ON_MAIN** | PR #1176 merged as `45c7cbd1`; #1174 remains blocked on production source semantics and consumer policy |
| Legacy `mc01_trigger_split_truth.py` weight carrier | **BLOCKED** | #880/#1053 first-primary and fallback-to-unit semantics |
| Production-sample ESS/provenance report | **BLOCKED_EXTERNAL** | exact immutable production ROOT bytes |
| Event/stave truth producer integration | **ACTIVE / BLOCKED** | #1169 must dispatch on a source-authorized adapter and use this population contract |
| Authorising weighted DATA↔MC inference | **BLOCKED** | #1049/#1052/#1164 plus detector-chain and null-calibration dependencies |

# ARU-MC-WEIGHT-CARRIER-001 — raw PrimaryWeight → event-measure weight

Status: **BLOCKED / ACTIVE CHILD**  
Severity: **P0** for weighted MC inference and any producer that claims one validated generator weight per final event.  
Parent/related: #880, #1053, #1022, #1164, #1049; active producer PR #1169.  
Remote `main` inspected: `d088b5a886e0c8891d7926af7015193db7a503b8`.  
PR #1169 head inspected: `6345cb7ca804623e09ba77ff080377be59e7153e`.  
Exact-head CI observed for that head: MC Validation run `31397051913`, completed `success`. The green CI is non-dispositive for this atom because one test encodes the disputed first-element collapse as expected behavior.

## Atomic contract

Input is the raw generator weight representation attached to one `hibeam` tree entry. Output is exactly one event-measure weight `w_e` that may be attached once to the final generator-event statistical unit. Units are dimensionless analysis/generator measure weight; scientific meaning depends on the generator proposal/target mode and cannot be inferred from the branch name alone.

For event observables `X_e`, the downstream normalized empirical measure is

`F_w(x) = sum_e w_e I(X_e <= x) / sum_e w_e`.

Therefore the raw-to-event map is part of the scientific measure. A change in that map can change every weighted histogram, fraction, quantile, calibration nuisance, discrepancy and null law.

## Evidence inspected

1. `docs/contracts/MC_WEIGHT_POLICY.md`: requires one scalar weight per tree entry; no silent flattening/truncation/filtering; finite nonnegative vector; at least one positive weight and positive finite `sum(w^2)`; `math.fsum` sufficient statistics.
2. `tools/audit/audit_mc_weight_usage.py`: operationalizes that policy as a one-dimensional event-aligned scalar vector and rejects empty/nonfinite/negative/all-zero weight populations.
3. `scripts/mc01_trigger_split_truth.py`: contradicts the scalar raw-branch description by documenting `PrimaryWeight` as a per-event variable-length array, one value per primary, and choosing the first primary as event weight.
4. `docs/validation/issue880_weight_semantics_audit.md`: status `PARTIAL`; explicitly states that it does not establish that the first primary is the scientifically correct event-weight carrier.
5. `docs/validation/issue880_strict_producer_audit.md`: says production rerun is blocked, retained result remains `FLAWED`, first-primary carrier correctness is not established, and closing #880 requires a content-addressed rerun plus scientific review of the weight definition.
6. #1053: distinguishes at least legacy weighted-generator and direct-sampled generator-measure modes; historical source assigned the same evaluated source weight to both outgoing primaries, while current direct target sampling is a distinct unity-weight world.
7. PR #1169 `truth/event_stave.py`: `primary_event_weight()` accepts any nonempty 1-D per-entry payload and returns `weights[0]`; the focused test currently asserts `[2.5, 9.0] -> 2.5`. Its H3 manifest does not carry `generator_measure_mode` or a raw-weight-adapter ID.

## Competing microscopic / software mechanisms

### H1 — scalar event branch
Raw representation has exactly one scalar per tree entry and `w_e` is that scalar. This matches the v2 policy/auditor. It survives only for source modes/files whose immutable schema proves this representation.

### H2 — common replicated per-primary value
Raw representation is `W_e=(w_e,...,w_e)` with one value attached to every generated primary. Collapse to the common value is representation-invariant if event-wise equality is guaranteed by the source and validated on bytes. This is compatible with the historical source pattern described by #1053. It must reject any event whose sibling primary weights disagree.

### H3 — first-primary carrier
`w_e = W_e[0]` even if sibling values differ. This is the current PR #1169 and legacy script behavior. **Not identified.** The existing issue-880 audit explicitly says the scientific correctness of the first-primary carrier has not been established.

### H4 — aggregate primary weights
`sum(W_e)`, `mean(W_e)`, `product(W_e)` and related rules define different event measures. They are not algebraically equivalent to H1/H2/H3 and are rejected absent a generator derivation.

### H5 — direct-sampled target distribution / unit analysis weight
The target event law is encoded at generation time and the correct analysis weight is unity unless another documented factor exists. #1053 identifies this as a separate generator-measure world. It must not inherit a legacy nonunit branch interpretation merely because a branch has the same name.

## Equivalence collapse

H1 and H2 become observationally equivalent only after source evidence proves every per-primary value in H2 is exactly the same event weight. H3 is equivalent to H2 only under that same equality condition; without it, first-element choice is order-dependent. H4 variants are separate target measures. H5 is a separate generator campaign class rather than a reparameterization of legacy weighting.

## Exact adversarial falsifier

Consider two event-level observables `X={0,1}`. Event 2 has weight 1. Event 1 carries raw primary payload `[2.5,9.0]`. A first-element adapter gives

`F_w(0) = 2.5 / (2.5 + 1) = 0.7142857142857143`.

Permute only the primary record order to `[9.0,2.5]`; the physical event and observable are unchanged, but the same adapter gives

`F_w(0) = 9 / (9 + 1) = 0.9`.

Difference: `0.18571428571428572` in the empirical CDF at the same point. Therefore arbitrary first-element collapse is not invariant to a representation-only permutation.

A second exact condition is `sum_e w_e > 0` for a nonempty normalized weighted population. If every retained event has zero weight, `F_w` is undefined because the denominator is zero. Reporting `ESS=0` does not make that a valid probability measure.

## Four sequential role reviews

### A. Generator/source-physics lead — **REVISE**
Evidence inspected: legacy and strict weight documentation, #1053 source-measure modes, active H3 producer. Strongest counter-hypothesis: element 0 is always the beam/event carrier by generator construction. Attempted falsifier: source contract currently also describes replicated weights on multiple outgoing primaries and the strict audit says first-primary correctness is unproven. Residual uncertainty: exact branch shape, primary multiplicity/order and event-wise equality on immutable production files are unavailable. Vote: **REVISE**.

### B. Adversarial mechanism reviewer — **BLOCK**
Evidence inspected: PR #1169 helper/test, competing collapse maps. Strongest counter-hypothesis: any primary-row ordering is stable enough that first element is effectively invariant. Falsifier: `[2.5,9.0] <-> [9.0,2.5]` changes the downstream empirical measure by 0.185714 at `x=0`. Residual: actual production files may happen to have equal sibling weights, but that is exactly the untested condition. Vote: **BLOCK arbitrary first-element collapse**.

### C. Independent statistics/validation reviewer — **BLOCK inference / ACCEPT discriminant**
Evidence inspected: canonical weight vector policy/auditor, weighted empirical-measure equation, all-zero case. Strongest counter-hypothesis: `ESS=0` is an adequate diagnostic for all-zero population. Falsifier: normalized weighted estimators require positive total mass. Residual: tail/ESS behavior and weight mode must be measured on immutable production samples. Vote: **BLOCK weighted inference**, **ACCEPT the permutation/equality and positive-mass tests as discriminators**.

### D. Claims/provenance reviewer — **BLOCK closure**
Evidence inspected: #880 closure comment, issue880 strict audit acceptance boundary, #1053, PR #1169 manifest identity. Strongest counter-hypothesis: the prior closure of #880 proves the weight contract. Falsifier: the audit itself says production rerun is blocked, retained result is `FLAWED`, first-primary correctness is unestablished and further review is required before closure. Residual: generator mode is not serialized into H3 product provenance. Vote: **BLOCK #880 closure and PR #1169 merge on current semantics**.

## Repository actions this session

- Reopened #880 instead of filing a duplicate issue.
- Added the full source-to-event carrier contract and acceptance/falsifier requirements to #880.
- Added a follow-up note documenting that the prior issue closure exceeded the retained audit's own acceptance boundary.
- Submitted two review passes on PR #1169: the first identified first-element/order, all-zero and summation defects; the second explicitly corrected an initially over-strong universal cardinality-1 recommendation after deeper source tracing exposed the raw-schema conflict.
- Cross-linked the corrected event-weight invariant into #1164 and generator-measure-mode implications into #1053.
- Did **not** merge PR #1169 despite exact-head green CI because the tests do not exercise the disputed source contract.

## Required discriminating experiment on real MC

For each immutable representative generator campaign:

1. record source ROOT SHA-256, byte count, tree schema, generator commit/config and source-table provenance;
2. inspect raw `PrimaryWeight` branch type/form and event-wise cardinality distribution;
3. pair each raw weight element with primary PDG/track/generator identity where available;
4. test event-wise equality of sibling primary weights and stability under primary ordering;
5. count zero-primary, one-primary, multi-primary, disagreeing-weight, nonfinite, negative and all-zero selected cases;
6. dispatch by a versioned `generator_measure_mode` plus `raw_weight_adapter_id`;
7. compute `sum(w)`, `sum(w^2)` and ESS with the canonical stable summation rule and reject nonempty zero-total measure;
8. only then regenerate any weighted H3 product and downstream weighted result.

No production ROOT bytes were available in this runtime, so no campaign weight vector, ESS, histogram, p-value, detector result or physics claim was regenerated.

## Child atoms spawned / retained

- #1053: source proposal/target law and generator-measure-mode provenance.
- #1164: exactly one **validated event-measure weight** per final event statistical unit; raw representation is source-adapter-specific.
- PR #1169 H3 integration: must add mode/adapter provenance and fail closed on incompatible raw representation before merge.
- positive-mass/stable-sufficient-statistic leaf: safe local software requirement independent of which source adapter ultimately survives.

## Claim/wiki implications

No numerical weighted result is automatically invalidated solely by this audit; equal replicated sibling weights could make the historical first-element operation numerically equivalent on a specific campaign. But that equivalence is currently an assumption, not a source-bound tested contract. Weighted MC claims remain gated by #1053/#880 and downstream statistical-unit/detector-response issues.

## Next highest-value atom

Obtain or run against immutable representative production MC bytes and resolve the raw branch carrier mode first. If bytes remain unavailable, the next code-only leaf is to make H3 weighted-population validation reject nonempty zero-total weight and use the canonical stable sufficient-statistic contract without presuming a particular raw carrier adapter. After the weight carrier is source-bound, return to H4 stepwise quenching/visible-energy construction before any detector-level DATA/MC inference.

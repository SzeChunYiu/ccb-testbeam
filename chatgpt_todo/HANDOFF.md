# Latest Handoff

## Selected atom: raw `PrimaryWeight` -> event-measure weight

Review of active PR `#1169` exposed an unresolved source-to-statistical-unit contract upstream of the new H3 event/stave truth product. The product correctly aggregates all `Sci_bar_EDep` records into one generator-event/stave row and preserves Sample-I/Sample-II membership, but its weighted mode currently maps an arbitrary non-empty per-event `PrimaryWeight` payload to `weights[0]`. Its focused tests explicitly accept `[2.5, 9.0] -> 2.5`.

The repository does not yet justify that operation as a campaign-general event-weight definition. `docs/contracts/MC_WEIGHT_POLICY.md` and `tools/audit/audit_mc_weight_usage.py` describe one scalar weight per tree entry. Legacy `scripts/mc01_trigger_split_truth.py`, however, describes `PrimaryWeight` as a variable-length per-primary array and chooses the first value. `docs/validation/issue880_weight_semantics_audit.md` is `PARTIAL`, and `docs/validation/issue880_strict_producer_audit.md` explicitly says first-primary carrier correctness is unestablished, the production rerun is blocked and the retained issue-880 result remains `FLAWED`.

## Stronger repository-resident schema evidence

The content-addressed S17a schema audit records `PrimaryWeight` as `std::vector<double>` / Uproot jagged for a `hibeam` ROOT file. The companion result binds the patched 100k smoke file to SHA-256

`74387a04571cf92724fb97974b1214579996ed33cff0b128e6a96eb21fc3164a`.

That run is explicitly nonproduction because `/ElGen/CSFile` was removed and the event count reduced to 100k. It therefore proves a real vector-valued raw schema exists, but does not establish production event-wise cardinality, sibling-weight equality, or physical weight semantics. The correct architecture must distinguish raw branch representation from the derived one-weight-per-event analysis vector.

## Exact counterexample and surviving mechanisms

For two event observables `X={0,1}` with event 2 weight 1, choosing the first value of event 1 payload `[2.5,9.0]` gives

`F_w(0) = 2.5/(2.5+1) = 0.7142857143`.

Permuting only primary-row order to `[9.0,2.5]` gives

`F_w(0) = 9/(9+1) = 0.9`.

Thus arbitrary first-element collapse changes the physical empirical measure under a representation-only permutation. The locally surviving adapter classes are:

- source-proven scalar event weight;
- source-proven common replicated per-primary weight, requiring exact sibling equality and primary-row permutation invariance;
- source-proven direct-sampled unit-weight mode.

Sum/mean/product adapters define different measures and are rejected without a generator derivation. A `first_primary_only` adapter remains unidentified unless source evidence proves that element 0 alone carries the event measure when siblings differ.

## Four sequential review passes

- **Generator/source-physics lead — REVISE.** Historical generators may attach a common weight to both outgoing primaries, but the exact production branch/cardinality/order and generator mode must be bound to bytes and source before H3 can choose an adapter.
- **Adversarial mechanism reviewer — BLOCK arbitrary first-element collapse.** The primary-row permutation example is an exact falsifier unless sibling equality is guaranteed.
- **Independent statistics/validation reviewer — BLOCK weighted inference / ACCEPT discriminator.** A non-empty all-zero selected population has no normalized weighted measure; post-adapter validation must require positive total mass and use the canonical stable sufficient-statistic rule.
- **Claims/provenance reviewer — BLOCK closure.** The previous #880 closure exceeded its own strict audit's stated acceptance boundary; generator-measure mode and raw-weight adapter are absent from the H3 manifest.

## Repository state and actions

- `#880` has been reopened instead of creating a duplicate weight issue.
- Full mechanism/falsifier/acceptance comments were added to `#880`; the prior closure-vs-audit contradiction is recorded there.
- `#1053` now owns the requirement that `generator_measure_mode` also define a versioned raw-weight adapter.
- `#1164` now states the invariant as exactly one **validated event-measure weight per final event row**, without assuming a universal raw branch shape.
- PR `#1169` received a blocking scientific review and a follow-up correction: do not replace first-element collapse with an equally unjustified universal raw-cardinality-one rule.
- Audit PR `#1170` preserves `ARU-MC-WEIGHT-CARRIER-001`, the S17a schema supplement, and this coordination state. Current head after coordination updates is newer than the initial `3768cf85...` audit head; fresh exact-head CI is required before merge.
- PR `#1169` exact-head MC Validation run `31397051913` succeeded. That green result does not close the concern because the test suite currently encodes `[2.5,9.0] -> 2.5` as expected behavior.

## Scientific boundary

No production MC ROOT file was opened in this runtime. No event-wise `PrimaryWeight` cardinality/equality distribution, campaign ESS, weighted spectrum, p-value, PID, penetration, calibration or detector-performance result was regenerated. The S17a ROOT evidence is schema/plumbing evidence only. CL-021 remains open; #1053/#880/#1164/#1049 remain upstream/downstream gates.

## Next highest-value work

First resolve the carrier on immutable representative MC files for every generator-measure mode: record ROOT SHA/tree/schema, generator commit/config/table digest, per-event `PrimaryWeight` cardinality, sibling equality, primary PDG/TrackID association/order, zero/multi-primary cases, and source mode. Then add `generator_measure_mode` + `raw_weight_adapter_id` to the H3 manifest and fail closed when the raw payload violates its declared adapter.

If production bytes remain unavailable, the safe implementation-only leaf is adapter-independent: reject a non-empty derived event-weight population when `sum(w)<=0` or `sum(w^2)<=0`, compute `sum(w)`, `sum(w^2)` and ESS with `math.fsum`, and keep the product `NONAUTHORISING_TRUTH_DIAGNOSTIC`. After that, continue the H4 stepwise quenching/visible-energy atom before any detector-level DATA/MC inference.

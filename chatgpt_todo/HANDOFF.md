# Latest Handoff

## Merged predecessor

The source-carrier audit PR `#1170` is now on protected `main` as `dcb4c12a4d7714d2f420e5ca1a61d2fb6048edbe`. Both exact-head `test` check-runs for `e25545883453116d645e1c40738e8e688e6416d3` completed successfully before merge. That audit reopened #880 and established that raw `PrimaryWeight` representation and the derived one-event-weight vector are different contracts.

## Selected atom: derived event-weight population

This session isolated the next adapter-independent universe. Assume a source-specific adapter has already produced one nonnegative dimensionless weight `w_i` for each final generator-event row. A normalized weighted empirical measure exists only if, for a nonempty population,

`S1 = sum_i w_i > 0`

and

`S2 = sum_i w_i^2 > 0`.

Then

`F_w(x) = sum_i w_i I(X_i <= x) / S1`

and the descriptive event-level effective sample size is

`ESS = S1^2 / S2`.

For finite nonnegative event weights with at least one positive weight, `1 <= ESS <= n_rows`. Empty diagnostic products are allowed, but they do not define a weighted probability measure and must not serialize a fake numerical `ESS=0` as though inference existed.

## Exact numerical falsifiers

The current active #1169 product computes moments with NumPy reduction and maps a zero squared-weight sum to `ESS=0.0`. Both mechanisms are rejected locally.

1. Dynamic-range/order fixture: `w=[1e16,1,1]` gives `np.sum=1e16`; reversing the same finite event-weight multiset gives `1.0000000000000002e16`. `math.fsum` returns `1.0000000000000002e16` in both orders. Provenance sufficient statistics therefore should use the repository's stable `math.fsum` rule.
2. All-zero nonempty fixture: `w=[0,0,0]` gives `S1=0`, so `F_w` is undefined and publication must fail closed rather than reporting `ESS=0`.
3. Dominant-weight fixture: `w=[1000,1,1,1]` gives `sum_w=1003`, `sum_w2=1000003`, `ESS=1.006005981982054`, ESS fraction `0.2515014954955135`, and maximum-weight fraction `0.9970089730807578`. Four nominal rows therefore contain information close to one equal-weight event.
4. Overflow fixture: `[1e154,1e154]` has finite individual binary64 weights and finite `sum_w`, but the squared-weight sum exceeds finite binary64 range. The new primitive catches `math.fsum` overflow and raises controlled `DataContractError` instead of emitting Inf/NaN provenance.

## Implemented repository work

Branch `fix/mc-event-weight-population-contract` now contains:

- `src/ccb_mc_validation/truth/event_weight_population.py` with policy ID `nonnegative_event_measure_v1` and summation ID `python_math_fsum_binary64_v1`;
- `tests/test_event_weight_population.py` covering empty/all-zero semantics, malformed/negative/nonfinite values, alignment, equal-weight and dominant-weight limits, common-rescaling invariance, explicit NumPy order-sensitivity negative control, `math.fsum` permutation stability, overflow, and JSON-ready policy provenance;
- `docs/contracts/MC_WEIGHT_POLICY.md` v3, which now separates raw generator representation, versioned source adapter, derived event-weight population, and downstream consumption. It distinguishes scalar-event, common-replicated-primary and direct-sampled/unit-weight adapter classes and explicitly forbids arbitrary first-element/mean/sum/product collapse without source derivation;
- `chatgpt_todo/archive/2026-08-10T145500Z_ARU-MC-EVENT-WEIGHT-POPULATION-001.md` with the full atomic-universe derivation and review record.

A temporary isolated replica of the new module/tests returned `16 passed`. This is only preflight evidence; exact repository CI on the eventual PR head remains the merge gate.

## Four sequential review passes

- **Generator/source-physics lead — ACCEPT local post-adapter contract / REVISE integration.** Positive mass/stable moments are independent of which surviving source adapter is ultimately selected, but production generator mode and raw carrier remain unresolved under #880/#1053.
- **Adversarial mechanism reviewer — ACCEPT fix / REJECT old population semantics.** The finite order fixture and all-zero denominator are exact falsifiers; `math.fsum` overflow is explicitly trapped.
- **Independent statistics/validation reviewer — ACCEPT numerical sufficient-statistic contract / BLOCK inferential promotion.** ESS is a diagnostic, not a null law. Event splitting can preserve a normalized weighted distribution while changing statistical-unit representation and ESS, so #1164 source-event clustering remains material.
- **Claims/provenance reviewer — ACCEPT policy repair / BLOCK physics promotion.** Green #1169 CI does not close this atom because the existing tests encode the old semantics. No production ROOT file was opened and no campaign result was regenerated.

## Integration dependency

PR #1169 should not be merged simply by importing this population primitive: its raw `primary_event_weight()` still chooses element zero from an arbitrary vector. The correct sequence is

`generator_measure_mode + immutable source provenance`

`-> versioned raw_weight_adapter_id`

`-> one derived event weight / immutable generator event`

`-> nonnegative_event_measure_v1 population validation`

`-> H3 event/stave truth diagnostic`

`-> quenching/optical/SiPM/electronics/digitizer/reconstruction`

`-> weighted DATA/MC inference only after #1049/#1052/#1164 gates`.

The producer manifest should serialize generator-measure mode, raw adapter ID, event-weight population policy ID, summation method, `sum_w`, `sum_w2`, ESS, ESS fraction, zero/positive counts and maximum-weight fraction.

## Scientific boundary and next work

No production MC ROOT file, Geant4 campaign, beam ROOT file, weighted spectrum, p-value, PID, penetration, timing, energy calibration, pile-up metric or detector-performance quantity changed. The source-carrier remains externally blocked until immutable representative production files can be inspected event-wise.

Next highest-value code integration is to make #1169 consume this primitive while keeping its raw adapter fail-closed/unresolved rather than silently choosing a source mode. In parallel, the highest-value external discriminator remains: for each generator-measure mode, bind ROOT SHA/tree/schema and generator config/table provenance, then measure per-event `PrimaryWeight` cardinality, sibling equality, primary PDG/TrackID ordering, zero/multi-primary cases and direct-sampling/unit-weight status.

# Iterative publication verification: trigger semantics and joint accounting

**Supervisor #1628; owning physics issue #1045; draft integration PR #1629. Scientific release: NOT AUTHORIZED.** This is a new bounded repair/reference and counterexample round, not a claim that all analyses have been verified. Main inspected: `a61427813344e29047ca9eb9b764182eb29e4c83`; review branch parent inspected: `527e9097bcf586330f1363c30580a59310bfd213`; trigger PR #1544 head: `223280d03a86d74d1656b70528fc17eb4f87984e`, still open/unmerged.

## Executed progress

- Added an independent strict event-level accounting reference. It joins explicit `(run_id,event_id)` keys, rejects unmatched/duplicate/invalid inputs, records conditional denominators, refuses silently ignored weights, and preserves both scan coordinates.
- **35 unittest methods passed** normally and with `python -O`. The second mode repeats the same tests, not 35 more independent findings.
- Exhaustively checked **87,381 pairs of Boolean selections**, all populations of size 0 through 8, against a separate integer-bitset oracle: **zero reference mismatches**.
- Enumerated **285 `(N,proxy_count,hardware_count)` triples** in that universe: every integer overlap inside the proposed bounds is attainable and none outside them occurs.
- The historical `min(proxy_count,hardware_count)` point assignment is wrong for **68,210** of those deliberately enumerated pairs. This is a finite software-test statistic, **not an experimental error rate or an estimate of how frequently production is wrong**.
- A complete second numerical run produced a byte-identical RESULT.json. The numerical runner deliberately returns exit 1, `REFERENCE_CONFORMANCE_PASS_LEGACY_DEFECTS_REMAIN`.

Reference code is not yet wired into PR #1544's ROOT producer or publication plotting. No real trigger migration, species fraction, hardware efficiency, Geant4 transport or detector measurement was recomputed. Full repository tests and latest-head remote CI were not run.

## TJ-01: replace invented overlap with joint evidence or sharp bounds

The previously demonstrated implementation fault remains in the pinned `scripts/trigger_migration_matrix.py::compute_migration_quadrant`: marginal pass counts are used to set `both=min(P,H)`. This is not newly discovered here; this round supplies a tested alternative and a proof of its finite-population contract.

Let the proxy and hardware selections be subsets A and B of the **same** N-event population, with sizes P and H, and overlap J. The four cell counts are:

`both=J; proxy_only=P-J; hardware_only=H-J; neither=N-P-H+J`.

Nonnegative cells imply:

`max(0,P+H-N) <= J <= min(P,H)`.

The bounds are sharp: for every integer J in that interval, partition N events into four groups of precisely those nonnegative sizes. This constructs a compatible joint table. Thus the marginal data identify a **set**, not normally one table. Choosing `min(P,H)` silently chooses maximal overlap/minimal disagreement.

For N=4, P=2 and H=2, identical selections and completely disjoint selections both fit the same marginals. The correct proxy-loss range is [0,1]. Event-level masks `[1,1,0,0]` and `[0,0,1,1]` give exactly 100% proxy loss; the legacy formula gives zero. These identification bounds are **not confidence intervals**.

The H=0 case is special: J=0 is identified. Therefore this general defect does not alone invalidate the historical zero-hardware scenario. Zero observed hardware acceptance still does not establish zero population probability; the event population, weighting, simulation model and confidence convention remain essential.

`joint_counts` returns the exact table only after identical key sets are established. Equal counts alone do not prove identical populations. Its population ID is a caller-supplied contract label, **not an independently authenticated raw-data manifest**. An adapter must bind it to source bytes, event domain and selections. The reference refuses extra/weighted fields rather than silently producing binomial event counts from weighted or correlated data.

## TJ-02: “primary species” is actually the first recognized charged hit

**New executed counterexample, confirmed on named source function.** `scripts/trigger_threshold_scan.py::get_primary_species` returns the first recognized charged PDG code in `Sci_bar_PDG`. It receives no parent ID, primary/track identity, or arm-entry constraint.

Permuting the same three hit records containing a proton, deuteron and electron gives **three different species labels** over six orderings. Physical hits are unchanged. The source then uses this label for its per-species enter/pass counts in both scan modes.

This is not evidence of the numerical production bias: the actual writer's ordering and data populations were not replayed. It does establish that the routine cannot infer primary ancestry from its arguments and is not invariant under record permutation. A deterministic storage order does not make first hit a physical primary.

**Required repair:** define the desired unit before relabeling: incident generator event, primary particle, particle entering B, or event containing a species. Preserve `TrackID`, `ParentID`, generator-primary identity and arm/layer crossing. A p+d event can contain both primary species; do not force it into one category solely by array order. If species-presence categories overlap, their counts cannot be summed as disjoint event counts. Unknown ancestry must remain unknown. Rerun per-species matrices and all dependent PID/mixture/trigger conclusions after this contract is fixed.

## TJ-03: per-hit thresholding depends on whether a signal is split into records

**Conditional physics-model gap, not an established installed-hardware bias.** The current T1/T2 function tests whether any *individual* listed deposit exceeds threshold. At threshold 1 MeV, one 1.2 MeV deposit in each counter at the same time gives coincidence; splitting each into two simultaneous 0.6 MeV entries makes the event fail.

If these entries partition one unresolved counter signal, the detector response should be formed from the appropriate combined time-dependent signal before discrimination. If each entry already represents an independently discriminated pulse, the interpretation is different. Geant4 permits user-defined hits associated with individual steps or accumulated cell quantities; a branch name alone cannot choose between these possibilities.

Recover the native T1/T2 writer and its unit/time/aggregation contract. Then specify scintillation/quenching, light transport, electronics impulse response, threshold crossing, discriminator busy/retrigger and coincidence logic at the required fidelity. Do not silently replace the implementation with total-event energy summation: signals far apart in time cannot automatically be integrated as one pulse.

## TJ-04: coincidence policy needs hardware evidence, not an attractive monotonic curve

A fixture with T1 times [0,20] ns and T2 time [20] ns has a valid late pair within a 5 ns window. The current earliest-only algorithm nevertheless rejects it. This separates earliest-only from any-pair policies; **neither is selected as the true electronics without timing/retrigger evidence**.

A second fixture has T1 deposits [1.5,3] MeV at [0,20] ns and T2 deposit 3 MeV at 20 ns. At threshold 1 MeV the earliest-only coincidence fails; at 2 MeV it passes, because the earlier T1 hit disappears from the accepted timing set.

This also corrects an audit assumption: increasing an amplitude threshold need not reduce *coincidence* acceptance when the timestamp-selection rule changes. A universal decreasing-efficiency check would falsely reject a possible result of the stated model. Use invariants conditional on the actual response/time algorithm, not generic monotonicity slogans. Window widening for fixed accepted times is a different, separately justified property.

The reference scan therefore preserves a complete two-coordinate surface but does not impose universal threshold monotonicity. All 24 row orders of a four-cell surface give identical output. The legacy curve overwrites the other coordinate and changes a retained efficiency from 0.8 to 0.2 on row reversal; that known defect is retained as a regression witness.

## TJ-05: invalid deposited energy silently becomes trigger failure

The copied hardware-response function accepts a NaN T1 energy without an exception and returns `t1_above_threshold=false` and coincidence=false. This can mix corrupt input with genuine inefficiency. The demonstration is synthetic; it does not establish NaNs in the production ROOT file.

Require matched energy/time array lengths, finite entries, allowed physical domains, and explicit attempted/valid/rejected counts before a result enters a denominator. Missing hardware evidence is BLOCKED, not trigger=false. The new accounting code validates Boolean selection records, but this earlier raw-hit validation layer still needs implementation in the producer.

## Confidence and event-domain controls

For zero successes in N independent identically distributed Bernoulli trials, the upper endpoint is `1-alpha**(1/N)`, derived from `(1-p)**N=alpha`. For an equal-tail two-sided interval use alpha/2 in the upper tail. The implementation uses `-expm1(log(alpha)/N)` for numerical stability and requires an explicit sampling-model declaration.

Thirty parameter combinations (five sample sizes, three confidence levels, two sidedness conventions) agree with SciPy's exact binomial interval to the tested tolerance. These comparisons are subcases within one unittest method, not 30 new detector validations. The helper rejects zero trials, unspecified conventions, nonfinite values and weighted/correlated sampling declarations. It does not infer that a real MC/data sample satisfies independent Bernoulli assumptions.

## Source research and deduplication

The initial source-research pass found that detailed interpolation, normalized common-scale cancellation, nonprobabilistic 3% box sensitivity and conditional statistical calculations already exist under #1178/#1179 and PRs #1186/#1187/#1190. These were read for continuity, **not rerun or counted as new discoveries**. #1179's closure comment refers to a code/ADR campaign; it is not evidence that the unreported experimental covariance or detector transfer was measured. #1608 retains those physical obligations.

APS's abstract verifies the Ermisch paper's identity and 190 MeV p+d/CM-angle scope. The institutional PDF returned HTTP 429; publisher full text was access restricted, and Scite lacked entitlement. No access restrictions were bypassed. **Original Table VI transcription remains unverified in this session.** The repository table's prior byte identity is not a substitute for that primary-page check. Raw GitHub byte downloads also failed DNS; connector source reads succeeded.

Primary sources read:
- Geant4 Hits documentation: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/hit.html — user-defined hit versus step/cell scoring semantics, not proof of this project's writer behavior; match the actual Geant4 release.
- SciPy official exact binomial interval documentation: https://docs.scipy.org/doc/scipy-1.16.1/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html — algorithm/reference convention. Local comparison used SciPy 1.17.0.
- Ermisch et al., PRC71,064004 (2005): https://journals.aps.org/prc/abstract/10.1103/PhysRevC.71.064004 — abstract/identity only, not completed table/covariance audit.

## Four-role review and handoff

Detector/DAQ perspective: real discriminator, native hit writer and hardware identity remain unbound. Nuclear/transport perspective: steps, tracks, primaries, species presence and events are distinct objects. Statistics perspective: joint observations are needed for migration; finite identification bounds and sampling confidence have different meanings. Software/provenance perspective: explicit keys, denominator controls, full scan coordinates and repeatable hostile tests are required.

These are four perspectives within one assistant, not fabricated independent reviewers. Independent human/experimental sign-off remains pending.

Run from this directory:

```sh
python -m unittest -v test_trigger_joint_reference
python -O -m unittest -v test_trigger_joint_reference
python run_verification.py > fresh_result.json
# Exit 1 deliberately retains unresolved legacy defects; compare to RESULT.json.
```

Source helpers are named-function excerpts with injected imports, not the full modules or a ROOT CLI. The new implementation is an independent reference awaiting reviewed integration. Neither `population_id` nor a passing test grants physical authority. Read EXECUTION_RECEIPT.json and SOURCE_BINDINGS.json before interpreting results.

Next tasks, in dependency order:
- [ ] Bind native T1/T2 hit production and primary/track/arm identity; resolve TJ-02/TJ-03/TJ-04 definitions with hardware evidence (#1045/#1617).
- [ ] Add immutable event identifiers and both selections to one common event table; keep weighted populations explicit and separate.
- [ ] Integrate joint counting or sharp marginal bounds into the owning PR #1544; no invented point migration when joint information is missing.
- [ ] Preserve two-dimensional scans and explicit fixed-coordinate slices; validate raw hit values and denominator populations before filling them.
- [ ] Regenerate per-species and aggregate matrices, uncertainties, plots and downstream statements; preserve historical zero-hardware evidence with its correct scope.
- [ ] Run real ROOT/full Geant4 and exact-head CI, then independent detector/physics/statistics/provenance review. Keep #1628/#1045 open meanwhile.

The continuing six-hour audit should pick a new unblocked physical or implementation atom rather than rerunning this finite enumeration as new progress. No automatic merge or publication promotion is authorized by this packet.

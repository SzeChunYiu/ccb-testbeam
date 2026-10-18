# Recursive publication assurance — issue #1628

**Scientific release: NOT AUTHORIZED.** This is a bounded continuation of #1628 and draft PR #1629, not a replacement for #1594/#1595 or a claim that every study has been verified. Repository source inspected: `main@a61427813344e29047ca9eb9b764182eb29e4c83`. Existing PR head inspected before this addition: `4210a4dd19ac9d2ee0eb6aad62d1349e7ba0a6bd`.

## Findings from following upstream corrections downstream

### PA-01 — retracted polarity evidence remains described as measured

`configs/channel_polarity_v2.json` states `RETRACTED_20260816_TRUNCATED_STAGING_DESYNC`. The same main revision's canonical `docs/claim_ledger.csv` still has:

| Claim | Recorded state | Source dependency | Required disposition |
|---|---|---|---|
| CL-954-001 | DONE_DATA_ONLY | polarity v2 | Retract the measured-polarity assertion and retain its historical provenance. |
| CL-1318-002 | GATED | polarity v2 | Invalidate the old depth-profile result as evidence from a retracted input; rebuild from authoritative raw data. |
| CL-1320-002 | GATED | polarity v2 | Invalidate the old 0.146 ns pair-residual result as evidence from a retracted input; rebuild before using it. |

All three rows have `allowed_status_validated=NO`. **This is a source/status/interpretation inconsistency, not evidence that a publication release actually succeeded.** A generic GATED label does not adequately distinguish a known-invalid input from an otherwise meaningful result awaiting a nuisance study. Preserve history, but prevent these values from being copied as current measured results.

The old v1-era FLAWED rows also retain the explanation that v1 was falsified by v2. The v2 source explicitly withdraws that explanation. Those reasons require reconciliation; do not simply restore v1-era results to VALIDATED. Authoritative 144-word raw identity, independent polarity and reruns remain necessary.

Source bindings: [polarity v2](https://github.com/SzeChunYiu/ccb-testbeam/blob/a61427813344e29047ca9eb9b764182eb29e4c83/configs/channel_polarity_v2.json), blob `955cd4581e915af326c9e37406adfc6574b5fb19`; [canonical ledger](https://github.com/SzeChunYiu/ccb-testbeam/blob/a61427813344e29047ca9eb9b764182eb29e4c83/docs/claim_ledger.csv), blob `acfab45eb45bb79129a39905ceadf80a27237ea2`. Relevant live connector reads covered the complete polarity file and ledger header plus rows 28–40.

### PA-02 — A09 central value agrees, sample count does not

CL-029 records `n_events=400`. Its referenced nominal E_vis result records `n_heldout=4000`, `n_train=6000`, and bootstrap `n_samples=4000`. The ledger's own note also says 4000 held-out events. The central value `0.06261039872036721` agrees exactly with the result file. Therefore the demonstrated defect is **metadata/sample-population inconsistency**, not a demonstrated error in the numerical 6.26% width.

`n_mc=1000` in that ledger row also needs a defined population; it must not be silently interpreted as the 500 bootstrap replicates. Generate structured ledger fields from a frozen artifact and explicitly name attempted, valid, held-out, training, independent-group and resample counts. Repairing the ledger alone does not resolve A09's separate estimator, uncertainty or input-model problems.

Source: [nominal result](https://github.com/SzeChunYiu/ccb-testbeam/blob/a61427813344e29047ca9eb9b764182eb29e4c83/reports/paper_1303_optical_campaign_20260815T2209Z/result.json), blob `5b05d4963b8bb4d6db6c22a9687efff0e9868119`; nominal summary starts at original line 252.

## What was executed

The earlier downloadable 61-case packet was replayed in this session. All 38 entries in its SHA-256 manifest matched. All seven programs completed; the top-level replay correctly returned exit 1, `KNOWN_DEFECTS_REPRODUCED_NO_SCIENTIFIC_CLEARANCE`. All 61 stable case records agreed exactly with the prior packet, excluding invocation stdout/stderr and path-bearing build metadata. See `PRIOR_PACKET_RECHECK.json`.

This is **repeatability of the same harness and inputs**, not independent experimental replication and not 61 new discoveries. The separate 45-probe report already on PR #1629 overlaps this packet. Do not sum the two or count repeated kinematic points as independent validated detector claims.

The new scoped auditor has **30 passing unittest methods**. They test multistep/diamond dependency invalidation, multiple root causes, pending versus invalid evidence, stale revision propagation, order invariance, malformed graphs, duplicate IDs/edges/JSON keys, cycles, missing dependencies, nonfinite metrics, integer count semantics, and CLI exit behavior. The observed projection returns exit 1 and four findings: three affected claims plus the A09 count mismatch. Correcting the count in a test does not clear the retracted-input claims.

These are software contract tests. They are not physics sign-offs. No full Geant4 application, real ROOT archive, installed hardware calibration, untouched experimental validation, new remote CI or independent human review was executed here.

## Reproduce and integrate without overwriting existing evidence

```bash
cd chatgpt_todo/publication_assurance_20261018
python -m unittest -v test_audit_claim_dependencies
python audit_claim_dependencies.py
# Expected on the frozen observed projection: exit 1, four inconsistencies.

# On a full checkout containing the pinned source bytes:
python audit_claim_dependencies.py --repo ../..
```

The last mode reads actual files, checks their Git blob identities, and parses those same byte snapshots. It refuses source drift, missing files, malformed/duplicate ledger rows, or ambiguous nominal summaries. **That full-checkout mode was not executed in this session**, because source retrieval was through the GitHub connector rather than a materialized repository. The committed JSON is explicitly a field projection, not a byte-identical copy of the original files. It must not be represented as independently verified raw data.

Exit 0 means only the scoped consistency check found no known blockers; it never authorizes publication. Exit 1 is a scientific-record inconsistency or declared graph blocker. Exit 2 is invalid input/execution. The scripts do not modify canonical results, source configurations, claim statuses or issue checkboxes.

Use these cases as regression witnesses when extending #1595's existing ledgers and #1611's gate. The graph here has only four declared nodes and three source-to-claim edges. It is **not** the full repository graph. The adapter must eventually enumerate all consumers, figures, tables and prose, not rely on this small seed set.

## Publication acceptance contract

**The unit of acceptance is a versioned scientific claim and its full dependency chain—not a script, green CI badge, number of tests, or attractive plot.** For every claim, record the physical quantity and units, evidence class, population, equation and assumptions, source/calibration/model dependencies, exact executed source and input/output hashes, statistical and systematic uncertainty, sensitivity/negative controls, independent validation and reviewer decision.

### 1. Verify the measurand and measurement chain

Separate raw ADC codes, signed pedestal-subtracted amplitude, integrated charge, detected-photon/SiPM response, Birks-visible energy, unquenched deposit, projectile energy loss, incident energy and stopping location. A missing field is unknown, not an equal substitute. Deepest observed activity is not automatically a stopping point. Specify clocks, residual signs, timing reference, selection and event identities before quoting resolution.

Check units, conservation laws, limiting cases and domain coverage. Apply the correct physical bookkeeping: Geant4's generated optical-photon energy is not added to the transport event-energy balance; optical response needs a separate ledger. A frozen equation matching its own inverse verifies numerical consistency, not the source distribution or detector model.

### 2. Resolve uncertainty and sampling populations

Specify the interval's target: a fixed-grid conditional event estimate, a fitted calibration, transfer to new runs, or physical detector performance. Refit/resample the appropriate stages and include covariance and model/source/hardware nuisances when the target requires them. More dependent pulses do not manufacture more independent run information. Few run/seed groups require explicit limitations, not confidence obtained by naive event pooling.

A count exactly reproduced from fixed bytes can legitimately have zero computational uncertainty. Do not impose a blanket ban on every zero. However, a zero-placeholder error bar is not an uncertainty calculation, and zero observed failures do not establish zero population probability. For zero successes in N independent Bernoulli trials, the one-sided confidence bound is `1 - alpha**(1/N)` at confidence `1-alpha`; weighted or correlated events need another justified treatment. Match confidence level, sidedness and population when comparing intervals.

### 3. Eliminate circular acceptance and model-selection reuse

Class labels should be independently justified; they should **not** be statistically independent of useful predictive features. The actual risk is defining the claimed physical truth from the same features or estimator and then reporting its recovery as independent validation. Distinguish weak labels, MC truth, external calibration and genuine species identification.

Freeze preprocessing, cuts, model selection and decision thresholds before the final validation. Audit the entire selection history across the fleet, not just one script's train/test variables. A reused held-out run is no longer untouched. Report unavailable independent validation honestly. Agreement between reconstruction and its own simulator can establish method closure under shared assumptions; installed-detector performance requires suitable external/data validation.

### 4. Propagate every change recursively

Maintain typed edges for data, calibration, selection, geometry, transport, statistical model, derived result, figure/table and text. Each edge binds the consumed revision. When a source is retracted or flawed, mark every transitive dependent unusable as current evidence. When it changes, mark dependents stale pending recomputation or an explicit reviewed proof of non-dependence. Keep all invalid root causes through multi-path graphs.

Coordination links and supersession references are not automatically physical dependency edges. Decompose calibration/fit/evaluation stages into versioned atoms; do not erase cycles merely to make a scheduler run. A fixed child does not repair its parents, and a fixed parent does not automatically regenerate its children.

### 5. Prove inventory coverage and preserve publication boundaries

Enumerate all analysis entry points, source/calibration assets, simulations, reports, numerical tables, equations, figures, captions, wiki pages and manuscript statements. Record the total inventory denominator and the number classified, tested, validated, conditional, invalidated and blocked. An empty or unenumerated inventory cannot pass.

Require every paper-facing scientific statement to link to canonical evidence. Unsupported conclusions must be withdrawn or framed as explicit limited hypotheses, never silently promoted. No whole-project clearance while the inventory or required physical anchors remain incomplete. A publishable narrow claim can be retained only with its actual validated domain and limitations; this does not authorize unrelated detector claims.

## Four review responsibilities and session handoff

| Review responsibility | Required challenge | Veto condition |
|---|---|---|
| Detector/DAQ experimentalist | Verify raw words, hardware, polarity, clock, trigger, calibration and exposure. | Missing or contradictory experimental anchor. |
| Nuclear/transport/optical physicist | Test source kinematics, event measure, materials, physics list/cuts, optical/digitizer response and transfer. | Wrong observable, unsupported model domain, missing material/source sensitivity. |
| Statistics/ML reviewer | Identify estimand, dependence, interval coverage, leakage and selection history. | Invalid population/uncertainty or circular final evaluation. |
| Software/provenance reviewer | Recompute from frozen bytes, attempt adverse cases and verify complete descendant propagation. | Stale/missing evidence, silent failure, incomplete declared dependencies. |

This session used these perspectives within one assistant. No human panel or independent reviewer identities/sign-offs are invented. Reviewers must be independent of the producing analysis as required by #1615; verification scripts cannot authenticate a person's actual review merely from a PASS string.

Next session: first inspect current #1628/#1629 and source revisions. Reproduce PA-01/PA-02 on the actual checkout. Add evidence-linked canonical retractions/count fixes, trace every consumer, and rerun from the earliest valid input. Do not change numerical values to satisfy expected headlines. Preserve failed fixtures and resulting source/claim revisions. Keep #1617 external evidence blockers visible.

## Mandatory next tasks

- [ ] PA-01: reconcile CL-954-001, CL-1318-002 and CL-1320-002 with the explicit source retraction; retire stale explanations in v1-era rows without restoring their scientific authority.
- [ ] Find and quarantine every affected derived figure/table/wiki/paper statement; independently rebuild from authoritative 144-word raw inputs after channel/DAQ contracts close.
- [ ] PA-02: generate CL-029 sample-count fields from the correct nominal artifact; define n_events/n_mc and retain separate uncertainty/calibration fixes.
- [ ] Integrate the scoped regressions into the canonical #1595/#1611 implementation and execute full-checkout/CI tests; do not replace it with a parallel truth ledger.
- [ ] Complete the full typed dependency graph and measurable inventory coverage. Unknown dependencies remain blockers.
- [ ] Independently inspect the original Ermisch Table VI against all 28 repository rows. Publisher abstract/source identity is not a completed table transcription audit.
- [ ] Complete real-data/Geant4/hardware validation and independent reviewer sign-off for every proposed detector-performance claim.

## Primary-method references and boundaries

- [BIPM/JCGM publications](https://www.bipm.org/en/committees/jc/jcgm/publications): GUM, measurement-model guidance and Monte Carlo propagation of distributions. Apply the relevant model and correlated inputs; metrological guidance does not supply the missing detector measurements.
- [Geant4 optical physics documentation](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/physicsProcess.html): optical energy bookkeeping and process registration. Match the actual production release before treating current documentation as an implementation witness.
- [Cawley and Talbot, JMLR 11 (2010), 2079–2107](https://www.jmlr.org/papers/v11/cawley10a.html): selection overfitting and performance-evaluation bias; it does not quantify bias for this repository.
- [Ermisch et al., PRC 71, 064004 (2005)](https://journals.aps.org/prc/abstract/10.1103/PhysRevC.71.064004): publisher abstract confirms the p+d energy/CM scope. Public PDF requests to the publisher and Kyushu university repository failed in this round; **Table VI remains unverified against the primary page**, and no table screenshots or numerical transcription are claimed.

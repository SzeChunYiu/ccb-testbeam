# Issue #1628: v2/v3 trigger physics source-lineage reconciliation (2026-10-19)

**Scientific release: NOT_AUTHORIZED.** Follow-on to audit PR #1629; related physics owners #1045, PR #1542, PR #1544. Main inspected: `a61427813344e29047ca9eb9b764182eb29e4c83`. PR #1542 head: `d53cb7b813c1f84ddc46d3e30db67df7a41ea4c7`. PR #1544 head: `223280d03a86d74d1656b70528fc17eb4f87984e`. Both physics PRs remain UNMERGED.

## CRITICAL cross-branch supersession

The prior #1628 report used #1544's v2 1M MC experiment: proxy pass **554**, modeled T1&T2 **0**. But a separate, already existing #1542 artifact **explicitly retracted that v2 geometry**: trigger slabs were sign-flipped on anti-arm rays (r=30 cm, opposite both spectrometer arms). Its corrected v3 reuses/instruments the **passive baseline Trig_stack_1/2** as B/A T1/T2 counter model at r=99 cm, geometry SHA-256 `657661c8bbae28e35bc9398e6752ed97f371e0939921770699df7d3dfb9c5eba`.

The v3 report's pre-existing per-event joint matrix, from reported LUNARC job **3507018** on v3 1M job **3507013**, yields at **1 MeV / 15 ns**: **both 165; proxy-only 389; trigger-model-only 195; neither 999251**. Thus proxy retention **165/554 = 29.783%**, modeled loss **70.217%**, and **195/360 = 54.167%** of trigger-model acceptances are outside the proxy sample. The old v2 zero is genuine to its *retracted simulation world* but must not be relabeled the current corrected model or measured detector response. No claims about beam-data hardware acceptance follow.

The **corrected per-event implementation already exists** at PR #1542 `scripts/trigger_joint_matrix.py`; its own history supersedes aggregate false-overlap 256 and hardware-only zero. Reconcile PR #1544 and the independent PR #1629 reference with it; don't claim a newly invented algorithm, and don't merge inconsistent v2/v3 artifact generations.

## Executed scoped controls

`verify_v3_grid.py` is a fail-closed **frozen field-projection** check: 20 grid cells, nonnegative partition sums to 1M, exact agreement of joint margins with both separately reported proxy/hardware scans, no missing/duplicate cells, and monotonic coincidence-window counts for the precise modeled timestamp rule. This is **not** a validation of source MC, hardware settings, or full files.

`python -m unittest -v test_verify_v3_grid`: **8 passed**; `python -O -m unittest -v test_verify_v3_grid`: same **8 passed**; `python verify_v3_grid.py`: projection consistent, publication forbidden. A separately executed larger 29-method local packet cross-checks numeric/source constraints, finite mask indexing, conditional exact binomial intervals and illustrative hypergeometric nulls. The earlier 45/61/35 test runs are overlapping scope and MUST NOT be counted as new experimental events.

Source Git blobs pinned on **unmerged PR1542**: `research/trigger_migration_study/phase4/joint_matrix_1m_v3.json` = `c90df1f5bc8be602e25d0d1557e78cd4eb2300bb`; `phase3/hardware_scan_1m_v3.json` = `52084dc7fba462978e08cc512e721735ea4551ac`; `phase3/baseline_proxy_scan_1m_v3.json` = `f66e0cd9e6294bc9fb8532f14cfb0a976fbc571e`; geometry receipt = `a3fea86f60d8d816839a4983737769a01b37805a`. **Only connector-read projected fields were locally rechecked; the original entire Git blob bytes and ROOT were not locally materialized.**

## Additional independently localized limitations

**Ray helper, source attribution distinction.** Legacy `scripts/trigger_phase2/predict_trig_acceptance.py` blob `46f72ad6df9a2d1b410bec6fca91bd31a9f9ec86` selects `np.argmax(np.where(arm_mask,times,np.inf))`. For any two-arm event each arm mask contains excluded opposite-arm hits, so this selects an **excluded hit**, not the earliest arm hit. Synthetic exhaustive checks across all **1,004 nontrivial masks** of lengths 2–9 confirm this. **A second existing helper** `scripts/trigger_phase2/predict_v2.py` blob `a8f9f608be63fe4f8ca44ca74173efcecf270c9b` already uses the correct `argmin` form. Therefore the erroneous legacy helper does **not** refute the v3 reported independent ray prediction **0.289**. The exact executed ray-helper/input/output receipt behind 0.289 remains unbound in this audit.

**Equal marginal counts are not event identity.** Both historical/updated proxy results report 554/1M. Equal *numbers* cannot prove identical accepted-event keys: [1,0,1,0] versus [0,1,0,1] are disjoint despite equal sums. V3's separate 8/8 geometry-builder controls are relevant but do not make equality of pass totals a proof of run-paired event membership. This is a missing proof, **not** a demonstrated difference in actual MC masks.

**Physical threshold ambiguity witnessed in committed v3 receipts.** The 5-MeV T1&T2 *per-event accumulated deposit* validation log reports **356**, while the *per-hit* scan/joint grid reports **355**. That is a one-event numerical consequence of two competing surrogate trigger-response definitions, not proof of correct electronics integration. The `TriggerSensitiveDetector.cc` collects event sums but forwards individual hit records via `SD_Det::ProcessHits`; native writer, pulse integration/discriminator and real thresholds remain unresolved.

**V2 statistical countercheck.** For old 1M v2 source reports T1=1436, T2=986, joint=0; a hypothetical exchangeable fixed-marginals null has E(overlap)=1.415896 and exact P(0)=**0.242292** (independent combinatorial formula and SciPy hypergeom agree); conditioning on those counters' disjoint union, a second toy null gives P(all 554 proxy events hit neither)=**0.260856**. Neither hypothetical null describes the actual geometry; their point is that zero and N=1M alone do not establish physical exclusion. Anti-arm geometry error is stronger and was documented as retracted in #1542.

A conditional iid 95% Clopper–Pearson interval for v3 proxy retention is **[0.260016, 0.337824]**. Its target differs from experimental/nuisance covariance; no installed electronics or real-data uncertainty budget was produced.

## Four specialist lenses / explicit non-independence

Detector/DAQ: **BLOCK** real trigger/electronics survey and readout transfer. Transport/geometry: **REVISE** v2 status, retain v3 source-bound geometry but require per-event identity and runtime. Statistics: **ACCEPT** reported 4x5 arithmetic consistency; **BLOCK** physical uncertainty and exchangeability transfer. Provenance: **ACCEPT** unmerged source version separation; **BLOCK** exact ROOT, ray-output provenance and paper-facing dependency regeneration. These are roles of **one assistant**, not human peer reviewers.

## Next atomic handoff

Resolve ownership with PRs #1542/#1544; preserve both historical worlds. Independently bind v3 builder/source/ROOT, eventwise v2→v3 masks, weight-carrier identity and exact selected physical species. Trace and retire the broken ray helper without falsely invalidating the corrected one. Obtain native step-signal writer/discriminator and actual installed/survey trigger settings; rerun calibrated migration versus energy, angle, species and multiplicity with source-bound uncertainty and new independent validation. Propagate all corrected numbers and caveats to the canonical #1595 ledgers, claim/figure citations and manuscript. Keep #1045/#1628 OPEN.

Primary method anchors: Geant4 sensitive-detector Hits documentation (https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/hit.html); SciPy conditional hypergeometric (https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.hypergeom.html). Neither substitutes for the experiment.

**Nothing in this commit authorizes main-branch acceptance, new Geant4 claims, human sign-off, or journal submission.**

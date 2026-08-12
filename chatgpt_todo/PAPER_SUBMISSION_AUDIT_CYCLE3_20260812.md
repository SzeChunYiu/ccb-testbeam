# CCB test-beam paper — Cycle-3 adversarial submission audit

**Date:** 2026-08-12  
**Scope:** PR #1298 / branch `chatgpt/paper-draft-20260812`  
**Purpose:** publication-level audit after the first LUNARC/Composer result updates. This audit supersedes any earlier internal-review statement that PAPER-A05/#956 or PAPER-A09/#1297 is scientifically closed.

## Decision

**NOT SUBMISSION READY.** The new analyses are useful, but this audit found publication-blocking defects in both newly promoted central numerical results. The correct action is to reopen #956 and #1297, demote their manuscript/ledger claims, regenerate from corrected contracts, and rerun the four-pass review.

A software script returning `PASS`, a closed GitHub issue, or a reproducible wrong transformation is not physics closure.

## Reviewer lenses

1. detector/test-beam and DAQ measurand fidelity;
2. Geant4 geometry/transport and optical-response semantics;
3. statistics/reconstruction and held-out validation;
4. adversarial claims/provenance and paper-result synchronization.

---

# P0 findings — central result invalidation

## C3-P0-001 — #956 uses a non-authorising 18-sample historical data product

**Evidence**

The publication producer consumes:

`reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz`

Its bound config is:

`reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s01b_s00_reproduction_local.yaml`

which declares `samples_per_channel: 18`, uses laptop-era `data/root/root` + `data/sorted-b`, and applies the 1000-ADC selected-pulse cut.

PAPER-A02/#993 now concludes that the located LUNARC raw product is a distinct `8x16` schema and explicitly makes the 18-sample historical product non-authorising for paper amplitude/timing on that raw product.

**Consequence**

CL-030/CL-031/CL-032 and manuscript Section 7.3 cannot be `DONE_DATA_ONLY` publication claims. #956 must be rerun directly from the selected authorising schema, or an independent source contract must authorise the historical 18-sample product for the intended amplitude result.

**Acceptance**

- build all four B-channel amplitudes directly from the authorising raw/product schema;
- bind exact raw/product SHA-256, producer SHA, git commit and selection contract;
- regenerate Figure 7, source tables and run-block intervals;
- update ledger, manuscript, evidence matrix and review before #956 can close.

## C3-P0-002 — #956 bypasses the geometry/readout contract and hard-codes a contradictory MC mapping

The new producer hard-codes `READOUT_PRIMARY=(1,3,5,7)` as B2/B4/B6/B8. The manuscript, `paper/hardware_bom.csv`, S12b detector-map report and paper claim surface instead use 0/2/4/6. The repository geometry contract additionally requires modules to obtain mappings through `GeometryRegistry/build_layer_to_stave` and states that the physical deployed mapping remains blocked pending the authoritative geometry/readout record.

**Consequence:** current four-readout MC numbers are mapping-dependent and cannot be promoted as canonical.

**Acceptance:** one source-bound/versioned mapping contract; publication producer imports it rather than carrying local constants; deliberate offset/parity nuisance retained until hardware mapping is source-bound.

## C3-P0-003 — #956 corrupts the supposed full-downstream MC sum by overwriting physical-layer columns with readout aliases

`build_mc_wide_table()` first creates physical `edep_B0 ... edep_B7`, then overwrites `edep_B2`, `edep_B4`, and `edep_B6` with deposits from the hard-coded readout layers and adds `edep_B8` as another alias. `_deltaE_E_core.derive_mc_columns()` then discovers all `edep_B*` columns and sums them as the full downstream observable.

This causes physical layers to be dropped/aliased and other layer deposits to be counted more than once. The reported full-downstream correlations (+0.130 Sample I, +0.045 Sample II) and the claimed sign flip relative to sparse readout are therefore not an admissible full-segmentation result.

**Acceptance:** keep distinct namespaces, e.g. `edep_layer_0...7` versus `edep_readout_B2...B8`; compute full residual E only from unique physical downstream layers; add a synthetic known-answer conservation test that every physical layer appears exactly once.

## C3-P0-004 — #956 data E is a threshold-censored selected-pulse sum, not an uncensored four-channel amplitude sum

The input S01b table contains only pulses with amplitude >1000 ADC. `deltaE_E_data_bridge.py` pivots those selected rows and converts absent B4/B6/B8 rows to zero. Therefore

`E = B4+B6+B8`

in the current product means the sum of **surviving selected downstream pulses**, not necessarily the amplitudes measured in all downstream channels for the event.

The identical 500/750/1000-ADC penetration results are an immediate consequence: information below 1000 ADC was already censored upstream.

**Acceptance:** reconstruct per-event amplitudes for B2/B4/B6/B8 before the analysis threshold, preserve measured zero versus censored/missing distinctly, and apply threshold scans after event-table construction. If a selected-pulse observable is retained, name it explicitly as threshold-censored and do not present it as the uncensored telescope analogue.

## C3-P0-005 — B2 “saturation” is not source-bound and Figure 7 marks it on the wrong axis

The producer sets `SAT_ADC=7000` and labels it saturation despite open P0 #1073/#1014 showing incompatible ADC worlds and no source-bound hardware censoring threshold. The value may only be a diagnostic high-amplitude boundary.

Additionally Figure 7 plots x=`E=B4+B6+B8` and y=`DeltaE=B2` but `_hexbin_panel(... vline_sat=7000)` draws a **vertical** line at x=7000 and labels it “B2 sat”. A B2 marker belongs on the y-axis.

**Acceptance:** until #1073 closes, rename as `A(B2)>=7000 ADC high-amplitude diagnostic` rather than hardware saturation; draw a horizontal y-line if the diagnostic is shown; never use this cut as a physical saturation correction without the DAQ contract.

## C3-P0-006 — #956 closure does not satisfy the supervisor #618 deliverables

Issue #618 requests, separately for Samples I/II, proton-only, deuteron-only, p+d truth-colour and all-species truth-colour DeltaE-E panels plus penetration/cumulative plots and summary tables. The current producer makes only all-particle weighted panels, a data panel, a phase panel and a two-channel diagnostic. Species panels and beam-energy sensitivity remain pending.

**Acceptance:** finish the requested species/penetration deliverables or explicitly narrow the publication scope with supervisor approval; #956 must not be labelled complete while the central requested discriminating plots remain absent.

## C3-P0-007 — A09 reconstructs Birks-visible energy while the issue/manuscript call it Geant4 deposited energy

The A09 script uses `edep_scint_MeV`. Geant4 source defines this as the **Birks-visible/quenched energy estimator**. The true unquenched energy deposit is stored separately as `edep_scint_raw_MeV`.

The manuscript and #1297 instead define `Edep` as Geant4 deposited energy and report the residual `(Ereco-Edep)/Edep`.

**Consequence:** the headline `sigma68=8.9%`, +10.1% bias, 17.8% RMS and 15% tails currently describe reconstruction of the visible/Birks quantity, not the stated raw deposited-energy estimand.

**Acceptance:** choose and freeze the physics target explicitly:

- `E_raw` = unquenched deposited energy, or
- `E_vis` = Birks-visible energy.

Rerun the reconstruction, result schema, figure/table, claim ledger and manuscript with unambiguous names. Do not use `Edep` as a synonym for `Evis`.

## C3-P0-008 — A09 “zero saturation” is a tautology caused by a sign-reversed diagnostic formula

A09 computes

`max(0, (pe_sat_readout - n_detected_pe)/n_detected_pe)`.

But Geant4 defines the legacy analytic occupancy transform as

`pe_sat = Ncell * (1-exp(-n_detected/Ncell))`,

so `pe_sat <= n_detected` by construction. The implemented fraction is therefore non-positive and clipped to zero even when the occupancy transform causes a loss.

The manuscript statement that saturation corrections are unnecessary because the mean saturation fraction is zero is unsupported.

**Acceptance:** remove this claim; define a physically meaningful loss diagnostic if needed, e.g. `(n_detected-pe_sat)/n_detected`, while retaining the fact that `pe_sat_readout` is a legacy independent diagnostic rather than the canonical SiPM/ADC path. Repeat with the source-bound response boundary required by A07/A08.

## C3-P0-009 — A09 result is not bound to the executed analysis producer

The A09 manifest records execution of `/tmp/paper_a09_heldout_edep_reconstruction.py`; the result's top-level `git_commit` is null and no executed-script SHA is stored. Therefore the committed producer cannot be proven identical to the code that generated the headline files.

**Acceptance:** rerun the committed producer from a clean repository worktree; require non-null superproject SHA, producer SHA-256, dirty-state record, exact command/config, input hashes and output hashes. Publication runs fail closed if source revision cannot be bound.

## C3-P0-010 — A09 position-transfer acceptance was not tested

#1297 requires performance versus hit position and explicit one-ended position extremes. The script merely copies `entry_x_cm` if present; it performs no position-stratified evaluation. The manuscript says longitudinal variation is negligible without a result demonstrating that statement.

**Acceptance:** quantify position distribution and held-out residual versus longitudinal coordinate, or state that the campaign is fixed-position and position transfer is **not evaluated**. One-ended attenuation is a central detector systematic, not optional prose.

## C3-P0-011 — #956 and #1297 were closed before physics acceptance; ledger/paper promotion must be reversed

Current ledger rows CL-030/031/032 promote #956 as `DONE_DATA_ONLY`; CL-029 records A09 as the deposited-energy result. The pre-submission review also checks these analyses as delivered. This Cycle-3 audit falsifies that closure.

**Acceptance:** reopen #956 and #1297; mark affected claims GATED/BLOCKED pending corrected reruns; update the paper after the result files change; only then repeat review and close.

---

# P1 major-revision findings

## C3-P1-001 — manuscript hard transcription error in Sample-II E

`sample_summary.json`: Sample-II `E_median=0`, `E_p84=4405 ADC`.

Manuscript Section 7.3 says median E = 4405 ADC. Correct after the rerun; 4405 is currently the 84th percentile, not the median.

## C3-P1-002 — abstract headlines a superseded legacy B2-B4 diagnostic

The abstract uses `n=33,966, r=+0.221`; the later composite-key rerun reports `n=25,423, r=+0.151`. A historical diagnostic should not be a headline abstract result, particularly while its replacement is under renewed provenance audit.

## C3-P1-003 — data Pearson r is called “weighted” although DATA uses unit weights

Use “Pearson correlation” for DATA; reserve weighted terminology for PrimaryWeight MC.

## C3-P1-004 — “tracks stop at B2” overstates a detector proxy

DATA directly measures the deepest active/read-out stave above a selection threshold, not primary physical stopping. Use proxy language and keep truth stopping distinct.

## C3-P1-005 — MC 16/84 ranges are unweighted while medians/correlations are weighted

`summarize_sample()` applies weighted median/correlation but `np.percentile()` to MC quantiles. A PrimaryWeight distribution needs weighted quantiles or an explicit declaration that ranges are unweighted diagnostics.

## C3-P1-006 — only 200 run-bootstrap replicates are used

For final central intervals, increase resampling substantially and report seed/resampling unit/Monte-Carlo error. The 68% interval itself must not be confused with a 95% confidence interval.

## C3-P1-007 — MC Sample-I/Sample-II proxy overlap is not made explicit

The producer adds II for every B-entering event and also adds I for coincidence, so an I event can also be II. Beam DATA populations are different run families. Quantitative comparison requires an explicit contract stating whether MC Sample II is inclusive `B` or exclusive `B and not A coincidence`, with overlap counts and rationale.

## C3-P1-008 — MC truth-species labelling is not track-identical with the stated DeltaE particle

The producer labels species using the PDG with largest deposit in layer 0. This can select a secondary/recoil and is inconsistent if DeltaE uses another layer alias. Use a source-bound primary/entrance-track definition and validate it against track IDs.

## C3-P1-009 — full/four-layer MC should test weight integrity per event

`PrimaryWeight` is taken from the first jagged entry. Assert source semantics and equality/constancy of any repeated per-hit event weight before reduction. Record negative/nonfinite/zero diagnostics and exact generator-weight definition.

## C3-P1-010 — correlation alone is a weak DeltaE-E topology statistic under structural zeros/censoring

Report zero-downstream fraction, conditional distributions/quantiles, Spearman/rank diagnostics where justified, and distribution-shape summaries. Do not use an invalid weighted-KS p-value (#1049 remains a blocker for that inference path).

## C3-P1-011 — A09 has only two held-out grid points at almost the same deposited/visible energy

Held-out medians are roughly 26.5 and 27.6 MeV. This supports one response-regime test, not an energy-resolution curve. Use leave-one-grid-point-out validation across the available grid and/or generate additional independent points spanning the physical E range.

## C3-P1-012 — Figure 11 has no uncertainty bars and exaggerates a two-point comparison

The producer explicitly sets bias `yerr=0` and provides no uncertainty for sigma68. Add held-out bootstrap/group intervals for bias/sigma68/RMS/tails, display N, and avoid visual language suggesting a resolved trend from two nearly coincident x values.

## C3-P1-013 — A09 eventwise OLS standard errors understate physical calibration uncertainty

The quoted slope/intercept SE treats hundreds of events as independent calibration support despite only three training grid conditions. Separate within-run MC statistics from between-energy/species/model transfer; use robust or hierarchical/grid bootstrap and an explicit nuisance envelope.

## C3-P1-014 — held-out data is used rhetorically to choose the primary model

The paper says the pooled line is retained because it beats the species-aware fit on the same held-out sample. If pooled linear was preregistered primary, say so. Otherwise model choice consumes the holdout and requires nested validation or a fresh final test set.

## C3-P1-015 — A09 model adequacy is not tested; fitted intercept is large

The pooled fit has an intercept around 49 PE. Compare an origin-constrained physical baseline, monotonic alternatives and residual-vs-target diagnostics. A non-zero intercept may encode nonlinearity/selection/model effects and should not be accepted solely because the global held-out sigma68 is small.

## C3-P1-016 — A09 lacks fail-closed target/input validation

Require declared exact input list, unique `(run,event)`, finite positive target energy, finite/nonnegative response, required meta sidecars, source revision and no unexpected ROOT files. Avoid silent NaN/Inf filtering in only some metrics.

## C3-P1-017 — existing A09 tests freeze numbers rather than validate physics semantics

Current tests assert the present 8.9% number and file existence. Add tests that distinguish raw Edep from Birks-visible energy, detect the saturation-sign bug, validate producer provenance and exercise shuffled-label/zero-signal/position controls.

## C3-P1-018 — central #956 figures are not committed for review

The LUNARC manifest lists Figure 7/8/segmentation/B2-B4 PNG/PDF files, but PR #1298 does not include them. Only the report/result/manifest are tracked. Publication figures and their source tables must be committed or reproducibly built by CI/registry from accessible immutable sources.

## C3-P1-019 — historical selected-pulse headline numbers remain gated after #993

The 640,737 laptop-era table and its B2 amplitude/high-signal fractions are not automatically authoritative for the distinct 8x16 raw product. The data-side study found a 709,003 raw rebuild and 617,377/640,737 overlap. Regenerate paper topology counts from the chosen authorising schema or retain explicit GATED/historical labels.

## C3-P1-020 — stale manuscript statements remain after newer closure state

Examples include claiming the 16/18 relationship is unresolved after #993 says DISTINCT_SCHEMAS, while elsewhere treating #956/A09 as complete although the concluding task list still calls for them. One generated truth surface should drive manuscript status prose.

## C3-P1-021 — hardware map remains unresolved while paper speaks too definitively about missing alternating physical layers

Every-other data channel naming is established, but exact physical layer/copy-number/material/readout mapping remains subject to #869/#1296 geometry/hardware evidence. Qualify statements until a layer-by-layer hardware map is source-bound.

## C3-P1-022 — hardware BOM measured waveform rows still carry `PENDING` evidence SHA

After #993, bind those rows directly to the immutable waveform-lineage manifest/validation artifact rather than the paper evidence matrix.

## C3-P1-023 — avoid “BC-408 equivalent” for generic extruded polystyrene

Material optical/scintillation/Birks properties cannot be assumed equivalent merely from chemical family. Use the exact source-bound formulation or mark unknown.

## C3-P1-024 — timing explanation should be updated after DISTINCT_SCHEMAS

Do not causally blame unavailable samples 16–17 from another schema for the 8x16 timing width. The measured 8x16 window/sampling/peak-position behaviour stands on its own. Also retain “nominal 10 ns analysis spacing” until DAQ hardware #1014 resolves the actual digitizer/transform.

## C3-P1-025 — current reference set is too old for a 2026 status statement

Re-run reference verification against the most recent HIBEAM/NNBAR detector/status and simulation publications. Keep official manufacturer/toolkit sources for component/process specifications, but add source-bound CCB facility/run references when available.

## C3-P1-026 — figure/status registry still contains stale claim promotion

`paper/figures.yaml` calls S00-COUNT `VALIDATED` and “the ONLY VALIDATED data row” despite the canonical claim ledger CL-001 being GATED; this is an internal contradiction. The same registry currently treats EDEP-RECO-MC as an admissible MC_MODEL_DEPENDENT result despite the target/provenance defects above. Registry status must mirror the canonical ledger exactly.

## C3-P1-027 — paper claim ledger and canonical claim ledger disagree

`paper/claims_ledger.csv` still has `CLM-006 Correct DeltaE-E ... BLOCKED_EXTERNAL`, while `docs/claim_ledger.csv` promotes CL-030/031 as DONE. Multiple truth surfaces are drifting. Publication status must be generated from one canonical ledger or checked by CI.

## C3-P1-028 — PR #1298 is not mergeable and no workflow run is attached to the current head

Rebase onto current `main`, resolve conflicts scientifically, rerun the full relevant test/figure/claim QA, and record exact passing head SHA before review sign-off.

---

# Mandatory paper synchronization after corrections

For every corrected rerun:

1. result/manifest/source tables first;
2. `docs/claim_ledger.csv` canonical status next;
3. `paper/figures.yaml` / figure source data next;
4. manuscript numbers/captions/abstract/conclusions next;
5. `PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md` and `PAPER_OPEN_ATOMS_20260812.md` next;
6. WIKI/academic chapters if current-facing wording changes;
7. rerun role-separated review; record both resolved and surviving alternative explanations;
8. only then close the issue.

Negative results and failed closure must propagate to the manuscript exactly like positive results.

# Immediate publication-state demotions required

- #956 / CL-030–CL-033: **GATED/BLOCKED pending corrected authorising-data + mapping/full-sum rerun**.
- #1297 / CL-029: **GATED/BLOCKED pending correct Eraw/Evis estimand, saturation diagnostic, position test and producer provenance**.
- Figure 7/8: **not publication-authorising in current form**.
- Figure 11: **diagnostic only until corrected A09 rerun; current 8.9% must not be called deposited-energy detector resolution**.
- Abstract/conclusion numerical statements that depend on these rows must be removed or explicitly labelled provisional until corrected artifacts exist.

# Submission gate

The paper may return to collaboration review after the P0 defects above are corrected and all central figures are directly inspectable. Journal-submission readiness additionally requires hardware/run provenance, timing-scope decision, optical/SiPM nuisance treatment appropriate to the claimed scope, full figure/reference audit, and a clean review/CI head.

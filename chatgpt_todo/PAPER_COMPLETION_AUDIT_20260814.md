# CCB test-beam paper — current-head completion audit and finish queue

**Audit date:** 2026-08-14  
**Audited head:** `main@c9796f28d9280591a475b1b1545686e26e0956a6`  
**Decision:** **FAIL_CLOSED / NOT SUBMISSION READY**  
**Status rule:** use this together with the Cycle-3 audit/addenda. Where an issue state or implementation changed after 2026-08-12, this file records the later current-head state.

## Review team and decision rule

This audit used three deliberately different reviewer lenses:

1. **Detector / beam-physics reviewer** — tests whether each paper quantity is actually measured by the installed test-beam apparatus and whether geometry, trigger, run-family, particle/energy and stopping/range language is physically warranted.
2. **Analysis / Monte-Carlo reviewer** — traces each result to its producer, input schema, event measure, truth definition, detector mapping, uncertainty model and negative controls.
3. **Paper / reproducibility reviewer** — checks claim status, source tables, figure provenance, build receipts, references, machine-readable evidence and whether internal issue-management prose is being mistaken for a submission-ready scientific narrative.

A result is publication-authorising only when all three lenses agree. A reproducible transformation is not sufficient if the transformation computes the wrong measurand.

---

# Executive finding

The canonical `publication/` package is a strong **fail-closed working manuscript**, but it is not yet a scientific-results paper ready for journal submission.

The most important current facts are:

- `publication/figures/final/` has **no authorising scientific figure**; it contains only its README.
- `publication/figures/source_data/` has **no final figure source table**; it contains only its README.
- `publication/tables/final/` has **no authorising scientific result table**; it contains only its README.
- `publication/figures/MANIFEST.csv` explicitly leaves the stave geometry, beam-data depth profile, MC depth profile and timing figure `PENDING`; the current DeltaE-E and energy-reconstruction products are `GATED`.
- `publication/scripts/validate_publication.py` validates package structure/hold state but does **not** implement the scientific reproducibility contract stated in Chapter 12: it does not recompute manuscript numbers, require source tables, verify source/result hashes, enforce claim-ledger authorisation, validate uncertainty fields, check units/estimands, or prove that plotted data came from the intended producer and dataset.
- The current `#956` publication producer still contains the defects identified by Cycle 3: pre-threshold selected-pulse input, hard-coded readout parity, a 7000-ADC pseudo-saturation threshold, physical-layer/readout alias collisions, inclusive overlapping MC Sample-I/Sample-II proxies, weak species labelling and only 200 run-bootstrap replicates.
- The current `#1297` producer still labels Birks-visible `edep_scint_MeV` as deposited energy, uses a tautological sign/clipping construction for saturation loss, draws zero uncertainty bars for bias, provides no uncertainty for `sigma68`, and evaluates only two held-out grid points at nearly the same target energy.
- The current single-stave **source** is materially better than the historical July grid: inner/outer cladding are now distinct material objects, WLS multiplicity is explicit and strict optical-table checks exist. Consequently the July optical grid cannot be repaired by prose; it must be regenerated with the current source and explicit nuisance contracts.
- The p-d source table is source-bound to K. Ermisch et al., *Phys. Rev. C* **71**, 064004 (2005), Table VI. The deterministic direct-CDF sampler defect owned by #1178 has been repaired/closed, but this does **not** authorise the paper MC: #1053 legacy weight conversion, #1179 source uncertainty, #1311 exact historical production provenance, source-support/model sensitivity and downstream detector-response dependencies remain.
- `WIKI.md` still contains current-facing stale promotions, including CL-001 as `VALIDATED`, old B2-vs-B4 as DeltaE-E, and 2.92 MHz as a data-derived Rmax. The canonical ledger disagrees. This is a publication-governance bug, not cosmetic documentation debt.
- No obvious public CCB/HIBEAM test-beam dataset was discoverable on Hugging Face during this audit, and the Hugging Face connector returned upstream 502 errors. The independent data-verification path therefore remains the repository-bound LUNARC/HRD lineage unless/until a public immutable mirror is created.

## Strongest currently supportable scientific statements

1. The located authorising raw waveform family is an **8 channels x 16 samples** product, distinct from historical 18-sample products.
2. Sample I and Sample II show different longitudinal B-stack activity in existing studies, but the final authorising statement must be regenerated directly from the 8x16 event population with run-aware uncertainty and adversarial drift/selection controls before it is a headline result.
3. For the current located 8x16 timing path, a B4-B6 pair residual with `sigma68 ~ 38 ns` is a **format-/estimator-limited pair residual**, not an intrinsic single-stave resolution. No `1/sqrt(2)` deconvolution is authorised.
4. The intended data DeltaE-E proxy is `DeltaE=A(B2)`, `E=A(B4)+A(B6)+A(B8)`. The current production result is not authorising because its event table is threshold-censored before construction and its MC layer bookkeeping is defective.
5. No current absolute optical yield, PE/MeV calibration or held-out energy-resolution number is publication-authorising. Historical order-10 PE/(Birks-visible MeV) and 8.9% reconstruction figures are superseded/model-gated.

---

# Section-by-section audit

| Paper part | Current scientific state | Corresponding code/evidence | Missing / wrong | Required refinement |
|---|---|---|---|---|
| 00 Abstract | Cautious but still written around internal audit state | all central result producers + claim ledger | It cannot yet function as a normal journal abstract because the central final figures/results do not exist. Do not headline historical 640737 selected pulses, old B2-B4 correlations, sub-ns timing, ~10 PE/MeV or 8.9% energy resolution. | After final figures close, rewrite around 3-5 authorising results, each with uncertainty and clear DATA vs MC status. Until then retain explicit non-submission wording. |
| 01 Introduction | Conceptually sound, under-referenced scientifically | HIBEAM/NNBAR prototype/framework papers; range/PID literature | Too much repository evidence taxonomy relative to detector/range-telescope physics motivation. Missing stronger primary context for range-based hadron identification and scintillator response. | Expand scientific motivation and primary literature; move detailed evidence-class governance to reproducibility/supplement. |
| 02 CCB configuration | Correctly separates `MEASURED/DESIGN_SPEC/SIM_CONFIG/UNKNOWN_EXTERNAL` | `publication/tables/hardware_bom.csv`, Geant4 `krakow.geoconf`, run/trigger contracts | Installed hardware is not source-bound sufficiently for exact geometry/target/trigger claims. Mapping and run/trigger interpretation remain open (#1296/#869/#962/#1045). | Bind collaboration CAD/build/channel/run records. Final setup figure must annotate which values are measured/design/schematic, never promote MC configuration as metrology. |
| 03 Stave/readout | Current 50 x 5.18 x 2.0 cm model and one-fibre/one-end narrative are clearly labelled design-spec | `geant4/single_stave/src/DetectorConstruction.cc`, stave docs/BOM | Old ~1 m BC-408 narrative conflicts with current design spec; actual installed material, fibre lot/end treatment, sensor operating point and DAQ transfer remain incompletely source-bound. | Resolve #1296, then make a source-bound stave schematic. Retain optical material identities as model hypotheses where installation evidence is absent. |
| 04 Simulation | Causal separation `E_raw -> E_vis -> photons -> sensor -> charge` is strong | `geant4/src_patch/ScatteringGenerator.cc`, MC weight adapter, single-stave Geant4 | Paper MC identity/provenance remains incomplete. #1178 sampler numerical repair is now later than the original manuscript status, but #1053/#1179/#1311 still block production MC. Historical `output_krakow_1M.root` is diagnostic only. | Update status wording for #1178 closure; regenerate publication MC with complete source/geometry/physics/build/seed manifest and model/nuisance IDs. Cite exact p-d Table-VI source. |
| 05 Data taking | Historical inventory is clearly gated; run-family depth difference is the candidate central data result | raw HRD 8x16 lineage, pulse-table builders, `reports/studies/data_side` | 640737 selected-pulse count belongs to a historical selected product; raw rebuild has a different count and incomplete provenance closure. A run-period/baseline/threshold mechanism could mimic part of Sample-I/II difference. | #1318: build pre-threshold event-level B2/B4/B6/B8 table from raw 8x16; freeze polarity/baseline/amplitude estimator; show run-block intervals, label permutation and threshold/baseline controls. |
| 06 Timing | Correct covariance formula and refusal of unjustified `sqrt(2)` are publication-safe | `scripts/real_data_cfd_timing.py`, timing validation docs | 5207 / ~38 ns is currently a negative/format-limited result. Component identity, polarity, sample period provenance, geometry/TOF and run dependence still gate stronger interpretation. | #1320: complete 8x16 authorising run with fraction/component stability, robust tails, run-block uncertainty, wrong-component control, source-bound TOF sign/magnitude. Caption as pair residual unless deconvolution is independently justified. |
| 07 DeltaE-E | Observable definition is now correct; numerical bundle remains properly gated | `scripts/single_stave/paper_956_deltaE_E_publication.py`, `_deltaE_E_core.py`, data bridge | Active producer still pre-censors at 1000 ADC, converts absent selected pulses to zero, hard-codes parity, aliases physical/readout columns, uses unresolved 7000-ADC 'saturation', overlapping MC sample proxies and legacy-weighted MC. | Fix producer before any rerun. Preserve missing/below-threshold/measured-zero separately; apply thresholds after event construction; separate `edep_layer_*` from `edep_readout_*`; source mapping/weights/trigger; add known-answer conservation tests and dependence-aware uncertainty. |
| 08 Optical response | Causal stage accounting is the correct conceptual framework | current `geant4/single_stave` source, optical tables, SiPM layer | Historical July grid predates repaired cladding objects and later explicit contracts. WLS quantum-yield/multiplicity, fibre-SiPM interface, direct Y11 light, phase-space transfer and response-boundary nuisances remain. | #1303/#1322: regenerate current model with `E_raw` and `E_vis`, stage counters, current fingerprints, paired nuisance branches and position/angle coverage. Report absolute response only at the response boundary actually modelled. |
| 09 Energy reconstruction | Definitions/desired held-out protocol are sensible; current result is non-authorising | `scripts/single_stave/paper_a09_heldout_edep_reconstruction.py` | Producer targets `edep_scint_MeV` (= Birks-visible) while calling it deposited energy; saturation loss sign is wrong; only two nearly coincident held-out target-energy points; zero/missing uncertainty; eventwise OLS errors ignore grid-level transfer; model choice touches holdout; no real position test. | #1297/#1302/#1322: explicit `E_raw` and/or `E_vis` target; regenerate current grid with broader held-out energy/position/species coverage; nested/frozen model choice; group-aware uncertainty; signed known-answer saturation metric; shuffled-target negative control. |
| 10 Discussion | Correctly emphasizes mechanism/limitations | all final results | Currently discusses candidate/blocked results rather than a closed set of measured results. Risk of calling deepest active readout 'stopping' and run-family difference 'trigger effect'. | After reruns, separate observation from causal interpretation; discuss sparse segmentation, censoring, source/geometry/optical nuisances quantitatively. |
| 11 Conclusions | Appropriate internal fail-closed conclusion, not a submission conclusion | final claim set | Explicitly says the work is not yet a quantitative performance publication. That is correct now, but must be replaced for submission. | Rewrite only after the final claim ledger contains the authorising result set. Every numerical conclusion must have source-table/hash/uncertainty traceability. |
| 12 Reproducibility | Strong written contract | claim ledger, manifests, build receipt, validator | Written requirements are much stronger than automated enforcement. Current final figure/source-data/table directories are empty while structure validation can still pass. | Add a submission-mode scientific package validator; require final artifacts + source tables + claim authorisation + hash/manifest consistency + exact build head. |
| Appendix A/B | Useful collaboration audit trail | issue tracker + repo evidence paths | Too much internal issue/path bookkeeping for a final journal manuscript; Appendix A is already stale around #1178. | Keep during internal review. Before submission, move issue/path audit material to supplementary/reproducibility metadata and replace with a concise data/code availability statement. |

---

# Confirmed code/result defects still present on current main

## P0-1 — DeltaE-E publication producer must not be rerun unchanged

`paper_956_deltaE_E_publication.py` still contains all of the following current-head defects:

- `S00_CUT_ADC = 1000.0` is applied to a selected-pulse-derived event table before the advertised lower threshold scans;
- `SAT_ADC = 7000.0` is named as saturation without a source-bound hardware transfer/censoring threshold;
- `READOUT_PRIMARY = (1,3,5,7)` is a local hard-coded mapping while the paper/BOM/current detector-map surface uses a competing 0/2/4/6 mapping contract and hardware truth is not closed;
- physical columns `edep_B0...edep_B7` are created, then `edep_B2/B4/B6` are overwritten with readout aliases and `edep_B8` added. Any generic `edep_B*` full-layer sum is therefore not a unique physical-layer sum;
- the block constructing `edeps` / `edep_cols` is duplicated in the source;
- MC Sample II is populated for every B-entering event and Sample I is additionally populated for coincidences, so the two MC sample labels overlap while the beam-data samples are different run families;
- species is assigned by the PDG contributing the largest deposit in the selected first B layer rather than a track-identity/entrance-primary contract;
- `PrimaryWeight` is taken from the first jagged value with no proof in this producer that all repeated hit-level values are identical or that the campaign measure makes that field valid;
- run bootstrap defaults to only 200 replicates for central intervals.

**Required disposition:** repair producer and tests before #1321 figure production. Do not use old result files as numeric seeds for the paper.

## P0-2 — Energy reconstruction producer must not be promoted unchanged

`paper_a09_heldout_edep_reconstruction.py` currently:

- defines the target as `edep_scint_MeV`, which the single-stave source distinguishes from raw deposited energy;
- computes `max(0, (pe_sat_readout - n_detected_pe)/n_detected_pe)`. For the occupancy transform where the saturated value is no larger than unsaturated detected PE, this clips the physical loss to zero by construction;
- fits eventwise OLS and reports eventwise slope/intercept standard errors despite only a few independent grid conditions;
- evaluates fixed train points `d70,p100,p140` and held-out `d110,p60`; the two held-out target-energy distributions are too close to establish a resolution-vs-energy curve;
- gives the bias panel `yerr=0` and gives `sigma68` no uncertainty;
- copies `entry_x_cm` if present but does not perform position-stratified transfer validation;
- compares a species-aware model on the same held-out set, which cannot then be treated as an untouched final test set if model choice is based on that comparison;
- has no shuffled-target or deliberately mis-specified-response negative control.

**Required disposition:** replace by an explicit-target, group-aware, pre-registered held-out analysis after the optical grid is regenerated.

## P0-3 — Publication validation is structural, not scientific

Chapter 12 requires every number/figure to be machine-reconstructable with inputs, hashes, weights, uncertainties and evidence class. `validate_publication.py` presently checks required files/directories/chapters and quarantine naming/status only. It does not enforce the Chapter-12 contract.

**Required disposition:** add a separate submission-readiness validation layer rather than weakening the present fail-closed working-build behavior.

## P0-4 — Current final artifact namespaces are empty

Submission cannot be declared ready while all three conditions hold:

- no non-README files in `publication/figures/final/`;
- no non-README files in `publication/figures/source_data/`;
- no non-README files in `publication/tables/final/`.

This must become an automated submission gate.

## P0-5 — Current-facing WIKI can override the canonical scientific state

`WIKI.md` still presents the selected-pulse inventory as `VALIDATED`, describes the old B2-vs-B4 correlation as DeltaE-E, and describes 2.92 MHz as a data-derived Rmax. The same file says the canonical ledger wins on conflict, which is not sufficient: readers and generated figure surfaces still see the stale promotion.

**Required disposition:** #1304/#1299 must make generated/current-facing status derive from the canonical ledger or fail CI on divergence.

---

# Ordered finish-to-publication queue

The order below is a dependency order, not simply editorial priority. Later tasks must not be used to bypass earlier physics contracts.

## Stage 0 — freeze truth surfaces and prevent stale promotion

### PAPER-FINISH-00A — synchronize current-head issue/status state
**Priority:** P0  
**Dependencies:** none  
**Action:** update publication status surfaces so #1178 is recorded as a repaired/closed deterministic sampler atom while #1053/#1179/#1311 remain the publication MC blockers. Audit all current-facing references to #1178 before changing scientific conclusions.  
**Acceptance:** STATUS, Appendix A, claim/source docs and issue tracker do not disagree on whether #1178 itself is open.

### PAPER-FINISH-00B — enforce one scientific claim source of truth
**Priority:** P0  
**Dependencies:** #1304  
**Action:** make `docs/claim_ledger.csv` canonical; generate/check publication/paper/WIKI status from it; distinguish rendering QA from scientific authorisation.  
**Acceptance:** a hostile fixture that marks a canonical claim GATED while a WIKI/figure says VALIDATED fails CI.

### PAPER-FINISH-00C — add submission-mode scientific package validation
**Priority:** P0  
**Dependencies:** 00B  
**Action:** extend tooling so `submission-ready` fails if any final figure/table lacks source data/result/manifest/hash/allowed claim status or if the PDF build head differs from the final reviewed head.  
**Acceptance:** current package intentionally fails this gate for the empty final namespaces and pending/gated manifest rows.

## Stage 1 — experiment/data contracts

### PAPER-FINISH-01A — installed hardware/BOM closure
**Priority:** P0  
**Owners/issues:** #1296, #1317  
**Action:** source-bind installed stave dimensions/material, fibre/end readout, sensor operating point, target, arm layout, trigger counters, channel map and run-relevant changes from collaboration records.  
**Acceptance:** every exact Figure-1/2 annotation has evidence class + source + revision/hash; unresolved values are explicitly schematic/unknown.

### PAPER-FINISH-01B — run/trigger/polarity authorisation
**Priority:** P0  
**Owners/issues:** #962, #1045, #954  
**Action:** freeze run-family ledger, channel polarity and hardware trigger semantics.  
**Acceptance:** no data result infers trigger causation from run labels alone; polarity cannot be chosen from the result it is meant to validate.

### PAPER-FINISH-01C — immutable 8x16 raw event product
**Priority:** P0  
**Owners/issues:** #993/#1318  
**Action:** create a content-addressed pre-threshold event-level product with 8 channels x 16 samples, composite event identity, channel states, raw/baseline/amplitude fields and complete per-file digests.  
**Acceptance:** exact input file count/digests, event counts, duplicate/corrupt accounting and producer hash are machine-readable; historical 18-sample products are not a dependency.

## Stage 2 — central DATA result

### PAPER-FINISH-02 — authorising longitudinal depth profile
**Priority:** P0  
**Owner:** #1318  
**Dependencies:** 01B, 01C  
**Action:** generate Sample-I/II B2/B4/B6/B8 profile from the pre-threshold event table; quantify run-block variation and estimator/threshold/baseline sensitivity.  
**Negative controls:** within-compatible-period run-label permutation; deliberately wrong polarity where safe; alternate baseline windows; threshold scan applied *after* event construction.  
**Acceptance:** final PDF/PNG/source table/result JSON/manifest; event and run counts; run-aware interval; effect cannot be explained solely by one run period/baseline convention; wording says run-family difference unless trigger cause is independently proven.

## Stage 3 — MC source and detector truth

### PAPER-FINISH-03A — production MC event-measure closure
**Priority:** P0  
**Owners/issues:** #1053, #1179, #1311 plus surviving source-support/runtime atoms  
**Action:** prefer regeneration from a current direct-sampled, provenance-complete campaign over rehabilitating `output_krakow_1M.root` unless exact historical provenance is recovered. Include Table-VI source ID/SHA, support/interpolation law, source uncertainty model, unit/direct weight semantics, source azimuth mode, seeds/build/Geant4/physics list/geometry/material hashes.  
**Acceptance:** generator-level CDF/source law closes; every analysis panel reports event measure diagnostics; no legacy `PrimaryWeight` is consumed merely because the branch exists.

### PAPER-FINISH-03B — MC longitudinal profile and sparse segmentation closure
**Priority:** P0  
**Owner:** #1319  
**Dependencies:** 01A, 01B, 03A, mapping closure/nuisance  
**Action:** keep `edep_layer_0...7` immutable; create separate readout aliases; verify per-event conservation and unique full-layer sums with known-answer toys; propagate mapping/trigger nuisances if still unresolved.  
**Acceptance:** full and sparse depth profiles have source tables, uncertainty and weight diagnostics; no layer namespace collision is possible.

## Stage 4 — timing

### PAPER-FINISH-04 — 8x16 timing residual
**Priority:** P0 for final timing figure, P1 if timing is intentionally removed from paper scope  
**Owner:** #1320  
**Dependencies:** 01A/01B/01C  
**Action:** run component-safe CFD across fractions with frozen calibration where needed; report median, sigma68, RMS, tails, run-block intervals and TOF sensitivity.  
**Negative controls:** wrong pulse component; fraction chosen without width minimisation; shuffled channel pairing; high-amplitude diagnostic without calling 7000 ADC hardware saturation.  
**Acceptance:** final result remains a pair residual unless covariance/deconvolution is independently justified; 10 ns sampling is not claimed to be the sole origin of ~38 ns.

## Stage 5 — DeltaE-E/PID topology

### PAPER-FINISH-05A — repair #956 producer
**Priority:** P0  
**Owner:** #956  
**Dependencies:** 01B/01C, 03A/03B  
**Action:** pre-threshold data amplitudes; explicit missing/below-threshold/zero/clipped states; threshold scan downstream; unique physical-layer namespace; source-bound/propagated readout mapping; valid event measure; trigger proxy clearly separated.  
**Unit tests:** unique full-layer sum known-answer event; alias collision; threshold-censoring fixture; missing != zero; weight cardinality/constancy; sample-overlap contract.

### PAPER-FINISH-05B — final DeltaE-E figures and inference
**Priority:** P0  
**Owner:** #1321  
**Dependencies:** 05A  
**Action:** produce matched DATA Sample-I/II and MC sparse/full panels; include zero-downstream fraction, conditional distributions/quantiles and a suitable dependence statistic with run/event/weight-aware uncertainty; use B4-only and wrong-parity controls.  
**Acceptance:** no material-budget/PID-separation causal claim unless nuisance scans support it; source tables and uncertainties committed.

## Stage 6 — optical simulation

### PAPER-FINISH-06A — current-source optical grid
**Priority:** P0  
**Owner:** #1303  
**Dependencies:** current source build/provenance + #1088/#1083/#1084/#1035 dispositions  
**Action:** regenerate with distinct `E_raw` and `E_vis`, distinct cladding objects, strict optical table inputs, explicit WLS multiplicity model, defined sensor/SiPM response boundary and position/angle phase space.  
**Acceptance:** current build receipt/fingerprints, stage counters, source tables, paired nuisance branches; July grid visibly historical/superseded.

### PAPER-FINISH-06B — optical-stage result
**Priority:** P0 if absolute response remains in paper; P1 if narrowed to model-method section  
**Owner:** #1322  
**Dependencies:** 06A  
**Action:** report conversion stages with denominator definitions and model-systematic envelope.  
**Acceptance:** no bare PE/MeV denominator; label PE per raw deposited MeV and/or per Birks-visible MeV explicitly.

## Stage 7 — held-out energy reconstruction

### PAPER-FINISH-07 — corrected reconstruction and energy-resolution figure
**Priority:** P0 if energy performance is a paper claim  
**Owners:** #1297/#1302/#1322  
**Dependencies:** 06A/06B  
**Action:** choose `E_raw` and/or `E_vis` as separate estimands; broaden held-out energy coverage; freeze train/model selection before final test; use grid/run-aware bootstrap or hierarchical uncertainty; evaluate species and position transfer; add physically signed saturation/occupancy diagnostic and negative controls.  
**Acceptance:** bias/sigma68/RMS/tails all have uncertainty; adequate energy leverage for any trend; no holdout retuning; result and figure source tables bound to exact current optical grid.

## Stage 8 — paper conversion from audit report to journal article

### PAPER-FINISH-08A — results-first manuscript rewrite
**Priority:** P1 after Stages 2-7  
**Action:** remove issue numbers and internal repository bookkeeping from Abstract/Introduction/Methods/Results/Discussion wherever not scientifically necessary. Move detailed gates/evidence paths to supplementary reproducibility material.  
**Acceptance:** a reader can understand the experimental question, apparatus, methods, results, uncertainties and limitations without GitHub issue context.

### PAPER-FINISH-08B — references and physics checks
**Priority:** P1  
**Action:** cite the primary p-d source (Ermisch PRC 71 064004), current HIBEAM/NNBAR detector/framework papers, Geant4, manufacturer datasheets where appropriate, and primary/authoritative sources for any stopping/range or optical assertions. NIST PSTAR must be described as a **proton** reference only; no deuteron range may be attributed to PSTAR.  
**Acceptance:** every nontrivial external numerical/material/physics statement has a correct primary/authoritative source.

### PAPER-FINISH-08C — final abstract/conclusion synchronisation
**Priority:** P0 at submission freeze  
**Action:** enumerate every numeric token in abstract/conclusion and map it to an allowed claim ID + result/source table + uncertainty.  
**Acceptance:** adversarial reviewer can recompute every headline number and finds no GATED/BLOCKED/SUPERSEDED claim.

## Stage 9 — final reproducibility and submission freeze

### PAPER-FINISH-09 — exact-head submission gate
**Priority:** P0  
**Dependencies:** all included-scope stages  
**Action:** rebuild all final figures/tables/PDF on one exact clean head; record full build/source receipts; run scientific validator, tests and four-pass claim review.  
**Acceptance:** non-empty final figure/table/source-data namespaces; zero PENDING/GATED artifacts referenced by the manuscript; claim statuses synchronised; final PDF build receipt points to the exact reviewed head; no known P0 paper blocker remains for the retained scope.

---

# Scope decision that can shorten the critical path

If hardware/optical/energy closures cannot be completed on the publication timescale, the scientifically defensible alternative is to **narrow the paper** rather than keep placeholder performance claims. A narrower paper could focus on:

- source-bound CCB test-beam apparatus at the level actually known;
- authorising 8x16 beam-data longitudinal response/run-family topology;
- the format-limited timing result as a negative DAQ-method result if useful;
- sparse-segmentation implications using only provenance-complete MC;
- corrected DeltaE-E topology if Stage 5 closes;

and explicitly defer absolute optical/energy performance to a separate current-model simulation paper. This scope still requires Stages 0-5 and 9; it does not permit use of the historical optical/8.9% numbers.

---

# Data publication / Hugging Face action

A public immutable reduced-data mirror would materially improve reproducibility. If collaboration policy permits, create a versioned dataset containing **reduced non-sensitive authorising products**, not necessarily raw beam ROOT:

- file-level raw-input manifest (names or opaque IDs, bytes, SHA-256, run IDs, schema);
- pre-threshold 8x16 event-level reduced amplitude/timing table used for the paper;
- final MC truth/reduced tables with generator/geometry/model IDs and event weights;
- every final figure source table;
- claim/result manifests and schemas;
- dataset card explaining units, event identity, selection, missing/censoring semantics, evidence status and license/access constraints.

Pin an immutable dataset revision in the manuscript/data-availability statement. Do not make the paper depend on an unversioned dataset `main` revision.

---

# Handoff protocol for the next AI/reviewer session

1. Read this file, `publication/STATUS.md`, `publication/figures/MANIFEST.csv`, `publication/tables/MANIFEST.csv`, and the canonical `docs/claim_ledger.csv` before touching a central result.
2. Choose the **lowest-numbered unfinished PAPER-FINISH stage whose dependencies are closed**. Do not jump to figure polishing while an upstream measurand/event-measure contract is unresolved.
3. For each task, preserve four artifacts: implementation/test, immutable result+manifest, adversarial validation evidence, and claim/manuscript synchronisation.
4. A task is not complete because a script exits 0 or an issue is closed. Verify physics estimand, statistical unit, provenance and downstream wording separately.
5. If new evidence contradicts this queue, update this file and the canonical claim surface in the same change; never leave a stale publication status behind.

## Recommended immediate next action

Start with **PAPER-FINISH-00A + 00C**, then **01C/02** if the raw 8x16 data are operationally available. This gives the paper its first genuinely authorising central data figure while the longer MC/optical closures proceed in parallel.

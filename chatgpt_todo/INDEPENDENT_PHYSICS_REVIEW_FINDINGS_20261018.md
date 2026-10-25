# Independent physics review — first-pass evidence and gaps (2026-10-18)

**Supervisor:** https://github.com/SzeChunYiu/ccb-testbeam/issues/1628  
**Prior master:** https://github.com/SzeChunYiu/ccb-testbeam/issues/1594  
**Reference tree:** SzeChunYiu/ccb-testbeam main at a61427813344e29047ca9eb9b764182eb29e4c83  
**Status:** STATIC_REVIEW_ONLY / NO SCIENTIFIC_CLEARANCE / NO NEW ROOT OR GEANT4 RUN EXECUTED  
**Matrix:** OPEN_ISSUE_SCIENTIFIC_CLOSURE_MATRIX_20261018.csv (25 original open issues)  
**Existing audit implementation:** https://github.com/SzeChunYiu/ccb-testbeam/pull/1595 (open and unmerged at snapshot)

These are observations to test and prioritize, **not** independently reproduced experimental results. In particular, no 6.4-GB raw archive, installed-detector hardware measurement, ROOT analysis or compiled Geant4 simulation was available to this reviewer. Static code inspection is not a substitute.

## Independent review lanes

**A, detector/DAQ:** recover physical readout semantics and every quantity's measurement anchor, deny acceptance of unsupported hardware specifications.  
**B, transport/nuclear/optical:** test generator phase space and weights; conserve energy and 4-momentum; compare source domains; propagate material/optical nuisances.  
**C, statistics/ML:** independently define estimands and sampling units; detect leakage/selection multiplicity; demand untouched final validation and valid coverage.  
**D, code/provenance/adversary:** trace immutable data and executed binaries; independently recompute and run mutation/negative fixtures; verify CI cannot authorize false claims.

A result requires appropriate **separate evidence from all affected lanes**; assigning roles to AI readers does not create independent data.

## F0: Static code-level faults on reference main

### F0-01 [CONFIRMED CODE; P0] Rmax checker reports green for its own FLAWED status

- main scripts/check_rmax_formula.py, function main near the final lines: accepts status in ("VALIDATED", "FLAWED", "BLOCKED") and returns exit code 0 with PASS. This is a direct logical fail-open; it does not mean an invalid rate physically occurred.
- Open #1607 reports a fixed version 3 in the **unmerged** PR #1595; branch code was inspected and checks governance_status == PASS before success.
- Falsifier: feed an internally inconsistent but parsable ledger/WIKI and demand exit != 0, a failure receipt, and a failing CI job. Test benign BLOCKED-with-consistent-metadata as a *governance pass with scientific acceptance still BLOCKED*.
- Risk: an automated green code can be falsely construed as physical approval for Rmax.

### F0-02 [CONFIRMED SOURCE; P0] Polarity provenance status differs across main and unmerged audit patch

- main configs/channel_polarity_v1.json: LOCKED_FROM_DUPLICATE_READOUT_CONVENTION; provenance authorising flags true. This is not a defensible independent hardware/pulse measurement.
- The PR #1595 version changes status to GATED_FROM_DUPLICATE_READOUT_CONVENTION and authorising=false. main's scripts/channel_polarity.py defaults to v1; its loader validates JSON sign values but does not independently establish authorizing physical evidence.
- configs/channel_polarity_v2.json describes the 128-word truncated staging product desynchronizing 8x16 segmentation relative to 144-word channel-major frames; reported v2 sign inversion and B4/B6/B8 amplitude were later retracted. This case requires an independent raw-byte fixture, not a preference vote from the same corrupted product.
- Falsifier: synthetic 8x18 vs first-128-word truncation, fixed per-channel signed pulse, injected baseline step, even/odd duplicate pair; demand wrong-width rejection and *no* promoted amplitude/timing from unmeasured polarity. Then independently reproduce with actual hash-matched 144-word ROOT before authorizing.
- Upstream blockers #1603/#1617.

### F0-03 [CONFIRMED SOURCE; P0] Incomplete evidence layer on main

- main .github/workflows/ list lacks global_scientific_audit_gate.yml; open PR #1595 says it adds it. Current mc_validation_ci.yml performs focused unit/SiPM tests and curated ruff but does not run all historical data and nuclear transport jobs.
- Falsifier: inject a syntactically valid, physically false public timing/PID assertion into test branch and verify global promotion workflow vetoes it; prove the workflow actually runs on PR and main integration. Separately run real reproduction on data/compute-capable host.
- Important distinction: **green CI != physics validated.**

### F0-04 [CONFIRMED SOURCE; P0] Publication A09 plot has zero placeholders

- scripts/single_stave/paper_a09_heldout_edep_reconstruction.py::make_figure contains yerr=[[0],[0]] for bias; sigma68 per-point uncertainty is also not displayed there. Producer implements bootstrap metrics elsewhere, so the plotted zeros are not measured zero variance.
- The producer's E_vis (Birks-quenched) vs E_raw (unquenched) targets should be separately named and the heldout/model calibration domain audited; historical reporting records the A09 executed producer as /tmp/ file and null commit, which is a distinct provenance gap.
- Falsifier: invalid yerr zeros cause regression failure; generate interval for each plotted point or omit unestimated error bars. Freeze model before heldout measurement; link executed code hash, input/output hash, uncertainty resampling group, and E_vis/E_raw caption.
- #1592; review broader paper audit in chatgpt_todo/PAPER_COMPLETION_AUDIT_20260814.md.

## F1: Mechanism-level problems needing physical/empirical tests

### F1-01 [CONFIRMED MISSING PHYSICAL MODEL; P0] HRD-first-layer trigger proxy vs hardware

- src/ccb_mc_validation/truth/trigger.py explicitly says BLOCKED and MC_TRIGGER_PROXY; Sample I uses first-A/first-B-layer charged-hit coincidence; Sample II uses first-B entry. This is **not** detector hardware trigger response.
- A comment on #1045 states **reported** 554/1,000,000 proxy arm coincidences and 0/1,000,000 T1&T2 coincidences in a simulated implementation, with T1/T2 placement hypothesized as cause. Artifacts are from **unmerged** PR #1544 and were not independently rerun here. Zero observed is not proof of zero physical efficiency.
- Critical falsifier: source-bound real trigger counter/survey and thresholds; exact-model repeatable 1M run with seed/config SHA; test full hardware, truth crossing, first-layer proxy and data on matched domain, preserving migration and uncertainty by species/energy/angle/secondary multiplicity. Test geometry counterfactuals without tuning to desired result.
- #1045/#1608/#1617.

### F1-02 [CONFIRMED HARDWARE SPEC CONTRADICTION; P0] 100-MS/s 14-bit versus V1742 identity

- docs/contracts/ADR-DAQ-HARDWARE-SAMPLING-1014.md blocks assertion that a 12-bit up-to-5-GS/s V1742 is native 14-bit 100-MS/s V1724. The apparent sample step in a waveform is not a sufficient DAQ serial/model identification.
- Demand acquisition crate/firmware/run logs, original unpacker source and known ADC traces. Test actual full-scale, saturation and time sampling independently; propagate electronics uncertainty to CFD/timewalk and charge/PID.
- Do not promote a digitizer model merely because the data array is 18 samples long.

### F1-03 [EXTERNAL MODEL DOMAIN; P1] scattering support/weight/energy provenance

- geant4/src_patch/sigma_pd_cm_190.source.json binds K. Ermisch et al. 190-MeV p+d table to 26.49°–169.78° CM support, 28 rows and statistical/systematic notes.
- geant4/src_patch/scattering_source_model_v1.json explicitly truncates angular support and direct-samples with unit weights, yet model uncertainty not propagated and compiled Geant4 seed/production closure pending.
- Generator ScatteringGenerator.cc computes outgoing relativistic kinematics with Ekin from target-depth beam-energy loss while cross-section table is nominal 190 MeV; whether the difference matters is an **unquantified sensitivity**, not a proven bug.
- Check CM theta solid-angle factor sin(theta), φ full 2π, differential cross section and uncertainty covariance; source-energy variation through target, kinematic invariant s and outgoing kinetic energies, event weight applied once, subtable-angle extrapolation as alternate model.
- Main sources: https://doi.org/10.1103/PhysRevC.71.064004 and #1608.

### F1-04 [KNOWN DOMAIN LIMIT; P1] QGSP_BIC neutron tracking-time policy

- docs/contracts/NEUTRON_TRACKING_TIME_CUT.json records implicit 10-us QGSP_BIC neutron time cut, which does not configure transport. Official Geant4 description agrees: https://geant4.web.cern.ch/documentation/dev/plg_html/PhysicsListGuide/reference_PL/QGSP_BIC.html
- Requires runtime effective-cut receipt, neutron-rich known-answer shorter/default/longer-cut fixture, late quantiles and separate finite waveform DAQ timing; late-neutron exclusion in transport != physical DAQ censoring.
- #1091/#1608.

### F1-05 [DEFINED PHYSICAL DISTINCTION; P0] energy deposition, visible energy and projectile stopping not interchangeable

- Use distinct input projectile kinetic energy, energy lost by projectile (including escaping secondaries), charged step electronic/nuclear dE/dx, scintillator Edep, Birks E_vis and digitized PE/ADC; define both observable and per-step integration.
- NIST PSTAR database is for protons, **not** a direct reference for deuterons: https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html
- Falsify wrong equivalence with a known-answer material slab and measured projectile entry/exit kinetic energy; compare independent stopping integral and local detector deposit; vary production cut and escape. Require appropriate separate deuteron reference or bounded validated surrogate.
- #1606/#1602/#1608.

### F1-06 [OPEN STATISTICAL LIMIT; P0] multiple study winners may be selected and evaluated on the same test pool

- Example: open PR #1554 proposes corrected-source MC PID full AUC 0.953 replacing 0.898 while some folds lack two classes and remain NaN; don't compare only available folds as if complete independent validation.
- PR #1561 states a pileup uncertainty-calibration proxy previously included injected truth separation, making leakage-risk review necessary for descendants.
- BLK-P04P-001 documents acceptance coverage 0.501643 with run-bootstrap CI [0.478103, 0.538255] near a 0.5 threshold, without preregistered confidence-rule.
- Require label-to-feature causal graph, target shuffle, group/seed split, model-selection history, run/period independent final test, covariance bootstrap, coverage test, denominator and class counts. Never select on a final test set.
- #1609/#1614.

## F2: Recursive propagation and publication cautions

- WIKI.md header currently asserts "Every claim is traceable to source" while #1598/#1610 explicitly say not yet established. Treat as overclaim; record exact line in claim ledger and gate revision.
- PROJECT_REPORT.md and FINDINGS_SYNTHESIS.md are explicitly marked stale but retain strong historical "PASS" wording; all read-only/public copy paths need coherent supersession and source dates.
- README and WIKI typically label 0.089 ns as MC_METHOD_CLOSURE, not measured beam timing. Preserve this distinction. A future old table or renamed caption cannot upgrade the claim.
- publication/STATUS.md states FAIL_CLOSED/NOT_SUBMISSION_READY; no evidence this review changed that.
- Rmax arithmetic model P>=1=1-exp(-r tau) assumes stationary independent arrivals and a defined window. It **does not** identify input event-arrival rate from threshold-selected pulse count without live exposure and trigger efficiency. Definitions and data anchors are obligatory.
- Scintillator optical manufacturer's typical parameters, device PDE/crosstalk, fibre attenuation/reflectivity and Geant4 physics assumptions are not observations of the installed instrument without run-/position-specific calibration.
- Figure uncertainty, visual smoothness and high classifier AUC do not fix circular statistics or selection mismatch.

## Priority dependency ordering and handoff

1. **P0 governance:** Reconcile PR #1595 with current main and verify fail-closed negative tests (Rmax status, polarity and DAG), without prematurely merging conflicts.
2. **P0 external evidence:** #1617 hash-bound **8x18 144-word** raw and hardware truth, trigger geometry/DAQ/clock/temperature, immutable run masks and untouched sample.
3. **P0 trigger & MC:** Independently reproduce reported #1045 simulation with exact real geometry and sensitivity; verify generator/Geant4 source, optical/digitizer physics, weights and neutron policy.
4. **P0 methods:** Rerun waveform timing/charge/energy/PID and pileup/rate from independently verified inputs and explicit uncertainty, with model selection frozen before holdout.
5. **P0 publications:** Audit complete fleet, map supersessions, regenerate figures and front-door claims, hostile sign-off, auto-gate paper release.

**Next session must:** read issue #1628, all 25 linked original open issues, this file, the CSV closure matrix and the PR #1595 audit ledgers **on its branch**; identify first available unblocked atom; run independent evidence acquisition/negative fixtures and record execution. No checkbox may be checked solely because this review report was committed.

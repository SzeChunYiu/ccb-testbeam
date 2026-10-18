# Issue #1628: executed verification and physics research

Date: 2026-10-18. Main examined: `a61427813344e29047ca9eb9b764182eb29e4c83`. Continuation of #1628 in draft PR #1629; original master #1594. **Scientific acceptance: NOT AUTHORIZED.**

## Execution and evidence scope

This pass executed **45 probe records**: 9 actual Rmax command-line invocations, 23 waveform/A09/statistics component records, and 13 actual promotion-validator invocations. The required-behavior checker recorded **27 unmet requirements**, including repeated representations of the same defect; these are not 27 independent bugs. Other records are positive controls, numerical checks, and statistical/domain counterexamples. The replay completed and intentionally exited **1**, not a misleading success. A separate compact key-contract replay executed 14 checks and failed 13; it overlaps these witnesses and must not be counted as independent discoveries.

Independent Python calculations additionally exercised **200,000 angular inverse-CDF draws**, **12,006 elastic energy/angle points**, a **20,000-repetition statistical Monte Carlo**, synthetic frame truncation, and arithmetic from a committed trigger-migration table. These were **not compiled Geant4 transport runs or detector measurements**.

Four complete retrieved Python files matched Git blob SHA before execution. A09 testing used unmodified retrieved function bodies with injected imports/constants and a mocked ROOT decoder returning explicit DataFrames. It did not run the complete A09 CLI or read real ROOT bytes. Environment: Python 3.13.5, NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0. ROOT readers and the authoritative beam archive were unavailable locally.

Review lenses in this single session: detector/DAQ; nuclear/optical transport; statistics/ML; software/provenance. Distinct numerical formulations were used where stated. These lenses are not four independent human reviewers, and hardware acceptance remains outstanding.

## 1. Confirmed faults and acceptance gaps

### V01 — Rmax failure status becomes CLI success [P0; #1607]

Exact main CLI returned 0 for five fixtures it classified FLAWED: promoted blocked claim, invented rate, wrong time unit, missing withholding notice, and an explicitly forbidden overclaim. Missing/duplicate claim controls correctly returned 2; a consistent scientifically BLOCKED fixture correctly passed governance. A sixth overclaim using different wording escaped phrase checks. Distinguish the definite exit-code defect from the limited coverage of a phrase blacklist.

Integrate the PR #1595 fix only after these negative cases are rerun. No production source was changed in this verification pass. At the stored 124.79018394263471 ns window, 5% fixed-window Poisson overlap corresponds to **0.4110362912 MHz**, whereas 3.05 MHz implies **31.6556%** overlap. Neither arithmetic result measures detector throughput or live exposure.

### V02 — Promotion flags are not evidence verification [P0; #1611/#1616]

Exact PR #1595 science/ML validators correctly reject a blank promoted numerical row and an ML row missing required PASS flags. They nevertheless accept promoted rows with NOT_EVALUATED uncertainty/systematics, nonexistent figure source and malformed hash, nonexistent physics derivation, duplicate IDs, and a blocked ancestor. Unknown statuses silently skip validation; science and ML promotion-status vocabularies differ (PRODUCTION/COMPLETE). Writing PASS/COMPLETE satisfies the ML validator without supplying a receipt.

These findings delimit implemented metadata checking; they do not establish that every unimplemented check was advertised as implemented. Repair: explicit status enums; strict CSV shape/unique IDs; typed uncertainty; immutable file/hash/claim references; checked dependency edges; evidence-backed reviewer receipts. Test the complete CI chain too. Metadata-schema success is not empirical validation.

### V03 — Polarity representation changes the physical contract [P0; #1603]

`apply_polarity` rejects 0, 2, 0.5 and 1.5 in vector form but accepts mapping form by coercing to int, erasing or rescaling the waveform. Validate the same sign domain before coercion for mappings, arrays and loaded JSON.

`infer_channel_polarity` labels one strong positive observation MEASURED and authorising. The routine documents empirical agreement rather than confidence: this is an authorization-boundary gap, not proof deployed signs are wrong. One positive vote is not a robust calibration; 1/1 has a 0.025 lower endpoint for an equal-tail 95% binomial interval. Preserve the correctly rejecting zero-signal control.

### V04 — Dropout masking has an untested pulse-width domain [P1; #1603/#1605]

A synthetic causal exponential with 7 ns decay and 10 ns sampling loses its largest sample: peak100 becomes23.965 and retained charge is0.23965. A42 ns control is preserved. Thus the docstring's assertion that a genuine pulse is never masked is not universally true for sampled pulse shapes. This is not a measured CCB pulse or evidence of76% experimental charge bias. Establish installed impulse-response/phase support and test pulse preservation before authorizing polarity/amplitude.

### V05 — A09 can silently equate raw and visible energy [P0; #1592/#1606]

With `edep_scint_raw_MeV` absent, `load_grid` substitutes E_vis as E_raw. The returned frame has no incompleteness flag. The comment promising a flag is not an implemented gate. Missing unquenched energy must disable that estimand, not fabricate it. E_vis-only processing may continue with explicitly scoped outputs.

### V06 — A09 run identity and frozen split are not enforced [P0; #1606/#1609]

Mock decoded frames show: metadata energies70.1 and70.9 collapse to `proton_70`, producing40 duplicate run/event keys among80 rows; metadata deuteron/110 can disagree with decoded proton/70; a requested absent heldout run is silently omitted; overlapping train/test requests are accepted. Current hardcoded integer grid/disjoint lists do not prove historical leakage, but the loader/evaluator fails these boundary cases. Preserve source-file/seed identity and exact energy; enforce metadata consistency, required grid membership and disjoint event identities.

### V07 — A09 invalid energies produce inconsistent denominators [P0; #1609]

A fixture with40 heldout rows, five zero energies and three NaNs returns n_heldout40 while bootstrap uses32 finite residuals and headline median/RMS are nonfinite. Define one valid population, persist rejected counts/reasons, and reject nonfinite published results rather than JSON NaN or mixed denominators.

### V08 — The occupancy diagnostic is actually response retention [P0; #1604/#1607]

Main EventAction explicitly defines a legacy diagnostic F=N(1-exp(-D/N)); production ADC is generated separately by the SiPM core. A09 computes F/(F+max(0,D-F)), i.e. F/D for F<=D. This is retention, not fired-cell occupancy F/N. For N3600 and D1,3600,36000, A09 returns approximately0.999861,0.632121,0.099995; occupancy in this static model is0.000278,0.632121,0.999955. One decreases while the other increases. Rename the existing quantity, keep loss=1-F/D separate, and do not replace production recovery/crosstalk physics with this static approximation.

### V09 — A09 uncertainty is event resampling, not grid/run transfer [P0; #1609]

Header claims grid/run-aware bootstrap; implementation resamples pooled residuals individually and does not resample/refit the training calibration. This may represent a conditional event-sampling interval under explicit assumptions, but not run/grid transfer, calibration-fit uncertainty or a systematic envelope.

For a known-answer hierarchical Gaussian mean (20 groups,200 observations/group, group SD0.1, individual SD0.01), the actual generic bootstrap function's interval was **14.394 times narrower** than an independently implemented group bootstrap for one seeded dataset. This is not a correction factor for real A09 results.

A separate20,000-repetition exact Gaussian Monte Carlo found **5.355% coverage** [5.047%,5.676% MC CP95] for naive event-iid normal intervals nominally68%, versus **68.135%** [67.484%,68.781%] for the correct known-variance interval. This tests the hierarchy mechanism with normal SEM, not literal A09 bootstrap coverage or detector transport.

The zero-tail fixture returns [0,0] bootstrap bounds for0/40 tails. A one-sided95% exact upper bound is7.216%; confidence level and sidedness differ and are explicitly not a matched-level comparison. Zero observed failures never establishes zero physical failure probability.

## 2. Positive checks and source-model sensitivity

Using all28 repository nodes, a Python translation of the declared piecewise-linear node-PDF inverse achieved maximum CDF round-trip error **2.22e-16**, with no out-of-support draws among200,000. Independent integration of linear cross section times continuous sin(theta) differs in normalization by **0.48546%**; maximum nodewise normalized CDF difference is **0.00098137**. This is interpolation-model sensitivity, not an implementation defect or a detector uncertainty estimate.

The generator's elastic-energy formulas were compared with independent Kallen-invariant/Lorentz-boost calculations at2001 angles for each of1,10,60,100,190,250 MeV. Maximum outgoing-energy discrepancy was **5.12e-13 MeV**, energy-balance residual below **5.69e-13 MeV**. This verifies sampled algebra only, not cross sections away from190 MeV, compiled Geant4, target loss, final direction plumbing or detector acceptance/transport.

APS confirms the Ermisch paper includes190 MeV p+d differential cross sections. Full TableVI was not independently inspected; the28-row transcription remains repository-source evidence, not a completed paper-to-table audit. Support truncation is not physical zero probability outside measured angles. Runtime source bytes, energy dependence and covariance remain open.

A pure-pedestal144-word/8x18 fixture, truncated to128 words and wrongly viewed as8x16, generates apparent1000–2000 ADC excursions although no pulse was inserted. This establishes the artifact mechanism, not real-data bias magnitude.

PR1544 migration JSON at223280d03a86d74d1656b70528fc17eb4f87984e independently recomputes as550/1487=0.3698722259583 for deuteron and4/5598=0.0007145409075 for proton; proxy counts total554. No raw MC rerun. For0/554 the equal-tail two-sided95% upper endpoint is **0.66365%**; for0/1,000,000 the one-sided95% upper endpoint is **0.00029957%**. Denominators and confidence conventions differ. Neither establishes zero hardware efficiency. Confirm event overlap and weighting before pooling species.

## 3. Corrections to the audit plan itself

**Geant4 optical bookkeeping:** generated optical-photon energy must not be added to transport event energy balance. Use separate non-optical transport and optical-response ledgers. ParticleHP library/final-state-adjustment conventions also matter; do not impose one universal event-level tolerance independent of model and observable.

**Stopping:** PSTAR is proton-specific. CSDA range integrates reciprocal total stopping power; local scintillator Edep is not automatically projectile stopping power. Reference uncertainty is material/energy dependent. A deuteron-at-half-energy proton proxy needs separate justification.

**DAQ throughput:** CAEN V1742 is12-bit DRS4 with5/2.5/1/0.75 GS/s settings; V1724 is14-bit100 MS/s. V1742's110/181 us conversion deadtime would imply conditional per-busy-domain ceilings near9.09/5.52 ktriggers/s before other limits. These are not CCB measurements or evidence of installed board identity. Pulse-overlap rate, trigger acceptance and DAQ throughput are distinct.

**My earlier issue matrix is not a DAG:** five cyclic pairs are{1045,1608},{1597,1601},{1598,1611},{1599,1614},{1602,1612}; it also contains ALL and PR1595. Rename the dependency column to indicate related issue links. Split hardware acquisition, implementation, independent validation and publication into actual atomic prerequisites before topological scheduling; never silently drop physically necessary edges.

## 4. Existing CI inspected, not locally rerun

GitHub run39135979105/job117700458705 tested merge-preview `ee523985b5ae34a459bfa1e8a2c91279a9dc888c` (main plus original PR1629 head7c345687). Logs show **2357 passed,1 skipped,8 xfailed,1 xpassed**, plus **7/7 SiPM CTests**, submodule3627dc87137a9f33f511a755671414b11853c0a0. Integration tests excluded. This existing CI does not cover subsequent audit commits, full Geant4 or beam processing. Green baseline CI can coexist with the new counterexamples.

Artifact12139797377 ZIP SHA256 `02abe693d73969002ccd21d3ca6d89d6c227cdd6632a2c6f0bd35d7a5c677d8d`. Investigate XPASS and the test returning a dictionary rather than asserting. Preserve scientific failure evidence instead of treating collected test counts as physics validation.

## 5. Next atomic tasks; global science boxes remain open

- [ ] V01: integrate the Rmax nonzero-exit fix; replay every contradictory fixture and preserve scientifically BLOCKED status.
- [ ] V02: status enums, typed evidence, existing-file/hash/reviewer receipts, duplicate IDs and ancestor validation; complete-CI adversarial tests.
- [ ] V03/V04: sign-domain validation before coercion, minimum measured polarity support, installed pulse-preservation domain, authoritative144-word raw data.
- [ ] V05–V08: reject absent raw energy; enforce metadata, source/run/event identity, complete holdout, disjointness and finite denominators; rename retention; regenerate affected results/figures.
- [ ] V09: preregister conditional-event versus transfer estimands, calibration refits, covariance/systematics; claim-specific coverage and boundary-aware intervals.
- [ ] Bind all28 source rows to primary TableVI; compile and validate seeded transport with runtime source/cuts/model receipts and nuisance scans.
- [ ] Decompose issue cycles into a real atomic DAG and propagate invalidation to reports/figures/WIKI.
- [ ] Independent experimental, simulation, statistics and provenance review before promotion; #1617 external raw/hardware/material/untouched-validation inputs remain outstanding.

## Primary references inspected; applicability boundaries

1. https://geant4.web.cern.ch/documentation/dev/plg_html/PhysicsListGuide/reference_PL/QGSP_BIC.html — current11.4 guide:10us neutron default, reference list does not include optical physics; verify actual production version/processes.
2. https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/physicsProcess.html — optical energy accounting and ParticleHP model-dependent final-state treatment, not experimental response validation.
3. https://physics.nist.gov/PhysRefData/Star/Text/programs.html — proton/helium stopping/range definitions and uncertainty; not deuteron standard or installed material survey.
4. https://caen.it/products/v1742/ and https://caen.it/products/v1724/ — vendor specifications, not installed crate/firmware identity.
5. https://journals.aps.org/prc/abstract/10.1103/PhysRevC.71.064004 — Ermisch et al.(2005), identity/energy/CM scope verified from publisher abstract; full TableVI pending.
6. https://www.jmlr.org/papers/v11/cawley10a.html — Cawley & Talbot(2010), selection overfitting and evaluation bias; no quantitative bias estimate for this repository.
7. https://arxiv.org/abs/2007.07797 — Saravanan, Berman & Sober(2020), hierarchical resampling rationale; neuroscience effect sizes not transferred to CCB. Our statistical Monte Carlo is separately specified.

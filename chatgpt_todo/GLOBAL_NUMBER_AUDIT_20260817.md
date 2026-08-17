# Global Numerical Audit — 2026-08-17

## Why this exists

The project has accumulated hundreds of studies and thousands of numerical outputs. Several historically strong-looking conclusions were later downgraded when hidden selection differences, truth-level leakage, model circularity, quantity-definition ambiguity, incomplete systematics, or provenance gaps were discovered. This is therefore a repository-wide scientific-governance problem rather than a small collection of isolated mistakes.

The objective of this programme is stricter than the existing claim ledger: **inventory and audit every consequential number emitted by the analysis**, including intermediate numbers that propagate into later claims.

## Independent review panel

Every audit atom should be reviewed from four independent roles:

1. **Detector/data reviewer** — asks whether the observable is actually measured, whether trigger/readout/pedestal/saturation/deadtime/run conditions can bias it, and whether the event selection matches the physical question.
2. **Statistics/ML reviewer** — checks leakage, repeated model selection, multiplicity, resampling unit, CI construction, nuisance propagation, correlations, coverage, calibration, train/validation/test independence, and winner's curse.
3. **Simulation/physics reviewer** — checks Geant4 truth definitions, geometry/materials, generator assumptions, cross-sections, digitizer/SiPM response, circular MC closure, physical units, reference data, and whether the comparison observable is like-for-like.
4. **Reproducibility/provenance reviewer** — checks exact code/config/input hashes, row cardinality, joins, seeds, environment, deterministic reconstruction, artifact identity, and whether the reported number can be independently recomputed.

No number is promoted solely because one reviewer accepts it.

## Unit of audit

A **numerical atom** is any numeric value or interval that can affect interpretation or a downstream result. This includes:

- event/pulse/track counts and fractions;
- thresholds, cuts, windows, bin edges and constants;
- calibration constants and conversion factors;
- means, medians, RMS, sigma68, fit widths and tail fractions;
- efficiencies, fake/failure rates, acceptance and censoring fractions;
- AUC/AP/Brier/accuracy and regression metrics;
- chi-square, ndf, p-values, pulls, likelihoods and test statistics;
- slopes/intercepts/model coefficients;
- MC truth fractions and data/MC ratios;
- timing, energy, dE/dx, range and rate values;
- statistical and systematic uncertainties and covariance/correlation terms;
- extrapolated/projection values;
- expected/registered anchors used as gates;
- headline values copied into reports, README, WIKI, dashboards or papers.

## Required record for every number

Each numerical atom must receive a row in `NUMBER_AUDIT_LEDGER.csv` with:

- unique audit ID;
- literal value as printed and units;
- semantic quantity definition;
- source file/report and exact location;
- code/config producing it;
- exact input artifact identity where available;
- evidence class: DATA / SIMULATION / TRUTH_MC / SYNTHETIC / EXTERNAL_REFERENCE / ARITHMETIC / PROJECTION;
- selection and denominator definition;
- central estimator definition;
- uncertainty definition and resampling unit;
- nuisance/systematic coverage;
- independence status;
- reproducibility status;
- cross-check status;
- downstream dependents;
- trust state and reason.

## Trust states

- `REPRODUCED` — exact number independently recomputed from bound inputs/code; interpretation not necessarily validated.
- `VALIDATED` — reproduced and all applicable detector/statistical/physics/provenance checks pass with independent evidence.
- `CONDITIONAL` — numerically correct only under explicitly stated model/selection/calibration assumptions.
- `TRUTH_LEVEL_MC_ONLY` — valid only as simulation truth; cannot identify beam data.
- `MC_METHOD_CLOSURE` — reconstruction closes on MC; not detector validation.
- `GATED` — promising but missing a required independent test/systematic/provenance condition.
- `BLOCKED` — cannot be evaluated with currently available evidence.
- `FLAWED` — method/definition/comparison is invalid or materially misleading.
- `SUPERSEDED` — replaced by a better-defined or corrected quantity; retained for history.

`VALIDATED` is intentionally difficult to earn.

## Mandatory falsification tests

For every consequential number, apply all relevant tests rather than only those expected to pass.

### A. Reconstruction and arithmetic
- independent implementation or hand reconstruction of sufficient statistics;
- row-count/cardinality checks before and after every filter/join/groupby;
- unit/dimension checks;
- order/permutation stability where floating aggregation matters;
- exact denominator reconstruction for fractions/efficiencies;
- plot-to-table and report-to-result consistency.

### B. Selection and conditioning
- selection-before/after tables;
- trigger matching between data and MC;
- cut scans around every analysis threshold;
- alternative defensible event definitions;
- run/stave/channel dependence;
- censoring/truncation/deadtime/saturation tests;
- verify no selection uses future/downstream information that leaks the target.

### C. Statistical inference
- correct independent resampling unit (normally run/run-family when run-level correlations exist);
- nuisance/systematic variation, not just bootstrap statistical errors;
- covariance/correlation propagation;
- coverage checks for reported intervals where feasible;
- multiplicity/model-selection accounting;
- preregistered or untouched final validation sample for tuned headline methods;
- report worst slices, not only aggregate averages.

### D. ML leakage and selection bias
- target-shuffle sentinel;
- event-block and run-family shuffle/split sentinels;
- label-construction audit for self-referential features;
- duplicate/event identity leakage checks;
- feature preprocessing fitted on training only;
- hyperparameter/model-family selection separated from final evaluation;
- external transfer to untouched runs/staves/data mechanism.

### E. Physics and simulation
- distinguish truth-level, digitized-MC, reconstructed-MC and beam-data quantities;
- demonstrate data/MC selection equivalence before shape comparison;
- verify geometry/material budget and physics-list/generator assumptions;
- test sensitivity to digitizer, SiPM, Birks, gain, PDE, reflectivity, coupling, thresholds and noise;
- compare only like observables (e.g. projectile energy loss vs total local deposited energy);
- use independent reference data where available;
- never call shared-model closure an independent detector validation.

### F. External/independent anchors
At least one independent physical anchor is required for detector-performance promotion where applicable: pulser calibration, forced pedestal, beam-current scan, independent TOF/track length, survey/material measurement, external stopping-power/cross-section data, known source, redundant readout, or separate beam period.

## Global audit order

Audit in dependency order so corrupted primitives are not repeatedly rediscovered downstream:

1. raw data identities, schema, run list, branch/channel mapping;
2. pedestal/polarity/amplitude definitions and selected-pulse counts;
3. event keys, joins, duplicate handling and selection/trigger definitions;
4. calibration primitives and detector constants;
5. timing primitives;
6. energy/range/stopping primitives;
7. PID and anomaly labels;
8. pile-up/rate/deadtime/saturation;
9. ML comparisons and model winners;
10. Geant4/digitizer/SiPM closure and external reference comparisons;
11. all derived/headline results;
12. README/WIKI/dashboard/publication statements.

If an upstream atom is `FLAWED`, all dependent atoms are immediately reopened and cannot remain `VALIDATED` without explicit demonstration of non-dependence.

## Immediate high-risk families

The first hostile pass should prioritize:

- all timing numbers, especially values that differ by orders of magnitude between historical beam-data studies and newer MC closure;
- every p/d PID AUC and every label definition;
- every Rmax/live-time/pile-up number and its precise operational definition;
- stopping-depth and DeltaE-E results affected by trigger selection, geometry/materials or amplitude semantics;
- anomaly rates/species identity and data-vs-truth mapping;
- ADC/MeV, Birks and absolute-energy conversions;
- any result with AUC near 1, extremely small residuals, perfect closure, zero failures, or uncertainty much smaller than obvious detector systematics;
- every result selected after many model/cut/feature trials;
- every MC "PASS" whose model shares calibration/response assumptions with the reconstruction.

## Promotion rule

No scientific headline may be called a detector measurement solely because it is reproduced or closes on simulation. Headline promotion requires:

`exact provenance + independent reproduction + correct quantity definition + appropriate uncertainty + falsification controls + applicable independent physical anchor`.

Until the global census is materially complete, all project-wide summary language should default to the narrowest evidence class supported by the ledger.

## Session handoff protocol

A future AI session should:

1. read this file, `CLAIM_EVIDENCE_MATRIX.md`, `CODE_RESULT_MAP.md`, `BLOCKERS.md`, and canonical publication/dashboard/claim-ledger files;
2. choose one upstream numerical family, not an attractive downstream headline;
3. enumerate every number in that family into the CSV ledger before judging it;
4. reconstruct the producer and dependencies;
5. design hostile counterexamples/null tests before accepting the number;
6. commit audit evidence and update affected claim states;
7. propagate any flaw recursively to all dependent reports/WIKI/claims;
8. leave the next smallest unresolved atom explicit for another session.

The programme is complete only when the numerical census has no unclassified consequential values and every public claim points to audited numerical atoms.
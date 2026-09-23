# Scientific review protocol

Parent: #1594. Reviewer protocol: #1615.

A numerical result is not promoted by reproduction alone. Each consequential claim must receive four independent review verdicts. Reviewers should seek counterexamples and failure modes rather than confirm the nominal story.

## 1. Detector/data reviewer

Must verify raw waveform/channel/event semantics, hardware plausibility, trigger/selection logic, calibration provenance, run/stave stability, saturation and detector-specific failure modes. Veto if the observable is physically ambiguous, selection is unmatched, calibration is not anchored, or hardware interpretation is unsupported.

## 2. Statistics/ML reviewer

Must verify sampling/resampling unit, dependence/covariance, uncertainty coverage, multiple testing/model selection, leakage, target causality, train/validation separation, slice performance and untouched validation. Veto if the same information influences both selection and final performance without an independent final test, or if uncertainty omits material nuisance terms.

## 3. Simulation/physics reviewer

Must verify equations, units, approximation domains, geometry/materials, generator/physics model, digitizer/optical assumptions, nuisance sensitivity, selection matching and independence of validation. Veto if truth/MC closure is transferred to detector performance without independent data/bench evidence, or if the result relies on an ad-hoc physical model without sensitivity study.

## 4. Provenance/reproducibility reviewer

Must verify exact input hashes, code/config commit, environment/command, machine-readable output, figure generator, sufficient statistics and independent reconstruction. Veto if the result cannot be reproduced from immutable inputs or if a public number is hand-entered/unbound.

## Status transitions

`UNREVIEWED -> REVIEW -> {SUPPORTED | CONDITIONAL | BLOCKED | FLAWED | SUPERSEDED}`.

`SUPPORTED` requires all four roles ACCEPT and no unresolved upstream dependency. `CONDITIONAL` requires explicit scope/assumptions and may not be narrated more broadly. `BLOCKED` means missing evidence prevents a verdict. `FLAWED` means a demonstrated defect invalidates the claim as stated. `SUPERSEDED` preserves history but cannot authorize current claims.

## Evidence-class vocabulary

Keep DATA_MEASUREMENT, MC_METHOD_CLOSURE, TRUTH_LEVEL_MC_ONLY, DETECTOR_MODEL_PREDICTION, VALIDATED_TRANSFER, EXTERNAL_REFERENCE, PROJECTION and DIAGNOSTIC distinct. Evidence classes are not interchangeable.

## Checkbox rule

An issue checkbox is checked only when committed evidence exists and the corresponding machine-readable ledger row has been updated. A verbal statement, visually good plot, successful nominal run, or LLM narrative is not sufficient.

## Recursive reopening

When an upstream atom changes, identify all dependent claims/studies/figures through the audit graph and reopen them. Do not preserve a downstream conclusion merely because its numerical value happens to remain close after the change.

# Atomic research protocol for ccb-testbeam

Status: active research protocol. This document is a handoff contract for AI sessions; it is not a physics result.

## Goal

Review the project recursively at the smallest scientifically meaningful unit. A unit may be a byte-level data contract, one waveform transformation, one event-key rule, one estimator, one plot definition, one Geant4 material/property, one public claim, or one literature-dependent assumption. Do not close a parent topic merely because one implementation passes.

## Four role-separated passes

Every atomic task receives four explicit review passes. They are review lenses executed by AI sessions, not independent human collaborators.

1. **Domain/physics lead** — state the physical measurand, detector contract, and minimum model needed to answer the question.
2. **Adversarial reviewer** — construct counterexamples and alternative mechanisms that could reproduce the observed result without the preferred interpretation.
3. **Validation/statistics reviewer** — define independent data splits, weights, uncertainty, negative controls, synthetic corruption tests, and executable fail-closed acceptance criteria.
4. **Claims/provenance reviewer** — map every affected README/WIKI/report/claim-ledger/figure statement to immutable inputs, code commit, configuration, and evidence class.

For each pass record: evidence inspected, strongest counter-hypothesis, falsifier attempted, residual uncertainty, and vote (`ACCEPT`, `REVISE`, `BLOCK`, `REJECT`). `ACCEPT` requires all blocking criteria to pass; prose consensus cannot waive missing data or failed controls.

## Nature-style literature workflow

The requested `nature-skills`, `nature-academic-search`, and `nature-reviewer` packages are not mounted as native tools in every ChatGPT runtime. When absent, follow their public methodology manually:

- search multiple scholarly sources, prioritising primary papers, official detector documentation and collaboration manuals;
- broaden queries and deduplicate results;
- verify DOI/title/authors/year and distinguish peer-reviewed evidence from preprints/vendor measurements;
- use stable concern IDs and separate blocking from non-blocking concerns;
- do not claim reviewer independence or mutual blindness unless the runtime actually isolates contexts;
- citation support is necessary but not sufficient: every external parameter used in MC must be tied to the exact material/device/configuration in this experiment or treated as a nuisance/systematic.

## Atomic evidence states

- `CONFIRMED_BUG`: exact code/data/report evidence demonstrates an error.
- `CONFIRMED_GAP`: required evidence is absent and a claim depends on it.
- `CANDIDATE`: plausible issue requiring exact execution or immutable inputs.
- `NEGATIVE_RESULT`: a hypothesis was tested and failed; preserve it to prevent repetition.
- `VALIDATED_METHOD`: method passed positive and adversarial controls on immutable inputs, but may still be non-authorising for detector performance.
- `VALIDATED_CLAIM`: source-bound claim with correct measurand, uncertainty, provenance, and independent closure.

Never promote `CANDIDATE` to a defect without evidence, and never promote method closure to detector-performance validation.

## Required issue body

Each GitHub issue should contain:

- stable audit ID and severity;
- exact source pointers (commit/path/line or report/page/table);
- physical/software contract that is violated or missing;
- why the issue can bias physics conclusions;
- expert-pass questions and competing hypotheses;
- smallest implementation unit;
- positive control and at least one adversarial negative control;
- deterministic acceptance criteria and non-zero failure status;
- required immutable inputs and SHA-256/provenance fields;
- affected claims/plots/wiki text;
- dependencies and next issue to unlock.

Prefer one issue per independently testable failure. Cross-link to broader supervisor issues rather than duplicating them.

## Data-first release gates

No timing, PID, light-collection, pile-up, or data/MC performance claim may be authorised until all applicable gates pass:

1. exact raw event schema and per-event waveform length;
2. canonical event key and complete key-set closure;
3. exact raw-to-sorted ADC-word closure or a documented irreversible transform with validation;
4. readout-channel-to-physical-stave mapping;
5. measured per-channel polarity;
6. final-channel survival and malformed-record quarantine;
7. immutable run ledger and calibration/analysis split;
8. identical reconstruction definition for data and digitised MC;
9. MC event-weight and effective-sample-size audit;
10. held-out validation plus systematic/nuisance scans.

## Iteration rule

After resolving an issue, recurse into its assumptions. Ask: what data contract did the fix assume; what hidden transformation remains; what uncertainty was introduced; what alternative mechanism is still observationally equivalent; what claim surface is now stale; what new negative control could falsify the result? Create child issues only when they are independently actionable.

The review is complete only when all remaining leaves are either validated, explicitly blocked with an external dependency, or documented negative results with no untested material alternative under the stated scope.
# Scientific Audit Status — CCB Test-Beam

> **GLOBAL REVALIDATION IN PROGRESS.** This document is the safety front door for scientific interpretation while issue #1594 is open.

The repository contains a large historical study fleet. Several apparently strong results were later downgraded after discovering selection mismatch, label leakage/self-reference, ambiguous quantity definitions, incomplete systematic uncertainty, shared-assumption Monte-Carlo closure, stale documentation, or provenance defects. Therefore historical `PASS`, `VALIDATED`, visually attractive figures, and successful reproduction are **not sufficient evidence by themselves**.

## Current rule

A detector-performance or physics claim is authorizing only after all applicable gates below are satisfied:

1. exact input/data provenance and independent reconstruction;
2. physical quantity definition, units, denominator and selection are explicit;
3. every equation/method has derivation or authoritative support and a stated validity domain;
4. uncertainty includes dependence/covariance and relevant systematic nuisances;
5. data/MC comparisons use matched trigger, selection, acceptance and observable semantics;
6. ML/model-selection claims survive leakage, multiplicity and untouched-validation tests;
7. Monte-Carlo truth and method closure are not transferred to beam data without independent evidence;
8. figures are generated from auditable machine-readable inputs and expose uncertainty/context;
9. four-role adversarial review (detector, statistics, simulation/physics, provenance) has no unresolved veto.

## Evidence classes

Use evidence classes literally. In particular:

- `DATA_MEASUREMENT`: measured from beam data, but still conditional on validated data contracts/calibration/systematics.
- `MC_METHOD_CLOSURE`: reconstruction closes on simulation; **not a detector measurement**.
- `TRUTH_LEVEL_MC_ONLY`: truth-level mechanism/species statement; **not transferred to beam data**.
- `DETECTOR_MODEL_PREDICTION`: depends on detector/simulation assumptions and nuisance model.
- `VALIDATED_TRANSFER`: independent evidence supports transfer from model/MC to detector data.
- `GATED` / `BLOCKED` / `FLAWED` / `UNJUSTIFIED` / `SUPERSEDED`: cannot authorize a current physics conclusion.

## Priority audit chain

Scientific work proceeds upstream to downstream:

1. #1603 raw ROOT, waveform semantics, channel mapping, event keys, trigger and selection anchors;
2. #1604 detector/electronics/SiPM/WLS calibration and nuisance covariance;
3. #1608 simulation geometry/generator/digitizer physics and data/MC transfer;
4. #1609 statistical inference, ML leakage, multiplicity and untouched validation;
5. #1605 timing rebuild;
6. #1606 energy/stopping/ΔE–E/PID/anomaly rebuild;
7. #1607 pile-up/rate/saturation rebuild;
8. #1614 dependency-aware study supersession/rerun map;
9. #1597/#1601/#1613 figure regeneration;
10. #1598/#1611 WIKI/README/dashboard/publication reconciliation and hard evidence gate.

If an upstream primitive changes, every dependent study/figure/public statement reopens automatically.

## Known front-door contradictions under repair

- The WIKI contains stale statements that raw beam ROOT is not staged, while a later section records located/staged real-beam ROOT and a data-side analysis. Until #1598 reconciles the exact archive/lineage state, prose about data availability is non-authorizing.
- The WIKI currently states that every claim is traceable to source. The exhaustive census (#1610) is still testing that assertion; therefore it must not be treated as established fact.
- Historical timing, Rmax, gain, PID and anomaly headlines include superseded or restricted evidence classes. Current interpretation must follow the canonical audited ledger, not historical prose.

## Audit artifacts

- `chatgpt_todo/NUMBER_AUDIT_LEDGER.csv`
- `chatgpt_todo/PHYSICS_JUSTIFICATION_LEDGER.csv`
- `chatgpt_todo/FIGURE_AUDIT_LEDGER.csv`
- `chatgpt_todo/REDO_QUEUE.csv`
- `chatgpt_todo/SCIENTIFIC_REVIEW_PROTOCOL.md`
- `chatgpt_todo/AI_SESSION_PICKUP_GUIDE_20260817_GLOBAL_AUDIT.md`

No checkbox for a scientific result should be closed without committed evidence.
# Master Audit Index

This is the cumulative repository-coverage ledger. It is intentionally incomplete at initialization and must be expanded from repository evidence rather than guesses.

| ID | Type | Path or claim | Status | Dependencies | Current evidence / next action |
|---|---|---|---|---|---|
| AREA-G4-SINGLE-STAVE | Code/simulation | `geant4/single_stave/` | ACTIVE | Geant4 11.2.2, optical tables, configs | RNG audit in `AUD-G4-001`; inventory remaining modules and outputs. |
| CLAIM-G4-PE178 | Scientific claim | Optical collection ≈178 PE/event | PARTIAL | single-stave geometry, optical tables, seed handling, run config | Recent commit claims verification; reproduce after RNG fix and record uncertainty/configuration. |
| RESULT-G4-MERGED-NTUPLE | Output contract | One merged ROOT output in MT | PARTIAL | `SetNtupleMerging(true)`, thread model | Code path inspected; runtime row-count and event-ID validation required. |
| PROGRAM-STUDIES | Study programme | `studies/STUDIES.md` (~230 studies) | NOT_STARTED | reports, scripts, figures, data | Build one indexed row per study with claim/code/data/plot links. |
| DOC-WIKI | Documentation | `WIKI.md` and GitHub wiki | NOT_STARTED | study evidence and generated results | Audit headline values and trace each to reproducible outputs. |
| CLAIM-HEADLINE-TIMING | Scientific claim | B6 σ68 ≈0.68–0.75 ns | NOT_STARTED | pulse table, timing studies, MC validation | Reproduce selection, estimator, uncertainty, and MC closure. |
| CLAIM-HEADLINE-PILEUP | Scientific claim | Rmax ≈3.05 MHz | NOT_STARTED | pile-up model, correction, MC | Audit corrected value and assumptions. |
| CLAIM-HEADLINE-PID | Scientific claim | proton/deuteron AUC=0.986 | NOT_STARTED | labels, train/test split, MC | Check leakage, class balance, calibration, uncertainty, external validation. |

## Coverage rule

An item is COMPLETE only when its source data, code/configuration, result artifact, statistical/scientific validation, visualization, limitations, and downstream documentation are all linked and reproducible.

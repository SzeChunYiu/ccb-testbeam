# Issue reporting reconciliation and new MV3 profile verification

**Date:** 2026-10-19. **Scientific release: NOT_AUTHORIZED.** Master #1628 / #1594; review PR #1629. Main source inspected: `a61427813344e29047ca9eb9b764182eb29e4c83`; review branch head at intake: `1d5445fae12559d52143320b6fcb080ac87d6e95`. This packet does not change production code, close scientific issues or merge a PR.

## Reporting gap repaired

Several previous rounds committed evidence but could not post issue comments. This round successfully created seven OPEN issues:

| Issue | Explicitly reported work |
|---|---|
| #1630 | ROOT-truth units, jagged alignment, event/track identity and missing observations. |
| #1631 | Canonical CFD/leading-edge invalid waveform, lossy conversion and numerical-domain repair; the prior local patch is still not integrated. |
| #1632 | PID ROC/AP correctness, complete bootstrap populations, genuine folds, truth features and invalid JSON. |
| #1633 | Canonical track-builder event-weight authorization and spatial-order endpoint inference. |
| #1634 | **New this round:** MV3 occupancy-versus-deepest-hit mismatch, sample pooling, invalid input and actual JSON-writer failure. |
| #1635 | Stopped-beam/zero-energy scattering and unsupported negative stopping extrapolation. |
| #1636 | A09 raw/visible/response definitions, finite samples, split/metadata identity, uncertainty, null controls and refit-versus-transfer narrative. |

Existing owner issues #1045, #1598, #1603, #1607, #1608, #1611 and #1616 received explicit finding updates. The original A09 rendering issue #1592 is retained, not duplicated. Direct issue/comment bindings are in `FINDING_ISSUE_INDEX.csv`.

**Coverage:** 55 explicitly enumerated reporting entries map to 15 issue owners, with no unbound rows in this declared index. These are **not 55 independent bugs**: the index includes shared mechanisms, source qualifications, positive numerical controls and untested static concerns. It is also **not a complete repository inventory**. The broader pre-existing raw/hardware/physics/statistics/publication requirements remain under #1594/#1628 and their domain issues, including #1617 external inputs.

The committed45-probe report and later61-case download reuse V-numbers with different meanings. The index uses `probe45:` and `case61:` prefixes and retains aliases for shared mechanisms. In particular, probe45:V04 is pulse masking, whereas case61:V04 is static response retention. Repeated test modes, cases, CDF points or old CI counts are not independent experimental validation.

Issue creation and comments were confirmed by the GitHub write responses. The offline index validator checks structure and links only; it cannot authenticate remote state or prove scientific validity. Issue bodies preserve source commits, reproducible witnesses, acceptance tasks and what remains unmeasured.

## New finding MP-01: unlike observables are scored as a mapping discrepancy

`configs/mc_validation/mv3.yaml` supplies **selected B-pulse stave occupancy fractions**. `run_mv3` computes per-layer occupancy panels but compares the data profile with `truth_stave_counts` derived from **deepest observed layer**.

One track may occupy four staves while contributing only one deepest-layer count. Normalizing cannot make those quantities equivalent. For a synthetic Sample-I track with mask `[1,0,1,0,1,0,0,1]`, deepest layer7, and matched hit profile `[.25,.25,.25,.25]`, the existing score is **1.5**; the matched hit-presence comparison gives **0**. This is a wrong-comparison counterexample, not a measured detector disagreement.

The independent reference explicitly estimates unweighted track-stave hit presence. It combines a stave's constituent layers by per-track OR, not by counting one track twice. This is only a declared synthetic estimand: equivalence to recorded data-pulse/event populations, thresholds, trigger response and MC weights must be independently established before data/MC comparison.

## New finding MP-02: an I-only score changes when only other samples change

The source builds one `stave_truth` from all stop-layer rows and scores it against both named data references. Keeping the Sample-I observation fixed but adding one Sample-II/B8 observation changes the I-reference score from0 to1 while its own I-occupancy panel is unchanged. An explicitly NONE-labeled added row also changes it. The reference I-only profile remains unchanged.

The initial local probe stored labels in a fixed-width NumPy string array, so an intended NONE label was truncated to NO. Both are excluded from I and produced the same score, but the final probe now preserves object-string labels and verifies exact NONE. `PRELIMINARY_PROBE_IDENTITY.json` records that harness correction rather than silently treating the initial label as exact. This was a test-harness adjustment; the pinned source modules were not changed.

## New finding MP-03: invalid or unobserved states become numerical occupancy

The actual module accepts a NaN/-1 mask as occupied=True; NaN per-layer deposited energy becomes False through `>0`. A2-column mask silently reduces the declared8-layer problem to2 columns with PRODUCTION lifecycle status. A missing Sample-II population is assigned eight zeros using `max(N,1)`, rather than an explicitly unestimable/null occupancy. Its cutflow does retain N=0; that does not make the zero-valued metric a measurement.

Validate exact schema, finite binary masks/nonnegative finite deposited energies, supported dimensions, matched populations and normalization mass. Missing observations must not be confused with observed zero response. The independent reference rejects the tested invalid inputs and records null for an empty group or zero normalization mass; it is not yet a production repair.

## New finding MP-04: actual persistence accepts a NaN production score

A NaN reference profile produces a NaN mapping score with PRODUCTION lifecycle. The actual `common.write_study_result` accepts it and writes literal unquoted JSON NaN. Existing error/skip-marker checks do not cover this path. A strict finite/schema/serialization gate is required before output publication.

**Boundary:** a study's PRODUCTION lifecycle is not a scientific publication authorization. This test does not establish that the whole publication workflow ran or approved that malformed result.

## Executed verification, with exact imported source

Two complete repository modules were copied, verified by Git blob hash and imported with explicit origin checks:

| Source | Git blob |
|---|---|
| `src/ccb_mc_validation/studies/mv3_stopping_depth.py` | `9b0dfeaa6e74401345bc78c7ab82b33d7868b665` |
| `src/ccb_mc_validation/studies/common.py` | `a6a3da4aa58c8346758c26ac64d23c4f827c90aa` |

Two empty package `__init__.py` files isolate imports from any installed same-name package; they are import scaffolding. **No functions, classes or dependency behavior were stubbed.** Execution used synthetic in-memory records and the actual writer in a temporary directory. This is not the full repository/package initializer, command-line pipeline, original ROOT or Geant4 runtime.

**18 test methods passed** normally and under Python optimization. The default observation runner returns exit1 intentionally, with four retained source-failure classes. Normal and optimized observation JSONs are byte-identical. Repeated modes and the24 permutation subcases are not additional independent experiments. Logs, environment and commands are recorded in `mv3_profile_probe/EXECUTION_RECEIPT.json`.

Positive controls are retained: absent per-layer masks and all-NONE sample labels correctly BLOCK the study. In particular, current `root_truth`-shaped records lacking the mask cannot directly generate MV3 profile results. Do not conclude that the earlier converter kinetic-energy bug automatically contaminated an executed MV3 result merely because both modules appear in a workflow.

The scientific reasoning was checked from detector/measurand, transport hit-versus-endpoint, statistics/population, and source/persistence perspectives within **one assistant**. This is not independent human or experimental sign-off.

## Reproduce

```bash
cd chatgpt_todo/issue_reconciliation_20261019
python validate_reporting_index.py
# Exit0: declared reporting index structurally bound, never publication authority.

cd mv3_profile_probe
python verify_mv3_profiles.py --test
python -O verify_mv3_profiles.py --test
python verify_mv3_profiles.py > fresh_result.json
# Expected exit1: SOURCE_DEFECTS_REPRODUCED, NOT_AUTHORIZED.
python -O verify_mv3_profiles.py > fresh_optimized.json
cmp fresh_result.json fresh_optimized.json
```

`RESULT.json` contains no nonfinite JSON values; it records booleans documenting that the *tested original writer* emitted NaN. A source hash mismatch fails before source execution. The normal/optimized equality is repeatability, not an independent implementation of the entire study.

## Next atomic tasks and issue-reporting discipline

Under #1634, define compatible sample/track/event/stave observables and selected populations first, then owner-integrate corrected scoring, strict mask/reference schemas and result persistence. Preserve working missing-mask/label gates. Add complete-pipeline and real-ROOT tests only after source units, trigger, geometry, generator measure and raw archive identities are bound. Quantify downstream impact rather than tuning to historical scores; regenerate numerical tables, uncertainty, plots, wiki and manuscript or provide reviewed exact-input non-impact evidence.

Every subsequent discovery must receive a live issue or an explicit update in its existing owner issue, with reproducible source/command/evidence, uncertainty and acceptance requirements. Add its namespaced aliases to this reporting index after successful posting. On a blocked write, mark NOT_POSTED and preserve a prepared issue payload; do not claim a commit alone is an issue report. Update #1628 and the recurring handoff with only genuine new evidence, not repeated test counts.

No issue is closed by this packet. Full inventory coverage, installed hardware/DAQ/trigger calibration, original cross-section TableVI, physical nuisance covariance, real ROOT/Geant4, untouched final data and independent reviewers remain pending where required.

## Primary reference and precise limitation

Geant4's official [Hits developer documentation](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/hit.html) describes user-defined hit data associated with steps or accumulated detector information. It supports the need for an explicit native hit/observation contract; it does not certify this repository's writer, real geometry, electronics or data/MC equivalence. The new occupancy-versus-endpoint and sample-pooling counterexamples follow directly from the inspected source and synthetic record definitions.

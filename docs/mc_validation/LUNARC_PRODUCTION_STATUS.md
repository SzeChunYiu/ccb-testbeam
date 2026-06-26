# LUNARC MC Validation Production Status

Generated: 2026-06-25 06:48 UTC

## Current selected LUNARC run

- Run ID: `20260625T064500Z_full_input_artifacted`
- LUNARC job ID: `3316536`
- Terminal state: `COMPLETED`
- Exit code: `0:0`
- Node: `cn046`
- Elapsed: `00:01:01`
- Worktree: `/projects/hep/fs10/shared/nnbar/billy/worktrees/ccb-testbeam-origin-main`
- Code SHA at job completion: `7bd0a16` after PR #477.

## Inputs verified by LUNARC preflight

- MC ROOT: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root`
  - size: `677221620` bytes
  - sha256: `2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc`
- Pulse table: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz`
  - size: `9246625` bytes
  - sha256: `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f`

## Completed stages in job 3316536

The SLURM log reports these stages completed with `rc=0`:

1. `preflight`
2. `plan`
3. `truth-build`
4. `MV0 digitizer`
5. `MV1 PID`
6. `MV2 energy`
7. `MV3 stopping`
8. `MV9 synthesis`

Study outputs were written under the LUNARC worktree:

- `reports/mc_validation/mv1_pid/study_result.json`
- `reports/mc_validation/mv2_energy/study_result.json`
- `reports/mc_validation/mv3_stopping_depth/study_result.json`
- `reports/mc_validation/mv9_synthesis/MV9_SYNTHESIS.md`

## Current study summaries

These are full-input production-run summaries from `CCB_MAX_ROOT_EVENTS=0`, not final thesis conclusions.

- MV1: `PRODUCTION`, `n_tracks=1000000`, `n_proton=100549`, `n_deuteron=141047`, `hgb_auc=0.997641986277693`, `hgb_purity_at_90eff=0.9953867753902006`, `logreg_auc=0.9764543474193328`.
- MV2: `PRODUCTION`, `n_proton_uncensored=69455`, `n_deuteron_uncensored=139074`, `proton_ekin_recon_res68=0.036531109473233174`, `deuteron_ekin_recon_res68=0.13319490593145097` in the current aggregate record representation.
- MV3: `PRODUCTION`, `n_sample_I=64762`, `n_sample_II=172336`; layer occupancy profiles were generated from trigger-derived `sample_label` rather than event-parity labels.
- MV4-MV8: `BLOCKED`, requiring calibrated MV0 digitized MC and truth-labelled waveform products.

## Failed attempts and fixes merged

- Job `3315947`: failed closed because the SLURM wrapper did not expose the source package on `PYTHONPATH`. Fixed by PR #471.
- Job `3316098`: failed closed because the wrapper defaulted to `base.yaml`, ignoring environment-expanded input paths. Fixed by PR #472.
- Job `3316255`: failed closed because MV1-MV3 production ROOT loading was intentionally blocked. Fixed by PR #473.
- After job `3316449`, MV9 initially summarized stale fixture registry values. Fixed by PR #474 and rerun on LUNARC. Full-input job `3316531` used the corrected MV9 path.


## Artifact validation

Validation was run on LUNARC after PR #479 with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted validate --scope artifact --strict
```

Result: `PASS`. The generated files are:

- `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted/VALIDATION.json`
- `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted/VALIDATION_SUMMARY.md`

Checks passing in that summary: `job_state_completed`, `preflight_mc_root`, `preflight_data_pulses`, `MV1_study_result`, `MV2_study_result`, `MV3_study_result`, `MV9_synthesis`, and `slurm_logs_present`. This validates artifact consistency for MV1-MV3/MV9 only; it does not complete figures, notebooks, thesis, uncertainty/systematic arrays, or final release audit.


## Summary report and figures

After PR #481/#482, the compact run-summary generator was run on the selected LUNARC artifacted run. After PR #483, the same selected run was regenerated from the synced `origin/main` worktree to add the browser-readable HTML summary. Current regenerated artifacts are:

- `reports/mc_validation/summary/RUN_SUMMARY.md` (`526` bytes, refreshed 2026-06-25 17:27:54 +0200)
- `reports/mc_validation/summary/RUN_SUMMARY.html` (`1047` bytes, refreshed 2026-06-25 17:27:54 +0200)
- `reports/mc_validation/summary/metrics_table.csv` (`282` bytes, refreshed 2026-06-25 17:27:54 +0200)
- `figures/summary/study_support.svg` (`22092` bytes, refreshed 2026-06-25 17:27:57 +0200)
- `figures/summary/study_support.png` (`50970` bytes, refreshed 2026-06-25 17:27:57 +0200)
- `figures/summary/selected_metrics.svg` (`30534` bytes, refreshed 2026-06-25 17:27:57 +0200)
- `figures/summary/selected_metrics.png` (`106309` bytes, refreshed 2026-06-25 17:27:57 +0200)

All paths above are under `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted/`. Compact figures summarize study support and selected metrics only; they are not the final publication-quality figure suite required for thesis/release.

## Artifact-only notebook export

After PR #485, the selected run was regenerated on the synced LUNARC `origin/main` worktree with the lightweight artifact-only notebook phase:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted notebooks
```

Generated notebook artifacts are:

- `notebooks/source/00_release_overview.py` (`2117` bytes, refreshed 2026-06-25 17:38:09 +0200)
- `notebooks/html/00_release_overview.html` (`1927` bytes, refreshed 2026-06-25 17:38:09 +0200)
- `notebooks/NOTEBOOKS_MANIFEST.json` (`1333` bytes, refreshed 2026-06-25 17:38:09 +0200)

The manifest status is `PASS` for scope `artifact-summary`, with `full_notebook_suite_status` still `BLOCKED` and execution status `NOT_EXECUTED_ARTIFACT_HTML_ONLY`. This is a reader-facing summary export from frozen artifacts only; it is not the required full clean-kernel notebook suite, and it does not remove the MV4-MV8/systematics/thesis/release blockers.

## Artifact-backed reports

After PR #487, the selected run was regenerated on the synced LUNARC `origin/main` worktree with the frozen-artifact report phase:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted docs
```

Generated report artifacts are:

- `reports/mc_validation/artifact_reports/GLOBAL_REPORT.md` (`1152` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/GLOBAL_REPORT.html` (`1672` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/MV1_REPORT.md` (`1260` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/MV1_REPORT.html` (`1899` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/MV2_REPORT.md` (`3796` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/MV2_REPORT.html` (`5095` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/MV3_REPORT.md` (`1232` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/MV3_REPORT.html` (`1881` bytes, refreshed 2026-06-25 17:44:16 +0200)
- `reports/mc_validation/artifact_reports/REPORTS_MANIFEST.json` (`2067` bytes, refreshed 2026-06-25 17:44:16 +0200)

The reports manifest status is `PASS` for scope `artifact-summary`, with `full_report_suite_status` still `BLOCKED` and blocked studies `MV4,MV5,MV6,MV7,MV8`. These reports summarize frozen MV1-MV3/MV9 artifacts only; they do not constitute the final thesis/report/release package.

## Release QA audit

After PR #489 and the README fixture-status cleanup in PR #490, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

Updated QA artifacts are:

- `VALIDATION.json` (`8385` bytes, refreshed 2026-06-25 17:51:58 +0200)
- `VALIDATION_SUMMARY.md` (`945` bytes, refreshed 2026-06-25 17:51:58 +0200)
- `QA_RELEASE_AUDIT.json` (`3842` bytes, refreshed 2026-06-25 17:51:58 +0200)
- `QA_RELEASE_AUDIT.md` (`1662` bytes, refreshed 2026-06-25 17:51:58 +0200)

The broad validation status is now `PASS`, including `fixture_not_released` with no README matches. The release QA audit remains `BLOCKED` and `release_ready=false` because MV4-MV8 production artifacts, systematic arrays, the full figure catalog, clean-kernel LUNARC notebook execution, thesis/static site build, and final release bundle are still incomplete.

## Thesis draft scaffold

After PR #492, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted thesis
```

Generated draft artifacts are:

- `reports/mc_validation/thesis_draft/THESIS_DRAFT.md` (`2277` bytes, refreshed 2026-06-25 17:57:23 +0200)
- `reports/mc_validation/thesis_draft/THESIS_DRAFT.html` (`2982` bytes, refreshed 2026-06-25 17:57:23 +0200)
- `reports/mc_validation/thesis_draft/THESIS_DRAFT_MANIFEST.json` (`686` bytes, refreshed 2026-06-25 17:57:23 +0200)

The thesis draft manifest status is `PASS` for scope `artifact-thesis-draft`, with `final_thesis_status=BLOCKED` and `blocked_count=10`. This is a scaffold assembled from frozen artifacts and release-audit gaps; it is not a final thesis PDF/static-site release.

## Publication index draft

After PR #494, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
```

Generated publication draft artifacts are:

- `publication/index.html` (`3281` bytes, refreshed 2026-06-25 18:33:50 +0200)
- `publication/INDEX.md` (`2255` bytes, refreshed 2026-06-25 18:33:50 +0200)
- `publication/PUBLICATION_MANIFEST.json` (`2403` bytes, refreshed 2026-06-25 18:33:50 +0200)
- `release_BLOCKED.json` (`2593` bytes, refreshed 2026-06-25 18:33:50 +0200)

The publication manifest status is `BLOCKED` for scope `publication-index-draft`, with `release_ready=false`, `blocked_count=10`, and no missing linked draft artifacts. It links `figures/summary/FIGURE_CONTACT_SHEET.html` (`1192` bytes), `reports/mc_validation/claims/CLAIM_LEDGER.md` (`2138` bytes), and, after PR #506, `figures/summary/visual_review.html` (`985` bytes). This index is a navigation page over frozen artifacts, not a final signed release.

## Summary figure manifest/contact sheet

After PR #496, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted plot
```

Generated figure metadata artifacts are:

- `figures/summary/FIGURE_MANIFEST.json` (`1711` bytes, refreshed 2026-06-25 18:08:58 +0200)
- `figures/summary/FIGURE_CONTACT_SHEET.md` (`645` bytes, refreshed 2026-06-25 18:08:58 +0200)
- `figures/summary/FIGURE_CONTACT_SHEET.html` (`1192` bytes, refreshed 2026-06-25 18:08:58 +0200)

The figure manifest status is `PASS` for scope `summary-figure-manifest`, with two compact summary figures (`SUMMARY-F001`, `SUMMARY-F002`) and `full_figure_catalog_status=BLOCKED`. The full thesis/release figure catalog remains incomplete.

## Claim ledger / staleness guard

After PR #500, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

Generated claim-ledger artifacts are:

- `reports/mc_validation/claims/CLAIM_LEDGER.json` (`3547` bytes, refreshed 2026-06-25 18:19:15 +0200)
- `reports/mc_validation/claims/CLAIM_LEDGER.md` (`2138` bytes, refreshed 2026-06-25 18:19:15 +0200)
- `QA_RELEASE_AUDIT.json` (`3842` bytes, refreshed 2026-06-25 18:19:15 +0200)

The claim ledger status is `PASS` for scope `claim-ledger`. It supports the frozen MV1-MV3/MV9 artifact-summary claims but sets `release_claims_allowed=false` with `blocked_claim_count=6`, covering MV4-MV8 release claims and the final-release claim.

## Summary figure visual review

After PR #504, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted plot
```

Generated visual-review artifacts are:

- `figures/summary/visual_review.json` (`1414` bytes, refreshed 2026-06-25 18:29:32 +0200)
- `figures/summary/visual_review.md` (`550` bytes, refreshed 2026-06-25 18:29:32 +0200)
- `figures/summary/visual_review.html` (`985` bytes, refreshed 2026-06-25 18:29:32 +0200)

The visual-review status is `PASS` for scope `summary-figure-visual-review`, with `review_count=2` and `full_visual_review_status=BLOCKED`. This is scoped to compact summary figures only; the full thesis/release visual review remains incomplete.

## Refreshed release QA artifact gates

After PR #508, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

Updated QA artifacts are:

- `QA_RELEASE_AUDIT.json` (`4773` bytes, refreshed 2026-06-25 22:42:51 +0200)
- `QA_RELEASE_AUDIT.md` (`1763` bytes, refreshed 2026-06-25 22:42:51 +0200)
- `reports/mc_validation/claims/CLAIM_LEDGER.json` (`3547` bytes, refreshed 2026-06-25 22:42:51 +0200)
- `reports/mc_validation/claims/CLAIM_LEDGER.md` (`2138` bytes, refreshed 2026-06-25 22:42:51 +0200)

The release audit remains `BLOCKED` with `release_ready=false`, but the newly explicit generated-artifact gates pass: `summary_figure_manifest` (`1711` bytes), `summary_visual_review` (`1414` bytes), and `claim_ledger` (`3547` bytes). The remaining blockers are still the missing MV4-MV8 production artifacts, systematic arrays, full figure catalog, clean-kernel full-data notebooks, final thesis/PDF/static site, and final release bundle.

## GitHub wiki draft export

After PR #510, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
```

Generated GitHub-wiki-ready draft artifacts are:

- `wiki/Home.md` (`1127` bytes, refreshed 2026-06-25 22:50:46 +0200)
- `wiki/Scientific-Introduction.md` (`453` bytes, refreshed 2026-06-25 22:50:46 +0200)
- `wiki/Methods-and-Mathematics.md` (`1283` bytes, refreshed 2026-06-25 22:50:46 +0200)
- `wiki/Results-and-Figures.md` (`1309` bytes, refreshed 2026-06-25 22:50:46 +0200)
- `wiki/Discussion-and-Limitations.md` (`1741` bytes, refreshed 2026-06-25 22:50:46 +0200)
- `wiki/References-and-Reproducibility.md` (`730` bytes, refreshed 2026-06-25 22:50:46 +0200)
- `wiki/WIKI_MANIFEST.json` (`644` bytes, refreshed 2026-06-25 22:50:46 +0200)

The wiki manifest status is `PASS` for scope `github-wiki-draft`, with `final_wiki_status=BLOCKED`, `page_count=6`, and `release_ready=false`. These pages include introduction, methods/math formulas, results/figures, discussion/blockers, and reproducibility sections, but final GitHub wiki publication remains blocked until the full release audit passes and citations/references are curated.

## Reference registry and wiki citation refresh

After PR #512 and the release-ordering fix in PR #513, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
```

Generated/refreshed reference and wiki artifacts are:

- `reports/mc_validation/references/REFERENCE_REGISTRY.json` (`1383` bytes, refreshed 2026-06-25 23:02:55 +0200)
- `reports/mc_validation/references/REFERENCE_REGISTRY.md` (`910` bytes, refreshed 2026-06-25 23:02:55 +0200)
- `wiki/References-and-Reproducibility.md` (`1358` bytes, refreshed 2026-06-25 23:02:55 +0200)
- `wiki/WIKI_MANIFEST.json` (`644` bytes, refreshed 2026-06-25 23:02:55 +0200)
- `publication/PUBLICATION_MANIFEST.json` (`2565` bytes, refreshed 2026-06-25 23:02:55 +0200)
- `release_BLOCKED.json` (`3494` bytes, refreshed 2026-06-25 23:02:55 +0200)

The reference registry status is `PASS` for scope `reference-registry`, with `final_bibliography_status=BLOCKED` and one blocked literature-curation placeholder. The publication manifest now has `reference_registry.exists=true` for `reports/mc_validation/references/REFERENCE_REGISTRY.md` (`910` bytes). Final curated citations/references remain a release/wiki blocker.

## Notation and equation registry

After PR #515, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
```

Generated/refreshed notation and wiki artifacts are:

- `reports/mc_validation/notation/NOTATION_REGISTRY.json` (`1599` bytes, refreshed 2026-06-25 23:09:39 +0200)
- `reports/mc_validation/notation/NOTATION_REGISTRY.md` (`1137` bytes, refreshed 2026-06-25 23:09:39 +0200)
- `wiki/Notation-and-Equations.md` (`1044` bytes, refreshed 2026-06-25 23:09:39 +0200)
- `wiki/WIKI_MANIFEST.json` (`677` bytes, refreshed 2026-06-25 23:09:39 +0200)
- `publication/PUBLICATION_MANIFEST.json` (`2724` bytes, refreshed 2026-06-25 23:09:39 +0200)
- `release_BLOCKED.json` (`3700` bytes, refreshed 2026-06-25 23:09:39 +0200)

The notation registry status is `PASS` for scope `notation-registry`, with `final_notation_status=DRAFT` and `record_count=5`. The wiki draft now has `page_count=7` and the publication manifest has `notation_registry.exists=true` for `reports/mc_validation/notation/NOTATION_REGISTRY.md`. Final thesis derivations and systematic uncertainty notation remain part of the release blockers.

## Recursive open-question registry

After PR #517, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
```

Generated/refreshed open-question and wiki artifacts are:

- `reports/mc_validation/open_questions/OPEN_QUESTIONS.json` (`2159` bytes, refreshed 2026-06-25 23:14:56 +0200)
- `reports/mc_validation/open_questions/OPEN_QUESTIONS.md` (`1425` bytes, refreshed 2026-06-25 23:14:56 +0200)
- `wiki/Open-Questions.md` (`1542` bytes, refreshed 2026-06-25 23:14:56 +0200)
- `wiki/WIKI_MANIFEST.json` (`702` bytes, refreshed 2026-06-25 23:14:56 +0200)
- `publication/PUBLICATION_MANIFEST.json` (`2883` bytes, refreshed 2026-06-25 23:14:56 +0200)
- `release_BLOCKED.json` (`3898` bytes, refreshed 2026-06-25 23:14:56 +0200)

The open-question registry status is `PASS` for scope `open-question-registry`, with `all_questions_closed=false` and `open_count=7`. It tracks the recursive evidence still needed for MV4-MV8, systematic arrays, and final wiki/publication readiness. The wiki draft now has `page_count=8`, and the publication manifest has `open_questions.exists=true` for `reports/mc_validation/open_questions/OPEN_QUESTIONS.md`.

## Recursive open-question closure plan

After PR #519, the selected run was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
```

Generated/refreshed closure-plan artifacts are:

- `reports/mc_validation/open_questions/OPEN_QUESTION_CLOSURE_PLAN.json` (`4932` bytes, refreshed 2026-06-25 23:22:13 +0200)
- `reports/mc_validation/open_questions/OPEN_QUESTION_CLOSURE_PLAN.md` (`3356` bytes, refreshed 2026-06-25 23:22:13 +0200)
- `wiki/Open-Questions.md` (`2854` bytes, refreshed 2026-06-25 23:22:13 +0200)
- `publication/PUBLICATION_MANIFEST.json` (`3066` bytes, refreshed 2026-06-25 23:22:13 +0200)
- `release_BLOCKED.json` (`4091` bytes, refreshed 2026-06-25 23:22:13 +0200)

The closure-plan status is `PASS` for scope `open-question-closure-plan`, with `all_steps_closed=false` and `step_count=7`. It adds an evidence dependency DAG and terminal condition for each open question; the publication manifest has `open_question_closure_plan.exists=true` for `reports/mc_validation/open_questions/OPEN_QUESTION_CLOSURE_PLAN.md`.

## Guardrails and remaining blockers

- This run is not a final release: strict validation, full uncertainty treatment, figures, notebooks, thesis rendering, and final audit have not passed.
- Full-input campaign `3316536` completed and persisted logs, JOB_STATE.json, MV1/MV2/MV3 results, and MV9 synthesis into `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted`. Remaining release work is validation/uncertainty/figures/notebooks/thesis/final audit, not another MV1-MV3 ROOT pass.
- MV4-MV8 remain blocked until calibrated digitized MC is available.
- No fixture/smoke value should be promoted as a physics conclusion.

## Resume / next commands

From `billy-old`, after verifying the LUNARC socket:

```bash
ssh -O check lunarc 2>/dev/null && echo Connected || /home/billy/lunarc-init.sh
ssh lunarc
cd /projects/hep/fs10/shared/nnbar/billy/worktrees/ccb-testbeam-origin-main
git fetch origin && git reset --hard origin/main
export CCB_MC_REPO="$PWD"
export CCB_MC_PYTHON=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export CCB_MC_ROOT=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root
export CCB_PULSE_TABLE=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
export CCB_ARTIFACT_ROOT=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts
export CCB_MAX_ROOT_EVENTS=0
sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch
```

## Release-audit open-question gates

After PR #521, selected run QA was regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

Generated/refreshed QA audit artifacts are:

- `QA_RELEASE_AUDIT.json` (`6300` bytes, refreshed 2026-06-25 23:30:26 +0200)
- `QA_RELEASE_AUDIT.md` (`2018` bytes, refreshed 2026-06-25 23:30:26 +0200)

The release audit now checks the recursive open-question artifacts directly:

- `open_question_registry`: `PASS`, observed `PASS`, `2159` bytes
- `open_question_closure_plan`: `PASS`, observed `PASS`, `4932` bytes
- `all_questions_closed`: `BLOCKED`, observed `false`, reason `expected all_questions_closed=True, observed False`
- `all_question_steps_closed`: `BLOCKED`, observed `false`, reason `expected all_steps_closed=True, observed False`

Overall release audit remains `BLOCKED` with `release_ready=false` and `25` checks. This is expected: the registry and closure-plan files exist and validate, but the recursive evidence-reduction condition is intentionally fail-closed until all open questions and closure-plan steps are actually resolved with production evidence. MV4-MV8 production artifacts, thesis/static-site output, and release bundle gates also remain blocked.

## Open-question evidence packets

After PRs #523-#525, selected run release and QA artifacts were regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

Generated/refreshed evidence-packet artifacts are:

- `reports/mc_validation/open_questions/EVIDENCE_PACKETS.json` (`11579` bytes, refreshed 2026-06-25 23:48:07 +0200)
- `reports/mc_validation/open_questions/EVIDENCE_PACKETS.md` (`2676` bytes, refreshed 2026-06-25 23:48:07 +0200)
- `wiki/Open-Questions.md` (`4422` bytes, refreshed 2026-06-25 23:48:07 +0200; contains `## Evidence packet templates` at line 46)
- `wiki/WIKI_MANIFEST.json` (`702` bytes, refreshed 2026-06-25 23:48:07 +0200)
- `publication/PUBLICATION_MANIFEST.json` (`3243` bytes, refreshed 2026-06-25 23:48:07 +0200)
- `QA_RELEASE_AUDIT.json` (`7068` bytes, refreshed 2026-06-25 23:48:08 +0200)
- `QA_RELEASE_AUDIT.md` (`2156` bytes, refreshed 2026-06-25 23:48:08 +0200)

Evidence-packet status is `PASS` for artifact generation with `packet_count=7`, `open_packet_count=7`, and `all_packets_closed=false`. The publication manifest now has `open_question_evidence_packets.exists=true` for `reports/mc_validation/open_questions/EVIDENCE_PACKETS.md`; the wiki manifest remains `PASS` with `page_count=8`.

Release audit remains intentionally fail-closed: `open_question_evidence_packets` is `PASS`, but `all_evidence_packets_closed` is `BLOCKED` with observed `false` and reason `expected all_packets_closed=True, observed False`. Overall audit remains `BLOCKED`, `release_ready=false`, with `27` checks.

## Corrected evidence-packet SLURM hints

After PR #527, selected run release and QA artifacts were regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

Refreshed packet artifacts are:

- `reports/mc_validation/open_questions/EVIDENCE_PACKETS.json` (`12852` bytes, refreshed 2026-06-25 23:53:37 +0200)
- `reports/mc_validation/open_questions/EVIDENCE_PACKETS.md` (`3747` bytes, refreshed 2026-06-25 23:53:37 +0200)
- `wiki/Open-Questions.md` (`4422` bytes, refreshed 2026-06-25 23:53:37 +0200)
- `QA_RELEASE_AUDIT.json` (`7068` bytes, refreshed 2026-06-25 23:53:38 +0200)

The evidence packet command hints now match the actual SLURM wrapper interface: first packet check `hint_ok=True`, `has_unsupported_studies=False`, and `blocker_has_mv4=True`. MV4-MV8 packets therefore remain open because implementations/artifacts are missing, not because a per-study `sbatch --studies ...` command was submitted. Release audit remains `BLOCKED`, `release_ready=false`, with `27` checks.

## Study implementation gap audit

After PR #529, selected run release and QA artifacts were regenerated on synced LUNARC `origin/main` with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted release
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted qa
```

Generated/refreshed study-gap artifacts are:

- `reports/mc_validation/open_questions/STUDY_IMPLEMENTATION_GAP_AUDIT.json` (`1855` bytes, refreshed 2026-06-25 23:59:36 +0200)
- `reports/mc_validation/open_questions/STUDY_IMPLEMENTATION_GAP_AUDIT.md` (`1510` bytes, refreshed 2026-06-25 23:59:36 +0200)
- `publication/PUBLICATION_MANIFEST.json` (`3434` bytes, refreshed 2026-06-25 23:59:36 +0200)
- `QA_RELEASE_AUDIT.json` (`7879` bytes, refreshed 2026-06-25 23:59:37 +0200)
- `QA_RELEASE_AUDIT.md` (`2311` bytes, refreshed 2026-06-25 23:59:37 +0200)

Study-gap audit status is `PASS` for artifact generation, with `all_study_implementations_ready=false` and `blocked_count=5`. The publication manifest has `study_implementation_gap_audit.exists=true` for `reports/mc_validation/open_questions/STUDY_IMPLEMENTATION_GAP_AUDIT.md`.

Release audit remains intentionally fail-closed: `study_implementation_gap_audit` is `PASS`, but `all_study_implementations_ready` is `BLOCKED` with observed `false`. Overall audit remains `BLOCKED`, `release_ready=false`, with `29` checks. This records why MV4-MV8 should not be submitted/claimed as complete until their real production implementations and required artifacts exist.

## 2026-06-26 access and CI checkpoint

Local repository checkpoint, generated 2026-06-26 06:13 UTC / 08:13 CEST:

- LUNARC ControlMaster was not active. Required pre-check command
  `ssh -O check lunarc 2>/dev/null && echo Connected || /Users/billy/lunarc-init.sh`
  attempted to create the persistent socket, but authentication failed before a
  fresh OTP could complete (`Password rejected before OTP prompt`). No LUNARC
  job was submitted in this checkpoint; the selected production run therefore
  remains the completed artifacted run `20260625T064500Z_full_input_artifacted`
  / SLURM job `3316536`.
- GitHub PR `#530` (`codex/document-study-gap-audit` into `main`) remains open
  and unmerged because the self-hosted `s00c-selector-count` check is still
  queued for run `28203194089` / job `83547676520`, created 2026-06-25
  22:00:16 UTC. This checkpoint does not bypass that pending gate.
- Best available local verification on the same checkout passed:
  `python -m pytest tests/ -q` -> `57 passed in 13.76s`.
- Focused wiki/publication/evidence verification also passed:
  `python -m pytest tests/test_wiki_export.py tests/test_publication_index.py tests/test_evidence_packets.py tests/test_reference_registry.py tests/test_notation_registry.py -q`
  -> `5 passed in 10.37s`.

Release interpretation: this is a status/evidence update only. It does not close
MV4-MV8, systematic-array, full figure-catalog, clean-kernel notebook, final
wiki/thesis, or final release-bundle blockers. Those claims remain blocked until
LUNARC access is restored, production implementations exist, required artifacts
are regenerated, QA release audit passes, and the pending GitHub check reaches a
terminal successful state.

## 2026-06-26 wiki claim-traceability and QA gate checkpoint

Local/GitHub checkpoint, generated 2026-06-26 06:46 UTC / 08:46 CEST:

- PR `#534` merged to `main` (`7a7f994795ffca72c0921fc9307f9a807d0a7bb9`) and adds generated wiki page `wiki/Claim-Evidence-Matrix.md`. The page maps every claim-ledger row to project evidence artifacts plus curated reference anchors and leaves blocked claims as `BLOCKED: no production artifact yet`.
- PR `#535` merged to `main` (`f325fa36fa7c005985d61d7d0d13fa3ffc80a3e6`) and adds release-audit check `wiki_claim_evidence_matrix`. The check is fail-closed: it passes only when `wiki/WIKI_MANIFEST.json` lists `Claim-Evidence-Matrix.md` and the page exists non-empty.
- Local verification on `main` after PR `#535`: `python -m pytest tests/test_release_audit.py -q` -> `1 passed in 9.18s`. Full-suite verification on the PR branch before merge: `python -m pytest tests/ -q` -> `59 passed in 14.39s`; GitHub Actions MC Validation CI passed twice for PR `#535`.
- LUNARC remains unavailable for new job submission in this checkpoint. Required pre-check/autologin command `ssh -O check lunarc 2>/dev/null && echo Connected || /Users/billy/lunarc-init.sh` attempted again; the helper reported `LUNARC closed the connection before authentication completed`. Therefore no new SLURM job or fresh artifact regeneration is claimed here.

Release interpretation: this checkpoint strengthens wiki/report traceability and QA coverage only. It does not close MV4-MV8, systematic arrays, full figure catalog, clean-kernel notebook, final thesis/static-site, final release bundle, or LUNARC regeneration blockers. The authoritative selected run remains `20260625T064500Z_full_input_artifacted` / SLURM job `3316536` until remote access is restored and new production jobs complete.

## 2026-06-26 recursive claim-dependency wiki checkpoint

Local/GitHub checkpoint, generated 2026-06-26 07:13 UTC / 09:13 CEST:

- PR `#539` merged to `main` (`3e7c3c32b54e649935513ac7540a87f3642493fd`) and adds generated wiki page `wiki/Claim-Dependency-Tree.md`. The page renders a Mermaid dependency graph from final-release claim to QA/wiki traceability, individual claim-ledger rows, frozen evidence artifacts, curated reference anchors, and explicit blockers.
- PR `#540` merged to `main` (`7cd0624020a4e21ca851be0e3b98fa10f01d5fe2`) and adds release-audit check `wiki_claim_dependency_tree`. The check is fail-closed: it passes only when `wiki/WIKI_MANIFEST.json` lists `Claim-Dependency-Tree.md` and the page exists non-empty.
- Local verification on `main` after PR `#540`: `python -m pytest tests/test_release_audit.py -q` -> `1 passed in 9.29s`. Full-suite verification on PR branches before merge: `python -m pytest tests/ -q` -> `59 passed`; GitHub Actions MC Validation CI passed twice for both PRs.
- LUNARC remains unavailable for new job submission in this checkpoint. The required pre-check/autologin command authenticated through OTP but ended with `Socket not created - check SSH config try again`. Therefore no new SLURM job or fresh artifact regeneration is claimed here.

Release interpretation: this checkpoint strengthens recursive claim explanation and QA coverage only. It does not close MV4-MV8, systematic arrays, full figure catalog, clean-kernel notebooks, final thesis/static-site, final release bundle, or LUNARC regeneration blockers. The authoritative selected run remains `20260625T064500Z_full_input_artifacted` / SLURM job `3316536` until remote access is restored and new production jobs complete.

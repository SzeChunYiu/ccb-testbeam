# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-24T00:13:55Z`
- Task: `AUD-G4-020`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `b8e83fa39209d5e627c3e5c15834a10f80fcbcd2`
- Validated tool/test/evidence head: `81c02634e36a7111a9fe9f15d496203bf8c0e74f`
- Remote main immediately before final handoff: `51c5cce25b35b461e01c74e2bfd4c22d2ba180bc`
- Destination: direct to `main`
- Acceptance: VALIDATED source-audit gate and visual evidence; canonical cross-energy reporting remains FLAWED, so `AUD-G4-020` is PARTIAL.

## Start-of-run and concurrent-work review

- Confirmed repository admin/push permission, fetched current remote-main history, and based every write on current `main`.
- Inspected the canonical stopping-power comparison, shared simulation parser, recent stopping-power evidence, all mandatory `chatgpt_todo/` coordination files, open pull requests, PR #868, and commit status.
- `AUD-REPO-001` remained owned by a concurrent session and was not duplicated.
- PR #868 remains closed, unmerged, and non-mergeable. It was not reopened, changed, or merged.
- A direct clone/fetch attempt failed with `Could not resolve host: github.com`. Exact current source was inspected through authenticated GitHub reads; the new audit code and tests were executed in the local session workspace.
- Every repository write targeted `main`; no force push, history rewrite, task branch, or unrelated rollback was used.
- No status checks were attached to the start-of-run main commit.

## Confirmed statistical/reporting flaw

The canonical reporter groups ratios by particle species and prints:

```python
statistics.mean(ratios)
```

as `mean point-estimate ratio [species]` across distinct exact configured energies. At the same time, every comparison point records:

```text
uncertainty_method=NOT_EVALUATED
```

The reporter defines no combined measurand, point uncertainty, covariance, weighting rule, likelihood, or energy-grid sensitivity study. The equal-weight arithmetic mean is therefore not an accepted combined stopping-power closure estimate. It can conceal energy-dependent bias and changes when the configured energy grid changes.

Exact repository source inspected:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob SHA-1: `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`
- grouping/report block: approximately lines 365–372
- arithmetic mean call and label: approximately line 370

## Literature-backed method basis

- National Institute of Standards and Technology, Technical Note 1297.
- Persistent identifier: `doi:10.6028/NIST.tn.1297`.
- Statement supported: combination of measurement results requires identified uncertainty components and an established, documented propagation/combination method, with covariance considered where relevant.

This is a reporting-method basis only. It does not validate the repository's Geant4 observable, PSTAR comparison, or numerical result.

## Validated audit tooling and evidence

Added:

- `tools/audit/audit_stopping_power_cross_energy_summary.py` v1.0.0
- `tests/test_audit_stopping_power_cross_energy_summary.py`
- `docs/validation/stopping_power_cross_energy_summary_audit.md`
- `docs/validation/stopping_power_cross_energy_summary_validation.json`
- `docs/validation/stopping_power_cross_energy_summary.svg`

The audit tool:

1. reads one exact source snapshot;
2. parses the Python AST;
3. detects the conjunction of a `statistics.mean` call and the exact `mean point-estimate ratio` report label;
4. records source byte size and SHA-256;
5. emits `UNWEIGHTED_CROSS_ENERGY_MEAN` and returns status 1;
6. converts read, UTF-8, and Python-parse failures into controlled status 2.

Policy identifier:

`NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`

The SVG is explicitly synthetic software-method evidence, not detector data. It shows separate energy points and crosses out the arithmetic mean using position, text, and linework rather than color alone.

## Regression and validation

Executed in `/mnt/data/audit_run`:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_stopping_power_cross_energy_summary.py \
  tests/test_audit_stopping_power_cross_energy_summary.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_stopping_power_cross_energy_summary.py -q

4 passed in 0.03s
```

Additional passed checks:

- SVG XML parse;
- maximum audit-tool line length: 90 characters;
- maximum test line length: 81 characters.

The exact repository reporter was not executed locally because a current checkout could not be obtained. The machine-readable validation record explicitly distinguishes authenticated source inspection from local execution.

Not run: full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation execution, or GitHub Actions. No broader CI, simulation, uncertainty, or physics-closure success is claimed.

## Direct-to-main commit sequence

Implementation, test, and evidence:

- `a5985de2167a49a968190fd9505bd98db6e89218` — `feat(audit): detect unsupported cross-energy stopping means`
- `c13849fe7a23adbe8cb008b25233385b9d9f56b1` — `test(audit): cover cross-energy summary gate`
- `f83c12aafd7a3ae0389592e4b37a335e4cc553b6` — `docs(validation): record cross-energy summary flaw`
- `91957de2c5b1c93eb708ac2668b7709e1d756c62` — `docs(validation): add cross-energy summary audit record`
- `81c02634e36a7111a9fe9f15d496203bf8c0e74f` — `docs(validation): visualize cross-energy summary gate`

Coordination and provenance:

- `f34c528f12e0703600d736251111d8886a9b4649` — active task
- `83d0af4ea0f354bcc50672ca58509970171f0748` — backlog
- `db5158a0925d2d5b11440e45656c8dbf07279437` — master index
- `e99f96c55616a957e8cfaf7ce2d057dc6d02e2fb` — code-result map
- `eb6ca260d84aa2329095a76a3c113ace2fc7c710` — study ledger
- `70d1ad559866418e2744a8895fde71c8e384ba29` — claim matrix
- `d584c6a15a80e4a2a8cf89720bbb2365cadad5d2` — visualization matrix
- `740b7baa0e15e25a68aca50ed9b7f8969fb0ebc1` — blocker register
- `51c5cce25b35b461e01c74e2bfd4c22d2ba180bc` — immutable archive

Every contents write returned a successful direct-main commit. The commit containing this handoff must be confirmed separately as the final remote-main head.

## `chatgpt_todo/` updates

Updated:

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `MASTER_INDEX.md`
- `CODE_RESULT_MAP.md`
- `STUDY_REVIEW_LEDGER.md`
- `CLAIM_EVIDENCE_MATRIX.md`
- `VISUALIZATION_MATRIX.md`
- `BLOCKERS.md`
- `HANDOFF.md`

Added immutable session record:

- `chatgpt_todo/archive/2026-07-24T001355Z_AUD-G4-020_CROSS_ENERGY_SUMMARY.md`

`SESSION_LOG.md` was not replaced. The connector returned only a truncated portion of the long append-only file and exposes complete-file replacement rather than a byte-safe append primitive. Replacing it from incomplete bytes could destroy earlier provenance. The immutable archive and this handoff preserve the complete run record; the missing append is an explicit coordination limitation, not a scientific acceptance claim.

## Scientific boundary

This run did not:

- remove the arithmetic mean from the canonical reporter;
- run a real Geant4 event export;
- estimate statistical or systematic uncertainty;
- define or validate covariance or weighting;
- establish local deposited energy as projectile total energy loss;
- establish proton or deuteron stopping-power agreement;
- produce a detector calibration or performance result.

The canonical output remains `DIAGNOSTIC_ONLY`. `BLK-G4-SP-001` remains open, and new blocker `BLK-G4-SP-003` records the unsupported mean.

## Required next action

1. Remove `statistics.mean(ratios)` and `mean point-estimate ratio` from `compare_stopping_power.py`.
2. Report each energy point separately and, if useful, descriptive minimum/maximum bounds only.
3. Print and record `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`.
4. Add canonical reporter regressions proving no cross-energy combination is emitted.
5. Run the source audit and all supported stopping-power test modules.
6. Only define a future combined value after preregistering the measurand, point uncertainties, covariance, weighting or likelihood, energy-grid sensitivity, and coverage validation.

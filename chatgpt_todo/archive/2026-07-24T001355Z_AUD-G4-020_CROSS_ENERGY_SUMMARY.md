# Immutable Session Record — AUD-G4-020

## Session identity

- UTC: `2026-07-24T00:13:55Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Owner: scheduled ChatGPT scientific-review session
- Task: `AUD-G4-020`
- Initial remote `main`: `b8e83fa39209d5e627c3e5c15834a10f80fcbcd2`
- Validated tool/test/evidence head: `81c02634e36a7111a9fe9f15d496203bf8c0e74f`
- Destination: direct commits to `main`
- Acceptance state: audit gate and evidence VALIDATED; canonical reporting behavior FLAWED; task PARTIAL.

## Start-of-run review

- Confirmed repository admin/push permission and default branch `main`.
- Fetched recent remote-main history and based every write on current `main` through GitHub's contents API; no force push, history rewrite, task branch, or unrelated rollback was used.
- Inspected `chatgpt_todo/HANDOFF.md`, `ACTIVE_TASK.md`, `BACKLOG.md`, `MASTER_INDEX.md`, `CODE_RESULT_MAP.md`, `STUDY_REVIEW_LEDGER.md`, `CLAIM_EVIDENCE_MATRIX.md`, `VISUALIZATION_MATRIX.md`, `BLOCKERS.md`, and the available portion of `SESSION_LOG.md`.
- Inspected the canonical stopping-power reporter and simulation parser, recent commits, open pull requests, PR #868, and current commit status.
- PR #868 is closed, unmerged, and non-mergeable; it was not changed or merged.
- A direct clone/fetch remained unavailable because the container could not resolve `github.com`. Exact repository source was inspected through authenticated GitHub reads; focused new code/tests were executed from the local session workspace.
- No status checks were attached to the start-of-run main commit.

## Confirmed statistical/reporting flaw

`compare_stopping_power.py` groups point-estimate ratios by particle species and prints:

```python
statistics.mean(ratios)
```

under the label `mean point-estimate ratio [species]` across distinct exact configured energies. The same report records `uncertainty_method=NOT_EVALUATED` for every point. It defines no combined measurand, point uncertainty, covariance, weighting rule, likelihood, or energy-grid sensitivity study.

The equal-weight arithmetic mean is therefore not an accepted combined stopping-power closure estimate. It can hide energy-dependent bias and changes when the configured energy grid changes. The exact inspected source blob is:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob SHA-1: `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`
- grouping/report block: source lines approximately 365–372
- mean call and label: source line approximately 370

## Literature-backed method basis

- National Institute of Standards and Technology, Technical Note 1297.
- Persistent identifier: `doi:10.6028/NIST.tn.1297`.
- Statement supported: combined measurement results require identified uncertainty components and an established, documented combination/propagation method, with covariance considered where relevant.

This source is used as a reporting-method basis. It does not validate the repository's Geant4 observable or numerical result.

## Validated audit tooling

Added:

- `tools/audit/audit_stopping_power_cross_energy_summary.py` v1.0.0
- `tests/test_audit_stopping_power_cross_energy_summary.py`
- `docs/validation/stopping_power_cross_energy_summary_audit.md`
- `docs/validation/stopping_power_cross_energy_summary_validation.json`
- `docs/validation/stopping_power_cross_energy_summary.svg`

The audit tool reads one exact source snapshot, parses the AST, detects the conjunction of a `statistics.mean` call and the `mean point-estimate ratio` report label, records source byte size and SHA-256, emits `UNWEIGHTED_CROSS_ENERGY_MEAN`, and exits nonzero. Invalid source, UTF-8, or Python syntax is a controlled status-2 failure.

Policy identifier:

`NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`

The visual is explicitly labelled synthetic software-method evidence rather than detector data. It shows separate energy points and crosses out the arithmetic mean using position, text, and linework rather than color alone.

## Exact validation

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

- SVG parsed as XML;
- maximum tool line length: 90 characters;
- maximum test line length: 81 characters.

The exact repository reporter was not executed locally because a current checkout could not be obtained. Its bytes and source location were inspected through the authenticated GitHub connector. The machine-readable record states this limitation explicitly.

## Direct-to-main commit sequence

Implementation, tests, and evidence:

- `a5985de2167a49a968190fd9505bd98db6e89218` — `feat(audit): detect unsupported cross-energy stopping means`
- `c13849fe7a23adbe8cb008b25233385b9d9f56b1` — `test(audit): cover cross-energy summary gate`
- `f83c12aafd7a3ae0389592e4b37a335e4cc553b6` — `docs(validation): record cross-energy summary flaw`
- `91957de2c5b1c93eb708ac2668b7709e1d756c62` — `docs(validation): add cross-energy summary audit record`
- `81c02634e36a7111a9fe9f15d496203bf8c0e74f` — `docs(validation): visualize cross-energy summary gate`

Coordination and evidence mapping before this archive:

- `f34c528f12e0703600d736251111d8886a9b4649` — active task
- `83d0af4ea0f354bcc50672ca58509970171f0748` — backlog
- `db5158a0925d2d5b11440e45656c8dbf07279437` — master index
- `e99f96c55616a957e8cfaf7ce2d057dc6d02e2fb` — code-result map
- `eb6ca260d84aa2329095a76a3c113ace2fc7c710` — study ledger
- `70d1ad559866418e2744a8895fde71c8e384ba29` — claim matrix
- `d584c6a15a80e4a2a8cf89720bbb2365cadad5d2` — visualization matrix
- `740b7baa0e15e25a68aca50ed9b7f8969fb0ebc1` — blocker register

Every write returned a successful direct-main commit.

## `chatgpt_todo/` state

- `ACTIVE_TASK.md`: `AUD-G4-020`, PARTIAL / canonical behavior FLAWED.
- `BACKLOG.md`: added P0 task `AUD-G4-020`.
- `MASTER_INDEX.md`: added `IDX-G4-022`.
- `CODE_RESULT_MAP.md`: added `CRM-G4-020`.
- `STUDY_REVIEW_LEDGER.md`: added `ST-G4-STOP-012`.
- `CLAIM_EVIDENCE_MATRIX.md`: added `CL-G4-021` as FLAWED.
- `VISUALIZATION_MATRIX.md`: added `VIS-G4-020` as COMPLETE visual evidence.
- `BLOCKERS.md`: added open `BLK-G4-SP-003`.

`SESSION_LOG.md` was not replaced. The connector returned only a truncated portion of the long append-only file and exposes complete-file replacement rather than a byte-safe append primitive. Replacing it from incomplete bytes could destroy earlier provenance. This immutable archive and the final handoff preserve the complete run record; omission from the append-only log is an explicit coordination limitation, not a scientific success claim.

## Scientific boundary

This run did not:

- remove the unsafe mean from the canonical reporter;
- run a real Geant4 event export;
- estimate statistical or systematic uncertainty;
- define or validate a covariance model;
- establish local deposited energy as projectile total energy loss;
- establish proton or deuteron stopping-power agreement;
- produce a detector calibration or performance result.

The canonical output remains `DIAGNOSTIC_ONLY`, and `BLK-G4-SP-001` remains open.

## Required next action

1. Remove `statistics.mean(ratios)` and the `mean point-estimate ratio` line from `compare_stopping_power.py`.
2. Retain individual energy points and, if useful, descriptive min/max bounds only.
3. Print and record `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`.
4. Add canonical reporter tests proving no cross-energy mean is emitted.
5. Run the new source audit plus all supported stopping-power regression modules.
6. Only define a future combined value after preregistering the measurand, uncertainties, covariance, weighting/likelihood, energy-grid sensitivity, and coverage validation.

# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-24T011158Z`
- Task: `AUD-G4-020`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `6460d5f1479163d000d9fbbe260ba4e3ce0db7d7`
- Validated code/test/evidence head: `6ef9962fe8c5795d862728ad4d02c47138efc14f`
- Remote main immediately before final handoff: `82e3b0dc47183ea125f06b29bf4bf518af2f6a09`
- Destination: direct to `main`
- Acceptance: COMPLETE for removal of the unsupported cross-energy mean; broader stopping-power physics closure remains blocked.

## Start-of-run and concurrent-work review

- Confirmed repository admin/push permission, default branch `main`, recent history, source blob, commit status, open coordination records, and the previous `AUD-G4-020` handoff.
- Based work on current remote `main`; no task branch, PR, force push, history rewrite, or unrelated rollback was used.
- PR #868 remains closed, unmerged, and non-mergeable. It was not modified or merged.
- Start-of-run main had no attached status checks.
- A direct clone failed with `Could not resolve host: github.com`; exact source was read/written through the authenticated GitHub connector and validated in a reconstructed local workspace.
- `AUD-REPO-001` remains owned by a concurrent session and was not duplicated.

## Confirmed reporting flaw

The prior canonical reporter grouped point-estimate simulation/PSTAR ratios by particle species and printed:

```python
statistics.mean(ratios)
```

as `mean point-estimate ratio` across distinct exact configured energies. Every contributing point simultaneously recorded `uncertainty_method=NOT_EVALUATED`; no common measurand, point uncertainty, covariance, weighting rule, likelihood, energy-grid sensitivity, or coverage model existed.

Pre-change source:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob SHA-1: `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`

The arithmetic mean could conceal energy dependence and change with the configured grid. It was not an accepted combined stopping-power closure estimate.

## Corrected behavior

The canonical reporter now:

1. removes the `statistics` import and arithmetic mean;
2. retains every exact configured energy point separately;
3. emits only descriptive minimum and maximum point-estimate ratio bounds per species;
4. labels those bounds `no combined estimate`;
5. prints `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`;
6. records that policy in every result dictionary and output CSV row.

Descriptive bounds remain non-accepting and are not presented as an estimator of a common parameter.

## Regression and evidence

Added:

- `tests/test_compare_stopping_power_cross_energy_policy.py`
- `docs/validation/stopping_power_cross_energy_remediation_audit.md`
- `docs/validation/stopping_power_cross_energy_remediation_validation.json`
- `docs/validation/stopping_power_cross_energy_remediation.svg`

Synthetic points:

- proton, 1 MeV: ratio `1.0`;
- proton, 2 MeV: ratio `0.8`.

The reporter emitted `[0.8000, 1.0000]`, `no combined estimate`, and the explicit policy; it emitted no `mean point-estimate ratio`. Both machine-readable rows retained the policy. The SVG is synthetic software-method evidence, not detector data.

## Validation commands and results

Executed in a reconstructed exact-source workspace:

```text
PYTHONPATH=. python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/audit_stopping_power_cross_energy_summary.py \
  tests/test_audit_stopping_power_cross_energy_summary.py \
  tests/test_compare_stopping_power_cross_energy_policy.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_stopping_power_cross_energy_summary.py \
  tests/test_compare_stopping_power_cross_energy_policy.py -q

6 passed in 0.04s

PYTHONPATH=. python tools/audit/audit_stopping_power_cross_energy_summary.py \
  scripts/single_stave/compare_stopping_power.py \
  --output docs/validation/stopping_power_cross_energy_remediation_validation.json

CROSS-ENERGY SUMMARY AUDIT: status=VALIDATED
```

Additional passed checks:

- source local Git blob matched committed blob `360f3e46db664f4eead48021536f210e2f7a85c9`;
- test local Git blob matched committed blob `a46f092cccc8624db2078bd8da9eb8d5023c3386`;
- source SHA-256: `15653bb4d4b1a3e4a1b2296dc8c61bb7813bf29bbdbe6c05ea65731d106ee3ca`;
- maximum changed Python line length: 91 characters;
- validation JSON parse;
- SVG XML parse.

Not run: full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation execution, or GitHub Actions. No broader CI or physics-closure success is claimed.

## Direct-to-main commit sequence

- `fd6fd6dc383ccb69b5fde9fbcd7e306cb86eded8` — `fix(single-stave): remove unsupported cross-energy mean`
- `cc1f9832e6b4c6018de90caedc48743289d65cf7` — `test(single-stave): cover noncombined cross-energy reporting`
- `4d0a421c95593141f1a5e82ff4921a1a5e9f6aad` — `docs(validation): record cross-energy reporting remediation`
- `4f3e01dfdd58b7558b282fe8f76e9717870a715a` — `docs(validation): add cross-energy remediation record`
- `6ef9962fe8c5795d862728ad4d02c47138efc14f` — `docs(validation): visualize cross-energy remediation`
- `80f1379adc2ed1117c291602091903720cdd4c14` — `docs(audit): complete cross-energy summary remediation`
- `99367ae52cd90066878d43faa7fd59aebdaa39dd` — `docs(audit): close cross-energy summary backlog task`
- `4ab4a33025abb1e66289b994ad03f28ec3e12589` — `docs(audit): resolve cross-energy mean blocker`
- `82e3b0dc47183ea125f06b29bf4bf518af2f6a09` — `docs(audit): archive cross-energy reporting remediation`

Every write returned a successful direct-main commit. The commit containing this handoff must be confirmed separately as the final remote-main head.

## `chatgpt_todo/` updates

Updated:

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `BLOCKERS.md`
- `HANDOFF.md`

Added immutable session record:

- `chatgpt_todo/archive/2026-07-24T011158Z_AUD-G4-020_CROSS_ENERGY_REMEDIATION.md`

`SESSION_LOG.md` was not replaced because the connector returned only a truncated portion of the long append-only file and exposes complete-file replacement rather than a byte-safe append primitive. Replacing it from incomplete bytes could destroy earlier provenance. The immutable archive and this handoff preserve the complete run record; this missing append is an explicit coordination limitation.

## Scientific boundary

This run did not:

- define or estimate statistical/systematic uncertainty;
- define covariance, weighting, likelihood, or a combined measurand;
- validate exact real Geant4 exports;
- establish local deposited energy as projectile total energy loss;
- establish proton or deuteron Geant4/PSTAR agreement;
- produce calibration or detector-performance results.

`BLK-G4-SP-003` is RESOLVED. `AUD-G4-020` is COMPLETE. Accepted stopping-power closure remains open under `BLK-G4-SP-001`, `AUD-G4-005`, and `AUD-G4-011`.

## Required next action

Obtain immutable real Geant4 exports and validate a projectile-energy-loss observable or `G4EmCalculator::ComputeTotalDEDX`. Preregister and validate point uncertainty, covariance, configuration sensitivity, coverage, and acceptance criteria before any accepted Geant4/PSTAR agreement or combined result.

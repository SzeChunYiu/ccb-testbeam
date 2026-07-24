# Immutable Session Record — AUD-G4-020

## Session identity

- UTC: `2026-07-24T011158Z`
- Owner: scheduled ChatGPT audit session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `6460d5f1479163d000d9fbbe260ba4e3ce0db7d7`
- Remote main before this archive: `4ab4a33025abb1e66289b994ad03f28ec3e12589`
- Destination: direct to `main`
- Status: COMPLETE for unsupported cross-energy mean removal

## Start-of-run review

- Confirmed repository admin/push permission and default branch `main`.
- Re-read the previous `AUD-G4-020` handoff, active task, backlog, blocker register, canonical reporter, source-audit tool, focused tests, recent commits, commit status, and PR #868.
- PR #868 remained closed, unmerged, and non-mergeable and was not modified.
- Start-of-run main had no attached status checks.
- Direct clone failed with `Could not resolve host: github.com`; exact source was read and written through the authenticated GitHub connector and validated in a reconstructed local workspace.

## Confirmed defect

The canonical stopping-power reporter grouped point-estimate ratios by species and printed `statistics.mean(ratios)` across distinct exact configured energies as `mean point-estimate ratio`. Every contributing point declared `uncertainty_method=NOT_EVALUATED`; no combined measurand, point uncertainty, covariance, weighting rule, likelihood, energy-grid sensitivity, or coverage model existed.

Pre-change source:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob SHA-1: `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`

## Corrected method

The canonical reporter now:

1. removes the `statistics` import and arithmetic mean;
2. keeps every exact configured energy point separate;
3. prints descriptive minimum/maximum point-estimate ratio bounds only;
4. labels those bounds `no combined estimate`;
5. prints `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`;
6. records the same policy in every result dictionary and output CSV row.

The descriptive range is not used for acceptance and is not represented as a common-parameter estimate.

## Synthetic validation

Controlled synthetic points:

- proton, 1 MeV: ratio `1.0`;
- proton, 2 MeV: ratio `0.8`.

Observed output:

- descriptive range `[0.8000, 1.0000]`;
- explicit `no combined estimate` wording;
- explicit no-combination policy;
- no `mean point-estimate ratio`;
- policy present in both result dictionaries and both CSV rows.

Commands:

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

Additional checks:

- source local Git blob = committed blob `360f3e46db664f4eead48021536f210e2f7a85c9`;
- test local Git blob = committed blob `a46f092cccc8624db2078bd8da9eb8d5023c3386`;
- source SHA-256 = `15653bb4d4b1a3e4a1b2296dc8c61bb7813bf29bbdbe6c05ea65731d106ee3ca`;
- test SHA-256 = `b59ac51edf436fc3a353fbe198ffd105623180935176cbc56c7782ae2d892117`;
- maximum changed Python line length = 91 characters;
- validation JSON parsed;
- SVG parsed as XML.

## Evidence

- `docs/validation/stopping_power_cross_energy_remediation_audit.md`
- `docs/validation/stopping_power_cross_energy_remediation_validation.json`
- `docs/validation/stopping_power_cross_energy_remediation.svg`

The SVG is synthetic software-method evidence, not detector data.

## Direct-to-main commits before archive

- `fd6fd6dc383ccb69b5fde9fbcd7e306cb86eded8` — `fix(single-stave): remove unsupported cross-energy mean`
- `cc1f9832e6b4c6018de90caedc48743289d65cf7` — `test(single-stave): cover noncombined cross-energy reporting`
- `4d0a421c95593141f1a5e82ff4921a1a5e9f6aad` — `docs(validation): record cross-energy reporting remediation`
- `4f3e01dfdd58b7558b282fe8f76e9717870a715a` — `docs(validation): add cross-energy remediation record`
- `6ef9962fe8c5795d862728ad4d02c47138efc14f` — `docs(validation): visualize cross-energy remediation`
- `80f1379adc2ed1117c291602091903720cdd4c14` — `docs(audit): complete cross-energy summary remediation`
- `99367ae52cd90066878d43faa7fd59aebdaa39dd` — `docs(audit): close cross-energy summary backlog task`
- `4ab4a33025abb1e66289b994ad03f28ec3e12589` — `docs(audit): resolve cross-energy mean blocker`

All writes targeted `main`; no force push, history rewrite, temporary branch, PR, or unrelated rollback was used.

## Coordination

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/HANDOFF.md` after this archive

`SESSION_LOG.md` was not replaced because the connector returned only a truncated portion of the long append-only file and exposes complete-file replacement rather than a byte-safe append primitive. Replacing it from incomplete bytes could destroy earlier provenance. This immutable record and the final handoff preserve the full session; the missing append is explicit.

## Scientific boundary

This run did not:

- define or estimate point uncertainties;
- define covariance, weighting, likelihood, or a combined measurand;
- validate a real Geant4 event export;
- establish local deposited energy as projectile total energy loss;
- establish proton or deuteron Geant4/PSTAR agreement;
- produce calibration or detector-performance results.

`BLK-G4-SP-003` is resolved as an engineering/reporting blocker. Broader accepted stopping-power closure remains open under `BLK-G4-SP-001`, `AUD-G4-005`, and `AUD-G4-011`.

## Next action

Obtain exact immutable real Geant4 exports and validate a projectile-energy-loss observable or `G4EmCalculator::ComputeTotalDEDX`; preregister and validate statistical/systematic uncertainty, covariance, sensitivity, and coverage before any accepted agreement or combined result.

# Immutable session record — AUD-G4-013

## Session identity

- UTC stamp: `2026-07-23T190130Z`
- Owner: scheduled ChatGPT audit session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial observed remote main: `d880c7474b2ba3f981fa6e402d1723d1c450e22d`
- Concurrent main observed before first write: `6fd458150fd7f7eff1be044c40b0675031935547`
- Additional concurrent main observed after evidence commits: `2604129517e9241584cb91bea63aec1ceb1073a5`
- Validated implementation/evidence head: `2a29ffcfc0f645cede8b7ef621b1f17ac57a6bb7`
- Destination: direct commits to `main`; no task branch, pull request, force-push, or history rewrite.

## Files and history inspected

- `scripts/single_stave/compare_stopping_power.py`
- canonical simulation and PSTAR validators
- focused stopping-power tests
- current `chatgpt_todo/` active task, backlog, index, code-result map, study ledger, claim matrix, visualization matrix, blockers, session log, and handoff
- recent remote-main commits and current repository permissions

A local clone was attempted and failed because this runtime could not resolve `github.com`; authenticated GitHub connector reads and direct-main writes were used.

## Confirmed numerical-method defect

The former aggregator keyed rows by:

```python
(particle, round(energy_MeV, 1))
```

and reported the arithmetic mean of the original energies for the pooled group. Thus synthetic `1.01 MeV` and `1.04 MeV` events became one comparison row at `1.025 MeV`. This silently changed both the pooled simulation statistic and the energy at which the nonlinear PSTAR reference was evaluated, without a declared binning or integration rule.

The exact pre-change reconstruction matched Git blob:

```text
d525bf6b74a18d135b38434dd5085123b995132a
```

The new regression against that exact blob produced:

```text
2 failed, 1 passed in 0.57s
```

Both failures measured the former `[1.01, 1.04] -> [1.025]` merge.

## Validated correction

- Aggregation keys on `(particle, energy_MeV)` using the exact validated numeric energy.
- Numerically identical representations such as `1.0` and `1.00` still group after canonical numeric parsing.
- Distinct numeric energies remain separate.
- Result rows and CSV output record `energy_grouping=EXACT_CONFIGURED_ENERGY`.
- The CLI prints `ENERGY GROUPING: EXACT_CONFIGURED_ENERGY`.

## Validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_sim_input_integration.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_quenched_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_sim_input_integration.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_quenched_proxy.py -q

19 passed in 3.22s
```

Additional passed checks:

- exact pre-change Git-blob identity;
- JSON parse;
- SVG XML parse;
- changed Python line lengths no greater than 100 characters;
- local SHA-256 capture for the changed script and test.

Not run:

- full repository pytest;
- ruff, which was unavailable;
- Geant4 build or CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

## Version-controlled evidence

- `docs/validation/stopping_power_energy_grouping_audit.md`
- `docs/validation/stopping_power_energy_grouping_validation.json`
- `docs/validation/stopping_power_energy_grouping.svg`

The SVG is explicitly labelled synthetic regression evidence and not detector data.

## Direct-main commits before this archive

Implementation, tests, evidence:

- `e5a5dab83cbddbc8c65341043a21c11ea37d8d06` — `fix(single-stave): preserve exact configured energies`
- `ee141c4e1daea7fa9c862191e418954ebc2e3a95` — `test(single-stave): cover exact configured-energy grouping`
- `05c5b03098c36399abbced190cac71b1e9e4db36` — `docs(validation): record stopping-power energy grouping audit`
- `d3294ae5b477ffdf125aa404b9e397b7701b3ebc` — `docs(validation): add stopping-power energy grouping record`
- `2a29ffcfc0f645cede8b7ef621b1f17ac57a6bb7` — `docs(validation): visualize stopping-power energy grouping gate`

Coordination:

- `9d484db1d57679820c4d9e90356fa35e40b08a99` — active-task completion
- `658bc765d1b1e5e9aa93655526aec916cb91e701` — backlog completion
- `c30af2e5b98e0c3c6e39a22d6e19cb04a6f458e9` — master-index entry
- `c58d474d604fbb4c1e2d20718bc502b81f6034cb` — code-result map
- `fecd9572ece372a9a11da99facc042a1358a8dec` — study ledger
- `096606cf6497e6ad4d24b4210a539c75670f21a6` — claim matrix
- `da85305b2fcc2cebe789b1551dfcd8bdfff2e925` — visualization matrix
- `02117b84f41df0f19d7f38fa5ebee03c1b46fafb` — blocker refinement

## Scientific boundary and next work

This session validates numerical grouping semantics only. It does not establish that local deposited energy equals projectile total energy loss, does not validate the deuteron `E/2` approximation, and does not produce Geant4/PSTAR agreement, calibration, or detector-performance evidence.

`AUD-G4-011` remains PARTIAL because no exact real exported event table was available. `AUD-G4-005` and `BLK-G4-SP-001` remain open pending a provenance-retained proton stopping-power closure and secondary-energy accounting.

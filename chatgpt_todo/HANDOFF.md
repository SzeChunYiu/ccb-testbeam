# Latest Scientific Review Handoff

## Session

- **UTC:** `2026-07-23T19:01:30Z`
- **Task:** `AUD-G4-013`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial observed remote main:** `d880c7474b2ba3f981fa6e402d1723d1c450e22d`
- **Concurrent main observed before first write:** `6fd458150fd7f7eff1be044c40b0675031935547`
- **Additional concurrent main observed after evidence writes:** `2604129517e9241584cb91bea63aec1ceb1073a5`
- **Validated implementation/evidence head:** `2a29ffcfc0f645cede8b7ef621b1f17ac57a6bb7`
- **Coordination/archive head before this handoff:** `e991726e098166d0e48273e027d25960ab76a2dd`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for exact configured-energy grouping, focused regression, visual evidence, coordination, and immutable archive; accepted stopping-power physics closure remains PARTIAL.

## Start-of-run and concurrent-work review

- A direct clone was attempted and failed because this runtime could not resolve `github.com`; authenticated GitHub connector reads and writes were used.
- Inspected remote-main history and divergence, repository permissions, PR #868, canonical stopping-power code, simulation and PSTAR validators, focused tests, validation records, and all mandatory `chatgpt_todo/` files.
- PR #868 remains closed, unmerged, and non-mergeable. It was not reopened, modified, or merged.
- Concurrent commits were inspected before and during the run. The stopping-power file blob was unchanged by those commits, and no active completed task was duplicated.
- No task branch, pull request, force-push, history rewrite, unrelated deletion, or raw-data modification was used.

## Confirmed numerical-method defect

The former stopping-power aggregator used:

```python
key = (particle, round(energy, 1))
```

It then pooled deposited energy and path length and reported the arithmetic mean of the original energies. Synthetic events at `1.01 MeV` and `1.04 MeV` therefore became one comparison row at `1.025 MeV`.

This is not a harmless display transformation. PSTAR is energy dependent and evaluated with nonlinear log-log interpolation, so the implicit merge changed both the simulation statistic and reference energy without a declared binning, weighting, or integration rule.

The exact pre-change reconstruction matched Git blob:

```text
d525bf6b74a18d135b38434dd5085123b995132a
```

Running the new regression against that exact blob produced:

```text
2 failed, 1 passed in 0.57s
```

Both failures measured the former `[1.01, 1.04] -> [1.025]` coalescence.

## Validated correction

`aggregate()` now keys on the exact validated numeric energy:

```python
key = (particle, energy)
```

Consequences:

- distinct configured energies remain distinct comparison points;
- numerically equivalent tokens such as `1.0` and `1.00` still group after canonical float parsing;
- no arithmetic-mean energy is introduced;
- each result row records `energy_grouping=EXACT_CONFIGURED_ENERGY`;
- output CSVs include `energy_grouping`;
- the CLI prints `ENERGY GROUPING: EXACT_CONFIGURED_ENERGY`.

## Regression and validation

Added:

- `tests/test_compare_stopping_power_energy_grouping.py`

The test covers:

1. `1.01` and `1.04 MeV` remain separate;
2. `1.0` and `1.00 MeV` still group;
3. the direct CLI emits one row per exact energy and records grouping metadata.

Executed on exact local reconstructions:

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
- maximum changed Python line length: 91;
- local changed-file SHA-256 capture.

Changed-file SHA-256 values:

- `scripts/single_stave/compare_stopping_power.py`: `15cdc5d0ed128b84a4fd47e3d665a899356702338ddebbe1aff4240a88c712a1`
- `tests/test_compare_stopping_power_energy_grouping.py`: `fa4098be552361c91fce93e9d19a7dfc902fd8514e293042ecd5ca76c28de485`

Not run:

- full repository pytest;
- ruff, which was unavailable;
- Geant4 build and CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

No broader CI or stopping-power agreement is claimed.

## Reproducible evidence

Added:

- `docs/validation/stopping_power_energy_grouping_audit.md`
- `docs/validation/stopping_power_energy_grouping_validation.json`
- `docs/validation/stopping_power_energy_grouping.svg`

The SVG is explicitly labelled synthetic regression evidence, not detector data. It contrasts the former pooled `1.025 MeV` point with two exact-energy rows and states the `DIAGNOSTIC_ONLY` scientific boundary.

## Direct-to-main commits

Implementation, tests, and evidence:

- `e5a5dab83cbddbc8c65341043a21c11ea37d8d06` — `fix(single-stave): preserve exact configured energies`
- `ee141c4e1daea7fa9c862191e418954ebc2e3a95` — `test(single-stave): cover exact configured-energy grouping`
- `05c5b03098c36399abbced190cac71b1e9e4db36` — `docs(validation): record stopping-power energy grouping audit`
- `d3294ae5b477ffdf125aa404b9e397b7701b3ebc` — `docs(validation): add stopping-power energy grouping record`
- `2a29ffcfc0f645cede8b7ef621b1f17ac57a6bb7` — `docs(validation): visualize stopping-power energy grouping gate`

Coordination and provenance:

- `9d484db1d57679820c4d9e90356fa35e40b08a99` — active task completion
- `658bc765d1b1e5e9aa93655526aec916cb91e701` — backlog completion
- `c30af2e5b98e0c3c6e39a22d6e19cb04a6f458e9` — master index update
- `c58d474d604fbb4c1e2d20718bc502b81f6034cb` — code-result mapping
- `fecd9572ece372a9a11da99facc042a1358a8dec` — study ledger update
- `096606cf6497e6ad4d24b4210a539c75670f21a6` — claim matrix update
- `da85305b2fcc2cebe789b1551dfcd8bdfff2e925` — visualization matrix update
- `02117b84f41df0f19d7f38fa5ebee03c1b46fafb` — stopping-power blocker refinement
- `e991726e098166d0e48273e027d25960ab76a2dd` — immutable session archive

Every listed write returned a successful direct-main commit SHA. This handoff update is the final repository write for the session and must be re-read at remote-main head before delivery is reported.

## Repository-local records

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

Added immutable provenance:

- `chatgpt_todo/archive/2026-07-23T190130Z_AUD-G4-013_EXACT_ENERGY_GROUPING.md`

`SESSION_LOG.md` was inspected in complete non-overlapping line ranges, but the available connector exposes complete-file replacement rather than append. Because concurrent main activity continued and replacing an append-only log carries avoidable provenance-loss risk, it was not rewritten. The immutable archive above contains the complete session entry and this limitation is explicit rather than concealed.

## Blockers and next action

### Resolved

`AUD-G4-013` is COMPLETE. The canonical stopping-power comparison no longer silently pools distinct configured energies through 0.1 MeV rounding.

### Still open

- `AUD-G4-011`: run the integrated CLI on exact immutable real Geant4 exports with complete input/output/environment provenance.
- `AUD-G4-005` / `BLK-G4-SP-001`: establish an accepted proton closure using `G4EmCalculator` or primary entry/exit energy plus path/reference integration, quantify escaping-secondary energy and production-cut dependence, and treat deuterons separately.
- External PSTAR transcription/material provenance remains independently unverified.

## Scientific boundary

This session validates exact configured-energy aggregation and its traceable software enforcement. It does not establish that local deposited energy equals projectile total energy loss, does not validate the deuteron approximation, and does not establish Geant4/PSTAR agreement, calibration, or detector performance. No Geant4 executable, ROOT file, real event table, stopping-power closure, calibration, or detector-performance output was generated.

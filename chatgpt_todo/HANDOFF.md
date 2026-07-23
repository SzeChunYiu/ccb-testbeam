# Latest Handoff

## Session

- **UTC:** 2026-07-23T10:04:54Z
- **Task:** `AUD-G4-004`
- **Initial remote main:** `5a4bdfc3f0099f2b6e8c3891b5a2a05f57ecf770`
- **Validated implementation/evidence head:** `e4e7f8b8e61cdbd0e45304a4fdf80d917139e522`
- **Append-only session-log head before this handoff:** `ea0349094a9f0bec503b471e65f30eb8b55c2405`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Canonical destination:** `main`
- **Acceptance:** COMPLETE for reference-path/self-test provenance; PARTIAL for accepted stopping-power physics closure.

## Start-of-run review

- Fetched current `main`, recent commits, PR #890 and its merge commit, combined status, the PSTAR comparison script/reference, `RunAction.cc`, and all mandatory `chatgpt_todo/` records.
- Detected recent PR #890/#891 and PR #882 integration before selecting non-duplicative work.
- Direct clone/raw download remained unavailable because the runtime could not resolve GitHub hosts. Authenticated GitHub connector reads and direct-to-main writes were used; no force-push or history rewrite occurred.
- No combined status checks were attached to the initial or delivered heads, so no GitHub Actions result is claimed for this session.

## Confirmed defects

### Repository path

For a script at `<repo>/scripts/single_stave/compare_stopping_power.py`:

```text
HERE.parents[0] = <repo>/scripts
HERE.parents[1] = <repo>
HERE.parents[2] = <parent-of-repo>
```

The previous default used `HERE.parents[2]`, so it looked for the PSTAR CSV outside the repository instead of reading `data/reference/stopping_power/pstar_polystyrene.csv`.

### Masked self-test

When that incorrect path was absent, `self_test()` silently generated a tiny inline reference and returned success. A synthetic checkout reproduced:

```text
DEFAULT_REF /tmp/data/reference/stopping_power/pstar_polystyrene.csv
default exists False
self_test 0
```

Thus the old pass did not establish that the committed reference existed, was readable, or was exercised.

## Validated change

`scripts/single_stave/compare_stopping_power.py` now:

- defines `REPO_ROOT = HERE.parents[1]`;
- resolves the default reference below the repository root;
- fails closed when the selected reference is missing;
- removes the inline reference fallback;
- prints resolved path, SHA-256, and parsed row count;
- cleans synthetic files with `TemporaryDirectory`;
- labels the numerical comparison `SCIENTIFIC STATUS: DIAGNOSTIC_ONLY`;
- documents local unquenched deposited energy as a proxy rather than automatic projectile total-energy loss.

Added:

- `tests/test_compare_stopping_power_reference_path.py`;
- `docs/validation/stopping_power_reference_path_audit.md`;
- `docs/validation/stopping_power_reference_path_validation.json`;
- `docs/validation/stopping_power_reference_path.svg`.

Exact remote blobs:

- script: `d9282a5c26b8bc86427356f51dfe7e5ecba769d8`;
- regression test: `ab6265ef398ac0ad7cf3110d173c85cbd6d8f987`;
- reference table inspected before change: `7e953dd346caedcee6da54180fb636b890a64040`.

## Validation

Executed on a local exact reconstruction of the committed script/test:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_reference_path.py

python -m pytest tests/test_compare_stopping_power_reference_path.py -q
```

Result:

```text
3 passed in 0.55s
```

The changed Python files had no line longer than 100 characters. The remote script/test Git blobs matched the validated local blobs.

The local reconstruction used a minimal reference fixture containing the five PSTAR rows exercised by the self-test. The complete committed table was confirmed through the connector but was not executed locally because a complete checkout/raw-file download was unavailable. Full repository pytest, ruff, Geant4, CTest, ROOT, Slurm, and GitHub Actions were not run.

## Scientific interpretation

NIST defines stopping power as projectile energy loss per path length. Geant4 local energy deposit is not necessarily the projectile's full energy loss when generated secondaries carry energy out of the scored volume. The current event ntuple records configured incident kinetic energy, not primary energy sampled continuously along the scored track.

Therefore:

- `sum(edep_scint_raw_MeV) / sum(track_len_scint_mm)` is a useful deposited-energy diagnostic;
- passing a numerical tolerance against PSTAR is not yet an accepted stopping-power closure;
- the deuteron `S_d(E) ≈ S_p(E/2)` relation is an approximation and must be separated from the direct proton PSTAR comparison.

`AUD-G4-005` and `BLK-G4-SP-001` now require one or more controlled methods:

1. `G4EmCalculator::ComputeTotalDEDX` for the exact particle, material, energy, production cuts, and physics list;
2. primary entry/exit kinetic energy with measured path length and a reference integral over the actual energy interval;
3. containment and explicit accounting of energy carried by generated secondaries.

Required accepted evidence includes exact versions, commands, cuts, physics list, seeds, event counts, input/output hashes, uncertainty, proton overlay/ratio, energy/path scan, secondary-escape diagnostics, and separately labelled deuteron approximation.

## Direct-to-main commits

Implementation and validation evidence:

- `05d9d1e41dbe18db4786e6be73e41ddef55809e9` — `fix(single-stave): exercise committed PSTAR reference`
- `31a36feae3819df391e46915a473085ca082f948` — `style(single-stave): keep PSTAR diagnostic within lint limit`
- `434e1ad1acf688f89d233a4686fdd86428d277ce` — `test(single-stave): cover PSTAR reference path and self-test`
- `be06f890f4b7361f7446f74c498524a6259b6488` — `docs(validation): record PSTAR reference-path audit`
- `afd900025020722592cca8064f1dc45ab814b05e` — `docs(validation): add PSTAR path validation record`
- `e4e7f8b8e61cdbd0e45304a4fdf80d917139e522` — `docs(validation): visualize PSTAR reference resolution`

Coordination/provenance:

- `9b3fabf86de28912ed172a5cf14737df0aa35070` — active task
- `2e3bbb77e66f78f973792658c3efa14992577724` — backlog
- `85dcc38b297b8c5ce84a8dc1b0252ff66403647c` — master index
- `746f314ced43eb5e0001b3fec2104a5239e7eb9d` — code-result map
- `8a9ce1f68880f560d33ebdef13138fc4c74171a5` — study ledger
- `9d09e0e0832f6a8e3f8170952c3847e475748170` — claim matrix
- `1c825d66d207e72d4881a930ecdb442db866b755` — visualization matrix
- `89009b14e0995c55e783440f037fd440044441bc` — blocker register
- `6d1d982e0eb6764cc3cc036aa1df76b8f3fe35c7` — immutable archive
- `ea0349094a9f0bec503b471e65f30eb8b55c2405` — append-only session log

## Repository-local records

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/CODE_RESULT_MAP.md`
- `chatgpt_todo/STUDY_REVIEW_LEDGER.md`
- `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/SESSION_LOG.md`
- `chatgpt_todo/HANDOFF.md`

Added:

- `chatgpt_todo/archive/2026-07-23T100454Z_AUD-G4-004_PSTAR_REFERENCE_PATH.md`

## Boundary and next action

No Geant4 executable, ROOT file, Slurm job, simulation output, accepted stopping-power result, calibration, or detector-performance number was generated. No scientific result from PR #890 is promoted by this session.

Next task: execute `AUD-G4-005` in a clean Geant4 environment, beginning with a proton-only `G4EmCalculator::ComputeTotalDEDX` comparison at exact reference energies, followed by entry/exit-energy and secondary-escape diagnostics. Preserve immutable artifacts and do not interpret the deposited-energy proxy as validated total stopping power beforehand.

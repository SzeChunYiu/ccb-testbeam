# AUD-G4-004 — PSTAR reference-path and self-test audit

## Session

- UTC: `2026-07-23T10:04:54Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Canonical branch: `main`
- Initial remote main: `5a4bdfc3f0099f2b6e8c3891b5a2a05f57ecf770`
- Reviewed PR: #890, merged as `1eb38b483b391545510744872342f279344dca30`
- Reviewed script blob: `2212b4faf330adb40adffb6dc5334698443d8aa3`
- Reviewed reference blob: `7e953dd346caedcee6da54180fb636b890a64040`

## Start-of-run review

The run inspected current `main`, recent concurrent merges, PR #890 metadata and files, combined commit status, the current audit handoff/task/backlog/index/blockers/session log, `RunAction.cc`, the committed PSTAR table, and the new stopping-power script. A direct clone remained unavailable because the runtime could not resolve `github.com`; authenticated connector reads and writes were used. No force-push or history rewrite was performed.

## Confirmed repository defect

For `scripts/single_stave/compare_stopping_power.py`, `HERE` is `<repo>/scripts/single_stave`. The legacy expression `HERE.parents[2]` is the parent of the repository, not the repository root. The default therefore targeted `<parent>/data/reference/stopping_power/pstar_polystyrene.csv` rather than the committed table.

The legacy `self_test()` masked the missing default by creating a tiny inline reference and returned success. A synthetic checkout reproduced:

```text
DEFAULT_REF /tmp/data/reference/stopping_power/pstar_polystyrene.csv
default exists False
self_test 0
```

Thus the reported self-test pass did not establish that the committed PSTAR data existed, was readable, or was used.

## Validated engineering change

The script now:

- sets `REPO_ROOT = HERE.parents[1]`;
- resolves the default below the repository root;
- fails closed when the selected reference is missing;
- prints the resolved reference path, SHA-256, and parsed row count;
- removes the inline reference fallback;
- cleans synthetic files through `TemporaryDirectory`;
- labels numerical output `SCIENTIFIC STATUS: DIAGNOSTIC_ONLY`;
- identifies `edep_scint_raw_MeV / track_len_scint_mm` as a local deposited-energy proxy.

Added:

- `tests/test_compare_stopping_power_reference_path.py`;
- `docs/validation/stopping_power_reference_path_audit.md`;
- `docs/validation/stopping_power_reference_path_validation.json`;
- `docs/validation/stopping_power_reference_path.svg`.

## Reproducible validation

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

A changed-file scan found no line longer than 100 characters. The exact committed blobs were verified after writing:

- script: `d9282a5c26b8bc86427356f51dfe7e5ecba769d8`;
- test: `ab6265ef398ac0ad7cf3110d173c85cbd6d8f987`.

The local reconstruction used a minimal reference fixture containing the five PSTAR rows exercised by the self-test. The full committed table was confirmed through the connector but was not executed locally because a complete checkout/raw download was unavailable. Full repository pytest, ruff, Geant4, ROOT, CTest, Slurm, and GitHub Actions were not run.

## Scientific review

NIST stopping power is projectile energy loss per path length. Geant4 local energy deposit can exclude energy carried away by generated secondaries. The current ntuple stores configured incident kinetic energy rather than energy sampled along the scored path. Therefore the local-deposition ratio is diagnostic only.

An accepted closure requires one or more of:

1. `G4EmCalculator::ComputeTotalDEDX` for the exact particle, material, energy, physics list, and production cuts;
2. primary entry/exit kinetic energy and actual path length, compared with the reference integral over the energy interval;
3. demonstrated containment and explicit accounting of energy carried by generated secondaries.

The proton PSTAR comparison and deuteron `S_d(E) ≈ S_p(E/2)` approximation must be reported separately. No deuteron reference validation is claimed.

## Direct-to-main commit sequence

- `05d9d1e41dbe18db4786e6be73e41ddef55809e9` — `fix(single-stave): exercise committed PSTAR reference`
- `31a36feae3819df391e46915a473085ca082f948` — `style(single-stave): keep PSTAR diagnostic within lint limit`
- `434e1ad1acf688f89d233a4686fdd86428d277ce` — `test(single-stave): cover PSTAR reference path and self-test`
- `be06f890f4b7361f7446f74c498524a6259b6488` — `docs(validation): record PSTAR reference-path audit`
- `afd900025020722592cca8064f1dc45ab814b05e` — `docs(validation): add PSTAR path validation record`
- `e4e7f8b8e61cdbd0e45304a4fdf80d917139e522` — `docs(validation): visualize PSTAR reference resolution`
- `9b3fabf86de28912ed172a5cf14737df0aa35070` — `docs(audit): claim PSTAR reference-path correction`
- `2e3bbb77e66f78f973792658c3efa14992577724` — `docs(audit): track stopping-power closure work`
- `85dcc38b297b8c5ce84a8dc1b0252ff66403647c` — `docs(audit): index PSTAR path and closure findings`
- `746f314ced43eb5e0001b3fec2104a5239e7eb9d` — `docs(audit): map PSTAR diagnostic to evidence`
- `8a9ce1f68880f560d33ebdef13138fc4c74171a5` — `docs(audit): add stopping-power study review`
- `9d09e0e0832f6a8e3f8170952c3847e475748170` — `docs(audit): classify PSTAR self-test and closure claims`
- `1c825d66d207e72d4881a930ecdb442db866b755` — `docs(audit): specify stopping-power closure visuals`
- `89009b14e0995c55e783440f037fd440044441bc` — `docs(audit): add stopping-power closure blocker`

## Acceptance and boundary

- Reference-path defect: COMPLETE.
- Inline-fallback removal: COMPLETE.
- Missing-reference fail-closed behavior: COMPLETE.
- Reference path/hash/row provenance: COMPLETE.
- Focused regression: COMPLETE on the local reconstruction.
- Visual and machine-readable audit evidence: COMPLETE.
- Accepted proton stopping-power closure: PARTIAL / blocked under `BLK-G4-SP-001`.
- Deuteron stopping-power validation: NOT ESTABLISHED.
- No Geant4 or ROOT result was generated or changed.

## Next action

Execute `AUD-G4-005` in a clean Geant4 environment. Start with a proton-only `G4EmCalculator::ComputeTotalDEDX` comparison at the exact energies and material density in the committed reference, then add entry/exit-energy and secondary-escape diagnostics before interpreting event-level deposited energy. Preserve exact versions, commands, production cuts, physics list, seeds, event counts, hashes, uncertainty, and overlay/ratio plots.

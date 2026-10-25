# G408-KEYLINEAGE-01 — generated-key ROOT roundtrip is not an upstream DAQ↔Geant4 parent relation

**Disposition:** `POSTED_AND_READ_BACK`, live #1608 [comment 6393062088](https://github.com/SzeChunYiu/ccb-testbeam/issues/1608#issuecomment-6393062088). **Scientific release:** `NOT_AUTHORIZED`. **Source type:** GitHub-custodied historical generated ROOT file and full archived CSV (not original DAQ raw or original Geant4 truth ROOT); exact source function inspection and JS field-level source-expression replay. No native ROOT parsing, no Geant4/DAQ execution, no physical PID effect estimate.

## Exact source and historical artifact

Main pinned `a61427813344e29047ca9eb9b764182eb29e4c83`.

- [G4-08 producer](https://github.com/SzeChunYiu/ccb-testbeam/blob/a61427813344e29047ca9eb9b764182eb29e4c83/scripts/s29a_1783809265_5764_0f2a2dda_digitized_g4_multitask_truth_benchmark.py), Git blob `dfb35f03faaf104cc0a706ccbbf07eda2a536911`.
- [Historical G4-08 publication table and output](https://github.com/SzeChunYiu/ccb-testbeam/tree/a61427813344e29047ca9eb9b764182eb29e4c83/reports/1783883140.39222.3c4045b1__g4_08_keyed_digitized_geant4_native_join) (originals UNCHANGED): `native_joined_events.csv` blob `9d2c8dba5ba529cf33dcf6100e6c05ab35d04ee2`, 1,056 records/43 columns; `digitized_g4_08_keyed.root` blob `417650b63dfe08cd7e382ff93b9002c5b4750a0d`, 112,363 bytes. Base64 decode of that genuine Git blob established the `root` header and `g4_08_digitized`/key branch names only — **not** a native ROOT engine read.
- [Prior explicitly negative G4-08 bridge](https://github.com/SzeChunYiu/ccb-testbeam/blob/a61427813344e29047ca9eb9b764182eb29e4c83/reports/1783825724.33022.709b07a8__g4_08_native_eventid_bridge/REPORT.md) reported zero exact DAQ↔Geant4 event matches because the original `hibeam` tree did not carry `EVENTNO/EVT/TRIGGER`. That prior negative is preserved, not rediscovered.

## Mechanism

`align_geant4_truth()` independently samples source Geant4 records with `rng.choice`; `attach_native_keys()` separately selects the first N *authentic but independently sourced* selected DAQ keys per run. It stamps those keys, a computed `digitizer_seed`, and a `native_row` onto the hybrid synthetic records. `write_keyed_digitized_root()` serialises those fields, then `exact_native_join()` reads the newly generated ROOT and checks one-to-one equality against the writer's own input. This is a useful synthetic-key serialisation test, but it does not prove the chosen Geant4 particle originated from or matches the keyed DAQ event. The historical [report](https://github.com/SzeChunYiu/ccb-testbeam/blob/a61427813344e29047ca9eb9b764182eb29e4c83/reports/1783883140.39222.3c4045b1__g4_08_keyed_digitized_geant4_native_join/REPORT.md) already cautions that the upstream generator did not know DAQ keys; do not remove that scoped disclosure.

## Executed controls on *actual stored generated-table records*

Authenticated GitHub full-CSV read and source-expression replay in one JS isolate, all 1,056 rows from 13 source runs. Positive: 1,056/1,056 deterministic source seed equations match, six generated-key tuple uniqueness holds, and the recorded `native_row == native_row_digitized` checks pass. Hostile: cyclically reassign all Geant4-origin truth attributes **within** each run and recompute the derived digitizer seed and output-key image. It changes **1,056/1,056** G4 entries and energies, including **542/1,056** PID labels, while the same 1:1 self-write/self-read test still passes. Negative: if the output-key image remains frozen while caller assignments change, **2,112** key component comparisons differ and the projected join fails. All values and exact paths/identities are in `EVIDENCE.json`.

This verifies insufficiency of synthetic post-stamping key closure for upstream physical pairing; it is **not** a measured experimental error rate, nor was the archived ROOT binary rewritten or independently reopened as a ROOT tree.

## Executed historical checkout challenge

`manifest.json` in the historical G4-08 report advertises `git_commit=9ff7f2b61e437cff0e95acb7ee2ac1665fe8d0dd`, but the producer at that exact checkout is **different**, Git blob `d256c35dc058572ebb90b070f91e35b485a46d65` (24,899 characters), with **none** of the four keyed-digitizer functions. Those first appear in source blob `dfb35f...` (34,367 chars), merged at commit [6a88ae79](https://github.com/SzeChunYiu/ccb-testbeam/commit/6a88ae79dadca97a943df4ec54f53150bfff0ffd). Thus the manifest's recorded committed checkout alone cannot reproduce this generated output. The script might have been executed **uncommitted** before being committed; do **not** infer the runtime or stored products were fabricated. Its actual executed worktree/script hash is unbound to that stamped ref.

## Boundaries, repair and data custody

No original 144-word beam ROOT, 66.6 MB diagnostic Geant4 ROOT, deployed Sci_bar/T1/T2 writer, real DAQ clocks, Geant4 rerun or untouched hardware calibration was obtained. The existing generated ROOT is not a replacement for those. Source-only and generated-sample tests cannot authorise measured timing, PID, energy, detector transfer, figure genealogy, nuisance covariance or paper release.

Owner should distinguish `SYNTHETIC_PAIRING_WITH_DAQ_KEY_RELABEL` from true `PHYSICALLY_PAIRED` or independent ensembles, require an upstream authenticated parent-key relationship for paired designs, and use distributional inference for independent ensembles. Bind the **executed** source/worktree bytes, original raw/MC data checksums, physics/calibration/configuration/seed/selection and figure ancestry; owner-integrate hostile key-permutation and frozen-output cases; rerun genuinely authorized data/MC with correlated nuisances and external human review. Preserve #781's valid roundtrip software check and the original historical results unchanged. Protect SiPM #977/merged PR1294 and canonical PR1595.

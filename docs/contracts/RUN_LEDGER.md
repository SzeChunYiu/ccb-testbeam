# Run ledger (`ccb-run-ledger/1`) — issue #962

**Canonical Sample II calibration run: 64** (not 61).

## Evidence

- Newer report / `docs/02_data_and_runs.md` and
  `configs/data_side_s00_rebuild.yaml` define `sample_ii_calib: [64]` with
  run 61 in analysis.
- Older 54-page B-stack timing note used run 61; that role is recorded as
  `SUPERSEDED` on run 61 in `configs/daq/run_ledger.yaml`.

## Raw-product binding

The ledger's `raw_products:` block binds every located raw ROOT product
(A-stack `hrda_*`, B-stack `hrdb_*`) for the run universe 31..65 to its
path, byte size and SHA-256, transcribed from the committed s23 hash sweep
(`reports/1781181864.166962.68322ee6__s23_geant4_data_consistency_review/raw_root_file_hashes.csv`).
Run 38 has no located raw product (exclusion reason
`absent_A_stack_or_missing_file`); run 61's products are bound even though
its calibration role is SUPERSEDED.
`tests/test_962_run_role_conformance.py` re-verifies every ledger entry
against the committed CSV, so the binding cannot drift silently.

## Enforcement

`ccb_mc_validation.daq.run_ledger` loads the YAML ledger, rejects
calibration∩validation overlaps, asserts the Sample II calibration decision,
and — via `assert_configs_consistent_with_ledger` — sweeps every
`configs/**/*.{json,yaml,yml}` run-role block (403 blocks at introduction)
against the ledger:

1. any `sample_ii_calib` run list must equal the ledger's canonical `[64]`;
2. role lists must stay inside the ledger's canonical group for that sample
   and role — excluded runs (38, 43) cannot re-enter analysis;
3. within one block (one declared grouping context = one fitted object) no
   run may be both calibration and held-out/validation. Cross-object reuse
   in separate blocks of one file — a template-calibration population versus
   an ML train/test split — is allowed, matching the issue's "for the same
   fitted object" wording.

Expected-count blocks that reuse the role key names with pulse/event totals
(e.g. `sample_ii_calib: [14630]`) are not run lists and are ignored by
construction (values must lie in the ledger's run universe).

# Latest Handoff

## Session

- **UTC:** 2026-07-21T12:00Z
- **Task:** `AUD-G4-001` with partial progress on `AUD-G4-003`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Status:** PARTIAL — static RNG/thread-provenance fixes, event-tree validation, and photon-tree validation are pushed. Python execution, Geant4 compilation, real ROOT validation, multiseed analysis, and optical-yield regeneration remain mandatory.

## Area reviewed

Single-stave Geant4 optical-output integrity and multithread reproducibility:

- `geant4/single_stave/src/RunAction.cc`
- `scripts/compare_single_stave_mt_reproducibility.py`
- `tests/test_compare_single_stave_mt_reproducibility.py`
- `scripts/compare_single_stave_photon_trees.py`
- `tests/test_compare_single_stave_photon_trees.py`
- PR #868 and the previous coordination handoff

## New finding: photon rows cannot be compared by file position

The `photons` tree records `event`, `sensor`, `wavelength_nm`, `time_ns`, `path_len_mm`, and `detected`, but no persistent photon identifier. In multithreaded output, ROOT row order is not a physical invariant. A direct row-by-row comparison would therefore create false failures when identical photon records are written in a different order.

The scientifically defensible exact comparison is a multiset comparison: validate each row, canonicalize both trees lexicographically by every stored photon field, then compare the complete canonicalized records. This tests whether the recorded photon populations are identical without assigning unsupported photon identities.

## New changes pushed

### `scripts/compare_single_stave_photon_trees.py`

The new dedicated validator:

1. Requires the complete photon schema:
   - `event`
   - `sensor`
   - `wavelength_nm`
   - `time_ns`
   - `path_len_mm`
   - `detected`
2. Requires all branches to be one-dimensional and have consistent row counts.
3. Validates event foreign keys are integers in `[0, n_events)`.
4. Validates sensor IDs are integers in `{0,1,2,3}`.
5. Validates detection flags are integers in `{0,1}`.
6. Requires finite positive wavelengths.
7. Requires finite nonnegative arrival times and path lengths.
8. Ignores original ROOT row order and canonicalizes by all six stored fields.
9. Performs an exact field-by-field multiset comparison.
10. Reports per-event photon-row counts, zero-photon events, total and detected rows, detected fraction, and per-sensor row/detection counts.
11. Writes a machine-readable JSON summary.
12. Writes a multipage PDF with:
    - acceptance summary;
    - photon rows per event;
    - candidate-minus-reference rows per event;
    - wavelength distribution;
    - arrival-time distribution;
    - path-length distribution.
13. Returns nonzero status on schema, domain, foreign-key, row-count, or exact-record mismatch.

### `tests/test_compare_single_stave_photon_trees.py`

Synthetic uproot tests cover:

- identical photon multisets stored in different row order;
- invalid event foreign keys;
- invalid sensor IDs;
- invalid detection flags;
- nonpositive wavelengths;
- negative times;
- nonfinite path lengths;
- one changed photon value;
- one missing photon row;
- JSON and nonempty PDF output on the passing path.

## Evidence classification

- **Observed repository fact:** the photon tree has no persistent photon ID and records only the six fields listed above.
- **Methodological conclusion:** file row order cannot serve as photon identity in MT output; multiset comparison is required.
- **Static implementation evidence:** the new script canonicalizes using every recorded field and independently validates physical and referential domains.
- **Still unverified:** whether real one-thread and four-thread photon trees are exactly identical after the RNG fix; whether the approximately 178 PE/event result is stable.

## Commits added in this session

- `ccfe73916096dfa15135845a8ea068d0b651d682` — `feat(g4): add photon-tree MT reproducibility validator`
- `9e0d892e36073a5298a06d6cbfe0b7c9a7d62104` — `test(g4): cover photon-tree integrity validator`

The coordination-file update commits follow these code/test commits on the same branch.

## Static review performed

- Confirmed the canonical ordering includes every stored photon field.
- Confirmed event foreign keys use metadata `n_events` as the allowed domain.
- Confirmed comparison remains exact; no numerical tolerance is silently introduced.
- Confirmed empty or zero-photon events remain visible through the per-event aggregate.
- Confirmed sensor and detected categorical domains are checked before aggregation.
- Confirmed no raw data or generated binaries were committed.

## Checks not executed

This connector session did not expose a checked-out Python/ROOT/Geant4 environment or generated ROOT files. It therefore does **not** claim:

- pytest passed;
- ruff passed;
- the photon validator executed successfully;
- Geant4 compilation succeeded;
- one-thread/four-thread photon multisets match;
- photon foreign-key integrity passes on real output;
- approximately 178 PE/event was reproduced.

## Required runtime commands

```bash
python -m pytest \
  tests/test_compare_single_stave_mt_reproducibility.py \
  tests/test_compare_single_stave_photon_trees.py -q

ruff check \
  scripts/compare_single_stave_mt_reproducibility.py \
  scripts/compare_single_stave_photon_trees.py \
  tests/test_compare_single_stave_mt_reproducibility.py \
  tests/test_compare_single_stave_photon_trees.py

python scripts/compare_single_stave_photon_trees.py \
  --reference mt_rng_t1.root \
  --candidate mt_rng_t4.root \
  --reference-meta mt_rng_t1.root.meta.json \
  --candidate-meta mt_rng_t4.root.meta.json \
  --output-json results/g4_mt_photons_t1_vs_t4.json \
  --output-pdf docs/figures/g4_mt_photons_t1_vs_t4.pdf
```

## Photon-tree acceptance criteria

- Both trees contain all six required branches with equal branch lengths.
- Every photon event foreign key is in `[0, n_events)`.
- Sensor IDs are limited to `0..3` and detection flags to `0/1`.
- Wavelengths are finite and positive; times and paths are finite and nonnegative.
- Total photon rows match.
- After canonical multiset sorting, every recorded field matches exactly.
- JSON and PDF artifacts are generated from declared inputs.
- Any mismatch is investigated before relaxing the criterion; there is currently no tolerance option.

## Remaining audit work

1. Execute Python tests and lint.
2. Build with supported Geant4 11.2.2.
3. Generate same-seed one-thread and four-thread optical ROOT outputs.
4. Run both event-tree and photon-tree validators.
5. Confirm the forced-thread provenance case.
6. Add a multiseed ensemble validator and uncertainty plots.
7. Locate the exact provenance of the approximately 178 PE/event result, rerun it, quantify uncertainty, and update affected claims.
8. Populate the remaining required `chatgpt_todo` ledgers and broaden review beyond the current Geant4 study.

## Acceptance decision

Keep PR #868 in draft. Do not merge until the Python checks pass, supported Geant4 compilation succeeds, real event and photon outputs pass integrity/reproducibility checks, forced-thread provenance is verified, and the optical-yield claim is regenerated with uncertainty.

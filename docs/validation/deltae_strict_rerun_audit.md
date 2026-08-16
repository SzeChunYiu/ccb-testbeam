# A-002 ΔE-E strict rerun provenance audit

## Scope and evidence class

This audit reviews the publication and provenance path around `scripts/single_stave/deltaE_E_data_bridge.py`. It does not reclassify the bridge's already-tested composite-key or signed-polarity transformation, and it does not use real A-002 detector data. The executable validation is a synthetic software/provenance study.

- Task: `AUD-DELTAE-001`
- Session stamp: `2026-07-25T042815Z`
- Initial remote `main`: `86c6e086d3716ab3ac10481fae92f1a316adf2d3`
- Existing bridge blob: `7f50ce667a6cde07e94717d0187831da4d8459ac`
- Existing composite-key/polarity test blob: `3b59a793f5d67e6a0d3c7117c42ec41ad7b84a90`
- New policy: `DELTAE_BRIDGE_CONTENT_ADDRESSED_TRANSACTIONAL_RERUN`
- Runner version: `1.0.0`

## Confirmed engineering defect

The existing bridge correctly excludes `eventno` from the physical event key, requires explicit amplitude semantics, rejects polarity violations, and verifies that stopping-bin counts sum to the physical-event count. Its command-line entry point nevertheless cannot satisfy the repository's required immutable real-rerun contract:

1. `SRC` and `OUT` are hard-coded environment paths.
2. `pd.read_csv(SRC)` reads by pathname without requiring or recording an expected exact input SHA-256.
3. The input is not checked for replacement during processing.
4. `result.json`, the event CSV, and the plot are written directly rather than as one protected transactional bundle.
5. Existing output replacement is implicit rather than explicitly authorized.
6. The result omits the exact repository commit, producer byte identities, generation command, runtime versions, and output hashes.

These omissions do not prove that the historical numbers are wrong. They prevent a later reader from establishing that a reported JSON, table, and plot were generated together from the declared immutable input and exact code.

## Correction delivered

Added `scripts/single_stave/deltaE_E_data_bridge_strict.py` and `scripts/single_stave/DELTAE_STRICT_RERUN.md`.

The runner:

- requires an expected input SHA-256 and parses the exact captured bytes;
- requires the same input byte count and SHA-256 after the bridge call;
- requires a clean tracked checkout at an explicitly expected commit;
- records runner and bridge script hashes, command, Python/platform and package versions;
- requires explicit source identity, amplitude column, convention, and conditional polarity;
- delegates the scientific event construction to the existing bridge;
- independently checks required columns, unique `(source_file_id, run, evt)` rows, finite ADC quantities, source identity, event count, and stopping-distribution total;
- repeats provenance in every event-CSV row and in visible plus embedded SVG metadata;
- blocks output directories containing an input or code file;
- requires `--overwrite` for an existing bundle;
- stages JSON, CSV, and SVG in a sibling directory, then renames the directory into place;
- restores the previous complete bundle after an injected in-process publication failure;
- labels successful software output `BLOCKED_PENDING_A002_EVIDENCE_AND_CLOSURE` rather than presenting it as an accepted detector result.

`result.json` is the final bundle commit marker. It records the expected CSV and SVG byte counts and SHA-256 values before publication; the runner then re-reads all three published files and verifies their identities.

## Validation

Executed:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E_data_bridge_strict.py \
  tests/test_deltae_data_bridge_strict.py

PYTHONPATH=. pytest -q tests/test_deltae_data_bridge_strict.py

9 passed in 1.79s
```

The focused regressions cover:

- a valid content-addressed and reconstructable two-event bundle;
- expected-input hash mismatch;
- expected-repository-commit mismatch;
- input/output containment alias;
- preservation when overwrite is not authorized;
- restoration of all previous bundle files after injected publication failure;
- detection of input replacement during processing;
- duplicate physical composite keys;
- nonfinite or nonnumeric ADC output.

The synthetic fixture produced two event rows, two unique composite keys, and a stopping-distribution total of two. Its 109-byte input had SHA-256 `84deb3ae1b0a57a7e3026cb8eb6f34492dea4db1202789a110e9e49fe5f48ae7`. This is deliberately small software evidence, not a detector sample.

Machine-readable evidence is in `docs/validation/deltae_strict_rerun_validation.json`. The SVG in `docs/validation/deltae_strict_rerun.svg` parsed as XML and visibly states the synthetic/software boundary. Changed Python lines were at most 97 characters.

## Method comparison

The existing bridge functions remain preferable for unit-level scientific transformation tests because they are simple DataFrame operations. The new wrapper is preferable for production publication because it adds immutable byte identity and a complete-bundle transaction without duplicating the transformation. Replacing the bridge logic itself with a new implementation would have increased method-divergence risk without adding scientific value.

The staged-directory rename is stronger than three independent atomic file replacements: readers see either the previous complete directory or the new complete directory during the in-process replacement sequence. The rollback contract is tested. Host crash behavior still depends on filesystem rename and durability semantics, so the JSON remains an explicit commit marker and every file has an independently checkable digest.

## Scientific boundary and remaining work

No exact A-002 pulse-table bytes or independently reviewable amplitude-convention/polarity evidence were available. Therefore this run did not:

- authorize `amplitude_adc` as absolute or net;
- determine positive- or negative-going pulse polarity;
- execute the real bridge;
- publish a corrected stopping distribution;
- publish a real ΔE–E plot;
- estimate threshold, pedestal, calibration, selection, or detector systematics;
- establish particle-identification or detector-performance closure.

`BLK-AMP-001`, `AUD-AMP-009`, `AUD-AMP-010`, and `AUD-DELTAE-002` remain operative. `AUD-DELTAE-001` is advanced but remains `PARTIAL` until the exact content-addressed production rerun and scientific closure are complete.

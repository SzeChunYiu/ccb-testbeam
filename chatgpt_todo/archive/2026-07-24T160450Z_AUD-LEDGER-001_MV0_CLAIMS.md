# Immutable session record — AUD-LEDGER-001 MV0 claim rows

## Identity

- UTC stamp: `2026-07-24T160450Z`
- Task: `AUD-LEDGER-001`
- Unit: source-backed reconstruction of `CL-013` and `CL-014`
- First observed remote main: `ec4ab24ffdbcdeeae76c1e8be615cc3a6e4324d4`
- Concurrent main incorporated before writes: `9e1ccc57fee369293be0f090141831e0f65216b8`
- Delivery path: direct sequential commits to `main`
- Acceptance: this two-row unit is `VALIDATED`; ledger-wide audit remains `PARTIAL`

## Repository and concurrency review

Authenticated GitHub reads inspected repository metadata, recent main history, the
mandatory `chatgpt_todo/` files, the claim ledger and cumulative schema evidence, the
MV0 report, calibration JSON, tracked producer, source-introducing commit, current CI
status, and PR #868. The G4-07 commit at `9e1ccc57...` appeared after the first head
observation and was preserved as the base of this sequence. No force push or history
rewrite was used.

PR #868 is closed, unmerged, and non-mergeable. It was not modified or merged. The
connector returned successful direct-main commit SHAs rather than conventional textual
`git push` stdout.

## Confirmed defects

The ledger has a 43-field header, but the former MV0 records were malformed:

- `CL-013`: 38 columns;
- `CL-014`: 37 columns.

The fail-closed schema policy therefore withheld their late fields. The former rows
also cited `scripts/mv0_calibration.py` and a non-existent `results.json`, while the
tracked report points to `scripts/mv0_calibrate_from_data.py` and the committed result
is `calibration.json`. `CL-013` split a source-described 30% heuristic systematic range
into unsupported statistical and systematic components and supplied interval fields
without a source confidence-interval method. `CL-014` contained shifted count and
p-value-like fields that were not supported by the source.

## Exact source evidence

Source commit:

`3c5ff5cf587c8ca9cefda20cb220ba29effd2170`

Tracked report:

- path: `reports/mv0_calibration_1782677847/REPORT.md`;
- Git blob before this run: `34ad9f8b477390adb13f7781fbd31fb5a8f1d1d6`;
- SHA-256: `dc5b74056f7cac76e9c279e8e81c181453c854fd051dd82856c645c52a48b518`;
- bytes: `3733`.

Tracked calibration result:

- path: `reports/mv0_calibration_1782677847/calibration.json`;
- Git blob: `74e490753d3e821b0a1353490764a5ede0e9bf75`;
- SHA-256: `78a905473db33311b6ccfc7ef440fc076b5d210de07d09e1f868f9fdf05cd18b`;
- bytes: `2644`.

Source-supported values:

- median-matched B2 gain: `92 ADC/MeV`;
- heuristic gain systematic: `30%`, rounded to `28 ADC/MeV`;
- B2 data pulses: `579424`;
- MC tracks with B2 hit: `321130`;
- KS statistic at gain 92: `0.1577`;
- KS scan optimum: gain `60 ADC/MeV`, D = `0.1188`;
- previous v1 gain: `110 ADC/MeV`.

The report supplies no statistical gain uncertainty and no confidence interval. The KS
p-value is not reported. The report documents shape, polarity, pile-up, and selection
mismatches, and no content-addressed manifest binds the historical producer and data
bytes.

## Delivered interpretation

`CL-013` is now an exact-width `data_mc_calibration_proxy` claim with status `GATED`.
It records the source-supported 28 ADC/MeV heuristic systematic envelope only; it does
not publish a statistical uncertainty, total uncertainty, or confidence interval. It
supersedes the erroneous v1 value and is blocked by `BLK-MV0-001`.

`CL-014` is now an exact-width `data_mc_calibration_proxy` diagnostic with status
`TENSION`. It records D = 0.1577, the comparator D = 0.1188, and descriptive difference
0.0389. It explicitly records that the p-value was not reported and does not represent
the fixed statistic as a calibrated goodness-of-fit probability.

Corrected ledger snapshot:

- Git blob: `1964fadd5a1078c534cc14bdc30e63a38f1d73c8`;
- bytes: `15274`;
- SHA-256: `30a1f5fd03d82366df3201a9d0d37be54572f13fd6c990d92b6bd5a9feab69a5`.

Cumulative schema state after repair:

- exact-width rows: `14/26`;
- malformed and withheld rows: `12/26`;
- width histogram: `36:1, 37:2, 38:7, 39:2, 43:14`;
- global status remains intentionally `FLAWED` until all rows are reconstructed.

## Files

Added:

- `tools/audit/validate_mv0_claim_rows.py`;
- `tests/test_validate_mv0_claim_rows.py`;
- `docs/validation/mv0_claim_rows_audit.md`;
- `docs/validation/mv0_claim_rows_validation.json`;
- `docs/validation/mv0_claim_rows.svg`.

Updated:

- `docs/claim_ledger.csv`;
- `docs/validation/claim_ledger_schema_audit.md`;
- `docs/validation/claim_ledger_schema_validation.json`;
- `docs/validation/claim_ledger_schema.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`.

## Validation

Executed against exact local reconstructions before publication:

```text
python -m py_compile \
  tools/audit/validate_mv0_claim_rows.py \
  tests/test_validate_mv0_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv0_claim_rows.py -q

5 passed in 0.03s
```

The direct validator returned `VALIDATED` with zero issues. Regressions cover exact
source acceptance, wrong-gain rejection, caveat enforcement, width-mismatch fail-closed
handling, and invalid-UTF-8 input. JSON and SVG parsing passed, source snapshots matched
their Git blobs, and changed Python lines met the 100-character convention.

Not run: full repository pytest, ruff, ROOT processing, historical calibration rerun,
beam-data reprocessing, simulation, repository-wide link checks, or GitHub Actions.
No broader CI success is claimed.

## Direct-main sequence before archive

1. `b4a55d38d35641c1784b71bcdf49a13c1c1ae9c5` — ledger reconstruction
2. `aae50fe46e24f4d0d6bcf7473bac0071c7f97894` — validator
3. `e5268a1fed1d260eb994e50a84f8d841b32e2797` — tests
4. `779ff38d4a6a48a589067f981e2fd243f75e14b9` — validation JSON
5. `dddb270387f7b6125d0df0fa14729901798f4be9` — visual evidence
6. `ff73bfe1ec350508b68bf5fc3e6fd3b9f7ff0073` — audit report
7. `82925c2b79b0cb19767d56cc301b8e89e8e36e71` — cumulative schema audit
8. `9a6dd560e0c1ce8b8a83bcd6d10fbef6e1b5b496` — cumulative schema JSON
9. `62d0b95cb517493e4fd70c8a26e1a6645d283e27` — cumulative schema SVG
10. `484f0616f263636b372a4a075f0e83e33ec65736` — active-task completion

## Scientific boundary and next work

This unit does not establish a precision gain calibration, reproduce the historical
ROOT/data inputs, validate selection transfer, generate an uncertainty interval, or
resolve the data/MC shape mismatch. Resolving `BLK-MV0-001` requires exact producer and
input hashes, a clean-environment rerun, explicit pulse-selection and polarity closure,
preregistered alternative calibration methods, independent validation data, and an
accepted statistical/systematic uncertainty model.

Twelve ledger rows remain malformed. The next unit should reconstruct a source-coherent
pair without interpreting shifted late fields. Aggregate `SESSION_LOG.md`, `BACKLOG.md`,
and `BLOCKERS.md` were not replaced in this connector-only unit because safe updates
require a complete current snapshot and whole-file replacement could erase concurrent
provenance. This immutable record and the latest handoff preserve the complete session;
the exact claim rows carry `BLK-MV0-001`.

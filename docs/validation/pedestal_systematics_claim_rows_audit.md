# Pedestal and systematic-uncertainty claim-row reconstruction audit

## Scope

This unit reconstructs malformed claim-ledger records `CL-025` and `CL-026` as
exact 43-column rows. It does not create a pedestal measurement or a propagated
uncertainty budget. Both claims remain explicitly blocked.

## Repository facts and defect reproduction

The exact pre-change ledger was Git blob
`d33180f144cca10a6e310b3e89b5ab1d065d7e66`, SHA-256
`3a08d0d561de0ad11f2bbbf4a6cc1284af2315e30bbb3ded39be308b6d5125ff`.
Its row widths were:

- `CL-025`: 37 columns;
- `CL-026`: 35 columns.

The canonical ledger schema has 43 columns. The global schema policy therefore
withheld every late field in both rows, including truth type, status, source,
link state, confidence-interval state, blocker, and notes.

## Source evidence

The exact source document is
`docs/SYSTEMATIC_UNCERTAINTIES.md`, Git blob
`54088968264c3b714f03a7305fbf69dcc77b196e`, SHA-256
`2c2c9c44c57cddae3fb956281e70842627140e8b3a1b510c946385e8f4ec7ace`.
It states that no forced-trigger zero-signal events exist in the current dataset
and that a future forced-trigger S16 pedestal sample is required. It also lists
component-level systematic estimates and a simple quadrature summary.

That document is sufficient to support two negative governance claims only:

1. no independent forced-trigger pedestal truth is currently available;
2. a claim-specific, reproducible uncertainty propagation is not complete.

It is not treated as blanket authorization of every numerical statement in the
document. Several of its physics summaries are known to be stale and are
tracked separately.

## Reconstructed records

`CL-025` now records:

- truth type `data_availability`;
- status `BLOCKED` and `allowed_status_validated=NO`;
- source path and source commit;
- `NOT_APPLICABLE_WITH_REASON` for confidence-interval state;
- blocker `BLK-PED-001`;
- no numerical value, uncertainty, count, or interval.

`CL-026` now records:

- truth type `uncertainty_budget_incomplete`;
- status `BLOCKED` and `allowed_status_validated=NO`;
- the same exact source path and source commit;
- `NOT_APPLICABLE_WITH_REASON` for confidence-interval state;
- blocker `BLK-SYST-001`;
- no numerical value, uncertainty, count, or interval.

The corrected ledger has SHA-256
`d7231b66b477fffb3766bab68129ab8e4e56f37d3e84630d89bf5016023dfb79`.
Its cumulative schema state is now 12 exact-width rows and 14 withheld malformed
rows out of 26.

## Validation

Executed:

```text
python -m py_compile \
  tools/audit/validate_pedestal_systematics_claim_rows.py \
  tests/test_validate_pedestal_systematics_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_pedestal_systematics_claim_rows.py -q

7 passed in 0.70s

python tools/audit/validate_pedestal_systematics_claim_rows.py \
  docs/claim_ledger.csv \
  docs/SYSTEMATIC_UNCERTAINTIES.md \
  --output docs/validation/pedestal_systematics_claim_rows_validation.json \
  --svg docs/validation/pedestal_systematics_claim_rows.svg
```

The exact corrected ledger and exact source document returned `VALIDATED` with
zero issues. The JSON parsed, the SVG parsed as XML, and changed Python files
were at most 99 characters per line.

Regression coverage includes exact-width acceptance, 42-column fail-closed
rejection, prevention of numerical publication from a blocked row, missing
source-evidence detection, status mismatch detection, invalid-UTF-8 handling,
and CLI JSON/SVG output.

## Scientific boundary

No forced-trigger run, zero-signal waveform sample, pedestal distribution,
baseline estimator comparison, nuisance parameter model, covariance matrix,
Monte Carlo ensemble, coverage study, or end-to-end uncertainty propagation was
produced. `CL-025` and `CL-026` are valid blocked claims, not validated detector
performance claims.

# Claim-ledger row-width and field-alignment audit

## Scope

This audit checks the exact current `docs/claim_ledger.csv` byte snapshot before any
claim field is interpreted. It is a schema/provenance check, not a reanalysis of beam
data, simulation, detector performance, or uncertainty values.

Policy:

`NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`

## Exact input provenance

- File size: `9337` bytes
- SHA-256: `a760fdd78fd120b098a2342fbf3e8e681141ea08b4f0d42ace01ea5b91f96767`
- Snapshot method: one exact byte read followed by strict UTF-8 and CSV parsing
- Canonical header width: `43` columns
- Data rows: `26`

The Git blob SHA-1 for the published ledger is recorded in the session handoff after
remote publication.

## Cumulative measured state

`CL-001` has now been reconstructed from the S00 report, configuration, script,
count table, manifest, producing commit, generated-data contract, and figure registry.
Together with the previously repaired WIKI-bound rows, the exact-width records are:

- `CL-001`;
- `CL-007`;
- `CL-011`.

The remaining 23 rows contain 35--39 fields:

| Actual columns | Count | Claim IDs |
|---:|---:|---|
| 35 | 1 | `CL-026` |
| 36 | 4 | `CL-012`, `CL-015`, `CL-016`, `CL-021` |
| 37 | 7 | `CL-008`, `CL-009`, `CL-010`, `CL-014`, `CL-023`, `CL-024`, `CL-025` |
| 38 | 8 | `CL-002`, `CL-004`, `CL-005`, `CL-013`, `CL-017`, `CL-018`, `CL-019`, `CL-020` |
| 39 | 3 | `CL-003`, `CL-006`, `CL-022` |
| 43 | 3 | `CL-001`, `CL-007`, `CL-011` |

A width mismatch is not safely equivalent to trailing empty fields. Missing commas
can shift every subsequent value into the wrong header. Late-field interpretation
therefore remains withheld for all 23 malformed records.

## Validator

`tools/audit/validate_claim_ledger_schema.py` version `1.0.0`:

- reads the input bytes once and records byte size and SHA-256;
- requires the exact canonical 43-field header;
- parses CSV with strict syntax handling;
- checks every data-row width before mapping fields;
- detects missing and duplicate claim IDs;
- records row number, claim ID, actual width, and missing/excess field count;
- explicitly records `field_interpretation=WITHHELD` for malformed rows;
- returns `0` for `VALIDATED`, `1` for measured schema flaws, and `2` for
  controlled input/schema/UTF-8 errors;
- writes deterministic JSON and an accessible SVG row-width diagnostic.

## Validation commands and measured result

```text
python tools/audit/validate_claim_ledger_schema.py \
  docs/claim_ledger.csv \
  --output docs/validation/claim_ledger_schema_validation.json \
  --svg docs/validation/claim_ledger_schema.svg

process status: 1
status: FLAWED
data rows: 26
exact-width rows: 3
width-mismatched rows: 23
```

The nonzero status is the required fail-closed result for the still-incomplete ledger.
It is not a validator regression failure.

Additional checks:

- the row-width JSON parsed successfully;
- the row-width SVG parsed as XML;
- focused schema-validator tests remain unchanged and previously passed `9 passed`;
- the new CL-001 source-backed validator passed `5` focused tests.

## Acceptance state and required remediation

`AUD-LEDGER-001` remains `PARTIAL`. Completion requires, for every remaining
mismatched row:

1. inspect the cited report, script, data, configuration, figures, tables, history,
   and any source claim;
2. reconstruct all 43 fields from source-backed semantics, preserving every nonempty
   value and uncertainty caveat;
3. record unresolved values explicitly rather than shifting or inventing fields;
4. require this validator to return `VALIDATED` with 26/26 exact rows;
5. rerun WIKI, claim, and broken-link checks before interpreting late ledger fields.

No late field from a malformed row should be promoted based on ordinary positional
CSV parsing.

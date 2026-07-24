# Claim-ledger row-width and field-alignment audit

## Scope

This audit checks the exact current `docs/claim_ledger.csv` byte snapshot before
any claim field is interpreted. It is a schema/provenance check, not a
reanalysis of beam data, simulation, detector performance, or uncertainty
values.

Policy:

`NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`

## Exact input provenance

- Corrected committed size: `13413` bytes
- Corrected Git blob: `d33180f144cca10a6e310b3e89b5ab1d065d7e66`
- Corrected commit: `bf584eec7d64c6f78cd782b7b1ff84387d0f2bfe`
- Pre-change SHA-256:
  `9a099f76609c51b7400c8615a46c5e873058ac00e0fa9e3a0e2877a1d5e5db5c`
- Corrected candidate SHA-256:
  `3a08d0d561de0ad11f2bbbf4a6cc1284af2315e30bbb3ded39be308b6d5125ff`
- Snapshot method: one exact byte read followed by strict UTF-8 and CSV parsing
- Canonical header width: `43` columns
- Data rows: `26`

## Cumulative measured state

Source-backed exact-width records are:

- `CL-001`;
- `CL-007`;
- `CL-010`;
- `CL-011`;
- `CL-012`;
- `CL-015`;
- `CL-016`;
- `CL-022`;
- `CL-023`;
- `CL-024`.

The remaining 16 rows contain 35--39 fields:

| Actual columns | Count | Claim IDs |
|---:|---:|---|
| 35 | 1 | `CL-026` |
| 36 | 1 | `CL-021` |
| 37 | 4 | `CL-008`, `CL-009`, `CL-014`, `CL-025` |
| 38 | 8 | `CL-002`, `CL-004`, `CL-005`, `CL-013`, `CL-017`, `CL-018`, `CL-019`, `CL-020` |
| 39 | 2 | `CL-003`, `CL-006` |
| 43 | 10 | `CL-001`, `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, `CL-016`, `CL-022`, `CL-023`, `CL-024` |

A width mismatch is not safely equivalent to trailing empty fields. Missing
commas can shift every subsequent value into the wrong header. Late-field
interpretation therefore remains withheld for all malformed records.

## Latest reconstruction unit

`CL-023` and `CL-024` were reconstructed from the exact tracked MV6 producer,
summary JSON, historical report, and producing commit. The superseded
three-/eight-component values `0.89` and `0.997` were replaced by source-backed
synthetic-waveform values `0.7254602133437841` and `0.821883926913117`.
Both rows now explicitly carry the `synthetic_waveform_mc` truth type and
`TRUTH_LEVEL_MC_ONLY` status.

## Measured result

```text
process status: 1
status: FLAWED
rows: 26
exact-width rows: 10
width-mismatched rows: 16
width histogram: 35:1, 36:1, 37:4, 38:8, 39:2, 43:10
```

The nonzero status is the required fail-closed result for the still-incomplete
ledger. It is not a validator regression failure.

## Acceptance state

`AUD-LEDGER-001` remains `PARTIAL`. Completion requires source-backed
reconstruction of all 16 remaining mismatched rows, 26/26 exact-width
validation, and rerunning WIKI, claim, source-link, figure, and table checks
before interpreting late fields.

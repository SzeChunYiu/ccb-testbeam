# Claim-ledger row-width and field-alignment audit

## Scope

This audit checks the exact current `docs/claim_ledger.csv` byte snapshot before any claim field is interpreted. It is a schema/provenance check, not a reanalysis of beam data, simulation, detector performance, or uncertainty values.

Policy:

`NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`

## Exact input provenance

- File size: `10097` bytes
- SHA-256: `809e03162f04f94235fe36612c0ec8a3ccf4ae054a5d87341bdd5e26ad3c57d6`
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

The remaining 21 rows contain 35--39 fields:

| Actual columns | Count | Claim IDs |
|---:|---:|---|
| 35 | 1 | `CL-026` |
| 36 | 3 | `CL-015`, `CL-016`, `CL-021` |
| 37 | 6 | `CL-008`, `CL-009`, `CL-014`, `CL-023`, `CL-024`, `CL-025` |
| 38 | 8 | `CL-002`, `CL-004`, `CL-005`, `CL-013`, `CL-017`, `CL-018`, `CL-019`, `CL-020` |
| 39 | 3 | `CL-003`, `CL-006`, `CL-022` |
| 43 | 5 | `CL-001`, `CL-007`, `CL-010`, `CL-011`, `CL-012` |

A width mismatch is not safely equivalent to trailing empty fields. Missing commas can shift every subsequent value into the wrong header. Late-field interpretation therefore remains withheld for all malformed records.

## Latest reconstruction unit

`CL-010` and `CL-012` were reconstructed from the MV5 report, summary JSON, script, academic chapter, producing commit, and tracked figure. The source chain does not support an accepted canonical Rmax: `3.0448717948717947 MHz` is the duty-scaled reciprocal, the chapter derives `3.20 MHz` before substituting `3.05 MHz`, and the recovery-ceiling crossing is null. The canonical rows now block/supersede the headline pending `S-STAT-003`.

## Measured result

```text
process status: 1
status: FLAWED
data rows: 26
exact-width rows: 5
width-mismatched rows: 21
```

The nonzero status is the required fail-closed result for the still-incomplete ledger. It is not a validator regression failure.

## Acceptance state

`AUD-LEDGER-001` remains `PARTIAL`. Completion requires source-backed reconstruction of all 21 remaining mismatched rows, 26/26 exact-width validation, and rerunning WIKI, claim, source-link, figure, and table checks before interpreting late fields.

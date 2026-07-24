# Claim-ledger row-width and field-alignment audit

## Scope

This audit checks the exact current `docs/claim_ledger.csv` byte snapshot before any
claim field is interpreted. It is a schema/provenance check, not a reanalysis of beam
data, simulation, detector performance, or uncertainty values.

Policy:

`NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`

## Exact input provenance

- Git blob SHA-1: `0c7ea56d00ed44bd976e4ba8e05a84cb4c6eb63e`
- File size: `8971` bytes
- SHA-256: `3ef63ee3836ce67c8b9f4538f754737cdcf53bc67d9a746210a0ea9e81e41d2d`
- Snapshot method: one exact byte read followed by strict UTF-8 and CSV parsing
- Canonical header width: `43` columns
- Data rows: `26`

The local reconstruction's Git blob hash matched the authenticated GitHub contents
blob exactly before validation.

## Confirmed defect

Only `CL-007` and `CL-011` have the canonical 43-column width. The remaining 24
rows contain 35--40 fields:

| Actual columns | Count | Claim IDs |
|---:|---:|---|
| 35 | 1 | `CL-026` |
| 36 | 4 | `CL-012`, `CL-015`, `CL-016`, `CL-021` |
| 37 | 7 | `CL-008`, `CL-009`, `CL-010`, `CL-014`, `CL-023`, `CL-024`, `CL-025` |
| 38 | 8 | `CL-002`, `CL-004`, `CL-005`, `CL-013`, `CL-017`, `CL-018`, `CL-019`, `CL-020` |
| 39 | 3 | `CL-003`, `CL-006`, `CL-022` |
| 40 | 1 | `CL-001` |
| 43 | 2 | `CL-007`, `CL-011` |

A width mismatch is not safely equivalent to trailing empty fields. Missing commas
can shift every subsequent value into the wrong header. On the exact current bytes,
Python's ordinary `csv.DictReader` maps examples as follows:

- `CL-001`: `status` becomes `data/pulse_table.parquet`, and `ci_status` becomes
  `Exact reproduction count`.
- `CL-002`: `truth_type` becomes the results JSON path, `status` becomes the config
  path, and `source_report` becomes `FIG-TIM-001`.
- `CL-026`: `source_report` becomes `NOT_APPLICABLE_WITH_REASON`.

Those mappings are parser artifacts, not repository-supported claim semantics.
Therefore, late fields from a width-mismatched row must be treated as unresolved
until the row is reconstructed from source evidence.

## Added validator

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

The SVG uses text labels and hatching in addition to fill differences. It states that
physics values are not interpreted for malformed rows.

## Validation commands and measured result

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_schema.py \
  tests/test_validate_claim_ledger_schema.py

python -m pytest tests/test_validate_claim_ledger_schema.py -q

9 passed in 0.04s

python tools/audit/validate_claim_ledger_schema.py \
  docs/claim_ledger.csv \
  --output docs/validation/claim_ledger_schema_validation.json \
  --svg docs/validation/claim_ledger_schema.svg

process status: 1
status: FLAWED
data rows: 26
exact-width rows: 2
width-mismatched rows: 24
```

Additional checks:

- validation JSON parsed successfully;
- SVG parsed as XML;
- maximum validator line length: `91` characters;
- maximum test line length: `90` characters;
- invalid UTF-8, malformed CSV, noncanonical headers, duplicate IDs, middle-field
  shifts, short rows, JSON output, and accessible SVG output are covered.

Exact source and evidence blob IDs are recorded in the session handoff after remote
publication. The machine-readable JSON is the authoritative row-by-row inventory.

## Acceptance state and required remediation

This unit validates the defect and fail-closed schema gate. It does not guess where
missing fields belong and does not rewrite the 24 malformed rows.

`AUD-LEDGER-001` remains `PARTIAL` / blocked. Completion requires, for every
mismatched row:

1. inspect the cited report, script, data, configuration, figures, tables, history,
   and any source claim;
2. reconstruct all 43 fields from source-backed semantics, preserving every nonempty
   value and uncertainty caveat;
3. record unresolved values explicitly rather than shifting or inventing fields;
4. require this validator to return `VALIDATED` with 26/26 exact rows;
5. rerun WIKI, claim, and broken-link checks before interpreting late ledger fields.

No scientific claim status, truth type, source path, CI state, blocker, supersession,
or note from a malformed row should be promoted based on the current positional CSV
mapping.

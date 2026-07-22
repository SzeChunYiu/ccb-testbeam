# AUD-AMP-001 — Nonnumeric amplitude gate

- **UTC:** 2026-07-22T14:07:00Z
- **Initial remote main:** `1030da2a132670921de5bf5715c594f587ab12b7`
- **Task:** AUD-AMP-001
- **Scope:** `tools/audit/amplitude_convention_audit.py` and focused regression tests.

## Confirmed defect

The auditor counted `nonnumeric_amplitude_rows` after `pandas.to_numeric(..., errors="coerce")`, but neither emitted a warning nor failed the aggregate acceptance gate. A table containing valid ADC values mixed with malformed strings could therefore be classified from the surviving subset and return success. This differed from the already non-accepting treatment of nonfinite numeric values.

## Correction

Version 2.3.0 now:

- emits `NONNUMERIC_AMPLITUDE_VALUES_EXCLUDED` per affected table;
- reports aggregate `n_nonnumeric_tables`;
- includes that count in console output;
- returns nonzero when any classified table contains nonnumeric amplitude entries;
- rejects an all-nonnumeric amplitude column because it has no finite numeric values;
- renames the JSON rule flag to `finite_numeric_values_only`.

## Validation

Executed exact temporary copies:

```text
python -m py_compile /tmp/ccb_audit/tools/audit/amplitude_convention_audit.py /tmp/ccb_audit/tests/test_amplitude_convention_audit.py
python -m pytest /tmp/ccb_audit/tests/test_amplitude_convention_audit.py -q
13 passed in 0.21s
```

New regressions cover mixed numeric/malformed amplitudes and all-nonnumeric rejection. Existing full-table, prefix, ambiguity, provenance, nonfinite, baseline, skip, parse-error, and threshold tests remain passing.

## Commits

- `e494a436fc316467067dac97899abd7d7e456221` — `fix(audit): fail malformed amplitude-value gates`
- `83d92e291b5e3b23e9daaf3ff268e92e6fa07487` — `test(audit): cover malformed amplitude-value gates`

## Evidence boundary

No real pulse tables were available. The prior corpus and exact A-002 source table were not rerun. No scientific counts, fractions, CSV, figure, or convention claim changed.

## Next action

Run version 2.3.0 over the exact A-002 source table and prior corpus without `--max-rows`; review all errors, ambiguous classifications, nonfinite warnings, and nonnumeric warnings before regenerating quarantined A-002 outputs.

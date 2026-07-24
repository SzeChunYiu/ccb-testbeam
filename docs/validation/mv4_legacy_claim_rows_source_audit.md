# Legacy MV4 timing claim-row remediation

## Scope

This validation closes the exact-width and source-binding defect for canonical
claim rows `CL-002` through `CL-009`. It does not regenerate the historical ROOT
analysis or validate detector timing performance.

Policy:

`LEGACY_MV4_TIMING_REQUIRES_STRICT_INPUTS_AND_SOURCE_BOUND_CLAIMS`

## Exact source review

The tracked legacy artifacts contain only global toy-digitizer outputs:

- report: `reports/mv4_timing_1782678162/REPORT.md`;
- summary: `reports/mv4_timing_1782678162/mv4_summary.json`;
- historical source commit: `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`;
- current fail-closed contract: `scripts/MV4_TIMING_README.md`.

The report and summary contain no B6-specific `0.68 ns` or `0.75 ns` result, no
combined B4+B6+B8 `0.54 ns` or `0.56 ns` result, and no B4-B6 covariance
`-0.127 ns^2`. Those five former ledger values are now blank and `BLOCKED` by
`BLK-MV4-LEGACY-001`.

The two source-backed pulls are retained only as non-authorizing toy diagnostics:

| Claim | Fixed source value | Inputs and limitation | State |
|---|---:|---|---|
| `CL-007` | `-1.054403396247793 sigma` | MC sigma68 `1.744319343085384 ns`, i.i.d. track-bootstrap SE `0.006755405549476786 ns`, hard-coded data anchor `1.85 ns`, assumed data uncertainty `0.10 ns` | `GATED` |
| `CL-008` | `2.680528799917713 sigma` | corrected held-out MC sigma68 `1.7696154242198858 ns`, i.i.d. track-bootstrap SE `0.010813166729502352 ns`, hard-coded data anchor `1.50 ns`, assumed data uncertainty `0.10 ns` | `GATED` |

`CL-009` now identifies the actual method: CFD20 plus an analytic
`A+B/sqrt(amplitude)` correction. The source contains no ML model; the
qualitative source verdict is `REVIEW`.

## Claim-ledger result

- exact ledger bytes: `21486`;
- ledger SHA-256: `e7e560a66df43a9cacdf5041361aaffa0995927144adae3701b5c60e0433c26b`;
- canonical fields: `43`;
- exact-width claim rows: `26/26`;
- malformed rows: `0/26`;
- MV4 source-audit findings: `0`;
- MV4 source-audit status: `VALIDATED`;
- cumulative schema status: `VALIDATED`.

The ledger now permits field interpretation for every current row. This is a
schema and provenance result; it does not upgrade any blocked or gated claim.

## Reproduction

```bash
python -m py_compile \
  tools/audit/audit_mv4_legacy_claim_rows.py \
  tests/test_audit_mv4_legacy_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_mv4_legacy_claim_rows.py -q

PYTHONPATH=. python tools/audit/audit_mv4_legacy_claim_rows.py \
  --ledger docs/claim_ledger.csv \
  --report reports/mv4_timing_1782678162/REPORT.md \
  --summary reports/mv4_timing_1782678162/mv4_summary.json \
  --contract scripts/MV4_TIMING_README.md \
  --output-json docs/validation/mv4_legacy_claim_rows_audit_validation.json \
  --output-svg docs/validation/mv4_legacy_claim_rows_audit.svg

PYTHONPATH=. python tools/audit/validate_claim_ledger_schema.py \
  docs/claim_ledger.csv \
  --output docs/validation/claim_ledger_schema_validation.json \
  --svg docs/validation/claim_ledger_schema.svg
```

Observed focused result:

```text
7 passed in 0.03s
MV4 source audit: VALIDATED, 0 findings
claim-ledger schema: VALIDATED, 26/26 exact-width rows
```

## Scientific boundary

No per-stave timing resolution, combined-stave resolution, covariance matrix,
measured data-anchor uncertainty, ROOT rerun, run/block bootstrap, calibration
closure, or detector-performance result was produced. Resolving
`BLK-MV4-LEGACY-001` requires a strict source-bound rerun with current
calibration bytes, measured anchors and their uncertainty, run/block validation,
and reproducible per-stave/covariance outputs.

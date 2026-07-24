# Legacy MV4 timing claim source audit

## Scope and exact inputs

This audit checks `CL-002` through `CL-009` against the tracked legacy MV4 report,
`mv4_summary.json`, the historical producer at commit
`3c5ff5cf587c8ca9cefda20cb220ba29effd2170`, and the current corrected MV4 execution
contract.

The exact starting ledger is 18,183 bytes, Git blob
`58d70cdd7b90c256b2aa268c425de0e1dadbb3f6`, and SHA-256
`cfdfc8b38e53158fee5cb32a61165d2fc8c2e2370d81580e5f75fe369963fbcb`.

## Confirmed defects

- Seven timing rows are not the canonical 43 columns: `CL-002` 38, `CL-003` 39,
  `CL-004` 38, `CL-005` 38, `CL-006` 39, `CL-008` 37, and `CL-009` 37.
- The cited report and summary do not contain B6 `0.68/0.75 ns`, combined-stave
  `0.54/0.56 ns`, or B4-B6 covariance `-0.127 ns²`.
- `CL-007` calls a toy-digitizer pull `VALIDATED/PASS`, although it uses hard-coded
  data anchors and an assumed `0.10 ns` data uncertainty.
- `CL-009` calls the source an ML verdict. The source tests CFD20 and an analytic
  `A+B/sqrt(amplitude)` correction; no ML model is present.
- The former ledger paths `results.json` and `configs/mv4_timing.yaml` are absent.

## Exact fixed legacy outputs

The tracked summary contains 80,000 tracks from 241,487 scanned events, gain
`110 ADC/MeV`, raw sigma68 `1.744319343085384 ns` with i.i.d. track-bootstrap SE
`0.006755405549476786 ns`, corrected held-out sigma68
`1.7696154242198858 ns` with SE `0.010813166729502352 ns`, raw pull
`-1.054403396247793`, and corrected pull `2.680528799917713`.

Those pulls use hard-coded anchors `1.85 ns` and `1.50 ns` and assumed data
uncertainty `0.10 ns`. The train/application split is row-index parity. Calibration
bytes, anchor-result bytes, configuration, manifest, run inventory, and detector-response
systematics are not bound.

The current `scripts/MV4_TIMING_README.md` explicitly labels this path
`TOY_DIAGNOSTIC` and requires current calibration and measured anchors under `--strict`,
with run/block validation.

## Better method and acceptance criteria

A production timing claim must bind exact calibration and data-anchor artifacts, preserve
run/event groups, use run/block bootstrap or a justified dependence model, split training
and validation by run/event groups, report per-stave metrics and the full covariance matrix,
and retain immutable configuration, software versions, seeds, commands, hashes, and plots.
Analytic and plausible alternative timing methods should be compared on identical held-out
runs.

## Reproducible validation

```text
python -m py_compile \
  tools/audit/audit_mv4_legacy_claim_rows.py \
  tests/test_audit_mv4_legacy_claim_rows.py

PYTHONPATH=. python -m pytest tests/test_audit_mv4_legacy_claim_rows.py -q
4 passed in 0.03s

PYTHONPATH=. python tools/audit/audit_mv4_legacy_claim_rows.py \
  --ledger docs/claim_ledger.csv \
  --report reports/mv4_timing_1782678162/REPORT.md \
  --summary reports/mv4_timing_1782678162/mv4_summary.json \
  --contract scripts/MV4_TIMING_README.md \
  --output-json docs/validation/mv4_legacy_claim_rows_audit_validation.json
exit status: 1 (confirmed flaw)
```

The JSON parses, the SVG parses as XML, and changed Python lines are at most 97
characters. The audit is validated; the ledger remediation remains open.

## Scientific boundary

No ROOT processing, detector timing measurement, B6 or combined-stave estimate, covariance
matrix, calibration, or performance closure was produced. This is source/provenance evidence,
not detector data.

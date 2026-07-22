# AUD-AMP-001 — amplitude convention auditor hardening

- **UTC:** 2026-07-22T11:05:08Z
- **Initial remote main:** `10c1f92ba80f42792dfa8a2074161c073979b221`
- **Task:** harden `tools/audit/amplitude_convention_audit.py`
- **Evidence class:** code inspection plus synthetic regression; no real pulse table rerun.

## Confirmed defects in the previous auditor

1. It was tied to one LUNARC path and output location.
2. It silently ignored unreadable files, so the reported table count could look complete when inputs had failed.
3. It used one binary median threshold (`>3000`) and had no uncertainty state.
4. It did not hash or size the exact input files.
5. It marked baseline subtraction as correct for every ABSOLUTE classification even when no baseline column existed.

## Implemented correction

The auditor is now a CLI accepting explicit paths or glob patterns and an explicit JSON output path. It records SHA-256, byte size, rows read, finite amplitude rows, baseline-column diagnostics, and tool version. It uses preregistered thresholds with three states:

- NET: median `amplitude_adc <= 3500` ADC;
- ABSOLUTE: median `amplitude_adc >= 5000` ADC;
- AMBIGUOUS: between those thresholds, requiring manual review.

Unreadable inputs are retained in an `errors` array and cause a nonzero exit. AMBIGUOUS classifications also cause a nonzero exit. Files without `amplitude_adc` are explicit `SKIPPED` records rather than disappearing.

## Validation

Exact temporary copies of the final implementation and tests were executed:

```text
python -m pytest /mnt/data/audit_amp/test_amplitude_convention_audit.py -q
5 passed in 0.08s
```

The environment emitted an unrelated spreadsheet-runtime warmup error after Python startup; pytest itself exited 0.

Covered cases:

- ABSOLUTE classification with baseline-relative diagnostic;
- NET classification;
- AMBIGUOUS classification;
- exact SHA-256 and byte-size provenance;
- explicit skip for files without `amplitude_adc`;
- retained read-error diagnostics and nonzero exit;
- invalid threshold ordering.

## Commits

- `bae929447311ed78925a28d9481ae230a40c523e` — `fix(audit): harden amplitude convention classification`
- `4714e9c25cbb6393ec9f1b9422bcfdf8105a7e47` — `test(audit): cover amplitude convention provenance and ambiguity`

## Evidence boundary

No real report table was available in this execution environment. The previously reported 17 ABSOLUTE / 2 NET result was not rerun or changed. The new tool must be run against the exact A-002 source table and the prior 19-table corpus before those classifications are treated as current validated artifacts.

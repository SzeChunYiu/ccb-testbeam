# AUD-AMP-001 — baseline-level semantic gate

## Session

- UTC: 2026-07-22T15:03:46Z
- Initial remote main: `7d880de8af436634be083649350ce2ed26383424`
- Code/test commit: `76deb2a2c82eb8aaf4e809fc839e076162aca092`
- Write target: `main`

## Confirmed defect

Version 2.3.0 treated any single column whose name contained `baseline` as a pedestal-level baseline. A table containing `amplitude_adc` plus only `baseline_rms_adc` would therefore subtract an RMS/noise width from an absolute peak code, compute a meaningless pedestal-relative diagnostic, and mark `subtract_baseline_correct=true`.

The repository pulse-table contract defines the pedestal level as `baseline_adc`; dispersion quantities such as baseline RMS are not ADC pedestal levels.

## Correction

Version 2.4.0 separates baseline-like columns into:

- pedestal-level candidates: names containing `baseline` without dispersion tokens;
- auxiliary dispersion diagnostics: names containing `rms`, `std`, `sigma`, `noise`, `width`, `variance`, or `var`.

A subtraction diagnostic is produced only when exactly one pedestal-level candidate exists. Auxiliary columns are retained in provenance. Multiple pedestal-level candidates are not selected implicitly.

## Validation

Exact temporary copies were executed:

```text
python -m py_compile \
  /mnt/data/amp_baseline_fix/tools/audit/amplitude_convention_audit.py \
  /mnt/data/amp_baseline_fix/tests/test_amplitude_convention_audit.py

python -m pytest \
  /mnt/data/amp_baseline_fix/tests/test_amplitude_convention_audit.py -q

16 passed in 0.32s
```

New regression cases cover RMS-only input, simultaneous level/RMS columns, and multiple pedestal-level candidates. Existing convention, full-table, malformed-value, provenance, ambiguity, skip, and parser-error tests remain passing.

An unrelated spreadsheet-runtime warmup error was emitted during Python startup; both py_compile and pytest exited successfully.

## Evidence boundary

- No real pulse table was available.
- The prior 19-table corpus was not rerun with version 2.4.0.
- The exact A-002 source-table convention remains unmeasured.
- No corrected A-002 counts, CSV, or plot are claimed.
- Historical A-002 outputs remain quarantined.

## Next action

Run version 2.4.0 over the exact A-002 source table and prior corpus without `--max-rows`. Review every parser error, ambiguous convention, malformed amplitude warning, and baseline-level ambiguity before regenerating A-002 artifacts.

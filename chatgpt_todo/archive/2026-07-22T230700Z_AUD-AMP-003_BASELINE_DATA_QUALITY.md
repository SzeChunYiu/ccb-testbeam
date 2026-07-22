# AUD-AMP-003 — Baseline Data-Quality Gate

## Session

- UTC: 2026-07-22T23:07:00Z
- Initial remote main: `c6b86c9a5253887b709c235766687a69ee322bc2`
- Write target: `main`

## Confirmed defect

`tools/audit/amplitude_convention_audit.py` v2.6.0 set `convention_acceptance=ACCEPTABLE` whenever exactly one pedestal-level column name existed. It did not require that the column contain usable finite values for the finite amplitude rows. An empty, malformed, or nonfinite `baseline_adc` column could therefore authorize an amplitude convention and report subtraction correctness without any usable pedestal data.

## Change

Version 2.7.0 now records finite amplitude/baseline pair coverage. It requires one finite pedestal value for every finite amplitude used in classification. Incomplete coverage sets `baseline_data_quality=INCOMPLETE`, `convention_acceptance=BASELINE_DATA_INVALID`, withholds `subtract_baseline_correct`, emits `INCOMPLETE_BASELINE_FOR_FINITE_AMPLITUDES`, increments `n_invalid_baseline_data_tables`, and forces a nonzero exit.

## Validation

Executed on exact temporary copies:

```text
python -m py_compile tools/audit/amplitude_convention_audit.py tests/test_amplitude_baseline_data_quality.py
python -m pytest tests/test_amplitude_baseline_data_quality.py -q
3 passed in 0.08s
```

The environment emitted an unrelated spreadsheet-runtime warmup error after Python startup; both target commands exited successfully.

## Commits

- `1de58024d3a78525a299789c446e375e6cdd3f35` — `fix(audit): reject incomplete pedestal data`
- `8fd5b6ff4bbd544b4da0baf0acff205ec2ebe3cb` — `test(audit): cover incomplete pedestal data gates`
- `394a98bf45a64a398a3d3bb3d3eb62c13d5d215d` — `docs(audit): claim pedestal data-quality gate`

## Evidence boundary

No real pulse table was available. The historical corpus was not rerun, the exact A-002 amplitude convention remains unknown, and no stopping counts, fractions, CSV, plot, or calibration value was regenerated. Historical A-002 outputs remain quarantined.

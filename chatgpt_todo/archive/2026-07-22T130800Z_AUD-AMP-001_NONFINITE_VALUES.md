# AUD-AMP-001 — Nonfinite amplitude-value gate

## Session

- UTC: 2026-07-22T13:08:00Z
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `46fb4415323b872ef2a8026edd8d68148ae09f41`
- Write target: direct to `main`
- Task state: PARTIAL

## Confirmed defect

Version 2.1.0 converted `amplitude_adc` with `pandas.to_numeric(...).dropna()`. IEEE `+inf` and `-inf` are numeric and survive `dropna()`. A table containing infinities could therefore be classified using a nonphysical median, and baseline-relative diagnostics could also become infinite.

## Correction

Version 2.2.0 now:

- rejects a nonfinite scalar passed directly to `classify`;
- classifies only finite amplitude values;
- records finite, nonfinite, and nonnumeric row counts separately;
- emits `NONFINITE_AMPLITUDE_VALUES_EXCLUDED` when infinities are present;
- makes any table containing nonfinite amplitude values fail the aggregate acceptance gate;
- rejects tables with no finite numeric amplitude values;
- removes nonfinite amplitude/baseline pairs before baseline diagnostics;
- records `finite_amplitude_baseline_pairs` and aggregate `n_nonfinite_tables`.

## Validation

Exact temporary copies were executed with:

```text
python -m pytest /mnt/data/ampfix/tests/test_amplitude_convention_audit.py -q
11 passed in 0.10s
```

The focused tests cover finite classification, ambiguity, full-table versus prefix behavior, nonfinite amplitudes, nonfinite baseline pairs, all-nonfinite rejection, skipped tables, read errors, and invalid thresholds.

An unrelated spreadsheet-runtime warmup emitted an error after Python startup; pytest itself exited with status 0.

## Commits

- `b850e5c947aa8d27e568e145f8ca05e1c7a4991f` — `fix(audit): reject nonfinite amplitude classifications`
- `13aa547969a99bb71999742cbb919ebdbf9677e3` — `test(audit): cover nonfinite amplitude handling`

## Evidence boundary

No real pulse tables were available. The prior repository-recorded corpus classification was not rerun. The exact A-002 input convention and corrected stopping outputs remain unresolved.

## Next action

Run version 2.2.0 against the exact A-002 source table and the prior corpus without `--max-rows`. Review every error, `AMBIGUOUS` record, and nonfinite-value warning before passing a convention to the ΔE–E bridge.

# AUD-AMP-001 — Full-table amplitude classification

- **UTC:** 2026-07-22T12:08:38Z
- **Initial remote main:** `8bff3f834c9da713996d946de1b16f3777e433a4`
- **Task:** remove hidden row-order dependence from the amplitude-convention auditor.

## Confirmed defect

`tools/audit/amplitude_convention_audit.py` defaulted to `--max-rows 40000` and classified the median of only the first rows in each file. The reported convention could therefore change when the same rows were reordered. This is a reproducibility defect because file order is not a physical detector property.

## Correction

- Full-column evaluation is now the default.
- `--max-rows N` remains available only as an explicit prefix diagnostic.
- Prefix results are labelled `PREFIX_SAMPLE` and `PREFIX_SAMPLE_ROW_ORDER_DEPENDENT`.
- Prefix mode returns a nonzero status and cannot satisfy the acceptance gate.
- JSON now records `classification_scope`, `input_truncated`, `max_rows_requested`, and aggregate `n_partial`.
- Tool version advanced from 2.0.0 to 2.1.0.

## Validation

Exact temporary copies were syntax checked and tested:

```text
python -m py_compile /tmp/ccb_audit/tools/audit/amplitude_convention_audit.py /tmp/ccb_audit/tests/test_amplitude_convention_audit.py
python -m pytest /tmp/ccb_audit/tests/test_amplitude_convention_audit.py -q
7 passed in 0.19s
```

The regression fixture demonstrates that a prefix `[100, 200]` is classified NET while the complete table `[100, 200, 6700, 6800, 6900]` is classified ABSOLUTE. The accepted default now evaluates the complete table.

## Commits

- `3013c1eeba50de2c9df437da4d5b8ccf79ee0304` — `fix(audit): remove implicit prefix bias from amplitude classification`
- `a1ce2a1d1908876e684eaf68673c2894759af652` — `test(audit): cover full-table amplitude classification`

## Evidence boundary

No real pulse table was accessed. The prior 17 ABSOLUTE / 2 NET corpus result and the exact A-002 source-table convention remain unverified with version 2.1.0. No corrected A-002 numerical output is claimed.

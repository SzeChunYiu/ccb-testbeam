# AUD-DELTAE-001 — amplitude-convention gate

- **UTC:** 2026-07-22T10:03:23Z
- **Base remote main:** `e44083917882ca5bd6375211a0bb74a3b6d73a37`
- **Task:** AUD-DELTAE-001
- **Status:** PARTIAL
- **Write target:** direct to `main`

## Repository facts inspected

A concurrent main commit, `e44083917882ca5bd6375211a0bb74a3b6d73a37`, records an empirical scan of 19 pulse tables: 17 store legacy `amplitude_adc` as an absolute peak code and two timing tables store it as an already-net amplitude. Therefore the column name alone does not determine whether baseline subtraction is required.

The A-002 bridge previously selected `median_amp_adc` when available and otherwise silently used `amplitude_adc`. Applying the 200 ADC stopping threshold directly to an absolute code near the approximately 6752 ADC pedestal would classify nearly every populated layer as passing. Subtracting baseline from a net timing table would instead double-subtract. Both failure modes are possible without explicit convention provenance.

## Correction

`scripts/single_stave/deltaE_E_data_bridge.py` now:

- accepts explicit net-height columns (`median_amp_adc`, `peak_height_adc`, `net_adc`) as NET;
- refuses to infer semantics for legacy `amplitude_adc`;
- requires `amplitude_convention='absolute'` or `'net'` when that column is selected;
- requires `baseline_adc` for ABSOLUTE input;
- transforms ABSOLUTE input with `abs(amplitude_adc - baseline_adc)` before aggregation and thresholding;
- uses NET input unchanged;
- records source column, convention, transform, and whether the column was explicitly requested in `result.json` metadata;
- rejects multiple explicit amplitude fields unless the caller selects one.

## Validation

Exact temporary copies of the final implementation and tests were executed:

```text
python -m pytest /tmp/test_deltae.py -q
6 passed in 0.37s
```

Coverage includes:

1. composite-key event cardinality;
2. rejection of convention-free `amplitude_adc`;
3. absolute-code conversion to net height;
4. net input without subtraction;
5. missing baseline rejection for absolute input;
6. explicit selection when multiple net-height columns exist.

The unrelated spreadsheet-runtime warmup emitted an error after Python startup, but pytest exited 0 and all six target tests passed.

## Main commits

- `88c9349a5c2a9022f7c7714a634fa4a2c89b78d8` — initial fail-closed amplitude gate.
- `4b700bc0ab9ead04d14b88704102930ac74800d4` — initial gate tests.
- `f7a509c303140239f0c5494cd87a3c3fcdb320b7` — reconcile measured ABSOLUTE/NET conventions and transform correctly.
- `b8d9eb0a5d49e8dfa0e5d4bb56e7d7c0d83bb28d` — regression coverage for both measured conventions.

## Evidence boundary

No real A-002 pulse table was available in this session. The convention of `reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz` was not measured here and is not present in the inspected 19-table audit listing. The production `main()` therefore intentionally fails if that table exposes only ambiguous `amplitude_adc` until its convention is measured and passed explicitly, or until the table is regenerated with an explicit net-height field.

No corrected real stopping counts, fractions, CSV, or figure are claimed.

## Required rerun

1. Hash and inspect the exact A-002 source table.
2. Measure whether its `amplitude_adc` is ABSOLUTE or NET using baseline-relative distributions and the repository audit tool.
3. Prefer an explicit `peak_height_adc`, `median_amp_adc`, or `net_adc` field.
4. If legacy `amplitude_adc` must be used, pass the measured convention explicitly and retain the output metadata.
5. Require one output row per `(source_file_id, run, evt)` and stopping-bin total equal to the physical-event count.
6. Regenerate and review `result.json`, `deltaE_E_events_data.csv`, and `DE-01_deltaE_E_data.png` before replacing quarantined outputs.

# Latest Handoff

## Session

- **UTC:** 2026-07-22T15:03:46Z
- **Task:** AUD-AMP-001 (PARTIAL)
- **Initial remote main:** `7d880de8af436634be083649350ce2ed26383424`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Write target:** direct to `main`

## Confirmed engineering finding

Version 2.3.0 of `tools/audit/amplitude_convention_audit.py` selected any sole column containing `baseline` as the pedestal level. A table containing `amplitude_adc` plus only `baseline_rms_adc` could therefore subtract a noise width from an absolute peak code, produce a nonphysical baseline-relative diagnostic, and report `subtract_baseline_correct=true`.

The repository pulse-table contract identifies `baseline_adc` as a pedestal level. RMS, standard-deviation, sigma, noise, width, and variance fields are dispersion diagnostics rather than pedestal codes.

## Work pushed directly to main

The auditor is now version 2.4.0 and:

- separates baseline-like columns into pedestal-level candidates and auxiliary dispersion diagnostics;
- excludes names containing `rms`, `std`, `sigma`, `noise`, `width`, `variance`, or `var` from pedestal-level selection;
- records both `baseline_candidates` and `auxiliary_baseline_columns`;
- produces subtraction diagnostics only when exactly one pedestal-level candidate exists;
- reports `MULTIPLE_BASELINE_LEVEL_COLUMNS` rather than choosing among multiple level candidates;
- reports `ABSOLUTE_WITHOUT_BASELINE_LEVEL` for an absolute table with only dispersion diagnostics or no baseline level;
- preserves full-table classification, prefix rejection, ambiguity, SHA-256 provenance, malformed/nonfinite rejection, skips, and read-error reporting.

Regression coverage was expanded in `tests/test_amplitude_convention_audit.py`.

Immutable session record:

- `chatgpt_todo/archive/2026-07-22T150346Z_AUD-AMP-001_BASELINE_LEVEL.md`

## Validation

Exact temporary copies were executed:

```text
python -m py_compile /mnt/data/amp_baseline_fix/tools/audit/amplitude_convention_audit.py /mnt/data/amp_baseline_fix/tests/test_amplitude_convention_audit.py
python -m pytest /mnt/data/amp_baseline_fix/tests/test_amplitude_convention_audit.py -q
16 passed in 0.32s
```

New tests verify that `baseline_rms_adc` is never treated as a pedestal, that `baseline_adc` is selected when RMS is also present, and that multiple pedestal-level columns are not selected implicitly. Existing regression cases remain passing.

An unrelated spreadsheet-runtime warmup error appeared during Python startup; py_compile and pytest both exited successfully.

## Main progression

- `7d880de8af436634be083649350ce2ed26383424` — initial remote main.
- `76deb2a2c82eb8aaf4e809fc839e076162aca092` — `fix(audit): distinguish pedestal baselines from dispersion columns`.
- This handoff update is the final session commit and must be verified as remote `main`.

## Evidence boundary and blockers

- No real pulse table was available in this execution environment.
- The prior repository-recorded corpus classification was not rerun with version 2.4.0.
- The exact convention and baseline schema of the A-002 source table remain unmeasured here.
- Historical A-002 stopping outputs remain quarantined.
- No corrected stopping counts, fractions, CSV, or plot are claimed.

## Acceptance status

- Baseline-level versus dispersion-column semantics: VALIDATED on synthetic regression.
- Finite-numeric classification and malformed-value rejection: VALIDATED on synthetic regression.
- Full-table default and partial-mode rejection: VALIDATED on synthetic regression.
- Prior corpus classification: repository-recorded only; rerun required with version 2.4.0 and no `--max-rows`.
- A-002 source-table convention/schema: BLOCKED pending exact-table measurement.
- Corrected A-002 real-data artifacts: BLOCKED.

## Next action

Run version 2.4.0 against the exact A-002 source table and prior amplitude-table corpus without `--max-rows`. Commit generated JSON outputs with hashes, then review every parser error, `AMBIGUOUS` record, nonfinite/nonnumeric warning, and baseline-level ambiguity. Only after that should the measured convention be passed explicitly to `scripts/single_stave/deltaE_E_data_bridge.py` and the quarantined A-002 JSON, CSV, and figure be regenerated under the composite-key and stopping-bin cardinality invariants.

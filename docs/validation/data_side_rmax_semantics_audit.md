# Data-side Rmax occupancy-semantics audit

## Status

- **Task:** `AUD-LEDGER-004`
- **Policy:** `OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`
- **Current repository result:** `FLAWED`
- **Scientific acceptance:** `BLOCKED`
- **Accepted Rmax:** none

## Confirmed defect

The real-beam data-side study measures selected B-stave pulse multiplicity per composite
`(run,eventno)` key. That is useful descriptive occupancy evidence, but it does not provide
run exposure, trigger/live-time accounting, luminosity, or an independently measured
pile-up tolerance parameter.

The current producer nevertheless sets `mu_max = 0.38`, assumes `tau_eff = 160 - 30 =
130 ns`, calculates `2.923076923076923 MHz`, labels it `Rmax_data_derived_Hz`, and states
that occupancy grounds the convention. The canonical ledger then publishes `2.92 MHz`
with unsupported `0.10` and `0.20 MHz` uncertainty components and status
`DONE_DATA_ONLY`.

This conflicts with the existing source-conflict quarantine: `0.38` is a legacy duty-factor
convention, the recovery-failure ceiling was not crossed, and the exact S10b `CL-011`
estimand is `124.79018394263471 ns`, not the ad hoc `130 ns` value.

## Independent calculation

Using the exact S10b live-time estimand only as a model input gives

```text
0.38 / 124.79018394263471 ns = 3.045111305987686 MHz
```

The former 130 ns assumption gives

```text
0.38 / 130 ns = 2.923076923076923 MHz
```

The difference is `-0.12203438291076338 MHz` (`-4.007550813357915%`). Both values are
model/convention calculations. Neither becomes a data-derived absolute rate because a
selected-pulse multiplicity histogram is available.

## Fail-closed contract

The new validator requires:

1. `CL-010` has no accepted value or invented uncertainty components, remains `BLOCKED`,
   and retains blocker `S-STAT-003` and the MV5 conflict evidence.
2. `CL-011` remains bound to the exact `124.79018394263471 ns` data-only estimand and
   `BLK-S10B-001` limitation.
3. The data-side producer records occupancy as descriptive multiplicity only, sets
   `rmax_authorized=false`, and labels any reciprocal calculation as model sensitivity.
4. The data-side report states that occupancy does not measure event-arrival rate or
   exposure and that `CL-010` remains blocked.

## Validation

```text
python -m py_compile \
  tools/audit/audit_data_side_rmax_semantics.py \
  tests/test_audit_data_side_rmax_semantics.py \
  tools/audit/render_data_side_rmax_semantics_evidence.py

pytest -q tests/test_audit_data_side_rmax_semantics.py
6 passed in 0.03s
```

The executable current-like fixture returns `FLAWED` with 34 findings. A corrected
contract fixture returns `VALIDATED` with zero findings. Duplicate claim IDs, invalid
UTF-8, an altered exact tau value, and destructive output aliases fail closed. The JSON
and SVG parse successfully.

## Required remediation

A subsequent focused unit should update `scripts/studies/data_side_real_beam.py`,
`reports/studies/data_side/REPORT.md`, and the `CL-010` ledger row together. It should
regenerate the occupancy figure with `Rmax withheld` in the title, preserve the measured
multiplicity values, remove unsupported uncertainty components, and run both this gate and
`tools/audit/validate_claim_ledger_cl010.py` to zero findings.

## Scientific boundary

This audit does not measure an absolute event rate, beam luminosity, live exposure,
pile-up tolerance, recovery ceiling, calibration, or detector performance. The raw ROOT
files and production study were not rerun in this connector environment.

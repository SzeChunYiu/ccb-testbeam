# ΔE-E net-amplitude input-integrity remediation

## Scope and evidence class

This is a software-integrity and provenance correction for
`scripts/single_stave/deltaE_E_data_bridge.py`. The run began from remote
`main` `421aafd6894b6ba3b92b98f616141084742b6812`, where the canonical bridge
had Git blob `7f50ce667a6cde07e94717d0187831da4d8459ac`.

It is not detector data, a calibration, a stopping-profile measurement, or a
particle-identification result.

Policy:

`DELTAE_NET_AMPLITUDE_ROWS_MUST_BE_FINITE_NUMERIC_BEFORE_AGGREGATION`

## Confirmed former defect

The absolute-code path validated numeric finiteness before signed pedestal
conversion. The net-amplitude path instead copied the selected source column
directly into the aggregation value. The subsequent `groupby(...).max()` and
`pivot_table(...)` could omit an all-NaN stave cell, after which the
missing-layer loop filled that cell with `0.0`. Positive infinity was retained.

Executable synthetic controls reproduced both failures:

- a NaN B2 measurement with finite B4 became `amp_B2 = 0.0`;
- a positive-infinity B2 measurement remained infinite.

Either transformation could alter the stopping-layer category and the ΔE
coordinate without an explicit rejection.

## Correction

The canonical bridge now converts every selected net-amplitude row with
`pd.to_numeric(errors="coerce")` and rejects any nonfinite result with
`np.isfinite` before event/stave aggregation, pivoting, or missing-layer zero
filling.

Finite inputs preserve the established behavior. A genuinely absent stave is
still represented as zero only after every present measurement row has passed
the finite numeric gate.

The result dictionary now records:

- `amplitude_validation` with a convention-specific validation policy;
- `missing_layer_policy = ZERO_FILL_ONLY_AFTER_FINITE_ROW_VALIDATION_AND_EVENT_STAVE_AGGREGATION`.

Implementation provenance:

- implementation commit: `910efe6b37b3d16a31275e9c0502ee2bd5512ab9`;
- current source Git blob: `2820c461508990d743cc53754c33ec2934a3c9ad`;
- exact source bytes: `13225`;
- exact source SHA-256: `8295d117b068795ea48015c14cbd7531094dae5931283e5e9205121d5eaa8011`.

## Regression coverage

Added `tests/test_deltae_net_input_remediation.py`. It verifies:

1. NaN, positive infinity, negative infinity, and nonnumeric net amplitudes fail;
2. finite B2/B4 values are retained and truly absent B6/B8 layers are zero-filled;
3. the pre-existing executable audit returns `VALIDATED` with zero issues;
4. the strict content-addressed runner rejects invalid bridge input before an
   output bundle is published.

The strict runner was inspected at its current bridge-delegation and
pre-publication validation path. The new repository test calls its actual
`run_strict_bridge` API.

## Validation

Executed on exact reconstructed repository files:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E_data_bridge.py \
  tools/audit/audit_deltae_net_input_integrity.py \
  tests/test_deltae_net_input_remediation.py

pytest -q \
  tests/test_deltae_data_bridge_composite_key.py \
  tests/test_deltae_net_input_remediation.py

17 passed in 0.31s
```

The executable audit returned `VALIDATED`, `issue_count = 0`: the finite control
was accepted while NaN and positive infinity were rejected. JSON parsing, SVG
XML parsing, and changed-Python line-length checks passed; changed Python lines
are at most 95 characters.

The connector did not provide a full network checkout. The focused validation
used exact current source/test bytes reconstructed from GitHub and the unchanged
strict-runner call contract. No repository-wide pytest, ruff, ROOT, or LUNARC
execution is claimed.

## Acceptance state

The software-remediation unit of `AUD-DELTAE-003` is `COMPLETE`. The former
net-input integrity blocker is resolved: an invalid measured net-amplitude row
can no longer disappear into a zero-filled layer or propagate infinity.

A-002 scientific acceptance remains blocked under `BLK-AMP-001`,
`AUD-DELTAE-001`, and `AUD-DELTAE-002`. No exact A-002 pulse table, measured
convention/polarity authorization, production rerun, stopping distribution,
uncertainty budget, ΔE-E PID result, calibration, or detector-performance claim
was produced.

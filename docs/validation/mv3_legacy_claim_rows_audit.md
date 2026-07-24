# Legacy MV3 claim-row reconstruction audit

## Scope

This audit reconstructs canonical claim rows `CL-019`, `CL-020`, and `CL-021`
from the exact tracked legacy MV3 v3 stopping-depth report. It does not rerun
ROOT processing, beam data, or Geant4.

Policy:

`LEGACY_MV3_PROFILE_REQUIRES_EXACT_COUNTS_AND_FAIL_CLOSED_RERUN`

## Confirmed defects

The canonical claim ledger uses 43 fields, but the three legacy MV3 rows had
38, 38, and 36 fields. Their truth type, status, source, confidence-interval
state, blocker, supersession, and notes were therefore shifted and withheld.

The former rows also cited two paths that are not tracked on current `main`:

- `scripts/mv3_stopping.py`;
- `reports/mv3_stopping_v3_1782679272/results.json`.

The only tracked result artifact is the Markdown report. It provides rounded
three-decimal stopping fractions and the single label `chi2/ndf = 68269.4`, but
not exact per-stave counts, a separated chi-square and number of degrees of
freedom, a p-value, bin variances, or covariance information.

## Exact source evidence

Legacy report:

- path: `reports/mv3_stopping_v3_1782679272/REPORT.md`;
- Git blob: `b72eed4f7eb3237040a1346d7253080c098c8986`;
- bytes: `2232`;
- SHA-256:
  `a1027e168d1f0321a334c44f1a1d59176a17869b5239991709b861db7962fa0f`;
- introducing commit: `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`.

Source-supported quantities:

| Quantity | Value |
|---|---:|
| MC tracks above threshold | 249484 |
| Data events | 306745 |
| MC B8 fraction | 0.223 (rounded to 3 decimals) |
| Data B8 fraction | 0.023 (rounded to 3 decimals) |
| Reported profile label | `chi2/ndf = 68269.4` |

The rounded fractions do not identify exact binomial numerators. Under ordinary
round-to-nearest three-decimal interpretation:

- any MC B8 count from 55511 through 55759 is compatible with 0.223;
- any data B8 count from 6902 through 7208 is compatible with 0.023.

Consequently, an exact numerator, exact binomial interval, or exact profile
statistic cannot be reconstructed honestly from this report.

## Current fail-closed remediation

Current source:

- path: `src/ccb_mc_validation/studies/mv3_stopping_depth.py`;
- Git blob: `9b0dfeaa6e74401345bc78c7ab82b33d7868b665`;
- bytes: `7903`;
- SHA-256:
  `6f5d206caed1b54d0b6e2d0a9ef558e8f0e298bcb2683ccedd6fe33ff8e7bc43`.

The current module blocks when `sample_label` or a real per-layer hit/energy
mask is missing. It no longer synthesizes Sample I/II from parity and no longer
uses `stop_layer >= layer` as an occupancy proxy. The legacy fixed numbers have
not been rerun through this corrected path.

## Reconstructed governance state

- `CL-019` records the rounded MC B8 fraction as `GATED` and leaves numerator,
  denominator-derived uncertainty, and confidence interval fields blank.
- `CL-020` does the same for the rounded data B8 fraction.
- `CL-021` records the literal legacy `chi2/ndf` label as `FLAWED`, not as a
  calibrated goodness-of-fit result.
- All three rows are exact-width and blocked by `BLK-MV3-LEGACY-001`.

## Validation

```text
python -m py_compile \
  tools/audit/validate_mv3_legacy_claim_rows.py \
  tools/audit/render_mv3_legacy_claim_evidence.py \
  tests/test_validate_mv3_legacy_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv3_legacy_claim_rows.py -q

7 passed in 1.05s
```

The direct validator returned `VALIDATED` with zero issues. The regression suite
covers width mismatch, fabricated exact numerators, a changed profile value,
source mutation, invalid UTF-8, and SVG well-formedness. The JSON and SVG parse
successfully, and changed Python files contain no line longer than 100
characters.

## Scientific boundary

This is a source-governance correction, not a stopping-depth measurement. It
does not establish exact B8 counts, binomial intervals, a valid chi-square test,
a p-value, threshold-transfer closure, sample-trigger closure, material-budget
closure, or a detector-performance result. A clean rerun with immutable inputs,
current fail-closed code, exact counts, a preregistered profile statistic and
uncertainty model, and validated data/MC selections is required before these
legacy outputs can be promoted.

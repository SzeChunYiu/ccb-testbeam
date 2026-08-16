# MV3 tracked-summary remediation audit

## Scope

This unit corrects the canonical governance records and validation software for the
legacy MV3 stopping-profile result. It does not rerun MV3 or accept the legacy statistic
as a calibrated goodness-of-fit result.

The exact starting `main` commit was
`a52ea7c3f76eddff204e8ebb990a55cfe8793e7f`. The corrected unit binds the claim ledger
to the tracked files:

- `reports/mv3_stopping_v3_1782679272/REPORT.md`;
- `reports/mv3_stopping_v3_1782679272/mv3_summary.json`;
- `src/ccb_mc_validation/studies/mv3_stopping_depth.py`.

## Confirmed provenance error

The former `CL-019`, `CL-020`, and `CL-021` rows and validator version 1.0 asserted
that exact B-stack counts, exact B8 numerators, the underlying chi-square components,
and a machine-readable result were absent. The tracked summary contradicts that
statement.

It contains:

| Quantity | Exact tracked value |
|---|---:|
| MC B2/B4/B6/B8 counts | 117213 / 45507 / 31145 / 55619 |
| MC denominator | 249484 |
| MC B8 fraction | 0.22293614019335908 |
| Data B2/B4/B6/B8 counts | 268576 / 19284 / 11834 / 7051 |
| Data denominator | 306745 |
| Data B8 fraction | 0.02298651974767315 |
| Pearson chi-square | 204808.2179684494 |
| Degrees of freedom | 3 |
| Chi-square / ndf | 68269.40598948313 |

The rounded report remains useful as presentation history, but it is not the highest
precision tracked source.

## Independent calculation

For the four stave categories, the stored diagnostic is reproduced as:

```text
expected_i = 306745 * mc_fraction_i
chi2 = sum((data_count_i - expected_i)^2 / expected_i)
ndf = 4 - 1
```

The independent binary64 calculation gives exactly:

```text
chi2 = 204808.2179684494
chi2 / ndf = 68269.40598948313
```

This validates source arithmetic and provenance only.

## Corrected governance contract

The three canonical rows now use exact tracked values and the summary path:

- `CL-019`: `55619/249484`, exact fraction `0.22293614019335908`, `GATED`;
- `CL-020`: `7051/306745`, exact fraction `0.02298651974767315`, `GATED`;
- `CL-021`: exact Pearson `chi2/ndf = 68269.40598948313`, `FLAWED`.

`CL-021` remains `FLAWED`. Exact arithmetic does not supply an accepted covariance
model, p-value interpretation, geometry/material closure, trigger and selection
transfer, gain-response closure, or detector/model systematic propagation.

Validator version 2.0 requires the exact summary counts/fractions, independently
reconstructs the statistic, rejects unsupported uncertainty fields, requires the
tracked source path, and verifies that the current strict MV3 implementation blocks
without explicit `sample_label` and per-layer hit/energy masks.

The root WIKI was reviewed and still requires a separate safe full-file synchronization.
This unit does not claim that public-front-door remediation is complete.

## Validation

Executed on exact reconstructed repository bytes:

```text
python -m py_compile \
  tools/audit/validate_mv3_legacy_claim_rows.py \
  tools/audit/audit_mv3_summary_provenance.py \
  tools/audit/render_mv3_legacy_claim_evidence.py \
  tests/test_validate_mv3_legacy_claim_rows.py \
  tests/test_audit_mv3_summary_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv3_legacy_claim_rows.py \
  tests/test_audit_mv3_summary_provenance.py -q

11 passed in 1.76s
```

The direct validator returned `VALIDATED` with zero issues on an exact reconstructed ledger
containing the committed CL-019/020/021 rows. The exact former ledger blob
`bb552aa5ed70e7d81dcda888c5aa61402c01e03c` returned status 1 with 33 findings under
the corrected contract. JSON parsing and SVG XML parsing passed. Changed Python lines
are no longer than 100 characters.

## Visual evidence

`mv3_summary_remediation.svg` shows exact data and thresholded-MC B8 counts and
fractions, the reconstructed Pearson statistic, and the non-acceptance boundary. It is
software/provenance validation, not a new detector-data plot.

## Scientific boundary and next method

The legacy statistic uses selected-data counts against expected counts formed from the
thresholded-MC fractions. It is a fixed source diagnostic, not a validated contemporary
closure. A better method requires:

1. corrected and hash-bound geometry/material inputs;
2. explicit data trigger/sample labels and a matched MC selection model;
3. per-layer hit/energy masks rather than inferred occupancy;
4. declared treatment of normalization and category covariance;
5. detector-response, gain, pile-up, and selection systematics;
6. preregistered residual, ratio, pull, and sensitivity plots;
7. an independent validation sample or newly generated MC.

No ROOT file, GEANT4 sample, p-value, confidence interval, covariance matrix, corrected
geometry, acceptance correction, calibration, or detector-performance result was
produced in this unit.

## Remaining documentation blocker

The current root `WIKI.md` still contains stale MV3/GAP-01 absence wording. The available
contents connector requires whole-file replacement; this run did not replace a long public
document without a byte-safe complete snapshot. A subsequent unit must synchronize the
exact counts and Pearson diagnostic while retaining the `FLAWED` acceptance boundary.

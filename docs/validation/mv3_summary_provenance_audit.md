# MV3 tracked-summary provenance audit

## Status

**FLAWED current claim-ledger state; validated audit.** This is a documentation and
provenance finding, not a new detector-performance result.

Policy: `TRACKED_MV3_SUMMARY_OVERRIDES_ROUNDED_REPORT_PROSE`.

## Confirmed contradiction

The public MV3 report prints fractions rounded to three decimal places and a rounded
`χ²/ndf = 68269.4` label. The tracked file
`reports/mv3_stopping_v3_1782679272/mv3_summary.json` contains substantially more
information:

- exact thresholded-MC counts: B2/B4/B6/B8 = 117213/45507/31145/55619;
- exact selected-data counts: B2/B4/B6/B8 = 268576/19284/11834/7051;
- exact denominators: 249484 MC tracks and 306745 data events;
- stored Pearson χ² = 204808.2179684494;
- stored ndf = 3;
- stored χ²/ndf = 68269.40598948313.

The current canonical rows `CL-019`, `CL-020`, and `CL-021` instead say that exact
counts, the underlying χ²/ndf components, and a machine-readable result are absent.
They leave the exact numerator/denominator and `source_data` fields empty. The existing
v1.0 MV3 row validator enforces that incorrect absence narrative.

## Independent reconstruction

Using the tracked MC fractions as the expected multinomial profile for the 306745 data
events, the audit computes

```text
expected_i = 306745 * mc_fraction_i
χ² = Σ_i (data_count_i - expected_i)^2 / expected_i
ndf = 4 bins - 1 = 3
```

The result is exactly reproducible in binary64 arithmetic:

```text
χ² = 204808.2179684494
χ²/ndf = 68269.40598948313
```

This proves that the statistic is reconstructable from tracked bytes. It does **not**
make the comparison scientifically calibrated: geometry, trigger/selection transfer,
gain response, bin covariance, and detector/model systematics remain unresolved.
`CL-021` should remain `FLAWED`, but for those scientific reasons rather than absent
source data.

## Required correction contract

- `CL-019`: record 55619/249484, exact fraction 0.22293614019335908, and the summary
  path.
- `CL-020`: record 7051/306745, exact fraction 0.02298651974767315, and the summary
  path.
- `CL-021`: record exact χ²/ndf 68269.40598948313, the Pearson construction, and the
  summary path; retain `FLAWED` and the blocker.
- Replace the old validator contract that rejects exact numerators and denies the
  tracked summary.
- Synchronize WIKI GAP-01 prose so the number is described as an exact but flawed
  legacy Pearson diagnostic, not a non-reconstructable geometry-only proof.

No confidence interval is introduced. Exact fixed counts do not, by themselves,
provide an accepted statistical or systematic uncertainty model.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv3_summary_provenance.py \
  tests/test_audit_mv3_summary_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_mv3_summary_provenance.py -q

5 passed in 0.70s
```

The current-like ledger fixture returns status 1 with 32 explicit findings. A corrected
fixture returns `VALIDATED` with zero findings. Mutated χ² and fraction fields fail
closed, and invalid UTF-8 returns controlled status 2.

## Boundaries

No raw ROOT file, GEANT4 rerun, detector geometry, threshold transfer, gain calibration,
confidence interval, p-value, or covariance model was produced. The tracked summary
supports exact provenance and arithmetic reconstruction only. Accepted stopping-depth
closure remains blocked under `BLK-MV3-LEGACY-001`.

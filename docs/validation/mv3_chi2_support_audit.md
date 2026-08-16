# MV3 Pearson chi-square model-support audit

## Finding

The weighted MV3 producer masks categories with zero expected count before evaluating Pearson
chi-square. That is valid only when the corresponding observed count is also zero. If data contain a
positive count in a category assigned zero model probability, the Pearson statistic is not finite
under that model and the comparison must fail closed.

The producer also does not verify that the four supplied model fractions sum to one before treating
them as probabilities.

Policy:

`PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`

## Reproducible controls

For model fractions `[0.50, 0.50, 0, 0]` and observed counts `[45, 45, 10, 0]`, the current
implementation drops the unsupported B6 category and returns:

```text
chi2 = 1.0
ndf = 1
chi2/ndf = 1.0
```

The B6 observation is ten while its expected count is zero. Returning a finite statistic therefore
misstates model support.

For model fractions `[0.45, 0.45, 0.05, 0]`, which sum to `0.95`, and the same observed counts, the
current implementation returns:

```text
chi2 = 5.0
ndf = 2
chi2/ndf = 2.5
```

The expected counts sum to 95 rather than the observed total of 100, so these values are not a valid
four-category probability-model comparison.

## Required correction

Before forming expected counts, the producer must require the model profile to sum to one within a
declared numerical tolerance. It must reject every category with `observed > 0` and `expected == 0`
as `CHI2_OBSERVED_OUTSIDE_MODEL_SUPPORT`. Categories where both values are zero may be omitted, with
ndf derived from the remaining supported categories.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv3_chi2_support.py \
  tests/test_audit_mv3_chi2_support.py \
  tools/audit/render_mv3_chi2_support_evidence.py

pytest -q tests/test_audit_mv3_chi2_support.py
6 passed in 0.03s
```

The current exact function reconstruction returns `FLAWED` with two findings. A corrected fixture
returns `VALIDATED` with zero findings. Regressions also cover valid four-bin input, empty
zero-support categories, invalid UTF-8, destructive output aliasing, and atomic JSON publication.
The validation JSON parses, the SVG parses as XML, and changed Python lines are at most 100
characters.

The full remote producer blob could not be executed locally because the runtime could not resolve
`github.com`. The audited function was reconstructed exactly from authenticated connector-returned
source lines 123-136, and the validation record separately retains the current repository blob
identity `cd787ab64408228d67536b88bcc617fe32d0ec5a`.

## Scientific boundary

This is synthetic software and statistical-contract evidence. No production ROOT file, beam-data
profile, covariance, material or scattering correction, calibration, PID result, stopping-profile
closure, or detector-performance result was produced. Canonical `CL-021` remains `FLAWED` under
`BLK-MV3-LEGACY-001`.

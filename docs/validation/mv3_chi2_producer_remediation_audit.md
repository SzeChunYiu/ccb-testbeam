# MV3 Pearson chi-square producer remediation audit

## Scope

This unit follows `AUD-MV3-SEL-003`. The prior audit established that the weighted
selection-matched producer silently removed any category with zero expected count before evaluating
Pearson chi-square and accepted model fractions that did not sum to one.

Initial remote `main`:

`54a899d82c1991747218a5b3a5a0835c51991420`

Transport PR: `#933`

Candidate head reviewed here:

`c9b20d0707b675c134ce8e6b0e804a115b569ae4`

## Confirmed defect and independent controls

Former source blob `cd787ab64408228d67536b88bcc617fe32d0ec5a` applied
`expected > 0` as a mask before summing Pearson terms.

Control 1:

```text
model fractions = [0.50, 0.50, 0, 0]
observed counts = [45, 45, 10, 0]
former result = chi2 1.0, ndf 1, chi2/ndf 1.0
```

The B6 count of ten was outside the model support but was omitted rather than rejected.

Control 2:

```text
model fractions = [0.45, 0.45, 0.05, 0]
observed counts = [45, 45, 10, 0]
former result = chi2 5.0, ndf 2, chi2/ndf 2.5
```

The model fractions sum to `0.95`; expected counts therefore sum to 95 while observations sum to
100. The former implementation treated these values as a categorical probability model.

## Corrected method

Policy:

`PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`

The canonical front door now requires:

1. exactly the B2, B4, B6 and B8 categories in model and observation dictionaries;
2. finite nonnegative model and observed values;
3. model fractions summing to one within absolute tolerance `1e-12`;
4. positive observed total;
5. rejection of every positive observed count whose expectation is zero;
6. omission only of categories where both expected and observed counts are zero;
7. degrees of freedom from the supported categories;
8. `math.fsum` for the Pearson-term sum.

The existing weighted producer body is retained as an exact internal dependency. Generated summaries
record the canonical front-door and internal implementation byte counts and full SHA-256 digests.
This split is an engineering migration mechanism, not a scientific result.

## Regression and CI evidence

Focused workflow `MV3 Pearson Contract CI`, run `30181818650`, job `89739575951`, completed with
conclusion `success`. Its successful steps were:

- focused Python compilation;
- producer, weighting and audit regressions;
- exact canonical-source audit with zero findings;
- 100-character focused line-length gate.

The repository-wide `MC Validation CI`, run `30181818642`, job `89739575939`, remained red:

```text
ruff: All checks passed
pytest: 42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s
```

No candidate regression appeared in the failure list. The retained artifact is
`8625795443`, digest
`sha256:d16b0db6177e79fb30bcc682160d5460c30ea17f685b4a709c454f6c565adafa`.
The 42 failures span pre-existing stopping-power, figure-registry, claim-governance, PCA and public
WIKI contracts. They were not concealed or reclassified as passing.

## Delivery decision

The candidate was **not merged** and remote `main` was **not advanced**. The focused contract is
validated, but the repository-wide gate remains failed. PR #933 is retained only as a transport and
review artifact. This unit must not be reported as delivered to `main` until the required gate is
resolved and the resulting commit is confirmed on remote `main`.

## Scientific boundary

No production ROOT or beam-data file was rerun. No weighted stopping profile, covariance,
preregistered sensitivity scan, scattering/material correction, calibration, PID result, closure
claim or detector-performance result was produced. Canonical `CL-021` remains `FLAWED` under
`BLK-MV3-LEGACY-001`.

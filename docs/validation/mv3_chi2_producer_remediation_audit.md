# MV3 Pearson chi-square producer remediation audit

## Scope

This unit follows `AUD-MV3-SEL-003`. The prior audit established that the weighted
selection-matched producer silently removed any category with zero expected count before evaluating
Pearson chi-square and accepted model fractions that did not sum to one.

Initial remote `main`: `54a899d82c1991747218a5b3a5a0835c51991420`

Transport PR: `#933`

Validated implementation head: `c9b20d0707b675c134ce8e6b0e804a115b569ae4`

## Confirmed defect and independent controls

Former source blob `cd787ab64408228d67536b88bcc617fe32d0ec5a` applied
`expected > 0` as a mask before summing Pearson terms.

```text
model fractions = [0.50, 0.50, 0, 0]
observed counts = [45, 45, 10, 0]
former result = chi2 1.0, ndf 1, chi2/ndf 1.0
```

The B6 count of ten was outside model support but was omitted rather than rejected.

```text
model fractions = [0.45, 0.45, 0.05, 0]
observed counts = [45, 45, 10, 0]
former result = chi2 5.0, ndf 2, chi2/ndf 2.5
```

The model fractions sum to `0.95`; expected counts sum to 95 while observations sum to 100.

## Corrected method

Policy:

`PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`

The candidate requires exact B2/B4/B6/B8 keys, finite nonnegative values, model normalization within
absolute tolerance `1e-12`, positive observed total, rejection of positive observed mass at zero
expectation, omission only when expected and observed are both zero, supported-category ndf, and
`math.fsum`. The existing weighted producer body is retained as an exact internal dependency, and
summaries record both executable source snapshots and their complete SHA-256 digests.

## Regression and CI evidence

Focused workflow `30181818650`, job `89739575951`, concluded `success`. Compilation, focused
producer/audit regressions, exact-source zero-finding audit and line-length enforcement all passed.

Repository-wide workflow `30181818642`, job `89739575939`, remained red:

```text
ruff: All checks passed
pytest: 42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s
```

No candidate regression appeared in the failure list. Artifact `8625795443` has digest
`sha256:d16b0db6177e79fb30bcc682160d5460c30ea17f685b4a709c454f6c565adafa`.
The failures span existing stopping-power, figure-registry, claim-governance, PCA and public-WIKI
contracts and were not concealed or reclassified as passing.

## Delivery decision

The candidate producer was **not merged**. PR #933 was converted to draft and remains transport only.
Remote `main` advanced only with validated blocker documentation and evidence:

- `13ddd66f1b5280a960336d6f855631398d7db090` — blocker evidence
- `fae320327fc157ffa362ad139df568b311201372` — handoff

Producer code is not on `main` and must not be reported as delivered until the repository-wide gate
is resolved and the resulting commit is confirmed on remote `main`.

## Scientific boundary

No production ROOT or beam-data file was rerun. No weighted stopping profile, covariance,
preregistered sensitivity scan, material/scattering correction, calibration, PID result, closure
claim or detector-performance result was produced. Canonical `CL-021` remains `FLAWED` under
`BLK-MV3-LEGACY-001`.

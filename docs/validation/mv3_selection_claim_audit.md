# MV3 selection-matched claim semantics audit

## Scope and acceptance state

This focused unit independently reviews the MV3 selection-matched stopping-depth follow-up
introduced by merge commit `701116061eb3346a3ae2b31e2946ca450d6120e2`. The new study
reports a strong descriptive shift after applying an A/B coincidence selection to MC, but it
also upgrades the public interpretation of `CL-021`. This audit checks whether that upgrade is
supported by the repository's MC-source weight contract, canonical charge convention,
comparison estimand, exact summary, uncertainty treatment, and claim ledger.

Policy:

`MV3_SELECTION_CLAIM_REQUIRES_WEIGHTED_SIGNED_CHARGE_AND_SAME_TARGET_VALIDATION`

The audit gate and its tests are `VALIDATED`. The production follow-up remains `FLAWED`
pending a content-addressed weighted signed-charge rerun. Canonical `CL-021` remains
`FLAWED` under `BLK-MV3-LEGACY-001`.

## Exact reviewed repository state

Initial remote `main` was `701116061eb3346a3ae2b31e2946ca450d6120e2`. Reviewed blobs:

- producer `scripts/studies/mv3_selection_matched.py`:
  `32c2c9d480aa5bd02ecc6a73ddc4c0654dae21ca`;
- report `reports/studies/mv3_selection_matched/REPORT.md`:
  `7d0608e473bc85df7c1e5a8f2010ba01074d8ba8`;
- summary JSON: `bb659df56eacf6c7a9f0d3f56df3cf31043019ba`;
- canonical ledger: `83238de4b244b741bd2227986455edf04bff3265`;
- MC-weight audit: `3cf001dd7cc8ff489c7a804bd5aa53f8d663153a`;
- canonical PDG helper: `8c484b131ec07f3af2e2bd4726b83cd64601190c`;
- trigger-split producer: `6173fe27f3a7beaf74d3b3442153207b16d95074`.

PR #932 was merged. No open PR existed. PR #868 remained closed, unmerged, and
non-mergeable and was not modified. No status checks were attached to the initial head.

## Confirmed defects

### 1. The physical MC profile discards the source cross-section weight

The producer requests `PrimaryWeight`, constructs `w_evt`, silently substitutes `1.0` when
the first weight is absent or nonfinite, and then increments every stopping-profile count by
one. No weighted stopping accumulator, sum of weights, sum of squared weights, or effective
sample size is retained. A nearby comment incorrectly describes the final fractions as
weighted.

This conflicts with the repository's source-specific weight contract: the Krakow generator
samples the CM angle uniformly and stores the lab-angle cross-section factor in
`PrimaryWeight`; the retained production audit states that unweighted truth distributions are
not physical production distributions. The selection report nevertheless says the weight
“must NOT be used,” then attributes the residual to the absence of physical angular weighting.
The available correction is therefore loaded and discarded before that attribution is made.

### 2. The charged-particle mask is sign-asymmetric

The follow-up defines a hit as charged when `pdg_charge(int(p)) >= 1`. That accepts positive
particles but rejects electrons, negative pions, negative muons, and any negatively charged
nucleus. The canonical helper defines charged as `abs(charge) > 0.5`. This inconsistency can
change trigger membership, per-stave deposition, secondary composition, stopping depth, and
DeltaE-E correlations.

### 3. The advertised improvement changes both sides of the comparison

The reported `16.602672795596263x` ratio divides:

- unselected MC versus **all** selected data; by
- Sample-I MC versus **Sample-I** data.

That is not a controlled selection ablation because the data target also changes. Holding the
Sample-I data counts fixed gives:

```text
unselected MC vs Sample-I data chi2/ndf = 90082.25325752707
Sample-I MC vs Sample-I data chi2/ndf   = 5590.089500522007
same-target improvement                 = 16.114635239581606x
```

The selection effect is still large and worth retaining as a diagnostic, but the exact
advertised factor is not the controlled estimand it is described as.

### 4. “Shape matches” outruns the quantitative evidence

The matched Sample-I profile remains:

```text
MC B2     = 0.8669236675912432
Data B2   = 0.9442769031852253
B2 gap    = 7.735323559398211 percentage points
TVD       = 0.07735323559398212
chi2/ndf  = 5590.089500522007
```

Selection matching clearly moves the MC toward the observed profile, but the fixed Pearson
statistic strongly rejects equality under its own counting model. The summary/report language
that the gap is gone or the shapes match is therefore not authorized. The appropriate current
statement is that selection matching is an important, unweighted diagnostic sensitivity with
a substantial unresolved residual.

### 5. Provenance, uncertainty, and sensitivity are incomplete

The summary contains absolute filesystem paths but no input SHA-256 digests, source commit,
script digest, exact command, environment, weight sufficient statistics, or output manifest.
It has no weighted/unweighted ablation, no gain/threshold/coincidence-window scan, no finite-MC
uncertainty, no data covariance treatment, and no propagation of calibration or selection
uncertainty. The three committed PNGs therefore cannot serve as accepting scientific evidence.

## Better-method comparison

The minimum defensible rerun should produce both weighted and unweighted profiles, with the
weighted result designated primary and the unweighted result labelled sensitivity-only. It
should fail closed on missing, nonfinite, negative, ambiguous, or non-event-aligned weights;
record `sum_w`, `sum_w2`, Kish ESS, and weight tails; use the canonical signed-charge helper;
and hold the data target fixed for every selection ablation.

For uncertainty, a weighted multinomial or event-level bootstrap should retain the four-bin
covariance rather than treating bins independently. The final comparison should report the
full residual vector, covariance-aware statistic, total-variation distance, and a profile plot
with uncertainty bands. Gain, ADC threshold, coincidence window, max-over-tracks versus
sum-over-tracks, and weighting must be preregistered sensitivity axes. Residual attribution to
scattering or material requires a controlled rerun/ablation, not post-hoc assignment.

## Validation

Executed in Python 3.13.5 with NumPy 2.3.5 and pytest 9.0.2:

```text
python -m py_compile \
  tools/audit/audit_mv3_selection_claim.py \
  tests/test_audit_mv3_selection_claim.py \
  tools/audit/render_mv3_selection_claim_evidence.py

pytest -q tests/test_audit_mv3_selection_claim.py
7 passed in 0.07s
```

The seven regressions cover the observed fail-open contract, a corrected zero-finding fixture,
count/fraction mutation, duplicate `CL-021`, invalid UTF-8, destructive output aliasing, and
atomic JSON publication. JSON parsing and SVG XML parsing passed. Changed Python lines are no
longer than 99 characters.

The execution environment could not resolve `github.com` for a complete checkout. Exact
GitHub blobs were inspected through the authenticated connector and an executable byte-local
fixture reproduced the observed semantics. No claim is made that the new CLI was run against a
locally cloned copy of the production files.

## Required remediation contract

Before any public upgrade of `CL-021`:

1. validate and apply exactly one finite nonnegative `PrimaryWeight` per MC event;
2. use `is_charged()` for both trigger and deposition selections;
3. regenerate summary and plots from immutable MC/data bytes with full hashes and command;
4. report weighted primary plus unweighted sensitivity, weight ESS, and profile covariance;
5. hold the data target fixed in selection ablations;
6. scan gain, threshold, coincidence window, aggregation rule, and weighting;
7. remove “shape matches/gap gone” language unless preregistered acceptance criteria pass;
8. update the canonical ledger, WIKI, synthesis, executive summary, figures, and handoff
   together only after the exact-repository audit returns zero findings.

## Scientific boundary

No ROOT file was reprocessed, no weighted profile was generated, and no detector/model
parameter was changed. This unit does not establish stopping-profile closure, a physical p+d
angular model, an upstream-material correction, a calibration, PID performance, or detector
performance. It validates a fail-closed scientific-governance gate and records why the merged
follow-up cannot yet supersede canonical `CL-021`.

# MV3 Selection-Matched Stopping-Depth Diagnostic (CL-021 follow-up)

- **status:** `FLAWED` production result; producer software remediated, weighted rerun pending
- **canonical claim:** `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`
- **producer:** `scripts/studies/mv3_selection_matched.py`
- **policy:** `MV3_SELECTION_WEIGHTED_SIGNED_CHARGE_SAME_TARGET_V2`

## Evidence boundary

The tracked JSON and three PNG files were generated on 2026-07-25 by the former producer.
They are **SUPERSEDED_UNWEIGHTED_OUTPUTS** for scientific acceptance because that producer read
`PrimaryWeight`, replaced missing/nonfinite values with 1.0, then did not apply the weight to the
stopping profile. It also used a positive-charge-only mask. The retained numerical values are useful
for diagnosing the size of a trigger-selection effect, but they cannot upgrade `CL-021` or establish
physical data/MC closure.

The software correction in this repository does not regenerate the one-million-event ROOT result.
A production claim remains blocked until immutable ROOT and data inputs are rerun and the new output
contains full hashes, weight sufficient statistics, covariance, and sensitivity scans.

## What the former output demonstrated

The former unweighted diagnostic reported:

- Sample-I MC B2 fraction `0.8669236675912432` versus data `0.9442769031852253`;
- Sample-I Pearson chi-square/ndf `5590.089500522007`;
- B2 residual `7.735323559398211` percentage points;
- total-variation distance `0.07735323559398212`;
- a reported improvement of `16.602672795596263x` that changed the data target.

Holding the Sample-I data target fixed gives `16.114635239581606x`. These values show that trigger
selection materially changes the MC profile. They do **not** support the former statements that the
gap was gone or that the shapes matched.

## Corrected producer contract

The current producer now:

1. requires exactly one finite, nonnegative `PrimaryWeight` per event and never substitutes 1.0;
2. uses `ccb_mc_validation.truth.pdg.is_charged`, so both charge signs are retained;
3. publishes weighted stopping profiles as the primary MC result;
4. publishes unweighted profiles only as explicitly labelled sensitivities;
5. records `sum_w`, `sum_w2`, effective sample size, and zero-weight counts per selection;
6. computes weighted correlations and weighted entry-energy quantiles;
7. evaluates selection improvement against the same Sample-I data target in numerator and
   denominator;
8. records exact input and script SHA-256 digests, the full source commit, and the generation
   command;
9. writes JSON atomically and rejects output/input aliasing;
10. emits a non-authorizing diagnostic verdict unless the residual and goodness-of-fit gates pass.

## Required production rerun

A claim-authorizing rerun must use immutable MC ROOT, pulse-table, and event-table bytes and record:

- the corrected producer commit and command;
- one validated `PrimaryWeight` per event, with sums and effective sample size;
- weighted primary and unweighted sensitivity profiles;
- four-bin covariance or a justified multinomial/weighted alternative;
- fixed-target comparison metrics, B2 residual, total-variation distance, and Pearson diagnostics;
- preregistered scans over gain, threshold, coincidence window, weighting, and aggregation;
- controlled material and scattering-model ablations;
- regenerated JSON and PNG artifacts with hashes.

Until those gates pass, the residual attribution to scattering or material is a hypothesis and the
canonical state remains `FLAWED`.

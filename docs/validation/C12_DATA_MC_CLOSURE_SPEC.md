# C12-like Early-Peak Anomaly: Matched Data/MC Closure Specification

## Status and evidence boundary

This document defines the minimum reproducible study needed before the repository may identify the real-data early-peak anomaly as carbon-12 (C12) recoils.

Observed repository facts at the time of writing:

- Study MV6 reports 283 early-peak tracks among 87,555 truth-labelled Monte Carlo tracks, approximately 0.32%.
- The MV6 anomaly subset is C12-dominated, with approximately 55% carrying a C12 truth label.
- Repository summaries report a related real-data anomaly near 4%, more than an order of magnitude above the MC fraction.
- No inspected real-data product provides event-level particle-species truth.

Therefore the present evidence supports a **C12 candidate mechanism in MC**, not an empirical C12 identification in data. The authoritative status remains `TRUTH_LEVEL_MC_ONLY` until the closure gates below pass.

## Scientific question

Under identical waveform preprocessing and morphology selection, can the MC C12-dominated early-peak population explain the morphology, rate, detector dependence, and stability of the corresponding real-data anomaly within quantified uncertainty?

## Preregistered analysis contract

The implementation must freeze the following before inspecting final comparison plots:

1. Data run list and MC sample identifiers.
2. Event and pulse inclusion criteria, including detector/stave mapping.
3. Baseline estimator and samples used.
4. Amplitude, area, peak-sample, timing, and saturation definitions.
5. PCA training population, standardization, retained components, and random seed.
6. GMM covariance type, component-count selection rule, initialization count, convergence threshold, and random seed.
7. Definition of the early-peak/C12-like class.
8. Primary and secondary comparison metrics.
9. Acceptance thresholds and treatment of multiple comparisons.

The PCA/GMM model must not be fitted independently in data and MC for the primary closure test. The primary result must use one frozen transformation and classifier, with domain-transfer direction declared in advance. Independently fitted models may be shown only as sensitivity studies.

## Required provenance

For every input sample, record:

- repository commit SHA;
- source file paths and SHA-256 hashes;
- run numbers or MC production identifiers;
- acquisition or generator configuration;
- detector geometry and channel map version;
- number of events, tracks, and selected pulses before and after every cut;
- software environment and package versions;
- random seeds;
- exact execution command;
- generated artifact paths.

No cached table may be accepted without a traceable generating command and source hashes.

## Primary measurements

### 1. Matched anomaly fractions

For data and MC separately report:

- selected population size, `N`;
- anomaly count, `k`;
- fraction, `p = k/N`;
- two-sided 95% Wilson score interval.

For confidence level `1 - alpha` and normal quantile `z`, the Wilson interval is

\[
\frac{\hat p + z^2/(2N) \pm z\sqrt{\hat p(1-\hat p)/N + z^2/(4N^2)}}{1 + z^2/N}.
\]

Report the data/MC rate ratio and its uncertainty. Do not describe agreement using only overlapping intervals; also provide an explicit effect size and a predeclared goodness-of-fit or likelihood-ratio test.

### 2. Morphology closure

Compare data and MC within the frozen anomaly selection for at least:

- peak-sample distribution;
- integrated pulse area;
- maximum amplitude;
- rise and decay descriptors;
- PCA score distributions for every retained component;
- classifier responsibility or anomaly score;
- stave/channel occupancy;
- run dependence for data and production-seed dependence for MC.

Each distribution comparison must use identical bin edges. Show normalized overlays and a lower ratio or signed-residual panel with statistical uncertainty.

### 3. MC truth composition

Within the MC-selected anomaly class report species counts and fractions with intervals, not only the dominant label. Include protons, electrons, alpha particles, C12, other heavy ions, and unclassified entries. Quantify purity and efficiency for C12 truth separately:

- purity: `N(selected and C12) / N(selected)`;
- efficiency: `N(selected and C12) / N(all C12 in eligible population)`.

A C12-dominated selected class is not equivalent to a pure class and does not by itself identify data species.

## Mandatory sensitivity studies

Repeat the closure while varying one factor at a time:

- baseline window and estimator;
- amplitude and pulse-quality thresholds;
- number of PCA components;
- PCA standardization convention;
- GMM component count and covariance type;
- random initialization seed;
- detector/stave subset;
- run period;
- MC production seed or file ordering.

Report the full range of anomaly fractions and principal morphology metrics. Treat the variation as a model-selection or methodological systematic, not as independent statistical uncertainty.

## Negative controls and falsifiers

At minimum include:

1. A timing-shift or sample-permutation control that destroys coherent early-pulse morphology while preserving marginal ADC values.
2. A label-permutation control in MC to verify that apparent C12 enrichment is not an analysis artifact.
3. An electronic-noise-enriched control region.
4. A pile-up-enriched control region.
5. A detector/channel holdout test.
6. A run-period holdout test in data and a production-seed holdout in MC.

Failure of a falsifier must be reported and blocks species interpretation.

## Required visual artifacts

Produce version-controlled code and the following outputs:

1. `docs/figures/c12_closure_rate_comparison.pdf`
   - data and MC anomaly fractions with 95% Wilson intervals;
   - data/MC ratio and uncertainty;
   - exact selections and sample sizes in the caption.
2. `docs/figures/c12_closure_morphology.pdf`
   - matched overlays and ratio/residual panels for waveform and PCA observables.
3. `docs/figures/c12_closure_stability.pdf`
   - run, stave, preprocessing, model-choice, and seed dependence.
4. `results/c12_closure_summary.json`
   - machine-readable provenance, counts, intervals, tests, thresholds, and pass/fail gates.

Plots must identify axes, units, normalization, binning, uncertainty meaning, source hashes, generation command, and failure criteria.

## Acceptance gates

The real-data anomaly may be described as **consistent with a C12-recoil interpretation** only when all of the following hold:

- frozen preprocessing and selection reproduce the MC truth result;
- the data/MC rate difference is quantitatively explained or bounded by documented detector, generator, or selection effects;
- key morphology distributions pass preregistered closure criteria;
- the result is stable across detector, run, seed, and reasonable analysis variations;
- negative controls and holdouts pass;
- MC C12 purity and efficiency are reported with uncertainty;
- all inputs and outputs have complete provenance.

The wording **C12 identified in data** requires an independent event-level species tag or a separately validated proxy with measured confusion matrix and uncertainty. Without that evidence, repository summaries must retain `TRUTH_LEVEL_MC_ONLY` and explicitly label the data interpretation as a hypothesis.

## Current blocker

The repository does not yet contain the matched data anomaly count/denominator, frozen cross-domain classifier output, complete sample hashes, or the required closure plots and JSON result. This specification is therefore implementation-ready documentation, not a claim that closure has been achieved.

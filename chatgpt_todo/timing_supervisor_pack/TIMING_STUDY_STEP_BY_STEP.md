# CCB timing study, step by step

## Purpose

This note is written for the question a supervisor will ask at the board:

> What exactly was timed, which corrections changed the residual, why did a number near 0.1 ns
> appear despite 10 ns waveform samples, and what evidence is still required before quoting the
> timing resolution of each stave?

The answer has to distinguish four quantities that are currently mixed across project documents:

1. **A waveform pickoff error against Monte Carlo truth.** This validates an algorithm under a
   simulation model; it is not a beam-data stave resolution.
2. **A residual of one measured timestamp after predicting or centring it.** This can be useful for
   method comparison, but it is not automatically an inter-stave or absolute detector resolution.
3. **A pair residual**, such as `t_B6 - t_B4 - TOF`. This contains both stave terms and their
   covariance.
4. **An intrinsic single-stave resolution**, which needs a calibrated reference or a sufficiently
   constrained multi-detector model with closure.

The current Issue #1320 result belongs to category 3 only at the software-output level, and its
physical interpretation is blocked because the consumed polarity/frame interpretation is retracted.
It must not be used to infer category 4.

---

## One-page conclusion

### What the reported numbers mean

The current result table contains several different “small” numbers:

- `0.146 ns` is the fitted Gaussian-core width of the B4--B6 pair residual at CFD fraction 0.20.
- `0.138 ns` is the central-68% half-width of that pair residual at fraction 0.20.
- `0.096 ns` is the central-68% half-width at fraction 0.60.

They are **not single-stave resolutions**. At the same fractions the full residual RMS is about
`3.9--4.6 ns`, and the Gaussian-core fits have `chi2/ndf` around `770--830`. Thus a narrow central
population coexists with large non-Gaussian tails; the Gaussian model is not an adequate description
of the complete residual.

### Why a sub-sample crossing can exist in principle

A 10 ns sample spacing does not by itself impose a 10 ns timing quantisation. Linear interpolation
between two samples can estimate a crossing within the interval when the waveform shape, local slope,
noise, and timebase are calibrated. To first order, voltage noise contributes timing jitter of the
form

```text
sigma_t approximately sigma_voltage / |dV/dt|,
```

and correlations between adjacent samples and clock/timebase terms matter. Therefore a sub-nanosecond
interpolated timestamp is not mathematically impossible.

However, **interpolation precision is not the same as detector resolution**. It can be artificially
small when two channels share trigger/sample phase, when a deterministic digital boundary is timed,
or when a narrow central subset is reported while tails are ignored.

### Why the present 0.1 ns result is not physical

`configs/channel_polarity_v2.json` is marked
`RETRACTED_20260816_TRUNCATED_STAGING_DESYNC`. Its retraction record says that a 128-word staging
product was interpreted as eight channels with 16 samples although the true source frame had 144 words
(eight channels with 18 samples). The two-word-per-channel displacement turned channel-pedestal
boundaries into repeatable steps that were identified as B4/B6/B8 pulses. A deterministic step can
produce a highly repeatable interpolated crossing and therefore an extremely narrow pair core without
measuring scintillator timing.

The Issue #1320 producer does not fail closed on that retracted status. Its figure caption also mixes
waveform-row and unique-event counts, and its TOF-sensitivity text does not match the quantity it
computes. These are additional reasons to rebuild the analysis from the immutable raw source.

### Current stave-resolution statement

No intrinsic B4, B6, or B8 timing resolution is presently authorized from Issue #1320. With only a
B4--B6 pair,

```text
Var(t_B6 - t_B4) = sigma_B4^2 + sigma_B6^2 - 2 Cov(t_B4,t_B6),
```

so at least three unknown quantities enter one equation. Even `pair_width/sqrt(2)` works only under
an explicitly validated equal-resolution, zero-covariance, appropriate-distribution model. It is not
a general operation on `sigma68`.

---

## Review panel and division of responsibility

This analysis should be reviewed as four coupled problems rather than one histogram fit.

### Detector-timing physicist

Owns the physical timestamp definition, scintillator/SiPM pulse formation, timewalk, TOF, hit
position, path length, and whether the selected waveform component corresponds to the beam particle.
This reviewer asks: “What physical process sets this crossing?”

### DAQ and waveform specialist

Owns event framing, channel order, duplicate channels, polarity, ADC pedestal, sample-time calibration,
trigger phase, window boundaries, and truncation. This reviewer asks: “Are these samples actually the
channel and time cells we say they are?”

### Statistician

Owns the estimand, train/validation/test split, dependence-aware uncertainty, full-distribution
modelling, covariance, deconvolution, goodness-of-fit, systematic variations, and coverage. This
reviewer asks: “Which parameter is identifiable from these observations?”

### Reconstruction and reproducibility reviewer

Owns unique event keys, cut-flow accounting, producer/config versions, immutable input hashes,
fail-closed status checks, unit tests, output schema, and exact reproduction. This reviewer asks:
“Can the claim be regenerated without silently changing the population?”

The four reviewers agree on the present boundary: the 0.1--0.15 ns values are useful for diagnosing
the old algorithm output, but they do not authorize detector performance.

---

## The complete analysis chain

### Step 0 — Freeze the estimand before looking at a narrow histogram

Write the target in one line. For a B4--B6 pair the proposed observable is

```text
Delta_t_46 = t_B6 - t_B4 - TOF_46.
```

Record the sign convention once and test it. A different sign changes the median and every labelled
correlation but not the width, so a sign mismatch can survive a superficial width comparison.

Also state which width is primary:

- `sigma68 = (Q84 - Q16)/2` is robust but does not generally add in quadrature;
- Gaussian `sigma` is model-dependent and needs goodness-of-fit;
- RMS is variance-compatible but very sensitive to tails;
- tail fractions must accompany any core metric.

For intrinsic stave inference, variance is the algebraically natural quantity, but it is usable only
when the event population, tails, and covariance model are controlled. A robust pair width should
remain a pair descriptor unless a validated generative/deconvolution model says otherwise.

**Diagnostic output:** a machine-readable estimand block containing sign, units, event population,
primary metric, secondary metrics, and inference authorization.

---

### Step 1 — Validate the raw data contract

Before plotting pulses, inspect the waveform vector length for every run and compare it with the file
header and acquisition configuration.

Required checks:

1. Histogram the vector length per event and run.
2. Verify `vector_length = n_channels * samples_per_channel` exactly.
3. Compare inferred shape with the source header, not with a downstream filename.
4. Verify channel-major versus sample-major order using known pulser/duplicate behaviour.
5. Bind raw files by SHA-256 and preserve unique event identifiers.
6. Refuse any configuration whose status is `RETRACTED`.

**Pass:** one stable, source-authorized frame shape.

**Failure signature relevant to Issue #1320:** a 128-word product used as `8 x 16` while the true frame
is `8 x 18`. This shifts channel boundaries by two words per channel and can manufacture fixed steps.

**Plot:** `DATA-CONTRACT-001`, vector length and decoded boundary audit.

---

### Step 2 — Establish channel mapping, polarity, and duplicate relationships

For each channel, show raw waveforms without baseline subtraction, then baseline-subtracted waveforms
under both possible signs. A real pulse should be localized in time and should have a consistent
relationship to its duplicate readout. A pedestal boundary appears at a fixed structural index and
need not have a physical rise/fall morphology.

Required quantities:

- raw pedestal median and MAD/RMS;
- positive and negative excursion distributions;
- duplicate-channel waveform correlation and relative gain;
- pulse occupancy versus run;
- waveform overlays for random accepted and random rejected events.

Do not infer polarity only by asking which sign gives the largest excursion; a channel-boundary step
can win that test. The duplicate/readout wiring and correctly decoded frame must agree.

**Plots:** `WAVEFORM-001`, `BASELINE-001`, duplicate-correlation panels.

---

### Step 3 — Validate the baseline estimator

The existing analyses often use the median of the first four samples. That is acceptable only if the
pretrigger region is truly pre-pulse for every channel and trigger phase.

For each channel and run, plot:

- baseline mean/median;
- baseline RMS or MAD;
- linear baseline slope;
- first-four-sample residuals;
- baseline versus event number, run, temperature/current if available;
- baseline metrics versus pulse amplitude and peak sample.

Repeat the timing with alternative baseline windows that remain pretrigger. The result should move by
an amount included in the systematic budget. A baseline window contaminated by the pulse can make the
CFD threshold and crossing correlated in a non-physical way.

**Plot:** `BASELINE-001`.

---

### Step 4 — Define the pulse component before applying an amplitude cut

A multi-component waveform can have an early small local peak and a later large global peak. If the
event passes a cut on the global amplitude but timing is performed on the first local peak, the timed
component can be only a small ripple or pedestal step.

For every accepted waveform record:

- global amplitude and global peak sample;
- selected-component amplitude and peak sample;
- selected/global amplitude ratio;
- number of local peaks and their separation;
- whether the selected component has a matching duplicate-channel feature;
- component-selection failure reason.

The amplitude cut used to authorize timing must refer to the selected physical component, or the
analysis must independently prove that selected and global components are the same pulse.

**Plot:** `PULSE-ID-001`, including selected amplitude versus global amplitude and selected versus
global sample.

---

### Step 5 — Draw the CFD construction event by event

For representative low-, median-, and high-amplitude events, draw:

1. baseline-subtracted waveform samples;
2. selected peak and component interval;
3. the threshold `f * A_component`;
4. the two samples bracketing the crossing;
5. the interpolated crossing time;
6. local slope and estimated noise/slope jitter;
7. any recrossings or boundary conditions.

The linear interpolation for samples `y_k < fA <= y_{k+1}` is

```text
t_CFD = t_k + sample_period * (fA - y_k) / (y_{k+1} - y_k).
```

It is valid only when the selected segment is the intended rising edge and the denominator is safely
non-zero. Record the fractional phase within the sampling interval; later plots must show whether the
residual depends on that phase.

**Plot:** `CFD-EXAMPLE-001`.

---

### Step 6 — Build an event-level cut flow

Count unique physical events, not long-form stave rows. A two-stave pair table naturally contains two
rows per event before pivoting.

Recommended cut-flow stages:

1. raw events read;
2. frame-valid events;
3. baseline-valid channel observations;
4. physical pulse identity passed;
5. selected-component amplitude passed per stave;
6. valid CFD bracket per stave;
7. complete pair;
8. in-time/window quality;
9. track/geometry/TOF availability;
10. final frozen test sample.

For each rejection, save a named reason. The sum of accepted plus rejected categories must equal the
preceding stage.

**Issue #1320 bookkeeping warning:** `457,668` selected waveform rows correspond to about `228,834`
complete B4--B6 events. A caption calling the row count “events” overstates the event sample by a
factor of two.

**Plot:** `CUTFLOW-001`.

---

### Step 7 — Inspect each stave timestamp before taking a difference

Plot `t_B4` and `t_B6` separately, both in nanoseconds and in sample units. Then plot:

- `t_B6` versus `t_B4`;
- B6 peak sample versus B4 peak sample;
- B6 fractional CFD phase versus B4 phase;
- timestamp versus event/run;
- timestamp versus amplitude and baseline.

A genuine pair correlation should persist across amplitude, run, and phase strata. A lattice of fixed
sample-index combinations or a very narrow correlation tied to one boundary index indicates common
trigger/sample structure or a deterministic waveform artifact.

**Plots:** `TIME-001`, `PAIR-CORR-001`, `PEAKMAP-001`.

---

### Step 8 — Show the residual after every correction

Do not jump directly to the final histogram. Keep exactly the same event set and draw the residual at
successive stages:

```text
D0 = t_B6 - t_B4
D1 = D0 - constant_TOF
D2 = D1 - calibrated_channel_offset
D3 = D2 - held_out_timewalk_correction
D4 = D3 - validated_phase/position corrections
```

A constant TOF or channel offset changes the median but **cannot change a width** when the event set is
unchanged. If the width changes after a constant shift, events or weights changed silently.

The current Issue #1320 TOF correction is `0.312 ns`. Its size relative to a width is not a “TOF
uncertainty effect”; the correct sensitivity test varies the uncertain TOF model and measures the
change in the reported estimator. A uniform TOF variation should move the median and leave the width
identical.

**Plot:** `STAGE-001`, with a table of N, median, sigma68, RMS, and tails at every stage.

---

### Step 9 — Diagnose the complete residual distribution

For each frozen configuration show four views:

1. linear-y histogram over the full range;
2. log-y histogram to expose tails and secondary modes;
3. empirical CDF/quantiles;
4. QQ plot and fit pulls for any proposed parametric model.

Always report together:

- N unique pair events;
- median and mean;
- sigma68;
- RMS or standard deviation;
- Gaussian/core parameters and fit range;
- `chi2/ndf` or an unbinned goodness test;
- fractions beyond 1, 2, 5, and 10 ns;
- bootstrap intervals that respect run/block dependence.

For Issue #1320, the central width reaches `0.096 ns`, but RMS reaches `4.63 ns`, and core-fit
`chi2/ndf` remains hundreds. That is a shape diagnostic, not a one-number resolution measurement.

**Plots:** `SHAPE-001`, `FIT-001`.

---

### Step 10 — Look for timewalk and noise/slope scaling

Plot the residual against:

- B4 and B6 selected-component amplitudes;
- amplitude ratio and geometric mean;
- baseline RMS;
- CFD crossing slope on each stave;
- rise time or shape/template parameters;
- saturation and truncation flags.

A physically sensible electronics-jitter trend often improves with increasing local slope and SNR.
An ultra-narrow core that is independent of slope/noise, or is narrowest for an intermediate
amplitude band, can indicate a digital boundary/selection effect.

Any timewalk correction must be trained on designated calibration runs and evaluated on held-out runs.
Do not fit and quote the corrected width on the same event sample without accounting for model
selection and overfitting.

**Plots:** `TIMEWALK-001`, `SLOPE-001`.

---

### Step 11 — Audit sub-sample phase and trigger/window effects

For each crossing define

```text
phase = (t_CFD / sample_period) modulo 1.
```

Plot residual median and width versus B4 phase, B6 phase, phase difference, and peak-sample pair. A
sawtooth trend reveals timebase/interpolation calibration errors. A narrow result confined to one
phase cell can be common-mode cancellation rather than intrinsic timing.

Also plot results versus distance from the waveform boundaries. Exclude or separately report pulses
whose selected peak/crossing is too close to the start or end for the chosen component definition.

**Plot:** `PHASE-001`.

---

### Step 12 — Use run-held-out selection and dependence-aware uncertainty

Split by run or acquisition block before optimizing CFD fraction, component rules, timewalk model, or
cuts. A defensible pattern is:

- training runs: fit calibration and timewalk;
- validation runs: choose fraction/model complexity;
- test runs: one untouched final evaluation.

Bootstrap complete runs when enough runs are available. If there are too few runs, use contiguous
blocks and present sensitivity to block size. An IID event bootstrap treats correlated events as
independent and can make intervals too narrow.

Plot per-run and per-block medians, sigma68, RMS, tail fraction, population, and environmental
conditions. The headline must not be driven by one run.

**Plots:** `STABILITY-001`, `FRACTION-001`.

---

### Step 13 — Understand exactly what the CFD-fraction scan says

The Issue #1320 scan behaves as follows:

```text
fraction    sigma68(ns)    core sigma(ns)    RMS(ns)
0.10        0.161          0.197             3.92
0.20        0.138          0.146             4.09
0.30        0.122          0.132             4.25
0.40        0.110          0.129             4.40
0.50        0.102          0.128             4.52
0.60        0.096          0.129             4.63
```

As fraction increases, the central 68% becomes narrower while the full RMS gets wider. This is not a
monotonic improvement of one detector-resolution parameter. It shows a changing core/tail mixture or
component/phase selection. The best fraction cannot be selected from the minimum core width alone.

A legitimate fraction choice must minimize a pre-registered loss on validation data, for example a
combination of central width, tail probability, efficiency, bias, and stability. The final test-set
result is then quoted once.

**Plot:** `FRACTION-001`; the included script generates the historical scan and its RMS/core mismatch.

---

### Step 14 — Determine whether individual stave resolutions are identifiable

#### One pair

For B4--B6 alone,

```text
V_46 = sigma_4^2 + sigma_6^2 - 2 C_46.
```

One equation cannot determine `sigma_4`, `sigma_6`, and `C_46`. Even setting covariance to zero leaves
two unknown variances in one equation.

#### Three independent Gaussian detectors

If B4, B6, and B8 are all measured on the same physical event population and covariance is explicitly
validated as negligible, then

```text
V_46 = v4 + v6
V_48 = v4 + v8
V_68 = v6 + v8
```

and

```text
v4 = (V_46 + V_48 - V_68)/2
v6 = (V_46 + V_68 - V_48)/2
v8 = (V_48 + V_68 - V_46)/2.
```

Negative solutions or failure to reproduce held-out pair widths are model-failure diagnostics, not
values to clip silently. With more staves, use a non-negative/likelihood fit and propagate pair
covariances.

#### With common-mode jitter

A common trigger/clock term can cancel from a pair difference. Therefore a very narrow pair residual
can coexist with a much worse absolute time resolution. Estimate common and independent components
with a hierarchical covariance model, an external reference, or controlled calibration pulses.

#### Robust widths

The algebra above applies to variances under the specified model. `sigma68` does not generally obey
that addition law. The included fixed-seed counterexamples show that `pair sigma68 / sqrt(2)` is
approximately correct only for the special equal-independent-normal case and can be badly biased for
unequal, correlated, or non-Gaussian staves.

**Plots:** `PAIR-MATRIX-001`, `DECONV-001`.

---

### Step 15 — Prove closure before publishing a stave number

Build an injection/recovery test that passes through the same framing, baseline, component selection,
CFD, cuts, calibration, and fitting as data. Vary independently:

- per-stave intrinsic jitter;
- common clock/trigger jitter;
- adjacent-sample voltage correlation;
- timebase cell non-uniformity;
- amplitude/timewalk and saturation;
- pulse pile-up and multi-component waveforms;
- boundary truncation;
- non-Gaussian tails;
- run drift and missing channels.

The inferred stave parameters and intervals must recover injected truth over a grid, not only at one
nominal point. Coverage and failure modes must be documented. Monte Carlo truth closure near 0.15 ns
shows that the algorithm can work under that simulation; it does not validate the historical beam-data
frame or map.

**Plot:** `DECONV-001` plus coverage curves.

---

### Step 16 — Build the systematic uncertainty budget

At minimum include variations of:

- frame/header interpretation and channel map;
- polarity and duplicate-channel choice;
- baseline estimator/window;
- component selector and component-amplitude cut;
- CFD fraction and interpolation method;
- sample-time calibration and phase correction;
- timewalk model and train/test split;
- TOF/path-length model;
- position/track selection;
- run/block population;
- residual model, fit range, and tail treatment;
- covariance/deconvolution model.

Report correlations where possible. A statistical bootstrap interval alone is not the uncertainty on
stave performance.

**Plot:** `SYSTEMATICS-001`, preferably a signed shift/variance-component summary rather than only a
quadrature total.

---

## How the historical 0.1 ns core was reached

The software chain can be summarized as:

```text
8 x 16 interpreted waveform product
  -> first-four-sample baseline
  -> polarity from channel_polarity_v2.json
  -> global amplitude > 1000 ADC event/channel selection
  -> first-local-peak component selection
  -> component CFD at fractions 0.10 ... 0.60
  -> global peak-sample offsets (B4=6, B6=7)
  -> B4-B6 complete-pair lock
  -> subtract 0.312 ns constant TOF
  -> form pair residual
  -> quote central-68% width and a Gaussian+constant core fit
```

The narrow number is obtained because the central part of that residual is extremely concentrated.
The simultaneously broad RMS and rejected Gaussian fit show that the distribution contains another
large scale. The retraction explains a concrete mechanism: fixed pedestal-boundary steps in the
misframed waveform product generate repeatable crossings and common structure between channels. The
result therefore tells us about that analysis artifact, not about photon/scintillator timing.

---

## What can be stated to the supervisor now

A scientifically correct summary is:

> We reproduced the logic behind the reported 0.1--0.15 ns numbers and established that they are
> central/core widths of a B4--B6 pair residual, not individual stave resolutions. The full residual
> is strongly non-Gaussian, and the consumed polarity/frame interpretation is now explicitly retracted
> because a truncated 128-word staging frame was decoded as 8 x 16 instead of the true 8 x 18 source.
> Therefore the sub-nanosecond beam-data result is an analysis artifact and cannot be used as detector
> performance. We have frozen a diagnostic sequence that starts with frame and pulse-identity plots,
> then shows CFD construction, cut flow, correction stages, tails, phase/timewalk/stability, and finally
> covariance-aware multi-pair deconvolution. A stave resolution will be quoted only after correctly
> decoded data contain at least three connected physical timing measurements or a calibrated external
> reference and the inference closes on simulation/injection.

---

## Commands

From the repository root:

```bash
python chatgpt_todo/timing_supervisor_pack/timing_result_diagnostics.py \
  --result reports/issue_1320_timing/result.json \
  --polarity-map configs/channel_polarity_v2.json \
  --out chatgpt_todo/timing_supervisor_pack/generated \
  --allow-gated-exit-zero
```

The producer intentionally records:

```text
single_stave_resolution_authorized = false
```

and generates the historical fraction scan, non-Gaussianity ratio, fit-quality plot, fixed-seed
`sqrt(2)` counterexamples, and the inference gate.

Self-test:

```bash
python chatgpt_todo/timing_supervisor_pack/timing_result_diagnostics.py --self-test
```

---

## Primary-method references

- E. Delagnes, *What is the theoretical time precision achievable using a dCFD algorithm?*,
  arXiv:1606.05541. Derives digital threshold/CFD interpolation jitter including correlations between
  samples and clock/timebase terms.
- D. Breton et al., *Measurements of timing resolution of ultra-fast silicon detectors with the
  SAMPIC waveform digitizer*, arXiv:1604.02385. Demonstrates sub-sample timing with CFD/refined CFD
  and cross-correlation when the digitizer is calibrated and operated at multi-GS/s.
- P. W. Cattaneo et al., *Time resolution of time-of-flight detector based on multiple scintillation
  counters readout by SiPMs*, arXiv:1511.03891. Illustrates measured timing improvement from combining
  multiple counters and the need to define the combined estimator.

These references support the method principles; none validates the CCB waveform framing, channel map,
or detector resolution. Those require source-bound CCB data and closure.

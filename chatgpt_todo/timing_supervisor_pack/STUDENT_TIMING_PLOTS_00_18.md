# Raw-waveform timing from zero: a plot-by-plot student walkthrough

## What the student should be able to explain at the end

Starting from a ROOT file that contains digitized waveforms, the student should be able to answer five questions without jumping directly to a fitted number:

1. **Are the waveform samples decoded correctly?**
2. **Does the selected feature correspond to a real detector pulse?**
3. **How is one timestamp obtained from discrete samples?**
4. **How does a set of timestamps become a pair-residual distribution near 0.1 ns?**
5. **What additional information is required to turn pair residuals into the timing resolution of each stave?**

The central lesson is that a narrow distribution is the *last* step of the argument, not the first. A physical pulse and a deterministic data-format boundary can both produce a repeatable interpolated crossing. The earlier plots must distinguish them.

---

## The review panel

The tutorial treats timing as four connected problems. A result should not be promoted until all four reviewers agree on what the plotted quantity means.

| Reviewer | Background | Main question |
|---|---|---|
| Detector-timing physicist | Scintillator, SiPM, photon statistics, time of flight | Which physical process sets the timestamp? |
| DAQ and waveform specialist | Digitizer framing, channel mapping, polarity, clock and sampling cells | Are these samples really the channel and time cells claimed? |
| Statistician | Estimands, tails, covariance, uncertainty and deconvolution | Which resolution parameter is identifiable from these data? |
| Reconstruction/reproducibility reviewer | Event identity, software tests, provenance and manifests | Can the result be regenerated without silently changing the population? |

For every stage below, the tutorial records what each reviewer expects to see and what observation would stop the analysis.

---

# Part I — Vocabulary before code

## 1. Sample interval, timestamp, residual and resolution are different

Suppose the digitizer stores one voltage every 10 ns.

- The **sample interval** is 10 ns.
- A **timestamp** is an estimate of when a pulse crossed a defined level. Interpolation can place it between stored samples.
- A **pair time difference** is the difference between timestamps from two staves.
- A **pair residual** is that difference after subtracting known offsets such as time of flight.
- A **single-stave resolution** is an inferred property of one stave. It does not follow from one pair width unless additional assumptions or measurements are supplied.

For staves \(i\) and \(j\), define

\[
\Delta t_{ij}=t_j-t_i-t_{\mathrm{TOF},ij}-\delta_{ij},
\]

where \(\delta_{ij}\) is a calibrated electronic/channel offset. Its variance is

\[
\operatorname{Var}(\Delta t_{ij})
=\sigma_i^2+\sigma_j^2-2\operatorname{Cov}(t_i,t_j).
\]

One pair provides one equation. In general it contains two stave variances and a covariance term, so it cannot determine two individual stave resolutions.

## 2. Why a 10 ns sampler can produce a 0.1 ns timestamp difference

Let two samples on a rising edge be \((t_k,y_k)\) and \((t_{k+1},y_{k+1})\). For a constant-fraction threshold \(fA\), linear interpolation gives

\[
t_{\mathrm{CFD}}
=t_k+(t_{k+1}-t_k)
\frac{fA-y_k}{y_{k+1}-y_k}.
\]

The answer is continuous even though the inputs are discrete. To first order, voltage noise produces timing jitter roughly proportional to

\[
\sigma_t \sim \frac{\sigma_V}{|dV/dt|}.
\]

Therefore a steep, high-signal-to-noise edge can be timed much more precisely than one sample interval. Sample correlations, clock jitter, non-uniform sampling cells and pulse-shape fluctuations must still be included. Digital waveform timing experiments have demonstrated sub-sample precision when those effects are controlled.

The same mathematics can also time a non-physical step caused by a channel boundary. This is why waveform identity and frame validation come before the residual histogram.

---

# Part II — The complete raw-data analysis

## Step 0 — Freeze the question and the data split

Write the estimand before optimizing anything:

```text
primary pair: B4-B6
primary residual: t_B6 - t_B4 - TOF_B4B6 - frozen_channel_offset
primary width: sigma68 = (Q84-Q16)/2
secondary widths: RMS and fitted core sigma
mandatory tail fractions: |residual-median| > 1, 2, 5 and 10 ns
```

Divide runs before tuning:

- **Calibration runs:** determine baselines, fixed channel offsets, pulse templates and timewalk corrections.
- **Validation runs:** choose the CFD fraction and model complexity.
- **Test runs:** evaluate the frozen method once.

Never choose the best fraction on the same events used for the final headline.

### Plot 00 — Run map

Show a table or timeline with every run labelled calibration, validation, test or excluded. Include event counts and file hashes.

**Pass:** the split is fixed, complete and disjoint.

**Stop:** missing requested runs, overlapping calibration/test sets, or unexplained exclusions.

---

## Step 1 — Prove the waveform frame before reshaping

For every event, count the scalar words in the waveform vector. Do this *before* stacking events.

For the source currently used by the CCB S00 configuration, the declared frame is

```text
8 channels x 18 samples = 144 words per event.
```

A batch-level reshape is dangerous. For example, nine 128-word events contain 1152 words, which can be reshaped into eight false 144-word events without raising a numerical error. Event boundaries are then mixed.

### Plot 01 — Word-count histogram

Horizontal axis: words per event. Vertical axis: number of events.

**Pass:** one spike at the independently authorized source width.

**Stop:** more than one width, any malformed event, or a width chosen only because it reshapes cleanly.

### Plot 02 — Channel-boundary audit

Draw the flattened 144-word event and vertical lines at 18-word boundaries. Then draw the same event under any proposed legacy 128-word/8x16 interpretation.

**Pass:** boundaries coincide with stable channel pedestals and known duplicate pairs.

**Stop:** a pulse-like step appears exactly where a misframed block crosses from the tail of one physical channel into the head of another.

### Required provenance

Record, at minimum:

```text
absolute source pathname
SHA-256
file size
run number
ROOT tree and branch names
number of events
word-count histogram
channel count
samples per channel
sample period and its source
producer version and configuration hash
```

---

## Step 2 — Establish channel mapping and polarity

Do not begin with an amplitude histogram. Begin with raw waveforms for all channels.

For each physical stave, compare its main and duplicate readout channels. A real pair should show the same localized pulse with the expected relative sign and gain. A pedestal-boundary step can fool an algorithm that simply chooses whichever sign creates the largest excursion.

### Plot 03 — Raw waveform atlas

For every channel, show:

- 20 randomly selected events;
- the median waveform;
- the central 68% envelope;
- the nominal channel and duplicate label;
- acquisition-window boundaries.

**Pass:** a localized pulse with a plausible rise and fall appears on the intended channel and its duplicate.

**Stop:** the feature is a fixed step, occurs at the same structural sample in almost every event, or disappears in the correctly decoded frame.

### Plot 04 — Duplicate-channel correlation

Plot main-channel amplitude versus duplicate amplitude after applying their signed polarities. Also show waveform correlation and peak-time difference.

**Pass:** one physical population with stable gain ratio and timing.

**Stop:** no correlation, correlation only through a pedestal offset, or a relationship that changes when the frame is corrected.

---

## Step 3 — Validate the baseline

A timestamp is measured relative to the baseline, so a biased baseline changes both pulse amplitude and threshold.

For the first-four-sample median estimator, calculate per event and channel:

```text
baseline median
baseline RMS or MAD
linear baseline slope
maximum excursion inside the baseline window
```

### Plot 05 — Baseline distributions

Show baseline level, RMS and slope by channel and run.

**Pass:** one stable population, small slope and no pulse contamination.

**Stop:** multiple modes, run drift, a pulse inside the baseline window, or a baseline correlated with pulse amplitude/time.

### Plot 06 — Baseline stability versus event number

Use a run/block plot rather than hiding time ordering in one histogram.

**Pass:** fluctuations are consistent with noise and slow changes are calibrated or included as systematics.

**Stop:** abrupt jumps align with file boundaries, digitizer resets or temperature changes.

---

## Step 4 — Identify the pulse component

A waveform may contain an early ripple and a later large pulse. It is unsafe to pass an event using the global amplitude while timing a different, much smaller first local maximum.

For every event, store:

```text
global peak amplitude and sample
selected component amplitude and sample
selected/global amplitude ratio
number of eligible local peaks
component selection status
whether the duplicate channel contains a matching component
```

### Plot 07 — Selected versus global amplitude

**Pass:** points cluster near the diagonal, or a separately validated component class is visible.

**Stop:** the selected component is often a small fraction of the global peak while the global peak supplies the amplitude cut.

### Plot 08 — Selected versus global peak sample

**Pass:** the selected component corresponds to the same physical pulse family.

**Stop:** fixed early components are selected while the large pulse occurs much later.

The repository’s canonical `first_local_peak` implementation correctly exposes its current evidence status as a hypothesis rather than automatically declaring physical component identity. Raw-data use must close this gate with waveform and duplicate-channel evidence.

---

## Step 5 — Draw the CFD construction for individual events

For representative low-, medium- and high-amplitude pulses, show:

1. baseline-subtracted signed samples;
2. selected pulse component;
3. selected amplitude \(A\);
4. threshold \(fA\);
5. two bracketing samples;
6. interpolated crossing;
7. local slope;
8. fractional sample phase;
9. status code.

### Plot 09 — CFD event examples

Include accepted events and every failure class:

```text
OK
NO_CROSSING_IN_WINDOW
NO_CROSSING
NONPOSITIVE_BRACKET
INVALID_AMPLITUDE
```

**Pass:** the crossing lies on the intended rising edge with a positive, well-measured slope.

**Stop:** crossing at the first sample, recrossing, flat denominator, wrong component, or a threshold already exceeded before the acquisition window.

---

## Step 6 — Build a unique event-level timing table

The minimum row identity is

```text
(run, event, stave)
```

One physical B4-B6 event naturally produces two stave rows. Do not call both rows separate events.

Recommended columns:

```text
run, event, stave, channel
raw-file hash and entry index
baseline, baseline RMS, baseline slope
global amplitude and peak sample
selected amplitude and peak sample
CFD fraction, time, status, bracketing samples
crossing slope and fractional phase
all cut flags and rejection reason
```

### Plot 10 — Cut flow

Count unique physical events at every stage:

```text
raw frame valid
baseline valid
physical pulse identified
selected-component amplitude pass
valid CFD on each required stave
complete pair
track/geometry and TOF available
frozen test population
```

**Pass:** accepted plus rejected categories reconcile exactly to the previous stage.

**Stop:** waveform rows labelled as events, duplicate event keys, or unexplained losses.

---

## Step 7 — Understand individual timestamps before subtracting them

### Plot 11 — Per-stave timestamp distributions

Show timestamps in both nanoseconds and sample units.

Look for:

- boundary piles;
- integer-sample spikes;
- multiple trigger-phase modes;
- unexpected channel-dependent offsets.

### Plot 12 — Timestamp correlation \(t_j\) versus \(t_i\)

A real common particle time creates a diagonal correlation. A data-format artifact may create a discrete lattice tied to fixed sample indices.

### Plot 13 — Peak/crossing sample map

Plot peak sample of stave \(j\) versus stave \(i\), and repeat for the CFD bracket.

**Pass:** correlations remain physical across run and amplitude strata.

**Stop:** the narrow residual is confined to one fixed sample-pair cell or one channel boundary.

---

## Step 8 — Construct the residual one correction at a time

Using exactly the same event set, store:

```text
D0 = t_B6 - t_B4
D1 = D0 - constant TOF
D2 = D1 - frozen electronic/channel offset
D3 = D2 - held-out timewalk correction
D4 = D3 - validated phase or position correction
```

### Plot 14 — Residual correction stages

For each stage show \(N\), median, \(\sigma_{68}\), RMS and tail fractions.

A constant TOF or offset changes the median, not the width. A width change after a constant subtraction means the event population, weights or code path changed.

---

## Step 9 — Display the complete residual, not only the central peak

At the frozen analysis fraction, produce four views.

### Plot 15 — Full residual on a linear vertical scale

This shows the dominant population.

### Plot 16 — Full residual on a logarithmic vertical scale

This makes rare tails and satellite modes visible.

### Plot 17 — Zoomed central core

Mark the median and \(Q_{16},Q_{84}\). The central width is

\[
\sigma_{68}=\frac{Q_{84}-Q_{16}}{2}.
\]

### Plot 18 — Empirical CDF, QQ plot and fit pulls

Do not quote a Gaussian sigma without checking the model.

Report together:

```text
N unique pair events
mean and median
sigma68
full RMS or standard deviation
fitted core sigma and fit range
chi2/ndf or another goodness test
tail fractions beyond 1, 2, 5 and 10 ns
run/block-aware uncertainty interval
```

A 0.1 ns central width and a 4 ns RMS describe a mixture with two very different scales. Calling that complete distribution “a 0.1 ns resolution” is incorrect.

---

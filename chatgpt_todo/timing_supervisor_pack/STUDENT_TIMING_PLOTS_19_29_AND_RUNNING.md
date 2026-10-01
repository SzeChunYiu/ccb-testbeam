# Raw-waveform timing from zero — plots 19–29, execution, and publication

This continues `STUDENT_TIMING_PLOTS_00_18.md`.

## Step 10 — Scan the CFD fraction without selecting on the test sample

### Plot 19 — Fraction scan

For every fraction plot:

- efficiency;
- median;
- \(\sigma_{68}\);
- full RMS;
- tail fractions;
- core fit quality;
- run-to-run stability.

Choose the fraction on calibration/validation data using a predeclared loss. The loss may combine width, bias, efficiency, tails and stability. Then evaluate the test sample once.

### How the historical CCB number near 0.1 ns appeared

The live Issue #1320 table contains:

| CFD fraction | pair \(\sigma_{68}\) | fitted core sigma | full RMS | core \(\chi^2/\mathrm{ndf}\) |
|---:|---:|---:|---:|---:|
| 0.10 | 0.1611 ns | 0.1290 ns | 3.917 ns | 720.3 |
| 0.20 | 0.1460 ns | 0.1242 ns | 3.947 ns | 790.5 |
| 0.30 | 0.1316 ns | 0.1209 ns | 4.024 ns | 827.3 |
| 0.40 | 0.1183 ns | 0.1288 ns | 4.158 ns | 827.5 |
| 0.50 | 0.1065 ns | 0.1293 ns | 4.355 ns | 813.0 |
| 0.60 | **0.09635 ns** | 0.1291 ns | **4.630 ns** | 766.0 |

The central quantile narrows as the fraction rises, while the full RMS becomes broader. The map/frame interpretation used for this historical result is now retracted, so these numbers are retained as an analysis-artifact diagnostic, not detector performance.

---

## Step 11 — Diagnose timewalk and amplitude selection

### Plot 20 — Residual versus amplitude on each stave

### Plot 21 — Residual versus amplitude ratio and geometric mean

A residual trend means amplitude-dependent timing remains. Fit any correction on calibration runs only, freeze it, and test it on independent runs.

Compare fixed-threshold timing with CFD. A leading-edge threshold normally has stronger timewalk; CFD should reduce it when pulse shapes are stable.

**Stop:** a “correction” that improves only the same events used to fit it.

---

## Step 12 — Check the noise/slope expectation

### Plot 22 — Residual width versus crossing slope

### Plot 23 — Residual versus baseline RMS

A physical electronics-jitter contribution should improve as the local slope or signal-to-noise ratio increases. An ultra-narrow width independent of slope and noise can indicate a deterministic digital feature rather than pulse timing.

Also compare the observed scale with the event-level proxy

\[
\widehat{\sigma}_{t,\mathrm{noise}}
\approx \frac{\sigma_{V,\mathrm{baseline}}}{|dV/dt|}.
\]

This is a diagnostic, not a complete detector model; photon statistics and timebase terms remain.

---

## Step 13 — Audit sub-sample phase and sampling-cell calibration

Define

\[
\phi_i=\left(\frac{t_i}{T_{\mathrm{sample}}}\right)\bmod 1.
\]

### Plot 24 — Residual median and width versus phase

Show dependence on \(\phi_i\), \(\phi_j\), phase difference and physical sampling-cell index where available.

**Pass:** no sawtooth bias or narrow result restricted to one phase bin.

**Stop:** a fraction-dependent phase pattern or sampling-cell discontinuity.

---

## Step 14 — Test run and block stability

### Plot 25 — Per-run forest plot

For each run show event count, median, \(\sigma_{68}\), RMS and tail fraction with intervals.

### Plot 26 — Time-ordered block plot

Use contiguous blocks to reveal drift within a run.

Resample whole runs when enough runs exist. Otherwise use block bootstrap with a justified block length. Event-IID bootstrap generally understates uncertainty when events share run conditions.

**Stop:** one run dominates the headline or the width changes beyond its uncertainty across blocks.

---

## Step 15 — Form the all-pair matrix

With B2, B4, B6 and B8, measure every connected pair using the same frozen event definition.

### Plot 27 — Pair-width matrix

Display both variance-compatible widths and robust/tail metrics. Check whether every pair uses the same event population.

Under the special model of independent Gaussian stave errors,

\[
V_{ij}=v_i+v_j,
\]

where \(V_{ij}=\operatorname{Var}(\Delta t_{ij})\) and \(v_i=\sigma_i^2\). For three staves,

\[
\begin{aligned}
v_1&=(V_{12}+V_{13}-V_{23})/2,\\
v_2&=(V_{12}+V_{23}-V_{13})/2,\\
v_3&=(V_{13}+V_{23}-V_{12})/2.
\end{aligned}
\]

For more staves, fit non-negative variances and test closure. Negative unconstrained solutions, large fit residuals or pair-dependent populations indicate model failure.

Do not substitute \(\sigma_{68}\) into variance equations without a validated generative model. Quantile widths are not generally quadrature-additive.

---

## Step 16 — Model common-mode covariance

A common trigger or clock term can cancel from pair differences:

\[
t_i=t_0+c+\epsilon_i.
\]

Then

\[
t_j-t_i=\epsilon_j-\epsilon_i,
\]

so the pair residual can look excellent even if the absolute timestamp contains a large common term \(c\).

### Plot 28 — Covariance/correlation matrix

Use calibration pulses, an external reference or a hierarchical model to separate common and stave-specific terms.

**Stop:** quoting absolute stave timing from pair differences while common-mode jitter is unconstrained.

---

## Step 17 — Prove injection/recovery closure

Run synthetic or Monte Carlo samples through the *same* framing, baseline, component selection, CFD, cuts and fit used for data.

Vary:

```text
intrinsic stave jitter
common clock jitter
voltage noise and adjacent-sample correlation
sampling-cell non-uniformity
pulse amplitude and shape
timewalk
multi-pulse contamination
boundary truncation
non-Gaussian tails
run drift and missing channels
```

### Plot 29 — Injected versus recovered stave resolution

Show the identity line and coverage of the reported intervals.

The tutorial’s clean synthetic lane injects

```text
B2 0.055 ns
B4 0.065 ns
B6 0.075 ns
B8 0.090 ns
```

and, for a fixed 10,000-event teaching sample, recovers approximately

```text
B2 0.057 ns
B4 0.065 ns
B6 0.077 ns
B8 0.090 ns.
```

The B4-B6 pair has \(\sigma_{68}\approx0.100\) ns and RMS \(\approx0.101\) ns. In this lane the pulse identity and injected truth are known, the pair matrix closes and the full distribution has the same scale as its central core. This is a valid *method-closure demonstration*, not beam-data performance.

---

## Step 18 — Reproduce the dangerous look-alike

A good student tutorial must also show a false positive.

The provided artifact lane:

1. generates a correct 8x18 frame;
2. puts real pulses only on B2 and its duplicate;
3. truncates each 144-word event to 128 words;
4. reshapes it as 8x16;
5. applies the historical retracted polarity pattern;
6. times the resulting pedestal-boundary steps.

At CFD60, the fixed teaching sample gives approximately

```text
central sigma68 = 0.097 ns
full RMS        = 4.06 ns
tail > 10 ns    = 1.0%
```

The central number resembles the physical synthetic lane, but the waveform atlas, frame comparison, log residual and pulse-identity plots show that it has the wrong origin. Every artifact plot is watermarked `NON_PHYSICAL_DELIBERATE_TRUNCATION_ARTIFACT`.

This side-by-side comparison is the most important teaching result:

| Observation | Clean physical lane | Misframed artifact lane |
|---|---|---|
| Central B4-B6 width | about 0.1 ns | about 0.1 ns |
| Full RMS | about 0.1 ns | about 4 ns |
| Real localized B4/B6 pulses | yes | no |
| Correct source frame | yes | no |
| Pair matrix closes to injected truth | yes | no physical interpretation |
| Publishable beam result | no, synthetic closure only | no, explicit artifact |

---

# Part III — Running the tutorial

## 1. Bounded self-test

```bash
python chatgpt_todo/timing_supervisor_pack/student_timing_walkthrough.py self-test
```

Expected output:

```text
self-test: PASS
```

## 2. Generate the complete teaching atlas

```bash
python chatgpt_todo/timing_supervisor_pack/student_timing_walkthrough.py demo \
  --out reports/student_timing_walkthrough \
  --events 10000 \
  --seed 20260901
```

The output contains:

```text
STUDENT_REPORT.md
analysis_summary.json
*_pair_metrics.csv
*_cutflow.csv
plots/*.png
plots/*.svg
```

## 3. Run on raw ROOT files

Copy and edit `student_timing_config.example.yaml`, then run:

```bash
python chatgpt_todo/timing_supervisor_pack/student_timing_walkthrough.py raw \
  --config chatgpt_todo/timing_supervisor_pack/student_timing_config.example.yaml \
  --out reports/student_timing_raw
```

The raw lane refuses a retracted polarity status in an authorising analysis and validates every event width before stacking. The following gates default to false until independently documented:

```text
source_frame_authorized
component_identity_authorized
allow_independent_zero_covariance_resolution_model
```

This lets the student generate diagnostics without accidentally promoting them to a stave-resolution claim.

---

# Part IV — Minimum publication checklist

A beam-data statement such as “the stave timing resolution is 0.1 ns” requires all of the following:

- source-bound, immutable raw files and per-event frame validation;
- correct channel map, polarity and sample-time calibration;
- waveform evidence that each timed feature is a physical pulse;
- event-level cut flow with unique composite keys;
- a pre-registered calibration/validation/test split;
- full residual shape, tails and fit-quality reporting;
- timewalk, amplitude, slope, phase and run-stability closure;
- at least three connected physical timing measurements or a calibrated external reference;
- an explicit covariance/common-mode model;
- non-negative multi-pair deconvolution with held-out pair closure;
- simulation/injection recovery and interval coverage;
- a systematic uncertainty budget;
- no use of `pair_width/sqrt(2)` unless equal variances, zero covariance and the width algebra are independently validated.

Until those gates pass, report exactly what was measured:

```text
B4-B6 pair residual under the stated reconstruction and event selection
```

—not an intrinsic stave resolution.

---

# Primary method references

1. E. Delagnes, *What is the theoretical time precision achievable using a dCFD algorithm?*, arXiv:1606.05541. Digital interpolation, voltage-noise/slope timing and correlations between samples.
2. D. Breton et al., *Measurements of timing resolution of ultra-fast silicon detectors with the SAMPIC waveform digitizer*, arXiv:1604.02385. Experimental demonstration of sub-sample waveform timing using CFD and cross-correlation under calibrated conditions.
3. P. W. Cattaneo et al., *Time resolution of time-of-flight detector based on multiple scintillation counters readout by SiPMs*, arXiv:1511.03891. Multiple-counter timing, reference measurements and the conditional square-root improvement for independent measurements.

These papers justify timing-method principles. They do not validate the CCB frame, channel identity or detector resolution; those require source-bound CCB evidence.

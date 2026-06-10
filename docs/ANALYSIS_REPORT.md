# CCB Test-Beam Analysis Report

## Abstract

This report synthesizes the current CCB test-beam study program into a single
human-readable analysis chapter. The source material is the reproduced
raw-ROOT gate, the rolling scoreboard in `reports/SUMMARY.md`, the
physics-organized synthesis in `FINDINGS_SYNTHESIS.md`, the overview documents
in `docs/`, and a bounded set of representative per-study reports. All quoted
results are data-driven. No Monte Carlo truth, per-event particle identity, or
absolute deposited-energy truth is assumed.

The central conclusions are:

1. The raw B-stack selected-pulse population is reproducible from ROOT at
   exactly 640,737 pulse records with the even-channel HRDv gate
   `A > 1000 ADC`.
2. Timing is mostly explained by conventional amplitude timewalk once the
   traditional comparator is strengthened. A first ridge residual model beat a
   weak template baseline, but leave-one-run-out analytic timewalk and waveform
   ridge are statistically tied at about 1.55 ns pairwise sigma68.
3. B2-containing timing residuals and covariances are a detector-local,
   topology-driven problem. Downstream timing is much cleaner than the
   terminal-B2 population.
4. The old pile-up headline rate of about 4.2 MHz depends on an assumed
   90 ns live window. A direct waveform live-time measurement gives
   live10 = 124.79 ns [123.33, 126.36], rescaling the same occupancy criterion
   to about 3.05 MHz.
5. ML is strongest when the target is independent of the input waveform but
   shape contains recoverable information: duplicate-readout amplitude/charge,
   artificial saturation recovery, two-pulse synthetic recovery, anomaly
   triage, and compact representation learning.
6. ML is not adopted where the apparent target is a disguised function of the
   inputs or where a transparent physics model is already competitive:
   timewalk adoption, pile-up rate, PID, and absolute energy remain limited by
   labels and systematics.

## 1. Experimental Setup and Data

The experiment used a 190 MeV proton beam at the Cyclotron Centre Bronowice
incident on a CD2 target. Charged particles were recorded by trigger
scintillators, a TPC, and two HRD scintillator range stacks approximately
1 m from the target. The principal analysis uses the B-stack staves B2, B4,
B6, and B8. The A-stack channels A1 and A3 form an independent but lower
statistics cross-check.

Each HRD pulse is an 18-sample waveform with nominal 10 ns sample spacing. The
readout is one-ended through a wavelength-shifting fiber, so absolute position
and propagation effects are not independently measured pulse by pulse. The
analysis therefore focuses on same-particle inter-stave residuals, duplicate
readout closure, and run-held-out comparisons rather than absolute timing or
truth-level energy labels.

### 1.1 Raw Inputs

The data are outside git and exposed in this workspace through `data`, a
symlink to `/home/billy/ccb-data/extracted`. The reduced ROOT input set is:

| Input | Location | Role |
|---|---|---|
| B-stack raw ROOT | `data/root/root/hrdb_run_NNNN.root` | Primary B2/B4/B6/B8 waveform analysis |
| A-stack raw ROOT | `data/root/root/hrda_run_NNNN.root` | A1/A3 cross-check |
| Sorted files | `data/sorted-a`, `data/sorted-b` | Historical report inputs and diagnostics |

The root bundle is not the only copy of the original data. `DATA.md` records
the archive hashes and layout. The working rule in all serious studies is to
reproduce counts from raw `HRDv`, not from sorted proxy branches.

### 1.2 Run Samples

The current documentation follows the newer report split:

| Sample | Stack | Runs | Calibration | Analysis | Interpretation |
|---|---|---|---|---|---|
| I | B | 31-57 | 31-42, excluding absent/problem runs as documented | 44-57 | D-enriched, mostly terminal-B2 |
| II | B | 58-65 | 64 | 58-63, 65 | p-enriched, penetrating downstream timing reference |
| III | A | Same period as Sample I | 31-42 | 44-57 | A-stack analogue of Sample I |
| IV | A | Same period as Sample II | 64 | 58-63, 65 | Low-statistics A-stack analogue of Sample II |

The B-stack selected-pulse counts are strongly topology dependent. Sample I
analysis contains 252,266 selected B pulses, dominated by B2
(241,422 selected pulses in the overview). Sample II analysis contains 125,096
selected B pulses with more downstream support: B2 = 88,213, B4 = 21,229,
B6 = 11,148, and B8 = 4,506 in the raw-ROOT reproduction tables.

### 1.3 Reproduction Gate

The reproducible gate is:

1. Read `h101/HRDv` from B-stack raw ROOT.
2. Reshape the waveform into the physical channel layout.
3. Use even physical B channels B2/B4/B6/B8, mapped as 0/2/4/6 in the relevant
   reduced files.
4. Estimate the baseline as the median of waveform samples 0-3.
5. Define `A = max_j(w_j - median(w_0,...,w_3))`.
6. Select pulses with `A > 1000 ADC`.

This reproduces the canonical count exactly:

| Quantity | Value |
|---|---:|
| Selected B-stave pulse records | 640,737 |
| Sample II analysis selected pulses | 125,096 |
| Sample II analysis B2/B4/B6/B8 | 88,213 / 21,229 / 11,148 / 4,506 |

This count gate appears repeatedly in the per-study reports and is the entry
condition for downstream claims. When the target is this deterministic
threshold itself, ML is not useful; it can only approximate the known rule.

## 2. Pulse Reconstruction

The pulse reconstruction is intentionally conventional, because it defines the
strong traditional comparator that ML must beat.

### 2.1 Baseline and Amplitude

For waveform samples `w_j`, the seed baseline is

```text
b0 = median(w0, w1, w2, w3)
y_j = w_j - b0
A0 = max_j y_j .
```

The adaptive positivity-constrained pedestal lowers the baseline only as much
as needed to keep non-jagged corrected samples above

```text
-epsilon(A0),  epsilon(A0) = max(25 ADC, 0.015 A0).
```

This adaptive rule guarantees zero post-correction violations by construction.
The S16 validation therefore treats the zero-violation line only as a software
sanity check, not as evidence of unbiased pedestal estimation.

### 2.2 Timing Pickoff

The seed time is CFD20: the interpolated leading-edge crossing at 20% of peak.
Template/optimal-filter timing writes the waveform locally as

```text
y_j = c + A_fit s_j(A) - A_fit delta s'_j(A) + eta u_j + n_j,
```

where `s_j(A)` is an amplitude-adaptive template, `s'_j(A)` its derivative,
`delta` the sub-sample shift, and `u_j` nuisance structure. The resulting raw
time is corrected by

```text
t_i_corr = t_i_raw - f_i(A_i, x_i) - C_i - R_i,run - t_i,TOF .
```

In the newer report, B2 is excluded from the downstream timewalk reference and
fixed/run offsets are minimized to avoid circular alignment. The downstream
same-particle set B4/B6/B8 is the stable timing benchmark.

### 2.3 Residual Metrics

The main residual for staves `i,j` is

```text
Delta t_ij = t_i_corr - t_j_corr - Delta t_TOF,ij .
```

The robust width used throughout this synthesis is

```text
sigma68 = (q84 - q16) / 2 .
```

Gaussian core sigma, full RMS, and tail fractions are reported when available.
The studies repeatedly show that Gaussian core sigma alone is not an adequate
summary because tails and B2 topology drive many conclusions.

## 3. Methodology

The study program follows three rules.

### 3.1 Reproduce First

Every important report first reruns the raw-ROOT count or anchor metric. This
prevents derived tables, sorted proxy branches, and stale artifacts from
becoming silent assumptions.

### 3.2 Compare Traditional and ML Head to Head

ML is only credited when it beats a strong non-ML comparator on the same
held-out data and metric. A model that merely learns the label definition is
classified as a diagnostic or rejected result.

### 3.3 Split by Run and Bootstrap by Run

The default split unit is the run. CIs in the stronger studies are
run-bootstrap or held-out-run bootstrap intervals, not random row intervals.
This is essential because current, topology, calibration period, and waveform
pathologies are run-structured.

### 3.4 Leakage Controls

Common leakage controls include:

| Control | Purpose |
|---|---|
| No run/event/order features | Prevent direct run or event memorization |
| No target/other-stave timing features | Prevent target echo in timing tasks |
| Shuffled-target refits | Confirm the pipeline cannot reproduce the nominal gain without label structure |
| Intentional target-echo sentinels | Verify that obvious leakage would be detected |
| Row split versus run split comparisons | Detect optimistic random-row results |
| Forbidden-source probes | Quantify label-source ceilings, especially PID and duplicate-readout tasks |

The interpretation rule is conservative: an ML score can be useful for triage
or diagnostics even when it is rejected as a physics-facing measurement.

## 4. Timing and Timewalk

### 4.1 First Timing Pickoff Benchmark

S02 compared fixed traditional pickoffs and a ridge residual corrector on held
out run 65, using Sample II B4/B6/B8 events.

| Method | Held-out pairwise sigma68 (ns) | 95% CI (ns) | Note |
|---|---:|---:|---|
| Template phase | 2.889 | [2.639, 3.205] | Best fixed traditional scan in S02 |
| CFD20 reference | 2.993 | [2.615, 3.351] | Software CFD reference |
| Ridge on CFD20 | 1.846 | [1.521, 2.014] | ML residual correction |

On this narrow benchmark, ML improved over template phase by 1.043 ns. The
subsequent studies show why this was not the final timing answer: the
traditional baseline had not yet included a strong analytic timewalk closure.

### 4.2 Analytic Timewalk Closure

S03a fit interpretable amplitude transforms and stave intercepts to residuals,
with no run, event, or other-stave timing features. On the same run-65 benchmark:

| Method | sigma68 (ns) | 95% CI (ns) | Full RMS (ns) | Tail fraction > 5 ns |
|---|---:|---:|---:|---:|
| Template phase baseline | 2.889 | [2.639, 3.139] | 2.577 | 0.0505 |
| Analytic amplitude timewalk | 1.495 | [1.347, 1.644] | 1.699 | 0.0051 |
| Ridge on template phase | 1.392 | [1.297, 1.596] | 1.672 | 0.0051 |

The analytic method reduced sigma68 by 1.395 ns relative to the template
baseline and exceeded the original S02 ridge-on-CFD20 result. The best ML
residual model remained slightly narrower on this single run, but the main
effect was now clearly physics-like amplitude timewalk.

### 4.3 Leave-One-Run-Out Stability

S03c repeated the timing comparison with each Sample II analysis run held out.
The pooled intervals resample held-out runs:

| Method | Pooled sigma68 (ns) | Run-bootstrap CI (ns) | Tail fraction > 5 ns |
|---|---:|---:|---:|
| Template phase baseline | 2.741 | [2.681, 2.986] | 0.0813 |
| Analytic timewalk | 1.551 | [1.367, 1.903] | 0.0191 |
| Ridge on template phase | 1.537 | [1.335, 1.819] | 0.0174 |

The robust conclusion is therefore not "deep ML wins timing." It is that a
simple amplitude timewalk and a waveform ridge residual correction are
statistically tied once evaluated across runs. The analytic method is preferred
as the production-facing timing correction because it is interpretable and
nearly as good as ML under the same run-held-out discipline.

### 4.4 Per-Sample Timing Anatomy

The pulse-shape importance map identifies samples 3-6, especially the rising
edge and early peak, as the dominant timing carriers. Contiguous windows 1-4,
0-3, 2-4, and 3-4 produce the largest timing damage when ablated or permuted.
This is consistent with CFD and template-phase timing: the leading edge is
where timing information resides, while later samples mainly diagnose
overlap, tails, and saturation.

## 5. Error Structure and Two-Ended Projection

### 5.1 B2-Dominated Covariance

S05c fit a hierarchical B-stack covariance model and compared traditional
pair-median residuals with an ExtraTrees residual model under leave-one-run-out
evaluation.

| Method | Subset | sigma68 (ns) | 95% CI (ns) | Full RMS (ns) | Tail fraction > 5 ns |
|---|---|---:|---:|---:|---:|
| Raw pair median | All | 2.082 | [1.786, 7.533] | 20.675 | 0.1417 |
| Raw pair median | B2-containing | 3.512 | [1.891, 19.901] | 24.817 | 0.2026 |
| Raw pair median | Downstream only | 1.733 | [1.694, 1.767] | 6.537 | 0.0172 |
| ExtraTrees | All | 1.449 | [1.314, 1.957] | 5.619 | 0.0899 |
| ExtraTrees | B2-containing | 1.749 | [1.461, 2.712] | 6.320 | 0.1250 |
| ExtraTrees | Downstream only | 1.099 | [1.069, 1.167] | 3.814 | 0.0183 |

The ML residual model reduces widths, but the covariance decomposition still
identifies B2 as the dominant local variance node. Traditional B2-containing
pair covariances were about 1041.84 ns^2 [748.08, 1311.91], compared with
15.99 ns^2 [4.76, 37.13] for downstream-only pair covariances. This rejects a
simple detector-wide common-mode explanation.

### 5.2 Two-Ended Projection

The documents quote a two-ended timing projection of roughly a factor sqrt(2)
improvement for uncorrelated end noise:

```text
sigma_two_end ~= sigma_one_end / sqrt(2).
```

That projection does not remove correlated clock, electronics, timewalk, or
topology terms. The covariance studies imply that a realistic two-ended
projection must separate downstream clean timing from B2-local topology
variance; otherwise it will overstate the improvement for terminal-B2 events.

### 5.3 A-Stack Cross-Check

S18 reproduced the A-stack A1-A3 scale from raw ROOT:

| Sample | Method | n pairs | robust width (ns) | 95% CI (ns) | core sigma (ns) | chi2/ndf |
|---|---|---:|---:|---:|---:|---:|
| Sample III | traditional CFD20 polynomial timewalk | 2,514 | 1.389 | [1.339, 1.453] | 1.451 | 1.318 |
| Sample III | ridge timewalk | 2,514 | 1.383 | [1.337, 1.426] | 1.415 | 0.933 |
| Sample IV | traditional CFD20 polynomial timewalk | 127 | 1.794 | [1.379, 2.220] | 1.992 | 1.536 |
| Sample IV | ridge timewalk | 127 | 1.559 | [1.334, 1.780] | 1.808 | 1.032 |

For Sample III, the paired ML-minus-traditional CI was [-0.054, 0.026] ns
with p = 0.524, so ML was not adopted. The A-stack supports the timing scale
but remains a two-stave, lower-statistics cross-check, not a B-stack
calibration source.

## 6. Pile-Up Rate and Current Excess

### 6.1 Occupancy Model

The historical pile-up model uses a Poisson occupancy `mu = R tau_eff` and
efficiency

```text
P0 = exp(-mu)
P1 = mu exp(-mu)
Pge2 = 1 - P0 - P1
epsilon(mu) = P0 + P1 epsilon1 ,
R_max = mu_max / tau_eff .
```

For the combined requirement `|Delta t| < 1 ns` and area error below 20% at
greater than 90% efficiency, the reproduced occupancy anchor is
`mu_max = 0.380`. With the assumed `tau_eff = 90 ns`, this gives
`R_max = 4.222 MHz`.

### 6.2 Measured Live-Time Revision

S10b measured the waveform live-time rather than assuming it. The traditional
template tail fit gives:

| Method | live10 (ns) | 95% CI (ns) | Note |
|---|---:|---:|---|
| Traditional template tail | 124.79 | [123.33, 126.36] | Held-out-run bootstrap |
| ML ridge live10 | 123.19 | [120.72, 125.55] | Shape-to-live10 diagnostic |
| Empirical mean cross-check | 123.26 | - | Direct pulse check |

The occupancy `mu_max` is unchanged, but the live window is longer. Rescaling:

```text
R_max = 0.380 / 124.79 ns = 3.05 MHz .
```

Thus the 4.2 MHz number remains a reproducible assumption, not a measured
waveform rate limit. The measured live-time revision is the most important
physics-facing update to the pile-up section.

### 6.3 Current-Dependent Topology Excess

The raw topology fractions reproduce the high/low current difference:

| Quantity | 2 nA | 20 nA |
|---|---:|---:|
| Multi-stave per selected event | 0.01559 | 0.02681 |
| Three-stave per selected event | 0.00411 | 0.00854 |
| Downstream per selected event | 0.02312 | 0.03341 |

After P09a taxonomy/control matching, S10f gives a physics-facing
downstream high-minus-low excess of 0.00478 [0.00346, 0.00663] per selected
event, with topology odds ratio 1.505 [1.365, 1.700]. The largest rare-class
row is baseline_excursion, with downstream excess 0.02952 [0.01646, 0.04473].

ML current scores are useful diagnostics but not adopted as calibrated pile-up
rates. In S10f, the LORO ML current-score delta is 0.02218 [0.01456, 0.03845],
but Brier and log-loss are worse than the traditional train-run stratum-rate
baseline. S13b CWoLa transfers modestly: score ratio 1.220 [1.193, 1.257] and
held-out current AUC 0.668 [0.656, 0.682], while the transparent downstream
topology ratio is 1.445 [1.220, 2.542]. The topology handle remains the
physics-facing rate observable.

## 7. Two-Pulse Recovery

Synthetic two-pulse injection gives an independent target: clean real pulses
are overlaid, and the primary/secondary constituents define the closure truth.
This is not Monte Carlo; it is data-driven injection with known overlay
parameters.

S11e conditioned residual pools by run family, stave, amplitude bin, and
late-tail class, while training templates and ML only on train runs. The
headline comparison is:

| Benchmark | Traditional RMS (ns) | ML RMS (ns) | Gap traditional - ML (ns) |
|---|---:|---:|---:|
| S11c source residuals | 18.65 | 10.59 | 8.06 |
| Train-only residual control | 17.81 | 9.84 | 7.97 |
| Conditioned train-only residuals | 17.36 [17.16, 17.55] | 9.07 [8.88, 9.26] | 8.28 [7.89, 8.68] |

The compact MLP clearly wins the time-RMS closure metric. However, the same
report shows higher ML failure rates:

| Held-out run | Traditional failure rate | ML failure rate |
|---:|---:|---:|
| 63 | 0.010 | 0.243 |
| 65 | 0.013 | 0.260 |

The result is therefore split: ML wins synthetic timing RMS and charge res68,
but production use is gated by failure-rate transfer to real high-current data.
The safer operational method at a strict accepted-recovery point may still be a
traditional template fit or a hybrid with explicit failure rejection.

## 8. Pulse Shape, Representation, and Anomalies

### 8.1 Representation Learning

P01 trained a masked denoising autoencoder and compared it with PCA and
hand-built shape features on held-out runs 42, 57, 64, and 65.

| Task | Traditional | ML | Verdict |
|---|---:|---:|---|
| Dim-4 reconstruction MSE | PCA 0.013372 | AE 0.014277 | PCA wins reconstruction |
| Stave linear-probe balanced accuracy | hand/amplitude controls near 0.355 | AE-4 0.364 [0.345, 0.371] | Small ML probe gain |
| Label-shuffle probe | - | 0.243 [0.230, 0.250] | No obvious leakage |

The broader P02/P01 program finds that a compact nonlinear representation can
beat PCA at very low dimension for selected morphology tasks, while PCA remains
strong for reconstruction once enough dimensions are allowed. Later leakage
sentinels reject broad downstream claims unless run-family and event-block
controls are passed.

### 8.2 Anomaly Taxonomy

P09a compared a robust traditional template ranker with a PCA/autoencoder/
IsolationForest ML ranker for held-out anomaly triage.

| Ranker | Curated precision | 95% CI | Novel precision | 95% CI |
|---|---:|---:|---:|---:|
| Traditional robust template | 0.898 | [0.852, 0.945] | 0.555 | [0.508, 0.625] |
| ML PCA/AE/isolation | 0.883 | [0.797, 0.969] | 0.766 | [0.703, 0.828] |
| Balanced random | 0.180 | [0.125, 0.242] | 0.164 | [0.109, 0.227] |

The traditional ranker is slightly better for curated precision, while ML is
better for novel taxa. The taxonomy includes early pretrigger, delayed peak,
baseline excursion, broad template mismatch, pileup/long-tail, dropout, and
saturation classes. It is useful for audit triage and matching strata, not a
standalone discovery label.

## 9. Amplitude, Charge, Saturation, and Energy

### 9.1 Duplicate-Readout Amplitude and Charge

P04 uses the independent odd duplicate readout as the leakage-safe target. The
input features are even-channel waveforms and summaries only; odd-channel
samples, run IDs, and event IDs are excluded.

| Target | Best traditional | res68 | 95% CI | ML HGB res68 | 95% CI |
|---|---|---:|---:|---:|---:|
| Odd amplitude | peak-calibrated | 0.1238 | [0.1221, 0.1251] | 0.0091 | [0.0090, 0.0093] |
| Odd charge | integral-calibrated | 0.1954 | [0.1936, 0.1975] | 0.0151 | [0.0148, 0.0153] |

This is one of the strongest ML wins in the program. It is also deliberately
not promoted to absolute energy truth: the target is a duplicate electronic
readout, not a calibrated external calorimetric measurement.

### 9.2 Saturation Recovery

P07b reproduced the artificial fixed-ceiling saturation benchmark and applied
the trained models to natural high-amplitude B2 pulses.

| Task | Traditional | 95% CI | ML | 95% CI |
|---|---:|---:|---:|---:|
| Artificial clip amplitude res68 | 0.1480 | [0.1461, 0.1501] | 0.0298 | [0.0279, 0.0323] |
| Natural B2 q_template shift | 0.0010 | [0.0008, 0.0012] | -0.0897 | [-0.0947, -0.0864] |
| Natural timing-tail fraction | 0.0384 | [0.0174, 0.0593] | 0.0329 | [0.0175, 0.0470] |

ML decisively wins artificial-clip closure. Natural saturated transfer has no
truth label and shifts template quality more aggressively, so it is carried as
a calibration systematic rather than a production correction.

### 9.3 Energy Proxy

S14c combines saturation-corrected charge with a PSTAR/depth monotonic ordering
envelope. It is explicitly a proxy-ordering study, not an absolute energy or
PID calibration.

| Method | Unsaturated charge res68 | 95% CI | Energy-proxy res68 | 95% CI |
|---|---:|---:|---:|---:|
| Observed even charge | 0.1399 | [0.1061, 0.1748] | 0.0212 | [0.0198, 0.0225] |
| Traditional template corrected | 0.1399 | [0.1095, 0.1729] | 0.0289 | [0.0248, 0.0350] |
| ML P07/P04 corrected | 0.0663 | [0.0579, 0.0768] | 0.0145 | [0.0142, 0.0150] |

ML improves the internal energy-ordering proxy. It still does not solve
absolute energy: there is no event-level truth, Birks quenching and geometry
systematics remain, and the propagated external energy target in related S14
studies misses the 10% per-event threshold.

## 10. Pedestal and Baseline

S16 directly tested pedestal estimators by holding out one of samples 0-3 and
predicting it from the other pretrigger samples and waveform information.

| Method | Held-out pretrigger MAE (ADC) | 95% CI | Mean bias (ADC) |
|---|---:|---:|---:|
| Calibrated ML HGBR | 48.88 | [43.82, 55.29] | reported in artifacts |
| Mean3 | 260.70 | [236.25, 287.99] | -14.79 |
| Median3 | 273.64 | [244.24, 302.67] | -51.19 |
| Adaptive positivity constrained | 341.04 | [300.45, 373.27] | -310.69 |

The adaptive pedestal fails the pre-registered unbiasedness criterion: its
mean-bias CI excludes zero and it is worse than the simple median baseline.
The ML regressor wins this proxy benchmark, but no forced/random-trigger
pedestal sample exists in the current mirror. Large adaptive lowering should
therefore be used as a contamination/pathology diagnostic, not as proof of a
correct pedestal.

## 11. Particle ID and Calibration-Backed Weak Labels

PID remains label limited. P08b replaced a direct topology proxy with a
calibrated range-energy residual weak label using duplicate-readout charge
calibration and PSTAR depth anchors. The label support was 289,626 rows from
122 run/depth atoms, with a 29,134-row balanced held-out benchmark.

| Method | ROC AUC | 95% CI | AP | Purity at 80% high-residual efficiency |
|---|---:|---:|---:|---:|
| Traditional calibrated charge-depth logistic | 0.986 | [0.977, 0.992] | 0.983 | 0.989 |
| ML B2 waveform + PCA latent HGB | 0.986 | [0.978, 0.993] | 0.987 | 0.995 |

The paired run-block bootstrap for ML minus traditional ROC AUC is 0.000 with
95% CI [-0.003, 0.004]. The high AUC is explained by duplicate-readout
charge-scale closure: the even-charge calibration proxy itself reaches AUC
0.985, while the forbidden odd-energy source reaches 0.991. The topology-only
sentinel drops to 0.809 relative to the older perfect topology shortcut. This
is a useful weak-label stress test, not a PID adoption result.

## 12. Method Winners by Theme

| Theme | Strong traditional method | ML/NN method | Winner | Basis |
|---|---|---|---|---|
| S00 selection | Deterministic raw HRDv threshold | Logistic sanity checks | Traditional | Exact threshold rule reproduces 640,737 |
| Timing pickoff, weak baseline | Template phase | Ridge on CFD20 | ML diagnostic | 1.846 ns vs 2.889 ns on run 65 |
| Timewalk adoption | Analytic amplitude timewalk | Ridge residual correction | Tie / prefer traditional | LORO 1.551 [1.367, 1.903] vs 1.537 [1.335, 1.819] |
| Error structure | Pair covariance decomposition | ExtraTrees residual model | Mixed | ML narrows residuals; B2-local covariance remains the finding |
| A-stack timing | CFD20 polynomial timewalk | Ridge timewalk | Tie | ML-minus-trad CI [-0.054, 0.026] ns |
| Pile-up live-time | Template tail live10 | Ridge live10 diagnostic | Traditional | Both agree near 124 ns; template gives physics-facing rescale to 3.05 MHz |
| Current excess | Matched topology/rate excess | CWoLa/current scores | Traditional | ML diagnostics not calibrated; Brier/log-loss worse in S10f |
| Two-pulse synthetic recovery | Bounded template fit | Compact MLP | ML on RMS, not failure rate | 9.07 ns vs 17.36 ns, but ML failure about 0.25 |
| Representation | PCA and hand features | Masked AE | Mixed | PCA wins dim-4 recon in P01; AE useful compact/probe signal |
| Anomaly triage | Robust template ranker | PCA/AE/IsolationForest | Mixed | Traditional curated precision; ML novel precision |
| Duplicate amplitude/charge | Peak/integral calibration | HGB | ML | Amplitude res68 0.009 vs 0.124; charge 0.015 vs 0.195 |
| Saturation closure | Rising-edge template | Gradient-boosted regressor | ML on artificial truth | res68 0.0298 vs 0.1480 |
| Energy proxy | Observed/template charge | P07/P04 corrected ML | ML for proxy only | energy-proxy res68 0.0145 vs 0.0289 |
| Pedestal proxy | Mean/median/adaptive | HGBR | ML proxy | MAE 48.9 ADC vs 260-341 ADC |
| PID weak label | Charge-depth logistic | Waveform/PCA HGB | Tie / no adoption | AUCs both 0.986; label-source closure dominates |

## 13. Systematics and Caveats

### 13.1 No Monte Carlo Truth

Every result is data-driven. This is powerful for closure tests but limiting
for absolute physics claims. Energy, PID, and real unresolved pile-up lack
independent event truth.

### 13.2 Sorted Branch Semantics

The reproducible count gate uses raw `HRDv`, not sorted `hrdMax`. Sorted
branches are useful for historical checks but should not define the selected
population unless their semantics have been explicitly reconciled.

### 13.3 Timing Metrics

Core Gaussian sigma, robust sigma68, full RMS, and tail fractions can tell
different stories. B2 terminal topologies create tens-of-ns tails while
downstream B4/B6/B8 pairs are much narrower. Reporting only a narrow core
sigma hides the dominant failure modes.

### 13.4 B2 Topology

The B2 population is not merely a worse version of downstream timing. It is a
terminal/topology-heavy population with large covariance, saturation, pedestal
lowering, and late-overlap signatures. It should not be used to calibrate clean
same-particle downstream timing.

### 13.5 ML Label Source Risk

The most suspicious ML wins are those where the target is derived from timing
span, curvature, topology, duplicate charge, or other features adjacent to the
input. Such models can be valuable diagnostics but are rejected as independent
physics measurements unless a separate truth source exists.

### 13.6 Pile-Up Rate

The measured live-time revision changes the rate interpretation but not the
occupancy algebra. Any future Rmax must state both `mu_max` and the measured
or assumed `tau_eff`. Using 90 ns without qualification now overstates the
measured waveform tolerance.

### 13.7 Pedestal Truth

There is no true forced/random pedestal sample in the accessible data mirror.
The best available S16 benchmark is leave-one-pretrigger-out on beam-triggered
events. That benchmark is informative but cannot fully separate electronics
baseline from early pulse contamination.

## 14. Open Questions and GEANT4 Path

The open experimental questions are:

1. Build or validate an independent GEANT4 model for the CCB geometry and
   CD2 target response.
2. Obtain event-level energy/PID labels or credible simulated truth for
   calibrating the range-energy interpretation.
3. Locate or acquire true forced/random pedestal events.
4. Validate ML two-pulse failure rates on real high-current unresolved
   candidates, not only synthetic overlays.
5. Reconcile the remaining geometry/report discrepancies, including 2 cm
   versus 4 cm stave spacing assumptions where they enter TOF and energy
   proxies.
6. Quantify correlated versus uncorrelated timing terms before promoting the
   two-ended sqrt(2) projection.

A GEANT4 starting point exists at `/home/billy/ccb-geant4`, including
`krakow.geoconf`, `krakow.config`, `run_krakow.mac`, and related cross-section
or dE/dx text files. The next step is not to use those files as truth by
assertion; it is to turn them into a reproducible simulation chain with
geometry/version manifests, beam and target settings, digitization assumptions,
and closure comparisons against the raw-ROOT observables listed in this
report.

## 15. Conclusion

The CCB waveform program now has a coherent pattern. Conventional physics
models explain the main timing and rate observables when they are given fair
strength: analytic timewalk nearly matches ridge timing, topology rates remain
the current-excess handle, and template live-time provides the physically
transparent Rmax revision. ML earns its strongest claims in closure problems
where waveform shape carries information not captured by scalar summaries:
duplicate-readout amplitude/charge, artificial saturation recovery, synthetic
two-pulse timing RMS, compact representation learning, and anomaly triage.

The scientific discipline is the main result: every adopted claim is
reproduced from raw ROOT, benchmarked against a traditional method, split by
run, and stress-tested for leakage. The remaining path to absolute energy,
particle ID, and real pile-up truth runs through independent labels, most
plausibly a validated GEANT4 and/or new calibration data.

## Source Reports Read for This Chapter

This chapter was prepared from the project summaries and a bounded set of
representative reports:

| Theme | Source |
|---|---|
| Scoreboard and synthesis | `reports/SUMMARY.md`, `FINDINGS_SYNTHESIS.md` |
| Setup and methods | `docs/00_overview.md` through `docs/09_open_questions.md` |
| Timing pickoff | `reports/1780997954.15157.07ef03cf__s02_timing_pickoff/REPORT.md` |
| Analytic timewalk | `reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction/REPORT.md` |
| Timewalk LORO | `reports/1781005627.1877.378c7a87/REPORT.md` |
| Covariance/error structure | `reports/1781009478.9969.16fe02b4/REPORT.md` |
| A-stack cross-check | `reports/1780997954.15397.168324f2__s18_astack_independent_reproduction/REPORT.md` |
| Pile-up live-time | `reports/1781000867.546870.5c124aaf/REPORT.md` |
| Current excess | `reports/1781012706.846.1f364432/REPORT.md`, `reports/1781017360.928.15a27ed1/REPORT.md` |
| CWoLa current classifier | `reports/1781000867.546938.20f0173c/REPORT.md` |
| Two-pulse recovery | `reports/1781018533.1179.60a328c5/REPORT.md` |
| Representation and sample importance | `reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation/REPORT.md`, `reports/1781005319.562.584259c9__p01c_pulse_shape_importance_map/REPORT.md` |
| Anomaly taxonomy | `reports/1781005319.615.15053b04__p09a_rare_waveform_anomaly_taxonomy/REPORT.md` |
| Amplitude/charge | `reports/1780997954.15577.6c203777/REPORT.md` |
| Saturation | `reports/1781004956.668.7d00443a/REPORT.md` |
| Energy proxy | `reports/1781014263.712.4e9c774b/REPORT.md` |
| Pedestal | `reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/REPORT.md` |
| PID weak labels | `reports/1781027807.3490.5cdd4b0b/REPORT.md` |

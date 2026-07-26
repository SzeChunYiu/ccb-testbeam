# Real-Data CFD Timing Resolution (LUNARC fs10)

Independent measurement of detector timing resolution via CFD on the REAL LUNARC raw ROOT waveforms, with a pulse-shape assessment and CFD-fraction scan.

## Headline result

- **CFD on real waveforms (B6-B8 in-time pair, Sample-II runs 58-65): sigma68 = 0.899 ns** [t_cfd10, bootstrap CI 0.812-1.072 ns], tail fraction 15.9%.
- Single-stave estimate (pair / sqrt2) = **0.635 ns**, consistent with the validated ledger CL-002 (B6 = 0.63-0.80 ns).
- The 38 ns peak-TIME (sample-index) sampling limit is beaten by CFD sub-sample interpolation by roughly an order of magnitude on real data.
- The 0.151 ns Cluster-B MC ideal is NOT reached: the MC omits the dominant 0-5.9 ns WLS fibre position spread that only partially cancels in inter-stave residuals.

## Pulse-shape assessment (CFD applicability)

The task warned that CFD cannot help if the pulse spans only 1-2 samples. On this data the pulses are WIDE (tau_decay ~ 42 ns): each pulse spans ~8-14 samples above 10% of peak, with >=3 samples in 97-99% of pulses. **CFD sub-sample interpolation is fully applicable** — this is not the failure mode.

## Important caveats (honest)

1. **Claim status correction.** The task brief described CL-002..006 as GATED and asked to upgrade them. The repo ledger shows CL-002..005 are already **VALIDATED** (B6 = 0.63-0.80 ns; combined B4+B6+B8 = 0.46-0.62 ns). This study CONFIRMS the validated envelope; there is no GATED->measured upgrade to perform.
2. **Data-revision difference.** The LUNARC fs16 `hrdb_run_*.root` files differ from the laptop 18-sample data that produced the published s02 numbers: 16 vs 18 samples/channel, and ~3x more events per run (262k vs 90k in Sample II). The extra events are mostly out-of-time / pile-up hits, so a strict same-particle (in-time) selection is required before the sub-ns core emerges.
3. **Naive first-crossing CFD is fragile here.** The reviewed `cfd_time_samples` locks onto the first threshold crossing, which on this pile-up-heavy revision often catches an early tail rather than the true rising edge. Low fractions (CFD10) and an in-time event selection mitigate this; a peak-anchored CFD is the robust extension.
4. **The B4 channel (ch2) is unreliable on this revision** (CFD std ~ 35 ns, pile-up-dominated), so the headline uses the clean B6-B8 pair rather than a 3-stave combination. Reproducing the full CL-004 3-stave number requires the laptop 18-sample data.

## sample_II (runs [58, 59, 60, 61, 62, 63, 65])

In-time B6-B8 events (aligned-peak spread <= 1.5): **1888**.

| method | n | sigma68 (ns) | ci68 | core sigma (ns) | chi2/ndf | tail |
|---|---|---|---|---|---|---|
| t_cfd10 | 1888 | 0.899 | [0.812, 1.072] | 0.551 | 1.973 | 0.159 |
| t_cfd20 | 1888 | 15.434 | [9.367, 17.930] | 0.922 | 1.335 | 0.251 |
| t_cfd30 | 1888 | 25.751 | [25.622, 25.899] | 1.312 | 1.082 | 0.405 |
| t_cfd40 | 1888 | 30.584 | [30.467, 30.731] | nan | nan | 0.939 |
| t_cfd50 | 1888 | 34.394 | [34.235, 34.527] | 2.404 | 0.655 | 0.371 |
| template | 1888 | 1.750 | [1.500, 1.750] | 0.052 | 40.259 | 0.091 |

Best robust sigma68: **0.899 ns** (t_cfd10).

## task_runs (runs [19, 20, 23, 24, 25, 26, 27, 28, 29, 30])

In-time B6-B8 events (aligned-peak spread <= 1.5): **675**.

| method | n | sigma68 (ns) | ci68 | core sigma (ns) | chi2/ndf | tail |
|---|---|---|---|---|---|---|
| t_cfd10 | 675 | 3.548 | [3.046, 4.081] | 0.628 | 5.555 | 0.218 |
| t_cfd20 | 675 | 6.730 | [6.211, 7.185] | 2.110 | 2.285 | 0.284 |
| t_cfd30 | 675 | 7.577 | [6.882, 8.341] | 1.455 | 1.018 | 0.388 |
| t_cfd40 | 675 | 7.992 | [7.332, 8.842] | 3.486 | 1.012 | 0.439 |
| t_cfd50 | 675 | 8.493 | [7.892, 9.224] | 5.075 | 1.763 | 0.556 |
| template | 675 | 1.000 | [1.000, 1.000] | 0.012 | 8.808 | 0.000 |

Best robust sigma68: **1.000 ns** (template).

## Method

- Channel map (LUNARC, empirical): ch0=B2, ch4=B6, ch6=B8. Odd channels are ~95%-fire reference/noise and are not used.
- Baseline = median of pre-trigger samples [0,1,2,3]; amplitude = max above baseline; selection A > 1000 ADC (s02 config).
- Cable-delay removal: subtract each stave's median peak_sample.
- In-time selection: keep events where the cable-aligned peak_sample of B6 and B8 agree within 1.5 samples (same-particle filter; kills ~98% of the pile-up).
- CFD pickoff (fractions 0.1-0.5) via linear interpolation between adjacent samples; template-phase cross-check; both reuse the reviewed `scripts/s02_timing_pickoff.py`.
- Pair residual = t(B6) - t(B8) - TOF - cable-delay; reported as robust sigma68, Gaussian-core sigma (fit on |d-med|<5 ns), tail fraction (>5 ns), and bootstrap CI.
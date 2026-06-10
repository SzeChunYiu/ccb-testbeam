# Study report: S10 - pile-up rate model and current-dependent excess

- **Study ID:** S10
- **Ticket:** `1780997954.15277.548b01a3`
- **Author:** `testbeam-laptop-5`
- **Date:** 2026-06-09
- **Depends on:** S00
- **Input checksum(s):** raw ROOT hashes in `manifest.json`
- **Git commit:** `696daf4c4b7df48eae2ff23b7f6a08be4e0dcc1b`
- **Config:** none external; fixed parameters in `s10_pileup_rate_model.py` and `PRE_REGISTRATION.md`

## 0. Question
Does the S10 current-scaling evidence reproduce the documented occupancy `R_max ~= 4.2 MHz`, current-topology fractions, and ML score ratio, and is `tau_eff=90 ns` supported by a direct raw-waveform width handle?

## 1. Reproduction
The initial pre-registration assumed run 46 was low current and run 47 was high current. That failed and exposed a documentation consistency issue: `docs/01_setup_and_detector.md` states both runs 46 and 47 are 2 nA. The documented S10 fractions reproduce only when the denominator is events with at least one selected B pulse, with runs 46+47 as the 2 nA reference and Sample-I analysis runs 44,45,48-57 as 20 nA.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| 2 nA multi-stave / selected event | 0.0156 | 0.015588 | -0.000012 | 0.0015 | yes |
| 2 nA >=3-stave / selected event | 0.0041 | 0.004111 | 0.000011 | 0.0015 | yes |
| 2 nA downstream / selected event | 0.0231 | 0.023124 | 0.000024 | 0.0015 | yes |
| 20 nA multi-stave / selected event | 0.0268 | 0.026806 | 0.000006 | 0.0015 | yes |
| 20 nA >=3-stave / selected event | 0.0085 | 0.008538 | 0.000038 | 0.0015 | yes |
| 20 nA downstream / selected event | 0.0334 | 0.033414 | 0.000014 | 0.0015 | yes |

The Poisson occupancy table also reproduces. For the combined `|dt|<1 ns and area<20%` requirement, `mu_max=0.380` and `tau_eff=90 ns` gives `R_max=4.222 MHz`, matching the reported `~4.22 MHz`.

## 2. Traditional method
The traditional analysis is the raw topology-rate comparison plus the analytic Poisson occupancy model.

At 2 nA, 5,838 events have at least one selected B pulse; at 20 nA, 237,295 do. The downstream fraction rises from 2.312% to 3.341%, a high-low difference of 1.029 percentage points with 95% binomial CI [0.637, 1.421] percentage points. Expressed as the fraction of the 20 nA downstream rate attributable to the high-low excess, this is 30.8%.

There is no fit in the Poisson `R_max=mu_max/tau_eff` reproduction, so chi2/ndf is not applicable. Full distributions are represented by `fig_current_topology.png`, `fig_current_excess.png`, and the raw tables.

The direct waveform-width handle does not support 90 ns as an obvious measured live-time. Contiguous widths around the peak average 129.7 ns at 10% of amplitude and 120.4 ns at 20% for the 2 nA group; the 20 nA group is similar at 129.4 ns and 123.7 ns. This is not a calibrated `tau_eff`, but it argues that the 90 ns value is an assumption, not yet a measurement.

## 3. ML method
The ML method is an injection-trained, calibrated logistic pile-up score using waveform-shape features only: peak sample, area/peak, tail and late fractions, early fraction, post-peak minimum, negative-step count, width features, and final-sample fraction. Labels are synthetic clean vs injected two-pulse waveforms built from real selected pulses; they are not beam-pile-up truth labels.

Hyperparameter scan:

| Group | Best C | ML AUC | ML AP | Brier | Traditional AUC | Traditional AP |
|---|---:|---:|---:|---:|---:|---:|
| 2 nA | 10.0 | 0.986 [0.981, 0.990] | 0.982 [0.971, 0.992] | 0.0346 | 0.913 | 0.928 |
| 20 nA | 0.1 | 0.966 [0.960, 0.972] | 0.968 [0.961, 0.974] | 0.0661 | 0.911 | 0.931 |

Calibration is sigmoid calibration with reliability data in `ml_reliability.csv` and `fig_ml_reliability.png`. The calibrated probabilities are still imperfect in low-probability bins, so the score is used as a ranking/current-scaling diagnostic, not a literal beam-pile-up probability.

On real selected pulses, the fixed low-current-trained ML score mean rises from 0.1213 to 0.1574, a high/low ratio of 1.297. That reproduces the documented qualitative point: the score increases by about 30%, not by the 10x beam-current ratio, so most of the raw score is current-independent baseline.

## 4. Head-to-head benchmark

| Method | Metric | Value | Notes |
|---|---:|---:|---|
| Traditional topology | downstream high/low ratio | 1.445 | Strong, transparent current-rate baseline |
| Traditional topology | high-current excess fraction | 0.308 | Excess fraction of the 20 nA downstream rate |
| ML score | high/low score ratio | 1.297 | Matches documented App. H scale, but proxy only |
| ML score | high-current excess fraction | 0.229 | Current-independent baseline still dominates |

ML beats the scalar late-width traditional score on injected waveform labels, but it does not replace the analytic current-fraction baseline for the physics claim. The useful S10 result is diagnostic: both approaches say the high-current component is real, but the raw pile-up score is not pure beam pile-up.

## 5. Falsification
- **Pre-registration:** `PRE_REGISTRATION.md`; corrected after the run-46/run-47 current assumption was falsified by `docs/01_setup_and_detector.md`.
- **Falsification test:** fail if combined `R_max` differs from 4.22 MHz by more than 0.02 MHz, or if the downstream high-low CI includes zero.
- **Result:** `R_max=4.222 MHz`; downstream high-low CI is [0.00637, 0.01421], excluding zero. `n_tries=1` after the documented run grouping was corrected.

## 6. Threats to validity
- **Benchmark/selection:** the topology baseline is strong and transparent. The ML benchmark uses synthetic injection labels, which test waveform sensitivity but are not truth labels for beam pile-up.
- **Data leakage:** raw data are split by current/run group. ML features exclude current, run, and event topology labels. Synthetic labels are generated from waveforms, so the classifier is a pile-up-shape proxy.
- **Metric misuse:** the ML score ratio is a ranking/proxy statistic, not a calibrated beam-pile-up fraction. Full topology fractions and waveform-width distributions are reported.
- **Post-hoc selection:** the run grouping correction was forced by documentation and exact reproduction; it should be treated as a protocol correction, not a physics cut scan.

## 7. Provenance manifest
`manifest.json` contains the input hashes, command, seed, git commit, environment, and output hashes. The command is:

```bash
python3 reports/1780997954.15277.548b01a3__s10_pileup_rate_model/s10_pileup_rate_model.py
```

## 8. Findings & next steps
S10 reproduces the occupancy and current-scaling numbers. The detector has a real current-dependent topology excess, but it sits on a large current-independent pulse-shape/pathology baseline. The direct width handle makes `tau_eff=90 ns` look like an optimistic assumption relative to the observed raw pulse extent, not a measured live-time.

Hypothesis: the S10 score baseline is dominated by detector/pulse-shape pathologies and terminal-B2 topology, while the current-dependent component is a smaller beam-pile-up increment. A measured template/live-time fit should separate these effects better than a scalar 90 ns assumption.

Next tickets proposed in `result.json`:
- `S10b: measure tau_eff with a timing-template decay/live-time fit` - answers whether 90 ns is defensible or should be replaced by a measured effective window.
- `S13b: run-transfer CWoLa current classifier with multiple low/high-current runs` - tests whether the 1.29 ML score ratio is stable beyond this two-low-run reference.

## 9. Reproducibility
Artifacts written:
`reproduction_match_table.csv`, `topology_by_run.csv`, `poisson_rmax_table.csv`, `tau_width_handle.csv`, `ml_cv_scan.csv`, `ml_injection_benchmark.csv`, `ml_reliability.csv`, `ml_score_by_run.csv`, `current_excess_table.csv`, `fig_current_topology.png`, `fig_poisson_rmax.png`, `fig_tau_width_handle.png`, `fig_ml_reliability.png`, `fig_current_excess.png`, `result.json`, and `manifest.json`.

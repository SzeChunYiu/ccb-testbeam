# S16m: Pseudo-Pedestal Charge and Live-Time Bias Closure

- **Study ID:** S16m
- **Ticket:** 1781038019.1322.46921ff8
- **Author (worker label):** testbeam-laptop-4
- **Date:** 2026-06-10
- **Depends on:** S00, S10, P04, S16g
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `f49b5332de25569e8a2b81fc21661fec3d578dbc`
- **Config:** `configs/s16m_1781038019_1322_46921ff8_pseudopedestal_charge_livetime_bias.json`

## 0. Question

Do S16g-style quiet-run/pre-trigger pseudo-pedestals introduce charge-closure or live-time biases when reused by P04-style duplicate charge transfer and S10-style pile-up summaries, or are they safe only as diagnostics?

The atomic tests are: reproduce the selected-pulse gate from raw ROOT; freeze five pseudo-pedestal estimators; propagate each baseline into duplicate-readout Huber charge closure, empirical last-above live-time, bounded two-pulse secondary summaries, and downstream timing-tail fractions; then benchmark pre-trigger risk predictors with leave-one-run-out Sample-II splits.

## 1. Reproduction

Raw `h101/HRDv` is read from `data/root/root/hrdb_run_NNNN.root`. The B2/B4/B6/B8 even channels are corrected by the median of samples 0--3, and selected pulses satisfy \(A>1000\) ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

All downstream S16m tables use the Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`, which contain `125096` selected pulse rows after this gate.

## 2. Traditional Method

The reference baseline is
\[
b_i^{(0)}=\operatorname{median}(x_{i0},x_{i1},x_{i2},x_{i3}),
\]
matching the S00 gate. Five frozen pseudo-pedestal estimators are compared against this reference:

\[
\begin{aligned}
b_i^{\mathrm{mean3}} &= (x_{i0}+x_{i1}+x_{i2})/3,\\
b_i^{\mathrm{median3}} &= \operatorname{median}(x_{i0},x_{i1},x_{i2}),\\
b_i^{\mathrm{quietest}} &= x_{ij} \quad j=\arg\min_j |x_{ij}-\operatorname{median}(x_i)|,\\
b_i^{\mathrm{quietish}} &= \frac12(x_{ia}+x_{ib}),\quad (a,b)=\arg\min_{a<b} |x_{ia}-x_{ib}|.
\end{aligned}
\]

`calibrated_pretrigger` is a run-heldout Huber calibration from the four pre-trigger samples, the four transparent estimators, pre-trigger range/slope, and stave id to the reference baseline. It is evaluated only on the held-out run for each fold.

Pedestal bias summary:

| Estimator | Mean bias ADC [95% CI] | MAE ADC [95% CI] | Sigma68 ADC | Full RMS ADC |
|---|---:|---:|---:|---:|
| mean3 | -49.62 [-59.54, -33.02] | 59.60 [45.35, 69.85] | 7.58 | 202.26 |
| median3 | -85.02 [-102.49, -60.40] | 95.09 [66.15, 110.80] | 10.50 | 304.53 |
| quietest | -85.02 [-102.56, -67.71] | 95.09 [73.65, 111.74] | 10.75 | 304.53 |
| quietish | -27.97 [-34.33, -17.25] | 112.17 [82.64, 132.27] | 8.25 | 358.44 |
| calibrated_pretrigger | 1.60 [0.96, 2.23] | 4.88 [3.58, 6.07] | 1.11 | 83.30 |

For P04-style charge transfer, a Huber regressor is trained in each leave-one-run-out fold to predict the odd-channel duplicate positive charge from log even-channel charge, log amplitude, peak sample, and stave id. The same held-out pulses are used for every baseline.

| Estimator | Charge res68 fraction [95% CI] | Median bias fraction [95% CI] | Full RMS fraction |
|---|---:|---:|---:|
| mean3 | 0.0626 [0.0577, 0.0693] | -0.0026 [-0.0090, 0.0016] | 0.8791 |
| median3 | 0.0291 [0.0252, 0.0336] | -0.0019 [-0.0038, 0.0002] | 10.5340 |
| quietest | 0.0279 [0.0245, 0.0324] | -0.0019 [-0.0038, 0.0000] | 10.6358 |
| quietish | 0.0211 [0.0192, 0.0233] | -0.0010 [-0.0022, 0.0006] | 50.3343 |
| calibrated_pretrigger | 0.0680 [0.0619, 0.0791] | -0.0027 [-0.0094, 0.0025] | 1.5621 |

For S10-style live-time and pile-up proxies, `tau_eff90` is the 90th percentile of the empirical last-above-10%-of-peak time. The bounded two-pulse summary fits a non-negative delayed copy of a stave template with amplitude constrained to \(0 \leq \alpha_2 \leq 0.8A\); pulses with \(\alpha_2/A>0.15\) are counted as secondary-like. Timing tails use all B4/B6/B8-selected events and the fixed \(|r-m_p|>5.0\) ns tail rule.

| Estimator | tau_eff90 ns [95% CI] | tau shift ns | Secondary frac [95% CI] | Secondary shift | Timing-tail frac | Timing-tail shift |
|---|---:|---:|---:|---:|---:|---:|
| mean3 | 170.00 [170.00, 170.00] | 0.00 | 0.2973 [0.2653, 0.3357] | 0.0013 | 0.0137 | -0.0015 |
| median3 | 170.00 [170.00, 170.00] | 0.00 | 0.2997 [0.2676, 0.3501] | 0.0037 | 0.0166 | 0.0014 |
| quietest | 170.00 [170.00, 170.00] | 0.00 | 0.2996 [0.2700, 0.3493] | 0.0036 | 0.0166 | 0.0014 |
| quietish | 170.00 [170.00, 170.00] | 0.00 | 0.2998 [0.2688, 0.3547] | 0.0038 | 0.0303 | 0.0151 |
| calibrated_pretrigger | 170.00 [170.00, 170.00] | 0.00 | 0.2961 [0.2638, 0.3346] | 0.0000 | 0.0147 | -0.0005 |

## 3. ML Method

The ML task is not to infer physical pedestal truth. It predicts a downstream-risk label defined before model fitting:

\[
y_i = 1\left[\max_e |\Delta Q_{ie}|/Q_i > 0.03 \; \lor \; \max_e |\Delta \tau_{ie}| \ge 10.0\,\mathrm{ns} \; \lor \; \mathrm{secondary\ toggle}\right],
\]
where \(e\) ranges over the frozen pseudo-pedestal estimators. This label asks whether baseline choice materially changes charge/live-time summaries, not whether the event is a true pedestal-contaminated pulse.

All ML comparisons are split by run. Features are limited to pre-trigger summaries and the two four-sample even/odd pre-trigger traces; they exclude event id, run id for the main models, charge, amplitude, timing residuals, last-above time, and secondary labels. Scores are Platt-calibrated inside the training runs before held-out evaluation. The compared methods are a traditional pre-trigger quantile envelope, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new dual-readout Siamese CNN plus metadata architecture. Shuffled-pre-trigger, amplitude-only, and run-only sentinels are reported separately.

## 4. Head-to-Head Benchmark

Primary risk metric: held-out high-risk enrichment, the risk rate in the top `15%` flagged pulses minus the risk rate in the unflagged pulses. Confidence intervals are run-block bootstraps.

| Method | AUC [95% CI] | AP [95% CI] | Brier | Risk delta [95% CI] | Flagged risk rate [95% CI] |
|---|---:|---:|---:|---:|---:|
| cnn1d | 0.960 [0.942, 0.970] | 0.933 [0.896, 0.952] | 0.0434 | 0.9482 [0.9414, 0.9545] | 0.9924 [0.9865, 0.9974] |
| gradient_boosted_trees | 0.956 [0.939, 0.965] | 0.929 [0.894, 0.945] | 0.0401 | 0.9419 [0.9347, 0.9498] | 0.9867 [0.9815, 0.9913] |
| mlp | 0.957 [0.946, 0.966] | 0.932 [0.906, 0.949] | 0.0392 | 0.9471 [0.9390, 0.9556] | 0.9909 [0.9842, 0.9964] |
| ridge | 0.931 [0.910, 0.941] | 0.894 [0.852, 0.915] | 0.0602 | 0.8918 [0.8820, 0.9034] | 0.9441 [0.9385, 0.9499] |
| siamese_cnn_meta | 0.960 [0.945, 0.967] | 0.934 [0.900, 0.949] | 0.0441 | 0.9480 [0.9405, 0.9573] | 0.9918 [0.9852, 0.9972] |
| traditional_quantile | 0.941 [0.930, 0.950] | 0.899 [0.868, 0.919] | 0.0962 | 0.8852 [0.8713, 0.9006] | 0.9379 [0.9291, 0.9465] |

Winner: **cnn1d**. The winning model is named in `result.json`. It is a risk-ranking winner, not an authorization to correct charge or live-time measurements with pseudo-pedestals.

## 5. Falsification

Pre-registration is the ticket text: metric with bootstrap CIs is pedestal bias/MAE, charge res68/bias, tau_eff shift, secondary-fraction shift, timing-tail fraction, and ML-minus-traditional risk delta under run splits. The falsification tests are:

- If a pseudo-pedestal estimator has charge-closure and live-time shifts consistent with zero and lower risk than the reference, it could be considered safe for downstream use.
- If shuffled-pre-trigger or amplitude/run sentinels match the best model, then the ML benchmark is dominated by nuisance leakage rather than pre-trigger pedestal structure.

Leakage and nuisance sentinels:

| Control | Method | AUC | AP | Risk delta |
|---|---|---:|---:|---:|
| shuffled_pretrigger | cnn1d | 0.623 | 0.430 | 0.3079 |
| shuffled_pretrigger | gradient_boosted_trees | 0.614 | 0.250 | 0.0469 |
| shuffled_pretrigger | mlp | 0.706 | 0.508 | 0.4902 |
| shuffled_pretrigger | ridge | 0.668 | 0.481 | 0.3312 |
| shuffled_pretrigger | siamese_cnn_meta | 0.663 | 0.488 | 0.3968 |
| shuffled_pretrigger | traditional_quantile | 0.498 | 0.185 | 0.0039 |
| nuisance_sentinel | amplitude_only | 0.699 | 0.339 | 0.2421 |
| nuisance_sentinel | run_only | 0.411 | 0.158 | nan |

The amplitude-only and run-only sentinels are not used to choose the winner.

## 6. Threats to Validity

Benchmark/selection: the traditional baseline is a direct quantile envelope over pre-trigger excursions and is not a strawman. The charge benchmark uses the same held-out duplicate-readout rows for every estimator.

Data leakage: all train/test splits are by run. The main risk models exclude run id, event id, charge, amplitude, timing, and downstream labels. `calibrated_pretrigger` is fit only on non-held-out runs. The risk label is itself derived from pseudo-pedestal perturbations, so it should be interpreted as a sensitivity label, not physical truth.

Metric misuse: sigma68 is reported with full RMS where relevant, and live-time/pile-up summaries include both continuous shifts and discrete secondary/tail fractions. No chi-square per ndf is quoted because the Huber closure and risk screens are robust predictive estimators, not parametric physics fits.

Post-hoc selection: the estimator list, Sample-II runs, risk thresholds, model families, 15% flagging fraction, and bootstrap count are fixed in the config. The report does not scan cuts after seeing the winner.

Systematics and caveats: the reference baseline is the S00 median4 gate, not an electronics pedestal truth sample. Odd-channel duplicate closure is an internal electronics consistency test, not absolute energy calibration. The bounded two-pulse summary is a compact template proxy for S10 sensitivity; it is not a direct two-particle truth label.

## 7. Provenance Manifest

`manifest.json` contains input hashes, command, config path, random seed, git commit, Python/platform metadata, and output hashes. `input_sha256.csv` pins every HRDB ROOT file read.

## 8. Findings and Next Steps

The main result is that pseudo-pedestal choices are measurable downstream nuisance handles. The best charge closure is `quietish` with res68 `0.0211`, while the largest tau shift is `0.00` ns and the largest timing-tail shift is `0.0151`. The risk-ranking winner is `cnn1d`, but the label is a sensitivity label derived from pseudo-pedestal perturbations. This supports using pseudo-pedestals as diagnostics and veto/risk annotations, not as correction-ready replacements for true forced/random pedestal data.

Hypothesis: selected beam pulses with unstable pre-trigger samples form a reproducible support atom that perturbs charge and live-time proxies, but the perturbation is estimator-defined. A true no-pulse pedestal acquisition should either confirm these atoms as electronics baseline contamination or falsify them as waveform-shape side effects.

Queued follow-up in `result.json`: `S16n: external no-pulse pedestal closure for pseudo-pedestal risk atoms`.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16m_1781038019_1322_46921ff8_pseudopedestal_charge_livetime_bias.py --config configs/s16m_1781038019_1322_46921ff8_pseudopedestal_charge_livetime_bias.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `selected_pulse_counts_by_run.csv`, `sample_ii_pulse_table.csv.gz`, `pedestal_estimator_summary.csv`, `charge_closure_benchmark.csv`, `charge_closure_predictions.csv.gz`, `livetime_pileup_summary.csv`, `risk_label_table.csv.gz`, `risk_model_benchmark.csv`, `risk_model_folds.csv`, `risk_model_predictions.csv.gz`, `risk_model_bootstrap_cis.csv`, and three figures.

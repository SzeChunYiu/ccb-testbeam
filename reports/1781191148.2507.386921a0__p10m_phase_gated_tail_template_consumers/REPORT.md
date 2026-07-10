# P10m: Frozen Phase-Gated Tail Templates for Downstream Consumers

**Ticket:** 1781191148.2507.386921a0  
**Worker:** testbeam-laptop-3  
**Date:** 2026-07-10  
**Raw input:** `/home/billy/ccb-data/extracted/root/root`  
**Git commit:** `6fce8edc68a587e914ed0be5b1eee939618440a4`

## Question

The P10l benchmark selected a ridge winner for waveform-template reconstruction, but its primary metric was still a local q-template loss. P10m asks whether a phase-gated tail template, frozen before any downstream consumer is fit, improves independent timing and charge-consumer outcomes relative to the P10l-style ridge comparator and a strong explicit-handle traditional baseline.

## Reproduction Gate

All B-stave pulses with amplitude greater than 1000 ADC were recounted from raw ROOT before fitting any consumer:

| quantity                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses |         640737 |       640737 |       0 |           0 | True   |

The equality requirement is exact; the analysis aborts if this table has any failing row.

## Methods

For pulse \(i\) in event \(e\) and stave \(s\), the raw waveform \(x_i(t)\) is baseline-subtracted by the median of samples 0--3. Amplitude \(A_i=\max_t x_i(t)\), charge proxy \(Q_i=\sum_t x_i(t)\), and CFD20 time \(c_i\) are computed directly from the raw waveform. The normalized waveform is \(u_i(t)=x_i(t)/A_i\).

The frozen template family is trained only inside each fold's training runs. Templates are medians of \(u_i(t)\) in cells keyed by stave, amplitude bin, and CFD phase bin:

\[
T_{s,a,p}(t)=\operatorname{median}\{u_i(t): s_i=s, a_i=a, p_i=p, i\in \mathcal{D}_\mathrm{train}\}.
\]

Cells below 25 pulses fall back to the train-only stave median. The downstream feature vector includes explicit handles \(\log A_i\), \(Q_i/A_i\), peak sample, CFD20 phase, rise width, normalized tail sums, categorical stave/bin labels, and frozen-template residual summaries \(\|u_i-T\|_2^2\), tail bias, and late-tail bias.

Timing and charge targets are event-internal leave-one-stave residuals. With geometry correction \(g_s\),

\[
y^t_i = (t_i-g_s)-\frac{1}{3}\sum_{r\ne s_i}(t_{e,r}-g_r),
\quad
y^q_i = \log Q_i-\frac{1}{3}\sum_{r\ne s_i}\log Q_{e,r}.
\]

Each method predicts \((\hat y^t_i,\hat y^q_i)\). Consumer values are \(t_i^\star=t_i-g_s-\hat y^t_i\) and \(q_i^\star=\log Q_i-\hat y^q_i\). Evaluation uses all pairwise same-event residuals among B2/B4/B6/B8. Per-run metrics are timing \(\sigma_{68}\) in ns and charge \(\sigma_{68}\) in log-charge units; 95% CIs are bootstraps over held-out runs.

## Compared Methods

- `traditional_explicit_handles`: train-only median residual tables keyed by stave, amplitude bin, phase bin, rise bin, and tail bin, with loose/stave/global fallbacks.
- `ridge`: P10l-style strong linear comparator on the explicit handles and frozen-template residual features.
- `gradient_boosted_trees`: multi-output gradient-boosted trees on the same tabular inputs.
- `mlp`: tabular neural network.
- `cnn_1d`: waveform CNN with tabular head.
- `phase_gated_cnn_new`: new architecture; a CNN representation is multiplicatively gated by phase/template-handle tabular features before the consumer head.
- `shuffled_target_ridge_sentinel`: leakage/sanity control; the ridge model is fit to row-permuted training targets and is reported only as a sentinel, not as a winner candidate.

## Results

| fold              | method                         | runs                                      |   n_eval_pulses |   n_events |   timing_sigma68_ns |   timing_sigma68_ns_ci_low |   timing_sigma68_ns_ci_high |   charge_sigma68_log |   charge_sigma68_log_ci_low |   charge_sigma68_log_ci_high |   timing_rms_ns |   timing_rms_ns_ci_low |   timing_rms_ns_ci_high |   charge_rms_log |   charge_rms_log_ci_low |   charge_rms_log_ci_high |   primary_loss |
|:------------------|:-------------------------------|:------------------------------------------|----------------:|-----------:|--------------------:|---------------------------:|----------------------------:|---------------------:|----------------------------:|-----------------------------:|----------------:|-----------------------:|------------------------:|-----------------:|------------------------:|-------------------------:|---------------:|
| holdout_sample_i  | gradient_boosted_trees         | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 |            2524 |        631 |            14.5983  |                    9.57898 |                    19.3748  |             0.325971 |                    0.282106 |                     0.362357 |        23.8089  |               19.655   |                 26.9412 |         0.955254 |                0.704335 |                 1.20194  |       17.858   |
| holdout_sample_i  | ridge                          | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 |            2524 |        631 |            15.4628  |                   10.9894  |                    19.8637  |             0.389692 |                    0.370737 |                     0.40695  |        24.7383  |               20.4084  |                 27.8937 |         0.959424 |                0.743162 |                 1.21374  |       19.3597  |
| holdout_sample_i  | phase_gated_cnn_new            | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 |            2524 |        631 |            16.9222  |                   11.42    |                    22.4544  |             0.552262 |                    0.507949 |                     0.598917 |        27.6147  |               22.6857  |                 31.3194 |         1.40393  |                1.10655  |                 1.682    |       22.4448  |
| holdout_sample_i  | mlp                            | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 |            2524 |        631 |            16.6078  |                   11.4935  |                    22.073   |             0.61254  |                    0.552279 |                     0.668632 |        27.0359  |               22.6043  |                 30.5144 |         1.36756  |                1.07324  |                 1.63194  |       22.7332  |
| holdout_sample_i  | traditional_explicit_handles   | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 |            2524 |        631 |            16.4098  |                   10.9707  |                    21.7922  |             0.656362 |                    0.598707 |                     0.703199 |        27.5149  |               22.3217  |                 30.9973 |         1.51455  |                1.21909  |                 1.79367  |       22.9734  |
| holdout_sample_i  | cnn_1d                         | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 |            2524 |        631 |            16.8067  |                   11.9901  |                    22.3489  |             0.650241 |                    0.596035 |                     0.708416 |        27.5669  |               22.9986  |                 31.1952 |         1.43861  |                1.15885  |                 1.70133  |       23.3091  |
| holdout_sample_i  | shuffled_target_ridge_sentinel | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 |            2524 |        631 |            16.8462  |                   11.4404  |                    22.4326  |             0.991961 |                    0.914401 |                     1.06785  |        28.0647  |               23.1464  |                 31.372  |         1.66087  |                1.44591  |                 1.85692  |       26.7658  |
| holdout_sample_ii | mlp                            | 58,59,60,61,62,63,65                      |           15096 |       3774 |             3.73394 |                    3.43257 |                     4.08545 |             0.282967 |                    0.247774 |                     0.324818 |         9.50375 |                7.70393 |                 11.5634 |         1.23189  |                1.14671  |                 1.32997  |        6.56361 |
| holdout_sample_ii | phase_gated_cnn_new            | 58,59,60,61,62,63,65                      |           15096 |       3774 |             4.51949 |                    4.12148 |                     4.86366 |             0.264108 |                    0.236372 |                     0.293296 |        10.9996  |                8.69979 |                 13.3065 |         1.28187  |                1.19488  |                 1.39922  |        7.16057 |
| holdout_sample_ii | cnn_1d                         | 58,59,60,61,62,63,65                      |           15096 |       3774 |             4.29421 |                    3.99983 |                     4.58325 |             0.311312 |                    0.280876 |                     0.344751 |        10.9154  |                8.51503 |                 13.4832 |         1.27585  |                1.18268  |                 1.37397  |        7.40733 |
| holdout_sample_ii | traditional_explicit_handles   | 58,59,60,61,62,63,65                      |           15096 |       3774 |             4.12562 |                    3.44164 |                     5.26411 |             0.408809 |                    0.383946 |                     0.432279 |        13.9869  |               11.3915  |                 16.6902 |         1.51542  |                1.43785  |                 1.60258  |        8.21371 |
| holdout_sample_ii | gradient_boosted_trees         | 58,59,60,61,62,63,65                      |           15096 |       3774 |             8.03812 |                    7.27787 |                     8.86698 |             0.223721 |                    0.211906 |                     0.237405 |        10.7723  |               10.047   |                 11.5726 |         0.558661 |                0.514383 |                 0.592471 |       10.2753  |
| holdout_sample_ii | shuffled_target_ridge_sentinel | 58,59,60,61,62,63,65                      |           15096 |       3774 |             4.97714 |                    4.61076 |                     5.33885 |             0.5361   |                    0.47541  |                     0.600601 |        12.6212  |               10.1021  |                 15.368  |         1.48335  |                1.37217  |                 1.6095   |       10.3381  |
| holdout_sample_ii | ridge                          | 58,59,60,61,62,63,65                      |           15096 |       3774 |            11.413   |                   11.0859  |                    11.6762  |             0.307285 |                    0.298377 |                     0.318212 |        12.8977  |               12.4487  |                 13.3022 |         0.902067 |                0.838182 |                 1.00327  |       14.4859  |

The winner named in `result.json` is **gradient_boosted_trees**, selected among non-sentinel methods by the mean of the fold-level primary loss `timing_sigma68_ns + 10 * charge_sigma68_log`. Timing and charge are both reported separately so the scalar score cannot hide a detector-performance tradeoff.

## Model Diagnostics

| model                          | status          |   train_rows |   eval_rows |   fit_predict_sec | meta                                               | fold              |
|:-------------------------------|:----------------|-------------:|------------:|------------------:|:---------------------------------------------------|:------------------|
| ridge                          | trained         |          828 |        2524 |              0.07 | nan                                                | holdout_sample_i  |
| gradient_boosted_trees         | trained         |          828 |        2524 |              0.15 | nan                                                | holdout_sample_i  |
| shuffled_target_ridge_sentinel | trained_control |          828 |        2524 |              0    | {"target": "row-permuted train targets"}           | holdout_sample_i  |
| mlp                            | trained         |          828 |        2524 |              0.05 | {"device": "cpu", "epochs": 8, "train_rows": 828}  | holdout_sample_i  |
| cnn_1d                         | trained         |          828 |        2524 |              0.07 | {"device": "cpu", "epochs": 6, "train_rows": 828}  | holdout_sample_i  |
| phase_gated_cnn_new            | trained         |          828 |        2524 |              0.13 | {"device": "cpu", "epochs": 6, "train_rows": 828}  | holdout_sample_i  |
| ridge                          | trained         |         2300 |       15096 |              0.02 | nan                                                | holdout_sample_ii |
| gradient_boosted_trees         | trained         |         2300 |       15096 |              0.54 | nan                                                | holdout_sample_ii |
| shuffled_target_ridge_sentinel | trained_control |         2300 |       15096 |              0.02 | {"target": "row-permuted train targets"}           | holdout_sample_ii |
| mlp                            | trained         |         2300 |       15096 |              0.22 | {"device": "cpu", "epochs": 8, "train_rows": 2300} | holdout_sample_ii |
| cnn_1d                         | trained         |         2300 |       15096 |              0.19 | {"device": "cpu", "epochs": 6, "train_rows": 2300} | holdout_sample_ii |
| phase_gated_cnn_new            | trained         |         2300 |       15096 |              0.19 | {"device": "cpu", "epochs": 6, "train_rows": 2300} | holdout_sample_ii |

## Systematics and Caveats

Run-family splits are deliberately harsh: Sample-I analysis is evaluated after training on run 64 only, while Sample-II analysis is evaluated after training on Sample-I calibration runs. This tests transport across sample/current families but gives the Sample-I holdout a small training source. The charge target uses the raw area sum as a stable charge proxy, not a calibrated energy scale. The bootstrap treats runs as exchangeable units within each fold; it captures run-to-run variation but not alternate waveform preprocessing choices. All template and consumer fits are train-only within fold, and event identifiers, run labels, and held-out peer residuals are excluded from model features. The shuffled-target ridge sentinel is included to make gross leakage visible; it is excluded from winner selection by construction.

## Files

The report directory contains `result.json`, `manifest.json`, `reproduction_match_table.csv`, `fold_run_metrics.csv`, `fold_summary.csv`, `model_diagnostics.csv`, `template_support.csv`, `input_sha256.csv`, and `fig_consumer_summary.png`.

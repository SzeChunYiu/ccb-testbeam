# P12b Pulse-Support Tensor for PID Energy Consumers

- **Ticket:** `1781040960.896.205a0b9d`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT under `/home/billy/ccb-data/extracted/root/root`
- **Primary benchmark target:** held-out charge-transfer failure risk, `charge_transfer_error = 1`.
- **Split:** train on non-Sample-II-analysis runs; evaluate on runs 58, 59, 60, 61, 62, 63, and 65.
- **Uncertainty:** run-block bootstrap 95 percent confidence intervals.

## 1. Raw-ROOT Reproduction

The first operation is a direct scan of `h101/HRDv` in the raw ROOT files. For every configured B-stack run, the script subtracts the median of samples 0--3, selects even B staves B2/B4/B6/B8, and applies `A > 1000 ADC`. No downstream support tensor or model output is written unless this count check passes.

| quantity                                      |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses                 |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib events with selected pulse     |         239559 |       239559 |       0 |           0 | True   |
| sample_i_calib selected pulses                |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis events with selected pulse  |         243133 |       243133 |       0 |           0 | True   |
| sample_i_analysis selected pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_i_analysis B2 selected pulses          |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4 selected pulses          |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6 selected pulses          |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8 selected pulses          |           1299 |         1299 |       0 |           0 | True   |
| sample_ii_calib events with selected pulse    |          12103 |        12103 |       0 |           0 | True   |
| sample_ii_calib selected pulses               |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis events with selected pulse |          89807 |        89807 |       0 |           0 | True   |
| sample_ii_analysis selected pulses            |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2 selected pulses         |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4 selected pulses         |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6 selected pulses         |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8 selected pulses         |           4506 |         4506 |       0 |           0 | True   |

## 2. Estimand and Tensor Definition

For pulse record `i`, let `x_i` denote the baseline-corrected B-stack pulse summaries and let `r_i` be the charge residual from the P12 charge model fitted on non-Sample-II-analysis runs. The benchmark label is

`y_i = 1{|r_i| >= tau_train}`,

where `tau_train` is the 95 percent absolute residual threshold fitted on the same non-held-out run family. The support tensor is a contingency table over ten atoms:

`shape x timing x amplitude x saturation x pileup x baseline x dropout/anomaly x q_template x covariance x charge_transfer`.

The charge-transfer atom is included in the published tensor for consumers, but it is excluded from all benchmark model features so the risk benchmark is not tautological. The q-template atom is a morphology score from late fraction, half-height width, and peak phase; the covariance atom counts concurrent non-target pathology flags.

## 3. Methods

The traditional method is `empirical_bayes_support`, a hierarchical support-cell estimator. For predictor cell `c`, with `s_c` failures in `n_c` training pulses and global failure rate `pi`, it predicts

`p(y=1|c) = (s_c + k pi)/(n_c + k)`, with `k = 30`, falling back to a coarser stave-amplitude-shape-timing-pileup-baseline cell and then the global rate.

The ML/NN comparators are ridge logistic regression, histogram gradient-boosted trees, a tabular MLP, a 1D-CNN over the ordered standardized feature vector, and the new `tensor_prior_residual_cnn_new_arch`. The new architecture is sensible for P12b because it fuses a convolutional residual learner with the empirical tensor-prior logit, forcing the neural branch to learn departures from the deterministic support tensor rather than replacing it.

## 4. Benchmark Results

| method                             | family           |      n |   event_rate |      auc | auc_ci95                                 |   average_precision |     brier | brier_ci95                                   |        ece | ece_ci95                                     |   support_coverage_at_risk10 |   failure_rate_at_risk10 |
|:-----------------------------------|:-----------------|-------:|-------------:|---------:|:-----------------------------------------|--------------------:|----------:|:---------------------------------------------|-----------:|:---------------------------------------------|-----------------------------:|-------------------------:|
| mlp                                | nn               | 125096 |    0.0748865 | 0.990439 | [0.987996183628281, 0.9930296956379074]  |            0.922499 | 0.01694   | [0.01174991772058091, 0.020424904315331036]  | 0.00318606 | [0.00212040409498573, 0.005222242107887179]  |                     0.88261  |               0.00403945 |
| gradient_boosted_trees             | ml               | 125096 |    0.0748865 | 0.98893  | [0.9859989981602924, 0.9919704419679637] |            0.904421 | 0.0198206 | [0.015057454698973361, 0.023450907700940046] | 0.0078664  | [0.004976696861564045, 0.010987966156557262] |                     0.8856   |               0.00419732 |
| empirical_bayes_support            | traditional      | 125096 |    0.0748865 | 0.898072 | [0.880639653450252, 0.9178406518659825]  |            0.486466 | 0.0517304 | [0.03810941785510169, 0.06348238580968425]   | 0.0170089  | [0.010621038175984638, 0.02601991302876508]  |                     0.866846 |               0.0286336  |
| tensor_prior_residual_cnn_new_arch | new_architecture | 125096 |    0.0748865 | 0.913121 | [0.8955629288056827, 0.931880182109943]  |            0.467733 | 0.139975  | [0.11585315061246913, 0.16079498850030438]   | 0.245376   | [0.21678916902539805, 0.2689444024892904]    |                     0.347285 |               0.001266   |
| ridge                              | ml               | 125096 |    0.0748865 | 0.920551 | [0.9061013186910235, 0.9384957628784459] |            0.530349 | 0.143422  | [0.11730960290841635, 0.1618012754180305]    | 0.227844   | [0.203018602441926, 0.24769728620180564]     |                     0.462821 |               0.0038344  |
| 1d_cnn                             | nn               | 125096 |    0.0748865 | 0.850485 | [0.8277875066755642, 0.871992268292501]  |            0.355755 | 0.19757   | [0.16878323512032528, 0.2261228883705027]    | 0.342429   | [0.3164598977834937, 0.36571355437891223]    |                     0        |             nan          |

Winner by the preregistered primary metric, minimum held-out Brier score, is `mlp` (`nn`) with Brier `0.016940` and 95 percent CI `[0.01174991772058091, 0.020424904315331036]`. Lower Brier and ECE are better; higher AUC/AP and support coverage at fixed risk are better.

Run-level Brier scores:
|   run |   1d_cnn |   empirical_bayes_support |   gradient_boosted_trees |        mlp |     ridge |   tensor_prior_residual_cnn_new_arch |
|------:|---------:|--------------------------:|-------------------------:|-----------:|----------:|-------------------------------------:|
|    58 | 0.103149 |                 0.0170549 |               0.00556254 | 0.00544509 | 0.0855605 |                            0.066994  |
|    59 | 0.225646 |                 0.0596772 |               0.0257875  | 0.0220663  | 0.162584  |                            0.163805  |
|    60 | 0.230261 |                 0.0629362 |               0.0227871  | 0.019426   | 0.172794  |                            0.166819  |
|    61 | 0.223037 |                 0.070937  |               0.0245301  | 0.0221595  | 0.162967  |                            0.165518  |
|    62 | 0.229436 |                 0.0591256 |               0.0226243  | 0.0188176  | 0.163208  |                            0.162923  |
|    63 | 0.187588 |                 0.047275  |               0.02001    | 0.016514   | 0.137239  |                            0.133613  |
|    65 | 0.161076 |                 0.0363606 |               0.0132858  | 0.0103568  | 0.0996425 |                            0.0982059 |

## 5. Published Support Tensor

Each row in `support_tensor.csv` is one populated atom cell. The table records occupancy, number of runs, charge failure rate, charge residual sigma68, timing-tail rate, pile-up enrichment, and weak PID-label stability. The top populated cells are:

| support_cell                                                                                                                                                      |     n |   n_runs |   charge_failure_rate |   charge_res68 |   timing_tail_rate |   pileup_rate |   weak_pid_fraction |   weak_pid_run_span |
|:------------------------------------------------------------------------------------------------------------------------------------------------------------------|------:|---------:|----------------------:|---------------:|-------------------:|--------------:|--------------------:|--------------------:|
| shape_nominal|timing_core|amp_extreme_ge7000|sat_high_amp|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_low|covariance_sparse|charge_transfer_ok             | 80115 |       33 |                     0 |       0.450678 |                  0 |             0 |            0.893915 |           0.122248  |
| shape_late_tail|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_extreme|covariance_sparse|charge_transfer_ok            | 44507 |       33 |                     0 |       1.05192  |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_extreme_ge7000|sat_high_amp|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok        | 34846 |       33 |                     0 |       0.817342 |                  0 |             0 |            0.904724 |           0.127873  |
| shape_nominal|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok                 | 21346 |       33 |                     0 |       1.41705  |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_like|baseline_quiet|anomaly_secondary_peak|qtemplate_low|covariance_sparse|charge_transfer_ok         | 19537 |       33 |                     0 |       0.870279 |                  0 |             1 |            0        |           0         |
| shape_late_tail|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok               | 19275 |       33 |                     0 |       0.666343 |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_extreme|covariance_sparse|charge_transfer_ok              | 18414 |       33 |                     0 |       1.30379  |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_low_1000_2000|sat_none|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok                 | 17827 |       33 |                     0 |       0.969331 |                  0 |             0 |            0        |           0         |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok              | 14411 |       33 |                     0 |       1.04463  |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok             | 12841 |       33 |                     0 |       1.66034  |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok                  | 11539 |       33 |                     0 |       0.86408  |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok                 | 11117 |       33 |                     0 |       0.78548  |                  0 |             0 |            0        |           0         |
| shape_nominal|timing_core|amp_extreme_ge7000|sat_high_amp|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok            | 10895 |       33 |                     0 |       1.24642  |                  0 |             0 |            0.996879 |           0.0416667 |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_plateau|pileup_like|baseline_quiet|anomaly_secondary_peak|qtemplate_low|covariance_sparse|charge_transfer_ok      |  8725 |       33 |                     0 |       1.14348  |                  0 |             1 |            0        |           0         |
| shape_late_tail|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_secondary_peak|qtemplate_moderate|covariance_sparse|charge_transfer_ok |  8423 |       33 |                     0 |       0.926728 |                  0 |             1 |            0        |           0         |
| shape_late_tail|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok           |  8395 |       33 |                     0 |       0.130446 |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_secondary_peak|qtemplate_moderate|covariance_sparse|charge_transfer_ok   |  8376 |       33 |                     0 |       0.677041 |                  0 |             1 |            0        |           0         |
| shape_nominal|timing_core|amp_extreme_ge7000|sat_boundary|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_low|covariance_coupled|charge_transfer_ok            |  7385 |       33 |                     0 |       0.682944 |                  0 |             0 |            0        |           0         |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_plateau|pileup_like|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok           |  7164 |       33 |                     0 |       1.19168  |                  0 |             1 |            0        |           0         |
| shape_late_tail|timing_core|amp_extreme_ge7000|sat_high_amp|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_low|covariance_sparse|charge_transfer_ok           |  7156 |       33 |                     0 |       0.145112 |                  0 |             0 |            0.484069 |           0.627451  |

Run-block CIs for the top cells are in `support_tensor_ci.csv`; preview:
| support_cell                                                                                                                                               | metric              |   value |   ci_low |   ci_high |
|:-----------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------|--------:|---------:|----------:|
| shape_nominal|timing_core|amp_extreme_ge7000|sat_high_amp|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_low|covariance_sparse|charge_transfer_ok      | charge_failure_rate |       0 |        0 |         0 |
| shape_late_tail|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_extreme|covariance_sparse|charge_transfer_ok     | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_extreme_ge7000|sat_high_amp|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok          | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_like|baseline_quiet|anomaly_secondary_peak|qtemplate_low|covariance_sparse|charge_transfer_ok  | charge_failure_rate |       0 |        0 |         0 |
| shape_late_tail|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok        | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_extreme|covariance_sparse|charge_transfer_ok       | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_low_1000_2000|sat_none|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok          | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok       | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_high_4000_7000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_moderate|covariance_sparse|charge_transfer_ok      | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_like|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok           | charge_failure_rate |       0 |        0 |         0 |
| shape_nominal|timing_core|amp_mid_2000_4000|sat_none|pileup_quiet|baseline_quiet|anomaly_none|qtemplate_high|covariance_sparse|charge_transfer_ok          | charge_failure_rate |       0 |        0 |         0 |

## 6. Systematics and Controls

- **Run family drift:** all headline intervals resample run blocks, so the uncertainty is dominated by run-to-run changes rather than pulse-count statistics.
- **Target definition:** `charge_transfer_error` is a closure-failure proxy, not an absolute PID or energy truth label.
- **Support sparsity:** high-dimensional cells can be populated by many pulses from few runs; consumers should check both `n` and `n_runs`.
- **q-template proxy:** no frozen per-pulse q-template likelihood exists in the current committed artifacts, so this report uses a reproducible morphology proxy from raw-derived pulse summaries.
- **Neural calibration:** the CNNs are intentionally small CPU-trained models; they are benchmark comparators, not production calibrators.
- **Leakage:** event identifiers, run identifiers, and the charge-transfer target are excluded from the feature matrix; the published charge-transfer atom is not used as a predictor.

| check                                               | value                                                                                                                                                                                                                                                                                                                                                                                                        | pass   |
|:----------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------|
| heldout_runs_excluded_from_training                 | 58,59,60,61,62,63,65                                                                                                                                                                                                                                                                                                                                                                                         | True   |
| model_features_exclude_event_ids                    | log_amp,amplitude_adc,area_over_amp,peak_sample,width035_samples,width050_samples,plateau_count,secondary_peak_rel,late_fraction,seed_baseline_adc,pre_rms_adc,pre_max_exc_adc,adaptive_lowering_adc,event_timing_abs_resid_ns_filled,active_atom_count_no_charge,stave,amplitude_atom,shape_atom,timing_atom,saturation_atom,pileup_atom,baseline_atom,dropout_anomaly_atom,q_template_atom,covariance_atom | True   |
| target_charge_transfer_error_excluded_from_features | charge_transfer_error                                                                                                                                                                                                                                                                                                                                                                                        | True   |
| evaluation_runs_present                             | 7                                                                                                                                                                                                                                                                                                                                                                                                            | True   |
| training_rows_after_cap                             | 30000                                                                                                                                                                                                                                                                                                                                                                                                        | True   |
| evaluation_rows                                     | 125096                                                                                                                                                                                                                                                                                                                                                                                                       | True   |

## 7. Caveats

The tensor is a map of current support, not a permission slip for physics separation. PID and energy workers should treat unsupported or high-risk cells as abstention candidates unless an independent truth source or calibration target confirms them. The weak PID label is deliberately operational, based on high-amplitude non-pileup non-saturated timing-core pulses; it should not be interpreted as particle identity. The raw-ROOT reproduction fixes the event population, but alternate baseline windows, amplitude cuts, or charge residual definitions would change the support frontier.

## 8. Verdict

`mlp` is the winner for P12b by held-out Brier score. The published tensor identifies which pulse atom combinations are populated and gives consumers per-cell occupancy, run support, timing-tail, pile-up, charge-closure, and weak-label stability diagnostics. The strongest practical rule is to require both multi-run occupancy and low empirical or model-predicted charge-transfer risk before using a cell for PID/energy calibration.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p12b_1781040960_896_205a0b9d_pulse_support_tensor.py --config configs/p12b_1781040960_896_205a0b9d_pulse_support_tensor.json
```

Runtime: 432.6 s.

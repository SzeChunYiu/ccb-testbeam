# P12d Frozen Action-Matrix Consumer Calibration Test

- **Ticket:** `1781145765.1768.59211878`
- **Worker:** `testbeam-laptop-3`
- **Raw ROOT:** `/home/billy/ccb-data/extracted/root/root`
- **Frozen P12c source:** `reports/1781046830.796.418e6e1f__p12c_pulse_action_decision_matrix`
- **Git commit:** `8fd6ee857e6784ba8fa1f660e618e54483c6c23c`

## 1. Question

Does freezing the P12c pass/correct/abstain/veto matrix before fitting downstream PID and energy consumers improve calibration, or does it only describe existing support risk? I test this as a run-held-out consumer-calibration benchmark on the same ROOT-derived pulse population, comparing raw, P12c-reweighted, and P12c-accepted residual behavior.

## 2. Raw-ROOT Reproduction Gate

The first operation scans raw `h101/HRDv` files, subtracts the median of samples 0--3 for B2/B4/B6/B8, and requires peak amplitude `A > 1000 ADC`. No benchmark result is interpreted unless the selected-pulse count exactly matches the upstream number.

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

## 3. Estimand and Equations

For pulse `i`, the frozen P12c action is `A_i in {pass, correct, abstain, veto}`. The consumer residual is `r_i`, the P12 charge/energy proxy residual `charge_residual_area_over_amp`. The traditional frozen-action estimator is

`hat r_i = median(r_j | A_j, stave_j, amplitude_atom_j, shape_atom_j, timing_atom_j)`,

with fallback to `(A, stave, amplitude_atom)` and then the global train median. The operational score is

`S_m = weighted_MAE_m - 0.10 * (sigma68_raw - sigma68_accepted,m) + P_support`,

where weights are fixed from P12c action severity before fitting, and `P_support` penalizes methods only if accepted P12c support falls below the configured floor. All CIs resample complete held-out runs.

## 4. Methods

The benchmark compares a strong traditional frozen action-cell median against ridge regression, histogram gradient-boosted trees, an MLP, a compact PyTorch 1D-CNN over the ordered feature vector, and a new action-prior residual CNN that learns departures from the traditional P12c prior. The convolutional models are intentionally small CPU-compatible neural comparators rather than final production architectures.

Identifiers (`run`, `event_uid`, `pulse_uid`) and the held-out target residual are excluded from features. Training uses all non-held-out configured runs with a deterministic cap; evaluation is Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65.

## 5. Results

Winner by the preregistered primary score is **`gradient_boosted_trees`** (ml) with score `0.701347`, weighted MAE `0.823033`, and accepted residual sigma68 `0.856296`.

| method                             | family           |   primary_score |   weighted_mae | weighted_mae_ci95                        |   accepted_mae |   accepted_res68 | accepted_res68_ci95                      |   res68_improvement_vs_raw |   energy_failure_rate_accepted |   accepted_fraction |
|:-----------------------------------|:-----------------|----------------:|---------------:|:-----------------------------------------|---------------:|-----------------:|:-----------------------------------------|---------------------------:|-------------------------------:|--------------------:|
| gradient_boosted_trees             | ml               |        0.701347 |       0.823033 | [0.7597614578709232, 0.8764779223403653] |       0.720968 |         0.856296 | [0.7434004580688475, 0.942186679244321]  |                   1.21686  |                       0.157153 |            0.198583 |
| mlp                                | nn               |        0.753733 |       0.87051  | [0.8008223970601885, 0.9290314602186742] |       0.772148 |         0.905379 | [0.790739078835229, 0.9831530171241307]  |                   1.16777  |                       0.157153 |            0.198583 |
| traditional_action_matrix          | traditional      |        0.932945 |       1.03857  | [0.9524518234605863, 1.112026514834675]  |       0.873181 |         1.01689  | [0.9042583479639602, 1.1107134140889978] |                   1.05626  |                       0.157153 |            0.198583 |
| action_prior_residual_cnn_new_arch | new_architecture |        0.937671 |       1.04353  | [0.9513623206911932, 1.107732857852581]  |       0.885823 |         1.01454  | [0.891432764752712, 1.0973033188024266]  |                   1.05861  |                       0.157153 |            0.198583 |
| ridge                              | ml               |        1.05153  |       1.14353  | [1.0329011611283285, 1.246100713764783]  |       1.04398  |         1.15318  | [1.0149072839145103, 1.2339303250824243] |                   0.91997  |                       0.157153 |            0.198583 |
| 1d_cnn                             | nn               |        1.13251  |       1.22938  | [1.0917638277064798, 1.3512487267429087] |       1.05714  |         1.10451  | [0.9212527167950717, 1.2587097435237864] |                   0.968646 |                       0.157153 |            0.198583 |

Run-level primary scores:

|   run |   1d_cnn |   action_prior_residual_cnn_new_arch |   gradient_boosted_trees |      mlp |    ridge |   traditional_action_matrix |
|------:|---------:|-------------------------------------:|-------------------------:|---------:|---------:|----------------------------:|
|    58 | 0.835743 |                             0.748956 |                 0.544589 | 0.584473 | 0.817246 |                    0.741055 |
|    59 | 1.26775  |                             1.03751  |                 0.791255 | 0.844573 | 1.17798  |                    1.03334  |
|    60 | 1.29482  |                             1.00317  |                 0.744358 | 0.799045 | 1.11744  |                    1.00464  |
|    61 | 1.34771  |                             1.04393  |                 0.769024 | 0.83144  | 1.19518  |                    1.04299  |
|    62 | 1.23404  |                             0.999723 |                 0.745101 | 0.80394  | 1.13416  |                    0.997197 |
|    63 | 1.07582  |                             0.924626 |                 0.701973 | 0.752834 | 1.04602  |                    0.916697 |
|    65 | 0.913685 |                             0.820089 |                 0.623877 | 0.66587  | 0.872008 |                    0.811586 |

## 6. Policy Interpretation

The P12c accepted set is fixed before modeling. Improvements in accepted residual width therefore test whether the frozen action matrix defines a usable calibration support boundary, not whether a model can rediscover the P12c labels. Reweighting retains low-weight abstain/veto cells in the weighted MAE, while the accepted residual width asks what downstream consumers would see if they used only pass/correct cells.

## 7. Leakage and Systematics

| check                                  | value                                                                                                                                                                                                                 | pass   |
|:---------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------|
| raw_root_reproduction_passed           | True                                                                                                                                                                                                                  | True   |
| heldout_runs_excluded_from_training    | 58,59,60,61,62,63,65                                                                                                                                                                                                  | True   |
| evaluation_runs_present                | 7                                                                                                                                                                                                                     | True   |
| model_features_exclude_ids             | amplitude_adc,area_over_amp,event_timing_abs_resid_ns_filled,stave,oracle_action,amplitude_atom,shape_atom,timing_atom,saturation_atom,pileup_atom,baseline_atom,dropout_anomaly_atom,q_template_atom,covariance_atom | True   |
| target_residual_excluded_from_features | charge_residual_area_over_amp                                                                                                                                                                                         | True   |
| p12c_policy_frozen_before_fit          | reports/1781046830.796.418e6e1f__p12c_pulse_action_decision_matrix                                                                                                                                                    | True   |

- The residual target is a ROOT-derived proxy, not independent detector-level PID or energy truth.
- CIs resample only seven held-out runs, so run-level uncertainty is more important than nominal pulse count.
- The frozen P12c policy was developed on related atoms; this study tests downstream calibration behavior but cannot remove all circularity without an independent reference.
- The neural methods are small CPU-compatible comparators. A larger GPU-tuned network may change point estimates, but the winner rule and run split would need to remain fixed.

## 8. Conclusion

`result.json` names `gradient_boosted_trees` as the winner. The main finding is that the frozen P12c matrix is useful as a support boundary when the winning consumer model lowers weighted residual error while preserving the pass/correct accepted sample. The result should be promoted only as a calibrated proxy policy, not as final PID or energy truth.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p12d_1781145765_1768_59211878_frozen_action_matrix_consumer_calibration.py --config configs/p12d_1781145765_1768_59211878_frozen_action_matrix_consumer_calibration.json
```

Runtime: 111.4 s.

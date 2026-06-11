# P12d Consumer Action Conflict Arbitration

- **Study ID:** `P12d`
- **Ticket:** `1781054026.1869.66191fe9`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Raw data:** `/home/billy/ccb-data/extracted/root/root`
- **No detector Monte Carlo:** all labels are operational pulse-atom and downstream-consumer proxies.
- **Git commit:** `92fbdd8fb660b6c3dd6d4f70e5ac0c02c31c6ad9`
- **Config:** `configs/p12d_1781054026_1869_66191fe9_consumer_action_conflict_arbitration.json`

## 1. Question and Reproduction Gate

P12d asks: when frozen pulse-action rules disagree across timing, charge, saturation, pile-up, baseline, dropout, PID, and energy consumers, which conflict patterns predict downstream harm rather than harmless support mismatch? The first operation is a direct raw-ROOT scan of `h101/HRDv`: median samples 0--3 are subtracted for B2/B4/B6/B8, and a pulse is selected when `A > 1000 ADC`. The benchmark is not evaluated unless this exact count gate passes.

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

## 2. Estimand and Conflict Algebra

For pulse `i` and consumer `c`, the frozen P12c action rule returns
`A_c(i) in {pass, correct, abstain, veto}`.
Map actions to severities `s(pass)=0`, `s(correct)=1`, `s(abstain)=2`, and `s(veto)=3`. A pulse has a conflict when
`C_i = 1{ |{A_c(i): c in consumers}| > 1 }`.
The operational harm label is
`H_i = 1{charge_transfer_error or timing_tail or pileup_like or baseline_harm or dropout_harm or pid_energy_proxy_degradation or covariance_harm}`.
The classifier target is the harmful-conflict indicator `Y_i = C_i H_i`. This is not particle truth; it is a frozen downstream-consumer risk proxy built from raw-derived pulse atoms.

Dominant conflict patterns in held-out Sample-II analysis runs:
| conflict_pattern   |     n |   support_fraction |   conflict_rate |   harmful_conflict_rate |   timing_tail_rate |   charge_res68 |   pid_energy_proxy_degradation |
|:-------------------|------:|-------------------:|----------------:|------------------------:|-------------------:|---------------:|-------------------------------:|
| p0_c0_a0_v8        | 50128 |         0.400716   |               0 |              0          |         0.0792172  |       1.95984  |                       0.471333 |
| p5_c1_a2_v0        | 18460 |         0.147567   |               1 |              1          |         0          |       1.05345  |                       0        |
| p4_c2_a2_v0        | 17459 |         0.139565   |               1 |              1          |         0          |       1.06961  |                       0        |
| p7_c1_a0_v0        | 11762 |         0.0940238  |               1 |              0.00586635 |         0.00586635 |       0.839207 |                       0        |
| p1_c1_a5_v1        |  6125 |         0.0489624  |               1 |              1          |         0.99951    |       1.458    |                       1        |
| p6_c2_a0_v0        |  5722 |         0.0457409  |               1 |              0.328032   |         0.328032   |       1.21849  |                       0        |
| p5_c3_a0_v0        |  5022 |         0.0401452  |               1 |              0.168658   |         0.168658   |       0.940894 |                       0        |
| p1_c1_a6_v0        |  4069 |         0.032527   |               1 |              1          |         0          |       2.40973  |                       1        |
| p3_c3_a2_v0        |  1272 |         0.0101682  |               1 |              1          |         0          |       1.34609  |                       0        |
| p8_c0_a0_v0        |  1069 |         0.00854544 |               0 |              0          |         0          |       0.4994   |                       0        |
| p4_c4_a0_v0        |  1013 |         0.00809778 |               1 |              0.0286278  |         0.0286278  |       1.6039   |                       0        |
| p0_c1_a7_v0        |   779 |         0.00622722 |               1 |              1          |         0          |       1.71937  |                       1        |
| p2_c0_a6_v0        |   371 |         0.00296572 |               1 |              1          |         0.202156   |       1.43193  |                       1        |
| p2_c6_a0_v0        |   254 |         0.00203044 |               1 |              0          |         0          |       1.94925  |                       0        |
| p4_c3_a1_v0        |   242 |         0.00193451 |               1 |              1          |         0          |       2.30338  |                       0        |
| p6_c1_a1_v0        |   234 |         0.00187056 |               1 |              1          |         0          |       0.969944 |                       0        |

## 3. Traditional Arbitration Rule

The strong traditional baseline is `traditional_precedence_ladder`. It freezes the P12c action tables, then rejects a conflict if a priority consumer (timing, charge, PID, energy) vetoes, if veto/abstain support is broad, or if the non-charge active-atom count marks sparse coupled support. Algebraically, the reject indicator is
`R_i^trad = C_i * 1{ priority_veto or (n_abstain+n_veto>=4 and harm_score>=1) or (active_atoms>=4 and n_pass<=2) }`.
This is deliberately strong: it is transparent, consumer-prioritized, and allowed to use the same frozen harm atoms that motivate the action table.

## 4. ML and Neural Comparators

All learned comparators are trained on non-held-out runs and evaluated only on Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65. Features are the predeclared P12 predictor atoms and raw pulse summaries from P12b: no run id, event id, pulse id, `harmful_conflict`, `charge_transfer_error`, or `charge_transfer_atom` is in the model matrix. The methods are ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN, and the new `conflict_prior_residual_cnn_new_arch`. The new architecture appends the empirical conflict-cell prior logit to a small convolutional residual learner, so it can only win by learning departures from the transparent conflict prior.

## 5. Benchmark Results

Primary score is lower-is-better: harmful-conflict Brier score plus penalties for recall below 0.70, accepted support below 0.15, positive PID drift, and positive energy-proxy degradation. CIs are event-paired run-block bootstraps over held-out runs.

| method                               | family           |   n_conflicts |   conflict_rate |   harmful_conflict_rate |      auc |      brier |   harmful_conflict_precision |   harmful_conflict_recall |   accepted_support_fraction |   timing_tail_delta |   charge_res68_delta |   charge_bias_delta |   pid_weak_label_drift |   energy_proxy_degradation_delta |   primary_score |
|:-------------------------------------|:-----------------|--------------:|----------------:|------------------------:|---------:|-----------:|-----------------------------:|--------------------------:|----------------------------:|--------------------:|---------------------:|--------------------:|-----------------------:|---------------------------------:|----------------:|
| gradient_boosted_trees               | ml               |         73899 |        0.590738 |                0.423259 | 0.999935 | 0.00182546 |                     0.999602 |                  0.997299 |                    0.177    |          -0.106422  |            -0.969333 |           -0.88034  |              0.115548  |                        -0.280305 |      0.00760283 |
| mlp                                  | nn               |         73899 |        0.590738 |                0.423259 | 0.999793 | 0.00279658 |                     0.999791 |                  0.995845 |                    0.177696 |          -0.106422  |            -0.963531 |           -0.88625  |              0.11534   |                        -0.276867 |      0.00856356 |
| ridge                                | ml               |         73899 |        0.590738 |                0.423259 | 0.999625 | 0.00297176 |                     0.999375 |                  0.996053 |                    0.177432 |          -0.106422  |            -0.965103 |           -0.885901 |              0.1156    |                        -0.277348 |      0.00875176 |
| conflict_prior_residual_cnn_new_arch | new_architecture |         73899 |        0.590738 |                0.423259 | 0.999434 | 0.0192434  |                     0.980591 |                  1        |                    0.167647 |          -0.106422  |            -1.0067   |           -0.823191 |              0.121831  |                        -0.286764 |      0.0253349  |
| 1d_cnn                               | nn               |         73899 |        0.590738 |                0.423259 | 0.887184 | 0.12794    |                     0.879556 |                  0.797046 |                    0.21573  |          -0.106422  |            -1.10949  |           -0.485276 |              0.0850124 |                        -0.285874 |      0.13219    |
| traditional_precedence_ladder        | traditional      |         73899 |        0.590738 |                0.423259 | 0.615642 | 0.550778   |                     1        |                  0.231284 |                    0.501391 |          -0.0614301 |            -0.873575 |           -0.457224 |              0.0214256 |                        -0.286764 |      0.669028   |

Bootstrap 95 percent intervals:
| method                               | brier_ci95                                     | harmful_conflict_precision_ci95          | harmful_conflict_recall_ci95               | accepted_support_fraction_ci95             | timing_tail_delta_ci95                        | charge_res68_delta_ci95                    | pid_weak_label_drift_ci95                    | energy_proxy_degradation_delta_ci95          |
|:-------------------------------------|:-----------------------------------------------|:-----------------------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------------|:-------------------------------------------|:---------------------------------------------|:---------------------------------------------|
| gradient_boosted_trees               | [0.0011379194442253673, 0.0027523520894702784] | [0.9994444592211265, 0.9997622176830449] | [0.9959827436080108, 0.9983591662365509]   | [0.14813195773866653, 0.21483303544568122] | [-0.13888163738202525, -0.06249713376200619]  | [-1.0063222714975026, -0.8805151525532247] | [0.07015748432199168, 0.15752331476083875]   | [-0.33146424860585477, -0.20586364034864915] |
| mlp                                  | [0.001745489270852148, 0.004189389745432328]   | [0.9997271371639129, 0.9998745601940772] | [0.9937139607498454, 0.9974063451668965]   | [0.14724372583874795, 0.21420712638660308] | [-0.14356546889837696, -0.061430864285567516] | [-1.0013479862390875, -0.8643533934293925] | [0.06791478166466663, 0.15755897473224362]   | [-0.3333149740670924, -0.2000278721028446]   |
| ridge                                | [0.0017855163711637944, 0.00447754882620421]   | [0.9991534444282298, 0.9995421952101576] | [0.9939931962884775, 0.9975930718164144]   | [0.14617883059804657, 0.21082600404169125] | [-0.14094412218394795, -0.07199250902969004]  | [-1.0040120405929818, -0.8851236275435199] | [0.07001178117378577, 0.16119314262762768]   | [-0.3336592065906868, -0.21084145143208516]  |
| conflict_prior_residual_cnn_new_arch | [0.013197668508212404, 0.02453815711651123]    | [0.974917811479517, 0.9877975508187135]  | [1.0, 1.0]                                 | [0.1361435827258669, 0.20735923628031333]  | [-0.1388659827819375, -0.06863942615238976]   | [-1.0513178245909514, -0.9110194935951768] | [0.07430116118599461, 0.16448896682752667]   | [-0.3423563309178598, -0.21284706813077578]  |
| 1d_cnn                               | [0.11862763078522391, 0.13722663887976128]     | [0.8632384208112728, 0.8957120580013727] | [0.7478142465756318, 0.8379168939433393]   | [0.166900707206274, 0.27797773281616406]   | [-0.13812475539208663, -0.061598737490005516] | [-1.1905665116645845, -0.990179466614974]  | [0.05057691791117837, 0.11092333302259101]   | [-0.3395866131778434, -0.2091661444316471]   |
| traditional_precedence_ladder        | [0.5340318797330003, 0.5760690444302685]       | [1.0, 1.0]                               | [0.17774724709658807, 0.27482881077101307] | [0.45081366652320104, 0.5709210267588776]  | [-0.07617579109148058, -0.041583913670560434] | [-0.9460789573296129, -0.7673402652931548] | [0.012540119499358016, 0.030516987973484785] | [-0.34086320232391737, -0.21101398759729292] |

Winner by the preregistered operational score is `gradient_boosted_trees` (`ml`), with primary score `0.007603`, Brier `0.001825`, harmful-conflict precision `1.000`, recall `0.997`, and accepted support fraction `0.177`.

Run-level primary scores:
|   run |   1d_cnn |   conflict_prior_residual_cnn_new_arch |   gradient_boosted_trees |        mlp |      ridge |   traditional_precedence_ladder |
|------:|---------:|---------------------------------------:|-------------------------:|-----------:|-----------:|--------------------------------:|
|    58 | 0.123125 |                              0.0167696 |               0.0118164  | 0.012254   | 0.0124046  |                        0.762813 |
|    59 | 0.137645 |                              0.0331104 |               0.00632476 | 0.00732735 | 0.00724342 |                        0.637135 |
|    60 | 0.111306 |                              0.0302733 |               0.00864464 | 0.00959911 | 0.00971819 |                        0.641115 |
|    61 | 0.126358 |                              0.0362338 |               0.010209   | 0.0130567  | 0.0136662  |                        0.667252 |
|    62 | 0.124888 |                              0.0294357 |               0.00545652 | 0.0063143  | 0.00667548 |                        0.626792 |
|    63 | 0.146049 |                              0.024213  |               0.00851801 | 0.00892886 | 0.00917167 |                        0.672764 |
|    65 | 0.162919 |                              0.0114057 |               0.0034205  | 0.00333753 | 0.00334993 |                        0.674747 |

## 6. ML-minus-Traditional Deltas

The table below subtracts `traditional_precedence_ladder` from each method. Negative Brier and primary-score deltas are improvements; positive precision/recall/support deltas are improvements; negative timing, charge-width, and energy-proxy deltas indicate cleaner accepted support.

| method                               |   accepted_support_fraction |     brier |   charge_bias_delta |   charge_res68_delta |   energy_proxy_degradation_delta |   harmful_conflict_precision |   harmful_conflict_recall |   pid_weak_label_drift |   primary_score |   timing_tail_delta |
|:-------------------------------------|----------------------------:|----------:|--------------------:|---------------------:|---------------------------------:|-----------------------------:|--------------------------:|-----------------------:|----------------:|--------------------:|
| 1d_cnn                               |                   -0.285661 | -0.422838 |          -0.0280515 |           -0.235913  |                      0.000889317 |                 -0.120444    |                  0.565763 |              0.0635868 |       -0.536838 |          -0.0449922 |
| conflict_prior_residual_cnn_new_arch |                   -0.333744 | -0.531534 |          -0.365966  |           -0.133125  |                      0           |                 -0.0194088   |                  0.768716 |              0.100405  |       -0.643693 |          -0.0449922 |
| gradient_boosted_trees               |                   -0.324391 | -0.548952 |          -0.423116  |           -0.0957584 |                      0.00645831  |                 -0.000397532 |                  0.766016 |              0.0941219 |       -0.661425 |          -0.0449922 |
| mlp                                  |                   -0.323695 | -0.547981 |          -0.429026  |           -0.0899557 |                      0.00989698  |                 -0.000208574 |                  0.764561 |              0.0939139 |       -0.660465 |          -0.0449922 |
| ridge                                |                   -0.323959 | -0.547806 |          -0.428677  |           -0.0915276 |                      0.00941611  |                 -0.000625332 |                  0.764769 |              0.0941744 |       -0.660276 |          -0.0449922 |
| traditional_precedence_ladder        |                    0        |  0        |           0         |            0         |                      0           |                  0           |                  0        |              0         |        0        |           0         |

## 7. Knockout and Sentinel Tests

Action-knockout policies test whether arbitration itself matters. `no_arbitration` accepts every non-veto/non-severe pulse, while `reject_all_conflicts` is the conservative upper bound on conflict rejection.

| policy                        |   conflict_rate |   harmful_conflict_precision |   harmful_conflict_recall |   accepted_support_fraction |   timing_tail_delta |   charge_res68_delta |   energy_proxy_degradation_delta |
|:------------------------------|----------------:|-----------------------------:|--------------------------:|----------------------------:|--------------------:|---------------------:|---------------------------------:|
| no_arbitration                |        0.590738 |                     0        |                  0        |                  0.546908   |          -0.063026  |            -0.764884 |                        -0.203538 |
| reject_all_conflicts          |        0.590738 |                     0.716491 |                  1        |                  0.00854544 |          -0.106422  |            -1.57375  |                        -0.286764 |
| traditional_precedence_ladder |        0.590738 |                     1        |                  0.231284 |                  0.501391   |          -0.0614301 |            -0.873575 |                        -0.286764 |

Consumer-knockout removes one consumer from the conflict calculation. The largest negative `delta_harmful_conflict_rate` values identify consumers most responsible for harmful disagreements.

| knockout   |      n |   conflict_rate |   harmful_conflict_rate |   delta_conflict_rate |   delta_harmful_conflict_rate |
|:-----------|-------:|----------------:|------------------------:|----------------------:|------------------------------:|
| dropout    | 125096 |        0.583168 |                0.415689 |          -0.00757019  |                  -0.00757019  |
| timing     | 125096 |        0.590187 |                0.422707 |          -0.000551576 |                  -0.000551576 |
| baseline   | 125096 |        0.590379 |                0.422899 |          -0.000359724 |                  -0.000359724 |
| none       | 125096 |        0.590738 |                0.423259 |           0           |                   0           |
| charge     | 125096 |        0.590738 |                0.423259 |           0           |                   0           |
| saturation | 125096 |        0.584223 |                0.423259 |          -0.006515    |                   0           |
| pileup     | 125096 |        0.503781 |                0.423259 |          -0.0869572   |                   0           |
| pid        | 125096 |        0.590738 |                0.423259 |           0           |                   0           |
| energy     | 125096 |        0.590738 |                0.423259 |           0           |                   0           |

Leakage and run-family sentinels:
| check                                          | value                                                                                                                                                                                                                                                                                                                                                                                                        | pass   |
|:-----------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------|
| heldout_runs_excluded_from_training            | 58,59,60,61,62,63,65                                                                                                                                                                                                                                                                                                                                                                                         | True   |
| model_features_exclude_event_ids               | log_amp,amplitude_adc,area_over_amp,peak_sample,width035_samples,width050_samples,plateau_count,secondary_peak_rel,late_fraction,seed_baseline_adc,pre_rms_adc,pre_max_exc_adc,adaptive_lowering_adc,event_timing_abs_resid_ns_filled,active_atom_count_no_charge,stave,amplitude_atom,shape_atom,timing_atom,saturation_atom,pileup_atom,baseline_atom,dropout_anomaly_atom,q_template_atom,covariance_atom | True   |
| target_harmful_conflict_excluded_from_features | harmful_conflict                                                                                                                                                                                                                                                                                                                                                                                             | True   |
| charge_transfer_atom_excluded_from_features    | charge_transfer_atom                                                                                                                                                                                                                                                                                                                                                                                         | True   |
| evaluation_runs_present                        | 7                                                                                                                                                                                                                                                                                                                                                                                                            | True   |
| training_conflict_rows_after_cap               | 30000                                                                                                                                                                                                                                                                                                                                                                                                        | True   |
| evaluation_conflict_rows                       | 73899                                                                                                                                                                                                                                                                                                                                                                                                        | True   |
| shuffled_target_gbt_auc_below_0p70             | 0.5066559364692804                                                                                                                                                                                                                                                                                                                                                                                           | True   |

## 8. Systematics and Caveats

- **Operational labels:** `H_i` is a downstream-risk proxy, not absolute PID, energy, or pile-up truth.
- **Action-rule circularity:** the traditional ladder intentionally uses frozen P12c action and harm atoms; learned models are restricted to predictor atoms to avoid using `charge_transfer_atom` or the target directly.
- **Run dependence:** every uncertainty interval resamples complete held-out runs, but Sample-II has only seven analysis runs; small CIs would not imply independent pulse statistics.
- **Conflict definition:** action disagreement can be benign when consumers have different support needs. P12d therefore reports accepted support, PID drift, energy-proxy degradation, and charge/timing deltas rather than only classification AUC.
- **Neural capacity:** CNNs are small tabular-sequence comparators trained for three epochs; the result is a policy benchmark, not a final production neural calibrator.
- **Post-hoc selection:** consumers, held-out runs, threshold, primary score, and minimum support/recall constraints are fixed in the config before output tables are written.

## 9. Finding

The winner is `gradient_boosted_trees`. The central result is that consumer disagreements are common enough to need arbitration, but their downstream harm is not equivalent to raw conflict count. A useful policy must reject high-risk conflicts while keeping sufficient accepted support and avoiding PID/energy drift. The full artifact set includes `result.json`, `method_metrics.csv`, `method_by_run.csv`, `ml_minus_traditional_deltas.csv`, `conflict_patterns.csv`, `consumer_knockout.csv`, `action_knockout.csv`, `leakage_checks.csv`, `heldout_conflict_predictions.csv.gz`, `input_sha256.csv`, and `manifest.json`.

Queued follow-up candidate in `result.json`: `P12e frozen arbitration policy downstream consumer trial`. Expected information gain: Freeze the P12d conflict-arbitration winner and test whether accepted pulses improve independent timing, charge, PID, and energy-proxy consumers under run-held-out bootstrap CIs, against deterministic precedence and no-arbitration baselines.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p12d_1781054026_1869_66191fe9_consumer_action_conflict_arbitration.py --config configs/p12d_1781054026_1869_66191fe9_consumer_action_conflict_arbitration.json
```

Runtime: 340.7 s.

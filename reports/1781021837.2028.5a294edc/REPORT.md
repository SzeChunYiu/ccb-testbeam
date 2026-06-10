# P11a: pretrigger baseline spectrum atom table

- **Ticket:** 1781021837.2028.5a294edc
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `138c8721d36655281a8bfdf4f7288f534714e0d0`

## Raw ROOT reproduction first

The S00 B-stack selected-pulse gate is reproduced directly from raw `h101/HRDv`: **640737** pulses with `A > 1000 ADC`.

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

## Traditional atom table

Atoms are frozen per training fold from pretrigger samples 0-3 only: quiet, noisy RMS, sloped, early-asymmetric, adaptive-lowering, and spike. The held-out rows below are averaged over run-heldout folds.

| atom              |      n |   fraction |   baseline_excursion_rate |   dropout_rate |   timing_tail_rate |   charge_bias_tail_rate |   large_pulse_fraction |   charge_residual_delta_vs_quiet |   sat_boundary_charge_residual_delta_vs_quiet |
|:------------------|-------:|-----------:|--------------------------:|---------------:|-------------------:|------------------------:|-----------------------:|---------------------------------:|----------------------------------------------:|
| quiet             | 474988 |   0.7413   |                  0.004545 |        0.01358 |          0.008986  |                 0.07589 |                0.2709  |                           0      |                                        0      |
| early_asym        |  96651 |   0.1508   |                  0.01517  |        0.0216  |          0.004495  |                 0.03326 |                0.4917  |                          -0.5883 |                                        0.1773 |
| adaptive_lowering |  33079 |   0.05161  |                  0.9111   |        0.01969 |          0.007299  |                 0.3673  |                0.07394 |                          -5.99   |                                       -0.4915 |
| spike             |  32116 |   0.0501   |                  0.9423   |        0.02591 |          0.004429  |                 0.409   |                0.08097 |                          -6.825  |                                       -0.4282 |
| sloped            |   2773 |   0.004328 |                  0.01443  |        0.01507 |          0.003478  |                 0.02324 |                0.4378  |                          -0.3846 |                                        0.3698 |
| noisy_rms         |   1130 |   0.001764 |                  0.03021  |        0.0159  |          0.0008889 |                 0.02853 |                0.4309  |                          -0.4219 |                                        0.3176 |

The quiet atom covers 74.1% of held-out selected pulses. Spike/adaptive-lowering atoms are rare but concentrate baseline excursion and modestly enrich dropout/charge-tail proxies; the saturation-boundary charge residual deltas stay small after the amplitude control model.

## ML method

The ML method is a regularized logistic classifier trained only on pretrigger summaries: mean, RMS, slope, max excursion, early asymmetry, and peak-to-peak over samples 0-3. It excludes run, event id, stave, amplitude, area, peak sample, timing, and all post-trigger samples. CIs bootstrap held-out runs.

| target                   | method                    | metric   |     value |    ci_low |    ci_high |
|:-------------------------|:--------------------------|:---------|----------:|----------:|-----------:|
| baseline_excursion       | traditional_atom_logistic | auc      |  0.9741   |  0.9693   |  0.9786    |
| baseline_excursion       | traditional_atom_logistic | ap       |  0.8977   |  0.8833   |  0.9092    |
| baseline_excursion       | traditional_atom_logistic | ece      |  0.05251  |  0.05047  |  0.05548   |
| baseline_excursion       | ml_pretrigger_logistic    | auc      |  0.996    |  0.995    |  0.9968    |
| baseline_excursion       | ml_pretrigger_logistic    | ap       |  0.9776   |  0.9731   |  0.9815    |
| baseline_excursion       | ml_pretrigger_logistic    | ece      |  0.04796  |  0.03945  |  0.05907   |
| baseline_excursion       | ml_minus_traditional      | auc      |  0.0219   |  0.02104  |  0.02286   |
| baseline_excursion       | ml_minus_traditional      | ap       |  0.07993  |  0.07493  |  0.08426   |
| baseline_excursion       | ml_minus_traditional      | ece      | -0.004556 | -0.01393  |  0.006575  |
| charge_bias_tail         | traditional_atom_logistic | auc      |  0.6793   |  0.6369   |  0.7315    |
| charge_bias_tail         | traditional_atom_logistic | ap       |  0.2323   |  0.207    |  0.2626    |
| charge_bias_tail         | traditional_atom_logistic | ece      |  0.3334   |  0.3198   |  0.3455    |
| charge_bias_tail         | ml_pretrigger_logistic    | auc      |  0.7066   |  0.6756   |  0.7376    |
| charge_bias_tail         | ml_pretrigger_logistic    | ap       |  0.452    |  0.411    |  0.4932    |
| charge_bias_tail         | ml_pretrigger_logistic    | ece      |  0.3159   |  0.3008   |  0.3288    |
| charge_bias_tail         | ml_minus_traditional      | auc      |  0.02734  | -0.002808 |  0.05353   |
| charge_bias_tail         | ml_minus_traditional      | ap       |  0.2196   |  0.1741   |  0.2588    |
| charge_bias_tail         | ml_minus_traditional      | ece      | -0.01743  | -0.03464  | -0.004113  |
| dropout_proxy            | traditional_atom_logistic | auc      |  0.5417   |  0.5051   |  0.5832    |
| dropout_proxy            | traditional_atom_logistic | ap       |  0.01966  |  0.01613  |  0.02434   |
| dropout_proxy            | traditional_atom_logistic | ece      |  0.4754   |  0.4724   |  0.4793    |
| dropout_proxy            | ml_pretrigger_logistic    | auc      |  0.5558   |  0.5254   |  0.5904    |
| dropout_proxy            | ml_pretrigger_logistic    | ap       |  0.02628  |  0.02125  |  0.03415   |
| dropout_proxy            | ml_pretrigger_logistic    | ece      |  0.4719   |  0.4678   |  0.4759    |
| dropout_proxy            | ml_minus_traditional      | auc      |  0.01409  | -0.02196  |  0.05062   |
| dropout_proxy            | ml_minus_traditional      | ap       |  0.006623 |  0.001783 |  0.01374   |
| dropout_proxy            | ml_minus_traditional      | ece      | -0.003496 | -0.007229 |  0.0008133 |
| saturation_boundary_bias | traditional_atom_logistic | auc      |  0.5773   |  0.5431   |  0.6125    |
| saturation_boundary_bias | traditional_atom_logistic | ap       |  0.01119  |  0.008774 |  0.0145    |
| saturation_boundary_bias | traditional_atom_logistic | ece      |  0.4642   |  0.4577   |  0.4705    |
| saturation_boundary_bias | ml_pretrigger_logistic    | auc      |  0.6174   |  0.5791   |  0.6589    |
| saturation_boundary_bias | ml_pretrigger_logistic    | ap       |  0.01712  |  0.01383  |  0.02188   |
| saturation_boundary_bias | ml_pretrigger_logistic    | ece      |  0.4567   |  0.4479   |  0.4631    |
| saturation_boundary_bias | ml_minus_traditional      | auc      |  0.0401   |  0.003624 |  0.07456   |
| saturation_boundary_bias | ml_minus_traditional      | ap       |  0.005923 |  0.003152 |  0.01029   |
| saturation_boundary_bias | ml_minus_traditional      | ece      | -0.007509 | -0.01484  |  0.0001293 |
| timing_tail              | traditional_atom_logistic | auc      |  0.5187   |  0.4457   |  0.5967    |
| timing_tail              | traditional_atom_logistic | ap       |  0.008302 |  0.004961 |  0.01485   |
| timing_tail              | traditional_atom_logistic | ece      |  0.4809   |  0.4748   |  0.4863    |
| timing_tail              | ml_pretrigger_logistic    | auc      |  0.7845   |  0.7531   |  0.8123    |
| timing_tail              | ml_pretrigger_logistic    | ap       |  0.0315   |  0.02435  |  0.03892   |
| timing_tail              | ml_pretrigger_logistic    | ece      |  0.4424   |  0.4351   |  0.4485    |
| timing_tail              | ml_minus_traditional      | auc      |  0.2658   |  0.2383   |  0.2979    |
| timing_tail              | ml_minus_traditional      | ap       |  0.02319  |  0.01513  |  0.02984   |
| timing_tail              | ml_minus_traditional      | ece      | -0.03849  | -0.04632  | -0.0318    |

## Leakage checks

Every target also gets shuffled-label, run-only, and post-trigger-oracle diagnostics. A good pretrigger result would be suspect if shuffled labels or run-only features also score high.

|   fold | target                   | heldout_runs         |   ml_auc |   shuffled_label_auc |   run_only_auc |   posttrigger_oracle_auc |
|-------:|:-------------------------|:---------------------|---------:|---------------------:|---------------:|-------------------------:|
|      1 | baseline_excursion       | 33,42,45,48,49,52    |   0.998  |               0.4472 |            0.5 |                   0.9361 |
|      1 | dropout_proxy            | 33,42,45,48,49,52    |   0.6    |               0.4631 |            0.5 |                   0.9621 |
|      1 | timing_tail              | 33,42,45,48,49,52    |   0.8295 |               0.3286 |            0.5 |                   0.836  |
|      1 | charge_bias_tail         | 33,42,45,48,49,52    |   0.7721 |               0.3961 |            0.5 |                   0.9681 |
|      1 | saturation_boundary_bias | 33,42,45,48,49,52    |   0.6092 |               0.6253 |            0.5 |                   0.9854 |
|      2 | baseline_excursion       | 35,37,39,44,56,58,63 |   0.9953 |               0.7578 |            0.5 |                   0.9029 |
|      2 | dropout_proxy            | 35,37,39,44,56,58,63 |   0.5932 |               0.4377 |            0.5 |                   0.9613 |
|      2 | timing_tail              | 35,37,39,44,56,58,63 |   0.8011 |               0.7399 |            0.5 |                   0.7966 |
|      2 | charge_bias_tail         | 35,37,39,44,56,58,63 |   0.6788 |               0.5415 |            0.5 |                   0.9431 |
|      2 | saturation_boundary_bias | 35,37,39,44,56,58,63 |   0.6186 |               0.5723 |            0.5 |                   0.9857 |
|      3 | baseline_excursion       | 31,50,51,57,60,61    |   0.9942 |               0.3871 |            0.5 |                   0.9191 |
|      3 | dropout_proxy            | 31,50,51,57,60,61    |   0.5461 |               0.4664 |            0.5 |                   0.9535 |
|      3 | timing_tail              | 31,50,51,57,60,61    |   0.7478 |               0.7047 |            0.5 |                   0.8221 |
|      3 | charge_bias_tail         | 31,50,51,57,60,61    |   0.7003 |               0.5795 |            0.5 |                   0.9519 |
|      3 | saturation_boundary_bias | 31,50,51,57,60,61    |   0.6825 |               0.5577 |            0.5 |                   0.9831 |
|      4 | baseline_excursion       | 32,34,36,41,47,59,64 |   0.9961 |               0.7533 |            0.5 |                   0.8943 |
|      4 | dropout_proxy            | 32,34,36,41,47,59,64 |   0.5899 |               0.4473 |            0.5 |                   0.9684 |
|      4 | timing_tail              | 32,34,36,41,47,59,64 |   0.7691 |               0.2332 |            0.5 |                   0.8409 |
|      4 | charge_bias_tail         | 32,34,36,41,47,59,64 |   0.7045 |               0.5087 |            0.5 |                   0.942  |
|      4 | saturation_boundary_bias | 32,34,36,41,47,59,64 |   0.6726 |               0.3767 |            0.5 |                   0.9868 |
|      5 | baseline_excursion       | 40,46,53,54,55,62,65 |   0.9963 |               0.2208 |            0.5 |                   0.9101 |
|      5 | dropout_proxy            | 40,46,53,54,55,62,65 |   0.5582 |               0.546  |            0.5 |                   0.9635 |
|      5 | timing_tail              | 40,46,53,54,55,62,65 |   0.7692 |               0.6676 |            0.5 |                   0.8456 |
|      5 | charge_bias_tail         | 40,46,53,54,55,62,65 |   0.6945 |               0.29   |            0.5 |                   0.9607 |
|      5 | saturation_boundary_bias | 40,46,53,54,55,62,65 |   0.5763 |               0.4454 |            0.5 |                   0.9858 |

The run-only diagnostic is 0.5 in every fold, so the models are not simply learning held-out run identities. However, shuffled-label AUC exceeds 0.65 for some fold/target combinations, especially baseline and timing, so high ML scores are treated as nuisance flags rather than discovery-grade predictive claims.

## Conclusion

Pretrigger structure is real but limited: the best ML-minus-traditional AUC delta is 0.266 for `timing_tail`. The shuffled-label audit flags instability for `baseline_excursion`, `timing_tail`. The atom table is therefore useful as a nuisance/control table, not as a replacement for downstream waveform quality cuts.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p11a_1781021837_2028_5a294edc_pretrigger_atoms.py --config configs/p11a_1781021837_2028_5a294edc_pretrigger_atoms.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `raw_count_match.csv`, `pretrigger_atom_summary.csv`, `heldout_method_metrics.csv`, `leakage_checks.csv`, and `heldout_predictions.csv`.

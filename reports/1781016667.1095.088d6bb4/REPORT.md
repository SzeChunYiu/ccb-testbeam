# P01d: time-local sample-epoch waveform probe

**Ticket:** 1781016667.1095.088d6bb4

## Reproduction first
The analysis rescanned raw B-stack ROOT files from `data/root/root` before any modelling.
Using the P01/S00 gate (B2/B4/B6/B8, baseline median samples 0-3, `A > 1000` ADC), it reproduced
**640,737** selected pulse records versus the ticket target
**640,737**.

## Local targets
The broad P01b-downstream Sample I vs II target was replaced by local labels: adjacent run-pair
side, a within-Sample-I calibration/analysis transition, and a within-Sample-II early/late split.
Each representation and probe was fit without held-out runs. CIs are 95% stratified run-block
bootstrap intervals over held-out runs.

## Main held-out probes
| task                      | method                   | value | ci_low | ci_high | roc_auc | average_precision | train_rows | heldout_rows |
| ------------------------- | ------------------------ | ----- | ------ | ------- | ------- | ----------------- | ---------- | ------------ |
| adjacent_run_pair_side    | traditional hand-shape   | 0.485 | 0.413  | 0.575   | 0.483   | 0.445             | 69186      | 22160        |
| adjacent_run_pair_side    | traditional PCA-6        | 0.486 | 0.408  | 0.571   | 0.481   | 0.444             | 69186      | 22160        |
| adjacent_run_pair_side    | ML masked-denoising AE-6 | 0.495 | 0.434  | 0.567   | 0.480   | 0.445             | 69186      | 22160        |
| sample_i_local_transition | traditional hand-shape   | 0.555 | 0.489  | 0.615   | 0.567   | 0.555             | 42802      | 15580        |
| sample_i_local_transition | traditional PCA-6        | 0.561 | 0.512  | 0.619   | 0.587   | 0.573             | 42802      | 15580        |
| sample_i_local_transition | ML masked-denoising AE-6 | 0.567 | 0.488  | 0.631   | 0.585   | 0.565             | 42802      | 15580        |
| sample_ii_adjacent_era    | traditional hand-shape   | 0.489 | 0.464  | 0.508   | 0.473   | 0.358             | 17944      | 17790        |
| sample_ii_adjacent_era    | traditional PCA-6        | 0.460 | 0.426  | 0.487   | 0.440   | 0.343             | 17944      | 17790        |
| sample_ii_adjacent_era    | ML masked-denoising AE-6 | 0.503 | 0.494  | 0.513   | 0.534   | 0.388             | 17944      | 17790        |

## Proxy and leakage checks
| task                      | method                                    | value | ci_low | ci_high | roc_auc | average_precision |
| ------------------------- | ----------------------------------------- | ----- | ------ | ------- | ------- | ----------------- |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 0.487 | 0.442  | 0.526   | 0.482   | 0.447             |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 0.487 | 0.453  | 0.522   | 0.481   | 0.448             |
| adjacent_run_pair_side    | leakage check: AE label shuffle           | 0.475 | 0.405  | 0.556   | 0.480   | 0.443             |
| sample_i_local_transition | proxy: amplitude+multiplicity             | 0.531 | 0.503  | 0.588   | 0.563   | 0.568             |
| sample_i_local_transition | leakage check: topology/stave composition | 0.517 | 0.483  | 0.568   | 0.561   | 0.554             |
| sample_i_local_transition | leakage check: AE label shuffle           | 0.570 | 0.484  | 0.630   | 0.563   | 0.521             |
| sample_ii_adjacent_era    | proxy: amplitude+multiplicity             | 0.378 | 0.318  | 0.420   | 0.367   | 0.327             |
| sample_ii_adjacent_era    | leakage check: topology/stave composition | 0.374 | 0.317  | 0.414   | 0.381   | 0.326             |
| sample_ii_adjacent_era    | leakage check: AE label shuffle           | 0.503 | 0.496  | 0.510   | 0.539   | 0.405             |

## Leakage interpretation
| task                      | best_main_method         | best_main_value | best_proxy_value | label_shuffle_value | interpretation                                        |
| ------------------------- | ------------------------ | --------------- | ---------------- | ------------------- | ----------------------------------------------------- |
| adjacent_run_pair_side    | ML masked-denoising AE-6 | 0.495           | 0.487            | 0.475               | unstable: label shuffle matches or exceeds main score |
| sample_i_local_transition | ML masked-denoising AE-6 | 0.567           | 0.531            | 0.570               | unstable: label shuffle matches or exceeds main score |
| sample_ii_adjacent_era    | ML masked-denoising AE-6 | 0.503           | 0.378            | 0.503               | unstable: label shuffle matches or exceeds main score |

The proxy rows use amplitude, multiplicity, topology-mask, and stave-composition features only.
The leakage hunt flags `adjacent_run_pair_side` (unstable: label shuffle matches or exceeds main score), `sample_i_local_transition` (unstable: label shuffle matches or exceeds main score), `sample_ii_adjacent_era` (unstable: label shuffle matches or exceeds main score). The strongest local waveform score is 0.567 on
`sample_i_local_transition` from `ML masked-denoising AE-6`, which is well below the earlier
broad sample-epoch P01b-downstream PCA score of about 0.65.

## Held-out run breakdown
| task                      | method                                    | run | class_name            | heldout_rows | run_class_recall | positive_rate | mean_score |
| ------------------------- | ----------------------------------------- | --- | --------------------- | ------------ | ---------------- | ------------- | ---------- |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 35  | earlier_run_in_pair   | 2138         | 0.573            | 0.427         | 0.498      |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 36  | later_run_in_pair     | 2044         | 0.480            | 0.480         | 0.499      |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 42  | earlier_run_in_pair   | 2635         | 0.479            | 0.521         | 0.501      |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 44  | later_run_in_pair     | 1654         | 0.486            | 0.486         | 0.498      |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 57  | earlier_run_in_pair   | 2559         | 0.560            | 0.440         | 0.498      |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 58  | later_run_in_pair     | 2490         | 0.412            | 0.412         | 0.496      |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 63  | earlier_run_in_pair   | 4606         | 0.713            | 0.287         | 0.495      |
| adjacent_run_pair_side    | ML masked-denoising AE-6                  | 64  | later_run_in_pair     | 4034         | 0.283            | 0.283         | 0.494      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 35  | earlier_run_in_pair   | 2138         | 0.570            | 0.430         | 0.494      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 36  | later_run_in_pair     | 2044         | 0.495            | 0.495         | 0.497      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 42  | earlier_run_in_pair   | 2635         | 0.457            | 0.543         | 0.498      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 44  | later_run_in_pair     | 1654         | 0.470            | 0.470         | 0.495      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 57  | earlier_run_in_pair   | 2559         | 0.564            | 0.436         | 0.494      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 58  | later_run_in_pair     | 2490         | 0.461            | 0.461         | 0.495      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 63  | earlier_run_in_pair   | 4606         | 0.563            | 0.437         | 0.495      |
| adjacent_run_pair_side    | leakage check: topology/stave composition | 64  | later_run_in_pair     | 4034         | 0.367            | 0.367         | 0.493      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 35  | earlier_run_in_pair   | 2138         | 0.559            | 0.441         | 0.495      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 36  | later_run_in_pair     | 2044         | 0.487            | 0.487         | 0.498      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 42  | earlier_run_in_pair   | 2635         | 0.463            | 0.537         | 0.499      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 44  | later_run_in_pair     | 1654         | 0.473            | 0.473         | 0.496      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 57  | earlier_run_in_pair   | 2559         | 0.564            | 0.436         | 0.495      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 58  | later_run_in_pair     | 2490         | 0.458            | 0.458         | 0.496      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 63  | earlier_run_in_pair   | 4606         | 0.589            | 0.411         | 0.495      |
| adjacent_run_pair_side    | proxy: amplitude+multiplicity             | 64  | later_run_in_pair     | 4034         | 0.348            | 0.348         | 0.493      |
| adjacent_run_pair_side    | traditional PCA-6                         | 35  | earlier_run_in_pair   | 2138         | 0.456            | 0.544         | 0.501      |
| adjacent_run_pair_side    | traditional PCA-6                         | 36  | later_run_in_pair     | 2044         | 0.563            | 0.563         | 0.501      |
| adjacent_run_pair_side    | traditional PCA-6                         | 42  | earlier_run_in_pair   | 2635         | 0.433            | 0.567         | 0.501      |
| adjacent_run_pair_side    | traditional PCA-6                         | 44  | later_run_in_pair     | 1654         | 0.541            | 0.541         | 0.501      |
| adjacent_run_pair_side    | traditional PCA-6                         | 57  | earlier_run_in_pair   | 2559         | 0.501            | 0.499         | 0.500      |
| adjacent_run_pair_side    | traditional PCA-6                         | 58  | later_run_in_pair     | 2490         | 0.390            | 0.390         | 0.496      |
| adjacent_run_pair_side    | traditional PCA-6                         | 63  | earlier_run_in_pair   | 4606         | 0.704            | 0.296         | 0.492      |
| adjacent_run_pair_side    | traditional PCA-6                         | 64  | later_run_in_pair     | 4034         | 0.306            | 0.306         | 0.493      |
| adjacent_run_pair_side    | traditional hand-shape                    | 35  | earlier_run_in_pair   | 2138         | 0.529            | 0.471         | 0.500      |
| adjacent_run_pair_side    | traditional hand-shape                    | 36  | later_run_in_pair     | 2044         | 0.514            | 0.514         | 0.501      |
| adjacent_run_pair_side    | traditional hand-shape                    | 42  | earlier_run_in_pair   | 2635         | 0.487            | 0.513         | 0.501      |
| adjacent_run_pair_side    | traditional hand-shape                    | 44  | later_run_in_pair     | 1654         | 0.508            | 0.508         | 0.501      |
| adjacent_run_pair_side    | traditional hand-shape                    | 57  | earlier_run_in_pair   | 2559         | 0.553            | 0.447         | 0.499      |
| adjacent_run_pair_side    | traditional hand-shape                    | 58  | later_run_in_pair     | 2490         | 0.331            | 0.331         | 0.496      |
| adjacent_run_pair_side    | traditional hand-shape                    | 63  | earlier_run_in_pair   | 4606         | 0.718            | 0.282         | 0.493      |
| adjacent_run_pair_side    | traditional hand-shape                    | 64  | later_run_in_pair     | 4034         | 0.268            | 0.268         | 0.493      |
| sample_i_local_transition | ML masked-denoising AE-6                  | 40  | sample_i_calib_era    | 2633         | 0.668            | 0.332         | 0.494      |
| sample_i_local_transition | ML masked-denoising AE-6                  | 41  | sample_i_calib_era    | 2683         | 0.641            | 0.359         | 0.495      |
| sample_i_local_transition | ML masked-denoising AE-6                  | 42  | sample_i_calib_era    | 2635         | 0.602            | 0.398         | 0.497      |
| sample_i_local_transition | ML masked-denoising AE-6                  | 55  | sample_i_analysis_era | 2152         | 0.644            | 0.644         | 0.506      |
| sample_i_local_transition | ML masked-denoising AE-6                  | 56  | sample_i_analysis_era | 2918         | 0.545            | 0.545         | 0.503      |
| sample_i_local_transition | ML masked-denoising AE-6                  | 57  | sample_i_analysis_era | 2559         | 0.318            | 0.318         | 0.494      |
| sample_i_local_transition | leakage check: topology/stave composition | 40  | sample_i_calib_era    | 2633         | 0.415            | 0.585         | 0.493      |
| sample_i_local_transition | leakage check: topology/stave composition | 41  | sample_i_calib_era    | 2683         | 0.421            | 0.579         | 0.494      |

## Verdict
Time-local labels are much weaker than the broad Sample I vs II label. The adjacent-run-pair and
Sample II early/late tasks are at chance. The only visible bump is the Sample I local transition,
but its label-shuffle control matches the main waveform score, so it is not a robust pulse-shape
claim. This supports the interpretation that P01b's sample-epoch separability is dominated by
long-range calibration, topology, and detector-domain drift rather than a stable local
pulse-shape label.

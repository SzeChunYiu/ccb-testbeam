# Study report: S03f - Sample-I sparse downstream S03e proxy validation

- **Ticket:** 1781020221.987.29815c7f
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `/home/billy/Desktop/test_beam/data/root/root`
- **Split:** leave-one-run-out over Sample-I analysis runs 44-57; held-out bootstrap resamples runs
- **Config:** `configs/s03f_1781020221_987_29815c7f_sample_i_downstream_proxy.yaml`
- **Monte Carlo:** none

## 1. Raw-ROOT reproduction gate

The selected-pulse count gate and the Sample-II S03e single-stave proxy numbers were rebuilt before the Sample-I study.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

| method                         |   value |   ci_low |   ci_high |   n_pair_residuals |
|:-------------------------------|--------:|---------:|----------:|-------------------:|
| cfd20_base                     | 3.15027 |  3.02462 |   3.27295 |              11460 |
| ml_shuffled_proxy_control      | 4.11888 |  3.77371 |   4.35019 |              11460 |
| ml_single_stave_proxy          | 2.82906 |  2.68709 |   2.96323 |              11460 |
| traditional_amp_isotonic_proxy | 4.44711 |  4.23328 |   4.60373 |              11460 |
| traditional_template_phase     | 2.74141 |  2.68945 |   2.99232 |              11460 |

## 2. Methods

This repeats the S03e no-event-residual single-stave proxy target `t_cfd20_ns - t_template_phase_ns`. The traditional branch uses train-run templates plus the amplitude-isotonic proxy; the ML branch is the same histogram-gradient-boosting proxy regressor over normalized single-stave waveform features. Inter-stave timing is used only for held-out scoring.

For Sample I, events with at least two selected downstream staves are retained and each available pair is scored. This is the sparse-topology extension relative to the strict all-three Sample-II S03e reference.

## 3. Topology limitation

|   runs |   events_ge2_downstream |   events_exactly_2_downstream |   events_all_3_downstream |   fraction_exactly_2 |   pair_residuals |
|-------:|------------------------:|------------------------------:|--------------------------:|---------------------:|-----------------:|
|     14 |                    2130 |                          1480 |                       650 |             0.694836 |             3430 |

|   run |   events_ge2_downstream |   events_2_downstream |   events_3_downstream |   B4_B6 |   B4_B8 |   B6_B8 |
|------:|------------------------:|----------------------:|----------------------:|--------:|--------:|--------:|
|    44 |                      31 |                    24 |                     7 |      27 |       8 |      10 |
|    45 |                     306 |                   212 |                    94 |     291 |      97 |     106 |
|    46 |                       1 |                     0 |                     1 |       1 |       1 |       1 |
|    47 |                      26 |                    17 |                     9 |      24 |      10 |      10 |
|    48 |                     190 |                   132 |                    58 |     182 |      60 |      64 |
|    49 |                     210 |                   154 |                    56 |     203 |      58 |      61 |
|    50 |                     215 |                   155 |                    60 |     208 |      62 |      65 |
|    51 |                     106 |                    72 |                    34 |     101 |      36 |      37 |
|    52 |                      51 |                    29 |                    22 |      49 |      22 |      24 |
|    53 |                     189 |                   130 |                    59 |     180 |      61 |      66 |
|    54 |                     181 |                   131 |                    50 |     175 |      52 |      54 |
|    55 |                     129 |                    85 |                    44 |     127 |      44 |      46 |
|    56 |                     276 |                   184 |                    92 |     268 |      94 |      98 |
|    57 |                     219 |                   155 |                    64 |     212 |      66 |      69 |

## 4. Held-out Sample-I results

|   heldout_run | method                         |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|--------------:|:-------------------------------|-------------:|--------------:|----------------------:|-------------------:|
|            44 | cfd20_base                     |      3.27746 |       5.39582 |             0.111111  |                 45 |
|            44 | ml_shuffled_proxy_control      |      7.98581 |      10.0719  |             0.511111  |                 45 |
|            44 | ml_single_stave_proxy          |      2.50435 |       3.01002 |             0.0444444 |                 45 |
|            44 | traditional_amp_isotonic_proxy |      5.30707 |       8.24683 |             0.311111  |                 45 |
|            44 | traditional_template_phase     |      2.42161 |       3.13641 |             0.0444444 |                 45 |
|            45 | cfd20_base                     |      2.94064 |       6.62095 |             0.0890688 |                494 |
|            45 | ml_shuffled_proxy_control      |      8.86758 |      11.1066  |             0.536437  |                494 |
|            45 | ml_single_stave_proxy          |      2.46365 |       3.11915 |             0.034413  |                494 |
|            45 | traditional_amp_isotonic_proxy |      4.9642  |       8.58693 |             0.313765  |                494 |
|            45 | traditional_template_phase     |      2.60214 |       3.20605 |             0.196356  |                494 |
|            46 | cfd20_base                     |      2.65999 |       3.6276  |             0.333333  |                  3 |
|            46 | ml_shuffled_proxy_control      |      6.17526 |       7.97299 |             0.333333  |                  3 |
|            46 | ml_single_stave_proxy          |      1.27195 |       1.58456 |             0         |                  3 |
|            46 | traditional_amp_isotonic_proxy |      2.17105 |       2.80584 |             0.333333  |                  3 |
|            46 | traditional_template_phase     |      1.42965 |       1.74544 |             0         |                  3 |
|            47 | cfd20_base                     |      2.5728  |       2.52596 |             0.0909091 |                 44 |
|            47 | ml_shuffled_proxy_control      |      8.93874 |       8.55417 |             0.522727  |                 44 |
|            47 | ml_single_stave_proxy          |      1.87119 |       1.89645 |             0.0227273 |                 44 |
|            47 | traditional_amp_isotonic_proxy |      5.59853 |       6.72039 |             0.295455  |                 44 |
|            47 | traditional_template_phase     |      2.14167 |       1.98631 |             0         |                 44 |
|            48 | cfd20_base                     |      2.77081 |       2.64292 |             0.0522876 |                306 |
|            48 | ml_shuffled_proxy_control      |      8.074   |       8.79157 |             0.522876  |                306 |
|            48 | ml_single_stave_proxy          |      2.32364 |       2.17193 |             0.0392157 |                306 |
|            48 | traditional_amp_isotonic_proxy |      4.98655 |       7.51762 |             0.30719   |                306 |
|            48 | traditional_template_phase     |      2.51379 |       2.23886 |             0.176471  |                306 |
|            49 | cfd20_base                     |      2.61914 |       7.52326 |             0.0962733 |                322 |
|            49 | ml_shuffled_proxy_control      |      8.66027 |      11.0449  |             0.596273  |                322 |
|            49 | ml_single_stave_proxy          |      1.83012 |       2.84425 |             0.0186335 |                322 |
|            49 | traditional_amp_isotonic_proxy |      4.39367 |      11.1977  |             0.257764  |                322 |
|            49 | traditional_template_phase     |      1.91305 |       2.81772 |             0.015528  |                322 |
|            50 | cfd20_base                     |      2.77875 |       7.97381 |             0.0716418 |                335 |
|            50 | ml_shuffled_proxy_control      |      8.3781  |      11.8792  |             0.570149  |                335 |
|            50 | ml_single_stave_proxy          |      2.70682 |       3.66891 |             0.0925373 |                335 |
|            50 | traditional_amp_isotonic_proxy |      5.66149 |      10.5228  |             0.274627  |                335 |
|            50 | traditional_template_phase     |      2.68199 |       2.92464 |             0.18209   |                335 |
|            51 | cfd20_base                     |      3.11159 |      15.5945  |             0.155172  |                174 |
|            51 | ml_shuffled_proxy_control      |      8.66184 |      19.6859  |             0.591954  |                174 |
|            51 | ml_single_stave_proxy          |      2.243   |       8.29189 |             0.045977  |                174 |
|            51 | traditional_amp_isotonic_proxy |      4.94953 |      16.445   |             0.293103  |                174 |
|            51 | traditional_template_phase     |      2.11016 |       4.34251 |             0.045977  |                174 |
|            52 | cfd20_base                     |      3.15536 |       9.08894 |             0.0315789 |                 95 |
|            52 | ml_shuffled_proxy_control      |      7.72517 |      12.1661  |             0.526316  |                 95 |
|            52 | ml_single_stave_proxy          |      2.65676 |       3.7954  |             0.0210526 |                 95 |
|            52 | traditional_amp_isotonic_proxy |      5.13454 |      10.4311  |             0.347368  |                 95 |
|            52 | traditional_template_phase     |      2.32118 |       4.64511 |             0.0210526 |                 95 |
|            53 | cfd20_base                     |      2.79905 |       2.85073 |             0.0716612 |                307 |
|            53 | ml_shuffled_proxy_control      |      9.55458 |       8.92575 |             0.570033  |                307 |
|            53 | ml_single_stave_proxy          |      2.59636 |       2.33473 |             0.0651466 |                307 |
|            53 | traditional_amp_isotonic_proxy |      5.06288 |       6.4972  |             0.273616  |                307 |
|            53 | traditional_template_phase     |      2.50382 |       2.36891 |             0.205212  |                307 |
|            54 | cfd20_base                     |      2.59401 |       8.33404 |             0.103203  |                281 |
|            54 | ml_shuffled_proxy_control      |      7.7786  |      11.1606  |             0.519573  |                281 |
|            54 | ml_single_stave_proxy          |      2.69052 |       3.2621  |             0.0960854 |                281 |
|            54 | traditional_amp_isotonic_proxy |      4.8968  |      10.4537  |             0.263345  |                281 |
|            54 | traditional_template_phase     |      2.76049 |       3.2426  |             0.181495  |                281 |
|            55 | cfd20_base                     |      3.06053 |       4.95249 |             0.0737327 |                217 |
|            55 | ml_shuffled_proxy_control      |      7.52917 |       8.9974  |             0.483871  |                217 |
|            55 | ml_single_stave_proxy          |      2.68744 |       3.28588 |             0.0645161 |                217 |
|            55 | traditional_amp_isotonic_proxy |      5.17732 |       6.80299 |             0.294931  |                217 |
|            55 | traditional_template_phase     |      2.66139 |       3.35635 |             0.202765  |                217 |
|            56 | cfd20_base                     |      2.77743 |       8.26238 |             0.0782609 |                460 |
|            56 | ml_shuffled_proxy_control      |      9.18146 |      11.9917  |             0.580435  |                460 |
|            56 | ml_single_stave_proxy          |      1.98171 |       4.11524 |             0.0347826 |                460 |
|            56 | traditional_amp_isotonic_proxy |      4.55655 |       8.89477 |             0.273913  |                460 |
|            56 | traditional_template_phase     |      1.95986 |       3.28958 |             0.0282609 |                460 |
|            57 | cfd20_base                     |      2.66173 |       3.10024 |             0.0662824 |                347 |
|            57 | ml_shuffled_proxy_control      |      7.75787 |       8.66489 |             0.553314  |                347 |
|            57 | ml_single_stave_proxy          |      2.06344 |       1.97921 |             0.0144092 |                347 |
|            57 | traditional_amp_isotonic_proxy |      4.76195 |       6.6668  |             0.262248  |                347 |
|            57 | traditional_template_phase     |      2.18869 |       2.11242 |             0.0144092 |                347 |

Pooled CIs resample held-out runs.

| method                         |   value |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:-------------------------------|--------:|---------:|----------:|--------------:|----------------------:|-------------------:|
| cfd20_base                     | 2.83781 |  2.75301 |   2.92443 |       7.21451 |             0.0816327 |               3430 |
| ml_shuffled_proxy_control      | 8.44259 |  8.16803 |   8.73326 |      11.245   |             0.559767  |               3430 |
| ml_single_stave_proxy          | 2.51357 |  2.21378 |   2.64996 |       3.61396 |             0.0379009 |               3430 |
| traditional_amp_isotonic_proxy | 5.14797 |  4.86371 |   5.42593 |       9.38721 |             0.302915  |               3430 |
| traditional_template_phase     | 2.66199 |  2.18719 |   2.77098 |       3.11583 |             0.0670554 |               3430 |

## 5. Comparison with Sample-II S03e

| method                         |   sample_i_sparse_sigma68_ns |   sample_i_ci_low |   sample_i_ci_high |   sample_ii_s03e_sigma68_ns |   sample_ii_ci_low |   sample_ii_ci_high |   delta_sample_i_minus_sample_ii_ns |
|:-------------------------------|-----------------------------:|------------------:|-------------------:|----------------------------:|-------------------:|--------------------:|------------------------------------:|
| cfd20_base                     |                      2.83781 |           2.75301 |            2.92443 |                     3.15027 |            3.02462 |             3.27295 |                          -0.312458  |
| ml_shuffled_proxy_control      |                      8.44259 |           8.16803 |            8.73326 |                     4.11888 |            3.77371 |             4.35019 |                           4.32371   |
| ml_single_stave_proxy          |                      2.51357 |           2.21378 |            2.64996 |                     2.82906 |            2.68709 |             2.96323 |                          -0.315487  |
| traditional_amp_isotonic_proxy |                      5.14797 |           4.86371 |            5.42593 |                     4.44711 |            4.23328 |             4.60373 |                           0.700862  |
| traditional_template_phase     |                      2.66199 |           2.18719 |            2.77098 |                     2.74141 |            2.68945 |             2.99232 |                          -0.0794238 |

## 6. Leakage checks

|   heldout_run | model    | split   |   rmse_ns |   mae_ns |   n_pulses |
|--------------:|:---------|:--------|----------:|---------:|-----------:|
|            44 | ml_proxy | train   |  0.67875  | 0.352671 |       4841 |
|            44 | ml_proxy | heldout |  0.629269 | 0.396759 |         69 |
|            45 | ml_proxy | train   |  0.725188 | 0.38313  |       4204 |
|            45 | ml_proxy | heldout |  0.661349 | 0.425332 |        706 |
|            46 | ml_proxy | train   |  0.646515 | 0.359803 |       4907 |
|            46 | ml_proxy | heldout |  0.377302 | 0.310566 |          3 |
|            47 | ml_proxy | train   |  0.647533 | 0.351259 |       4849 |
|            47 | ml_proxy | heldout |  0.487374 | 0.390054 |         61 |
|            48 | ml_proxy | train   |  0.713732 | 0.392471 |       4472 |
|            48 | ml_proxy | heldout |  0.592151 | 0.427776 |        438 |
|            49 | ml_proxy | train   |  0.720397 | 0.386271 |       4434 |
|            49 | ml_proxy | heldout |  0.604394 | 0.442745 |        476 |
|            50 | ml_proxy | train   |  0.692392 | 0.391395 |       4420 |
|            50 | ml_proxy | heldout |  1.7497   | 0.550633 |        490 |
|            51 | ml_proxy | train   |  0.730692 | 0.330794 |       4664 |
|            51 | ml_proxy | heldout |  4.73057  | 0.949442 |        246 |
|            52 | ml_proxy | train   |  0.663334 | 0.369354 |       4786 |
|            52 | ml_proxy | heldout |  2.91957  | 0.724439 |        124 |
|            53 | ml_proxy | train   |  0.72165  | 0.384819 |       4473 |
|            53 | ml_proxy | heldout |  0.681921 | 0.464869 |        437 |
|            54 | ml_proxy | train   |  0.716304 | 0.383453 |       4498 |
|            54 | ml_proxy | heldout |  0.724068 | 0.48584  |        412 |
|            55 | ml_proxy | train   |  0.702495 | 0.376893 |       4608 |
|            55 | ml_proxy | heldout |  0.700942 | 0.484723 |        302 |
|            56 | ml_proxy | train   |  0.813173 | 0.322246 |       4266 |
|            56 | ml_proxy | heldout |  2.50897  | 0.594855 |        644 |
|            57 | ml_proxy | train   |  0.689608 | 0.35909  |       4408 |
|            57 | ml_proxy | heldout |  0.528863 | 0.40309  |        502 |

| check                                          |   min |   median |   max |
|:-----------------------------------------------|------:|---------:|------:|
| features_include_run_event_or_other_stave_time |     0 |        0 |     0 |
| fit_targets_include_event_residuals            |     0 |        0 |     0 |
| n_single_stave_features                        |    36 |       36 |    36 |
| train_heldout_event_id_overlap                 |     0 |        0 |     0 |
| train_heldout_run_overlap                      |     0 |        0 |     0 |

The shuffled-target ML control gives `8.443 ns`, so it does not explain the ML proxy result. Run/event overlap checks are zero and the feature audit excludes run id, event id, event order, and other-stave timing.

## 7. Verdict

Sample-I sparse CFD20 is `2.838 ns` with CI `[2.753, 2.924] ns`.
The strong traditional train-template phase method is `2.662 ns` with CI `[2.187, 2.771] ns`.
The ML single-stave proxy is `2.514 ns` with CI `[2.214, 2.650] ns`.
Conclusion: `sample_i_sparse_proxy_supported_with_topology_caveat`.

## 8. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03f_1781020221_987_29815c7f_sample_i_downstream_proxy.py --config configs/s03f_1781020221_987_29815c7f_sample_i_downstream_proxy.yaml
```

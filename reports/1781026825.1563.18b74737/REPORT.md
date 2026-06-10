# S14c: reduce P04b charge-proxy term for range-energy preflight

- **Ticket:** `1781026825.1563.18b74737`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.
- **Split:** leave-one-run-out by run on Sample II runs 58, 59, 60, 61, 62, 63, and 65; CIs are held-out run-block bootstraps.

## Raw reproduction first

P04b external reproduction from raw ROOT gives `external_ml_hgb` res68 `0.213174465233` vs expected `0.213174465233` (delta `0`).

## Topology support

|   run |   B4 |   B4B6 |   B4B6B8 |   B6 |   B6B8 |   B8 |   total_listed |
|------:|-----:|-------:|---------:|-----:|-------:|-----:|---------------:|
|    58 |  355 |    125 |       72 |   14 |      2 |   11 |            579 |
|    59 | 2261 |   1360 |      749 |   74 |     41 |   28 |           4513 |
|    60 | 1934 |   1194 |      802 |   33 |     18 |    5 |           3986 |
|    61 | 2000 |   1364 |      925 |   33 |     21 |   14 |           4357 |
|    62 | 1955 |   1325 |      798 |   30 |     24 |   12 |           4144 |
|    63 | 1488 |    663 |      365 |   41 |     13 |   15 |           2585 |
|    65 |  526 |    178 |       63 |   20 |      7 |    5 |            799 |

## Best charge-proxy rows

| target   | gate            | method            |    n |   bias_median_frac |   res68_abs_frac | res68_ci95                   |   within_10pct |   within_25pct |
|:---------|:----------------|:------------------|-----:|-------------------:|-----------------:|:-----------------------------|---------------:|---------------:|
| B4B6     | all_three       | ml_hgb            | 3774 |        -0.00407641 |         0.201152 | [0.1909403978, 0.2237773529] |       0.379173 |       0.768945 |
| B4       | b4b6_no_b8      | ml_hgb            | 6209 |        -0.0171704  |         0.205217 | [0.1903818249, 0.2294649147] |       0.384764 |       0.767434 |
| B4B6B8   | all_three       | ml_hgb            | 3774 |        -0.0169869  |         0.214429 | [0.2035582317, 0.226763264]  |       0.350556 |       0.759936 |
| B4B6B8   | target_hit_only | ml_hgb            | 3774 |        -0.0169869  |         0.214429 | [0.2030848036, 0.2284964938] |       0.350556 |       0.759936 |
| B4B6B8   | b8_present      | ml_hgb            | 3774 |        -0.0169869  |         0.214429 | [0.203189603, 0.226558382]   |       0.350556 |       0.759936 |
| B4       | all_three       | ml_hgb            | 3774 |        -0.00829879 |         0.220052 | [0.2084049647, 0.2376359484] |       0.36089  |       0.738739 |
| B4B6B8   | b8_present      | traditional_ridge | 3774 |        -0.0209566  |         0.228177 | [0.2116874891, 0.2448210559] |       0.32035  |       0.727875 |
| B4B6B8   | target_hit_only | traditional_ridge | 3774 |        -0.0209566  |         0.228177 | [0.2120177773, 0.2443602826] |       0.32035  |       0.727875 |
| B4B6B8   | all_three       | traditional_ridge | 3774 |        -0.0209566  |         0.228177 | [0.2128525631, 0.2443102816] |       0.32035  |       0.727875 |
| B4B6     | b4b6_no_b8      | ml_hgb            | 6209 |        -0.0303138  |         0.230728 | [0.2209495372, 0.2457410264] |       0.319375 |       0.719923 |
| B4B6     | all_three       | traditional_ridge | 3774 |        -0.015825   |         0.231141 | [0.2147949694, 0.2685779694] |       0.344727 |       0.711182 |
| B4       | b4b6_no_b8      | traditional_ridge | 6209 |        -0.0291057  |         0.232099 | [0.2133838711, 0.2673917051] |       0.328877 |       0.71493  |

## Best charge-propagated energy rows

| target   | gate            | charge_method     | s14b_energy_method   |   n_charge_rows |   charge_res68_abs_frac |   charge_propagated_energy_res68 |   combined_energy_proxy_res68 | combined_energy_proxy_res68_ci95           | acceptable_for_s14_preflight   |
|:---------|:----------------|:------------------|:---------------------|----------------:|------------------------:|---------------------------------:|------------------------------:|:-------------------------------------------|:-------------------------------|
| B4B6     | all_three       | ml_hgb            | ml_monotonic_hgb     |            3774 |                0.201152 |                         0.176303 |                      0.178068 | [0.16921163155567812, 0.19772193781958083] | False                          |
| B4       | b4b6_no_b8      | ml_hgb            | ml_monotonic_hgb     |            6209 |                0.205217 |                         0.179867 |                      0.181597 | [0.1687274509590388, 0.20266786084698363]  | False                          |
| B4B6B8   | b8_present      | ml_hgb            | ml_monotonic_hgb     |            3774 |                0.214429 |                         0.187941 |                      0.189597 | [0.17983679321612756, 0.20014008805071404] | False                          |
| B4B6B8   | target_hit_only | ml_hgb            | ml_monotonic_hgb     |            3774 |                0.214429 |                         0.187941 |                      0.189597 | [0.17974583260154198, 0.20182558300869705] | False                          |
| B4B6B8   | all_three       | ml_hgb            | ml_monotonic_hgb     |            3774 |                0.214429 |                         0.187941 |                      0.189597 | [0.18015675160824607, 0.20031825483466434] | False                          |
| B4       | all_three       | ml_hgb            | ml_monotonic_hgb     |            3774 |                0.220052 |                         0.192869 |                      0.194483 | [0.18436458356087476, 0.20977665538812837] | False                          |
| B4B6B8   | target_hit_only | traditional_ridge | ml_monotonic_hgb     |            3774 |                0.228177 |                         0.19999  |                      0.201548 | [0.18750233053947943, 0.21562944673174783] | False                          |
| B4B6B8   | all_three       | traditional_ridge | ml_monotonic_hgb     |            3774 |                0.228177 |                         0.19999  |                      0.201548 | [0.18822748351724647, 0.21558591815500966] | False                          |
| B4B6B8   | b8_present      | traditional_ridge | ml_monotonic_hgb     |            3774 |                0.228177 |                         0.19999  |                      0.201548 | [0.18721543323804693, 0.21603058045761883] | False                          |
| B4B6     | b4b6_no_b8      | ml_hgb            | ml_monotonic_hgb     |            6209 |                0.230728 |                         0.202226 |                      0.203766 | [0.19526359894737932, 0.21683150601876167] | False                          |
| B4B6     | all_three       | traditional_ridge | ml_monotonic_hgb     |            3774 |                0.231141 |                         0.202588 |                      0.204126 | [0.18991498598685655, 0.2367250829136476]  | False                          |
| B4       | b4b6_no_b8      | traditional_ridge | ml_monotonic_hgb     |            6209 |                0.232099 |                         0.203427 |                      0.204959 | [0.18868904076200588, 0.235691201701319]   | False                          |

## B2 amplitude strata

Best 36 method/target/gate/bin rows by held-out res68; the full table is `charge_proxy_by_b2_amp.csv`.

| target   | gate            | method            | b2_amp_bin   |    n |   bias_median_frac |   res68_abs_frac |   within_25pct |
|:---------|:----------------|:------------------|:-------------|-----:|-------------------:|-----------------:|---------------:|
| B4B6     | all_three       | ml_hgb            | 2000_3000    | 1932 |        -0.00511213 |         0.17962  |       0.813665 |
| B4       | b4b6_no_b8      | ml_hgb            | 3000_5000    | 2976 |        -0.0202569  |         0.185981 |       0.803091 |
| B4B6     | all_three       | traditional_ridge | 2000_3000    | 1932 |        -0.0208671  |         0.193484 |       0.797101 |
| B4       | b4b6_no_b8      | ml_hgb            | 2000_3000    | 2213 |        -0.0146429  |         0.199717 |       0.785811 |
| B4       | all_three       | ml_hgb            | 2000_3000    | 1932 |        -0.012321   |         0.199929 |       0.787267 |
| B4B6B8   | target_hit_only | ml_hgb            | 2000_3000    | 1932 |        -0.0214812  |         0.207055 |       0.783126 |
| B4B6B8   | b8_present      | ml_hgb            | 2000_3000    | 1932 |        -0.0214812  |         0.207055 |       0.783126 |
| B4B6B8   | all_three       | ml_hgb            | 2000_3000    | 1932 |        -0.0214812  |         0.207055 |       0.783126 |
| B4B6     | all_three       | ml_hgb            | 1000_2000    |  516 |         0.00867159 |         0.207283 |       0.75969  |
| B4       | all_three       | traditional_ridge | 2000_3000    | 1932 |        -0.0300993  |         0.208673 |       0.76087  |
| B4B6B8   | target_hit_only | traditional_ridge | 2000_3000    | 1932 |        -0.0424856  |         0.211262 |       0.777433 |
| B4B6B8   | all_three       | traditional_ridge | 2000_3000    | 1932 |        -0.0424856  |         0.211262 |       0.777433 |
| B4B6B8   | b8_present      | traditional_ridge | 2000_3000    | 1932 |        -0.0424856  |         0.211262 |       0.777433 |
| B4B6B8   | b8_present      | ml_hgb            | 3000_5000    | 1121 |        -0.013395   |         0.211527 |       0.772525 |
| B4B6B8   | all_three       | ml_hgb            | 3000_5000    | 1121 |        -0.013395   |         0.211527 |       0.772525 |
| B4B6B8   | target_hit_only | ml_hgb            | 3000_5000    | 1121 |        -0.013395   |         0.211527 |       0.772525 |
| B4       | b4b6_no_b8      | traditional_ridge | 2000_3000    | 2213 |        -0.00242636 |         0.213572 |       0.752824 |
| B4B6B8   | target_hit_only | traditional_ridge | 7000_inf     |   73 |         0.0295766  |         0.215636 |       0.767123 |
| B4B6B8   | b8_present      | traditional_ridge | 7000_inf     |   73 |         0.0295766  |         0.215636 |       0.767123 |
| B4B6B8   | all_three       | traditional_ridge | 7000_inf     |   73 |         0.0295766  |         0.215636 |       0.767123 |
| B4       | b4b6_no_b8      | traditional_ridge | 3000_5000    | 2976 |        -0.0753345  |         0.218125 |       0.749664 |
| B6       | all_three       | ml_hgb            | 2000_3000    | 1932 |        -0.00810974 |         0.221914 |       0.744824 |
| B4B6     | b4b6_no_b8      | ml_hgb            | 3000_5000    | 2976 |        -0.037033   |         0.222422 |       0.739919 |
| B4B6B8   | all_three       | ml_hgb            | 7000_inf     |   73 |        -0.0096448  |         0.223735 |       0.69863  |
| B4B6B8   | target_hit_only | ml_hgb            | 7000_inf     |   73 |        -0.0096448  |         0.223735 |       0.69863  |
| B4B6B8   | b8_present      | ml_hgb            | 7000_inf     |   73 |        -0.0096448  |         0.223735 |       0.69863  |
| B4B6     | all_three       | ml_hgb            | 3000_5000    | 1121 |        -0.00775816 |         0.224103 |       0.727921 |
| B4B6B8   | all_three       | traditional_ridge | 3000_5000    | 1121 |        -0.0534018  |         0.226023 |       0.727029 |
| B4B6B8   | target_hit_only | traditional_ridge | 3000_5000    | 1121 |        -0.0534018  |         0.226023 |       0.727029 |
| B4B6B8   | b8_present      | traditional_ridge | 3000_5000    | 1121 |        -0.0534018  |         0.226023 |       0.727029 |
| B4B6     | b4b6_no_b8      | ml_hgb            | 2000_3000    | 2213 |        -0.0215208  |         0.227229 |       0.733845 |
| B6       | all_three       | traditional_ridge | 2000_3000    | 1932 |        -0.0269146  |         0.229455 |       0.722567 |
| B4       | all_three       | ml_hgb            | 3000_5000    | 1121 |        -0.00843735 |         0.232797 |       0.71008  |
| B4B6     | target_hit_only | ml_hgb            | 2000_3000    | 4145 |         0.00295788 |         0.236831 |       0.703981 |
| B4B6     | b4b6_no_b8      | traditional_ridge | 3000_5000    | 2976 |        -0.071643   |         0.237833 |       0.707325 |
| B4B6     | b4b6_no_b8      | traditional_ridge | 2000_3000    | 2213 |        -0.0284611  |         0.239178 |       0.70131  |

## Leakage checks

| check                                             | value          | pass   |
|:--------------------------------------------------|:---------------|:-------|
| p04b_external_ml_reproduced_from_raw_root         | 0.213174465233 | True   |
| p04b_expected_delta                               | 0              | True   |
| train_heldout_run_overlap                         | 0              | True   |
| features_exclude_run_event_and_downstream_targets | true           | True   |
| best_real_charge_res68                            | 0.201152       | True   |
| best_shuffled_charge_res68                        | 0.271198       | True   |
| best_real_looks_too_good                          | False          | True   |

## Finding

No downstream proxy/topology row reaches the 0.10 S14 threshold. The best charge row is B4B6 with gate all_three and method ml_hgb, res68 0.2012; after S14b charge propagation the best combined row is 0.1781 for B4B6 / all_three / ml_hgb into ml_monotonic_hgb. The all-three B4+B6+B8 baseline reproduces P04b at 0.2132. Single-stave and relaxed gates add support but do not provide a run-held-out charge proxy below the roughly 0.11 res68 needed for a 0.10 combined range-energy preflight; the limitation is topology-conditioned downstream charge variability, not a hidden B2 waveform model failure.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14c_1781026825_1563_18b74737_charge_proxy_topology.py --config configs/s14c_1781026825_1563_18b74737_charge_proxy_topology.yaml
```

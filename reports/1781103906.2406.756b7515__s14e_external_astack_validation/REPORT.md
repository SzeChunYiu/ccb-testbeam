# S14e: external A-stack validation of accepted saturation bands

## Abstract

Raw ROOT reproduction passes the B-stack selected-pulse anchor exactly: `640737` selected pulses versus the expected `640737`.
Starting from event-matched HRDA/HRDB rows, this study tests whether S14d accepted saturated B-stack correction bands transfer to an external A-stack charge handle.
The external target is deliberately not duplicate readout; it is the positive-lobe selected A1/A3 charge in the same event.  The best leave-one-run-out method is **physics_residual_mlp** with fractional res68 0.35934 and run-bootstrap 95% CI [0.35268, 0.37164].

## Inputs and Raw Reproduction

- **Ticket:** `1781103906.2406.756b7515`
- **Worker:** `testbeam-laptop-2`
- **Raw files:** `data/root/root/{hrda,hrdb}_run_*.root`.
- **S14d source:** `reports/1781033028.1769.29f13a58__s14d_saturation_acceptance_bands/result.json`; S14d winner `gradient_boosted_trees`, accepted band count `12`.
- **P04c topology:** match HRDA and HRDB by `(run, EVT)`, require selected B2 and selected A1 or A3.

| gate | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| B-stack selected pulses | 640737 | 640737 | +0 | True |
| A/B event-matched rows | NA | 4055 | NA | True |

A-stack selected-count reproduction from P04c configuration:

| sample              | events_total | events_with_selected | selected_pulses | A1   | A3   |
| --- | --- | --- | --- | --- | --- |
| sample_iii_analysis | 388848       | 7168                 | 9682            | 2799 | 6883 |
| sample_iv_analysis  | 262189       | 767                  | 894             | 167  | 727  |

A/B topology rows by run:

| run | matched_events | a_any_selected | b2_selected | ab_rows_b2_and_a_any | ab_rows_b2_a_any_downstream_any |
| --- | --- | --- | --- | --- | --- |
| 31  | 16383          | 359            | 11294       | 229                  | 0                               |
| 32  | 16383          | 304            | 11564       | 207                  | 4                               |
| 33  | 16383          | 8              | 13656       | 8                    | 1                               |
| 34  | 16383          | 22             | 13830       | 16                   | 0                               |
| 35  | 16288          | 610            | 6130        | 221                  | 8                               |
| 36  | 16268          | 626            | 7216        | 295                  | 11                              |
| 37  | 16383          | 660            | 7036        | 292                  | 10                              |
| 39  | 16377          | 700            | 7238        | 324                  | 16                              |
| 40  | 16350          | 651            | 6854        | 265                  | 9                               |
| 41  | 16381          | 652            | 7197        | 295                  | 14                              |
| 42  | 16383          | 578            | 8114        | 279                  | 11                              |
| 44  | 1376           | 60             | 602         | 30                   | 2                               |
| 45  | 16383          | 635            | 7597        | 302                  | 15                              |
| 46  | 0              | 0              | 0           | 0                    | 0                               |
| 47  | 5558           | 191            | 2653        | 92                   | 3                               |
| 48  | 16352          | 688            | 6294        | 260                  | 10                              |
| 49  | 16319          | 665            | 7235        | 288                  | 14                              |
| 50  | 16383          | 79             | 12260       | 61                   | 1                               |
| 51  | 16160          | 43             | 11154       | 25                   | 0                               |
| 52  | 2499           | 6              | 1743        | 6                    | 0                               |
| 53  | 16383          | 19             | 12830       | 17                   | 0                               |
| 54  | 16383          | 24             | 12890       | 18                   | 0                               |
| 55  | 16268          | 37             | 11113       | 27                   | 1                               |
| 56  | 16383          | 89             | 12118       | 68                   | 1                               |
| 57  | 16290          | 660            | 6619        | 276                  | 16                              |
| 58  | 16382          | 72             | 7427        | 34                   | 4                               |
| 59  | 16383          | 22             | 5175        | 9                    | 4                               |
| 60  | 16383          | 42             | 4665        | 10                   | 2                               |
| 61  | 16383          | 16             | 4749        | 6                    | 3                               |
| 62  | 16383          | 21             | 4863        | 8                    | 2                               |
| 63  | 16381          | 86             | 6401        | 39                   | 2                               |
| 64  | 16383          | 92             | 6239        | 35                   | 2                               |
| 65  | 16381          | 66             | 4874        | 13                   | 0                               |

Accepted S14d bands imported for external validation:

| current_family | depth_stave | saturated_stave | method                 | n_saturated | saturated_energy_res68 | matched_unsat_energy_res68 | accepted_with_margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| high_20nA      | B2          | B2              | p07_p04_corrected      | 102060      | 0.0271                 | 0.02055                    | True                 |
| high_20nA      | B2          | B2              | gradient_boosted_trees | 102060      | 0.018346               | 0.01353                    | True                 |
| high_20nA      | B4          | B2              | p07_p04_corrected      | 1564        | 0.026254               | 0.016204                   | True                 |
| high_20nA      | B4          | B2              | gradient_boosted_trees | 1564        | 0.015425               | 0.014705                   | True                 |
| high_20nA      | B4          | B4              | p07_p04_corrected      | 73          | 0.016674               | 0.017351                   | True                 |
| high_20nA      | B4          | B4              | gradient_boosted_trees | 73          | 0.010985               | 0.012568                   | True                 |
| high_20nA      | B6          | B2              | p07_p04_corrected      | 703         | 0.011019               | 0.0098946                  | True                 |
| high_20nA      | B6          | B2              | gradient_boosted_trees | 703         | 0.0094421              | 0.0074045                  | True                 |
| high_20nA      | B8          | B2              | p07_p04_corrected      | 354         | 0.0093687              | 0.0067328                  | True                 |
| high_20nA      | B8          | B2              | gradient_boosted_trees | 354         | 0.0077467              | 0.0063888                  | True                 |
| low_2nA        | B2          | B2              | p07_p04_corrected      | 1389        | 0.027253               | 0.013429                   | True                 |
| low_2nA        | B2          | B2              | gradient_boosted_trees | 1389        | 0.023598               | 0.0089842                  | True                 |

## Estimand and Split

For event `i`, the external response is

`y_i = sum_{a in {A1,A3}} 1[A_a selected] sum_t max(w_{iat} - median(w_{ia,0:3}), 0)`.

All predictors use B-stack quantities only: selected even-channel waveforms, B2 charge/amplitude, downstream multiplicity, depth, and charge fractions.  The split is leave-one-run-out.  For run `r`, each model `f_{-r}` is trained on all rows with `run != r` and evaluated only on rows with `run == r`.  Confidence intervals resample the held-out runs as blocks.

## Methods

The strong traditional comparator is a train-only hierarchical median estimator:

`f_trad(x) = median_train(log y | current, A topology, depth, B multiplicity, downstream multiplicity, B2 charge bin, downstream charge bin)`,

with progressively coarser fallback strata down to A topology.  Bins are recomputed inside each training fold, so no held-out quantile information enters the model.

ML/NN comparators are ridge regression on engineered B-stack features, gradient-boosted regression trees, a tabular MLP, a 1D-CNN over the four selected B-stack waveforms plus tabular features, and a new physics-residual MLP.  The residual model learns `log(y) - log(f_trad)` from the same B-stack inputs and then multiplies the traditional prediction by the learned residual factor.

## Main Benchmark

| method                        | n    | bias_median_frac | bias_ci95              | res68_abs_frac | res68_ci95         | full_rms_frac | full_rms_ci95      | within_25pct | tail_gt50pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| physics_residual_mlp          | 4055 | -0.038953        | [-0.056404, -0.01444]  | 0.35934        | [0.35268, 0.37164] | 0.58433       | [0.52261, 0.67228] | 0.48212      | 0.17928      |
| traditional_depth_charge_bins | 4055 | -0.004819        | [-0.024214, 0.014188]  | 0.36105        | [0.3509, 0.37644]  | 0.62157       | [0.54701, 0.71709] | 0.49125      | 0.19309      |
| ridge                         | 4055 | -0.046016        | [-0.071216, -0.020283] | 0.5201         | [0.50251, 0.53693] | 0.84585       | [0.73902, 0.97812] | 0.34969      | 0.34229      |
| gradient_boosted_trees        | 4055 | -0.047558        | [-0.071064, -0.022801] | 0.52238        | [0.50435, 0.54413] | 0.84906       | [0.75066, 1.0016]  | 0.34303      | 0.34254      |
| mlp                           | 4055 | -0.78015         | [-0.83477, -0.65323]   | 0.936          | [0.93201, 0.93985] | 1.7699        | [1.604, 1.9442]    | 0.069544     | 0.84513      |
| 1d_cnn                        | 4055 | -0.91893         | [-0.92069, -0.91706]   | 0.93632        | [0.93423, 0.93782] | 0.90315       | [0.90027, 0.9056]  | 0.0014797    | 0.99753      |

Traditional res68 is 0.36105 [0.3509, 0.37644]; ridge 0.5201 [0.50251, 0.53693]; gradient-boosted trees 0.52238 [0.50435, 0.54413]; MLP 0.936 [0.93201, 0.93985]; 1D-CNN 0.93632 [0.93423, 0.93782]; physics-residual MLP 0.35934 [0.35268, 0.37164].

## Run and Topology Stability

| run | sample                | method                        | n   | bias_median_frac | res68_abs_frac | within_25pct |
| --- | --- | --- | --- | --- | --- | --- |
| 31  | sample_i_calibration  | traditional_depth_charge_bins | 229 | 0.086978         | 0.36548        | 0.45415      |
| 31  | sample_i_calibration  | gradient_boosted_trees        | 229 | -0.059577        | 0.56106        | 0.31441      |
| 31  | sample_i_calibration  | physics_residual_mlp          | 229 | 0.038047         | 0.36251        | 0.46725      |
| 32  | sample_i_calibration  | traditional_depth_charge_bins | 207 | 0.1139           | 0.38356        | 0.48792      |
| 32  | sample_i_calibration  | gradient_boosted_trees        | 207 | 0.015737         | 0.57259        | 0.32367      |
| 32  | sample_i_calibration  | physics_residual_mlp          | 207 | 0.079065         | 0.36122        | 0.47826      |
| 33  | sample_i_calibration  | traditional_depth_charge_bins | 8   | -0.28969         | 0.47562        | 0.25         |
| 33  | sample_i_calibration  | gradient_boosted_trees        | 8   | 0.25171          | 0.41458        | 0.25         |
| 33  | sample_i_calibration  | physics_residual_mlp          | 8   | -0.33516         | 0.45128        | 0.25         |
| 34  | sample_i_calibration  | traditional_depth_charge_bins | 16  | -0.11061         | 0.38992        | 0.5          |
| 34  | sample_i_calibration  | gradient_boosted_trees        | 16  | 0.054264         | 0.57777        | 0.25         |
| 34  | sample_i_calibration  | physics_residual_mlp          | 16  | -0.13893         | 0.40875        | 0.5          |
| 35  | sample_i_calibration  | traditional_depth_charge_bins | 221 | -0.0046612       | 0.36022        | 0.53846      |
| 35  | sample_i_calibration  | gradient_boosted_trees        | 221 | 0.030976         | 0.51431        | 0.34389      |
| 35  | sample_i_calibration  | physics_residual_mlp          | 221 | -0.046628        | 0.35385        | 0.52941      |
| 36  | sample_i_calibration  | traditional_depth_charge_bins | 295 | -0.0062667       | 0.37182        | 0.53559      |
| 36  | sample_i_calibration  | gradient_boosted_trees        | 295 | -0.03313         | 0.48708        | 0.36271      |
| 36  | sample_i_calibration  | physics_residual_mlp          | 295 | -0.047344        | 0.35466        | 0.49153      |
| 37  | sample_i_calibration  | traditional_depth_charge_bins | 292 | -0.057133        | 0.33728        | 0.53425      |
| 37  | sample_i_calibration  | gradient_boosted_trees        | 292 | -0.086822        | 0.4926         | 0.39041      |
| 37  | sample_i_calibration  | physics_residual_mlp          | 292 | -0.07838         | 0.34169        | 0.50685      |
| 39  | sample_i_calibration  | traditional_depth_charge_bins | 324 | 0.015284         | 0.34481        | 0.50309      |
| 39  | sample_i_calibration  | gradient_boosted_trees        | 324 | -0.10632         | 0.46203        | 0.3642       |
| 39  | sample_i_calibration  | physics_residual_mlp          | 324 | -0.0051838       | 0.35368        | 0.5          |
| 40  | sample_i_calibration  | traditional_depth_charge_bins | 265 | -0.059551        | 0.33145        | 0.48679      |
| 40  | sample_i_calibration  | gradient_boosted_trees        | 265 | -0.058865        | 0.49055        | 0.39623      |
| 40  | sample_i_calibration  | physics_residual_mlp          | 265 | -0.081997        | 0.34073        | 0.46415      |
| 41  | sample_i_calibration  | traditional_depth_charge_bins | 295 | -0.013355        | 0.33364        | 0.51186      |
| 41  | sample_i_calibration  | gradient_boosted_trees        | 295 | -0.11317         | 0.52083        | 0.30508      |
| 41  | sample_i_calibration  | physics_residual_mlp          | 295 | -0.046672        | 0.34803        | 0.49831      |
| 42  | sample_i_calibration  | traditional_depth_charge_bins | 279 | 0.04202          | 0.35429        | 0.50179      |
| 42  | sample_i_calibration  | gradient_boosted_trees        | 279 | -0.040607        | 0.50767        | 0.35842      |
| 42  | sample_i_calibration  | physics_residual_mlp          | 279 | 0.010349         | 0.35762        | 0.50538      |
| 44  | sample_i_analysis     | traditional_depth_charge_bins | 30  | -0.058709        | 0.35384        | 0.53333      |
| 44  | sample_i_analysis     | gradient_boosted_trees        | 30  | -0.13672         | 0.52836        | 0.3          |
| 44  | sample_i_analysis     | physics_residual_mlp          | 30  | -0.11404         | 0.35802        | 0.5          |
| 45  | sample_i_analysis     | traditional_depth_charge_bins | 302 | 0.03251          | 0.38337        | 0.48344      |
| 45  | sample_i_analysis     | gradient_boosted_trees        | 302 | 0.010863         | 0.52917        | 0.30795      |
| 45  | sample_i_analysis     | physics_residual_mlp          | 302 | -0.01692         | 0.3658         | 0.48344      |
| 47  | sample_i_analysis     | traditional_depth_charge_bins | 92  | -0.016622        | 0.27518        | 0.6087       |
| 47  | sample_i_analysis     | gradient_boosted_trees        | 92  | 0.002104         | 0.48568        | 0.33696      |
| 47  | sample_i_analysis     | physics_residual_mlp          | 92  | -0.056968        | 0.29092        | 0.56522      |
| 48  | sample_i_analysis     | traditional_depth_charge_bins | 260 | -0.032046        | 0.32661        | 0.49231      |
| 48  | sample_i_analysis     | gradient_boosted_trees        | 260 | -0.11597         | 0.4915         | 0.35769      |
| 48  | sample_i_analysis     | physics_residual_mlp          | 260 | -0.050648        | 0.33546        | 0.51538      |
| 49  | sample_i_analysis     | traditional_depth_charge_bins | 288 | -0.012366        | 0.36276        | 0.48958      |
| 49  | sample_i_analysis     | gradient_boosted_trees        | 288 | -0.090294        | 0.55164        | 0.29167      |
| 49  | sample_i_analysis     | physics_residual_mlp          | 288 | -0.060202        | 0.365          | 0.48611      |
| 50  | sample_i_analysis     | traditional_depth_charge_bins | 61  | -0.039647        | 0.44293        | 0.37705      |
| 50  | sample_i_analysis     | gradient_boosted_trees        | 61  | 0.095249         | 0.58349        | 0.32787      |
| 50  | sample_i_analysis     | physics_residual_mlp          | 61  | -0.062373        | 0.43346        | 0.40984      |
| 51  | sample_i_analysis     | traditional_depth_charge_bins | 25  | -0.23053         | 0.44892        | 0.28         |
| 51  | sample_i_analysis     | gradient_boosted_trees        | 25  | -0.035108        | 0.66452        | 0.28         |
| 51  | sample_i_analysis     | physics_residual_mlp          | 25  | -0.23677         | 0.45587        | 0.24         |
| 52  | sample_i_analysis     | traditional_depth_charge_bins | 6   | -0.19226         | 0.43242        | 0.16667      |
| 52  | sample_i_analysis     | gradient_boosted_trees        | 6   | -0.22656         | 0.3712         | 0.5          |
| 52  | sample_i_analysis     | physics_residual_mlp          | 6   | -0.23063         | 0.4636         | 0.16667      |
| 53  | sample_i_analysis     | traditional_depth_charge_bins | 17  | 0.23953          | 0.72827        | 0.29412      |
| 53  | sample_i_analysis     | gradient_boosted_trees        | 17  | 0.45836          | 1.1348         | 0.23529      |
| 53  | sample_i_analysis     | physics_residual_mlp          | 17  | 0.16676          | 0.7398         | 0.17647      |
| 54  | sample_i_analysis     | traditional_depth_charge_bins | 18  | -0.020412        | 0.44092        | 0.33333      |
| 54  | sample_i_analysis     | gradient_boosted_trees        | 18  | 0.40068          | 0.68049        | 0.27778      |
| 54  | sample_i_analysis     | physics_residual_mlp          | 18  | -0.076486        | 0.43467        | 0.33333      |
| 55  | sample_i_analysis     | traditional_depth_charge_bins | 27  | -0.29322         | 0.51954        | 0.18519      |
| 55  | sample_i_analysis     | gradient_boosted_trees        | 27  | -0.11836         | 0.45627        | 0.25926      |
| 55  | sample_i_analysis     | physics_residual_mlp          | 27  | -0.2759          | 0.53058        | 0.18519      |
| 56  | sample_i_analysis     | traditional_depth_charge_bins | 68  | 0.086539         | 0.42808        | 0.42647      |
| 56  | sample_i_analysis     | gradient_boosted_trees        | 68  | 0.05115          | 0.64819        | 0.29412      |
| 56  | sample_i_analysis     | physics_residual_mlp          | 68  | 0.082985         | 0.42863        | 0.39706      |
| 57  | sample_i_analysis     | traditional_depth_charge_bins | 276 | -0.037239        | 0.33544        | 0.50725      |
| 57  | sample_i_analysis     | gradient_boosted_trees        | 276 | -0.12964         | 0.53707        | 0.29348      |
| 57  | sample_i_analysis     | physics_residual_mlp          | 276 | -0.064007        | 0.3568         | 0.51449      |
| 58  | sample_ii_analysis    | traditional_depth_charge_bins | 34  | 0.049027         | 0.53462        | 0.47059      |
| 58  | sample_ii_analysis    | gradient_boosted_trees        | 34  | -0.0084717       | 0.51037        | 0.41176      |
| 58  | sample_ii_analysis    | physics_residual_mlp          | 34  | 0.010034         | 0.50947        | 0.44118      |
| 59  | sample_ii_analysis    | traditional_depth_charge_bins | 9   | -0.22853         | 0.35282        | 0.55556      |
| 59  | sample_ii_analysis    | gradient_boosted_trees        | 9   | -0.13636         | 0.27083        | 0.66667      |
| 59  | sample_ii_analysis    | physics_residual_mlp          | 9   | -0.18372         | 0.33661        | 0.44444      |
| 60  | sample_ii_analysis    | traditional_depth_charge_bins | 10  | 0.8867           | 1.4301         | 0.2          |
| 60  | sample_ii_analysis    | gradient_boosted_trees        | 10  | 1.3465           | 1.949          | 0.1          |
| 60  | sample_ii_analysis    | physics_residual_mlp          | 10  | 0.86121          | 1.293          | 0.2          |
| 61  | sample_ii_analysis    | traditional_depth_charge_bins | 6   | -0.17215         | 0.45954        | 0.5          |
| 61  | sample_ii_analysis    | gradient_boosted_trees        | 6   | -0.072454        | 0.42463        | 0.5          |
| 61  | sample_ii_analysis    | physics_residual_mlp          | 6   | -0.19466         | 0.56395        | 0.5          |
| 62  | sample_ii_analysis    | traditional_depth_charge_bins | 8   | -0.011174        | 0.37581        | 0.5          |
| 62  | sample_ii_analysis    | gradient_boosted_trees        | 8   | 0.16581          | 0.4083         | 0.5          |
| 62  | sample_ii_analysis    | physics_residual_mlp          | 8   | -0.044724        | 0.31816        | 0.5          |
| 63  | sample_ii_analysis    | traditional_depth_charge_bins | 39  | -0.15113         | 0.38828        | 0.25641      |
| 63  | sample_ii_analysis    | gradient_boosted_trees        | 39  | -0.072312        | 0.247          | 0.69231      |
| 63  | sample_ii_analysis    | physics_residual_mlp          | 39  | -0.19286         | 0.37525        | 0.28205      |
| 64  | sample_ii_calibration | traditional_depth_charge_bins | 35  | -0.076754        | 0.45448        | 0.37143      |
| 64  | sample_ii_calibration | gradient_boosted_trees        | 35  | 0.0874           | 0.75773        | 0.48571      |
| 64  | sample_ii_calibration | physics_residual_mlp          | 35  | -0.114           | 0.42601        | 0.28571      |
| 65  | sample_ii_analysis    | traditional_depth_charge_bins | 13  | -0.10217         | 0.36325        | 0.38462      |
| 65  | sample_ii_analysis    | gradient_boosted_trees        | 13  | 0.047508         | 0.44586        | 0.53846      |
| 65  | sample_ii_analysis    | physics_residual_mlp          | 13  | -0.16613         | 0.39191        | 0.38462      |

| current_family | depth_stave | a_topology | method                        | n    | bias_median_frac | res68_abs_frac | within_25pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| high_20nA      | B2          | A1         | traditional_depth_charge_bins | 143  | 0.0045228        | 0.51828        | 0.36364      |
| high_20nA      | B2          | A1         | gradient_boosted_trees        | 143  | 0.6565           | 1.1754         | 0.16783      |
| high_20nA      | B2          | A1         | physics_residual_mlp          | 143  | -0.040469        | 0.515          | 0.35664      |
| high_20nA      | B2          | A1+A3      | traditional_depth_charge_bins | 1260 | -0.0021991       | 0.27277        | 0.63413      |
| high_20nA      | B2          | A1+A3      | gradient_boosted_trees        | 1260 | -0.42558         | 0.49973        | 0.16032      |
| high_20nA      | B2          | A1+A3      | physics_residual_mlp          | 1260 | -0.027403        | 0.27138        | 0.63651      |
| high_20nA      | B2          | A3         | traditional_depth_charge_bins | 2397 | -0.0030273       | 0.40749        | 0.42178      |
| high_20nA      | B2          | A3         | gradient_boosted_trees        | 2397 | 0.21101          | 0.56575        | 0.44806      |
| high_20nA      | B2          | A3         | physics_residual_mlp          | 2397 | -0.045572        | 0.40855        | 0.40759      |
| high_20nA      | B4          | A1+A3      | traditional_depth_charge_bins | 37   | -0.20221         | 0.42793        | 0.40541      |
| high_20nA      | B4          | A1+A3      | gradient_boosted_trees        | 37   | -0.4578          | 0.51762        | 0.13514      |
| high_20nA      | B4          | A1+A3      | physics_residual_mlp          | 37   | -0.22915         | 0.42579        | 0.43243      |
| high_20nA      | B4          | A3         | traditional_depth_charge_bins | 60   | 0.062918         | 0.46048        | 0.48333      |
| high_20nA      | B4          | A3         | gradient_boosted_trees        | 60   | 0.10418          | 0.38493        | 0.56667      |
| high_20nA      | B4          | A3         | physics_residual_mlp          | 60   | 0.019237         | 0.43916        | 0.46667      |
| high_20nA      | B6          | A3         | traditional_depth_charge_bins | 36   | 0.022667         | 0.41956        | 0.47222      |
| high_20nA      | B6          | A3         | gradient_boosted_trees        | 36   | 0.14239          | 0.43085        | 0.44444      |
| high_20nA      | B6          | A3         | physics_residual_mlp          | 36   | -0.0091408       | 0.39019        | 0.47222      |
| low_2nA        | B2          | A1+A3      | traditional_depth_charge_bins | 30   | -0.1059          | 0.23294        | 0.76667      |
| low_2nA        | B2          | A1+A3      | gradient_boosted_trees        | 30   | -0.48243         | 0.53271        | 0.1          |
| low_2nA        | B2          | A1+A3      | physics_residual_mlp          | 30   | -0.10568         | 0.25816        | 0.66667      |
| low_2nA        | B2          | A3         | traditional_depth_charge_bins | 59   | 0.031682         | 0.33049        | 0.52542      |
| low_2nA        | B2          | A3         | gradient_boosted_trees        | 59   | 0.2304           | 0.41464        | 0.44068      |
| low_2nA        | B2          | A3         | physics_residual_mlp          | 59   | -0.0458          | 0.32784        | 0.50847      |

## Systematics and Caveats

- External A-stack charge is a detector handle, not an absolute proton energy measurement.
- A-stack support is sparse relative to the B-stack selected-pulse anchor; sample-II analysis A-stack counts are especially small.
- The result tests transfer away from duplicate readout.  It does not invalidate S14d duplicate-readout closure; it bounds how far that closure can be generalized to an independent detector handle.
- Geometry, A-stack efficiency, and A/B acceptance are not unfolded here.  The proposed follow-up ticket targets those nuisance terms directly.
- Neural models are intentionally compact and trained inside run folds.  Their comparison is a leakage-resistant benchmark, not an architecture search.

## Finding

External A-stack transfer is much broader than S14d duplicate-readout closure. The winner is physics_residual_mlp with selected-A charge res68 0.35934 [0.35268, 0.37164], while the strong traditional hierarchical bins give 0.36105 [0.3509, 0.37644]. The imported S14d winner was gradient_boosted_trees on duplicate-readout saturated B-stack energy proxy, but the external A-stack handle is topology- and acceptance-limited; therefore S14d accepted bands should not be promoted as detector-independent range-energy corrections without a geometry-aware external calibration.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `b_s00_counts_by_run.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `external_astack_summary.csv`, `external_astack_by_run.csv`, `external_astack_by_band.csv`, `fold_diagnostics.csv`, and `external_astack_predictions.csv`.

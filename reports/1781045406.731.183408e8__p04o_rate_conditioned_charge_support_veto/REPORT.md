# P04o: rate-conditioned charge support veto

- **Ticket:** 1781045406.731.183408e8
- **Worker:** testbeam-laptop-4
- **Config:** `configs/p04o_1781045406_731_183408e8_rate_conditioned_charge_support_veto.yaml`
- **Raw input:** `data/root/root`
- **Git commit at run:** `124659c50f1b88bd01cad4b91e2ab9672b7ea27e`

## Abstract

This study tests whether sparse A/B coincidence-rate and current-acceptance atoms create a charge-transfer nuisance that should veto P04/S14 energy or PID consumers in low-support regions.  The analysis rebuilds the P04 raw-ROOT selected-pulse population, uses independent odd-channel duplicate-readout charge as the charge-closure target, and evaluates traditional, ML, and neural regressors with complete runs held out.  The primary result is the charge residual width, signed bias, energy-ordering flip rate, conformal coverage, and support loss after rate-aware abstention.

The named winner in `result.json` is `extra_trees_with_rate`.  Its charge res68 is `0.00882` with run-block 95% CI `[0.00733, 0.01097]`.

## Raw-ROOT Reproduction Gate

The reproduced number is the P04 selected B-stave pulse count from raw `h101/HRDv`: subtract the median of samples 0--3 separately for each channel, select physical B channels `B2/B4/B6/B8 = 0/2/4/6`, and require `max(HRDv - baseline) > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| all configured B-stave selected pulses | 640,737 | 640,737 | +0 | true |

Analysis-run anchors:

| run_group          |   selected_pulses |
|:-------------------|------------------:|
| sample_i_analysis  |            252266 |
| sample_ii_analysis |            125096 |

Only after this gate passes does the script construct the analysis table.  The P04o fit table contains `377,273` valid analysis-run rows after requiring a positive independent odd-readout charge.

## Data and Labels

For event `i`, stave `s`, and sample index `t`, let

`x_ist = HRDv_ist - median_t in B(HRDv_ist)`, with `B = {0,1,2,3}`.

The input waveform is the even physical B-stave channel.  The target is the paired odd-channel duplicate-readout positive lobe,

`y_is = sum_t max(-(HRDv_odd,ist - baseline_odd,is), 0)`.

This target is not the same waveform used as input, so peak and charge features do not trivially define the label.  The available non-waveform covariates are run family, current, event topology, saturation depth `max(A-3800,0)`, q-template/tail quantile, baseline RMS taxon, geometry support, and the held-out run-level A/B rate residual.

## Rate Residual Model

For analysis run `r`, the rate target is

`p_r = (N(A_any and B_any) + 1/2) / (N(B_any) + 1)`.

The traditional rate model is a weighted Ridge regression on `logit(p_r)` using only current, target setting, B-only topology fractions, and B occupancy.  Predictions are group-held-out by run; the residual used by charge models is `100*(p_r - p_hat_r)`.

|   fold | heldout_runs   |   n_train_runs |   rate_rmse_pp |
|-------:|:---------------|---------------:|---------------:|
|      0 | 44,48,54,58,65 |             16 |       0.707757 |
|      1 | 49,53,59,63    |             17 |       0.276078 |
|      2 | 45,50,55,60    |             17 |       1.0092   |
|      3 | 46,51,56,61    |             17 |       0.382133 |
|      4 | 47,52,57,62    |             17 |      35.7204   |

Run-level rate table:

|   run | run_group          |   current_nA |   b_any_events |   target_rate |   pred_rate_traditional |   rate_residual_pp |   b_multi_frac |   b2_share |
|------:|:-------------------|-------------:|---------------:|--------------:|------------------------:|-------------------:|---------------:|-----------:|
|    44 | sample_i_analysis  |           20 |           1912 |    0.0394668  |             0.0206858   |         1.8781     |     0.0209595  |   0.985356 |
|    45 | sample_i_analysis  |           20 |          23004 |    0.0392741  |             0.020308    |         1.8966     |     0.019581   |   0.990132 |
|    46 | sample_i_analysis  |            2 |            661 |    0.0294562  |             0.000968793 |         2.84874    |     0.00567779 |   0.996974 |
|    47 | sample_i_analysis  |            2 |           5141 |    0.0356865  |             0.98636     |       -95.0674     |     0.00759239 |   0.991441 |
|    48 | sample_i_analysis  |           20 |          13167 |    0.0424894  |             0.0284168   |         1.40726    |     0.0184442  |   0.989291 |
|    49 | sample_i_analysis  |           20 |          13919 |    0.0395474  |             0.0409987   |        -0.145129   |     0.0192784  |   0.988649 |
|    50 | sample_i_analysis  |           20 |          34251 |    0.00480264 |             0.00188359  |         0.291904   |     0.0154251  |   0.995066 |
|    51 | sample_i_analysis  |           20 |          14291 |    0.00297369 |             0.00277777  |         0.0195918  |     0.0149791  |   0.993352 |
|    52 | sample_i_analysis  |           20 |           6933 |    0.00151428 |             0.000434879 |         0.10794    |     0.0146971  |   0.99423  |
|    53 | sample_i_analysis  |           20 |          31385 |    0.00116294 |             0.00496998  |        -0.380704   |     0.0143142  |   0.99487  |
|    54 | sample_i_analysis  |           20 |          29638 |    0.00163636 |             0.00451824  |        -0.288189   |     0.0146071  |   0.99423  |
|    55 | sample_i_analysis  |           20 |          16820 |    0.00270495 |             0.00275144  |        -0.00464838 |     0.0155001  |   0.993698 |
|    56 | sample_i_analysis  |           20 |          38913 |    0.00558925 |             0.00239572  |         0.319353   |     0.0164871  |   0.994809 |
|    57 | sample_i_analysis  |           20 |          12925 |    0.0410413  |             0.110298    |        -6.92568    |     0.0200288  |   0.987234 |
|    58 | sample_ii_analysis |           20 |          15890 |    0.00437354 |             0.00336732  |         0.100622   |     0.0172247  |   0.991945 |
|    59 | sample_ii_analysis |           20 |          13863 |    0.00155078 |             0.00247853  |        -0.0927752  |     0.108503   |   0.978504 |
|    60 | sample_ii_analysis |           20 |          10139 |    0.0020217  |             0.00100753  |         0.101417   |     0.112436   |   0.973666 |
|    61 | sample_ii_analysis |           20 |          11282 |    0.00226004 |             0.00101517  |         0.124486   |     0.121176   |   0.975891 |
|    62 | sample_ii_analysis |           20 |          11902 |    0.00155423 |             0.00330038  |        -0.174615   |     0.112265   |   0.976727 |
|    63 | sample_ii_analysis |           20 |          14756 |    0.00545504 |             0.00331933  |         0.213571   |     0.0707295  |   0.98543  |
|    65 | sample_ii_analysis |           20 |          11875 |    0.00509431 |             0.00779405  |        -0.269974   |     0.0212894  |   0.988547 |

## Charge Models

All reported predictions are out-of-fold with complete runs held out using grouped 5-fold CV over analysis runs.  The methods are:

- `traditional_stratified_charge`: P04-style log charge calibration with a frozen stratified median residual correction over stave, run family, event topology, saturation depth, q-template bin, baseline taxon, and geometry support.
- `ridge_no_rate` and `ridge_with_rate`: linear ridge baselines with standardized continuous features and one-hot support taxa.
- `hgb_no_rate` and `hgb_with_rate`: histogram gradient-boosted regressors with and without rate residual features.
- `extra_trees_with_rate`: ExtraTrees charge regressor with the same rate-aware support features.
- `mlp_with_rate`: shallow neural MLP on the tabular support feature set.
- `cnn_1d_with_rate`: 1D-CNN on the 18-sample even waveform fused with auxiliary rate/support coordinates.
- `new_rate_support_gated_hgb`: a rate-aware HGB with an explicit support/conformal abstention gate.
- `hgb_shuffled_rate_control`, `run_only_control`, and `topology_only_control`: nuisance and leakage controls.

For method `m`, fractional charge residual is `e_i(m) = (hat y_i(m)-y_i)/max(y_i,1)`.  The primary width is `Q_0.68(|e_i|)`, signed bias is `median(e_i)`, and the conformal half width is the train-fold 90th percentile of `|e_i|`.  Coverage is evaluated on held-out rows.  Energy-ordering flips compare all non-tied same-event selected-stave pairs and count sign disagreements between true and predicted charge ordering.

## Results

| method                        |   n_eval |   res68_frac |   res68_ci_low_frac |   res68_ci_high_frac |   signed_bias_frac |   bias_ci_low_frac |   bias_ci_high_frac |   energy_ordering_flip_rate |   flip_ci_low |   flip_ci_high |   support_loss |   conformal_coverage_90 |
|:------------------------------|---------:|-------------:|--------------------:|---------------------:|-------------------:|-------------------:|--------------------:|----------------------------:|--------------:|---------------:|---------------:|------------------------:|
| extra_trees_with_rate         |   377273 |   0.00882021 |          0.00732791 |            0.0109737 |       -0.000468998 |       -0.000679021 |        -0.00030546  |                  0.00948074 |    0.00781235 |      0.0107467 |       0        |                0.894355 |
| new_rate_support_gated_hgb    |   321315 |   0.0137541  |          0.0121689  |            0.0161296 |        0.000257679 |       -6.28695e-05 |         0.000723172 |                  0.0103823  |    0.00886526 |      0.0120129 |       0.148322 |                0.894382 |
| hgb_with_rate                 |   377273 |   0.0153142  |          0.0139559  |            0.0173119 |        0.000231599 |       -0.000167292 |         0.000823053 |                  0.00949749 |    0.00794714 |      0.0106418 |       0        |                0.895564 |
| hgb_shuffled_rate_control     |   377273 |   0.0153627  |          0.0138234  |            0.017428  |        0.000212171 |       -0.00021505  |         0.00074005  |                  0.00953099 |    0.00816149 |      0.0106346 |       0        |                0.895148 |
| hgb_no_rate                   |   377273 |   0.0153822  |          0.0138492  |            0.0176419 |        0.00022361  |       -0.000176639 |         0.000793167 |                  0.0100335  |    0.0081991  |      0.0113611 |       0        |                0.895079 |
| mlp_with_rate                 |   377273 |   0.0259562  |          0.0213677  |            0.0345781 |        0.00819305  |        0.00094466  |         0.0126478   |                  0.011943   |    0.010016   |      0.0144957 |       0        |                0.865249 |
| traditional_stratified_charge |   377273 |   0.0467691  |          0.0300417  |            0.0712076 |       -0.000287411 |       -0.00104192  |         0.000714094 |                  0.0648576  |    0.0614461  |      0.0729102 |       0        |                0.894379 |
| ridge_no_rate                 |   377273 |   0.0525328  |          0.0408937  |            0.0827091 |        0.00261325  |       -0.00788161  |         0.00812731  |                  0.0296817  |    0.0259876  |      0.0324516 |       0        |                0.8947   |
| ridge_with_rate               |   377273 |   0.0537711  |          0.0430059  |            0.0814432 |        0.00188077  |       -0.00861385  |         0.00687386  |                  0.0296147  |    0.0261106  |      0.0324648 |       0        |                0.894143 |
| cnn_1d_with_rate              |   377273 |   0.163725   |          0.144625   |            0.191062  |       -0.0050823   |       -0.014478    |         0.00502979  |                  0.145343   |    0.123117   |      0.163253  |       0        |                0.884055 |
| run_only_control              |   377273 |   0.455915   |          0.42381    |            0.570244  |       -0.267678    |       -0.318102    |        -0.14833     |                  1          |    1          |      1         |       0        |                0.896847 |
| topology_only_control         |   377273 |   0.481236   |          0.387227   |            0.557505  |       -0.199745    |       -0.271359    |        -0.162685    |                  0.325578   |    0.293628   |      0.341659  |       0        |                0.898344 |

ML-minus-traditional deltas use the same run-block bootstrap:

| comparison                                                           |   delta_res68_frac |   ci_low_frac |   ci_high_frac |
|:---------------------------------------------------------------------|-------------------:|--------------:|---------------:|
| ridge_no_rate_minus_traditional_stratified_charge_res68              |         0.00682066 |    0.00254069 |      0.0117015 |
| ridge_with_rate_minus_traditional_stratified_charge_res68            |         0.00799897 |    0.00338269 |      0.0126702 |
| hgb_no_rate_minus_traditional_stratified_charge_res68                |        -0.0315876  |   -0.0519567  |     -0.0149922 |
| hgb_with_rate_minus_traditional_stratified_charge_res68              |        -0.0328573  |   -0.0555872  |     -0.0179389 |
| extra_trees_with_rate_minus_traditional_stratified_charge_res68      |        -0.0399134  |   -0.0604433  |     -0.0225982 |
| mlp_with_rate_minus_traditional_stratified_charge_res68              |        -0.0218215  |   -0.0397735  |     -0.0069067 |
| cnn_1d_with_rate_minus_traditional_stratified_charge_res68           |         0.117871   |    0.0963169  |      0.143783  |
| new_rate_support_gated_hgb_minus_traditional_stratified_charge_res68 |        -0.0342856  |   -0.0547748  |     -0.0187205 |
| hgb_shuffled_rate_control_minus_traditional_stratified_charge_res68  |        -0.0321758  |   -0.049647   |     -0.0162449 |
| run_only_control_minus_traditional_stratified_charge_res68           |         0.423284   |    0.388269   |      0.507315  |
| topology_only_control_minus_traditional_stratified_charge_res68      |         0.433364   |    0.358576   |      0.493892  |

## Support Veto Map

The table below lists the highest-loss or widest support cells for the new gated architecture.  These cells are the practical veto candidates for downstream P04/S14 charge, energy, or weak PID consumers.

| stave   | run_group          |   event_b_n_selected | saturation_bin   | q_template_bin   | baseline_taxon   |   n |   n_runs |   rate_residual_median_pp |   new_arch_res68_frac |   support_loss |
|:--------|:-------------------|---------------------:|:-----------------|:-----------------|:-----------------|----:|---------:|--------------------------:|----------------------:|---------------:|
| B8      | sample_i_analysis  |                    1 | none             | q1               | wide             |  80 |       13 |               -0.00464838 |            0.0475841  |       1        |
| B2      | sample_i_analysis  |                    2 | low              | q1               | wide             |  80 |        9 |                0.305629   |            0.0398195  |       1        |
| B2      | sample_ii_analysis |                    2 | mid              | q2               | wide             |  93 |        6 |               -0.0927752  |            0.0337071  |       1        |
| B8      | sample_i_analysis  |                    2 | none             | q4               | wide             |  84 |       12 |                0.10794    |            0.0331293  |       1        |
| B2      | sample_i_analysis  |                    4 | high             | q2               | wide             |  83 |       12 |                0.0195918  |            0.0319688  |       1        |
| B2      | sample_ii_analysis |                    3 | high             | q4               | wide             |  88 |        7 |               -0.0927752  |            0.0235664  |       1        |
| B6      | sample_i_analysis  |                    3 | low              | q4               | wide             |  89 |       13 |               -0.00464838 |            0.0208152  |       1        |
| B6      | sample_ii_analysis |                    1 | none             | q4               | wide             |  90 |        7 |                0.100622   |            0.0192405  |       1        |
| B4      | sample_ii_analysis |                    2 | low              | q4               | quiet            |  83 |        7 |                0.101417   |            0.0161913  |       1        |
| B2      | sample_ii_analysis |                    4 | none             | q2               | mid              |  89 |        6 |                0.101417   |            0.0129234  |       1        |
| B6      | sample_ii_analysis |                    3 | none             | q4               | quiet            |  92 |        6 |               -0.0927752  |            0.012466   |       1        |
| B4      | sample_ii_analysis |                    2 | low              | q3               | wide             |  85 |        7 |                0.101417   |            0.0121405  |       1        |
| B2      | sample_ii_analysis |                    2 | none             | q2               | mid              |  80 |        6 |                0.101417   |            0.0114424  |       1        |
| B2      | sample_ii_analysis |                    3 | none             | q1               | mid              |  84 |        6 |                0.101417   |            0.0109771  |       1        |
| B4      | sample_ii_analysis |                    2 | high             | q3               | wide             |  84 |        7 |                0.101417   |            0.00892006 |       1        |
| B2      | sample_i_analysis  |                    1 | low              | q2               | mid              |  81 |       13 |                0.319353   |            0.00647277 |       1        |
| B2      | sample_ii_analysis |                    3 | none             | q2               | mid              |  87 |        7 |                0.101417   |            0.0148072  |       0.931034 |
| B4      | sample_i_analysis  |                    2 | low              | q1               | wide             |  92 |       13 |                0.291904   |            0.0371198  |       0.913043 |
| B8      | sample_ii_analysis |                    4 | high             | q4               | wide             |  89 |        7 |                0.101417   |            0.0155966  |       0.910112 |
| B2      | sample_ii_analysis |                    2 | mid              | q3               | wide             |  94 |        7 |                0.100622   |            0.017455   |       0.882979 |
| B8      | sample_ii_analysis |                    4 | none             | q4               | quiet            |  91 |        6 |                0.100622   |            0.0183618  |       0.879121 |
| B2      | sample_i_analysis  |                    1 | low              | q3               | quiet            | 107 |       14 |               -0.00464838 |            0.00935185 |       0.82243  |
| B2      | sample_i_analysis  |                    4 | none             | q4               | wide             |  92 |       12 |                0.10794    |            0.0236849  |       0.793478 |
| B6      | sample_ii_analysis |                    4 | none             | q2               | wide             |  93 |        6 |                0.101417   |            0.0138293  |       0.763441 |
| B2      | sample_ii_analysis |                    2 | low              | q3               | wide             |  95 |        7 |               -0.0927752  |            0.012391   |       0.726316 |
| B2      | sample_ii_analysis |                    3 | low              | q4               | wide             | 107 |        7 |                0.101417   |            0.0221609  |       0.71028  |
| B4      | sample_ii_analysis |                    2 | mid              | q2               | wide             | 107 |        7 |                0.101417   |            0.0295971  |       0.691589 |
| B2      | sample_i_analysis  |                    4 | none             | q1               | wide             | 108 |       13 |                0.291904   |            0.0735881  |       0.666667 |
| B4      | sample_ii_analysis |                    4 | none             | q4               | quiet            | 113 |        7 |                0.101417   |            0.0194952  |       0.654867 |
| B8      | sample_ii_analysis |                    1 | none             | q1               | wide             | 106 |        7 |                0.101417   |            0.1444     |       0.641509 |

## Systematics and Caveats

The study is a duplicate-readout closure, not an absolute particle-energy calibration.  A/B rate residuals are run-level observables, so within-run event-level current structure can remain unresolved.  The low-current run 47 fold is an explicit stress case: the held-out weighted-logit rate model extrapolates far outside the observed few-percent A/B rate scale, which is why the rate residual should be treated as a support warning rather than a calibrated correction.  The A-stack matching is based on raw `EVENTNO`, while B-stack pulse rows retain `EVT` only for internal event grouping.  The conformal intervals are fold-local empirical intervals on fractional charge residuals; they are valid as operational abstention checks under exchangeability within the held-out run family, not as detector truth intervals.  The energy-ordering flip metric is relative to odd-channel duplicate charge and ignores pairs whose true charges differ by less than 5%, because those are operationally indistinguishable at this resolution.

The support veto is therefore conservative: a low-support atom means "do not promote this charge closure to a P04/S14 physics consumer without independent validation", not "the event is physically invalid".

## Conclusion

The best out-of-fold charge closure is extra_trees_with_rate with res68 0.00882 [0.00733, 0.01097], versus the frozen traditional stratified closure at 0.04677. The explicit rate-support gate abstains on 14.83% of rows and gives conformal coverage 0.894; low-support cells concentrate in high-saturation, high-tail, sparse-topology atoms. Rate residual features improve the best HGB/ExtraTrees closures only modestly relative to waveform/topology features, so the operational recommendation is to use the support veto as a downstream P04/S14 guardrail rather than treat A/B rate as an energy correction.

## Artifacts

`counts_by_run.csv`, `run_level_rates.csv`, `rate_cv.csv`, `analysis_rows_preview.csv`, `oof_predictions.csv.gz`, `method_metrics.csv`, `method_deltas.csv`, `support_veto_cells.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and this report.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04o_1781045406_731_183408e8_rate_conditioned_charge_support_veto.py --config configs/p04o_1781045406_731_183408e8_rate_conditioned_charge_support_veto.yaml
```

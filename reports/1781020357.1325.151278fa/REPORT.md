# S14c: externalized S14b energy-proxy validation

- **Ticket ID:** 1781020357.1325.151278fa
- **Worker:** testbeam-laptop-2
- **Input:** raw `data/root/root/hrda_run_*.root` and `data/root/root/hrdb_run_*.root` only; no Monte Carlo and no absolute PID truth labels.
- **Split:** training/calibration runs are disjoint from analysis held-out runs; CIs resample held-out runs as blocks.

## Raw Reproduction

| quantity                                        |   expected |   reproduced |   delta | pass   |
|:------------------------------------------------|-----------:|-------------:|--------:|:-------|
| S00 selected B-stave pulse records              |     640737 |       640737 |       0 | True   |
| A-stack sample_i_analysis events_with_selected  |       7168 |         7168 |       0 | True   |
| A-stack sample_i_analysis selected_pulses       |       9682 |         9682 |       0 | True   |
| A-stack sample_ii_analysis events_with_selected |        767 |          767 |       0 | True   |
| A-stack sample_ii_analysis selected_pulses      |        894 |          894 |       0 | True   |

## Methods

Traditional closure bins the S14 B-stack energy proxies into train-run quartile strata, then compares held-out stratum means for event-matched A-stack tags, downstream B-stack multiplicity, and documented Sample-I low-current runs.

ML uses a domain-residualized standardized ridge surrogate for a composite external score: A-stack depth tag, downstream multiplicity, and a small low-current term. The target is residualized by run-family means learned only from training runs. Features exclude A-stack observables, run id, event id, group labels, odd duplicate target charge, and the current label.

## Traditional External Closure

| method                         | proxy                    | target                    |      n |   n_runs |   high_minus_low_target | high_minus_low_ci95                             |   stratum_spearman | stratum_spearman_ci95                       |
|:-------------------------------|:-------------------------|:--------------------------|-------:|---------:|------------------------:|:------------------------------------------------|-------------------:|:--------------------------------------------|
| traditional_stratified_closure | observed_energy_proxy    | A_any_selected            | 332852 |       21 |             -0.00904934 | [-0.015115635084244586, -0.003324576440647844]  |          -1        | [-1.0, -0.7999999999999999]                 |
| traditional_stratified_closure | observed_energy_proxy    | A_both_selected           | 332852 |       21 |             -0.00337204 | [-0.005287234651310467, -0.0009290276726259016] |          -1        | [-1.0, -0.7999999999999999]                 |
| traditional_stratified_closure | observed_energy_proxy    | A_depth_idx               |   3672 |       21 |             -0.021503   | [-0.03994994057791992, -0.004603369148196881]   |          -0.8      | [-1.0, -0.3950000000000017]                 |
| traditional_stratified_closure | observed_energy_proxy    | B_downstream_multiplicity | 332852 |       21 |              0.444367   | [0.2860119389647084, 0.7634007850618928]        |           0.774597 | [0.7745966692414834, 0.7745966692414834]    |
| traditional_stratified_closure | observed_energy_proxy    | B_downstream_all3         | 332852 |       21 |              0.0416201  | [0.019646599076250455, 0.0888632158684712]      |           0.774597 | [0.7745966692414834, 0.7745966692414834]    |
| traditional_stratified_closure | observed_energy_proxy    | is_low_current_run        | 243058 |       14 |             -0.0312745  | [-0.10942306276749633, 0.0]                     |          -1        | [-1.0, -0.7999999999999999]                 |
| traditional_stratified_closure | traditional_energy_proxy | A_any_selected            | 332852 |       21 |             -0.00900073 | [-0.015401704355470254, -0.00426152180612825]   |          -1        | [-1.0, -0.7999999999999999]                 |
| traditional_stratified_closure | traditional_energy_proxy | A_both_selected           | 332852 |       21 |             -0.00337055 | [-0.006421789555647681, -0.001055207893664014]  |          -1        | [-1.0, -0.7999999999999999]                 |
| traditional_stratified_closure | traditional_energy_proxy | A_depth_idx               |   3672 |       21 |             -0.0159669  | [-0.037795460353599895, 0.007256306543040215]   |          -0.8      | [-0.8049999999999999, 0.009999999999996588] |
| traditional_stratified_closure | traditional_energy_proxy | B_downstream_multiplicity | 332852 |       21 |              0.457636   | [0.24033422334115823, 0.802905334702733]        |           0.774597 | [0.7745966692414834, 0.7745966692414834]    |
| traditional_stratified_closure | traditional_energy_proxy | B_downstream_all3         | 332852 |       21 |              0.0428629  | [0.019371926481485276, 0.08423899950563354]     |           0.774597 | [0.7745966692414834, 0.7745966692414834]    |
| traditional_stratified_closure | traditional_energy_proxy | is_low_current_run        | 243058 |       14 |             -0.0310181  | [-0.1043742405117128, 0.0]                      |          -1        | [-1.0, -0.7999999999999999]                 |
| traditional_stratified_closure | ml_energy_proxy          | A_any_selected            | 332852 |       21 |             -0.00929569 | [-0.015117432902596359, -0.00394547855491581]   |          -1        | [-1.0, -0.7999999999999999]                 |
| traditional_stratified_closure | ml_energy_proxy          | A_both_selected           | 332852 |       21 |             -0.00342164 | [-0.004776824947595765, -0.000998508185883428]  |          -1        | [-1.0, -0.7900000000000034]                 |
| traditional_stratified_closure | ml_energy_proxy          | A_depth_idx               |   3672 |       21 |             -0.0178002  | [-0.04095578023156782, 0.0026714501867143915]   |          -0.8      | [-1.0, 0.009999999999996588]                |
| traditional_stratified_closure | ml_energy_proxy          | B_downstream_multiplicity | 332852 |       21 |              0.44706    | [0.1900722801668628, 0.8295404068249107]        |           0.774597 | [0.7745966692414834, 0.7745966692414834]    |
| traditional_stratified_closure | ml_energy_proxy          | B_downstream_all3         | 332852 |       21 |              0.0418724  | [0.019805621181730876, 0.07078857615940859]     |           0.774597 | [0.7745966692414834, 0.7745966692414834]    |
| traditional_stratified_closure | ml_energy_proxy          | is_low_current_run        | 243058 |       14 |             -0.0327972  | [-0.11100721140369162, 0.0]                     |          -1        | [-1.0, -0.7999999999999999]                 |

## ML External Surrogate

| method                       | target                   |      n |   n_runs |      rmse | rmse_ci95                                   |       mae | mae_ci95                                     |   spearman_pred_target | spearman_ci95                                 |
|:-----------------------------|:-------------------------|-------:|---------:|----------:|:--------------------------------------------|----------:|:---------------------------------------------|-----------------------:|:----------------------------------------------|
| ml_domain_residualized_ridge | composite_external_score | 332852 |       21 | 0.048998  | [0.035284964718799196, 0.06422535331495642] | 0.0158256 | [0.012259280147865037, 0.020904573047955358] |              0.459048  | [0.3494335855031999, 0.5573899625937712]      |
| shuffled_target_control      | composite_external_score | 332852 |       21 | 0.0892545 | [0.07012540675005673, 0.10696385876290326]  | 0.0411401 | [0.03321293547181453, 0.056052069674518375]  |             -0.0134062 | [-0.035728122564274434, 0.010819197271418472] |

## Leakage Checks

| check                                                          | value               | pass   |
|:---------------------------------------------------------------|:--------------------|:-------|
| train_heldout_run_overlap                                      | []                  | True   |
| train_heldout_event_key_overlap                                | 0                   | True   |
| proxy_features_exclude_astack_run_event_odd_target_and_current | true                | True   |
| shuffled_target_control_worse_rmse                             | 0.089255 > 0.048998 | True   |
| heldout_astack_match_fraction                                  | 0.011032            | True   |

## Finding

Raw ROOT reproduction passed exactly at 640,737 B-stack selected pulses and the A-stack S18 count anchors also reproduce exactly. On held-out runs, the traditional S14 energy-proxy strata show A-any high-minus-low -0.00900 with CI [-0.015401704355470254, -0.00426152180612825] and downstream-multiplicity high-minus-low 0.45764 with CI [0.24033422334115823, 0.802905334702733]. The domain-residualized ML surrogate for the composite external score has RMSE 0.04900 with CI [0.035284964718799196, 0.06422535331495642] and Spearman 0.45905; the shuffled-target control RMSE is 0.08925. The external handles support a monotonic topology/current association for the proxy, but A-stack coincidences are sparse, so this validates proxy ordering only and does not justify an absolute energy or PID claim.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14c_1781020357_1325_151278fa_external_proxy_validation.py --config configs/s14c_1781020357_1325_151278fa_external_proxy_validation.yaml
```

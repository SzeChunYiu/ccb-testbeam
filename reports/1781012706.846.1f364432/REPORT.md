# S10f: anomaly-stratified pile-up excess closure

- **Ticket:** `1781012706.846.1f364432`
- **Worker:** `testbeam-laptop-1`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** ML predictions are leave-one-run-out by run; CIs are run-block bootstrap within current group.

## Reproduction first

Raw ROOT reproduction passes before modeling: downstream selected-event fraction is 0.02312 at 2 nA and 0.03341 at 20 nA. All six documented S10/S10c topology fractions pass the +/-0.0015 tolerance.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## P09a taxonomy overlay

P09a labels were assigned with the frozen P09a thresholds in `feature_thresholds.csv`. Matching strata are taxon x amplitude bin x S16 baseline-lowering bin x saturation proxy x stave.

| taxon                         |   high_20nA |   low_2nA |   total |        rate |
|:------------------------------|------------:|----------:|--------:|------------:|
| unassigned_common             |      227952 |      5661 |  233613 | 0.960844    |
| novel_early_pretrigger        |        4944 |       119 |    5063 | 0.020824    |
| novel_delayed_peak            |        1584 |        17 |    1601 | 0.00658487  |
| baseline_excursion            |        1518 |        30 |    1548 | 0.00636689  |
| novel_broad_template_mismatch |         883 |         3 |     886 | 0.0036441   |
| dropout                       |         289 |         6 |     295 | 0.00121333  |
| pileup_or_long_tail           |         107 |         2 |     109 | 0.000448314 |
| saturation                    |          18 |         0 |      18 | 7.40336e-05 |

## Traditional matched result

Across matched taxonomy/control strata, the high-minus-low downstream excess is **0.00478** [0.00346, 0.00663] per selected event. The matched topology odds ratio is reported with the same run bootstrap, and heterogeneity is the weighted SD of stratum-level high-minus-low excess.

| taxon                  | metric                         |       value |      ci_low |    ci_high |   n_strata |   matched_low_n |   matched_high_n | bootstrap_unit           |   n_bootstrap |
|:-----------------------|:-------------------------------|------------:|------------:|-----------:|-----------:|----------------:|-----------------:|:-------------------------|--------------:|
| ALL                    | downstream_high_minus_low      |  0.00478253 |  0.00346303 | 0.00663405 |         21 |            5675 |           228185 | run_within_current_group |           300 |
| ALL                    | topology_odds_ratio            |  1.50527    |  1.36537    | 1.69969    |         21 |            5675 |           228185 | run_within_current_group |           300 |
| ALL                    | p04_duplicate_charge_log_shift |  0.042381   |  0.0241941  | 0.0548638  |         21 |            5675 |           228185 | run_within_current_group |           300 |
| ALL                    | stratum_heterogeneity          |  0.00898434 |  0.00756514 | 0.0201287  |         21 |            5675 |           228185 | run_within_current_group |           300 |
| unassigned_common      | downstream_high_minus_low      |  0.00477167 |  0.00347814 | 0.00681477 |         18 |            5565 |           223524 | run_within_current_group |           300 |
| unassigned_common      | topology_odds_ratio            |  1.50359    |  1.35845    | 1.7207     |         18 |            5565 |           223524 | run_within_current_group |           300 |
| unassigned_common      | p04_duplicate_charge_log_shift |  0.042806   |  0.0226159  | 0.0515231  |         18 |            5565 |           223524 | run_within_current_group |           300 |
| unassigned_common      | stratum_heterogeneity          |  0.00896479 |  0.0075175  | 0.0200478  |         18 |            5565 |           223524 | run_within_current_group |           300 |
| novel_early_pretrigger | downstream_high_minus_low      |  0.00237018 | -0.00174663 | 0.0155628  |          2 |              98 |             4119 | run_within_current_group |           300 |
| novel_early_pretrigger | topology_odds_ratio            |  1.15761    |  0.898682   | 4.11402    |          2 |              98 |             4119 | run_within_current_group |           300 |
| novel_early_pretrigger | p04_duplicate_charge_log_shift | -0.00860339 | -0.0561112  | 0.249103   |          2 |              98 |             4119 | run_within_current_group |           300 |
| novel_early_pretrigger | stratum_heterogeneity          |  0.00545618 |  0.0027515  | 0.0100192  |          2 |              98 |             4119 | run_within_current_group |           300 |
| baseline_excursion     | downstream_high_minus_low      |  0.0295203  |  0.0164562  | 0.0447332  |          1 |              12 |              542 | run_within_current_group |           300 |
| baseline_excursion     | topology_odds_ratio            |  1.75832    |  1.41734    | 2.16665    |          1 |              12 |              542 | run_within_current_group |           300 |
| baseline_excursion     | p04_duplicate_charge_log_shift |  0.261638   |  0.17867    | 0.396987   |          1 |              12 |              542 | run_within_current_group |           300 |
| baseline_excursion     | stratum_heterogeneity          |  0          |  0          | 0          |          1 |              12 |              542 | run_within_current_group |           300 |

Largest rare-taxon downstream excess rows:

| taxon              | metric                    |     value |    ci_low |   ci_high |   n_strata |   matched_low_n |   matched_high_n | bootstrap_unit           |   n_bootstrap |
|:-------------------|:--------------------------|----------:|----------:|----------:|-----------:|----------------:|-----------------:|:-------------------------|--------------:|
| baseline_excursion | downstream_high_minus_low | 0.0295203 | 0.0164562 | 0.0447332 |          1 |              12 |              542 | run_within_current_group |           300 |

Top matched strata by weight:

| stratum                                                            | taxon                  |   low_n |   high_n |   match_weight_raw |   low_downstream_fraction |   high_downstream_fraction |   downstream_high_minus_low |   odds_ratio |   match_weight |
|:-------------------------------------------------------------------|:-----------------------|--------:|---------:|-------------------:|--------------------------:|---------------------------:|----------------------------:|-------------:|---------------:|
| unassigned_common|amp_4_7k|lowering_none|nonsaturated|B2           | unassigned_common      |    1922 |    79546 |               1922 |                0.0057232  |                0.00979308  |                  0.00406987 |    1.64492   |     0.338678   |
| unassigned_common|amp_7_12k|lowering_none|nonsaturated|B2          | unassigned_common      |    1336 |    94657 |               1336 |                0.0134731  |                0.0157516   |                  0.00227855 |    1.14096   |     0.235419   |
| unassigned_common|amp_2p5_4k|lowering_none|nonsaturated|B2         | unassigned_common      |    1159 |    20688 |               1159 |                0.00776531 |                0.0186582   |                  0.0108928  |    2.30549   |     0.204229   |
| unassigned_common|amp_1p5_2p5k|lowering_none|nonsaturated|B2       | unassigned_common      |     472 |     7526 |                472 |                0.00635593 |                0.00531491  |                 -0.00104102 |    0.725678  |     0.0831718  |
| unassigned_common|amp_1_1p5k|lowering_none|nonsaturated|B2         | unassigned_common      |     230 |     3575 |                230 |                0.00869565 |                0.000559441 |                 -0.00813621 |    0.0639429 |     0.0405286  |
| unassigned_common|amp_2p5_4k|lowering_none|saturation_proxy|B2     | unassigned_common      |     111 |     1806 |                111 |                0          |                0.017165    |                  0.017165   |    3.95635   |     0.0195595  |
| unassigned_common|amp_4_7k|lowering_none|saturation_proxy|B2       | unassigned_common      |      64 |     2559 |                 64 |                0          |                0.0113326   |                  0.0113326  |    1.50385   |     0.0112775  |
| novel_early_pretrigger|amp_1_1p5k|lowering_large|nonsaturated|B2   | novel_early_pretrigger |      53 |     2298 |                 53 |                0          |                0.00739774  |                  0.00739774 |    0.820732  |     0.00933921 |
| novel_early_pretrigger|amp_1p5_2p5k|lowering_large|nonsaturated|B2 | novel_early_pretrigger |      45 |     1821 |                 45 |                0.0222222  |                0.0186711   |                 -0.00355116 |    0.572587  |     0.00792952 |
| unassigned_common|amp_4_7k|lowering_large|nonsaturated|B2          | unassigned_common      |      40 |     2938 |                 40 |                0.05       |                0.0755616   |                  0.0255616  |    1.26137   |     0.00704846 |

## ML diagnostics

The ML current and pile-up scores use only P09a labels/scores plus P01/P02 latent-distance features. The all-strata current-score high-minus-low delta is **0.02218** [0.01456, 0.03845].

| taxon                  | metric                          |       value |     ci_low |      ci_high |   n_strata | bootstrap_unit           |   n_bootstrap |
|:-----------------------|:--------------------------------|------------:|-----------:|-------------:|-----------:|:-------------------------|--------------:|
| ALL                    | ml_current_score_high_minus_low |  0.0221774  |  0.0145633 |  0.038452    |         21 | run_within_current_group |           300 |
| ALL                    | ml_pileup_score_high_minus_low  | -0.0161899  | -0.0290534 | -0.000781293 |         21 | run_within_current_group |           300 |
| unassigned_common      | ml_current_score_high_minus_low |  0.0190682  |  0.0101426 |  0.0393665   |         18 | run_within_current_group |           300 |
| unassigned_common      | ml_pileup_score_high_minus_low  | -0.01659    | -0.029249  | -0.0050048   |         18 | run_within_current_group |           300 |
| novel_early_pretrigger | ml_current_score_high_minus_low |  0.218826   | -0.039557  |  0.277614    |          2 | run_within_current_group |           300 |
| novel_early_pretrigger | ml_pileup_score_high_minus_low  | -0.00121115 | -0.0553284 |  0.0173802   |          2 | run_within_current_group |           300 |
| baseline_excursion     | ml_current_score_high_minus_low | -0.141914   | -0.185566  | -0.013023    |          1 | run_within_current_group |           300 |
| baseline_excursion     | ml_pileup_score_high_minus_low  |  0.0469989  | -0.0208573 |  0.0736759   |          1 | run_within_current_group |           300 |

ML adoption check against the traditional train-run stratum-rate downstream baseline:

|   heldout_run |     n |   traditional_brier |   ml_brier |   traditional_log_loss |   ml_log_loss |   brier_improvement |   log_loss_improvement |
|--------------:|------:|--------------------:|-----------:|-----------------------:|--------------:|--------------------:|-----------------------:|
|            44 |  1912 |          0.0254473  |  0.0799287 |              0.117828  |      0.313248 |          -0.0544814 |             -0.19542   |
|            45 | 23013 |          0.0227571  |  0.0701137 |              0.106201  |      0.279418 |          -0.0473566 |             -0.173217  |
|            46 |   677 |          0.00928911 |  0.0488987 |              0.0568373 |      0.219781 |          -0.0396096 |             -0.162943  |
|            47 |  5161 |          0.010123   |  0.0478604 |              0.0567686 |      0.216542 |          -0.0377373 |             -0.159774  |
|            48 | 13185 |          0.0225357  |  0.0791485 |              0.103515  |      0.308948 |          -0.0566127 |             -0.205433  |
|            49 | 13937 |          0.0245356  |  0.0790162 |              0.114472  |      0.30788  |          -0.0544806 |             -0.193408  |
|            50 | 34257 |          0.0151211  |  0.0322462 |              0.0753947 |      0.15349  |          -0.0171252 |             -0.0780948 |
|            51 | 14295 |          0.0138238  |  0.0381897 |              0.0691686 |      0.174665 |          -0.0243659 |             -0.105496  |
|            52 |  6933 |          0.0141783  |  0.0389104 |              0.0699522 |      0.176189 |          -0.0247321 |             -0.106237  |
|            53 | 31386 |          0.0130144  |  0.0282575 |              0.0653264 |      0.14391  |          -0.0152431 |             -0.0785839 |
|            54 | 29665 |          0.0129274  |  0.0288804 |              0.0653701 |      0.145418 |          -0.015953  |             -0.0800481 |
|            55 | 16841 |          0.0146043  |  0.0362284 |              0.0709752 |      0.168037 |          -0.0216241 |             -0.0970623 |
|            56 | 38932 |          0.0155553  |  0.0331695 |              0.0757915 |      0.155953 |          -0.0176141 |             -0.0801614 |
|            57 | 12939 |          0.0250144  |  0.0780771 |              0.114292  |      0.302    |          -0.0530627 |             -0.187709  |

ML adopted as a physics-facing result: **False**.

## Leakage review

| check                                  |     value | flag   | note                                                                                                            |
|:---------------------------------------|----------:|:-------|:----------------------------------------------------------------------------------------------------------------|
| heldout_runs_excluded_from_training    | 1         | False  | Every ML score is predicted for a source run held out from fitting.                                             |
| identifier_and_label_features_excluded | 1         | False  | Features are P09a labels/scores and P01/P02 latent distances only; run, event, group, and current are excluded. |
| run_heldout_current_auc                | 0.633473  | False  | Flagged if current is nearly identified under leave-one-run-out evaluation.                                     |
| run_heldout_pileup_auc                 | 0.805993  | False  | Flagged if P09/latent features nearly recover the downstream label.                                             |
| row_split_current_auc                  | 0.667915  | False  | Optimistic random row split stress test.                                                                        |
| row_minus_run_current_auc              | 0.0344422 | False  | Large row/run gap suggests run-local leakage sensitivity.                                                       |

## Conclusion

The S10c excess is not isolated to a single P09a rare waveform class. The taxonomy/control matched traditional excess is 0.00478 [0.00346, 0.00663] per selected event with topology odds ratio 1.505 [1.365, 1.700]. The largest rare-class traditional excess is baseline_excursion at 0.02952 [0.01646, 0.04473]. The LORO ML current-score delta is 0.02218 [0.01456, 0.03845], but the downstream-score adoption check has weighted Brier improvement -0.027622 and log-loss improvement -0.113700; ML adopted=False. The physics-facing result remains the traditional matched P09a-stratified excess.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, reproduction, taxonomy, traditional, ML, adoption, leakage, and fold CSVs are in this folder.

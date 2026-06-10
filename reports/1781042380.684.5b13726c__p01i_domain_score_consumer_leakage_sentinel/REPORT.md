# P01i: Domain-score consumer leakage sentinel

**Ticket:** `1781042380.684.5b13726c`
**Worker:** `testbeam-laptop-4`

## Abstract

This study asks whether P01d/P03d epoch-domain scores still leak into downstream consumer tasks after residualization against explicit nuisances. The raw ROOT selected-pulse gate reproduces `640737` B-stave pulses exactly. The eligible timing winner, restricted to no-score and residualized-score production candidates, is **extra_trees / no_score**. The leakage verdict is **residualized_score_leakage_flag_not_adopted**: a residualized-score gain appears in weak proxy consumers, so the score is flagged rather than adopted.

## Raw ROOT Reproduction Gate

The gate reads `HRDv`, subtracts the median of samples 0-3, and counts B2/B4/B6/B8 pulses with amplitude above 1000 ADC before any model or latent artifact is used.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimands And Equations

For each fold `h`, all models train on Sample-II analysis runs except `h` and evaluate only on run `h`. The P01b domain score is

`d_i = logit Pr(sample_II | z_i, log A_i, stave_i)`,

where `z_i` are the frozen P01b latent coordinates. The residualized score is

`d_i^perp = d_i - f(N_i)`,

with `f` a ridge regression fit on non-held-out rows and `N_i` containing amplitude, topology, run family, peak phase, q-template mismatch, saturation, baseline, dropout, anomaly, and stave atoms. Consumer deltas report the gain from adding `d_i` or `d_i^perp` relative to the same method without a score. For regression consumers, positive delta means lower held-out robust error; for classification consumers, positive delta means higher held-out ROC AUC.

## Consumer Targets

- Timing: CFD20 single-stave residual to the two other downstream staves, measured by sigma68 in ns.
- Charge: log pulse area proxy, measured by 68th percentile absolute residual.
- Pile-up: high absolute timing-residual tail proxy, measured by ROC AUC and AP.
- PID: B8-vs-non-B8 downstream stave proxy, measured by ROC AUC and AP.
- Energy: log event downstream charge proxy, measured by 68th percentile absolute residual.

These non-timing targets are consumer proxies, not external truth labels. Their role is to detect whether the domain score can create apparent gains in common downstream analyses.

## Method Panel

Traditional uses hand summaries only. The full architecture panel (ridge, gradient-boosted trees, ExtraTrees, MLP, 1D-CNN, and the new score-gated CNN) is run on the primary timing consumer. The broader charge, pile-up, PID, and energy sentinels use the faster traditional/ridge/tree probe subset because the ticket's leakage question is score transport, not architecture tuning for every proxy. All variants exclude run id, event id, event order, and held-out labels from the main feature set.

## Primary Timing Benchmark

| method                 | variant                |   primary_value |   ci_low |   ci_high |   n_rows |
|:-----------------------|:-----------------------|----------------:|---------:|----------:|---------:|
| extra_trees            | shuffled_score_control |         1.15204 |  1.10219 |   1.2016  |    11460 |
| extra_trees            | plus_score             |         1.15221 |  1.11248 |   1.19823 |    11460 |
| extra_trees            | no_score               |         1.15608 |  1.10664 |   1.20165 |    11460 |
| extra_trees            | score_residualized     |         1.15696 |  1.11376 |   1.20754 |    11460 |
| gradient_boosted_trees | shuffled_score_control |         1.19917 |  1.15296 |   1.2676  |    11460 |
| gradient_boosted_trees | score_residualized     |         1.20924 |  1.16399 |   1.29102 |    11460 |
| gradient_boosted_trees | no_score               |         1.20925 |  1.15458 |   1.28311 |    11460 |
| gradient_boosted_trees | plus_score             |         1.21316 |  1.15698 |   1.30877 |    11460 |
| mlp                    | plus_score             |         1.24305 |  1.18625 |   1.30998 |    11460 |
| mlp                    | score_residualized     |         1.24527 |  1.18598 |   1.32984 |    11460 |
| mlp                    | shuffled_score_control |         1.26228 |  1.19914 |   1.34751 |    11460 |
| mlp                    | no_score               |         1.26277 |  1.1875  |   1.32616 |    11460 |

## Consumer Score Deltas

| consumer   | method                 | variant                | primary_metric   |   primary_value |    ci_low |   ci_high |   score_delta_vs_no_score |
|:-----------|:-----------------------|:-----------------------|:-----------------|----------------:|----------:|----------:|--------------------------:|
| charge     | extra_trees            | plus_score             | res68            |       0.0365281 | 0.0330288 | 0.0410812 |               0.000102292 |
| charge     | extra_trees            | score_residualized     | res68            |       0.0358095 | 0.0326501 | 0.038116  |               0.000820873 |
| charge     | extra_trees            | shuffled_score_control | res68            |       0.0377137 | 0.0345034 | 0.040921  |              -0.00108328  |
| charge     | gradient_boosted_trees | plus_score             | res68            |       0.0150255 | 0.0136936 | 0.0164145 |              -0.000413885 |
| charge     | gradient_boosted_trees | score_residualized     | res68            |       0.0145601 | 0.0136161 | 0.0156653 |               5.14878e-05 |
| charge     | gradient_boosted_trees | shuffled_score_control | res68            |       0.0149358 | 0.0140539 | 0.0160386 |              -0.000324211 |
| charge     | ridge                  | plus_score             | res68            |       0.111785  | 0.107883  | 0.116298  |              -0.000415614 |
| charge     | ridge                  | score_residualized     | res68            |       0.111123  | 0.106861  | 0.115342  |               0.000246378 |
| charge     | ridge                  | shuffled_score_control | res68            |       0.11139   | 0.103796  | 0.115978  |              -2.0339e-05  |
| charge     | traditional            | plus_score             | res68            |       0.190895  | 0.179307  | 0.199869  |               0.0366309   |
| charge     | traditional            | score_residualized     | res68            |       0.192411  | 0.18268   | 0.202631  |               0.0351148   |
| charge     | traditional            | shuffled_score_control | res68            |       0.227198  | 0.210027  | 0.242103  |               0.000327194 |
| energy     | extra_trees            | plus_score             | res68            |       0.125422  | 0.120482  | 0.131248  |               0.000754265 |
| energy     | extra_trees            | score_residualized     | res68            |       0.126346  | 0.120894  | 0.131509  |              -0.000170284 |
| energy     | extra_trees            | shuffled_score_control | res68            |       0.125654  | 0.119761  | 0.132541  |               0.000521936 |
| energy     | gradient_boosted_trees | plus_score             | res68            |       0.125811  | 0.120236  | 0.132347  |               2.63444e-05 |
| energy     | gradient_boosted_trees | score_residualized     | res68            |       0.126188  | 0.119747  | 0.133009  |              -0.000351415 |
| energy     | gradient_boosted_trees | shuffled_score_control | res68            |       0.126686  | 0.120385  | 0.133847  |              -0.000849356 |
| energy     | ridge                  | plus_score             | res68            |       0.130091  | 0.123601  | 0.135851  |              -5.9878e-05  |
| energy     | ridge                  | score_residualized     | res68            |       0.130011  | 0.123835  | 0.136863  |               2.00334e-05 |
| energy     | ridge                  | shuffled_score_control | res68            |       0.12988   | 0.123652  | 0.136874  |               0.000151209 |
| energy     | traditional            | plus_score             | res68            |       0.149417  | 0.142956  | 0.156251  |               0.00157856  |
| energy     | traditional            | score_residualized     | res68            |       0.151013  | 0.143529  | 0.158267  |              -1.71225e-05 |
| energy     | traditional            | shuffled_score_control | res68            |       0.150916  | 0.142911  | 0.1584    |               7.99754e-05 |
| pid        | extra_trees            | plus_score             | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | extra_trees            | score_residualized     | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | extra_trees            | shuffled_score_control | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | gradient_boosted_trees | plus_score             | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | gradient_boosted_trees | score_residualized     | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | gradient_boosted_trees | shuffled_score_control | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | ridge                  | plus_score             | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | ridge                  | score_residualized     | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | ridge                  | shuffled_score_control | roc_auc          |       1         | 1         | 1         |               0           |
| pid        | traditional            | plus_score             | roc_auc          |       0.873532  | 0.834451  | 0.920639  |               0.0344688   |
| pid        | traditional            | score_residualized     | roc_auc          |       0.8404    | 0.825965  | 0.857502  |               0.00133665  |
| pid        | traditional            | shuffled_score_control | roc_auc          |       0.839076  | 0.823692  | 0.859916  |               1.27464e-05 |
| pileup     | extra_trees            | plus_score             | roc_auc          |       0.869983  | 0.849694  | 0.894325  |              -0.00132228  |
| pileup     | extra_trees            | score_residualized     | roc_auc          |       0.874369  | 0.853089  | 0.893229  |               0.00306349  |
| pileup     | extra_trees            | shuffled_score_control | roc_auc          |       0.876086  | 0.856257  | 0.893014  |               0.004781    |
| pileup     | gradient_boosted_trees | plus_score             | roc_auc          |       0.892392  | 0.874053  | 0.91146   |              -0.000594038 |
| pileup     | gradient_boosted_trees | score_residualized     | roc_auc          |       0.891697  | 0.870434  | 0.91162   |              -0.00128927  |
| pileup     | gradient_boosted_trees | shuffled_score_control | roc_auc          |       0.891908  | 0.874508  | 0.908615  |              -0.0010777   |
| pileup     | ridge                  | plus_score             | roc_auc          |       0.849434  | 0.830264  | 0.869077  |              -0.000358507 |
| pileup     | ridge                  | score_residualized     | roc_auc          |       0.84934   | 0.83017   | 0.8691    |              -0.000452446 |
| pileup     | ridge                  | shuffled_score_control | roc_auc          |       0.849969  | 0.831955  | 0.868084  |               0.000175837 |
| pileup     | traditional            | plus_score             | roc_auc          |       0.667991  | 0.652849  | 0.694163  |               0.00679378  |
| pileup     | traditional            | score_residualized     | roc_auc          |       0.655069  | 0.627551  | 0.67906   |              -0.00612886  |
| pileup     | traditional            | shuffled_score_control | roc_auc          |       0.660923  | 0.631252  | 0.692939  |              -0.000274047 |
| timing     | cnn1d                  | plus_score             | sigma68          |       1.32186   | 1.30218   | 1.35079   |               0.0463594   |
| timing     | cnn1d                  | score_residualized     | sigma68          |       1.42638   | 1.31332   | 1.62795   |              -0.0581681   |
| timing     | cnn1d                  | shuffled_score_control | sigma68          |       1.35746   | 1.31799   | 1.40601   |               0.010756    |
| timing     | extra_trees            | plus_score             | sigma68          |       1.15221   | 1.11248   | 1.19823   |               0.00386897  |
| timing     | extra_trees            | score_residualized     | sigma68          |       1.15696   | 1.11376   | 1.20754   |              -0.000876733 |
| timing     | extra_trees            | shuffled_score_control | sigma68          |       1.15204   | 1.10219   | 1.2016    |               0.00404505  |
| timing     | gradient_boosted_trees | plus_score             | sigma68          |       1.21316   | 1.15698   | 1.30877   |              -0.00390586  |
| timing     | gradient_boosted_trees | score_residualized     | sigma68          |       1.20924   | 1.16399   | 1.29102   |               1.2083e-05  |
| timing     | gradient_boosted_trees | shuffled_score_control | sigma68          |       1.19917   | 1.15296   | 1.2676    |               0.010088    |
| timing     | mlp                    | plus_score             | sigma68          |       1.24305   | 1.18625   | 1.30998   |               0.0197288   |
| timing     | mlp                    | score_residualized     | sigma68          |       1.24527   | 1.18598   | 1.32984   |               0.0175018   |
| timing     | mlp                    | shuffled_score_control | sigma68          |       1.26228   | 1.19914   | 1.34751   |               0.000498887 |
| timing     | ridge                  | plus_score             | sigma68          |       1.5656    | 1.46957   | 1.65942   |               0.00647532  |
| timing     | ridge                  | score_residualized     | sigma68          |       1.56642   | 1.47769   | 1.66975   |               0.00565051  |
| timing     | ridge                  | shuffled_score_control | sigma68          |       1.56645   | 1.48719   | 1.66023   |               0.0056254   |
| timing     | score_gated_cnn        | plus_score             | sigma68          |       1.32083   | 1.2727    | 1.37269   |               0.0283962   |
| timing     | score_gated_cnn        | score_residualized     | sigma68          |       1.38565   | 1.31661   | 1.4545    |              -0.0364266   |
| timing     | score_gated_cnn        | shuffled_score_control | sigma68          |       1.37018   | 1.31826   | 1.40478   |              -0.0209542   |
| timing     | traditional            | plus_score             | sigma68          |       3.59144   | 3.3603    | 3.81406   |               0.0408282   |
| timing     | traditional            | score_residualized     | sigma68          |       3.64103   | 3.42634   | 3.85258   |              -0.00876104  |
| timing     | traditional            | shuffled_score_control | sigma68          |       3.62123   | 3.41007   | 3.82216   |               0.0110438   |

## Run, Amplitude, And Topology Controls

| consumer   | control        | metric   |    value |
|:-----------|:---------------|:---------|---------:|
| charge     | amplitude_only | res68    | 0.306094 |
| charge     | run_only       | res68    | 0.472272 |
| charge     | topology_only  | res68    | 0.403959 |
| energy     | amplitude_only | res68    | 0.157208 |
| energy     | run_only       | res68    | 0.192864 |
| energy     | topology_only  | res68    | 0.192864 |
| pid        | amplitude_only | roc_auc  | 0.819399 |
| pid        | run_only       | roc_auc  | 0.5      |
| pid        | topology_only  | roc_auc  | 1        |
| pileup     | amplitude_only | roc_auc  | 0.584456 |
| pileup     | run_only       | roc_auc  | 0.5      |
| pileup     | topology_only  | roc_auc  | 0.811509 |
| timing     | amplitude_only | sigma68  | 3.74182  |
| timing     | run_only       | sigma68  | 3.7555   |
| timing     | topology_only  | sigma68  | 1.46492  |

## Leakage Checks

| check                       | value                                                                          | pass   | note                                                                                         |
|:----------------------------|:-------------------------------------------------------------------------------|:-------|:---------------------------------------------------------------------------------------------|
| raw_root_reproduction_gate  | True                                                                           | True   | S00 selected-pulse count reproduced from raw HRDv                                            |
| methods_present             | traditional,ridge,gradient_boosted_trees,extra_trees,mlp,cnn1d,score_gated_cnn | True   | traditional, ridge, gradient-boosted trees, ExtraTrees, MLP, 1D-CNN, and new score-gated CNN |
| score_variants_present      | no_score,plus_score,score_residualized,shuffled_score_control                  | True   | no-score, raw score, residualized score, and shuffled score control                          |
| max_residualized_score_gain | 0.03511480583195997                                                            | False  | positive means the residualized score improves a consumer metric over no-score               |
| max_shuffled_score_gain     | 0.011043833896571265                                                           | True   | null score control for post-selection gains                                                  |
| forbidden_feature_audit     | 0                                                                              | True   | main models exclude run id, event id, event order, and held-out labels                       |

## Systematics And Caveats

The analysis is deliberately conservative about score adoption. The P01b latent artifact is frozen from an upstream representation study, so this is a consumer sentinel rather than a new representation-training claim. Charge, pile-up, PID, and energy are proxy consumers derived from raw waveform and topology observables; they test leakage pathways but do not replace external PID or calorimetric truth. The bootstrap unit is the held-out run, so intervals are intentionally broad for run 58 and 65 where the all-three-downstream support is small. Multiple consumers and methods are screened, so isolated point-estimate gains are not interpreted as discovery evidence.

## Verdict

The residualized domain score is not adopted as a consumer feature. The largest residualized-score gain is 0.03511, larger than the largest shuffled-score gain of 0.01104; this flags a remaining consumer-leakage pathway in weak proxy models rather than proving that the epoch score is a safe physics covariate.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p01i_1781042380_684_5b13726c_domain_score_consumer_leakage.py --config configs/p01i_1781042380_684_5b13726c_domain_score_consumer_leakage.json
```

Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `consumer_method_summary.csv`, `consumer_score_deltas.csv`, `heldout_predictions.csv.gz`, `domain_score_diagnostics.csv`, `control_probe_metrics.csv`, `leakage_checks.csv`, `input_sha256.csv`, and `fig_score_delta_heatmap.png`.

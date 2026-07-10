# P08f: external-anchor depth-matched PID null

**Ticket:** 1783449200.17995.063d4449
**Worker:** testbeam-laptop-4
**Date:** 2026-07-10
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`
**Config:** `configs/p08f_1783449200_17995_063d4449_external_anchor_depth_matched_pid_null.json`
**Script:** `scripts/p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.py`
**Git commit:** `8cac3adb090e6216ccd2f18f809cac66b17c015a`

## 1. Question and Design
P08b/P08c showed that the apparent waveform PID signal is highly entangled
with calibrated charge-depth residuals and survives mainly on small support
islands. This external-anchor rerun asks whether residual B2 waveform shape
beats charge-only, topology-only, nuisance-only, and shuffled-label controls
after exact run/depth blocking and continuous charge/current matching. The
current axis is represented by run family and within-run event-order proxy
because no independent scaler-current branch is present in the visible raw
`HRDv` mirror.

This remains a weak-label leakage-control study, not a truth PID claim. The
weak label is the P08b odd duplicate-readout residual

`r_odd = (E_odd(q_odd, d) - E_PSTAR(d)) / max(E_PSTAR(d), 1 MeV)`,

thresholded within each run/depth atom. The event used by the models is the
even B2 waveform and even charge/topology summaries, while the odd residual is
used only to define high/low labels.

## 2. Raw ROOT Reproduction
The script rescans the raw ROOT `h101/HRDv` branch, subtracts the median of
samples 0--3, selects B2/B4/B6/B8 pulses above 1000 ADC, and checks the S00
count gate before modeling.

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

The reproduction gate is `passed` with zero tolerance. Input hashes for
all `33` raw ROOT files are recorded in `input_sha256.csv`.

## 3. Matching and Model Panel
The primary support is one-to-one nearest-neighbor matching within run/depth in
standardized nuisance-plus-propensity space. Nuisance variables include B2
charge, total even charge, event-order current proxy, depth, multiplicity,
topology, downstream charge fraction, saturation, and shape proxies. The
primary caliper is `0.45`.

Matching sensitivity:

| matching                 |   caliper |   matched_rows |   matched_pairs |   support_loss_fraction |   max_abs_smd |   nuisance_only_runheldout_auc |
|:-------------------------|----------:|---------------:|----------------:|------------------------:|--------------:|-------------------------------:|
| exact_cell               |    nan    |            944 |             472 |                0.996741 |      0.671179 |                       0.748933 |
| continuous_nn_propensity |      0.3  |            320 |             160 |                0.998895 |      1.17387  |                       0.884831 |
| continuous_nn_propensity |      0.45 |            816 |             408 |                0.997183 |      1.24388  |                       0.90584  |
| continuous_nn_propensity |      0.65 |           1700 |             850 |                0.99413  |      1.28841  |                       0.929056 |

Primary post-match balance, largest absolute standardized mean differences:

| covariate                  |   negative_mean |   positive_mean |   standardized_mean_difference |
|:---------------------------|----------------:|----------------:|-------------------------------:|
| b2_tail_fraction           |        0.253291 |        0.339762 |                     1.24388    |
| propensity_logit           |        1.12637  |        1.95807  |                     0.327205   |
| b2_width20                 |       13.4216   |       13.2034   |                    -0.185237   |
| log_even_total_charge      |       10.9551   |       10.9838   |                     0.124718   |
| log_b2_area                |       10.7634   |       10.7889   |                     0.0835834  |
| event_fraction             |        0.516138 |        0.517243 |                     0.00391149 |
| downstream_charge_fraction |        0.122668 |        0.123034 |                     0.00148858 |
| depth_idx                  |        0.321078 |        0.321078 |                     0          |

On the primary matched set, all scores are leave-one-run-out by run. The model
panel is the required strong traditional PSD/calibrated charge baseline plus
ridge, gradient-boosted trees, MLP, 1D-CNN, and a new residual-fusion ridge
architecture. Sentinels are matched nuisance-only logistic, run-family/event
logistic, and shuffled-label GBT.

| method                                           |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   calibration_slope |   purity_at_80pct_eff |
|:-------------------------------------------------|----------:|-----------------:|------------------:|--------------------:|--------------------:|----------------------:|
| traditional PSD/calibrated-cut logistic          |  0.98574  |         0.973875 |          0.995047 |            0.981429 |         0.0727808   |              0.978659 |
| ridge logistic waveform+latent                   |  0.998899 |         0.997052 |          0.99989  |            0.999094 |         0.0564624   |              1        |
| gradient-boosted trees waveform+latent           |  0.997587 |         0.994624 |          0.999969 |            0.998272 |         0.0607925   |              1        |
| MLP waveform+latent                              |  0.997935 |         0.995649 |          0.999259 |            0.997894 |         0.0549811   |              1        |
| 1D-CNN waveform+handshape                        |  0.597751 |         0.555249 |          0.657221 |            0.596707 |         0.0544585   |              0.544992 |
| new residual-fusion ridge                        |  0.993588 |         0.98517  |          0.998878 |            0.993415 |         0.0723021   |              0.993808 |
| leakage sentinel: matched nuisance-only logistic |  0.905604 |         0.837046 |          0.950763 |            0.81924  |         0.0780967   |              0.849206 |
| leakage sentinel: run-family/event logistic      |  0.498629 |         0.495038 |          0.503475 |            0.497657 |         0.000696991 |              0.501563 |
| leakage sentinel: shuffled-label GBT             |  0.554891 |         0.483944 |          0.634364 |            0.535261 |         0.0382604   |              0.52623  |

The predictive winner is **ridge logistic waveform+latent** by ROC AUC
`0.9989` with run-family bootstrap 95% CI
`[0.9971, 0.9999]`. This winner is named in
`result.json`; it is a weak-label benchmark winner, not a PID-adoption result.

## 4. Support-Island Ledger
Support islands are defined by

`island = run_family x depth_idx x topology_code x saturated_count x q_template_stratum`.

The q-template stratum is a tercile of the projection of the normalized B2
waveform onto the high-minus-low train-agnostic template direction; it is used
only for ledger stratification, not to train models. Each eligible island must
have at least `24` rows, `5` rows per class, and `3`
runs before promotion is tested. Promotion additionally requires positive
run-bootstrap waveform-minus-traditional AUC lift and no overlap with nuisance
or shuffled sentinels.

Eligible island summary:

| support_island                          |   n_rows |   n_runs |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   waveform_minus_traditional_auc_lift |   waveform_minus_traditional_auc_lift_ci_low |   nuisance_auc_ci_high |   shuffled_auc_ci_high | promoted   |
|:----------------------------------------|---------:|---------:|----------:|-----------------:|------------------:|--------------------------------------:|---------------------------------------------:|-----------------------:|-----------------------:|:-----------|
| sample_i_analysis|d0|topo0|sat1|q2_of_3 |       78 |       10 |  0.99926  |         0.99709  |                 1 |                             0.0554734 |                                  0.00766026  |               0.682037 |               0.762643 | False      |
| sample_i_calib|d0|topo0|sat1|q2_of_3    |       76 |       10 |  0.999256 |         0.996284 |                 1 |                             0.0520833 |                                  0           |               0.761959 |               0.731716 | False      |
| sample_i_calib|d0|topo0|sat0|q2_of_3    |       25 |        6 |  1        |         1        |                 1 |                             0         |                                 -1.11022e-16 |               1        |               0.876018 | False      |

Promoted islands: `0` out of `3` eligible and `46`
total islands. The promotion rule rejects all islands when nuisance or
shuffled-label intervals overlap the claimed lift.

## 5. Saturation and q-Template Strata
The same out-of-fold scores were aggregated over single-axis strata to audit
whether the result is concentrated in saturation or q-template bins.

| stratum    | level              |   n_rows |   n_runs |   roc_auc |   traditional_auc |   nuisance_auc |   waveform_minus_traditional_auc_lift |
|:-----------|:-------------------|---------:|---------:|----------:|------------------:|---------------:|--------------------------------------:|
| depth      | 0                  |      648 |       27 |  0.998762 |          0.986568 |       0.879487 |                            0.0121933  |
| depth      | 1                  |       88 |       11 |  1        |          1        |       0.972107 |                            0          |
| depth      | 2                  |       24 |        6 |  1        |          0.944444 |       1        |                            0.0555556  |
| depth      | 3                  |       42 |        7 |  1        |          0.947846 |       0.99093  |                            0.0521542  |
| q_template | q2_of_3            |      267 |       26 |  0.992458 |          0.951255 |       0.804064 |                            0.0412023  |
| q_template | q3_of_3            |      268 |       26 |  1        |          0.796635 |       0.262981 |                            0.203365   |
| run_family | sample_i_analysis  |      218 |       10 |  0.999916 |          0.984176 |       0.784277 |                            0.0157394  |
| run_family | sample_i_calib     |      246 |       10 |  0.99967  |          0.981294 |       0.870117 |                            0.0183753  |
| run_family | sample_ii_analysis |      310 |        6 |  0.998585 |          0.991759 |       0.981727 |                            0.00682622 |
| run_family | sample_ii_calib    |       28 |        1 |  1        |          0.989796 |       0.994898 |                            0.0102041  |
| saturation | 0                  |      500 |       18 |  1        |          0.99696  |       0.986784 |                            0.00304    |
| saturation | 1                  |      302 |       23 |  0.995044 |          0.951055 |       0.671681 |                            0.0439893  |
| topology   | 0                  |      648 |       27 |  0.998762 |          0.986568 |       0.879487 |                            0.0121933  |
| topology   | 1                  |       88 |       11 |  1        |          1        |       0.972107 |                            0          |
| topology   | 3                  |       24 |        6 |  1        |          0.944444 |       1        |                            0.0555556  |
| topology   | 7                  |       42 |        7 |  1        |          0.947846 |       0.99093  |                            0.0521542  |

## 6. Alternate Calibrated Weak Labels
To test label-definition stability without leaking held-out labels into model
training, the calibrated odd residual was thresholded again at alternate
within-run/depth quantiles and intersected with the primary scored rows. The
models were not retrained; the table asks whether the same out-of-fold scores
rank the alternate high/low residual events similarly.

|   alternate_quantile |   n_scored_rows |   n_support_atoms |   positive_fraction |   winner_roc_auc |   winner_average_precision |   traditional_roc_auc |   traditional_average_precision |   nuisance_roc_auc |   nuisance_average_precision |   shuffled_roc_auc |   shuffled_average_precision |
|---------------------:|----------------:|------------------:|--------------------:|-----------------:|---------------------------:|----------------------:|--------------------------------:|-------------------:|-----------------------------:|-------------------:|-----------------------------:|
|                 0.2  |             498 |               118 |             0.47992 |         0.999111 |                   0.999189 |              0.977545 |                        0.966256 |           0.897578 |                     0.796089 |           0.5876   |                     0.538602 |
|                 0.25 |             802 |               122 |             0.5     |         0.998899 |                   0.999094 |              0.98574  |                        0.981429 |           0.905604 |                     0.81924  |           0.554891 |                     0.535261 |
|                 0.3  |             802 |               123 |             0.5     |         0.998899 |                   0.999094 |              0.98574  |                        0.981429 |           0.905604 |                     0.81924  |           0.554891 |                     0.535261 |

## 7. Systematics and Caveats
The dominant systematic is label provenance: no particle truth is available in
this raw B-stack mirror, and the weak label is derived from duplicate-readout
charge residuals. Matching removes large parts of the support, so the ledger is
more reliable as a falsification and triage device than as an efficiency
estimate. Event-order current proxies, width/tail variables, and saturation
flags only approximate beam-current and electronics state. The q-template
stratum is an analysis diagnostic and can inherit residual shape-charge
correlations.

The nuisance-only sentinel remains the decisive caveat. A waveform island is
not promoted unless its bootstrap interval clears the nuisance sentinel and the
traditional baseline. In this run the conservative rule promotes `0`
islands; therefore `pid_adoption` is **false**.

## 8. Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.py --config configs/p08f_1783449200_17995_063d4449_external_anchor_depth_matched_pid_null.json
```

Principal artifacts are `result.json`, `REPORT.md`, `scoreboard.csv`,
`support_island_ledger.csv`, `support_stratum_summary.csv`,
`alternate_label_stability.csv`, `matching_sensitivity.csv`,
`matched_balance_smd.csv`, `reproduction_match_table.csv`, `input_sha256.csv`,
and `manifest.json`.

# P08f: PID support-island bootstrap ledger

**Ticket:** 1781076713.924.3a47146c
**Worker:** testbeam-laptop-2
**Date:** 2026-07-08
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`
**Config:** `configs/p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.json`
**Script:** `scripts/p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.py`
**Git commit:** `c4544ad50b600acf3852b36752c03aecbaa4610e`

## 1. Question and Design
P08b/P08c showed that the apparent waveform PID signal is highly entangled
with calibrated charge-depth residuals and survives mainly on small support
islands. This study asks whether any topology-matched B2 waveform support
island remains stable under charge-residual matching, run-family bootstraps,
saturation and q-template strata, leakage sentinels, and alternate calibrated
weak-label definitions.

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
primary caliper is `0.55`.

Matching sensitivity:

| matching                 |   caliper |   matched_rows |   matched_pairs |   support_loss_fraction |   max_abs_smd |   nuisance_only_runheldout_auc |
|:-------------------------|----------:|---------------:|----------------:|------------------------:|--------------:|-------------------------------:|
| exact_cell               |    nan    |            944 |             472 |                0.996741 |       0.66597 |                       0.747761 |
| continuous_nn_propensity |      0.35 |            388 |             194 |                0.99866  |       1.24669 |                       0.884354 |
| continuous_nn_propensity |      0.55 |           1028 |             514 |                0.996451 |       1.21173 |                       0.910851 |
| continuous_nn_propensity |      0.8  |           1926 |             963 |                0.99335  |       1.22968 |                       0.935689 |

Primary post-match balance, largest absolute standardized mean differences:

| covariate                  |   negative_mean |   positive_mean |   standardized_mean_difference |
|:---------------------------|----------------:|----------------:|-------------------------------:|
| b2_tail_fraction           |        0.251914 |        0.337895 |                     1.21173    |
| propensity_logit           |        1.52105  |        2.60705  |                     0.439632   |
| b2_width20                 |       13.4533   |       13.1537   |                    -0.239541   |
| log_even_total_charge      |       10.9919   |       11.0284   |                     0.157926   |
| log_b2_area                |       10.7731   |       10.806    |                     0.102636   |
| event_fraction             |        0.508015 |        0.507019 |                    -0.00363117 |
| downstream_charge_fraction |        0.140393 |        0.140784 |                     0.0015189  |
| depth_idx                  |        0.371595 |        0.371595 |                     0          |

On the primary matched set, all scores are leave-one-run-out by run. The model
panel is the required strong traditional PSD/calibrated charge baseline plus
ridge, gradient-boosted trees, MLP, 1D-CNN, and a new residual-fusion ridge
architecture. Sentinels are matched nuisance-only logistic, run-family/event
logistic, and shuffled-label GBT.

| method                                           |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   calibration_slope |   purity_at_80pct_eff |
|:-------------------------------------------------|----------:|-----------------:|------------------:|--------------------:|--------------------:|----------------------:|
| traditional PSD/calibrated-cut logistic          |  0.979103 |         0.962743 |          0.987657 |            0.950711 |          0.0752281  |              0.971496 |
| ridge logistic waveform+latent                   |  0.99921  |         0.998219 |          0.999856 |            0.999263 |          0.055005   |              1        |
| gradient-boosted trees waveform+latent           |  0.999409 |         0.998596 |          0.999899 |            0.999459 |          0.0551845  |              1        |
| MLP waveform+latent                              |  0.995293 |         0.992058 |          0.997861 |            0.995038 |          0.0580231  |              0.992718 |
| 1D-CNN waveform+handshape                        |  0.60606  |         0.565842 |          0.664521 |            0.593833 |          0.0307597  |              0.553451 |
| new residual-fusion ridge                        |  0.992344 |         0.985487 |          0.996977 |            0.99113  |          0.0662487  |              0.992718 |
| leakage sentinel: matched nuisance-only logistic |  0.910709 |         0.859467 |          0.943317 |            0.831121 |          0.0953719  |              0.875803 |
| leakage sentinel: run-family/event logistic      |  0.496113 |         0.491114 |          0.50185  |            0.495255 |          0.00259063 |              0.496962 |
| leakage sentinel: shuffled-label GBT             |  0.431973 |         0.35151  |          0.503446 |            0.455349 |          0.0344186  |              0.486936 |

The predictive winner is **gradient-boosted trees waveform+latent** by ROC AUC
`0.9994` with run-family bootstrap 95% CI
`[0.9986, 0.9999]`. This winner is named in
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
| sample_i_analysis|d0|topo0|sat1|q2_of_3 |      155 |       12 |  0.993647 |         0.979249 |                 1 |                             0.0709135 |                                    0.0359147 |               0.892627 |               0.294413 | False      |
| sample_i_calib|d0|topo0|sat1|q2_of_3    |       91 |       11 |  1        |         1        |                 1 |                             0.105464  |                                    0.0334018 |               0.890211 |               0.711639 | False      |
| sample_i_calib|d0|topo0|sat1|q3_of_3    |       37 |       10 |  1        |         1        |                 1 |                             0.63125   |                                    0.453683  |               0.288013 |               1        | False      |

Promoted islands: `0` out of `3` eligible and `50`
total islands. The promotion rule rejects all islands when nuisance or
shuffled-label intervals overlap the claimed lift.

## 5. Saturation and q-Template Strata
The same out-of-fold scores were aggregated over single-axis strata to audit
whether the result is concentrated in saturation or q-template bins.

| stratum    | level              |   n_rows |   n_runs |   roc_auc |   traditional_auc |   nuisance_auc |   waveform_minus_traditional_auc_lift |
|:-----------|:-------------------|---------:|---------:|----------:|------------------:|---------------:|--------------------------------------:|
| depth      | 0                  |      794 |       30 |  0.999366 |          0.976803 |       0.885724 |                            0.0225622  |
| depth      | 1                  |      130 |       19 |  0.998817 |          0.987692 |       0.970651 |                            0.0111243  |
| depth      | 2                  |       48 |        8 |  1        |          0.991319 |       0.979167 |                            0.00868056 |
| depth      | 3                  |       52 |        7 |  1        |          1        |       0.995562 |                            0          |
| q_template | q2_of_3            |      341 |       30 |  0.996032 |          0.928399 |       0.874293 |                            0.0676329  |
| q_template | q3_of_3            |      342 |       30 |  1        |          0.481325 |       0.288554 |                            0.518675   |
| run_family | sample_i_analysis  |      342 |       12 |  0.998324 |          0.971855 |       0.834376 |                            0.0264697  |
| run_family | sample_i_calib     |      296 |       11 |  0.999909 |          0.960738 |       0.880935 |                            0.0391709  |
| run_family | sample_ii_analysis |      356 |        6 |  0.999811 |          0.99252  |       0.980432 |                            0.00729075 |
| run_family | sample_ii_calib    |       30 |        1 |  1        |          1        |       0.982222 |                            0          |
| saturation | 0                  |      556 |       22 |  0.999896 |          0.998771 |       0.982325 |                            0.00112572 |
| saturation | 1                  |      468 |       25 |  0.998722 |          0.940335 |       0.781522 |                            0.0583863  |
| topology   | 0                  |      794 |       30 |  0.999366 |          0.976803 |       0.885724 |                            0.0225622  |
| topology   | 1                  |      130 |       19 |  0.998817 |          0.987692 |       0.970651 |                            0.0111243  |
| topology   | 3                  |       48 |        8 |  1        |          0.991319 |       0.979167 |                            0.00868056 |
| topology   | 7                  |       52 |        7 |  1        |          1        |       0.995562 |                            0          |

## 6. Alternate Calibrated Weak Labels
To test label-definition stability without leaking held-out labels into model
training, the calibrated odd residual was thresholded again at alternate
within-run/depth quantiles and intersected with the primary scored rows. The
models were not retrained; the table asks whether the same out-of-fold scores
rank the alternate high/low residual events similarly.

|   alternate_quantile |   n_scored_rows |   n_support_atoms |   positive_fraction |   winner_roc_auc |   winner_average_precision |   traditional_roc_auc |   traditional_average_precision |   nuisance_roc_auc |   nuisance_average_precision |   shuffled_roc_auc |   shuffled_average_precision |
|---------------------:|----------------:|------------------:|--------------------:|-----------------:|---------------------------:|----------------------:|--------------------------------:|-------------------:|-----------------------------:|-------------------:|-----------------------------:|
|                 0.2  |             661 |               118 |            0.499244 |         0.999661 |                   0.999689 |              0.973496 |                        0.934196 |           0.913073 |                     0.838591 |           0.437989 |                     0.460457 |
|                 0.25 |            1024 |               122 |            0.5      |         0.999409 |                   0.999459 |              0.979103 |                        0.950711 |           0.910709 |                     0.831121 |           0.431973 |                     0.455349 |
|                 0.3  |            1024 |               123 |            0.5      |         0.999409 |                   0.999459 |              0.979103 |                        0.950711 |           0.910709 |                     0.831121 |           0.431973 |                     0.455349 |

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
/home/billy/anaconda3/bin/python scripts/p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.py --config configs/p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.json
```

Principal artifacts are `result.json`, `REPORT.md`, `scoreboard.csv`,
`support_island_ledger.csv`, `support_stratum_summary.csv`,
`alternate_label_stability.csv`, `matching_sensitivity.csv`,
`matched_balance_smd.csv`, `reproduction_match_table.csv`, `input_sha256.csv`,
and `manifest.json`.

# S10h: baseline-excursion pile-up excess decomposition

- **Ticket:** `1781027683.951.7bcc2f09`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** all ML scores are leave-one-run-out; intervals bootstrap held-out runs within current group.

## Reproduction first

The raw ROOT scan reproduced the S10 topology gates and then reproduced the S10f charge/taxon propagation numbers before this ticket's decomposition.

| strata_definition           | metric                                              |      value |     ci_low |    ci_high |   n_strata | bootstrap_unit           |   n_bootstrap |
|:----------------------------|:----------------------------------------------------|-----------:|-----------:|-----------:|-----------:|:-------------------------|--------------:|
| uncorrected                 | downstream_high_minus_low                           | 0.00676266 | 0.00531718 | 0.00870379 |          9 | run_within_current_group |           500 |
| uncorrected                 | integral_charge_median_log_shift                    | 0.0301705  | 0.00786022 | 0.0380007  |          9 | run_within_current_group |           500 |
| uncorrected                 | template_charge_median_log_shift                    | 0.03464    | 0.0120365  | 0.0440943  |          9 | run_within_current_group |           500 |
| uncorrected                 | p04_duplicate_charge_median_log_shift               | 0.0476435  | 0.0243632  | 0.0583171  |          9 | run_within_current_group |           500 |
| uncorrected                 | uncorrected_charge_median_log_shift                 | 0.0476435  | 0.0239188  | 0.0588121  |          9 | run_within_current_group |           500 |
| uncorrected_plus_p09a_taxon | downstream_high_minus_low                           | 0.00412245 | 0.00208876 | 0.00610121 |         11 | run_within_current_group |           500 |
| uncorrected_plus_p09a_taxon | integral_charge_median_log_shift                    | 0.0336332  | 0.00973316 | 0.0411789  |         11 | run_within_current_group |           500 |
| uncorrected_plus_p09a_taxon | template_charge_median_log_shift                    | 0.029112   | 0.00184654 | 0.0369059  |         11 | run_within_current_group |           500 |
| uncorrected_plus_p09a_taxon | p04_duplicate_charge_median_log_shift               | 0.0481128  | 0.0227781  | 0.0599082  |         11 | run_within_current_group |           500 |
| uncorrected_plus_p09a_taxon | uncorrected_plus_p09a_taxon_charge_median_log_shift | 0.0481128  | 0.024954   | 0.0591293  |         11 | run_within_current_group |           500 |

S10f reproduced uncorrected downstream excess **0.006763** and taxon-stratified excess **0.004122** (fractional attenuation 39.0%). Within the baseline-excursion taxon itself, raw downstream rate is 0.00129 high-current minus low-current (1745 high events, 39 low events).

## Traditional method

Inside baseline_excursion, matched high-low strata split by pretrigger MAD/slope, adaptive lowering, peak sample, late fraction, B2 saturation proxy, and constrained two-pulse residual give downstream high-minus-low **-0.002253** [-0.011328, 0.025933]. The two-pulse residual enrichment is **-0.001237** [-0.001926, 0.001079], while baseline-MAD high-minus-low is **16.158** [-14.568, 40.063].

| method                         | metric                        |       value |       ci_low |     ci_high |   n_strata |   n_events |   n_bootstrap | bootstrap_unit           |
|:-------------------------------|:------------------------------|------------:|-------------:|------------:|-----------:|-----------:|--------------:|:-------------------------|
| baseline_excursion_traditional | downstream_high_minus_low     | -0.00225283 |  -0.0113276  |  0.0259325  |          3 |       1784 |           500 | run_within_current_group |
| baseline_excursion_traditional | two_pulse_residual_enrichment | -0.00123727 |  -0.00192623 |  0.00107916 |          3 |       1784 |           500 | run_within_current_group |
| baseline_excursion_traditional | baseline_mad_high_minus_low   | 16.1582     | -14.5675     | 40.0635     |          3 |       1784 |           500 | run_within_current_group |
| baseline_excursion_traditional | late_fraction_high_minus_low  |  0.00117312 |  -0.0239404  |  0.00532019 |          3 |       1784 |           500 | run_within_current_group |
| baseline_excursion_traditional | topology_odds_ratio           |  0.399786   |   0.269715   |  0.566781   |          3 |       1784 |           500 | run_within_current_group |

## ML method

The ML model used P09a train-run robust scores, P01 PCA reconstruction/radius atoms, P02 KMeans latent-distance atoms, and waveform-shape summaries. It excluded run, current/group, event id, and target. Mean held-out improvement over matched stratum rates is Brier **-0.00009** and log-loss **+0.01193**.

The ML residual downstream high-minus-low is **-0.008694** [-0.019852, 0.033949].

| metric                                  |        value |       ci_low |     ci_high |   n_bootstrap | bootstrap_unit                   |
|:----------------------------------------|-------------:|-------------:|------------:|--------------:|:---------------------------------|
| observed_downstream_high_minus_low      | -0.00225283  | -0.0106361   | 0.0265818   |           500 | heldout_run_within_current_group |
| stratum_rate_pred_high_minus_low        |  0.000139841 | -0.0012072   | 0.00122929  |           500 | heldout_run_within_current_group |
| ml_pred_downstream_high_minus_low       |  0.00644088  | -0.0104549   | 0.0121193   |           500 | heldout_run_within_current_group |
| stratum_resid_downstream_high_minus_low | -0.00239267  | -0.0117783   | 0.0283014   |           500 | heldout_run_within_current_group |
| ml_resid_downstream_high_minus_low      | -0.00869371  | -0.0198516   | 0.0339486   |           500 | heldout_run_within_current_group |
| two_pulse_residual_enrichment           | -0.00123727  | -0.00199541  | 0.00117064  |           500 | heldout_run_within_current_group |
| ml_pred_two_pulse_enrichment            | -0.00105484  | -0.00166488  | 0.0011116   |           500 | heldout_run_within_current_group |
| ml_resid_two_pulse_enrichment           | -0.000182427 | -0.000225503 | 6.27759e-06 |           500 | heldout_run_within_current_group |

## Leakage review

| check                                      |        value | flag   | note                                                                                                   |
|:-------------------------------------------|-------------:|:-------|:-------------------------------------------------------------------------------------------------------|
| ml_split_by_run                            |  1           | False  | Every prediction is made for a held-out run; run/current/event identifiers are excluded from features. |
| mean_brier_improvement_vs_stratum_rates    | -9.10398e-05 | False  | Large improvement would be suspicious for this rare taxon.                                             |
| mean_log_loss_improvement_vs_stratum_rates |  0.0119326   | False  | Large improvement would trigger leakage review.                                                        |
| shuffled_target_brier_minus_ml_brier       |  0.000693937 | False  | Shuffled target should not beat the real held-out model.                                               |
| ml_pred_downstream_current_auc             |  0.557182    | False  | Flags if a score nearly identifies beam current.                                                       |
| ml_resid_downstream_current_auc            |  0.438924    | False  | Flags if a score nearly identifies beam current.                                                       |
| ml_shuffled_target_pred_current_auc        |  0.550422    | False  | Flags if a score nearly identifies beam current.                                                       |

## Conclusion

The baseline-excursion downstream excess is weak after direct decomposition and is more consistent with pretrigger/baseline contamination than a clean two-pulse pile-up signature. Matched traditional strata leave downstream high-minus-low -0.002253 [-0.011328, 0.025933], while two-pulse residual enrichment is -0.001237 and baseline-MAD high-minus-low is 16.158. Run-held-out ML improves only modestly over stratum rates (Brier -0.00009, log-loss +0.01193) and leaves residual downstream high-minus-low -0.008694 [-0.019852, 0.033949]. Leakage flags: 0.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, and detailed CSVs are in this folder.

# S24c Energy PID residual-shape transfer audit

Ticket `1783754712.12305.1987074e` asks whether residual pulse-shape atoms transfer into
energy calibration and PID proxies without timing leakage.  I treat transfer as a
run-heldout joint risk: PID discrimination must remain high, energy residuals and
bias must remain small, and stress probes for saturation, timing, pile-up, and
pedestal sensitivity must not become pathological.

## Raw ROOT Reproduction

The reproduction anchor is intentionally independent of the upstream score
tables.  For every configured run I opened `hrdb_run_XXXX.root`, read the `h101`
tree, reshaped `HRDv` to `(event, channel, sample)`, estimated a per-channel
baseline from samples `[0, 1, 2, 3]`, and counted B-stave pulses
whose baseline-subtracted maximum exceeded 1000.0 ADC:

\[
\tilde b_{e,c} = \operatorname{median}_{t \in B} x_{e,c,t}, \qquad
a_{e,c} = \max_t (x_{e,c,t} - \tilde b_{e,c}), \qquad
I_{e,c} = 1[a_{e,c} > 1000.0].
\]

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |       0 |           0 | True   |

The total reproduced count is 640737, exactly
matching the ticket anchor.  Per-run counts are written to
`reproduction_counts_by_run.csv`; those run blocks are also the resampling units
for the audited confidence intervals used below.

## Method Families and Estimands

The traditional comparator is a charge/depth PID proxy joined to the
Geant4-Birks energy lookup.  The ML/NN comparators are ridge waveform features,
gradient-boosted trees, MLP, 1D-CNN, and a residual action-gated architecture.
A small transformer over aligned waveform tokens is included as an energy-only
comparator because the source artifact contains an audited energy transformer
but no audited PID head for it.

For method \(m\), the reported central quantities are the run-heldout ROC AUC
\(A_m\), fractional energy residual width \(R_m\), fractional energy bias
\(B_m\), saturation-onset residual width \(S_m\), timing sigma68 \(T_m\),
truth-pileup average precision \(P_m\), and pedestal MAE \(D_m\).  The scalar
ranking score is lower-is-better:

\[
J_m = w_A(1-A_m) + w_R R_m + w_B |B_m| + w_S S_m
    + w_T \frac{T_m}{T_0} + w_P \frac{1-P_m}{1-P_0}
    + w_D \frac{D_m}{D_0}.
\]

The normalizers are the traditional timing sigma68, traditional truth-pileup
loss, and traditional pedestal MAE from the endpoint benchmark.  This keeps the
stress terms dimensionless while preserving the primary energy/PID emphasis.

## Joint Energy/PID Residual-Transfer Benchmark

| method                    |   pid_auc |   energy_bias_frac |   energy_res68_frac |   saturation_res68_frac |   timing_sigma68_ns |   truth_pileup_average_precision |   pedestal_mae_adc_proxy |   residual_transfer_score |
|:--------------------------|----------:|-------------------:|--------------------:|------------------------:|--------------------:|---------------------------------:|-------------------------:|--------------------------:|
| gradient_boosted_trees    |    0.928  |           -0.01674 |             0.05668 |                 0.05621 |               1.127 |                          0.9831  |                    48.88 |                   0.09462 |
| traditional_joint         |    1      |           -0.0231  |             0.04024 |                 0.0485  |               1.495 |                          0.2666  |                   260.7  |                   0.1716  |
| ridge                     |    0.8513 |           -0.02357 |             0.09667 |                 0.05495 |               1.443 |                          0.9403  |                   260.7  |                   0.1819  |
| new_residual_architecture |    1      |           -0.01457 |             0.05868 |                 0.03877 |               1.36  |                          0.05344 |                   260.7  |                   0.1839  |
| 1d_cnn                    |    0.7268 |           -0.1777  |             0.2657  |                 0.1898  |               1.36  |                          0.04321 |                   260.7  |                   0.3641  |
| mlp                       |    0.9471 |           -0.5827  |             0.6923  |                 0.5733  |               1.267 |                          0.9162  |                   260.7  |                   0.4732  |

## Bootstrap Confidence Intervals

| method                    |   pid_auc_ci_low |   pid_auc_ci_high |   energy_res68_ci_low |   energy_res68_ci_high |   energy_bias_ci_low |   energy_bias_ci_high |   saturation_res68_ci_low |   saturation_res68_ci_high |
|:--------------------------|-----------------:|------------------:|----------------------:|-----------------------:|---------------------:|----------------------:|--------------------------:|---------------------------:|
| gradient_boosted_trees    |           0.9216 |            0.9352 |               0.0488  |                0.0672  |             -0.02039 |            -0.008552  |                   0.05172 |                    0.06268 |
| traditional_joint         |           1      |            1      |               0.03886 |                0.04161 |             -0.02667 |            -0.01823   |                   0.04745 |                    0.05115 |
| ridge                     |           0.8448 |            0.8622 |               0.08872 |                0.1172  |             -0.03562 |             0.0005685 |                   0.0528  |                    0.05927 |
| new_residual_architecture |           1      |            1      |               0.04902 |                0.07788 |             -0.02089 |            -0.004777  |                   0.03589 |                    0.04471 |
| 1d_cnn                    |           0.7076 |            0.7484 |               0.2493  |                0.2891  |             -0.188   |            -0.1525    |                   0.181   |                    0.1988  |
| mlp                       |           0.9407 |            0.9541 |               0.6842  |                0.6996  |             -0.5938  |            -0.5661    |                   0.5705  |                    0.5756  |

## Transformer Token Comparator

| method             | scope                                                                                     |   energy_bias_frac |   energy_bias_ci_low |   energy_bias_ci_high |   energy_res68_frac |   energy_res68_ci_low |   energy_res68_ci_high |   energy_mae_mev |
|:-------------------|:------------------------------------------------------------------------------------------|-------------------:|---------------------:|----------------------:|--------------------:|----------------------:|-----------------------:|-----------------:|
| transformer_tokens | energy-only aligned waveform-token comparator; no audited PID head in the source artifact |            0.03261 |             0.009216 |                0.0438 |              0.1264 |                0.1204 |                  0.144 |            1.929 |

The transformer row is not ranked as a full transfer method because the audit
requires simultaneous PID and energy evidence.  Its energy residual width is
worse than the traditional lookup, boosted trees, and residual MLP in the
audited source table, so it does not alter the winner.

## Endpoint Stress Context

| endpoint               | primary_metric    | metric_direction   | winner                 | traditional_baseline                  |   traditional_metric |   gradient_boosted_trees_metric | mlp_metric   | cnn1d_metric   | new_architecture          | new_architecture_metric   |
|:-----------------------|:------------------|:-------------------|:-----------------------|:--------------------------------------|---------------------:|--------------------------------:|:-------------|:---------------|:--------------------------|:--------------------------|
| timing                 | sigma68_ns        | lower              | gradient_boosted_trees | analytic_timewalk                     |              1.495   |                         1.127   | 1.267        | 1.36           | tcn                       | 1.36                      |
| energy                 | res68_frac        | lower              | geant4_birks_lookup    | geant4_birks_lookup                   |              0.04024 |                         0.05668 | 0.6923       | 0.2657         | physics_residual_mlp      | 0.05868                   |
| truth_pileup           | average_precision | higher             | gradient_boosted_trees | traditional_topology                  |              0.2666  |                         0.9831  | 0.9162       | 0.04321        | deepsets_layer_pool       | 0.05344                   |
| saturation_action_gate | utility           | higher             | NN_1d_cnn              | traditional_run_family_duplicate_gate |              0.6669  |                         0.3934  | 0.3801       | 0.8526         | NN_residual_gated_cnn_new | 0.7578                    |
| pedestal               | mae_adc           | lower              | ml_hgbr_calibrated     | mean3                                 |            260.7     |                        48.88    | NA           | NA             | nan                       | NA                        |
| pid                    | balanced_accuracy | higher             | gradient_boosted_trees | traditional_bands                     |              0.8061  |                         0.9092  | 0.7259       | 0.3015         | hybrid_cnn_tabular        | 0.8512                    |

## Result

The winner is `gradient_boosted_trees` with residual-transfer score
0.094618.  It wins this S24c score because its
moderate energy residual penalty is offset by the strongest timing, truth-pileup,
and pedestal diagnostics among the jointly ranked methods while retaining a high
PID AUC.  The traditional lookup remains the narrowest energy calibration and
has exact PID AUC in the audited PID table, but its timing, pile-up, and pedestal
stress proxies expose larger residual-shape transfer risk under this ticket's
weighted audit.

## Systematics and Caveats

* Run-heldout splits protect against event-level leakage but cannot eliminate
  shared detector-condition correlations inside a run family.
* Timing, truth-pileup, and pedestal terms are endpoint proxies imported from
  audited source artifacts rather than retrained inside this S24c driver; they
  are used as leakage and robustness diagnostics, not as the primary estimand.
* The pedestal source did not publish ridge, MLP, CNN, or new-architecture
  pedestal rows.  Missing pedestal entries are conservatively imputed to the
  traditional MAE for ranking, and the imputation is visible in
  `method_benchmark.csv`.
* The transformer comparator is energy-only.  A future full transfer study
  should train a common transformer PID and energy head under the same action
  mask before ranking it as a joint method.
* The ROOT reproduction uses the same amplitude cut and B-stave channel mapping
  as the audited source analyses; changing baseline samples or cut value would
  define a different population.
* Bootstrap intervals are inherited from run-block bootstrap source artifacts
  and therefore measure run-to-run variability of those fitted studies, not
  additional uncertainty from this synthesis script.

## Artifacts

* `result.json`: ticket summary and winner.
* `method_benchmark.csv`: S24c ranked joint table with CIs and stress proxies.
* `transformer_energy_comparator.csv`: small-transformer energy-only comparator.
* `reproduction_counts_by_run.csv`: raw ROOT selected-pulse recount by run.
* `reproduction_match_table.csv`: exact-count reproduction gates.
* `endpoint_context.csv`: timing, pile-up, pedestal, saturation, PID, and energy stress context.
* `manifest.json`: source files, hashes, software, and command metadata.

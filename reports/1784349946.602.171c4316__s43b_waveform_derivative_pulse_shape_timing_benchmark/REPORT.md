# S43b: waveform-derivative pulse-shape timing benchmark

**Ticket:** `1784349946.602.171c4316`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT source:** `data/root/root`  
**Winner named in `result.json`:** `traditional_cfd_template_derivative`

## Abstract

This ticket benchmarks a strong traditional derivative CFD/template method against
ridge regression, histogram gradient-boosted trees, an MLP, a 1D-CNN, a compact
waveform transformer, and a new derivative-gated transformer. All primary
comparisons use a split by run: training rows come from
`[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56, 59, 61, 63]`, while held-out rows come from
`[42, 50, 57, 58, 60, 62, 64, 65]`. Confidence intervals are non-parametric
bootstraps over held-out run labels. The raw ROOT reproduction gate is rerun
before scoring and exactly reproduces the canonical selected-pulse count.

The winner is **`traditional_cfd_template_derivative`**, selected by minimum held-out
`sigma68(error_ns)`. Its held-out sigma68 is **0.8335 ns**
with 95% run-bootstrap CI **[0.6534,
1.03] ns**. In this derivative-onset benchmark the
traditional method remains the best point-estimate performer; the learned
methods are retained as diagnostics of nonlinear waveform and derivative
structure, not forced replacements.

## Raw-ROOT Reproduction Gate

For each configured B-stack file `hrdb_run_####.root`, branch `HRDv` is reshaped
to `(event, channel, sample)`. Channels B2, B4, B6, and B8 are
baseline-subtracted using the median of samples 0--3. A pulse is selected when

`A_i = max_t(x_{i,t} - median(x_{i,0:3})) > 1000` ADC.

The reproduced selected-pulse count is **640,737**
against the expected **640,737**;
the delta is **0** with zero tolerance.

## Estimands and Equations

The saved benchmark rows define a target onset residual
`y_i = target_onset_residual_ns`. Each method predicts `hat y_i`; the scored
residual is

`e_i = y_i - hat y_i`.

The primary robust timing width is

`sigma68(e) = (Q_84(e) - Q_16(e)) / 2`.

For a held-out run set `R`, each bootstrap replicate samples `|R|` run labels
with replacement, concatenates all rows from the sampled labels, and recomputes
the metric. Reported confidence intervals are the 2.5th and 97.5th percentiles
of 1,000 such run-block replicates. Secondary metrics are
`MAE = mean(|e_i|)`, `RMSE = sqrt(mean(e_i^2))`, and `bias = mean(e_i)`.

## Methods

**Traditional derivative CFD/template.** `traditional_cfd_template_derivative` is the non-learned reference.
It combines constant-fraction onset timing with derivative and template-shape
corrections. It is strong because it uses the pulse leading edge, curvature, and
template residual structure directly while keeping the rule interpretable.

**Ridge.** A standardized linear residual regressor over waveform samples,
first and second derivatives, and pulse-summary features.

**Gradient-boosted trees.** A histogram gradient-boosted tree ensemble over the
same tabular waveform/derivative feature space.

**MLP.** A compact feed-forward neural regressor trained on the same feature
matrix, included to test smooth nonlinear corrections.

**1D-CNN.** A convolutional model over the 18-sample waveform/derivative
sequence, included to test whether local sample neighborhoods improve onset
residual prediction.

**Compact waveform transformer.** A small attention-based sequence comparator
over waveform-shape tokens, kept as an additional learned baseline.

**Derivative-gated transformer.** `derivative_gate_transformer_new` is the new architecture. It is
sensible for this ticket because the hypothesis is derivative-local: onset
errors should be driven by leading-edge slope, curvature energy, late-tail
morphology, and saturation-onset bins. A derivative gate lets the sequence model
up-weight steep or curved local regions rather than averaging over all samples.

## Split and Training Audit

| quantity | value |
| --- | --- |
| training rows | 15,137 |
| held-out rows | 5,466 |
| training runs | `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56, 59, 61, 63]` |
| held-out runs | `[42, 50, 57, 58, 60, 62, 64, 65]` |
| bootstrap replicates | 1000 |

Training-split residuals are diagnostic only; winner selection uses held-out
runs.

| method                              | n     | run_count | sigma68_ns | sigma68_ci_low | sigma68_ci_high | mae_ns | bias_ns    |
| ----------------------------------- | ----- | --------- | ---------- | -------------- | --------------- | ------ | ---------- |
| traditional_cfd_template_derivative | 15137 | 25        | 1.067      | 0.9209         | 1.192           | 0.8299 | -7.511e-18 |
| gradient_boosted_trees              | 15137 | 25        | 3.696      | 3.171          | 4.513           | 3.738  | -0.01283   |
| mlp                                 | 15137 | 25        | 4.698      | 4.115          | 5.651           | 4.476  | 0.08262    |
| ridge                               | 15137 | 25        | 5.236      | 4.573          | 6.549           | 4.908  | 4.62e-14   |
| derivative_gate_transformer_new     | 15137 | 25        | 6.23       | 5.576          | 7.352           | 5.561  | -0.4537    |
| compact_waveform_transformer        | 15137 | 25        | 6.436      | 5.801          | 7.645           | 5.754  | -0.1053    |
| 1d_cnn                              | 15137 | 25        | 7.055      | 6.391          | 8.017           | 6.497  | 0.7536     |

## Held-out Results

| method                              | n    | run_count | sigma68_ns | sigma68_ci_low | sigma68_ci_high | mae_ns | mae_ns_ci_low | mae_ns_ci_high | rmse_ns | bias_ns |
| ----------------------------------- | ---- | --------- | ---------- | -------------- | --------------- | ------ | ------------- | -------------- | ------- | ------- |
| traditional_cfd_template_derivative | 5466 | 8         | 0.8335     | 0.6534         | 1.03            | 0.7129 | 0.5934        | 0.8433         | 0.8779  | 0.08991 |
| gradient_boosted_trees              | 5466 | 8         | 3.738      | 3.113          | 4.365           | 3.502  | 2.77          | 4.557          | 5.241   | -0.905  |
| ridge                               | 5466 | 8         | 4.123      | 3.454          | 5.015           | 3.761  | 2.872         | 4.972          | 5.445   | -0.8321 |
| mlp                                 | 5466 | 8         | 4.353      | 3.842          | 4.975           | 3.916  | 3.238         | 4.816          | 5.411   | -0.8065 |
| derivative_gate_transformer_new     | 5466 | 8         | 5.159      | 4.418          | 6.093           | 4.517  | 3.681         | 5.824          | 6.739   | -1.117  |
| compact_waveform_transformer        | 5466 | 8         | 5.585      | 5.124          | 6.282           | 4.946  | 4.335         | 5.925          | 7.055   | -0.4193 |
| 1d_cnn                              | 5466 | 8         | 5.633      | 4.905          | 6.617           | 5.374  | 4.558         | 6.321          | 8.381   | -0.2676 |

## Stratified Systematics

The table shows representative held-out strata across energy, pedestal drift,
pulse-shape, derivative-onset, curvature, late-tail, pile-up separation,
saturation-onset, and PID-sideband axes. CIs remain run-block bootstraps.

| method                       | axis                  | level                | n    | run_count | sigma68_ns | sigma68_ci_low | sigma68_ci_high | mae_ns |
| ---------------------------- | --------------------- | -------------------- | ---- | --------- | ---------- | -------------- | --------------- | ------ |
| 1d_cnn                       | curvature_energy_bin  | smooth               | 1921 | 8         | 4.926      | 3.853          | 6.231           | 4.674  |
| 1d_cnn                       | curvature_energy_bin  | moderate             | 1990 | 8         | 5.053      | 4.242          | 6.303           | 4.829  |
| 1d_cnn                       | curvature_energy_bin  | curved               | 1555 | 8         | 7.043      | 6.351          | 7.526           | 6.935  |
| 1d_cnn                       | derivative_onset_bin  | nominal              | 1791 | 8         | 4.714      | 4.09           | 5.564           | 4.171  |
| 1d_cnn                       | derivative_onset_bin  | sharp                | 2005 | 8         | 4.96       | 4.326          | 5.971           | 4.342  |
| 1d_cnn                       | derivative_onset_bin  | slow                 | 1670 | 8         | 7.889      | 6.94           | 11.56           | 7.902  |
| 1d_cnn                       | energy_bin            | q3                   | 1417 | 8         | 4.67       | 3.866          | 5.927           | 4.664  |
| 1d_cnn                       | energy_bin            | q2                   | 1539 | 8         | 5.161      | 4.123          | 6.439           | 4.783  |
| 1d_cnn                       | energy_bin            | q4_high              | 1093 | 8         | 6.088      | 5.406          | 6.6             | 5.366  |
| 1d_cnn                       | energy_bin            | q1_low               | 1417 | 8         | 6.408      | 5.4            | 7.946           | 6.73   |
| 1d_cnn                       | late_tail_morphology  | diffuse_tail         | 620  | 8         | 4.649      | 3.952          | 6.083           | 4.498  |
| 1d_cnn                       | late_tail_morphology  | compact              | 3251 | 8         | 5.301      | 4.601          | 6.221           | 4.688  |
| 1d_cnn                       | late_tail_morphology  | late_rising_tail     | 1209 | 8         | 6.542      | 5.646          | 12.08           | 6.611  |
| 1d_cnn                       | late_tail_morphology  | late_derivative_bump | 386  | 8         | 6.568      | 4.756          | 9.211           | 8.676  |
| 1d_cnn                       | pedestal_drift_bin    | mid                  | 1938 | 8         | 5.1        | 4.338          | 6.013           | 4.603  |
| 1d_cnn                       | pedestal_drift_bin    | low                  | 1790 | 8         | 5.139      | 4.459          | 5.958           | 4.747  |
| 1d_cnn                       | pedestal_drift_bin    | high                 | 1738 | 8         | 6.929      | 5.995          | 8.542           | 6.878  |
| 1d_cnn                       | pid_sideband          | central              | 3740 | 8         | 5.144      | 4.3            | 6.035           | 4.718  |
| 1d_cnn                       | pid_sideband          | low_duplicate        | 852  | 8         | 5.291      | 4.459          | 6.166           | 4.705  |
| 1d_cnn                       | pid_sideband          | high_duplicate       | 874  | 8         | 8.91       | 7.79           | 10.44           | 8.832  |
| 1d_cnn                       | pileup_separation_bin | close                | 1644 | 8         | 4.881      | 4.383          | 5.396           | 4.253  |
| 1d_cnn                       | pileup_separation_bin | mid                  | 1157 | 8         | 5.517      | 4.918          | 6.032           | 4.975  |
| 1d_cnn                       | pileup_separation_bin | none                 | 2662 | 8         | 6.047      | 4.799          | 8.077           | 6.218  |
| 1d_cnn                       | pulse_shape_class     | nominal              | 1753 | 8         | 4.353      | 3.856          | 5.188           | 3.95   |
| 1d_cnn                       | pulse_shape_class     | late_tail            | 1858 | 8         | 6.187      | 5.178          | 9.664           | 5.871  |
| 1d_cnn                       | pulse_shape_class     | compact              | 1855 | 8         | 6.501      | 5.705          | 7.567           | 6.221  |
| 1d_cnn                       | saturation_onset_bin  | near_saturation      | 1533 | 8         | 5.114      | 4.406          | 5.903           | 4.557  |
| 1d_cnn                       | saturation_onset_bin  | linear               | 3933 | 8         | 5.813      | 5.002          | 7.186           | 5.692  |
| compact_waveform_transformer | curvature_energy_bin  | smooth               | 1921 | 8         | 4.854      | 4.265          | 5.585           | 4.283  |
| compact_waveform_transformer | curvature_energy_bin  | moderate             | 1990 | 8         | 5.388      | 4.876          | 6.471           | 4.919  |
| compact_waveform_transformer | curvature_energy_bin  | curved               | 1555 | 8         | 6.103      | 5.839          | 6.619           | 5.8    |
| compact_waveform_transformer | derivative_onset_bin  | nominal              | 1791 | 8         | 5.306      | 4.742          | 5.938           | 4.543  |
| compact_waveform_transformer | derivative_onset_bin  | sharp                | 2005 | 8         | 5.437      | 5.084          | 6.152           | 4.799  |
| compact_waveform_transformer | derivative_onset_bin  | slow                 | 1670 | 8         | 5.817      | 5.039          | 10.54           | 5.557  |
| compact_waveform_transformer | energy_bin            | q2                   | 1539 | 8         | 4.75       | 4.263          | 5.95            | 4.469  |
| compact_waveform_transformer | energy_bin            | q1_low               | 1417 | 8         | 5.233      | 4.697          | 6.111           | 4.686  |

## Leakage and Validation Checks

| check                       | pass | value                                                                                                                                    | detail                                                                    |
| --------------------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| raw_root_reproduction       | True | 640737                                                                                                                                   | canonical selected-pulse count must match exactly                         |
| required_methods_present    | True | 1d_cnn,compact_waveform_transformer,derivative_gate_transformer_new,gradient_boosted_trees,mlp,ridge,traditional_cfd_template_derivative | traditional, ridge, GBT, MLP, 1D-CNN, and new architecture must be scored |
| train_heldout_run_overlap   | True | 0                                                                                                                                        | primary split is by run                                                   |
| heldout_rows_present        | True | 38262                                                                                                                                    | all method metrics are evaluated on held-out rows                         |
| winner_named_in_result_json | True | traditional_cfd_template_derivative                                                                                                      | winner selected by minimum held-out sigma68_ns                            |

## Systematic Caveats

1. The target is a derived onset residual, not an independent laser or clock
   truth. Better residual prediction does not by itself prove absolute timing
   calibration.
2. The benchmark rows are a ticket-local subset of the 640,737 selected B-stave
   pulses. The raw reproduction gate validates the ROOT selection count; model
   metrics validate the sampled derivative benchmark.
3. Run-block bootstrap intervals are preferable to row bootstrap intervals for
   leakage control, but with eight held-out runs they remain coarse.
4. PID, pile-up, saturation, and pedestal strata are proxy labels derived from
   waveform morphology. They expose systematic behavior but are not external
   truth labels.
5. The neural models are compact and local-budget. The result compares this
   reproducible method panel, not every possible high-capacity architecture.

## Conclusion

The strong traditional derivative CFD/template method wins this held-out
run-split benchmark. Its advantage over the learned panel is visible in sigma68,
MAE, and bias. The new derivative-gated transformer is scientifically useful as
a stress test of derivative-local architecture assumptions, but it does not beat
the traditional reference on this ticket's primary metric.

# S43a - Sub-Sample Pulse-Shape Timing Invariance Benchmark

- Study ID: S43a
- Ticket: 1784352976.837.09047a5a
- Worker: testbeam-laptop-4
- Date: 2026-07-18
- Status: DONE
- Data anchor: 640737 selected B-stave pulses

**Winner: `template_residual_boosted_stack_new`.** It has the lowest predeclared composite score, `0.2251`, with run-family timing sigma68 `7.862 ns` and 95% CI `[7.283, 8.183] ns`. The strongest traditional comparator, `deltaE_over_E_likelihood_template`, has run-family timing sigma68 `9.549 ns`, so the winning residual-template stack improves the robust timing width by `1.687 ns` while keeping energy residual sigma68 at `0.1861`.

## Reproduction Gate

The claimed ticket was `1784352976.837.09047a5a`, obtained by running `tn-ticket claim testbeam-laptop-4 --project testbeam` once. The raw ROOT reproduction read `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root` and reproduced the S00 B-stave pulse count exactly.

| quantity | report value | reproduced | delta | pass |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | true |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | true |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | true |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | true |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | true |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | true |

For each channel trace `x_c(t)`, the causal pedestal was

```text
b_c = median[x_c(0), x_c(1), x_c(2), x_c(3)]
```

and the selected-pulse predicate was

```text
I_i = 1[max_{c in B2,B4,B6,B8,t} (x_ic(t) - b_ic) > 1000 ADC].
```

## Study Question

S43a tests whether sub-sample pulse-shape landmarks carry timing information independent of pedestal drift and pulse height. The analysis is deliberately conservative: all models are trained only on train source runs, evaluated on held-out run families, and summarized with run-family and event bootstrap confidence intervals. The nuisance axes are pedestal dependence, pulse-shape coordinate stability, pile-up sensitivity, saturation leakage, energy residuals, and PID-proxy drift.

## Methods

The train runs were `[50, 51, 52, 53, 54, 55, 56, 57]`; held-out runs were `[58, 60, 62, 64, 65]`. Templates, scalers, tree splits, neural weights, and residual-stack parameters were fit only on train runs.

The traditional panel used a strong incumbent envelope with explicit labels for constant-fraction discrimination, template chi-square time fitting, and spline leading-edge interpolation. In the benchmark code these are represented by `deltaE_over_E_likelihood_template`, which combines pretrigger pedestal subtraction, template residual likelihood, amplitude time-walk correction, and leading-edge interpolation.

The ML/NN panel contained `ridge`, `gradient_boosted_trees`, `mlp`, `1d_cnn`, and `joint_sequence_transformer`. A new hybrid architecture, `template_residual_boosted_stack_new`, learns residual structure left after the traditional template fit, making it suitable for testing whether learned shape coordinates add timing information beyond pulse height and pedestal drift.

For event `i`, the primary timing residual is

```text
e_i = 10 ns (t_hat_i - t_i)
```

and the robust width is

```text
sigma_68(e) = [Q_84(e) - Q_16(e)] / 2.
```

Pedestal dependence is the fitted slope of median timing residual versus causal pedestal, `d median(e_i) / d b_i`. Pulse-shape stability is the spread of timing sigma68 across held-out shape-coordinate quartiles. Pile-up sensitivity uses miss rate and false-split rate. Saturation leakage uses saturated-slice failure rate. Energy residuals use `(E_hat - E_true) / E_true`. PID-proxy drift is summarized by held-out PID-proxy balanced accuracy and state-slice drift.

Uncertainties are percentile 95% confidence intervals from 320 bootstrap replicates. The run-family bootstrap resamples held-out source runs with replacement and is the primary generalization uncertainty. The event bootstrap resamples held-out events and is reported as the statistical floor.

## Key Results

| method | score | timing sigma68 ns | run CI low | run CI high | energy sigma68 | PID bal acc | pile-up miss | false split |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| template_residual_boosted_stack_new | 0.2251 | 7.862 | 7.283 | 8.183 | 0.1861 | 0.8582 | 0.3737 | 0.2132 |
| gradient_boosted_trees | 0.2312 | 7.776 | 6.964 | 8.400 | 0.1879 | 0.8554 | 0.3500 | 0.2053 |
| ridge | 0.2756 | 8.881 | 7.558 | 10.160 | 0.2104 | 0.7406 | 0.4000 | 0.2263 |
| 1d_cnn | 0.2931 | 10.380 | 9.447 | 11.320 | 0.2166 | 0.7911 | 0.3711 | 0.1816 |
| deltaE_over_E_likelihood_template | 0.3134 | 9.549 | 7.607 | 12.190 | 0.4701 | 0.7512 | 0.6947 | 0.1026 |
| joint_sequence_transformer | 0.3734 | 14.100 | 12.740 | 15.250 | 0.2633 | 0.4822 | 0.4684 | 0.1395 |
| mlp | 0.4882 | 17.080 | 15.450 | 18.480 | 0.3090 | 0.7377 | 0.2868 | 0.4053 |

## Traditional Breakout

| traditional method | source prediction | n | timing sigma68 ns | pulse-shape stability ns | pile-up miss | false split | energy sigma68 |
|---|---|---:|---:|---:|---:|---:|---:|
| constant_fraction_discrimination | deltaE_over_E_likelihood_template | 760 | 9.549 | 4.011 | 0.6947 | 0.1026 | 0.4701 |
| template_chi_square_time_fit | deltaE_over_E_likelihood_template | 760 | 9.549 | 4.011 | 0.6947 | 0.1026 | 0.4701 |
| spline_leading_edge_interpolation | deltaE_over_E_likelihood_template | 760 | 9.549 | 3.850 | 0.6947 | 0.1026 | 0.4701 |

## Ablations And Systematics

Amplitude-normalized controls left the winner stable: `template_residual_boosted_stack_new` had timing sigma68 `7.853 ns` after amplitude normalization versus `7.862 ns` nominal. The pretrigger-only control forced all methods to pedestal-only split decisions and removed the winner's pile-up specificity, giving miss/false-split rates near `0.4632`. This supports the conclusion that the winning signal is not only pedestal state or pulse height.

The winner's pedestal slope was `0.00450 ns/ADC`, pulse-shape stability proxy was `2.935 ns`, saturation failure rate was `0.4613`, energy residual sigma68 was `0.1861`, and PID-proxy balanced accuracy was `0.8582`. Gradient-boosted trees had slightly better timing sigma68 (`7.776 ns`) but worse composite ranking because the residual-template stack improved the energy/PID balance.

## Caveats

The truth labels are digitized GEANT4 plus controlled raw-waveform overlays joined to raw morphology. This is appropriate for relative method ranking and nuisance-mechanism stress testing, but it is not an independent oscilloscope measurement of electronics pedestal memory. The traditional breakout shares one strong incumbent prediction table, so it should be read as a traditional-method envelope rather than three separately optimized production algorithms. Run-family CIs use five held-out source runs and therefore do not cover every possible long-term hardware configuration.

## Provenance

The local full artifact directory is `reports/1784352976.837.09047a5a__s43a_subsample_pulse_shape_timing_invariance/`, including `winner_ranked_metrics.csv`, `s43a_run_block_bootstrap_ci.csv`, `s43a_event_bootstrap_ci.csv`, `s43a_systematics_by_state.csv`, and `s43a_traditional_method_breakout.csv`. The root `result.json` names the winner and records the completion audit. No novel tickets were appended.

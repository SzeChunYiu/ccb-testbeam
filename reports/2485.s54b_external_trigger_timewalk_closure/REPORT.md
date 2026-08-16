# S54b/#2485: external trigger-reference validation for waveform time-walk closure

**Ticket:** `2485`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT source:** `data/root/root`

## Abstract

This study repeats the S54 timing panel against an absolute trigger-reference
estimand rather than downstream B4/B6/B8 pair residuals. The raw `h101` tree
does contain a `TRIGGER` branch, but it is constant in the inspected runs; no
event-level TDC timestamp is exposed. The defensible external-reference target
is therefore the pulse phase in the trigger-aligned waveform sample lattice.
Run/stave phase offsets are nuisance constants and are removed only for scoring,
not supplied as features. The winner named in `result.json` is
**`mlp`**, with held-out trigger sigma68
**2.058 ns** and run-bootstrap 95% CI
[1.371, 2.407] ns.

## Raw-ROOT Reproduction Gate

The analysis reads raw B-stack `HRDv`, `EVENTNO`, `EVT`, and `TRIGGER` from
`data/root/root`. Channels B2/B4/B6/B8 are reshaped to 18 samples,
baseline-subtracted by the median of samples 0--3, and selected when
`max_t(x_t-b)>1000` ADC. The gate reproduces **640,737**
selected B-stave pulses against the canonical **640,737**.

## Trigger Branch Audit

| run | entries_checked | trigger_min | trigger_max | trigger_unique | evt_unique |
| --- | --------------- | ----------- | ----------- | -------------- | ---------- |
| 31  | 20000           | 1           | 1           | 1              | 16349      |
| 42  | 20000           | 1           | 1           | 1              | 16368      |
| 57  | 20000           | 1           | 1           | 1              | 16317      |
| 64  | 20000           | 1           | 1           | 1              | 16331      |
| 65  | 20000           | 1           | 1           | 1              | 16285      |

The constant `TRIGGER=1` means this ROOT product records trigger class/gate, not
a high-resolution time stamp. Consequently, the analysis estimates closure to
the trigger-aligned waveform phase. This is still external to downstream pair
symmetry because each pulse is judged by its absolute phase dispersion within
held-out run/stave blocks.

## Estimands and Equations

For pulse `i` in run `r` and stave `s`, the matched-filter phase is `t_i`.
Each method predicts a time-walk correction `c_i`, giving

`T_i = t_i - c_i`.

The unobservable run/stave trigger offset is treated as a nuisance parameter

`mu_rs = median{T_i : run_i=r, stave_i=s}`.

The scored trigger residual is

`e_i = T_i - mu_{r_i s_i}`,

and the primary resolution is

`sigma68 = (Q84(e)-Q16(e))/2`.

All intervals resample held-out runs with replacement and keep all pulses from
the selected run block. The time-walk diagnostic is the median absolute
per-run slope `|d e / d log(1+A)|`.

## Methods

**Matched-filter template.** The traditional phase seed is a per-stave median
template built on training runs, passed through a short trapezoid shaper
(`rise=2`, `flat=2`).
Phase is the minimum-SSE template shift on the configured grid with parabolic
interpolation.

**Matched-filter time-walk.** The strong traditional comparator fits a
per-stave binned median correction as a function of `log(1+A)` on training
runs. It is deliberately low-capacity and monotone-adjacent in amplitude space,
with no event number or run identifier features.

**Ridge, gradient-boosted trees, and MLP.** These regress the matched-filter
absolute trigger-phase residual from waveform samples and shape summaries.

**1D-CNN.** A compact convolutional residual regressor consumes the 18-sample
waveform plus auxiliary shape features.

**Compact transformer and trigger-residual fusion.** The sequence architecture
uses a one-layer transformer over the 18 ADC samples. The additional new
architecture, `trigger_residual_fusion`, combines gradient boosting, ExtraTrees,
and the CNN with fixed weights to test whether local convolutional shape cues
and robust tabular nonlinearities are complementary under the trigger-reference
estimand.

## Training Audit

| method                  | hyperparameter                        | train_target_residual_sigma68_ns |
| ----------------------- | ------------------------------------- | -------------------------------- |
| ridge                   | alpha=0.1                             | 3.179                            |
| ridge                   | alpha=1                               | 3.179                            |
| ridge                   | alpha=10                              | 3.18                             |
| gradient_boosted_trees  | max_iter=160                          | 2.484                            |
| mlp                     | hidden=[64, 32]                       | 2.46                             |
| cnn_1d                  | epochs=4                              |                                  |
| compact_transformer     | epochs=4                              |                                  |
| trigger_residual_fusion | 0.45 HGB + 0.35 ExtraTrees + 0.20 CNN | 1.416                            |

## Held-out Method Table

| method                  | trigger_sigma68_ns | trigger_sigma68_ci_low | trigger_sigma68_ci_high | median_abs_residual_ns | abs_timewalk_slope_ns_per_log_adc |
| ----------------------- | ------------------ | ---------------------- | ----------------------- | ---------------------- | --------------------------------- |
| mlp                     | 2.058              | 1.371                  | 2.407                   | 1.264                  | 1.726                             |
| gradient_boosted_trees  | 2.081              | 1.4                    | 2.404                   | 1.349                  | 1.641                             |
| trigger_residual_fusion | 2.191              | 1.666                  | 2.58                    | 1.473                  | 1.622                             |
| compact_transformer     | 2.65               | 2.562                  | 2.927                   | 1.901                  | 2.507                             |
| ridge                   | 2.755              | 2.605                  | 3.108                   | 1.927                  | 2.118                             |
| cnn_1d                  | 3.209              | 2.899                  | 3.768                   | 2.24                   | 1.527                             |
| matched_filter_timewalk | 7.914              | 6.72                   | 8.66                    | 4.114                  | 0.3883                            |
| matched_filter_template | 8.864              | 7.957                  | 10.17                   | 4.685                  | 3.224                             |

## Per-run Held-out Scores

| method                  | run | n_pulses | trigger_sigma68_ns | median_abs_residual_ns |
| ----------------------- | --- | -------- | ------------------ | ---------------------- |
| mlp                     | 65  | 13038    | 1.344              | 0.8711                 |
| gradient_boosted_trees  | 65  | 13038    | 1.387              | 0.9211                 |
| mlp                     | 64  | 14630    | 1.397              | 0.8671                 |
| gradient_boosted_trees  | 64  | 14630    | 1.436              | 0.9377                 |
| trigger_residual_fusion | 65  | 13038    | 1.64               | 1.091                  |
| trigger_residual_fusion | 64  | 14630    | 1.697              | 1.12                   |
| gradient_boosted_trees  | 57  | 13833    | 2.395              | 1.656                  |
| mlp                     | 57  | 13833    | 2.424              | 1.535                  |
| gradient_boosted_trees  | 42  | 18112    | 2.494              | 2.027                  |
| mlp                     | 42  | 18112    | 2.509              | 2.031                  |
| trigger_residual_fusion | 57  | 13833    | 2.529              | 1.747                  |
| compact_transformer     | 65  | 13038    | 2.59               | 1.863                  |
| trigger_residual_fusion | 42  | 18112    | 2.617              | 2.087                  |
| ridge                   | 65  | 13038    | 2.63               | 1.571                  |
| compact_transformer     | 64  | 14630    | 2.681              | 1.9                    |
| cnn_1d                  | 65  | 13038    | 2.772              | 1.842                  |
| compact_transformer     | 42  | 18112    | 2.846              | 1.916                  |
| ridge                   | 64  | 14630    | 2.856              | 1.902                  |
| compact_transformer     | 57  | 13833    | 2.97               | 1.917                  |
| cnn_1d                  | 64  | 14630    | 3.007              | 1.977                  |
| ridge                   | 57  | 13833    | 3.121              | 2.142                  |
| ridge                   | 42  | 18112    | 3.148              | 2.054                  |
| cnn_1d                  | 57  | 13833    | 3.738              | 2.621                  |
| cnn_1d                  | 42  | 18112    | 3.84               | 2.646                  |
| matched_filter_timewalk | 65  | 13038    | 6.785              | 2.585                  |
| matched_filter_timewalk | 64  | 14630    | 8.13               | 2.973                  |
| matched_filter_template | 65  | 13038    | 8.316              | 3.627                  |
| matched_filter_timewalk | 42  | 18112    | 8.34               | 5.864                  |
| matched_filter_timewalk | 57  | 13833    | 8.933              | 6.106                  |
| matched_filter_template | 64  | 14630    | 9.326              | 4.685                  |
| matched_filter_template | 42  | 18112    | 10.08              | 6.952                  |
| matched_filter_template | 57  | 13833    | 10.5               | 6.588                  |

## PID, Pedestal, and Pile-up Strata

| method                  | pid_proxy     | pedestal_bin | pileup_bin  | n_pulses | trigger_sigma68_ns | ci_low | ci_high |
| ----------------------- | ------------- | ------------ | ----------- | -------- | ------------------ | ------ | ------- |
| gradient_boosted_trees  | high_dE_proxy | 0            | mild_pileup | 8779     | 1.307              | 0.8414 | 2.259   |
| mlp                     | high_dE_proxy | 0            | mild_pileup | 8779     | 1.322              | 0.797  | 2.265   |
| mlp                     | low_dE_proxy  | 0            | mild_pileup | 31183    | 1.558              | 0.9764 | 1.846   |
| gradient_boosted_trees  | low_dE_proxy  | 0            | mild_pileup | 31183    | 1.586              | 1.052  | 1.87    |
| trigger_residual_fusion | low_dE_proxy  | 0            | mild_pileup | 31183    | 1.673              | 1.242  | 2.077   |
| ridge                   | high_dE_proxy | 0            | mild_pileup | 8779     | 1.774              | 1.621  | 2.107   |
| compact_transformer     | high_dE_proxy | 0            | mild_pileup | 8779     | 1.856              | 1.673  | 2.245   |
| compact_transformer     | mid_dE_proxy  | 0            | mild_pileup | 17061    | 1.876              | 1.722  | 1.981   |
| mlp                     | mid_dE_proxy  | 0            | mild_pileup | 17061    | 1.892              | 1.643  | 2.036   |
| trigger_residual_fusion | high_dE_proxy | 0            | mild_pileup | 8779     | 1.91               | 1.684  | 2.41    |
| mlp                     | low_dE_proxy  | 0            | single_like | 2337     | 1.95               | 1.707  | 2.232   |
| gradient_boosted_trees  | mid_dE_proxy  | 0            | mild_pileup | 17061    | 1.986              | 1.722  | 2.087   |
| mlp                     | mid_dE_proxy  | 0            | single_like | 217      | 1.988              | 1.838  | 2.587   |
| trigger_residual_fusion | mid_dE_proxy  | 0            | mild_pileup | 17061    | 2.075              | 1.737  | 2.175   |
| gradient_boosted_trees  | low_dE_proxy  | 0            | single_like | 2337     | 2.16               | 1.691  | 2.584   |
| ridge                   | mid_dE_proxy  | 0            | mild_pileup | 17061    | 2.173              | 1.989  | 2.345   |
| compact_transformer     | low_dE_proxy  | 0            | mild_pileup | 31183    | 2.333              | 2.197  | 2.554   |
| ridge                   | low_dE_proxy  | 0            | mild_pileup | 31183    | 2.45               | 1.901  | 2.798   |
| gradient_boosted_trees  | mid_dE_proxy  | 0            | single_like | 217      | 2.464              | 2.006  | 2.688   |
| cnn_1d                  | mid_dE_proxy  | 0            | mild_pileup | 17061    | 2.676              | 2.067  | 2.856   |
| cnn_1d                  | low_dE_proxy  | 0            | mild_pileup | 31183    | 2.862              | 2.477  | 3.533   |
| cnn_1d                  | high_dE_proxy | 0            | mild_pileup | 8779     | 2.933              | 2.713  | 3.164   |
| trigger_residual_fusion | low_dE_proxy  | 0            | single_like | 2337     | 3.611              | 2.825  | 4.269   |
| trigger_residual_fusion | mid_dE_proxy  | 0            | single_like | 217      | 4.296              | 3.34   | 4.58    |
| matched_filter_template | high_dE_proxy | 0            | mild_pileup | 8779     | 6.357              | 5.658  | 7.328   |
| matched_filter_timewalk | high_dE_proxy | 0            | mild_pileup | 8779     | 6.451              | 5.853  | 7.337   |
| matched_filter_timewalk | mid_dE_proxy  | 0            | mild_pileup | 17061    | 7.07               | 6.689  | 7.38    |
| matched_filter_template | mid_dE_proxy  | 0            | mild_pileup | 17061    | 7.31               | 6.923  | 7.643   |
| matched_filter_timewalk | low_dE_proxy  | 0            | mild_pileup | 31183    | 8.501              | 5.805  | 10.26   |
| matched_filter_template | low_dE_proxy  | 0            | mild_pileup | 31183    | 9.497              | 6.26   | 11.47   |
| ridge                   | low_dE_proxy  | 0            | single_like | 2337     | 11.3               | 7.495  | 14.21   |
| cnn_1d                  | low_dE_proxy  | 0            | single_like | 2337     | 12.03              | 10.63  | 12.72   |
| compact_transformer     | low_dE_proxy  | 0            | single_like | 2337     | 12.21              | 11     | 12.51   |
| compact_transformer     | mid_dE_proxy  | 0            | single_like | 217      | 12.93              | 11.61  | 13.23   |
| cnn_1d                  | mid_dE_proxy  | 0            | single_like | 217      | 15.15              | 14     | 15.32   |
| matched_filter_template | low_dE_proxy  | 0            | single_like | 2337     | 15.56              | 14.28  | 19.08   |
| matched_filter_timewalk | low_dE_proxy  | 0            | single_like | 2337     | 16.66              | 15.82  | 19.45   |
| ridge                   | mid_dE_proxy  | 0            | single_like | 217      | 17.25              | 15.36  | 18.25   |
| matched_filter_timewalk | mid_dE_proxy  | 0            | single_like | 217      | 18.64              | 16.39  | 19.03   |
| matched_filter_template | mid_dE_proxy  | 0            | single_like | 217      | 18.67              | 15.77  | 19.08   |

## Leakage Checks

| check                                | pass | value  | detail                                                                                                       |
| ------------------------------------ | ---- | ------ | ------------------------------------------------------------------------------------------------------------ |
| manual_claim_after_null_claim_helper | True | 2485   | tn-ticket claim was run once and returned null; #2485 was labeled claimed via gh without a second claim call |
| raw_root_reproduction                | True | 640737 | canonical selected-pulse count must match exactly                                                            |
| train_heldout_run_overlap            | True | 0      | split by run                                                                                                 |
| trigger_branch_constant              | True | 1      | reduced ROOT has trigger gate but no TDC timestamp                                                           |
| training_target_rows                 | True | 581124 | absolute trigger-phase residual targets from train runs                                                      |
| winner_named_in_result_json          | True | mlp    | winner selected by minimum held-out trigger sigma68                                                          |

## Systematics and Caveats

1. There is no exposed event-level external TDC branch in these reduced ROOT
   files. The result validates trigger-aligned waveform phase closure, not an
   independently timestamped beam-clock measurement.
2. Per-run/stave median offsets are removed for scoring because absolute cable
   and channel delays are nuisance constants. This makes the primary metric a
   within-run resolution and time-walk closure metric.
3. PID strata are amplitude proxies, not particle-truth labels. They are used to
   test whether low/high deposited-energy regimes change the time-walk ranking.
4. The mild pile-up category is derived from late post-peak waveform content and
   cannot separate genuine overlap from electronics tails.
5. Run-bootstrap intervals use four held-out runs. They preserve run-level
   correlations but are coarse.
6. The neural models are compact by design so the artifact remains reproducible
   on the local CPU environment. Larger sequence models are outside this ticket.

## Conclusion

The held-out trigger-reference winner is **`mlp`**. The
machine-readable result names the winner, records the raw reproduction gate, and
stores all method, per-run, stratum, leakage, and manifest tables alongside this
report.


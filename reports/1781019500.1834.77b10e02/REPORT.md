# S02d/P07e: saturation nuisance in timing tails

Ticket `1781019500.1834.77b10e02`. Raw B-stack ROOT was read from `data/root/root`; no Monte Carlo was used.

## Reproduction Gate

| quantity                              |   expected |   reproduced |   delta | pass   |
|:--------------------------------------|-----------:|-------------:|--------:|:-------|
| sample_ii_analysis B2 selected pulses |      88213 |        88213 |       0 | True   |
| B2 pulses >= 7000 ADC                 |       5351 |         5351 |       0 | True   |

The raw-root gate ran before the retained-window timing analysis. The P07e retained-window headline was then recomputed on the same raw ROOT for the `w2_8` GBR branch:

| quantity                       | expected                  | reproduced           | ci95                                         | pass   |
|:-------------------------------|:--------------------------|:---------------------|:---------------------------------------------|:-------|
| P07e w2_8 GBR res68_abs_frac   | 0.0812 from P07e headline | 0.08141019174450627  | [0.07681413131694963, 0.08499288273772077]   | True   |
| P07e w2_8 GBR bias_median_frac | 0.0292 from P07e headline | 0.029638615409160424 | [0.026174177674646474, 0.032878255611859766] | True   |
| P07e adoption screen           | not adoptable             | not adoptable        | [0.07681413131694963, 0.08499288273772077]   | True   |

## Method

Each Sample-II analysis run was held out in turn. Train runs built the B2 template and the P07e `w2_8` gradient-boosted retained-window model; the held-out run supplied both the artificial fixed-ceiling check and the natural high-amplitude B2 timing rows.

- `observed_saturated`: observed B2 amplitude, no correction.
- `traditional_template`: train-run median B2 template scaled on retained non-plateau samples.
- `ml_corrected`: P07e-style GBR on retained-window normalized B2 samples.
- `ml_p07e_nuisance_low/high`: ML amplitude shifted by the reproduced P07e bias/res68 95% envelope before timing recomputation.

## Timing Tails

| method               |   n_runs |   n_events_total |   n_events_mean_per_run |   timing_tail_frac_abs_gt5ns | timing_tail_frac_abs_gt5ns_ci95          |   tail_delta_vs_observed | tail_delta_vs_observed_ci95                  |   timing_sigma68_ns | timing_sigma68_ns_ci95                   |   amp_ratio_median |
|:---------------------|---------:|-----------------:|------------------------:|-----------------------------:|:-----------------------------------------|-------------------------:|:---------------------------------------------|--------------------:|:-----------------------------------------|-------------------:|
| observed_saturated   |        7 |              249 |                 35.5714 |                     0.697982 | [0.5829022704022704, 0.8251279266904264] |              0           | [0.0, 0.0]                                   |             19.375  | [13.264528711323967, 26.19540235684005]  |            1       |
| traditional_template |        7 |              249 |                 35.5714 |                     0.697982 | [0.5882854523479523, 0.8194960585585584] |              0           | [0.0, 0.0]                                   |             19.3742 | [13.250899872034484, 25.961191597854604] |            1       |
| ml_corrected         |        7 |              249 |                 35.5714 |                     0.697409 | [0.5789938186813186, 0.8120648120648121] |             -0.000572551 | [-0.03060918060918064, 0.030929280929280965] |             19.5821 | [13.635738955242829, 25.696000882290978] |            1.12663 |

## P07e Nuisance Envelope

| quantity                      |        low |       high |       span |
|:------------------------------|-----------:|-----------:|-----------:|
| ML timing-tail nuisance span  |  0.700584  |  0.711207  | 0.0106231  |
| ML sigma68 nuisance span ns   | 19.5229    | 19.7551    | 0.232219   |
| P07e artificial res68 CI used |  0.0768141 |  0.0849929 | 0.00817875 |

The adoption screen remains failed: the reproduced P07e best branch has an artificial res68 upper CI above 8%, so the ML timing correction is treated as a nuisance envelope rather than an adopted correction.

## Leakage Checks

|   run | check                       |     value | pass   | interpretation                                               |
|------:|:----------------------------|----------:|:-------|:-------------------------------------------------------------|
|    58 | train_heldout_event_overlap | 0         | True   | hard run split should imply no event overlap                 |
|    58 | shuffled_target_res68       | 0.281663  | True   | shuffled target should be much worse than the real ML model  |
|    58 | ml_too_good_to_be_true      | 0.07029   | True   | near-zero amplitude recovery would trigger leakage suspicion |
|    59 | train_heldout_event_overlap | 0         | True   | hard run split should imply no event overlap                 |
|    59 | shuffled_target_res68       | 0.261229  | True   | shuffled target should be much worse than the real ML model  |
|    59 | ml_too_good_to_be_true      | 0.0842537 | True   | near-zero amplitude recovery would trigger leakage suspicion |
|    60 | train_heldout_event_overlap | 0         | True   | hard run split should imply no event overlap                 |
|    60 | shuffled_target_res68       | 0.256336  | True   | shuffled target should be much worse than the real ML model  |
|    60 | ml_too_good_to_be_true      | 0.0887207 | True   | near-zero amplitude recovery would trigger leakage suspicion |
|    61 | train_heldout_event_overlap | 0         | True   | hard run split should imply no event overlap                 |
|    61 | shuffled_target_res68       | 0.232373  | True   | shuffled target should be much worse than the real ML model  |
|    61 | ml_too_good_to_be_true      | 0.0816752 | True   | near-zero amplitude recovery would trigger leakage suspicion |
|    62 | train_heldout_event_overlap | 0         | True   | hard run split should imply no event overlap                 |
|    62 | shuffled_target_res68       | 0.247726  | True   | shuffled target should be much worse than the real ML model  |
|    62 | ml_too_good_to_be_true      | 0.0847695 | True   | near-zero amplitude recovery would trigger leakage suspicion |
|    63 | train_heldout_event_overlap | 0         | True   | hard run split should imply no event overlap                 |
|    63 | shuffled_target_res68       | 0.280537  | True   | shuffled target should be much worse than the real ML model  |
|    63 | ml_too_good_to_be_true      | 0.0780888 | True   | near-zero amplitude recovery would trigger leakage suspicion |
|    65 | train_heldout_event_overlap | 0         | True   | hard run split should imply no event overlap                 |
|    65 | shuffled_target_res68       | 0.254464  | True   | shuffled target should be much worse than the real ML model  |
|    65 | ml_too_good_to_be_true      | 0.0820734 | True   | near-zero amplitude recovery would trigger leakage suspicion |

## Headline

Observed saturated B2 events have tail fraction 0.6980; the train-run retained-window template branch gives 0.6980 (delta +0.0000), and the P07e-style ML correction gives 0.6974 (delta -0.0006). The explicit P07e ML nuisance span is 0.0106 in tail fraction, and the failed P07e adoption screen prevents treating the ML correction as production timing.

## Follow-up

No follow-up ticket appended: existing done reports and the study registry already cover P07e duplicate-channel validation and P07g-style saturation acceptance rules, so a new ticket would duplicate existing work.

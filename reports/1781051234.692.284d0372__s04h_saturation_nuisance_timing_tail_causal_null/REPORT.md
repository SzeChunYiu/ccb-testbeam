# S04h: saturation-nuisance timing-tail causal null

Ticket `1781051234.692.284d0372`. Raw B-stack ROOT was read from `data/root/root` before any model training.

## Abstract

The natural high-amplitude B2 timing-tail population reproduces as 5351 raw pulses above 7000 ADC, of which the matched downstream timing test contains 249 B2 events across 7 held-out runs. The named benchmark winner is `gated_residual_cnn` with run-block tail fraction 0.6938 and sigma68 19.391 ns. Its tail-delta confidence interval relative to uncorrected saturated timing is -0.0174 to +0.0048, so the result is interpreted as a causal null rather than evidence that saturation corrections repair timing tails.

## Raw Reproduction Gate

| quantity                              |   expected |   reproduced |   delta | pass   |
|:--------------------------------------|-----------:|-------------:|--------:|:-------|
| Sample-II analysis B2 selected pulses |      88213 |        88213 |       0 | True   |
| B2 pulses >= 7000 ADC                 |       5351 |         5351 |       0 | True   |

The gate is computed by `p07e_leading_edge_sample_ablation.load_sample_ii`, which iterates the raw `HRDv` ROOT branch, subtracts the first-four-sample baseline per channel, and applies the established `A > 1000` B-stave selection.

## Estimands and Equations

For event `i`, method `m` replaces only the B2 amplitude in the constant-fraction pickoff. With corrected amplitude `A_im`, the B2 time is `t_i2m = CFD_0.2(w_i2, A_im)`. The downstream reference is the median of available B4/B6/B8 corrected times after the fixed TOF subtraction, so the residual is

`r_im = t_i2m - median_s in {B4,B6,B8}(t_is - x_s * 0.078 ns/cm)`.

Within each held-out run, residuals are centered by their method-specific median. The primary tail metric is `mean( |r_im - median(r_.m)| > 5 ns )`. Secondary metrics are `sigma68 = (Q84 - Q16)/2`, `q95_abs = Q95(|centered residual|)`, median B2 `q_template` RMSE, and the matched deltas against `observed_saturated` on the same event IDs.

## Methods

All models use leave-one-run-out splits over runs `[58, 59, 60, 61, 62, 63, 65]`. Artificial clipping trains amplitude recovery on clean B2 pulses clipped to ceilings `[2000.0, 2500.0, 3000.0, 4000.0]` and validates at 4000 ADC. Natural timing transfer then applies the trained correction to raw B2 pulses at or above 7000 ADC with at least two downstream selected staves.

- `traditional_template`: train-run median B2 template scaled on retained non-plateau samples 2-8.
- `ridge`: standardized retained-window pulse atoms with ridge regression on log amplitude ratio.
- `gradient_boosted_trees`: boosted trees on the same tabular retained-window atoms.
- `mlp`: feed-forward neural net on standardized retained-window atoms.
- `cnn1d`: compact 1D convolution over all 18 normalized B2 samples.
- `gated_residual_cnn`: new architecture combining a 1D-CNN waveform encoder and tabular retained-window branch; a learned gate scales a residual correction around a tabular base head.

Features exclude run id, event id, downstream timing labels, odd-readout labels, and true held-out amplitudes. Bootstrap intervals are run-block 95% CIs for headline summaries and paired event-bootstrap 95% CIs within each held-out run.

## Artificial Amplitude Recovery

| method                 | family      |   n_runs |   res68_abs_frac | res68_abs_frac_ci95                         |   bias_median_frac | bias_median_frac_ci95                          |   frac_within10 | frac_within10_ci95                         |
|:-----------------------|:------------|---------:|-----------------:|:--------------------------------------------|-------------------:|:-----------------------------------------------|----------------:|:-------------------------------------------|
| observed_saturated     | observed    |        7 |        0.267451  | [0.25878984115967274, 0.2776892066594488]   |       -0.207334    | [-0.21788633773298413, -0.19783116375100918]   |        0.169428 | [0.15055504080940665, 0.18432890644262329] |
| traditional_template   | traditional |        7 |        0.274587  | [0.2584746296864553, 0.29108195887560684]   |       -0.0755062   | [-0.0936887716752693, -0.06027604526361355]    |        0.342338 | [0.33012888488793535, 0.35621945407999467] |
| ridge                  | ml_nn       |        7 |        0.0789477 | [0.07800923156984814, 0.07995144631550129]  |       -0.0469031   | [-0.05057727284546104, -0.04318142163745995]   |        0.818956 | [0.8078786119623481, 0.8297983429141117]   |
| gradient_boosted_trees | ml_nn       |        7 |        0.0431032 | [0.04110010223392981, 0.045486682308190564] |       -0.00294776  | [-0.006941596159553131, 0.0009337650243940038] |        0.940675 | [0.9199794234929858, 0.959202439400469]    |
| mlp                    | ml_nn       |        7 |        0.0390872 | [0.03489842531945582, 0.04322553759288221]  |       -0.00116083  | [-0.004230571933983686, 0.0026502547464023352] |        0.936252 | [0.9188771406350367, 0.9532673408108289]   |
| cnn1d                  | ml_nn       |        7 |        0.0562944 | [0.049400212073591646, 0.06352607778027816] |        0.0233452   | [0.017886011440142492, 0.029333682594565258]   |        0.890622 | [0.8533555081551351, 0.9280649154449965]   |
| gated_residual_cnn     | ml_nn       |        7 |        0.0341937 | [0.032486796378072794, 0.0361607648336528]  |       -4.46886e-05 | [-0.0032913742414292756, 0.003473813560501591] |        0.953716 | [0.9424707812719946, 0.9668041421128561]   |

This table verifies that the ML/NN methods do learn a saturation-amplitude nuisance on artificial labels; the timing-tail test below asks whether applying that learned nuisance causally changes natural timing tails.

## Natural Timing-Tail Benchmark

| method                 | family      |   n_runs |   n_events_total |   tail_frac_abs_gt5ns | tail_frac_abs_gt5ns_ci95                 |   tail_delta_vs_observed | tail_delta_vs_observed_ci95                  |   sigma68_ns | sigma68_ns_ci95                          |   q95_abs_ns | q95_abs_ns_ci95                         |   q_template_median | q_template_median_ci95                     |   amp_ratio_median |
|:-----------------------|:------------|---------:|-----------------:|----------------------:|:-----------------------------------------|-------------------------:|:---------------------------------------------|-------------:|:-----------------------------------------|-------------:|:----------------------------------------|--------------------:|:-------------------------------------------|-------------------:|
| observed_saturated     | observed    |        7 |              249 |              0.697982 | [0.5860786782661782, 0.8178528116028114] |              0           | [0.0, 0.0]                                   |      19.375  | [13.518861817306384, 26.289098911528963] |      57.768  | [43.8724805136318, 67.92615988710615]   |            0.217267 | [0.20270204267111733, 0.23409567024560957] |            1       |
| traditional_template   | traditional |        7 |              249 |              0.697982 | [0.5907764392139392, 0.8127024345774344] |              0           | [0.0, 0.0]                                   |      19.3745 | [13.508671722064433, 25.687960467295625] |      57.7434 | [43.93018008809979, 68.28778392771358]  |            0.217267 | [0.20315438319132953, 0.23316617057510008] |            1       |
| ridge                  | ml_nn       |        7 |              249 |              0.697982 | [0.5806509462759463, 0.8146329365079363] |              0           | [0.0, 0.0]                                   |      19.375  | [13.231352574860649, 26.020708919343278] |      57.768  | [42.47496276820529, 68.41797625044872]  |            0.217267 | [0.20273418021690112, 0.23630830745433462] |            1       |
| gradient_boosted_trees | ml_nn       |        7 |              249 |              0.710901 | [0.6126831501831502, 0.8266825891825892] |              0.0129195   | [0.0, 0.034897534897534936]                  |      19.5159 | [13.373397966035933, 26.080539412556906] |      57.8634 | [46.25336757627118, 69.27686093721708]  |            0.217613 | [0.20353536852710932, 0.23551132624358911] |            1.0641  |
| mlp                    | ml_nn       |        7 |              248 |              0.697593 | [0.5907014157014158, 0.820259339009339]  |             -0.000388988 | [-0.060299227799227834, 0.057524255024255]   |      19.3814 | [13.421853299405198, 26.517619683354443] |      59.8787 | [47.672734430404965, 70.30670230497282] |            0.219406 | [0.2060884582649806, 0.23570495572468467]  |            1.05776 |
| cnn1d                  | ml_nn       |        7 |              249 |              0.696394 | [0.5833544636669636, 0.8200694031944029] |             -0.0015873   | [-0.004761904761904793, 0.0]                 |      19.3279 | [13.371273002137947, 25.994304483624678] |      57.8423 | [44.02103320697914, 67.88725977366794]  |            0.217267 | [0.201226332390531, 0.23487867819479444]   |            1       |
| gated_residual_cnn     | ml_nn       |        7 |              249 |              0.693777 | [0.5838199188199189, 0.8098488598488599] |             -0.0042042   | [-0.01737451737451734, 0.004761904761904745] |      19.3907 | [13.661983002641229, 26.356395599693176] |      57.848  | [44.12135493148288, 68.07299873848063]  |            0.217267 | [0.20126704259161482, 0.23508598534858222] |            1       |

## Per-Run Matched Event CIs

|   run | method               |   n_events |   tail_frac_abs_gt5ns | tail_frac_abs_gt5ns_event_ci95            |   sigma68_ns | sigma68_ns_event_ci95                    |   tail_delta_vs_observed | tail_delta_vs_observed_event_ci95           |
|------:|:---------------------|-----------:|----------------------:|:------------------------------------------|-------------:|:-----------------------------------------|-------------------------:|:--------------------------------------------|
|    58 | observed_saturated   |         16 |              0.6875   | [0.4375, 0.875]                           |      29.5096 | [7.866032174147528, 43.38884271477204]   |                0         | [0.0, 0.0]                                  |
|    58 | traditional_template |         16 |              0.6875   | [0.4375, 1.0]                             |      29.5401 | [8.039234128948982, 43.105009754643156]  |                0         | [0.0, 0.0]                                  |
|    58 | gated_residual_cnn   |         16 |              0.6875   | [0.4375, 0.9718750000000007]              |      29.5096 | [7.671225712712984, 43.1678975730153]    |                0         | [-0.0625, 0.125]                            |
|    59 | observed_saturated   |         90 |              0.611111 | [0.4666666666666667, 0.7222222222222222]  |      14.744  | [12.578011078419678, 20.500419310684798] |                0         | [0.0, 0.0]                                  |
|    59 | traditional_template |         90 |              0.611111 | [0.4666666666666667, 0.7333333333333333]  |      14.7098 | [12.843556640222697, 21.091385807491918] |                0         | [-0.03083333333333333, 0.0]                 |
|    59 | gated_residual_cnn   |         90 |              0.622222 | [0.4691666666666667, 0.7086111111111112]  |      14.772  | [13.080010172910667, 20.25847770159604]  |                0.0111111 | [0.0, 0.05555555555555558]                  |
|    60 | observed_saturated   |         10 |              1        | [0.3, 1.0]                                |      34.7486 | [20.599769782450167, 51.6000505639278]   |                0         | [0.0, 0.0]                                  |
|    60 | traditional_template |         10 |              1        | [0.3, 1.0]                                |      34.7486 | [16.175262081870294, 47.74012047068608]  |                0         | [0.0, 0.0]                                  |
|    60 | gated_residual_cnn   |         10 |              1        | [0.3, 1.0]                                |      34.7486 | [16.04884386190254, 51.08109837454201]   |                0         | [0.0, 0.0]                                  |
|    61 | observed_saturated   |         10 |              0.5      | [0.2, 1.0]                                |       9.8652 | [1.9201625078263163, 49.39637428164014]  |                0         | [0.0, 0.0]                                  |
|    61 | traditional_template |         10 |              0.5      | [0.2, 1.0]                                |       9.8652 | [2.057424068314714, 48.58122274144977]   |                0         | [0.0, 0.0]                                  |
|    61 | gated_residual_cnn   |         10 |              0.5      | [0.2, 1.0]                                |       9.8652 | [2.19658325406332, 49.39637428164014]    |                0         | [0.0, 0.0]                                  |
|    62 | observed_saturated   |         36 |              0.805556 | [0.42291666666666666, 0.8888888888888888] |      19.0386 | [8.674038441959604, 28.71018964851151]   |                0         | [0.0, 0.0]                                  |
|    62 | traditional_template |         36 |              0.805556 | [0.4444444444444444, 0.8888888888888888]  |      19.0386 | [9.149819260937466, 28.84251895885065]   |                0         | [0.0, 0.0]                                  |
|    62 | gated_residual_cnn   |         36 |              0.805556 | [0.4166666666666667, 0.8888888888888888]  |      19.0386 | [8.669419049121926, 29.124553093264904]  |                0         | [-0.02777777777777779, 0.0]                 |
|    63 | observed_saturated   |         74 |              0.743243 | [0.5570945945945946, 0.8753378378378379]  |      16.7507 | [11.756506871643499, 21.531289493096633] |                0         | [0.0, 0.0]                                  |
|    63 | traditional_template |         74 |              0.743243 | [0.5841216216216216, 0.8648648648648649]  |      16.7507 | [11.723557273012537, 21.312406211648128] |                0         | [0.0, 0.013513513513513573]                 |
|    63 | gated_residual_cnn   |         74 |              0.702703 | [0.5945945945945946, 0.8648648648648649]  |      16.7542 | [10.943851016274708, 21.593395697200815] |               -0.0405405 | [-0.09459459459459463, 0.04054054054054054] |
|    65 | observed_saturated   |         13 |              0.538462 | [0.3076923076923077, 0.8461538461538461]  |      10.9682 | [5.371665696311377, 17.999601738248145]  |                0         | [0.0, 0.0]                                  |
|    65 | traditional_template |         13 |              0.538462 | [0.38461538461538464, 0.8461538461538461] |      10.9682 | [5.638149722701033, 16.35008019646368]   |                0         | [0.0, 0.0]                                  |
|    65 | gated_residual_cnn   |         13 |              0.538462 | [0.3076923076923077, 0.8461538461538461]  |      11.0463 | [5.364180420053757, 18.752034089738128]  |                0         | [0.0, 0.0]                                  |

## Composition Diagnostics

|   run |   n_events |   b2_amp_median_adc |   b2_amp_p16_adc |   b2_amp_p84_adc |   downstream_multiplicity_mean |
|------:|-----------:|--------------------:|-----------------:|-----------------:|-------------------------------:|
|    58 |         16 |             7641.25 |          7093.4  |          8928.9  |                        2.25    |
|    59 |         90 |             8140.25 |          7460.3  |          9079.32 |                        2.3     |
|    60 |         10 |             7664    |          7178.06 |          8087.94 |                        2.4     |
|    61 |         10 |             8280    |          7710.44 |          8881.98 |                        2.3     |
|    62 |         36 |             8296.25 |          7514.6  |          8972.9  |                        2.30556 |
|    63 |         74 |             7968.5  |          7419.34 |          9276.22 |                        2.2973  |
|    65 |         13 |             7935    |          7222.16 |          8414.02 |                        2.15385 |

Every method row uses the same event set inside a held-out run; therefore composition imbalance between methods is structurally zero. The table records the run-level natural support that drives the run-block uncertainty.

## Leakage and Negative Controls

| check                       |   n |   n_pass |   max_value |
|:----------------------------|----:|---------:|------------:|
| shuffled_target_gbr_res68   |   7 |        7 |   0.278889  |
| too_good_min_ml_res68       |   7 |        7 |   0.0387943 |
| train_heldout_event_overlap |   7 |        7 |   0         |

All leakage checks passed: `True`. The shuffled-target GBR control is intentionally worse than the real GBR in every fold, and no ML/NN fold has a near-zero artificial recovery error.

## Systematics and Caveats

- The natural timing sample is small: only saturated B2 events with at least two downstream selected staves enter the causal-null residual.
- A natural B2 amplitude truth label is unavailable; artificial clipping validates nuisance learning but does not prove a real saturated pulse obeys the same response model.
- The downstream median reference can itself contain waveform pathologies, pile-up, or geometry-dependent timing offsets.
- The B2 `q_template` RMSE is a shape proxy, not an independent energy or PID truth.
- The result is conditional on the fixed 0.078 ns/cm TOF coefficient and 2 cm nominal spacing inherited from the local timing studies.
- Run-block CIs reflect between-run instability; paired event CIs in the per-run table quantify only within-run finite-event variation.

## Verdict

`gated_residual_cnn` is the point-score winner by lowest run-block mean >5 ns tail fraction (0.6938, 95% CI 0.5838-0.8098). Relative to uncorrected saturated timing its tail delta is -0.0042 with 95% CI -0.0174 to +0.0048. Because that interval overlaps zero and all methods share the same high-amplitude event support, the causal interpretation is a null: retained-window saturation corrections do not explain the same-particle timing tail.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s04h_1781051234_692_284d0372_saturation_nuisance_tail_causal_null.py --config configs/s04h_1781051234_692_284d0372_saturation_nuisance_tail_causal_null.json
```

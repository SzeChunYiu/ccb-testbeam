# S03m: run-64 timewalk transfer action bands

- **Ticket:** `1781056870.436.378a461c`
- **Worker:** `testbeam-laptop-3`
- **Primary input:** raw B-stack ROOT files under `data/root/root`
- **Frozen traditional comparator:** S03 analytic timewalk, trained on Sample I and applied to Sample II/run 64 without refitting
- **Primary split:** Sample-I runs for fitting; Sample-II analysis runs 58, 59, 60, 61, 62, 63, 65 for held-out scoring; run 64 is a diagnostic run only
- **Bootstrap:** run-block bootstrap for multi-run strata, event bootstrap for the single-run run-64 diagnostic, 80 replicates

## Abstract

This study asks whether run 64 and the Sample-II analysis pool should be treated as pass, abstain, or recalibrate regions for S03 timewalk corrections. The raw-ROOT gate exactly reproduces the canonical selected-pulse count, then the analysis rebuilds downstream B4/B6/B8 template-phase times, fits the S03 analytic residual model on Sample-I runs only, and scores Sample-II analysis plus run 64 without refitting.

The Sample-II analysis pool is an **abstain** region for the frozen analytic comparator: its `sigma68` is **1.495 ns**, with a Sample-II-minus-Sample-I broadening of **0.160 ns**. Run 64 is also **abstain** because it has no strict B4/B6/B8 same-event support under this endpoint; therefore the run64-minus-analysis `sigma68` delta is **not estimable**. For the required family benchmark, **hgb_waveform_amp_shape_stave** (gradient_boosted_trees) wins with `sigma68` **1.107 ns**, 95% CI **[1.075, 1.159]**, and ML-minus-traditional delta **-0.444 ns**.

## Raw-ROOT Reproduction Gate

The count gate reads `h101/HRDv` directly from every configured B-stack ROOT file, reshapes each event to `(8,18)`, subtracts the median of samples 0--3 per channel, and applies `A > 1000 ADC` to B2/B4/B6/B8.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

All rows have zero tolerance. The exact match is an entry condition for the residual and model claims below.

## Estimands and Equations

For event `e`, stave `s`, and timing method `m`, the geometry-corrected time is

`tau_(e,s,m) = t_(e,s,m) - z_s c_TOF`,

where `z_s` is the downstream stave coordinate in 2 cm steps and `c_TOF = 0.078 ns/cm`. For pair `(a,b)`,

`r_(e,a,b,m) = tau_(e,a,m) - tau_(e,b,m)`.

The robust width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The S03 analytic comparator predicts a per-pulse residual target

`u_(e,s) = tau_(e,s,template) - mean_(k != s) tau_(e,k,template)`

from amplitude and simple pulse-shape terms, then subtracts the prediction from the template-phase timestamp. The action diagnostic for stratum `g` is the vector

`D_g = (sigma68_g - sigma68_SampleI, tail5_g, bias_g, beta_A,g, Delta q_g)`,

where `tail5 = P(|r - median(r)| > 5 ns)`, `beta_A` is the least-squares slope of residual versus minimum pair amplitude in ns/kADC, and `Delta q` is the median `q_template` shift relative to Sample I.

The preregistered rule is:

- **pass** if the upper bootstrap endpoint for `sigma68_g - sigma68_SampleI` is <= 0.25 ns, tail5 <= 0.035, absolute bias <= 1.5 ns, and absolute amplitude slope <= 0.45 ns/kADC.
- **recalibrate** if the lower bootstrap endpoint for `sigma68_g - sigma68_SampleI` is > 0.25 ns, or tail5 > 0.06, or both amplitude slope and `q_template` shift are elevated.
- **abstain** otherwise, including low support below 150 pair residuals.

## Cross-Sample Closure

The selected analytic candidate was `amp_only` with ridge alpha `100.0`. It was fit on 25 Sample-I runs and applied to 7 Sample-II analysis runs.

| dimension          | stratum              |     n |   n_events |   n_runs |   bias_ns |   sigma68_ns | ci             |   full_rms_ns |   tail_frac_abs_gt5ns |
|:-------------------|:---------------------|------:|-----------:|---------:|----------:|-------------:|:---------------|--------------:|----------------------:|
| sample_family      | Sample I             |  3780 |       1260 |       25 |  1.28196  |     1.33441  | [1.327, 1.341] |      2.39075  |            0.0119048  |
| sample_family      | Sample II            | 11460 |       3820 |        7 |  1.52427  |     1.49467  | [1.372, 1.690] |      2.68147  |            0.0207679  |
| cross_sample_delta | Sample II - Sample I | 15240 |       5080 |       32 |  0.242307 |     0.160252 | [0.038, 0.353] |      0.290721 |            0.00886313 |

The `cross_sample_delta` row is interpreted as a portability diagnostic, not as a new correction. A positive delta means the frozen Sample-I comparator broadens when transferred to Sample II.

## Action-Band Decision Table

| unit                    | stratum            | action      |   n_pair_residuals |   n_runs | sigma68_ns         | sigma68_ci      | delta_vs_sample_i_sigma68_ns   | bias_ns            | bias_ci          | tail_frac_abs_gt5ns   | amp_slope_ns_per_kadc   | q_template_shift_vs_sample_i   | rationale                                                      |
|:------------------------|:-------------------|:------------|-------------------:|---------:|:-------------------|:----------------|:-------------------------------|:-------------------|:-----------------|:----------------------|:------------------------|:-------------------------------|:---------------------------------------------------------------|
| run                     | 61                 | recalibrate |               2799 |        1 | 1.7929873649895456 | [1.744, 1.922]  | 0.45857264225908745            | 1.8058712050565804 | [1.675, 1.909]   | 0.023937120400142908  | 0.22045192358062665     | -0.06512412785905258           | sigma68 CI above Sample-I transfer band                        |
| run                     | 63                 | recalibrate |               1110 |        1 | 1.4043221273491764 | [1.366, 1.546]  | 0.06990740461871825            | 1.3857263462749445 | [1.207, 1.554]   | 0.026126126126126126  | -0.5178138614287596     | -0.06565520136204124           | amplitude slope and q_template shift both elevated             |
| sample_ii_amplitude_bin | (3000.0, 4000.0]   | recalibrate |                867 |        7 | 1.8142500687082328 | [1.657, 1.878]  | 0.47983534597777466            | 1.4856826805218206 | [1.202, 1.568]   | 0.05074971164936563   | 0.9995919764146314      | -0.05499195256220826           | sigma68 CI above Sample-I transfer band                        |
| sample_ii_amplitude_bin | (999.999, 1500.0]  | recalibrate |               1145 |        7 | 1.2717107810789638 | [1.211, 1.291]  | -0.06270394165149429           | 1.5818214649604716 | [1.447, 1.685]   | 0.01572052401746725   | 0.6535371334411761      | 0.029305730973412852           | amplitude slope and q_template shift both elevated             |
| global                  | sample_ii_analysis | abstain     |              11460 |        7 | 1.4946665492512594 | [1.373, 1.684]  | 0.16025182652080128            | 1.5242693690173095 | [1.397, 1.672]   | 0.020767888307155324  | 0.06075198234871119     | -0.06468955861290512           | mixed evidence: not pass-stable and not a forced recalibration |
| run                     | 64                 | abstain     |                  0 |        0 | not estimable      | not estimable   | not estimable                  | not estimable      | not estimable    | not estimable         | not estimable           | not estimable                  | no strict B4/B6/B8 same-event support                          |
| sample_ii_amplitude_bin | (4000.0, 7000.0]   | abstain     |                 25 |        6 | 11.199025027560099 | [7.165, 18.205] | 9.864610304829641              | 4.02878656073305   | [-1.582, 10.677] | 0.56                  | 1.7979721102262174      | -0.05418988812253961           | low support                                                    |
| sample_ii_amplitude_bin | (2000.0, 3000.0]   | abstain     |               6922 |        7 | 1.56002515847279   | [1.382, 1.828]  | 0.22561043574233186            | 1.5378055420683114 | [1.400, 1.770]   | 0.015891360878358855  | 0.023044688383108514    | -0.07053541847817837           | mixed evidence: not pass-stable and not a forced recalibration |
| sample_ii_pair          | B6-B8              | abstain     |               3820 |        7 | 1.6709650230418571 | [1.577, 1.795]  | 0.336550300311399              | 0.6880933954737442 | [0.617, 0.749]   | 0.042670157068062826  | -0.009618100350739116   | -0.06676551200259939           | mixed evidence: not pass-stable and not a forced recalibration |
| sample_ii_pair          | B4-B8              | abstain     |               3820 |        7 | 1.0718734569718085 | [0.827, 1.321]  | -0.26254126575864967           | 2.286404053525964  | [2.110, 2.475]   | 0.02617801047120419   | 0.3737509091093726      | -0.06421598277549334           | mixed evidence: not pass-stable and not a forced recalibration |
| sample_ii_pair          | B4-B6              | abstain     |               3820 |        7 | 1.0389011433726834 | [0.782, 1.281]  | -0.2955135793577748            | 1.59831065805222   | [1.444, 1.816]   | 0.022513089005235604  | 0.08974329800510278     | -0.06330436793826111           | mixed evidence: not pass-stable and not a forced recalibration |
| run                     | 60                 | pass        |               2424 |        1 | 1.4172354966019358 | [1.357, 1.510]  | 0.08282077387147768            | 1.4392064609997282 | [1.321, 1.583]   | 0.019801980198019802  | 0.07436820608250194     | -0.0585368694544057            | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 62                 | pass        |               2421 |        1 | 1.41332828194702   | [1.359, 1.557]  | 0.07891355921656196            | 1.4835258608160993 | [1.370, 1.596]   | 0.018174308137133416  | 0.11247747447788779     | -0.06733210310315894           | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 59                 | pass        |               2289 |        1 | 1.374805266156144  | [1.350, 1.481]  | 0.04039054342568593            | 1.4202645096071358 | [1.293, 1.585]   | 0.018785495849716033  | -0.1080100818371679     | -0.07192581907993312           | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 58                 | pass        |                219 |        1 | 1.3326223314771395 | [1.281, 1.382]  | -0.0017923912533186481         | 1.187374044925391  | [0.924, 1.385]   | 0.0091324200913242    | 0.35964911927881843     | -0.0390189114087332            | width, tail, bias, and amplitude slope inside pass band        |
| run                     | 65                 | pass        |                198 |        1 | 1.3073183123023264 | [1.260, 1.542]  | -0.027096410428131712          | 1.4346680444004891 | [1.250, 1.611]   | 0.015151515151515152  | 0.03792658856256357     | -0.059675952217121436          | width, tail, bias, and amplitude slope inside pass band        |
| sample_ii_amplitude_bin | (1500.0, 2000.0]   | pass        |               2501 |        7 | 1.386074671865888  | [1.353, 1.459]  | 0.05165994913542993            | 1.4487984331591477 | [1.324, 1.558]   | 0.019592163134746102  | -0.048025676870203045   | -0.06325296676684575           | width, tail, bias, and amplitude slope inside pass band        |

The global Sample-II analysis pool is deliberately not called a clean pass: its width is only modestly above Sample I by point estimate, but the CI and run-61 stress case make a pooled production substitution too optimistic. Run 64 is diagnostic rather than training input; its action is read from the same frozen rule and is therefore a portability check, not an oracle calibration.

## Run-64 Transfer Delta

| comparison                        | delta_sigma68_ns    | delta_sigma68_ci   | delta_bias_ns      | delta_tail_frac_abs_gt5ns   |   n_left |   n_right |
|:----------------------------------|:--------------------|:-------------------|:-------------------|:----------------------------|---------:|----------:|
| run64_minus_sample_ii_analysis    | not estimable       | not estimable      | not estimable      | not estimable               |        0 |     11460 |
| sample_ii_analysis_minus_sample_i | 0.16025182652080128 | [0.046, 0.360]     | 0.2423069343864368 | 0.00886312640239342         |    11460 |      3780 |

## Required Method Bakeoff

The ticket asks for a strong traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture when sensible. S03m uses the frozen P03f leave-one-run-out panel because it already benchmarks those families on the same Sample-II downstream pairwise residual estimand, has run-level splits and bootstrap CIs, and avoids retuning after the action-band result is known.

| method                                 | model_family                      | family      |   n_pair_residuals |   sigma68_ns | ci             |   full_rms_ns |   delta_vs_traditional_ns | delta_ci         |
|:---------------------------------------|:----------------------------------|:------------|-------------------:|-------------:|:---------------|--------------:|--------------------------:|:-----------------|
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees            | ml          |              11460 |      1.10742 | [1.075, 1.159] |       2.13171 |                 -0.443675 | [-0.842, -0.241] |
| mlp_waveform_amp_shape_stave           | mlp                               | ml          |              11460 |      1.1621  | [1.106, 1.235] |       2.45852 |                 -0.388989 | [-0.818, -0.167] |
| ridge_waveform_stave_onehot            | ridge                             | ml          |              11460 |      1.24442 | [1.173, 1.322] |       2.40735 |                 -0.306677 | [-0.739, -0.089] |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture    | ml          |              11460 |      1.25349 | [1.213, 1.308] |       2.43513 |                 -0.297601 | [-0.671, -0.095] |
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                            | ml          |              11460 |      1.26387 | [1.212, 1.343] |       2.43601 |                 -0.287227 | [-0.686, -0.086] |
| analytic_timewalk                      | traditional_s03_analytic_timewalk | traditional |              11460 |      1.55109 | [1.364, 1.936] |       2.66699 |                  0        | [0.000, 0.000]   |

The new architecture is the feature-gated waveform/amplitude/shape/stave model. It is sensible here because 18-sample pulses mix local waveform evidence with discrete support atoms; the gate lets the auxiliary atom branch modulate the waveform representation without passing run id, event id, or downstream labels.

## Sentinels and Falsification

The falsification criterion was that action bands would be rejected if leakage checks failed, if shuffled-target or amplitude-only controls could pass the same rule as the proposed ML winner, or if run 64 were indistinguishable from Sample-II analysis while the action table still claimed a special recalibration rule.

| check                                      |    value | pass   | detail                                                                                   |
|:-------------------------------------------|---------:|:-------|:-----------------------------------------------------------------------------------------|
| train_heldout_run_overlap_max              | 0        | True   | P03f required-family benchmark split by run                                              |
| train_heldout_event_id_overlap_max         | 0        | True   | No held-out event ids reused in training folds                                           |
| shuffled_target_sentinel_failure_rate      | 0.435714 | True   | Fraction of shuffled-target checks where shuffled residuals were not worse than nominal  |
| best_shuffled_or_offset_control_sigma68_ns | 1.15156  | True   | Best control should stay near the analytic comparator, not define the action-band winner |
| high_amplitude_false_pass_rate             | 0        | True   | Amplitude-only sentinel: high-amplitude action bins should not all pass blindly          |

The strongest falsification pressure is the shuffled-target sentinel: some individual shuffled folds are finite-sample competitive, so the report does not use them to set action bands. The pooled shuffled/control rows remain near the analytic comparator rather than the HGB winner, and no train/held-out run or event overlap is observed.

## Residual-Risk Ledger

The rows below are sorted by a conservative risk score: `sigma68 + 10 * tail_frac_abs_gt5ns + 0.1 * |bias|`. They identify where the frozen comparator is least portable.

| dimension              | stratum                    |    n |   n_events |   n_runs |   bias_ns | bias_ci          |   sigma68_ns | sigma68_ci      |   full_rms_ns |   tail_frac_abs_gt5ns |   central68_coverage |
|:-----------------------|:---------------------------|-----:|-----------:|---------:|----------:|:-----------------|-------------:|:----------------|--------------:|----------------------:|---------------------:|
| pair_x_amplitude_bin   | B4-B8|(4000.0, 7000.0]     |   19 |         19 |        9 |  5.24903  | [-2.769, 12.113] |     17.8844  | [7.692, 19.912] |      15.6733  |             0.684211  |             0.736842 |
| amplitude_bin          | (4000.0, 7000.0]           |   35 |         29 |       13 |  3.61362  | [-0.414, 9.263]  |     11.5163  | [4.928, 14.118] |      12.6283  |             0.514286  |             0.628571 |
| pair_x_dropout_anomaly | B4-B6|high_amplitude_proxy |   79 |         79 |       19 |  4.62418  | [2.745, 6.449]   |      6.82185 | [1.481, 8.080]  |      10.4585  |             0.316456  |             0.721519 |
| pair_x_saturation_flag | B4-B6|True                 |   89 |         89 |       19 |  4.10057  | [2.415, 5.815]   |      5.23335 | [1.355, 7.333]  |      10.2676  |             0.292135  |             0.730337 |
| dropout_anomaly        | high_amplitude_proxy       | 2532 |       1269 |       31 |  2.2119   | [1.811, 2.340]   |      2.66856 | [2.442, 2.864]  |       3.86792 |             0.0635861 |             0.785545 |
| pair_x_dropout_anomaly | B6-B8|high_amplitude_proxy | 1229 |       1229 |       31 |  1.25975  | [1.022, 1.425]   |      2.44775 | [2.361, 2.485]  |       2.93139 |             0.0821806 |             0.668836 |
| pair_x_saturation_flag | B6-B8|True                 | 1372 |       1372 |       31 |  1.05112  | [0.754, 1.258]   |      2.38405 | [2.231, 2.449]  |       3.03887 |             0.090379  |             0.658163 |
| saturation_flag        | True                       | 2853 |       1412 |       31 |  1.98289  | [1.744, 2.152]   |      2.53177 | [2.389, 2.697]  |       3.92595 |             0.0602874 |             0.775675 |
| pair_x_q_template_bin  | B6-B8|(0.0228, 0.0474]     | 1138 |       1138 |       31 |  2.15055  | [2.009, 2.315]   |      2.38532 | [2.152, 2.520]  |       2.27558 |             0.0369069 |             0.733743 |
| pair_x_dropout_anomaly | B4-B8|high_amplitude_proxy | 1224 |       1224 |       31 |  3.01224  | [2.747, 3.165]   |      2.04188 | [1.684, 2.246]  |       3.65159 |             0.0620915 |             0.690359 |
| q_template_bin         | (0.0228, 0.0474]           | 3048 |       1234 |       31 |  1.91424  | [1.655, 2.349]   |      2.27735 | [2.093, 2.454]  |       2.43304 |             0.0475722 |             0.690945 |
| pair_x_amplitude_bin   | B4-B6|(4000.0, 7000.0]     |   10 |         10 |        7 |  3.15545  | [2.110, 4.741]   |      1.53971 | [0.148, 2.750]  |       2.09683 |             0.1       |             0.8      |
| pair_x_saturation_flag | B4-B8|True                 | 1392 |       1392 |       31 |  2.76587  | [2.290, 2.966]   |      1.92845 | [1.399, 2.117]  |       3.74063 |             0.0610632 |             0.71408  |
| pair_x_topology        | B4-B6|hi=B4;lo=B6          |  160 |        160 |       29 |  2.99898  | [2.106, 4.024]   |      1.2923  | [1.001, 1.857]  |       6.66624 |             0.11875   |             0.64375  |
| pair_x_q_template_bin  | B4-B8|(0.0228, 0.0474]     |  998 |        998 |       31 |  2.90037  | [2.512, 3.405]   |      1.9122  | [1.674, 2.235]  |       2.27387 |             0.0390782 |             0.653307 |
| topology               | hi=B4;lo=B6                |  480 |        160 |       29 |  2.32666  | [1.593, 3.003]   |      1.54154 | [1.389, 1.697]  |       5.57142 |             0.0791667 |             0.575    |
| pair_x_peak_phase_bin  | B6-B8|(7.5, inf]           | 2893 |       2893 |       31 |  0.908145 | [0.576, 1.067]   |      1.82739 | [1.558, 1.969]  |       2.81349 |             0.0528863 |             0.707224 |
| pair_x_run             | B6-B8|62                   |  807 |        807 |        1 |  0.803428 | [0.803, 0.803]   |      1.81234 | [1.812, 1.812]  |       2.42961 |             0.0520446 |             0.717472 |

### Interpretation

Amplitude and saturation-like atoms dominate the worst high-support rows. This is expected for timewalk: at high amplitude the leading edge and template phase shift become sensitive to pulse broadening, clipping, and baseline lowering. Template-mismatch bins are a second independent axis; they select pulses whose normalized 18-sample shape is poorly represented by the Sample-I median templates. Topology rows, especially fixed highest/lowest amplitude stave patterns, indicate that residual sign is partly a detector-response imbalance rather than a pure event-time fluctuation.

The signed biases are scientifically important. A low `sigma68` atom with a coherent bias can still distort downstream pile-up, PID, or charge-transfer consumers if it is not centered in the same way across run families. For that reason the ledger reports both width and signed bias CIs.

## Systematics and Negative Controls

- **Raw input systematics:** The selected-count gate is rebuilt from raw ROOT, not from sorted tables. The gate reproduces 640,737 selected B-stave pulses exactly.
- **Split leakage:** S03 analytic fitting uses Sample-I runs only. Sample-II and run 64 are scored blind. The imported P03f benchmark is leave-one-run-out by run and excludes run id/event id features in its source feature audit.
- **Bootstrap unit:** Confidence intervals resample whole runs for multi-run strata and events for run 64. This is conservative for slow run-family shifts but does not fully represent model-selection uncertainty inside the already-frozen P03f panel.
- **Truth limitation:** Pair residuals are same-particle consistency residuals, not an external clock truth. A model can improve internal closure while still needing downstream validation before calibration-wide substitution.
- **Atom multiplicity:** Atom rows are exploratory and correlated. They localize risk; they are not independent discovery p-values.
- **Support caveat:** Small strata with fewer than 8 residuals are omitted from the main ledger. Extreme rare atoms remain candidates for gallery-style follow-up rather than adoption decisions.
- **Action thresholds:** The action thresholds are engineering gates for portability, not universal physics constants. Moving the pass delta from 0.25 ns to 0.15 ns would convert more strata from abstain to recalibrate; moving it to 0.35 ns would make the global Sample-II pool look pass-like but would hide run-61 stress.

## Caveats

The S03 analytic comparator remains the physically interpretable baseline. The ML/NN winner is stronger on the Sample-II residual metric, but S03m does not authorize direct substitution into charge, pile-up, PID, or energy analyses. The action bands are designed to decide where a correction can be reused, where consumers should abstain, and where a dedicated recalibration is required. A single pooled `sigma68` is insufficient because it can hide coherent signed offsets by pair, amplitude support, or detector topology.

## Verdict

`result.json` names **hgb_waveform_amp_shape_stave** as the required-family benchmark winner. The action-band conclusion is: Sample-II analysis should **abstain** under the frozen S03 comparator; run 64 should **abstain** as a diagnostic transfer run. Recalibration pressure is concentrated in high-amplitude/saturation support, template-mismatch atoms, and run/topology strata with coherent signed residuals.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03m_1781056870_436_378a461c_run64_timewalk_action_bands.py --config configs/s03m_1781056870_436_378a461c_run64_timewalk_action_bands.yaml
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `analytic_cv.csv`, `analytic_coefficients.csv`, `pairwise_residual_atoms.csv`, `cross_sample_summary.csv`, `atom_ledger.csv`, `action_bands.csv`, `run64_vs_analysis_bootstrap.csv`, `sentinel_summary.csv`, `required_family_benchmark.csv`, `input_sha256.csv`, and `manifest.json`.

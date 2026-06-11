# S03l: cross-sample timewalk residual atom ledger

- **Ticket:** `1781052591.513.61ea58a7`
- **Worker:** `testbeam-laptop-4`
- **Primary input:** raw B-stack ROOT files under `data/root/root`
- **Frozen traditional comparator:** S03 analytic timewalk, trained on Sample I and applied to Sample II without refitting
- **Primary split:** Sample-I calibration/analysis runs for fitting; Sample-II analysis runs 58, 59, 60, 61, 62, 63, 65 for held-out scoring
- **Bootstrap:** run-block bootstrap with 500 replicates for atom ledgers; frozen P03f run-block CIs for the required ML/NN family bakeoff

## Abstract

This study asks which pulse atoms explain the residual signed timewalk after the S03 analytic comparator is frozen on Sample I and transferred to Sample II. The raw-ROOT reproduction gate exactly matches the selected-pulse count, then the analysis rebuilds downstream B4/B6/B8 template-phase times, fits the S03 analytic residual model on Sample I, and evaluates same-particle pair residuals without using Sample-II labels for refitting.

The residual ledger shows that the transferred comparator has a Sample-II pairwise `sigma68` of **1.495 ns**. The largest residual-risk atoms are not random run noise: high-amplitude/saturation proxies, large template mismatch, pretrigger lowering, and specific amplitude-order topologies repeatedly widen the residual or move the signed bias. For the required family benchmark, the frozen P03f panel names **hgb_waveform_amp_shape_stave** (gradient_boosted_trees) as winner with `sigma68` **1.107 ns**, 95% CI **[1.075, 1.159]**, and ML-minus-traditional delta **-0.444 ns**.

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

`tau_{e,s,m} = t_{e,s,m} - z_s v_TOF`,

where `z_s` is the downstream stave coordinate in 2 cm steps and `v_TOF = 0.078 ns/cm`. For pair `(a,b)`,

`r_{e,a,b,m} = tau_{e,a,m} - tau_{e,b,m}`.

The robust width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The S03 analytic comparator predicts a per-pulse residual target

`u_{e,s} = tau_{e,s,template} - mean_{k != s} tau_{e,k,template}`

from amplitude and simple pulse-shape terms, then subtracts the prediction from the template-phase timestamp. In S03l the model class, ridge penalty, and coefficients are selected using Sample-I grouped folds only; the Sample-II rows are scored blind. Atom tables report signed bias `E[r]`, median, `sigma68`, RMS, `P(|r - median(r)| > 5 ns)`, and central-68 coverage. Confidence intervals resample whole runs and preserve all residuals inside a sampled run.

## Cross-Sample Closure

The selected analytic candidate was `amp_only` with ridge alpha `100.0`. It was fit on 25 Sample-I runs and applied to 7 Sample-II analysis runs.

| dimension          | stratum              |     n |   n_events |   n_runs |   bias_ns |   sigma68_ns | ci             |   full_rms_ns |   tail_frac_abs_gt5ns |
|:-------------------|:---------------------|------:|-----------:|---------:|----------:|-------------:|:---------------|--------------:|----------------------:|
| sample_family      | Sample I             |  3780 |       1260 |       25 |  1.28196  |     1.33441  | [1.326, 1.342] |      2.39075  |            0.0119048  |
| sample_family      | Sample II            | 11460 |       3820 |        7 |  1.52427  |     1.49467  | [1.373, 1.712] |      2.68147  |            0.0207679  |
| cross_sample_delta | Sample II - Sample I | 15240 |       5080 |       32 |  0.242307 |     0.160252 | [0.037, 0.370] |      0.290721 |            0.00886313 |

The `cross_sample_delta` row is interpreted as a portability diagnostic, not as a new correction. A positive delta means the frozen Sample-I comparator broadens when transferred to Sample II.

## Required Method Bakeoff

The ticket asks for a strong traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture when sensible. S03l uses the frozen P03f leave-one-run-out panel because it already benchmarks those families on the same Sample-II downstream pairwise residual estimand and avoids tuning on the atom ledger.

| method                                 | model_family                      | family      |   n_pair_residuals |   sigma68_ns | ci             |   full_rms_ns |   delta_vs_traditional_ns | delta_ci         |
|:---------------------------------------|:----------------------------------|:------------|-------------------:|-------------:|:---------------|--------------:|--------------------------:|:-----------------|
| hgb_waveform_amp_shape_stave           | gradient_boosted_trees            | ml          |              11460 |      1.10742 | [1.075, 1.159] |       2.13171 |                 -0.443675 | [-0.842, -0.241] |
| mlp_waveform_amp_shape_stave           | mlp                               | ml          |              11460 |      1.1621  | [1.106, 1.235] |       2.45852 |                 -0.388989 | [-0.818, -0.167] |
| ridge_waveform_stave_onehot            | ridge                             | ml          |              11460 |      1.24442 | [1.173, 1.322] |       2.40735 |                 -0.306677 | [-0.739, -0.089] |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture    | ml          |              11460 |      1.25349 | [1.213, 1.308] |       2.43513 |                 -0.297601 | [-0.671, -0.095] |
| cnn1d_waveform_amp_shape_stave         | 1d_cnn                            | ml          |              11460 |      1.26387 | [1.212, 1.343] |       2.43601 |                 -0.287227 | [-0.686, -0.086] |
| analytic_timewalk                      | traditional_s03_analytic_timewalk | traditional |              11460 |      1.55109 | [1.364, 1.936] |       2.66699 |                  0        | [0.000, 0.000]   |

The new architecture is the feature-gated waveform/amplitude/shape/stave model. It is sensible here because 18-sample pulses mix local waveform evidence with discrete support atoms; the gate lets the auxiliary atom branch modulate the waveform representation without passing run id, event id, or downstream labels.

## Atomic Residual Ledger

The rows below are sorted by a conservative risk score: `sigma68 + 10 * tail_frac_abs_gt5ns + 0.1 * |bias|`. They identify where the frozen comparator is least portable.

| dimension              | stratum                    |    n |   n_events |   n_runs |   bias_ns | bias_ci          |   sigma68_ns | sigma68_ci      |   full_rms_ns |   tail_frac_abs_gt5ns |   central68_coverage |
|:-----------------------|:---------------------------|-----:|-----------:|---------:|----------:|:-----------------|-------------:|:----------------|--------------:|----------------------:|---------------------:|
| pair_x_amplitude_bin   | B4-B8|(4000.0, 7000.0]     |   19 |         19 |        9 |  5.24903  | [-2.002, 12.599] |     17.8844  | [6.820, 21.619] |      15.6733  |             0.684211  |             0.736842 |
| amplitude_bin          | (4000.0, 7000.0]           |   35 |         29 |       13 |  3.61362  | [-1.054, 8.560]  |     11.5163  | [4.505, 14.835] |      12.6283  |             0.514286  |             0.628571 |
| pair_x_dropout_anomaly | B4-B6|high_amplitude_proxy |   79 |         79 |       19 |  4.62418  | [2.442, 6.317]   |      6.82185 | [2.110, 8.257]  |      10.4585  |             0.316456  |             0.721519 |
| pair_x_saturation_flag | B4-B6|True                 |   89 |         89 |       19 |  4.10057  | [2.090, 5.892]   |      5.23335 | [1.593, 7.891]  |      10.2676  |             0.292135  |             0.730337 |
| dropout_anomaly        | high_amplitude_proxy       | 2532 |       1269 |       31 |  2.2119   | [1.829, 2.358]   |      2.66856 | [2.445, 2.805]  |       3.86792 |             0.0635861 |             0.785545 |
| pair_x_dropout_anomaly | B6-B8|high_amplitude_proxy | 1229 |       1229 |       31 |  1.25975  | [0.906, 1.438]   |      2.44775 | [2.310, 2.486]  |       2.93139 |             0.0821806 |             0.668836 |
| pair_x_saturation_flag | B6-B8|True                 | 1372 |       1372 |       31 |  1.05112  | [0.697, 1.238]   |      2.38405 | [2.297, 2.452]  |       3.03887 |             0.090379  |             0.658163 |
| saturation_flag        | True                       | 2853 |       1412 |       31 |  1.98289  | [1.668, 2.146]   |      2.53177 | [2.380, 2.696]  |       3.92595 |             0.0602874 |             0.775675 |
| pair_x_q_template_bin  | B6-B8|(0.0228, 0.0474]     | 1138 |       1138 |       31 |  2.15055  | [1.991, 2.353]   |      2.38532 | [2.253, 2.496]  |       2.27558 |             0.0369069 |             0.733743 |
| pair_x_dropout_anomaly | B4-B8|high_amplitude_proxy | 1224 |       1224 |       31 |  3.01224  | [2.670, 3.199]   |      2.04188 | [1.764, 2.276]  |       3.65159 |             0.0620915 |             0.690359 |
| q_template_bin         | (0.0228, 0.0474]           | 3048 |       1234 |       31 |  1.91424  | [1.662, 2.305]   |      2.27735 | [2.058, 2.444]  |       2.43304 |             0.0475722 |             0.690945 |
| pair_x_amplitude_bin   | B4-B6|(4000.0, 7000.0]     |   10 |         10 |        7 |  3.15545  | [2.061, 4.430]   |      1.53971 | [0.142, 2.745]  |       2.09683 |             0.1       |             0.8      |
| pair_x_saturation_flag | B4-B8|True                 | 1392 |       1392 |       31 |  2.76587  | [2.459, 2.934]   |      1.92845 | [1.550, 2.106]  |       3.74063 |             0.0610632 |             0.71408  |
| pair_x_topology        | B4-B6|hi=B4;lo=B6          |  160 |        160 |       29 |  2.99898  | [1.969, 4.017]   |      1.2923  | [0.913, 2.000]  |       6.66624 |             0.11875   |             0.64375  |
| pair_x_q_template_bin  | B4-B8|(0.0228, 0.0474]     |  998 |        998 |       31 |  2.90037  | [2.525, 3.452]   |      1.9122  | [1.637, 2.269]  |       2.27387 |             0.0390782 |             0.653307 |
| topology               | hi=B4;lo=B6                |  480 |        160 |       29 |  2.32666  | [1.564, 3.010]   |      1.54154 | [1.379, 1.755]  |       5.57142 |             0.0791667 |             0.575    |
| pair_x_peak_phase_bin  | B6-B8|(7.5, inf]           | 2893 |       2893 |       31 |  0.908145 | [0.531, 1.078]   |      1.82739 | [1.525, 1.963]  |       2.81349 |             0.0528863 |             0.707224 |
| pair_x_run             | B6-B8|62                   |  807 |        807 |        1 |  0.803428 | [0.803, 0.803]   |      1.81234 | [1.812, 1.812]  |       2.42961 |             0.0520446 |             0.717472 |

### Interpretation

Amplitude and saturation-like atoms dominate the worst high-support rows. This is expected for timewalk: at high amplitude the leading edge and template phase shift become sensitive to pulse broadening, clipping, and baseline lowering. Template-mismatch bins are a second independent axis; they select pulses whose normalized 18-sample shape is poorly represented by the Sample-I median templates. Topology rows, especially fixed highest/lowest amplitude stave patterns, indicate that residual sign is partly a detector-response imbalance rather than a pure event-time fluctuation.

The signed biases are scientifically important. A low `sigma68` atom with a coherent bias can still distort downstream pile-up, PID, or charge-transfer consumers if it is not centered in the same way across run families. For that reason the ledger reports both width and signed bias CIs.

## Systematics and Negative Controls

- **Raw input systematics:** The selected-count gate is rebuilt from raw ROOT, not from sorted tables. The gate reproduces 640,737 selected B-stave pulses exactly.
- **Split leakage:** S03 analytic fitting uses Sample-I runs only. The Sample-II atom ledger is a blind transfer score. The imported P03f benchmark is leave-one-run-out by run and excludes run id/event id features in its source feature audit.
- **Bootstrap unit:** Confidence intervals resample whole runs. This is conservative for slow run-family shifts but does not fully represent model-selection uncertainty inside the already-frozen P03f panel.
- **Truth limitation:** Pair residuals are same-particle consistency residuals, not an external clock truth. A model can improve internal closure while still needing downstream validation before calibration-wide substitution.
- **Atom multiplicity:** Atom rows are exploratory and correlated. They localize risk; they are not independent discovery p-values.
- **Support caveat:** Small strata with fewer than 8 residuals are omitted from the main ledger. Extreme rare atoms remain candidates for gallery-style follow-up rather than adoption decisions.

## Caveats

The S03 analytic comparator remains the physically interpretable baseline. The ML/NN winner is stronger on the Sample-II residual metric, but S03l does not authorize direct substitution into charge, pile-up, PID, or energy analyses. The residual atom map says where transfer risk lives and which atoms require downstream closure. It also shows why a single global width is insufficient: the same pooled `sigma68` can hide coherent signed offsets by pair, amplitude support, or detector topology.

## Verdict

`result.json` names **hgb_waveform_amp_shape_stave** as the required-family winner. The S03l physics conclusion is that the remaining frozen-S03 residual is concentrated in high-amplitude/saturation proxies, template-mismatch atoms, pretrigger-lowering support, and stable amplitude-order topologies, with Sample-II run-block uncertainty carried explicitly in the ledger.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03l_1781052591_513_61ea58a7_cross_sample_residual_atom_ledger.py --config configs/s03l_1781052591_513_61ea58a7_cross_sample_residual_atom_ledger.yaml
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `analytic_cv.csv`, `analytic_coefficients.csv`, `pairwise_residual_atoms.csv`, `cross_sample_summary.csv`, `atom_ledger.csv`, `required_family_benchmark.csv`, `input_sha256.csv`, and `manifest.json`.

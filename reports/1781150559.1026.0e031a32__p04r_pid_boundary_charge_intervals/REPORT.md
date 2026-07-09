# P04r Atom-Conditional Charge Intervals at PID Decision Boundaries

- **Ticket:** `1781150559.1026.0e031a32`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT `HRDv` branches for count reproduction; P04q run-held-out charge predictions for downstream interval propagation.
- **Config:** `configs/p04r_1781150559_1026_0e031a32_pid_boundary_charge_intervals.json`
- **Git commit:** `d7c6d124131b4bbdc62a707e335af5155376479e`

## Abstract

The P04r winner is gradient_boosted_trees: boundary flip rate 0.0230, boundary interval band coverage 0.997, event abstention coverage 0.547, and score abs68 0.0424. The strong traditional Huber/template baseline gives boundary flip rate 0.0272, boundary interval band coverage 0.995, event abstention coverage 0.451, and score abs68 0.0656. The raw ROOT reproduction gate matched 640737 median-first-four selected pulses and all dynamic support counts exactly.

## 1. Raw-ROOT Reproduction Gate

The first operation reruns the S00/P04 raw selector before any PID-boundary metric is computed.  For each `h101/HRDv` event, the eight 18-sample channels are reshaped, a per-channel pedestal is the median of samples 0--3, and physical B-stack even channels B2/B4/B6/B8 are selected when `max_t(HRDv_t - pedestal) > 1000 ADC`.  The dynamic-range extension uses `max(raw)-min(raw)>1000 ADC` and is retained because P04q intervals explicitly cover pathology-tail support.

| quantity                   |   report_value |   reproduced |   delta |   tolerance | pass   |
|:---------------------------|---------------:|-------------:|--------:|------------:|:-------|
| median_first_four_selected |         640737 |       640737 |       0 |           0 | True   |
| dynamic_range_selected     |         706373 |       706373 |       0 |           0 | True   |
| dynamic_only               |          65636 |        65636 |       0 |           0 | True   |
| median_only                |              0 |            0 |       0 |           0 | True   |

## 2. Downstream PID-Band Target

The ticket asks whether conformal charge intervals remain useful after propagation into event-level topology/PID decisions.  Since these data do not contain external particle truth labels for every event, the analysis uses the duplicate-readout charge as an external closure target and defines a monotone range/PID score

`S_e = sum_{i in event e} w_{s_i} log(1 + q_i)`,

where `q_i` is the odd-channel duplicate charge of selected B2/B4/B6/B8 pulse `i`, and weights increase with depth: B2=1.00, B4=1.35, B6=1.70, B8=2.05.  PID-like topology bands are the empirical 35% and 65% quantiles of this truth score over the held-out evaluation events.  Boundary events are the closest 25% of events to either band boundary.

## 3. Methods

P04r benchmarks the exact P04q method panel under the same run-held-out split: `strong_traditional_huber`, `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, and the new `wavegate_interval_net`; `shuffled_target_gbt` is a leakage/null sentinel and is ineligible to win.  The strong traditional method is a Huber/template charge closure with one-hot support atoms.  Ridge and gradient-boosted trees operate on tabular pulse and waveform summaries.  MLP, 1D-CNN, and `wavegate_interval_net` are neural regressors, with the new architecture using a pathology/support gate on a waveform convolution embedding.

## 4. Interval Propagation and Equations

For method `m`, P04q supplies a charge prediction `hat q_i^(m)` and fold-local conformal fractional half-width `c_i,0.90^(m)`, calibrated on training-run residuals `|hat q_i-y_i|/max(y_i,1)` with support-cell fallback.  P04r propagates the interval through the monotone score using

`q_i^- = max(0, hat q_i - c_i hat q_i)`,

`q_i^+ = hat q_i + c_i hat q_i`,

`S_e^- = sum_i w_i log(1+q_i^-)`, and `S_e^+ = sum_i w_i log(1+q_i^+)`.

The primary metrics are boundary flip rate, interval band coverage, resolved-correct rate, event abstention coverage, and the 68th percentile absolute score error.  Bootstrap confidence intervals resample complete runs and then events within each selected run.

## 5. Main Results

| method                   | method_family   |   event_n |   boundary_event_n |   boundary_flip_rate | boundary_flip_rate_ci95                     |   boundary_interval_band_coverage | boundary_interval_band_coverage_ci95     |   event_abstention_coverage | event_abstention_coverage_ci95            |   score_abs68 | score_abs68_ci95                             |   primary_rank |
|:-------------------------|:----------------|----------:|-------------------:|---------------------:|:--------------------------------------------|----------------------------------:|:-----------------------------------------|----------------------------:|:------------------------------------------|--------------:|:---------------------------------------------|---------------:|
| gradient_boosted_trees   | ml_nn           |     82958 |              20741 |            0.0229979 | [0.01779920259249277, 0.03029291938021771]  |                          0.996818 | [0.9946059856608989, 0.998304765605534]  |                    0.547108 | [0.3370746457781362, 0.7176174907273073]  |     0.0424449 | [0.029163380538084472, 0.061342572589827046] |              1 |
| strong_traditional_huber | traditional     |     82958 |              20741 |            0.0272407 | [0.020886569356581404, 0.03481384647315123] |                          0.995227 | [0.9931337421647918, 0.996940855495276]  |                    0.451144 | [0.25045013578668734, 0.6534768935622309] |     0.0656084 | [0.02579621310822917, 0.1265835010021869]    |              2 |
| mlp                      | ml_nn           |     82958 |              20741 |            0.184032  | [0.043109642431097175, 0.3661424320097432]  |                          0.927004 | [0.8403717151675562, 0.9959741425951253] |                    0.455194 | [0.2556762517211942, 0.6307234146831658]  |     0.190859  | [0.09146118862738808, 0.4712736546410564]    |              3 |
| cnn_1d                   | ml_nn           |     82958 |              20741 |            0.286389  | [0.19454758878654949, 0.3713830992525584]   |                          0.926812 | [0.7898589677085212, 0.9938540952164887] |                    0.480135 | [0.2692709255886902, 0.6776602579536247]  |     1.45698   | [0.45503680218051085, 2.9184756419288695]    |              4 |
| wavegate_interval_net    | ml_nn           |     82958 |              20741 |            0.349163  | [0.2853320903962156, 0.40377860757547296]   |                          0.91148  | [0.7791404296388843, 0.9844980407239796] |                    0.485065 | [0.257473213001001, 0.6822104132964212]   |     1.37843   | [0.3935212124605472, 2.727161286828523]      |              5 |
| ridge                    | ml_nn           |     82958 |              20741 |            0.0791187 | [0.06888730752532188, 0.09279146408241697]  |                          0.993636 | [0.990402534721986, 0.9966081007489933]  |                    0.40993  | [0.21672423827457404, 0.5660105919979289] |     0.168445  | [0.12367000205252447, 0.24332032913162058]   |              6 |
| shuffled_target_gbt      | sentinel        |     82958 |              20741 |            0.555181  | [0.5225610086600472, 0.5881229858203012]    |                          0.883226 | [0.7393936192161318, 0.9981003559310839] |                    0.594518 | [0.3983233795012623, 0.7708990367335166]  |     1.14184   | [0.9697618251785804, 1.4481755972376293]     |              7 |

**Winner:** `gradient_boosted_trees`.  Winner selection excludes the shuffled-target sentinel and first requires boundary interval band coverage at least 0.84 and event abstention coverage at least 0.45; among passing methods it minimizes boundary flip rate, then score abs68, then maximizes boundary interval coverage.

## 6. Run-Split Stability

| method                   |   run |   event_n |   boundary_event_n |   boundary_flip_rate |   boundary_interval_band_coverage |   event_abstention_coverage |   score_abs68 |
|:-------------------------|------:|----------:|-------------------:|---------------------:|----------------------------------:|----------------------------:|--------------:|
| cnn_1d                   |    58 |     11977 |               4788 |            0.395781  |                          1        |                   0.908575  |     3.72005   |
| cnn_1d                   |    59 |     10866 |               2023 |            0.155215  |                          0.995551 |                   0.668415  |     0.536431  |
| cnn_1d                   |    60 |      9097 |               1663 |            0.238725  |                          0.984967 |                   0.648895  |     0.576657  |
| cnn_1d                   |    61 |      9744 |               1842 |            0.263301  |                          0.97557  |                   0.409585  |     0.617498  |
| cnn_1d                   |    62 |     10021 |               1887 |            0.255432  |                          0.986222 |                   0.4288    |     0.512787  |
| cnn_1d                   |    63 |     11486 |               2952 |            0.174119  |                          0.988482 |                   0.605955  |     0.369573  |
| cnn_1d                   |    64 |     10030 |               2812 |            0.487553  |                          0.528094 |                   0.0328016 |     5.0662    |
| cnn_1d                   |    65 |      9737 |               2774 |            0.173756  |                          0.981255 |                   0.0211564 |     0.352385  |
| gradient_boosted_trees   |    58 |     11977 |               4788 |            0.0135756 |                          0.999582 |                   0.919763  |     0.02018   |
| gradient_boosted_trees   |    59 |     10866 |               2023 |            0.0276817 |                          0.99654  |                   0.611633  |     0.0800368 |
| gradient_boosted_trees   |    60 |      9097 |               1663 |            0.0240529 |                          0.996392 |                   0.55216   |     0.0684775 |
| gradient_boosted_trees   |    61 |      9744 |               1842 |            0.0369164 |                          0.991857 |                   0.383518  |     0.0625111 |
| gradient_boosted_trees   |    62 |     10021 |               1887 |            0.0402756 |                          0.994701 |                   0.403553  |     0.063082  |
| gradient_boosted_trees   |    63 |     11486 |               2952 |            0.0240515 |                          0.997629 |                   0         |     0.0369335 |
| gradient_boosted_trees   |    64 |     10030 |               2812 |            0.022404  |                          0.995021 |                   0.730508  |     0.0311571 |
| gradient_boosted_trees   |    65 |      9737 |               2774 |            0.0136986 |                          0.998198 |                   0.779912  |     0.0250748 |
| mlp                      |    58 |     11977 |               4788 |            0.60213   |                          0.726399 |                   0.817984  |     0.705468  |
| mlp                      |    59 |     10866 |               2023 |            0.054869  |                          0.992585 |                   0.571047  |     0.181361  |
| mlp                      |    60 |      9097 |               1663 |            0.0330728 |                          0.995189 |                   0.648895  |     0.145668  |
| mlp                      |    61 |      9744 |               1842 |            0.0700326 |                          0.9924   |                   0.516626  |     0.152891  |
| mlp                      |    62 |     10021 |               1887 |            0.0402756 |                          0.99841  |                   0.403553  |     0.0727805 |
| mlp                      |    63 |     11486 |               2952 |            0.0586043 |                          0.993902 |                   0.543618  |     0.094705  |
| mlp                      |    64 |     10030 |               2812 |            0.11771   |                          0.949147 |                   0.0328016 |     0.169066  |
| mlp                      |    65 |      9737 |               2774 |            0.0212689 |                          0.998919 |                   0.0211564 |     0.0323948 |
| ridge                    |    58 |     11977 |               4788 |            0.0611947 |                          0.999791 |                   0.808466  |     0.101059  |
| ridge                    |    59 |     10866 |               2023 |            0.0968858 |                          0.992091 |                   0.574544  |     0.274922  |
| ridge                    |    60 |      9097 |               1663 |            0.0877931 |                          0.992183 |                   0.387051  |     0.279083  |
| ridge                    |    61 |      9744 |               1842 |            0.100977  |                          0.987514 |                   0.383518  |     0.282223  |
| ridge                    |    62 |     10021 |               1887 |            0.101219  |                          0.988341 |                   0.403553  |     0.270283  |
| ridge                    |    63 |     11486 |               2952 |            0.0809621 |                          0.992547 |                   0.543618  |     0.156047  |
| ridge                    |    64 |     10030 |               2812 |            0.0746799 |                          0.993954 |                   0.0328016 |     0.140198  |
| ridge                    |    65 |      9737 |               2774 |            0.0648882 |                          0.993511 |                   0.0211564 |     0.104758  |
| shuffled_target_gbt      |    58 |     11977 |               4788 |            0.60401   |                          1        |                   0.927611  |     0.813738  |
| shuffled_target_gbt      |    59 |     10866 |               2023 |            0.539298  |                          1        |                   0.659948  |     1.67615   |
| shuffled_target_gbt      |    60 |      9097 |               1663 |            0.590499  |                          1        |                   0.556227  |     1.53667   |
| shuffled_target_gbt      |    61 |      9744 |               1842 |            0.590662  |                          0.993485 |                   0.551006  |     1.55095   |
| shuffled_target_gbt      |    62 |     10021 |               1887 |            0.590355  |                          0.987811 |                   0.4288    |     1.50409   |
| shuffled_target_gbt      |    63 |     11486 |               2952 |            0.483062  |                          0.99729  |                   0.037611  |     1.11212   |
| shuffled_target_gbt      |    64 |     10030 |               2812 |            0.512447  |                          0.577881 |                   0.79003   |     1.02721   |
| shuffled_target_gbt      |    65 |      9737 |               2774 |            0.533886  |                          0.570296 |                   0.817192  |     0.940896  |
| strong_traditional_huber |    58 |     11977 |               4788 |            0.0148287 |                          0.998747 |                   0.927611  |     0.0107432 |
| strong_traditional_huber |    59 |     10866 |               2023 |            0.0350964 |                          0.994068 |                   0.66547   |     0.201913  |
| strong_traditional_huber |    60 |      9097 |               1663 |            0.0318701 |                          0.995189 |                   0.556227  |     0.132507  |
| strong_traditional_huber |    61 |      9744 |               1842 |            0.0363735 |                          0.993485 |                   0.383518  |     0.130227  |
| strong_traditional_huber |    62 |     10021 |               1887 |            0.0386857 |                          0.993641 |                   0.403553  |     0.138115  |
| strong_traditional_huber |    63 |     11486 |               2952 |            0.0281165 |                          0.995257 |                   0.543618  |     0.0592233 |
| strong_traditional_huber |    64 |     10030 |               2812 |            0.0295164 |                          0.993954 |                   0         |     0.0394467 |
| strong_traditional_huber |    65 |      9737 |               2774 |            0.0230714 |                          0.993511 |                   0         |     0.0265724 |
| wavegate_interval_net    |    58 |     11977 |               4788 |            0.395781  |                          1        |                   0.908575  |     3.63815   |
| wavegate_interval_net    |    59 |     10866 |               2023 |            0.334652  |                          0.976767 |                   0.694368  |     0.509282  |
| wavegate_interval_net    |    60 |      9097 |               1663 |            0.312688  |                          0.971137 |                   0.691547  |     0.615615  |
| wavegate_interval_net    |    61 |      9744 |               1842 |            0.408252  |                          0.956026 |                   0.516626  |     0.701641  |
| wavegate_interval_net    |    62 |     10021 |               1887 |            0.266031  |                          0.949656 |                   0.403553  |     0.403718  |
| wavegate_interval_net    |    63 |     11486 |               2952 |            0.254065  |                          0.958672 |                   0.543096  |     0.350801  |
| wavegate_interval_net    |    64 |     10030 |               2812 |            0.487553  |                          0.513158 |                   0         |     5.1155    |
| wavegate_interval_net    |    65 |      9737 |               2774 |            0.27938   |                          0.973324 |                   0.0211564 |     0.245592  |

## 7. Atom Systematics

| lowering_axis   | anomaly_taxon     | saturation_stratum   | method                   |   pulse_rows |   event_rows |   atom_flip_rate |   atom_band_accuracy |
|:----------------|:------------------|:---------------------|:-------------------------|-------------:|-------------:|-----------------:|---------------------:|
| dynamic_only    | baseline_lowering | below_sat            | gradient_boosted_trees   |        13180 |         8868 |       0.00439783 |             0.995602 |
| median_selected | baseline_lowering | below_sat            | gradient_boosted_trees   |        15345 |        10546 |       0.0113787  |             0.988621 |
| median_selected | baseline_lowering | sat_boundary         | gradient_boosted_trees   |         1791 |         1777 |       0.0157569  |             0.984243 |
| dynamic_only    | baseline_lowering | below_sat            | strong_traditional_huber |        13180 |         8868 |       0.0258232  |             0.974177 |
| median_selected | baseline_lowering | below_sat            | strong_traditional_huber |        15345 |        10546 |       0.0457045  |             0.954295 |
| median_selected | baseline_lowering | sat_boundary         | strong_traditional_huber |         1791 |         1777 |       0.073157   |             0.926843 |
| median_selected | template_shift    | sat_boundary         | gradient_boosted_trees   |         5309 |         5212 |       0.00498849 |             0.995012 |
| median_selected | template_shift    | below_sat            | gradient_boosted_trees   |       117132 |        69683 |       0.006056   |             0.993944 |
| median_selected | template_shift    | below_sat            | strong_traditional_huber |       117132 |        69683 |       0.00621385 |             0.993786 |
| median_selected | template_shift    | sat_boundary         | strong_traditional_huber |         5309 |         5212 |       0.0076746  |             0.992325 |

The main systematic is that nominal median-selected template-shift pulses dominate event count, while large baseline-lowering and saturation-boundary atoms dominate interval width and abstention.  Thus a method can have excellent charge closure yet remain operationally weak if its intervals do not contain the correct PID band near the boundaries.

## 8. Caveats

- The PID score is a monotone topology proxy, not an externally calibrated proton/deuteron truth label.
- P04r reuses P04q frozen run-held-out predictions instead of refitting every model, so the comparison tests downstream propagation of an existing charge-interval panel.
- The conformal intervals are empirical and support-cell conditional; sparse atom exchangeability remains an assumption, especially for boundary events.
- The run-block bootstrap has only eight held-out runs, so CIs are stability intervals rather than asymptotic guarantees.
- A shuffled-target sentinel is retained to expose leakage-scale failures but cannot validate physical interpretation by itself.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04r_1781150559_1026_0e031a32_pid_boundary_charge_intervals.py --config configs/p04r_1781150559_1026_0e031a32_pid_boundary_charge_intervals.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `pid_boundary_method_summary.csv`, `pid_boundary_by_run.csv`, `atom_pid_systematics.csv`, `event_scores_sample.csv`, and this `REPORT.md`.

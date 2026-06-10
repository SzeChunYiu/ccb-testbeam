# S16g: Traditional Baseline Repair for P04f Anomaly Strata

- **Ticket:** `1781033470.1792.71446312`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/hrdb_run_*.root`; P09a labels are recomputed from the same raw ROOT rows.
- **Run split:** train on Sample I plus run 64; hold out Sample II analysis runs `58, 59, 60, 61, 62, 63, 65`.
- **Primary target:** paired odd-channel inverted duplicate-readout positive charge, `sum(max(-odd,0))`.

## Abstract

Raw selected-pulse reproduction passes exactly (640,737 vs 640,737). The held-out winner is strong_huber_baseline_repair with res68 0.0110 and run-block CI [0.008671793390406786, 0.013669986675151999]; the best traditional baseline-repair comparator is strong_huber_baseline_repair with res68 0.0110. P09a baseline-excursion and early-pretrigger rows remain measurable stress strata under run/stave/amplitude/peak/saturation matching, so the safest interpretation is a duplicate-readout electronics repair benchmark rather than external energy recovery.

## 1. Raw ROOT Reproduction Gate

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

The reproduction gate reshapes `HRDv` into eight 18-sample channels, subtracts the median of samples 0--3 independently per channel, and selects B2/B4/B6/B8 even-channel pulses with peak amplitude above 1000 ADC. Odd-channel target quality cuts are applied only after this count is reproduced.

## 2. Estimand and Metrics

For pulse record \(i\), the duplicate-readout charge target is

\[ y_i = \sum_t \max[-o_i(t),0], \]

where \(o_i(t)\) is the baseline-subtracted paired odd-channel waveform. Each method predicts \(\hat y_i\). The fractional residual is

\[ r_i = \frac{\hat y_i-y_i}{\max(y_i,1)}. \]

The primary metric is \(Q_{0.68}(|r_i|)\), the 68th percentile of absolute fractional residuals. Secondary metrics are median residual bias, full RMS, catastrophic rate \(P(|r_i|>0.25)\), and timing-tail mean absolute residual. Confidence intervals resample held-out runs with replacement, preserving within-run correlations.

## 3. P09a Strata

P09a baseline-excursion and novel early-pretrigger labels are recomputed after a second raw ROOT scan and exact row alignment on `(run,eventno,evt,stave)`. The frozen thresholds used by the taxonomy are:

| threshold               |       value |
|:------------------------|------------:|
| amplitude_adc_q995      | 9505.5      |
| amplitude_adc_q999      | 9605.5      |
| saturation_count_q995   |    2        |
| post_peak_min_q001      |   -4.55857  |
| baseline_mad_q995       | 1975.5      |
| abs_baseline_slope_q995 | 6414.52     |
| late_fraction_q999      |    0.999342 |
| timing_span_dup_q990    |   18        |
| secondary_peak_q999     |    0.999373 |
| undershoot_area_q001    |  -39.3171   |
| width_half_q995         |   12        |
| q_template_rmse_q995    |    2.24423  |
| q_template_rmse_q999    |    3.01372  |

## 4. Methods

### Traditional Baseline Repair

- `repair_median_sample_logcal`: per-stave log calibration of the positive charge after subtracting the median of pretrigger samples 0--3.
- `repair_robust_pretrigger_logcal`: same calibration after dropping the most deviant pretrigger sample and averaging the remaining three.
- `repair_slope_corrected_logcal`: sample-wise subtraction of the linear baseline trend fitted on samples 0--3.
- `repair_train_run_template_pedestal_logcal`: subtracts a train-run pedestal-shape template in `(stave, amplitude bin, peak bin, saturation)` cells before charge integration.
- `strong_huber_baseline_repair`: Huber log-charge regression on hand-built pulse, saturation, and baseline-repair summaries.

### ML/NN Comparators

Ridge regression, histogram gradient-boosted trees, a tabular MLP, a waveform 1D-CNN, `wave_atom_net`, and the new `baseline_gated_cnn_new` are trained on the same train-run rows. Features exclude event identifiers, run id, odd-channel target samples, and target charge.

## 5. Held-out Benchmark

| method                                    |      n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |   full_rms_frac |   catastrophic_rate | run_block_catastrophic_rate_ci95             |   timing_tail_abs_frac_mean |
|:------------------------------------------|-------:|-------------------:|-----------------:|:---------------------------------------------|----------------:|--------------------:|:---------------------------------------------|----------------------------:|
| strong_huber_baseline_repair              | 125078 |         0.00160775 |        0.0110054 | [0.008671793390406786, 0.013669986675151999] |       0.296498  |           0.0670542 | [0.05181977005087834, 0.07859360330814653]   |                   0.0496813 |
| hgb_waveform_atoms                        | 125078 |         0.00046565 |        0.0155161 | [0.0128064860215057, 0.017964222993404576]   |       0.0448325 |           0.0049729 | [0.003174576009087605, 0.006411406102834408] |                   0.015622  |
| ridge_waveform_atoms                      | 125078 |         0.00365003 |        0.0237628 | [0.021321313988417388, 0.02562837710045279]  |       0.133463  |           0.0406466 | [0.027452303257831767, 0.04837350822496909]  |                   0.0343931 |
| wave_atom_net                             | 125078 |        -0.00390812 |        0.0286174 | [0.023452913854271173, 0.03320684695988893]  |       0.124729  |           0.0419978 | [0.02971411903728988, 0.04906028058369935]   |                   0.0372041 |
| mlp_waveform_atoms                        | 125078 |         0.00964408 |        0.0317933 | [0.02590196207165718, 0.035645480059087284]  |       0.103819  |           0.028902  | [0.01849382372439008, 0.035476404093414626]  |                   0.030891  |
| baseline_gated_cnn_new                    | 125078 |         0.00854846 |        0.0414961 | [0.035481039062142374, 0.04689733967185023]  |       0.147494  |           0.0493772 | [0.03517702067971723, 0.058017507761971135]  |                   0.0479921 |
| repair_median_sample_logcal               | 125078 |        -0.107371   |        0.186395  | [0.16842700713439768, 0.20069946555884513]   |       1.75017   |           0.21202   | [0.17043196611275313, 0.24090995759793118]   |                   0.176064  |
| repair_robust_pretrigger_logcal           | 125078 |        -0.107371   |        0.186395  | [0.16931827727145224, 0.20147268416408629]   |       1.75017   |           0.21202   | [0.16880868436295776, 0.24007119337098276]   |                   0.176064  |
| repair_train_run_template_pedestal_logcal | 125078 |        -0.113035   |        0.193432  | [0.1767505648269192, 0.2078317069717204]     |       2.01803   |           0.220215  | [0.17710093120812215, 0.24751695508898375]   |                   0.183122  |
| cnn_1d_waveform                           | 125078 |        -0.0543775  |        0.283038  | [0.21957983009517193, 0.33568891167640735]   |       1.43729   |           0.351053  | [0.2861121046075607, 0.387757561155503]      |                   0.275144  |
| repair_slope_corrected_logcal             | 125078 |         0.0586958  |        0.300542  | [0.2644430404137149, 0.3323679810834018]     |       4.00627   |           0.387654  | [0.33832653477181684, 0.42736915055920555]   |                   1.20178   |
| adaptive_template_logcal                  | 125078 |         0.138055   |        0.539309  | [0.4762847830764746, 0.6366811046368093]     |       2.92618   |           0.561634  | [0.4928006277040471, 0.6006185303545106]     |                   0.438423  |

The winner by held-out \(Q_{0.68}(|r|)\) is `strong_huber_baseline_repair`. The strongest traditional method is `strong_huber_baseline_repair`.

## 6. P09a-Stratum Benchmark

| stratum                | method                        |      n |   bias_median_frac |   res68_abs_frac | run_block_res68_ci95                         |   catastrophic_rate |
|:-----------------------|:------------------------------|-------:|-------------------:|-----------------:|:---------------------------------------------|--------------------:|
| all_valid              | repair_median_sample_logcal   | 125078 |       -0.107371    |       0.186395   | [0.17013586745994505, 0.20199310704472317]   |          0.21202    |
| all_valid              | repair_slope_corrected_logcal | 125078 |        0.0586958   |       0.300542   | [0.2611962194041122, 0.3361293170428104]     |          0.387654   |
| all_valid              | strong_huber_baseline_repair  | 125078 |        0.00160775  |       0.0110054  | [0.008515774793252743, 0.013524745382393332] |          0.0670542  |
| all_valid              | hgb_waveform_atoms            | 125078 |        0.00046565  |       0.0155161  | [0.012423056412627836, 0.01812383085711047]  |          0.0049729  |
| all_valid              | baseline_gated_cnn_new        | 125078 |        0.00854846  |       0.0414961  | [0.03459978476166725, 0.047064665943384175]  |          0.0493772  |
| baseline_excursion     | repair_median_sample_logcal   |    974 |        6.44525     |       7.73117    | [7.359368149607497, 8.290391377022402]       |          0.966119   |
| baseline_excursion     | repair_slope_corrected_logcal |    974 |        1.19828     |       1.68596    | [1.6020113264167246, 1.9049153717546379]     |          0.86653    |
| baseline_excursion     | strong_huber_baseline_repair  |    974 |       -0.10857     |       0.524071   | [0.49993403371947887, 0.5539920998340512]    |          0.679671   |
| baseline_excursion     | hgb_waveform_atoms            |    974 |       -0.00178027  |       0.0857696  | [0.07491699171213742, 0.09563667536724683]   |          0.0728953  |
| baseline_excursion     | baseline_gated_cnn_new        |    974 |       -0.0125665   |       0.400061   | [0.3706616571843625, 0.4511890709400177]     |          0.560575   |
| novel_early_pretrigger | repair_median_sample_logcal   |   4658 |        4.71182     |       6.99023    | [6.650742785071472, 7.142977621583748]       |          0.933877   |
| novel_early_pretrigger | repair_slope_corrected_logcal |   4658 |        1.61016     |       2.79369    | [2.7049349668733793, 2.947254342406532]      |          0.840919   |
| novel_early_pretrigger | strong_huber_baseline_repair  |   4658 |        0.532425    |       0.914305   | [0.8602200207135114, 0.955257974319793]      |          0.717475   |
| novel_early_pretrigger | hgb_waveform_atoms            |   4658 |       -0.00292317  |       0.0896804  | [0.08399584324662308, 0.0961848732174363]    |          0.0498068  |
| novel_early_pretrigger | baseline_gated_cnn_new        |   4658 |       -0.114135    |       0.496572   | [0.49060222607851034, 0.5027100828886032]    |          0.676041   |
| other_valid            | repair_median_sample_logcal   | 119446 |       -0.11123     |       0.174626   | [0.16136491201455902, 0.1880862395432326]    |          0.17772    |
| other_valid            | repair_slope_corrected_logcal | 119446 |        0.0508818   |       0.282098   | [0.2504633620263536, 0.3092386743636631]     |          0.366073   |
| other_valid            | strong_huber_baseline_repair  | 119446 |        0.00138326  |       0.00973177 | [0.007993936065704293, 0.01129068615045068]  |          0.0366944  |
| other_valid            | hgb_waveform_atoms            | 119446 |        0.000483237 |       0.0143403  | [0.011860107742987529, 0.016463899964209976] |          0.00267066 |
| other_valid            | baseline_gated_cnn_new        | 119446 |        0.00883912  |       0.0386904  | [0.03358985937386752, 0.04307160601019861]   |          0.0207709  |

## 7. Matched Stratum Effects

Controls are sampled within run, stave, amplitude bin, peak bin, and saturation. Positive deltas mean the P09a stratum has larger residuals than matched non-P09a controls.

| method                        | label                       |   n_cells |   n_exposed |   n_control |   delta_abs_frac | delta_abs_frac_ci95                          |   delta_catastrophic_rate |
|:------------------------------|:----------------------------|----------:|------------:|------------:|-----------------:|:---------------------------------------------|--------------------------:|
| strong_huber_baseline_repair  | p09a_baseline_excursion     |        35 |         806 |        6602 |        0.385942  | [0.33656687308069316, 0.4406678597639565]    |                 0.589868  |
| strong_huber_baseline_repair  | p09a_novel_early_pretrigger |        78 |        4401 |        9809 |        0.649546  | [0.6041627632569112, 0.6861198519826038]     |                 0.496615  |
| repair_median_sample_logcal   | p09a_baseline_excursion     |        35 |         806 |        6602 |        5.6225    | [5.200628543911314, 6.031977803956693]       |                 0.224843  |
| repair_median_sample_logcal   | p09a_novel_early_pretrigger |        78 |        4401 |        9809 |        4.31935   | [4.112017846461279, 4.462997221008386]       |                 0.0183658 |
| repair_slope_corrected_logcal | p09a_baseline_excursion     |        35 |         806 |        6602 |        3.15923   | [2.44044235023659, 4.014253643540832]        |                -0.0307535 |
| repair_slope_corrected_logcal | p09a_novel_early_pretrigger |        78 |        4401 |        9809 |        4.51862   | [4.249083788056662, 4.904618601234807]       |                -0.0440523 |
| hgb_waveform_atoms            | p09a_baseline_excursion     |        35 |         806 |        6602 |        0.0513574 | [0.03770923260842928, 0.0715974012712837]    |                 0.0648558 |
| hgb_waveform_atoms            | p09a_novel_early_pretrigger |        78 |        4401 |        9809 |        0.0271256 | [0.021493127748454223, 0.032214789685217016] |                 0.0334778 |
| baseline_gated_cnn_new        | p09a_baseline_excursion     |        35 |         806 |        6602 |        0.258051  | [0.23268323014124057, 0.2875373630665012]    |                 0.501236  |
| baseline_gated_cnn_new        | p09a_novel_early_pretrigger |        78 |        4401 |        9809 |        0.259397  | [0.23608763035198654, 0.2716394826430463]    |                 0.519414  |

## 8. Per-run Stability

| method                       | split          |     n |   res68_abs_frac |   catastrophic_rate |   timing_tail_abs_frac_mean |
|:-----------------------------|:---------------|------:|-----------------:|--------------------:|----------------------------:|
| strong_huber_baseline_repair | heldout_run_58 | 16780 |       0.00616985 |         0.0189511   |                   0.0369797 |
| strong_huber_baseline_repair | heldout_run_59 | 21374 |       0.01493    |         0.0862263   |                   0.0560175 |
| strong_huber_baseline_repair | heldout_run_60 | 17021 |       0.0137758  |         0.0752012   |                   0.0619862 |
| strong_huber_baseline_repair | heldout_run_61 | 18963 |       0.0131801  |         0.0696092   |                   0.0486571 |
| strong_huber_baseline_repair | heldout_run_62 | 19088 |       0.0134509  |         0.0750733   |                   0.0479668 |
| strong_huber_baseline_repair | heldout_run_63 | 18814 |       0.0108842  |         0.0738812   |                   0.0514066 |
| strong_huber_baseline_repair | heldout_run_65 | 13038 |       0.00921271 |         0.0615892   |                   0.0393589 |
| ridge_waveform_atoms         | heldout_run_58 | 16780 |       0.019122   |         0.0104291   |                   0.0333991 |
| ridge_waveform_atoms         | heldout_run_59 | 21374 |       0.0267552  |         0.0509965   |                   0.0361799 |
| ridge_waveform_atoms         | heldout_run_60 | 17021 |       0.0260631  |         0.0512896   |                   0.0383216 |
| ridge_waveform_atoms         | heldout_run_61 | 18963 |       0.0253796  |         0.0469335   |                   0.0298882 |
| ridge_waveform_atoms         | heldout_run_62 | 19088 |       0.0252789  |         0.0481978   |                   0.0338408 |
| ridge_waveform_atoms         | heldout_run_63 | 18814 |       0.0234193  |         0.0394919   |                   0.0378884 |
| ridge_waveform_atoms         | heldout_run_65 | 13038 |       0.0219082  |         0.0301427   |                   0.0306875 |
| hgb_waveform_atoms           | heldout_run_58 | 16780 |       0.00897662 |         0.000715137 |                   0.0118876 |
| hgb_waveform_atoms           | heldout_run_59 | 21374 |       0.0183884  |         0.00743894  |                   0.0185717 |
| hgb_waveform_atoms           | heldout_run_60 | 17021 |       0.0174158  |         0.00364256  |                   0.0147789 |
| hgb_waveform_atoms           | heldout_run_61 | 18963 |       0.0190366  |         0.00606444  |                   0.0157926 |
| hgb_waveform_atoms           | heldout_run_62 | 19088 |       0.0178294  |         0.00565801  |                   0.0162446 |
| hgb_waveform_atoms           | heldout_run_63 | 18814 |       0.0148293  |         0.00611247  |                   0.0164744 |
| hgb_waveform_atoms           | heldout_run_65 | 13038 |       0.0127709  |         0.00391164  |                   0.0138807 |
| cnn_1d_waveform              | heldout_run_58 | 16780 |       0.169849   |         0.17062     |                   0.240427  |
| cnn_1d_waveform              | heldout_run_59 | 21374 |       0.370384   |         0.404276    |                   0.305938  |
| cnn_1d_waveform              | heldout_run_60 | 17021 |       0.317284   |         0.382645    |                   0.264255  |
| cnn_1d_waveform              | heldout_run_61 | 18963 |       0.313804   |         0.387439    |                   0.248915  |
| cnn_1d_waveform              | heldout_run_62 | 19088 |       0.330204   |         0.390455    |                   0.265639  |
| cnn_1d_waveform              | heldout_run_63 | 18814 |       0.272145   |         0.338631    |                   0.298517  |
| cnn_1d_waveform              | heldout_run_65 | 13038 |       0.320191   |         0.362095    |                   0.307477  |

## 9. Leakage Sentinels and Systematics

- Train/held-out run overlap: `[]`.
- Train/held-out `(run,event,stave)` key overlap: `0`.
- Invalid odd-target rows removed after reproduction: `255`.
- Shuffled-target HGB res68: `1.2462`.
- Topology-only ridge res68: `0.3444`.
- Baseline-only ridge res68: `1.2205`.
- Saturation-only ridge res68: `0.2822`.

The target is duplicate-readout electronics closure, not deposited-energy truth. Since baseline-repair features come from the same even waveform as the charge estimate, improvements support an electronics-correction interpretation but do not by themselves prove external energy transfer. The held-out set contains seven runs, so run-block intervals are the uncertainty scale emphasized in all tables.

## 10. Caveats

- P09a labels are deterministic taxonomy labels, not hand-reviewed causal categories for every event.
- Neural models are laptop-scale capacity checks with fixed hyperparameters; they are not an exhaustive architecture search.
- The train-run pedestal template can only repair pretrigger shapes represented in train support; unseen baseline modes should be treated as out-of-support.
- Same-event duplicate closure can be much easier than external charge prediction because both channels share electronics and event conditions.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781033470_1792_71446312_baseline_repair_p04f.py --config configs/s16g_1781033470_1792_71446312_baseline_repair_p04f.json
```

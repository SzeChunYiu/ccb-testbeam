# P04w External-Charge Abstention Frontier

- **Ticket:** `1781065299.620.6b5f516e`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.
- **Split:** leave-one-run-out by run; all bootstrap intervals resample held-out run blocks.
- **Target:** event-matched selected A1/A3 positive-lobe charge on rows with selected B2 and selected A1 or A3.

## 0. Question

Can any support-aware abstention frontier make B-stack waveform charge a safe external proxy for downstream energy/PID labels, or does the A-stack target remain indistinguishable from topology/shuffled sentinels?

## 1. Reproduction From Raw ROOT

The B-stack gate is rebuilt directly from `HRDv`: for each event and B stave, the channel median over samples 0--3 is subtracted and the pulse is selected when the corrected peak exceeds 1000 ADC. The A-stack gate uses the same baseline rule on A1/A3. No sorted-table target is used for the gate.

| quantity | expected | reproduced | delta | tolerance | pass |
|---|---:|---:|---:|---:|:---|
| B-stack selected pulse records | 640,737 | 640,737 | +0 | 0 | true |

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

As a ticket-local reproduction of the previous external-charge number, the P04c leave-one-run-out A/B charge-transfer benchmark is rerun on the same raw ROOT rows:

| method                      |    n |   bias_median_frac |   res68_abs_frac | res68_ci95                               |   full_rms_frac |   within_25pct |
|:----------------------------|-----:|-------------------:|-----------------:|:-----------------------------------------|----------------:|---------------:|
| b2_loglinear                | 4055 |         -0.0476348 |         0.520285 | [0.5042076716660516, 0.5379899217206028] |        0.84526  |       0.344513 |
| charge_transfer_ridge       | 4055 |         -0.0474201 |         0.519271 | [0.5070335247751083, 0.5395311609280796] |        0.842762 |       0.343527 |
| b_waveform_extra_trees      | 4055 |         -0.0465142 |         0.520437 | [0.5064227771915828, 0.5389865814252444] |        0.846084 |       0.346486 |
| shuffled_target_extra_trees | 4055 |         -0.0460192 |         0.519843 | [0.5079350572985499, 0.5344939770913222] |        0.847478 |       0.340074 |

The reproduced P04c traditional ridge res68 is `0.5193` and the waveform ExtraTrees res68 is `0.5204` on `4,055` rows.

## 2. Methods

For event i, the external target is

`y_i = sum_{a in {A1,A3}} 1[A_a>1000] sum_t max(A_{iat}, 0)`.

Every model predicts `log(y_i)` from B-stack waveform and topology features only. Event number, run number, A-stack charge, A-stack selected flags, and the target are excluded from features. The residual reported in all tables is

`e_i(m) = (hat y_i(m) - y_i) / max(y_i, 1)`

with primary width `res68 = Q_0.68(|e_i|)`. The traditional panel is a topology/support-cell median and a robust Huber log-charge transfer using B2/B-stack charge, amplitude, peak phase, width, late/early fractions, saturation, baseline, and topology atoms. The ML/NN panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, and the new support-gated residual CNN. The new architecture is appropriate here because the question is explicitly about support atoms: it convolves normalized B2/B4/B6/B8 waveforms and fold-local residual-template channels, then gates the latent representation with scalar support features before regression.

The abstention score is train-fold conformal risk: within each support cell, the 68th percentile of train-run absolute fractional residual is assigned to held-out rows, with a penalty for cells below strong support. This uses training targets only and is fixed before looking at the held-out target residuals.

## 3. Head-To-Head Benchmark

| method                     | family           |    n |   bias_median_frac | bias_ci95                                      |   res68_abs_frac | res68_ci95                                 |   full_rms_frac | full_rms_ci95                            |   within_10pct |   within_25pct |
|:---------------------------|:-----------------|-----:|-------------------:|:-----------------------------------------------|-----------------:|:-------------------------------------------|----------------:|:-----------------------------------------|---------------:|---------------:|
| topology_median            | traditional      | 4055 |        -0.00193406 | [-0.023648830250350864, 0.022033567973357444]  |         0.381402 | [0.36524143903490036, 0.39494831122836876] |        0.6699   | [0.5781603315740257, 0.7974759378398638] |       0.194821 |       0.470037 |
| strong_huber_transfer      | traditional      | 4055 |        -0.0143204  | [-0.031522607681081415, 0.0066416703888268385] |         0.354272 | [0.34352534818707625, 0.36674368176601363] |        0.588912 | [0.5278007061004806, 0.6825814184473148] |       0.195808 |       0.494451 |
| ridge                      | ml               | 4055 |        -0.039456   | [-0.05970728628565902, -0.020534400821250656]  |         0.35907  | [0.3495729693581149, 0.36888255829634664]  |        0.563354 | [0.5002331519172452, 0.6635600599563982] |       0.197534 |       0.475462 |
| gradient_boosted_trees     | ml               | 4055 |        -0.0463165  | [-0.06052090967704887, -0.027428114748121502]  |         0.360203 | [0.3485397132987771, 0.3722438332012629]   |        0.570509 | [0.5045229302639455, 0.6522979554660829] |       0.19852  |       0.481134 |
| mlp                        | ml               | 4055 |        -0.042221   | [-0.061413058819288026, -0.024985241305924742] |         0.385088 | [0.37438122072611324, 0.39777275111641286] |        0.600078 | [0.544423884531305, 0.6971938576887706]  |       0.18397  |       0.456227 |
| 1d_cnn                     | nn               | 4055 |        -0.00697367 | [-0.023636824456169957, 0.009070086661006995]  |         0.366955 | [0.3531009636998877, 0.38289159314043486]  |        0.645082 | [0.5810041364958114, 0.74921301810953]   |       0.197041 |       0.494205 |
| support_gated_residual_cnn | new_architecture | 4055 |        -0.00408348 | [-0.021611483073703988, 0.020104875082250877]  |         0.363855 | [0.3492059400465913, 0.37939114057696877]  |        0.62813  | [0.5651052202117464, 0.7235445899713325] |       0.194821 |       0.501603 |
| topology_only_sentinel     | negative_control | 4055 |        -0.042667   | [-0.05804805635726696, -0.023618018407260407]  |         0.351925 | [0.3417595497423454, 0.36609890356167535]  |        0.559756 | [0.499988369057981, 0.6646109915506268]  |       0.195561 |       0.485327 |
| shuffled_target_hgb        | negative_control | 4055 |        -0.0424156  | [-0.06146795671370704, -0.012145602703422187]  |         0.526496 | [0.5135898082126807, 0.5418290803884698]   |        0.836595 | [0.7454470988761924, 0.9754837957177579] |       0.136128 |       0.353391 |

Point-estimate winner among non-sentinel methods: `strong_huber_transfer` with res68 `0.3543`. Best traditional method: `strong_huber_transfer` at `0.3543`. Best ML/NN method: `ridge` at `0.3591`. The shuffled-target HGB sentinel is `0.5265`.

## 4. Abstention Frontier

The table below shows risk-ranked accepted fractions for the point-estimate winner. A valid production frontier would need lower res68, useful accepted support, and a negative real-minus-shuffled separation.

| method                |   accepted_fraction |   abstained_fraction |    n |   n_runs |   bias_median_frac |   res68_abs_frac | res68_ci95                               |   full_rms_frac |   within_10pct |   within_25pct |   shuffled_res68_abs_frac |   topology_only_res68_abs_frac |   real_minus_shuffled_res68 |   real_minus_topology_res68 |
|:----------------------|--------------------:|---------------------:|-----:|---------:|-------------------:|-----------------:|:-----------------------------------------|----------------:|---------------:|---------------:|--------------------------:|-------------------------------:|----------------------------:|----------------------------:|
| strong_huber_transfer |            1        |             0        | 4055 |       32 |        -0.0143204  |         0.354272 | [0.3437922330312273, 0.3653180079875444] |        0.588912 |       0.195808 |       0.494451 |                  0.526496 |                       0.351925 |                   -0.172224 |                  0.00234707 |
| strong_huber_transfer |            0.749938 |             0.250062 | 3041 |       32 |        -0.0136603  |         0.347845 | [0.3381640902929588, 0.3630306471279187] |        0.599373 |       0.20125  |       0.50148  |                  0.520703 |                       0.345493 |                   -0.172857 |                  0.00235264 |
| strong_huber_transfer |            0.500123 |             0.499877 | 2028 |       32 |        -0.0108661  |         0.357203 | [0.3403460703176651, 0.372617003718216]  |        0.644995 |       0.195759 |       0.502465 |                  0.514618 |                       0.350343 |                   -0.157415 |                  0.00686044 |
| strong_huber_transfer |            0.250062 |             0.749938 | 1014 |       30 |        -0.00638046 |         0.359891 | [0.3468343231587485, 0.3759489598115471] |        0.584901 |       0.191321 |       0.499014 |                  0.524581 |                       0.355096 |                   -0.16469  |                  0.00479455 |

Largest or best support cells for the winner:

| category           | value                                                                    |    n |   n_runs |   bias_median_frac |   res68_abs_frac |   shuffled_res68_abs_frac |   topology_only_res68_abs_frac |   real_minus_shuffled_res68 |   real_minus_topology_res68 | support_call   |
|:-------------------|:-------------------------------------------------------------------------|-----:|---------:|-------------------:|-----------------:|--------------------------:|-------------------------------:|----------------------------:|----------------------------:|:---------------|
| support_cell       | B2_only|2000_3000|all_B_amp_lt7000|broad_saturation_like|downstream_none |   75 |       17 |        -0.0378     |         0.317631 |                  0.542932 |                       0.320345 |                   -0.225301 |                -0.00271377  | weak_or_null   |
| support_cell       | B2_only|3000_5000|all_B_amp_lt7000|dropout_like|downstream_none          |   54 |       18 |        -0.0693144  |         0.319387 |                  0.480003 |                       0.297684 |                   -0.160616 |                 0.0217029   | weak_or_null   |
| support_cell       | B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none        |  253 |       23 |        -0.0173767  |         0.319826 |                  0.493867 |                       0.331551 |                   -0.174041 |                -0.0117244   | weak_or_null   |
| b2_amp_bin         | 1000_2000                                                                |  496 |       26 |        -0.0239028  |         0.326528 |                  0.512561 |                       0.330032 |                   -0.186033 |                -0.00350405  | weak_or_null   |
| topology_pattern   | B2_B4                                                                    |  102 |       21 |        -0.0280215  |         0.332811 |                  0.519594 |                       0.298733 |                   -0.186783 |                 0.0340776   | weak_or_null   |
| support_cell       | B2_only|3000_5000|all_B_amp_lt7000|late_tail_high|downstream_none        |  125 |       20 |        -0.00992149 |         0.334717 |                  0.406584 |                       0.332847 |                   -0.071867 |                 0.00186964  | weak_or_null   |
| support_cell       | B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none          |  184 |       20 |        -0.0498018  |         0.33998  |                  0.513381 |                       0.344401 |                   -0.173401 |                -0.00442166  | weak_or_null   |
| support_cell       | B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none        |  278 |       22 |         0.00865372 |         0.346384 |                  0.505369 |                       0.344068 |                   -0.158984 |                 0.0023159   | weak_or_null   |
| baseline_bin       | large                                                                    | 1395 |       31 |        -0.0203568  |         0.348707 |                  0.525624 |                       0.343326 |                   -0.176916 |                 0.00538095  | weak_or_null   |
| saturation_stratum | all_B_amp_lt7000                                                         | 3134 |       32 |        -0.0115053  |         0.349763 |                  0.520253 |                       0.347521 |                   -0.170489 |                 0.00224208  | weak_or_null   |
| support_cell       | B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none |  957 |       30 |         0.00442005 |         0.350446 |                  0.533042 |                       0.349935 |                   -0.182597 |                 0.000510771 | weak_or_null   |
| support_cell       | B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|downstream_none |  888 |       30 |        -0.0144302  |         0.351756 |                  0.520845 |                       0.346353 |                   -0.169089 |                 0.00540308  | weak_or_null   |
| anomaly_stratum    | broad_saturation_like                                                    | 2271 |       32 |        -0.00991003 |         0.351813 |                  0.529109 |                       0.348639 |                   -0.177296 |                 0.00317476  | weak_or_null   |
| peak_phase_bin     | early_le5                                                                | 1045 |       28 |        -0.0274628  |         0.351855 |                  0.521777 |                       0.339422 |                   -0.169923 |                 0.0124324   | weak_or_null   |
| b2_amp_bin         | 5000_7000                                                                |  953 |       30 |        -0.00744519 |         0.351964 |                  0.520162 |                       0.346633 |                   -0.168198 |                 0.00533143  | weak_or_null   |
| peak_phase_bin     | late_ge12                                                                |   61 |       14 |        -0.0256994  |         0.352113 |                  0.501188 |                       0.334623 |                   -0.149075 |                 0.0174902   | weak_or_null   |
| baseline_bin       | quiet                                                                    | 1851 |       32 |        -0.0131546  |         0.352381 |                  0.519907 |                       0.351649 |                   -0.167526 |                 0.00073238  | weak_or_null   |
| q_template_bin     | low                                                                      |  201 |       20 |        -0.0394148  |         0.35307  |                  0.487291 |                       0.360071 |                   -0.134221 |                -0.00700133  | weak_or_null   |
| b2_amp_bin         | 3000_5000                                                                | 1212 |       31 |        -0.00853395 |         0.353129 |                  0.524969 |                       0.349662 |                   -0.171841 |                 0.003467    | weak_or_null   |
| topology_pattern   | B2_only                                                                  | 3889 |       32 |        -0.0139309  |         0.353922 |                  0.525861 |                       0.352166 |                   -0.171939 |                 0.00175615  | weak_or_null   |
| q_template_bin     | high                                                                     |  127 |       19 |        -0.0655895  |         0.354253 |                  0.558045 |                       0.333893 |                   -0.203793 |                 0.02036     | weak_or_null   |
| q_template_bin     | extreme                                                                  | 3680 |       32 |        -0.013156   |         0.35473  |                  0.528229 |                       0.352138 |                   -0.1735   |                 0.00259198  | weak_or_null   |
| peak_phase_bin     | rising_6_8                                                               | 2871 |       32 |        -0.0102803  |         0.355116 |                  0.528563 |                       0.354203 |                   -0.173447 |                 0.00091312  | weak_or_null   |
| anomaly_stratum    | late_tail_high                                                           | 1349 |       32 |        -0.0196018  |         0.356725 |                  0.518481 |                       0.355811 |                   -0.161756 |                 0.000914771 | weak_or_null   |

## 5. Falsification

The preregistered failure condition is that an apparent real model improvement is rejected if a shuffled-target or topology-only sentinel matches it within run-block uncertainty, or if abstention can only improve res68 by throwing away nearly all support. This is the decisive test for P04w because P04h found the global A-stack proxy to be shuffled-like.

Observed shuffled-target res68 is `0.5265` and topology-only res68 is `0.3519`. The best non-sentinel minus shuffled res68 is `-0.1722`, while best-minus-topology is `0.0023`. The analysis therefore treats any point-estimate win as diagnostic unless both separations are clearly negative.

## 6. Systematics And Caveats

- The A-stack charge target is an external detector handle but not absolute energy or PID truth; particle identity, material budget, Birks quenching, and geometry are not calibrated here.
- A/B event matching by `(run, EVT)` may couple topology and trigger acceptance; the topology-only sentinel bounds this risk.
- Run-block CIs cover finite run-to-run variation among the available matched runs, not unobserved detector configurations or alternate baseline definitions.
- The neural networks are compact CPU-scale models. They test architecture class plausibility, not an exhaustive GPU sweep.
- The conformal abstention score is target-calibrated on train runs only; if support cells drift across runs, its coverage can fail despite clean splitting.

## 7. Findings And Next Steps

The point-estimate winner is strong_huber_transfer (res68 0.3543), but it does not earn production status because the shuffled-target sentinel is 0.5265 and the topology-only sentinel is 0.3519; the best-minus-topology separation is 0.0023. Risk-ranked abstention lowers some local widths but does not produce a supported frontier that beats both sentinels. B-stack waveform charge should therefore remain a diagnostic proxy, not an energy/PID label source.

Hypothesis: B-stack waveform charge does not contain enough independent information to predict sparse selected A-stack charge after topology and run-family effects are controlled; any safe use in PID/energy needs either new external truth or a much narrower detector-geometry acceptance label.

No follow-up ticket is appended from this study. The current queue already contains P04x/S14/PID externalization tickets, and adding another external-charge frontier without new truth would duplicate this negative-control result.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04w_1781065299_620_6b5f516e_external_charge_abstention_frontier.py --config configs/p04w_1781065299_620_6b5f516e_external_charge_abstention_frontier.yaml
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `method_summary.csv`, `abstention_frontier.csv`, `support_frontier_cells.csv`, `prediction_sample.csv`, and `leakage_checks.csv`.

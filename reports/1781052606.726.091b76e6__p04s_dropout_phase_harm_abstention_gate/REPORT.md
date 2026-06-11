# P04s: dropout recovery phase-harm abstention gate

Ticket `1781052606.726.091b76e6`. Worker `testbeam-laptop-3`. The study reads the raw B-stack ROOT files from `data/root/root` and does not use simulation.

## Abstract

This analysis asks where P04g-style sample-dropout recovery improves amplitude or charge while damaging timing phase, tail shape, q_template support, or pile-up-score support. The raw reproduction gate exactly recovers the canonical S00 selected-pulse count, then deterministic dropouts are injected into real selected pulses. A strong rising-edge Huber recovery is compared to ridge, gradient-boosted trees, MLP, 1D-CNN inpainting, and a new phase-harm-gated CNN. The primary selection criterion is a pre-registered utility combining charge resolution, amplitude resolution, timing phase error, q_template shift, pile-up-score shift, catastrophic failures, and phase-harm labels.

## Raw reproduction gate

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | True |

The reproduced count is computed from `HRDv` in the raw ROOT tree by subtracting the median of samples 0-3, taking even B-stack channels B2/B4/B6/B8, and applying the same `A > 1000 ADC` pulse gate used by S00.

## Data split and dropout model

Training runs are all configured B-stack analysis/calibration runs except held-out runs `[57, 65]`. Held-out intervals resample `(run,event,stave)` blocks, preserving the four paired dropout variants.

For a clean waveform vector $x_i \in \mathbb{R}^{18}$ with peak sample $p_i$, each dropout case defines a mask $m_i$ at offsets $\Delta$. The corrupted waveform is

$$\tilde{x}_{it}=x_{it}(1-m_{it}), \qquad m_{it}=1[t=\mathrm{clip}(p_i+\Delta,4,17)].$$

The reference amplitude is $A_i=\max_t x_{it}$ and charge is $Q_i=\sum_t \max(x_{it},0)$. Timing is the CFD-20 crossing in sample units, linearly interpolated between neighboring samples.

The q_template score is an operational raw-data proxy. For each training-only `(stave, amplitude bin)` cell, a normalized template $\tau_{sb}$ is the median of $x_i/A_i$. For a predicted waveform $\hat x_i$,

$$q_i(\hat x)=\sqrt{\frac{1}{18}\sum_t\left(\frac{\hat x_{it}}{\max_t \hat x_{it}}-\tau_{s(i)b(i)t}\right)^2}.$$

The pile-up score is another operational proxy, $\pi_i=0.65E_{late}/Q+0.35A_{secondary}/A_{peak}$, combining late energy after the peak and the largest secondary lobe outside the peak neighborhood.

## Methods

- `rising_edge_huber`: strong traditional comparator. It uses rising-edge maxima, positive integral summaries, dropout geometry, stave, and case indicators in robust log-linear Huber regressions.
- `ridge_residual`: standardized ridge regression for log residuals $\log A-\log \hat A_{interp}$ and $\log Q-\log \hat Q_{interp}$.
- `gbt_residual`: histogram gradient-boosted trees for the same residual targets.
- `mlp_residual`: two-output neural residual regressor on the engineered waveform/mask feature vector.
- `cnn_inpaint`: 1D convolutional denoiser trained to reconstruct the clean 18-sample waveform from corrupted waveform, mask, and interpolated waveform channels.
- `phase_harm_gated_cnn`: new architecture for this ticket. It shares a 1D convolutional encoder with a residual-regression head and a phase-harm probability head; if predicted phase harm exceeds the configured gate, it abstains to the traditional Huber estimate.

All learned models exclude run id, event id, clean targets, duplicate targets, and any held-out labels from features. Hyperparameters were fixed before evaluation and no held-out run is used for training or calibration.

## Metrics

Fractional errors are $e_A=(\hat A-A)/A$ and $e_Q=(\hat Q-Q)/Q$. The reported robust resolutions are $P_{68}(|e_A|)$, $P_{68}(|e_Q|)$, and $P_{68}(|\hat t-t|)$. Catastrophic rate is

$$r_{cat}=\frac{1}{N}\sum_i 1\{|e_{A,i}|>0.2 \;\lor\; |e_{Q,i}|>0.2\}.$$

A row is counted as a phase-harm label when the method improves absolute charge error by more than the configured charge-gain margin relative to no recovery, but increases absolute timing error, absolute tail-fraction error, q_template shift, or pile-up-score shift beyond the configured harm margins.

The primary utility minimized for winner selection is

$$U=P_{68}(|e_Q|)+0.15P_{68}(|e_A|)+0.20P_{68}(|\Delta t|)+0.35P_{68}(|\Delta q|)+0.35P_{68}(|\Delta \pi|)+1.50r_{phaseharm}+0.50r_{cat}.$$

## Held-out method table

| method | method_family | n | accepted_fraction | amp_res68_abs_frac | charge_res68_abs_frac | time_abs68_samples | tail_bias_median_frac | q_template_abs68_shift | pileup_score_abs68_shift | catastrophic_rate | phase_harm_rate | utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rising_edge_huber | traditional | 4248 | 1 | 0.035301 | 0.023255 | 0.059692 | -0.0078743 | 0.082984 | 0.15022 | 0.090866 | 0 | 0.16754 |
| phase_harm_gated_cnn | new_phase_harm_gated_cnn | 4248 | 0.59063 | 0.038226 | 0.029353 | 0.048807 | -0.031913 | 0.037669 | 0.10656 | 0.066384 | 0.20951 | 0.44279 |
| gbt_residual | gradient_boosted_trees | 4248 | 1 | 0.018894 | 0.0144 | 0.048344 | 0.00033736 | 0.016088 | 0.10065 | 0.027307 | 0.2806 | 0.50232 |
| mlp_residual | mlp | 4248 | 1 | 0.023136 | 0.016499 | 0.048344 | 0.00033736 | 0.016896 | 0.10065 | 0.024247 | 0.28272 | 0.50698 |
| no_recovery | baseline | 4248 | 0 | 0.041847 | 0.23124 | 0.059692 | -0.0078743 | 0.082984 | 0.15022 | 0.41761 | 0 | 0.53988 |
| interpolation | traditional | 4248 | 1 | 0.041847 | 0.034524 | 0.048344 | 0.00033736 | 0.017087 | 0.10065 | 0.10993 | 0.27072 | 0.55272 |
| ridge_residual | ridge | 4248 | 1 | 0.10456 | 0.065964 | 0.048344 | 0.00033736 | 0.022206 | 0.10065 | 0.13701 | 0.30155 | 0.65515 |
| cnn_inpaint | 1d_cnn | 4248 | 1 | 0.053204 | 0.032716 | 0.12437 | -0.0028639 | 0.019014 | 0.040958 | 0.10899 | 0.56709 | 0.99169 |

## Bootstrap confidence intervals

| method | amp_res68_abs_frac_ci95 | charge_res68_abs_frac_ci95 | time_abs68_samples_ci95 | tail_bias_median_frac_ci95 | q_template_abs68_shift_ci95 | pileup_score_abs68_shift_ci95 | catastrophic_rate_ci95 | phase_harm_rate_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rising_edge_huber | [0.033478, 0.036482] | [0.021975, 0.02498] | [0.053944, 0.065067] | [-0.013199, -0.0036003] | [0.079029, 0.08735] | [0.13903, 0.15984] | [0.07789, 0.10547] | [0, 0] |
| phase_harm_gated_cnn | [0.036176, 0.04026] | [0.027822, 0.031314] | [0.043775, 0.053674] | [-0.034429, -0.029561] | [0.035746, 0.040017] | [0.10252, 0.10954] | [0.054826, 0.078631] | [0.19796, 0.22037] |
| gbt_residual | [0.017634, 0.020883] | [0.013564, 0.015595] | [0.042719, 0.053336] | [2.3246e-05, 0.00094168] | [0.015149, 0.017097] | [0.096886, 0.10495] | [0.019291, 0.036023] | [0.26788, 0.29435] |
| mlp_residual | [0.02219, 0.024571] | [0.015816, 0.017299] | [0.042719, 0.053336] | [2.3246e-05, 0.00094168] | [0.015778, 0.01779] | [0.096886, 0.10495] | [0.018356, 0.032963] | [0.27091, 0.29618] |
| no_recovery | [0.037235, 0.046666] | [0.22556, 0.23724] | [0.053944, 0.065067] | [-0.013199, -0.0036003] | [0.079029, 0.08735] | [0.13903, 0.15984] | [0.40131, 0.43293] | [0, 0] |
| interpolation | [0.037235, 0.046666] | [0.032485, 0.036191] | [0.042719, 0.053336] | [2.3246e-05, 0.00094168] | [0.016013, 0.018023] | [0.096886, 0.10495] | [0.096033, 0.1243] | [0.25916, 0.28367] |
| ridge_residual | [0.097105, 0.11039] | [0.062243, 0.070059] | [0.042719, 0.053336] | [2.3246e-05, 0.00094168] | [0.020361, 0.024002] | [0.096886, 0.10495] | [0.11839, 0.15264] | [0.28742, 0.31592] |
| cnn_inpaint | [0.050149, 0.057425] | [0.030925, 0.034878] | [0.11245, 0.13536] | [-0.0035997, -0.0020994] | [0.017473, 0.021009] | [0.037226, 0.044896] | [0.092738, 0.129] | [0.54916, 0.58218] |

## Winner and pairwise deltas

Winner by the pre-registered utility is `rising_edge_huber` with utility `0.16754`. The best traditional method is `rising_edge_huber`.

| comparison | metric | delta | delta_ci95 |
| --- | --- | --- | --- |
| interpolation minus rising_edge_huber | charge_res68_abs_frac | 0.011269 | [0.0098354, 0.012794] |
| interpolation minus rising_edge_huber | time_abs68_samples | -0.011348 | [-0.014443, -0.0088403] |
| interpolation minus rising_edge_huber | q_template_abs68_shift | -0.065897 | [-0.069714, -0.062389] |
| interpolation minus rising_edge_huber | pileup_score_abs68_shift | -0.049577 | [-0.057706, -0.04112] |
| interpolation minus rising_edge_huber | phase_harm_rate | 0.27072 | [0.25727, 0.28399] |
| interpolation minus rising_edge_huber | utility | 0.38517 | [0.36125, 0.40888] |
| ridge_residual minus rising_edge_huber | charge_res68_abs_frac | 0.042709 | [0.039284, 0.046208] |
| ridge_residual minus rising_edge_huber | time_abs68_samples | -0.011348 | [-0.014443, -0.0088403] |
| ridge_residual minus rising_edge_huber | q_template_abs68_shift | -0.060778 | [-0.064943, -0.056657] |
| ridge_residual minus rising_edge_huber | pileup_score_abs68_shift | -0.049577 | [-0.057706, -0.04112] |
| ridge_residual minus rising_edge_huber | phase_harm_rate | 0.30155 | [0.28412, 0.31319] |
| ridge_residual minus rising_edge_huber | utility | 0.4876 | [0.46078, 0.50962] |
| gbt_residual minus rising_edge_huber | charge_res68_abs_frac | -0.008855 | [-0.0098986, -0.0076988] |
| gbt_residual minus rising_edge_huber | time_abs68_samples | -0.011348 | [-0.014443, -0.0088403] |
| gbt_residual minus rising_edge_huber | q_template_abs68_shift | -0.066896 | [-0.070869, -0.063297] |
| gbt_residual minus rising_edge_huber | pileup_score_abs68_shift | -0.049577 | [-0.057706, -0.04112] |
| gbt_residual minus rising_edge_huber | phase_harm_rate | 0.2806 | [0.2653, 0.29308] |
| gbt_residual minus rising_edge_huber | utility | 0.33477 | [0.30816, 0.36014] |
| mlp_residual minus rising_edge_huber | charge_res68_abs_frac | -0.0067563 | [-0.0080759, -0.0055044] |
| mlp_residual minus rising_edge_huber | time_abs68_samples | -0.011348 | [-0.014443, -0.0088403] |
| mlp_residual minus rising_edge_huber | q_template_abs68_shift | -0.066088 | [-0.070012, -0.062535] |
| mlp_residual minus rising_edge_huber | pileup_score_abs68_shift | -0.049577 | [-0.057706, -0.04112] |
| mlp_residual minus rising_edge_huber | phase_harm_rate | 0.28272 | [0.26765, 0.29712] |
| mlp_residual minus rising_edge_huber | utility | 0.33944 | [0.3148, 0.36378] |
| cnn_inpaint minus rising_edge_huber | charge_res68_abs_frac | 0.0094611 | [0.008183, 0.01081] |
| cnn_inpaint minus rising_edge_huber | time_abs68_samples | 0.064676 | [0.051937, 0.07854] |
| cnn_inpaint minus rising_edge_huber | q_template_abs68_shift | -0.06397 | [-0.06815, -0.059608] |
| cnn_inpaint minus rising_edge_huber | pileup_score_abs68_shift | -0.10926 | [-0.12025, -0.0963] |
| cnn_inpaint minus rising_edge_huber | phase_harm_rate | 0.56709 | [0.54587, 0.58429] |
| cnn_inpaint minus rising_edge_huber | utility | 0.82415 | [0.7874, 0.85421] |
| phase_harm_gated_cnn minus rising_edge_huber | charge_res68_abs_frac | 0.0060984 | [0.0051074, 0.0073514] |
| phase_harm_gated_cnn minus rising_edge_huber | time_abs68_samples | -0.010884 | [-0.013984, -0.0084166] |
| phase_harm_gated_cnn minus rising_edge_huber | q_template_abs68_shift | -0.045315 | [-0.049065, -0.041594] |
| phase_harm_gated_cnn minus rising_edge_huber | pileup_score_abs68_shift | -0.043663 | [-0.052104, -0.035743] |
| phase_harm_gated_cnn minus rising_edge_huber | phase_harm_rate | 0.20951 | [0.19585, 0.22391] |
| phase_harm_gated_cnn minus rising_edge_huber | utility | 0.27524 | [0.25626, 0.29675] |

## Support atoms

Each atom is a held-out `(stave, dropout case, amplitude bin, peak region)` cell. `accept` means the cell has charge gain over no recovery with phase-harm rate <=5%; `harm_watch` means charge gain is present but timing/tail/q_template/pile-up harm is non-negligible; `abstain` means the charge gain is too small or unstable.

| stave | dropout_case | amp_bin_label | peak_region | method | n | charge_gain_vs_no_recovery | time_delta_vs_no_recovery_samples | tail_bias_median_frac | q_template_abs68_shift | pileup_score_abs68_shift | phase_harm_rate | support_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B2 | peak_sample | 5000_7000 | early | gbt_residual | 24 | 0.11255 | 0 | -0.069999 | 0.030012 | 0.051964 | 0.95833 | harm_watch |
| B2 | peak_sample | 5000_7000 | early | mlp_residual | 24 | 0.1114 | 0 | -0.069999 | 0.030012 | 0.051964 | 0.95833 | harm_watch |
| B2 | peak_sample | 5000_7000 | early | interpolation | 24 | 0.089144 | 0 | -0.069999 | 0.032508 | 0.051964 | 0.95833 | harm_watch |
| B2 | peak_sample | 5000_7000 | early | ridge_residual | 24 | 0.077301 | 0 | -0.069999 | 0.0292 | 0.051964 | 0.95833 | harm_watch |
| B6 | trailing_sample | 1000_2000 | early | cnn_inpaint | 24 | 0.14072 | 0.2817 | 0 | 0.41604 | 0.029606 | 0.91667 | harm_watch |
| B4 | trailing_sample | 3000_5000 | central | cnn_inpaint | 24 | 0.092405 | 0.034197 | -0.0026669 | 0.0086944 | 0.078616 | 0.91667 | harm_watch |
| B2 | peak_sample | 5000_7000 | early | phase_harm_gated_cnn | 24 | 0.089703 | 0 | -0.069999 | 0.03293 | 0.051964 | 0.91667 | harm_watch |
| B2 | trailing_sample | ge7000 | late | cnn_inpaint | 24 | 0.054931 | 0.13384 | 0.011015 | 0.015275 | 0.05055 | 0.91667 | harm_watch |
| B2 | peak_trailing | 5000_7000 | late | cnn_inpaint | 24 | 0.27794 | 0.13342 | 0.0095327 | 0.062532 | 0.069209 | 0.875 | harm_watch |
| B8 | peak_trailing | 3000_5000 | central | cnn_inpaint | 24 | 0.20056 | 0.03907 | -0.0047893 | 0.022226 | 0.14999 | 0.875 | harm_watch |
| B2 | trailing_sample | 2000_3000 | late | cnn_inpaint | 24 | 0.13771 | 0.052241 | 0.0072256 | 0.018377 | 0.032699 | 0.875 | harm_watch |
| B6 | trailing_sample | 2000_3000 | early | cnn_inpaint | 24 | 0.12044 | 0.053568 | -0.0080858 | 0.027519 | 0.056863 | 0.875 | harm_watch |
| B6 | peak_sample | 3000_5000 | central | gbt_residual | 24 | 0.11827 | 0 | -0.23417 | 0.0099783 | 0.16846 | 0.875 | harm_watch |
| B6 | peak_sample | 3000_5000 | central | mlp_residual | 24 | 0.11765 | 0 | -0.23417 | 0.0099783 | 0.16846 | 0.875 | harm_watch |
| B4 | trailing_sample | 2000_3000 | early | cnn_inpaint | 24 | 0.11533 | 0.040076 | -0.0055714 | 0.011882 | 0.051578 | 0.875 | harm_watch |
| B6 | trailing_sample | 1000_2000 | central | cnn_inpaint | 24 | 0.11281 | 0.032938 | 0.001558 | 0.0070857 | 0.013726 | 0.875 | harm_watch |
| B6 | peak_sample | 3000_5000 | central | interpolation | 24 | 0.10708 | 0 | -0.23417 | 0.014006 | 0.16846 | 0.875 | harm_watch |
| B4 | peak_sample | 3000_5000 | early | gbt_residual | 24 | 0.10648 | 1.5959e-16 | -0.07493 | 0.015083 | 0.085261 | 0.875 | harm_watch |

The full support map is in `support_atoms.csv`.

## Natural dropout/anomaly candidate audit

The injected benchmark has truth by construction. Natural raw dropout/anomaly candidates do not have clean counterfactual waveforms, so they are treated as an unsupervised support audit: a pulse is flagged when one sample in the peak neighborhood is lower than the interpolation of its two neighbors by more than the configured amplitude fraction. The table is stratified by missing-sample location, peak phase, amplitude, stave, q_template score, lowering proxy, saturation proxy, and a P09-style morphology proxy.

| dropout_like_location | stave | amp_bin_label | peak_region | q_template_bin | saturation_proxy | lowering_proxy | p09_taxon_proxy | n_raw_pulses | n_candidates | candidate_fraction | median_notch_deficit_frac |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| leading_edge | B2 | ge7000 | early | q_low | amp_ge_7000 | quiet_prepeak | saturation_edge | 101207 | 101207 | 1 | 0.2517 |
| leading_edge | B2 | 5000_7000 | early | q_low | amp_lt_7000 | quiet_prepeak | ordinary | 63895 | 63895 | 1 | 0.25068 |
| leading_edge | B2 | 5000_7000 | early | q_mid | amp_lt_7000 | quiet_prepeak | ordinary | 41291 | 41291 | 1 | 0.18134 |
| leading_edge | B2 | 3000_5000 | central | q_low | amp_lt_7000 | quiet_prepeak | ordinary | 34480 | 34480 | 1 | 0.16492 |
| leading_edge | B2 | 3000_5000 | early | q_low | amp_lt_7000 | quiet_prepeak | ordinary | 26069 | 26069 | 1 | 0.20887 |
| leading_edge | B2 | 3000_5000 | early | q_mid | amp_lt_7000 | quiet_prepeak | ordinary | 20050 | 20050 | 1 | 0.15108 |
| trailing_sample | B2 | ge7000 | early | q_low | amp_ge_7000 | quiet_prepeak | saturation_edge | 16469 | 16469 | 1 | 0.14096 |
| leading_edge | B2 | 5000_7000 | central | q_low | amp_lt_7000 | quiet_prepeak | ordinary | 15000 | 15000 | 1 | 0.21451 |
| trailing_sample | B2 | ge7000 | early | q_mid | amp_ge_7000 | quiet_prepeak | saturation_edge | 11649 | 11649 | 1 | 0.10298 |
| trailing_sample | B2 | 5000_7000 | early | q_mid | amp_lt_7000 | quiet_prepeak | ordinary | 5516 | 5516 | 1 | 0.092157 |
| leading_edge | B2 | ge7000 | central | q_mid | amp_ge_7000 | quiet_prepeak | saturation_edge | 5215 | 5215 | 1 | 1.689 |
| leading_edge | B2 | 3000_5000 | central | q_mid | amp_lt_7000 | quiet_prepeak | ordinary | 4237 | 4237 | 1 | 0.15765 |
| leading_edge | B4 | 3000_5000 | central | q_low | amp_lt_7000 | quiet_prepeak | ordinary | 4118 | 4118 | 1 | 0.184 |
| trailing_sample | B2 | 1000_2000 | early | q_extreme | amp_lt_7000 | negative_prepeak | qtemplate_outlier | 3698 | 3698 | 1 | 0.28948 |
| trailing_sample | B2 | 2000_3000 | early | q_high | amp_lt_7000 | negative_prepeak | ordinary | 2661 | 2661 | 1 | 0.1922 |
| leading_edge | B2 | ge7000 | central | q_low | amp_ge_7000 | quiet_prepeak | saturation_edge | 2626 | 2626 | 1 | 0.20033 |
| trailing_sample | B2 | 3000_5000 | early | q_mid | amp_lt_7000 | quiet_prepeak | ordinary | 2550 | 2550 | 1 | 0.098587 |
| trailing_sample | B2 | 3000_5000 | early | q_high | amp_lt_7000 | negative_prepeak | ordinary | 2500 | 2500 | 1 | 0.13641 |

The full natural-candidate stratification is in `real_candidate_audit.csv`; it is a support warning table, not a supervised recovery metric.

## Leakage and systematics

- Held-out runs absent from training: `True`.
- Train/evaluation `(run,event,stave)` overlap: `0`.
- Exact corrupted-waveform hash overlap: `0`.
- Feature exclusion: run id, event id, clean waveform, clean amplitude, clean charge, and post-injection labels are excluded from predictors.

Important systematics are not removed by this ticket: injected zero-sample dropouts approximate digitizer or reconstruction losses but do not prove the same support for natural missing-sample mechanisms; the natural-candidate audit has no clean counterfactual target; q_template and pile-up scores are operational waveform proxies rather than independent downstream labels; support atoms are sparse for late peaks and high-amplitude B8 cells; and the CFD timing metric is local to waveform phase, not a full downstream physics selection. The gate should therefore be used as an abstention prior for P04/P07/S14/PID charge consumers, not as an unconditional correction license.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04s_1781052606_726_091b76e6_dropout_phase_harm_abstention_gate.py --config configs/p04s_1781052606_726_091b76e6_dropout_phase_harm_abstention_gate.json
```

# P04r: dropout recovery timing-harm support map

Ticket `1781051221.550.4fc60093`. Worker `testbeam-laptop-3`. The study reads the raw B-stack ROOT files from `data/root/root` and does not use simulation.

## Abstract

This analysis asks where sample-dropout recovery improves amplitude or charge while damaging timing phase, tail shape, or downstream support. The raw reproduction gate exactly recovers the canonical S00 selected-pulse count, then deterministic dropouts are injected into real selected pulses. A strong rising-edge Huber recovery is compared to ridge, gradient-boosted trees, MLP, 1D-CNN inpainting, and a support-gated CNN. The primary selection criterion is a pre-registered utility combining charge resolution, amplitude resolution, timing phase error, catastrophic failures, and net timing/tail harm.

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

## Methods

- `rising_edge_huber`: strong traditional comparator. It uses rising-edge maxima, positive integral summaries, dropout geometry, stave, and case indicators in robust log-linear Huber regressions.
- `ridge_residual`: standardized ridge regression for log residuals $\log A-\log \hat A_{interp}$ and $\log Q-\log \hat Q_{interp}$.
- `gbt_residual`: histogram gradient-boosted trees for the same residual targets.
- `mlp_residual`: two-output neural residual regressor on the engineered waveform/mask feature vector.
- `cnn_inpaint`: 1D convolutional denoiser trained to reconstruct the clean 18-sample waveform from corrupted waveform, mask, and interpolated waveform channels.
- `support_gated_cnn`: new architecture for this ticket. It shares a 1D convolutional encoder with a residual-regression head and a harm-probability head; if the predicted harm probability exceeds the configured gate, it abstains to the traditional Huber estimate.

All learned models exclude run id, event id, clean targets, duplicate targets, and any held-out labels from features. Hyperparameters were fixed before evaluation and no held-out run is used for training or calibration.

## Metrics

Fractional errors are $e_A=(\hat A-A)/A$ and $e_Q=(\hat Q-Q)/Q$. The reported robust resolutions are $P_{68}(|e_A|)$, $P_{68}(|e_Q|)$, and $P_{68}(|\hat t-t|)$. Catastrophic rate is

$$r_{cat}=\frac{1}{N}\sum_i 1\{|e_{A,i}|>0.2 \;\lor\; |e_{Q,i}|>0.2\}.$$

A row is counted as a net harm label when the method improves absolute charge error by more than the configured charge-gain margin relative to no recovery, but increases either absolute timing error or absolute tail-fraction error beyond the configured harm margins.

The primary utility minimized for winner selection is

$$U=P_{68}(|e_Q|)+0.15P_{68}(|e_A|)+0.20P_{68}(|\Delta t|)+1.50r_{harm}+0.50r_{cat}.$$

## Held-out method table

| method | method_family | n | accepted_fraction | amp_res68_abs_frac | charge_res68_abs_frac | time_abs68_samples | tail_bias_median_frac | catastrophic_rate | net_harm_label_rate | utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rising_edge_huber | traditional | 4248 | 1 | 0.036211 | 0.023738 | 0.060097 | -0.010784 | 0.098164 | 0 | 0.09027 |
| support_gated_cnn | new_support_gated_cnn | 4248 | 0.55508 | 0.0488 | 0.025016 | 0.048159 | -0.034119 | 0.055556 | 0.15184 | 0.2975 |
| gbt_residual | gradient_boosted_trees | 4248 | 1 | 0.019274 | 0.015014 | 0.048159 | 0.00028805 | 0.032015 | 0.24576 | 0.41219 |
| mlp_residual | mlp | 4248 | 1 | 0.026229 | 0.019395 | 0.048159 | 0.00028805 | 0.04049 | 0.24529 | 0.42114 |
| no_recovery | baseline | 4248 | 0 | 0.039764 | 0.231 | 0.060097 | -0.010784 | 0.41384 | 0 | 0.45591 |
| interpolation | traditional | 4248 | 1 | 0.039764 | 0.0344 | 0.048159 | 0.00028805 | 0.11747 | 0.24105 | 0.47031 |
| ridge_residual | ridge | 4248 | 1 | 0.1138 | 0.071596 | 0.048159 | 0.00028805 | 0.17208 | 0.2354 | 0.53744 |
| cnn_inpaint | 1d_cnn | 4248 | 1 | 0.056437 | 0.032921 | 0.13521 | -0.0027296 | 0.11064 | 0.57392 | 0.98462 |

## Bootstrap confidence intervals

| method | amp_res68_abs_frac_ci95 | charge_res68_abs_frac_ci95 | time_abs68_samples_ci95 | tail_bias_median_frac_ci95 | catastrophic_rate_ci95 | net_harm_label_rate_ci95 |
| --- | --- | --- | --- | --- | --- | --- |
| rising_edge_huber | [0.034692, 0.037485] | [0.022464, 0.025317] | [0.053943, 0.064948] | [-0.016629, -0.0023152] | [0.086317, 0.11236] | [0, 0] |
| support_gated_cnn | [0.04656, 0.051488] | [0.02384, 0.026579] | [0.043584, 0.052838] | [-0.037655, -0.031577] | [0.044703, 0.069698] | [0.13792, 0.16408] |
| gbt_residual | [0.017904, 0.020922] | [0.014406, 0.016167] | [0.043584, 0.052838] | [0, 0.00087061] | [0.022917, 0.040254] | [0.22937, 0.26378] |
| mlp_residual | [0.024782, 0.027413] | [0.018294, 0.020417] | [0.043584, 0.052838] | [0, 0.00087061] | [0.031703, 0.048752] | [0.22861, 0.2636] |
| no_recovery | [0.035269, 0.045632] | [0.22448, 0.23649] | [0.053943, 0.064948] | [-0.016629, -0.0023152] | [0.39452, 0.42462] | [0, 0] |
| interpolation | [0.035269, 0.045632] | [0.032414, 0.036839] | [0.043584, 0.052838] | [0, 0.00087061] | [0.10439, 0.13159] | [0.22492, 0.25826] |
| ridge_residual | [0.1056, 0.12028] | [0.066784, 0.075675] | [0.043584, 0.052838] | [0, 0.00087061] | [0.15388, 0.19086] | [0.21911, 0.25149] |
| cnn_inpaint | [0.0529, 0.06018] | [0.03077, 0.034917] | [0.1219, 0.14926] | [-0.0037703, -0.0020897] | [0.097564, 0.12604] | [0.55673, 0.59204] |

## Winner and pairwise deltas

Winner by the pre-registered utility is `rising_edge_huber` with utility `0.09027`. The best traditional method is `rising_edge_huber`.

| comparison | metric | delta | delta_ci95 |
| --- | --- | --- | --- |
| interpolation minus rising_edge_huber | charge_res68_abs_frac | 0.010662 | [0.0089375, 0.012438] |
| interpolation minus rising_edge_huber | time_abs68_samples | -0.011938 | [-0.014657, -0.0088532] |
| interpolation minus rising_edge_huber | net_harm_label_rate | 0.24105 | [0.22801, 0.25589] |
| interpolation minus rising_edge_huber | utility | 0.38004 | [0.35945, 0.4023] |
| ridge_residual minus rising_edge_huber | charge_res68_abs_frac | 0.047858 | [0.044633, 0.05248] |
| ridge_residual minus rising_edge_huber | time_abs68_samples | -0.011938 | [-0.014657, -0.0088532] |
| ridge_residual minus rising_edge_huber | net_harm_label_rate | 0.2354 | [0.22416, 0.24853] |
| ridge_residual minus rising_edge_huber | utility | 0.44717 | [0.42303, 0.46679] |
| gbt_residual minus rising_edge_huber | charge_res68_abs_frac | -0.0087233 | [-0.010278, -0.0074316] |
| gbt_residual minus rising_edge_huber | time_abs68_samples | -0.011938 | [-0.014657, -0.0088532] |
| gbt_residual minus rising_edge_huber | net_harm_label_rate | 0.24576 | [0.23183, 0.2603] |
| gbt_residual minus rising_edge_huber | utility | 0.32192 | [0.29846, 0.35023] |
| mlp_residual minus rising_edge_huber | charge_res68_abs_frac | -0.0043424 | [-0.0055337, -0.0032379] |
| mlp_residual minus rising_edge_huber | time_abs68_samples | -0.011938 | [-0.014657, -0.0088532] |
| mlp_residual minus rising_edge_huber | net_harm_label_rate | 0.24529 | [0.23316, 0.26028] |
| mlp_residual minus rising_edge_huber | utility | 0.33087 | [0.30767, 0.35714] |
| cnn_inpaint minus rising_edge_huber | charge_res68_abs_frac | 0.0091832 | [0.0074644, 0.010957] |
| cnn_inpaint minus rising_edge_huber | time_abs68_samples | 0.075116 | [0.061878, 0.091195] |
| cnn_inpaint minus rising_edge_huber | net_harm_label_rate | 0.57392 | [0.55221, 0.594] |
| cnn_inpaint minus rising_edge_huber | utility | 0.89435 | [0.85812, 0.92937] |
| support_gated_cnn minus rising_edge_huber | charge_res68_abs_frac | 0.001278 | [0.00060524, 0.0023293] |
| support_gated_cnn minus rising_edge_huber | time_abs68_samples | -0.011938 | [-0.014657, -0.0088532] |
| support_gated_cnn minus rising_edge_huber | net_harm_label_rate | 0.15184 | [0.13968, 0.1657] |
| support_gated_cnn minus rising_edge_huber | utility | 0.20723 | [0.18406, 0.2279] |

## Support atoms

Each atom is a held-out `(stave, dropout case, amplitude bin, peak region)` cell. `accept` means the cell has charge gain over no recovery with net harm rate <=5%; `harm_watch` means charge gain is present but timing/tail harm is non-negligible; `abstain` means the charge gain is too small or unstable.

| stave | dropout_case | amp_bin_label | peak_region | method | n | charge_gain_vs_no_recovery | time_delta_vs_no_recovery_samples | tail_bias_median_frac | net_harm_label_rate | support_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B6 | trailing_sample | 3000_5000 | central | cnn_inpaint | 24 | 0.096906 | 0.059135 | -0.007937 | 1 | harm_watch |
| B2 | trailing_sample | 5000_7000 | early | cnn_inpaint | 24 | 0.074498 | 0.058581 | -0.0053414 | 1 | harm_watch |
| B4 | peak_sample | 2000_3000 | early | cnn_inpaint | 24 | 0.12497 | 0.075111 | -0.0053193 | 0.95833 | harm_watch |
| B2 | trailing_sample | 1000_2000 | central | cnn_inpaint | 24 | 0.10125 | 0.064411 | 0.0021604 | 0.95833 | harm_watch |
| B2 | trailing_sample | ge7000 | early | cnn_inpaint | 24 | 0.059074 | 0.073044 | -0.0028588 | 0.95833 | harm_watch |
| B4 | trailing_sample | 3000_5000 | late | cnn_inpaint | 24 | 0.17535 | 0.13086 | -0.012848 | 0.91667 | harm_watch |
| B6 | trailing_sample | 3000_5000 | early | cnn_inpaint | 24 | 0.093338 | 0.059122 | -0.0034581 | 0.91667 | harm_watch |
| B8 | trailing_sample | 3000_5000 | central | cnn_inpaint | 24 | 0.086785 | 0.066312 | -0.0001771 | 0.91667 | harm_watch |
| B2 | trailing_sample | ge7000 | central | cnn_inpaint | 24 | 0.05463 | 0.13595 | -0.0020333 | 0.91667 | harm_watch |
| B6 | peak_trailing | 3000_5000 | late | cnn_inpaint | 24 | 0.44696 | 0.21349 | -0.06712 | 0.875 | harm_watch |
| B6 | peak_sample | 3000_5000 | late | cnn_inpaint | 24 | 0.21775 | 0.11673 | -0.061582 | 0.875 | harm_watch |
| B2 | peak_trailing | ge7000 | central | cnn_inpaint | 24 | 0.20597 | 0.20184 | 0.015337 | 0.875 | harm_watch |
| B6 | trailing_sample | 3000_5000 | late | cnn_inpaint | 24 | 0.19206 | 0.15903 | -0.02025 | 0.875 | harm_watch |
| B2 | peak_sample | 2000_3000 | early | cnn_inpaint | 24 | 0.13472 | 0.21475 | -0.0058523 | 0.875 | harm_watch |
| B4 | trailing_sample | 2000_3000 | central | cnn_inpaint | 24 | 0.11341 | 0.058448 | 0.0026692 | 0.875 | harm_watch |
| B4 | peak_sample | 3000_5000 | central | cnn_inpaint | 24 | 0.10175 | 0.044628 | -0.0039424 | 0.875 | harm_watch |
| B4 | trailing_sample | 3000_5000 | central | cnn_inpaint | 24 | 0.091504 | 0.048904 | -0.00053535 | 0.875 | harm_watch |
| B2 | trailing_sample | 3000_5000 | early | cnn_inpaint | 24 | 0.081953 | 0.036369 | -0.0037307 | 0.875 | harm_watch |

The full support map is in `support_atoms.csv`.

## Leakage and systematics

- Held-out runs absent from training: `True`.
- Train/evaluation `(run,event,stave)` overlap: `0`.
- Exact corrupted-waveform hash overlap: `0`.
- Feature exclusion: run id, event id, clean waveform, clean amplitude, clean charge, and post-injection labels are excluded from predictors.

Important systematics are not removed by this ticket: injected zero-sample dropouts approximate digitizer or reconstruction losses but do not prove the same support for natural missing-sample mechanisms; the support atoms are sparse for late peaks and high-amplitude B8 cells; and the CFD timing metric is local to waveform phase, not a full downstream physics selection. The gate should therefore be used as an abstention prior for charge consumers, not as an unconditional correction license.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04r_1781051221_550_4fc60093_dropout_timing_harm_support_map.py --config configs/p04r_1781051221_550_4fc60093_dropout_timing_harm_support_map.json
```

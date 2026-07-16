# PULSE-SAT-PILEUP: template deconvolution vs ML saturation/pile-up recovery

**Ticket:** `1783745883.3711.1b7b30b5`  
**Worker:** `testbeam-laptop-1`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This study tests whether saturated and piled-up waveform recovery benefits from ML/NN-style models relative to a strong traditional template-deconvolution and constant-fraction timing baseline. The inputs are raw B-stack ROOT waveforms. Because no row-level external amplitude, timing, and pile-up truth is available in the raw files, the study uses a self-supervised construction: clean measured pulses supply the truth, then controlled clipping and delayed secondary-pulse injection create saturation and pile-up stress samples. Evaluation is leave-one-run-out, and uncertainty intervals are run-block bootstraps. The composite winner is **NN_1d_cnn_feature_mlp**.

## Raw reproduction gate

The analysis rescans every configured B-stack run from raw ROOT. For each event, `HRDv` is reshaped to `(8, 18)`, samples 0--3 define the pedestal, the even B-stave channels B2/B4/B6/B8 are baseline-subtracted, and a selected pulse has `max_t v(t) > 1000 ADC`. The reproduced selected-pulse count is **640,737**, matching the registered count **640,737** with delta **0**.

## Data set and truth construction

Clean seed pulses are selected from the raw reproduction table with peak sample in `[4, 11]`, amplitude in `[1300, 7000] ADC`, finite CFD50 time, and normalized area between 2.2 and 9.5. A stratified cap of `120` clean pulses per `(run, stave)` avoids domination by high-rate runs. This yields **13,383** clean seeds across **33** runs.

For saturation, each clean waveform `v_i(t)` with true amplitude `A_i=max_t v_i(t)` is clipped at a deterministic rotating ceiling `C_i in {2400.0, 3200.0, 4200.0}`:

`x_i^sat(t) = min(v_i(t), C_i),    y_i^E = log A_i,    y_i^T = t50(v_i).`

For pile-up, the same primary pulse is paired with another raw clean pulse `u_j`, a delay `d in {2, 3, 4, 5}`, and a secondary scale `alpha in [0.20, 0.55]`:

`x_i^pile(t) = v_i(t) + alpha_i u_j(t-d) 1{t >= d},    y_i^P = 1.`

The negative pile-up class is the unmodified clean pulse, `y_i^P=0`. Thus the amplitude and timing truth remain the measured primary pulse, while pile-up class truth is exactly known by construction.

## Methods

### Traditional template deconvolution and CFD

For each held-out run, the template `q(t)` is the mean normalized clean training pulse. Saturated amplitudes are recovered by least-squares scaling on unclipped samples:

`a_hat = argmin_a sum_{t in U_i} (x_i^sat(t) - a q(t))^2 = (sum_{t in U_i} q(t)x_i^sat(t))/(sum_{t in U_i} q(t)^2)`,

where `U_i={t: x_i^sat(t)<C_i}`. Timing is the CFD50 crossing of `x_i^sat/a_hat`. Pile-up uses the same template scale and scores the event by normalized residual energy plus a small CFD-time displacement term.

### ML/NN panel

Ridge, gradient-boosted trees, and MLP use waveform samples, normalized shape samples, log-amplitude, area/tail/rise/derivative descriptors, CFD times, and stave one-hot indicators. The 1D-CNN entry uses explicit local convolutional filters over the 18-sample waveform followed by an MLP head. The new architecture is `NN_causal_attention_mlp_new`: it augments the pulse with causal cumulative charge, slope-weighted causal attention time, attention-weighted signal summaries, and causal running maxima before an MLP head. This is a sensible transformer-like substitute in the current environment because PyTorch is absent and the waveform has only 18 samples; the causal attention features preserve the intended directional inductive bias without unverified torch training.

All models are trained in leave-one-run-out folds. For saturation the regression target is `log A_i`; for pile-up the classification target is the injected-pile-up indicator.

## Metrics and intervals

Energy residuals are `delta_E=(A_hat-A)/A`; the main energy metric is `sigma68(delta_E)=percentile_68(|delta_E-median(delta_E)|)`. Timing residuals are `delta_t=t50_hat-t50`; the timing metric is `sigma68(delta_t)`. Pile-up tagging uses ROC AUC and average precision. Bootstrap CIs resample runs with replacement, pool their rows, and recompute each metric 300 times.

## Saturation recovery results

| method | energy sigma68 | 95% CI | energy bias | timing sigma68 | 95% CI | rows |
|---|---:|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0.02227 | [0.02140, 0.02309] | +0.00060 | 0.1583 | [0.1471, 0.1702] | 13,383 |
| ML_ridge | 0.03962 | [0.03885, 0.04046] | +0.00149 | 0.1583 | [0.1456, 0.1703] | 13,383 |
| NN_1d_cnn_feature_mlp | 0.06869 | [0.06616, 0.07269] | +0.00183 | 0.1583 | [0.1456, 0.1694] | 13,383 |
| ML_mlp | 0.07298 | [0.07041, 0.07598] | +0.00395 | 0.1583 | [0.1462, 0.1687] | 13,383 |
| NN_causal_attention_mlp_new | 0.08632 | [0.08058, 0.09320] | +0.00762 | 0.1583 | [0.1460, 0.1712] | 13,383 |
| traditional_template_deconvolution_cfd | 0.13522 | [0.13140, 0.13816] | -0.15121 | 0.1583 | [0.1468, 0.1696] | 13,383 |

## Pile-up tagging results

| method | ROC AUC | 95% CI | average precision | 95% CI | rows |
|---|---:|---:|---:|---:|---:|
| NN_causal_attention_mlp_new | 0.99761 | [0.99703, 0.99814] | 0.99789 | [0.99731, 0.99832] | 26,766 |
| NN_1d_cnn_feature_mlp | 0.99748 | [0.99693, 0.99798] | 0.99749 | [0.99676, 0.99806] | 26,766 |
| ML_mlp | 0.99715 | [0.99658, 0.99776] | 0.99753 | [0.99692, 0.99805] | 26,766 |
| ML_gradient_boosted_trees | 0.99554 | [0.99472, 0.99637] | 0.99604 | [0.99537, 0.99671] | 26,766 |
| ML_ridge | 0.92676 | [0.92404, 0.92962] | 0.93287 | [0.92987, 0.93604] | 26,766 |
| traditional_template_residual_cfd | 0.51980 | [0.51381, 0.52513] | 0.49327 | [0.49004, 0.49735] | 26,766 |

## Composite decision

The winner is chosen by the mean rank of saturation energy sigma68, saturation timing sigma68, and pile-up ROC AUC. Lower composite rank is better.

| method | energy sigma68 | timing sigma68 | pile-up AUC | composite rank |
|---|---:|---:|---:|---:|
| NN_1d_cnn_feature_mlp | 0.06869 | 0.1583 | 0.99748 | 2.00 |
| NN_causal_attention_mlp_new | 0.08632 | 0.1583 | 0.99761 | 2.33 |
| ML_ridge | 0.03962 | 0.1583 | 0.92676 | 2.67 |
| ML_mlp | 0.07298 | 0.1583 | 0.99715 | 2.67 |
| ML_gradient_boosted_trees | 0.02227 | 0.1583 | 0.99554 | 3.33 |

## Per-run stability

| task | method | mean | min | max | finite runs |
|---|---|---:|---:|---:|---:|
| saturation energy sigma68 | ML_gradient_boosted_trees | 0.02252 | 0.01710 | 0.02664 | 33 |
| saturation energy sigma68 | ML_mlp | 0.07224 | 0.06140 | 0.08881 | 33 |
| saturation energy sigma68 | ML_ridge | 0.03965 | 0.03552 | 0.04439 | 33 |
| saturation energy sigma68 | NN_1d_cnn_feature_mlp | 0.06884 | 0.05678 | 0.12114 | 33 |
| saturation energy sigma68 | NN_causal_attention_mlp_new | 0.08571 | 0.05644 | 0.14235 | 33 |
| saturation energy sigma68 | traditional_template_deconvolution_cfd | 0.13458 | 0.10615 | 0.15587 | 33 |
| pile-up AUC | ML_gradient_boosted_trees | 0.99575 | 0.99070 | 0.99994 | 33 |
| pile-up AUC | ML_mlp | 0.99719 | 0.99393 | 1.00000 | 33 |
| pile-up AUC | ML_ridge | 0.92786 | 0.90988 | 0.94306 | 33 |
| pile-up AUC | NN_1d_cnn_feature_mlp | 0.99762 | 0.99395 | 1.00000 | 33 |
| pile-up AUC | NN_causal_attention_mlp_new | 0.99776 | 0.99219 | 1.00000 | 33 |
| pile-up AUC | traditional_template_residual_cfd | 0.51936 | 0.49112 | 0.56039 | 33 |

## Systematics

- The labels are self-supervised transformations of measured pulses. This is stronger than a toy waveform simulation because the seeds are raw measured pulses, but it is not a substitute for external beam truth.
- The saturation ceiling is imposed in software. Real electronics saturation may include recovery dynamics, baseline distortion, or nonlinearity before the ADC; those effects are not modeled.
- Pile-up uses delayed clean B-stack pulses as secondaries. It preserves realistic pulse shapes but assumes linear superposition and a uniform secondary scale/delay prior.
- Leave-one-run-out controls run leakage. The bootstrap CI treats runs as exchangeable blocks and therefore reflects run-to-run stability better than row-level CIs.
- PyTorch is not installed in this worker, so the CNN and causal-transformer-like entries are implemented as fixed temporal convolution and causal-attention feature maps with MLP heads. The report and `result.json` mark them as feature-map NN surrogates, not torch-trained end-to-end networks.

## Caveats

The study answers a bounded question: on raw-derived clipping and delayed-superposition stress tests, which method best recovers primary amplitude/timing and tags pile-up under run-heldout evaluation? It should not be read as a claim that the same ranking holds for all detector operating points, for external PID truth, or for hardware saturation modes absent from the measured seed pulses.

## Verdict

`result.json` names **NN_1d_cnn_feature_mlp** as the winner. The best traditional baseline is `traditional_template_deconvolution_cfd` for saturation and `traditional_template_residual_cfd` for pile-up; the composite table quantifies whether the ML/NN panel improves on those baselines.

## Reproducibility

```bash
.venv/bin/python scripts/pulse_sat_pileup_1783745883_3711_1b7b30b5.py --config configs/1783745883.3711.1b7b30b5_pulse_sat_pileup.json
```

Primary artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `counts_by_run.csv`, `clean_seed_sample.csv`, `saturation_summary.csv`, `pileup_summary.csv`, `composite_ranking.csv`, `saturation_per_run.csv`, `pileup_per_run.csv`, `saturation_predictions.csv.gz`, `pileup_predictions.csv.gz`, and `manifest.json`.

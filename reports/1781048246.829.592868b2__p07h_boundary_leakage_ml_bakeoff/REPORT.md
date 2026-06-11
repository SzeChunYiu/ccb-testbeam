# P07h: boundary-shrinkage leakage triage and ML/NN bakeoff

**Ticket:** `1781048246.829.592868b2`  
**Worker:** `testbeam-laptop-4`  
**Raw ROOT directory:** `data/root/root`  
**Command:** `/home/billy/anaconda3/bin/python scripts/p07h_1781048246_829_592868b2_boundary_leakage_ml_bakeoff.py --config configs/p07h_1781048246_829_592868b2_boundary_leakage_ml_bakeoff.json`

## Abstract

This study reopens the P07 natural B2 boundary-shrinkage leakage warning with a raw-ROOT audit and a fair run-split model bakeoff. The global B-stave selection count is reproduced exactly from raw ROOT, the P07d leakage anchor is reproduced as three flagged diagnostics, and the explicit ridge/GBT/MLP/CNN/residual-CNN panel is benchmarked on self-generated saturation truth. The winner by run-bootstrap res68 is **ML_gradient_boosted_trees** with res68 **0.0234** [0.0220, 0.0250]. The strongest traditional baseline is **traditional_template_family** with res68 **0.1480** [0.1460, 0.1499].

## Raw reproduction gates

For every registered S00/T07 B-stack ROOT run, `HRDv` was reshaped to `(8,18)`, samples 0-3 supplied the per-channel baseline, even B-stave channels were baseline-subtracted, and a pulse was selected if its maximum exceeded 1000 ADC. This gives **640,737** selected B-stave pulses versus the registered **640,737** count, delta **0**.

The P07h B2 boundary triage then uses runs `58, 59, 60, 61, 62, 63, 65` only. In that subset the raw scan finds **88,213** selected B2 pulses. Re-running the P07d boundary diagnostic reproduces the shape-only q-template shift as `-0.079604` versus the archived `-0.083233` and reproduces **3** leakage flags.

## Statistical design

The supervised benchmark uses clean unsaturated B2 pulses with peak samples 4-12, amplitude between 1500 and 6500 ADC, and true amplitude above `1.05 C`, where `C=4000` ADC. Each waveform is clipped at a fixed ceiling, so `x_i^C(t)=min(x_i(t), C)` and the target is the independent raw amplitude `A_i`. Folds are leave-one-run-out: for held-out run `r`, all templates and model parameters are fit only on runs `R \ {r}`.

The primary metric is

`res68 = percentile_68(|Ahat_i - A_i| / A_i)`,

with secondary median signed bias, fraction within 10%, fractional RMSE, and `R^2` in log amplitude. Confidence intervals are run-block bootstraps: draw held-out runs with replacement, average the per-run metric weighted by the run's test count, and report the 2.5% and 97.5% quantiles.

## Traditional and ML methods

The traditional baseline is a calibrated template-family recovery. Clean training pulses are binned by amplitude, normalized templates are fit in each bin, and the clipped rising-edge samples determine the least-squares amplitude scale. A final linear calibration `Ahat = beta_1 Araw + beta_0`, trained only on non-held-out runs, removes residual bias while preserving the non-ML pulse-shape model.

The ML panel uses the clipped 18-sample waveform plus compact pulse-shape statistics for ridge, gradient-boosted trees, and MLP. The neural methods receive only the normalized clipped sequence. The new residual squeeze CNN is sensible here because the waveform has only 18 time samples: residual temporal convolutions retain local edge information, global average/max pooling summarizes tail support, and a small squeeze gate lets the network emphasize informative channels without a large parameter count.

| method | n | bias | res68 | 95% CI | within 10% | RMSE frac | log-A R2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 19,250 | -0.0003 | 0.0234 | [0.0220, 0.0250] | 0.9911 | 0.0281 | 0.9483 |
| ML_ridge_regression | 19,250 | -0.0004 | 0.0364 | [0.0340, 0.0390] | 0.9612 | 0.0471 | 0.8587 |
| NN_residual_squeeze_cnn_new | 19,250 | +0.0156 | 0.0589 | [0.0527, 0.0674] | 0.8921 | 0.0678 | 0.6854 |
| NN_1d_cnn | 19,250 | +0.0121 | 0.0753 | [0.0653, 0.0886] | 0.7980 | 0.0902 | 0.4760 |
| ML_mlp | 19,250 | -0.0002 | 0.1053 | [0.0873, 0.1233] | 0.6649 | 0.1196 | 0.1108 |
| traditional_template_family | 19,250 | +0.0165 | 0.1480 | [0.1460, 0.1499] | 0.4594 | 0.1261 | -0.0181 |

## Boundary leakage triage

The natural-boundary arm reuses the P07d diagnostic layers and keeps the stricter interpretation: a correction is acceptable only if the 6500-7500 ADC boundary band passes `|q_template shift| <= 0.025` and `|CFD20 shift| <= 0.75 ns`. The reproduced flags are not random-row leakage: folds are by run, the primary calibration excludes raw observed amplitude, explicit ceiling, run id, `EVENTNO`, and `EVT`, and event-hash dependence remains small in the primary calibration. The three flags arise from diagnostic controls intentionally given observed-amplitude or run/event/amplitude handles, which can mimic the boundary alpha support but do not improve over the linear shrinkage layer.

| check | value | threshold | flag | interpretation |
|---|---:|---:|---:|---|
| p07c_boundary_q_shift_reproduction_delta | 0.0036292 | 0.004 | False | Raw ROOT reproduction of the P07c primary shape-only 6500-7500 q_template shift. |
| heldout_split_run_overlap | 0 | 0 | False | All ratio and calibration models train on complete non-held-out runs only. |
| primary_ml_raw_observed_amplitude_feature_count | 0 | 0 | False | Primary ML calibration uses normalized waveform shape plus base lift, not raw observed amplitude. |
| primary_ml_explicit_ceiling_feature_count | 0 | 0 | False | Primary shape-transfer and calibration features omit explicit log ceiling. |
| primary_ml_run_feature_count | 0 | 0 | False | Primary ML calibration omits run id. |
| primary_ml_event_id_feature_count | 0 | 0 | False | Primary ML calibration omits EVENTNO/EVT. |
| linear_boundary_q_gate_abs | 0.0216817 | 0.025 | False | Linear shrinkage must close the held-out boundary q_template gate. |
| ml_boundary_q_gate_abs | 0.0220518 | 0.025 | False | ML calibration must close the held-out boundary q_template gate. |
| ml_boundary_cfd_gate_abs_ns | 0.108736 | 0.75 | False | ML calibration must preserve held-out boundary CFD20 timing. |
| observed_amp_only_control_boundary_lift_fraction | 0.0243241 | 0.0180462 | True | An observed-amplitude-only calibration should not explain most primary ML lift. |
| run_event_amp_control_boundary_lift_fraction | 0.0243482 | 0.0180462 | True | Run/event/amplitude control should not reproduce primary ML correction on held-out runs. |
| shuffled_target_control_boundary_lift_fraction | 0.0242646 | 0.0180462 | True | Shuffled calibration target should not reproduce primary ML correction. |
| application_ml_abstention_fraction | 0.000569692 | 0.95 | False | A useful gate should not abstain on nearly all A>=7000 pulses. |
| application_linear_abstention_fraction | 0 | 0.95 | False | Traditional linear shrinkage should not collapse to no correction in application. |

## Systematics and caveats

- The amplitude benchmark uses artificial hard clipping of clean pulses. It tests recovery mechanics under controlled saturation truth, not unknown true amplitudes of naturally saturated pulses.
- The natural-boundary decision remains constrained by q-template and timing side effects. A model that wins artificial res68 is not automatically adoptable for production if it violates those boundary gates.
- The B2-only P07h triage is intentionally narrower than the global 640,737-pulse reproduction gate; it targets the same natural B2 boundary where P07d raised flags.
- Run-bootstrap CIs represent run-to-run stability, not independent event-count precision.
- Neural networks are small by design because 18 samples do not justify high-capacity architectures without external truth.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the artificial-saturation benchmark winner. For natural saturated B2 deployment, the boundary triage still prefers the simpler linear shrinkage layer unless a future study proves that the winning artificial-truth model also satisfies q-template, CFD20, and leakage gates on the natural boundary.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p07h_1781048246_829_592868b2_boundary_leakage_ml_bakeoff.py --config configs/p07h_1781048246_829_592868b2_boundary_leakage_ml_bakeoff.json
```

Artifacts include `result.json`, `manifest.json`, `global_reproduction_by_run.csv`, `benchmark_summary.csv`, `benchmark_by_run.csv`, `benchmark_predictions.csv.gz`, `leakage_checks.csv`, `boundary_by_run.csv`, and diagnostic figures.

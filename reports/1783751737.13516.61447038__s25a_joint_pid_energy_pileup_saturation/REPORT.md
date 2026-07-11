# S25a: Joint PID-energy calibration under pile-up and saturation stress

**Ticket:** `1783751737.13516.61447038`  
**Worker:** `testbeam-laptop-2`  
**Date:** 2026-07-11  
**Raw ROOT directory:** `data/root/root`  
**Config:** `configs/s25a_1783751737_13516_61447038_joint_pid_energy.yaml`  
**Git commit:** `2a50af146057f88865d7dfd5a4a6965efe2df3d0`

## Abstract

This ticket asks whether a joint calibration can separate PID, energy scale,
saturation, pedestal, and pile-up effects without leaking run identity. The
experimental ROOT files do not provide hidden event-level particle truth, so
the PID endpoint is the P08e beamline/range enriched proxy and the energy
endpoint is the S24a duplicate-readout closure on a GEANT4-truth anchored MeV
scale. Both source studies used complete held-out runs and 300 run-block
bootstrap resamples. This ticket independently recounts the raw selected-pulse
anchor from ROOT, then combines the two benchmark panels into a single
pre-registered score.

The machine-readable winner in `result.json` is **`traditional_joint`**.
Its PID AUC is `1.0000` with CI
`[1.0000, 1.0000]`, energy
res68 is `0.04024` with CI
`[0.03886, 0.04161]`,
and saturation-onset energy res68 is `0.04850`
with CI `[0.04745, 0.05115]`.

## 1. Raw-ROOT Reproduction Gate

For every configured B-stack run, the script reads `h101/HRDv`, reshapes each
event into eight channels by eighteen samples, subtracts the channel pedestal

`b_{e,c} = median(x_{e,c,t} : t in {0,1,2,3})`,

and counts selected B-stave pulses for even channels B2/B4/B6/B8:

`N = sum_{e,c} 1[max_t (x_{e,c,t} - b_{e,c}) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |       0 |           0 | True   |

The reproduction gate passes exactly; the raw input universe is the canonical
640,737 selected-pulse B-stave corpus.

## 2. Targets and Split

The split is by run, never by shuffled event. Calibration/train runs are
Sample I calibration runs 31-37 and 39-42 plus Sample II calibration run 64.
Held-out runs are Sample I analysis runs 44-57 and Sample II analysis runs
58-63 and 65. This blocks run-family leakage from train to test.

PID target: P08e defines a beamline/range enriched proxy. Terminal high
ionisation B2 events are positive, downstream penetrating events are negative,
and each run is balanced locally. This is a PID action-closure proxy, not a
hidden truth label.

Energy target: S24a maps duplicate odd readout to deposited energy using a
GEANT4 Sci_bar layer prior and a Birks-style response. For charge `Q`, deposited
energy `E`, and stopping power `dE/dx`,

`Q_hat = alpha E / (1 + k_B dE/dx)`,

and the inverse prediction is

`E_hat = Q (1 + k_B dE/dx) / alpha`.

## 3. Methods

The traditional joint method pairs `traditional_charge_depth_logistic` for PID
with `geant4_birks_lookup` for energy. This is a strong baseline: it encodes
range, charge-depth topology, GEANT4 layer priors, and a detector-response
equation rather than a weak threshold rule.

The learned panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, and a
ticket-local new residual architecture. PID ridge/GBT/MLP/CNN scores come from
P08e out-of-fold run-held-out predictions. Energy ridge/GBT/MLP/CNN scores
come from S24a on the same held-out run family. The new residual architecture
pairs the P08e action-gated residual ensemble with the S24a physics-residual
MLP:

`E_hat_new = E_hat_Birks exp(g_theta(phi(HRDv)))`.

S24a additionally trained a waveform transformer for the energy endpoint; it is
reported below as an energy-only neural comparator because the PID source panel
did not train a transformer PID head.

## 4. Metrics and Joint Score

PID is scored by ROC AUC, average precision, and expected calibration error:

`ECE = sum_b (n_b / N) | mean(y_b) - mean(p_b) |`.

Energy is scored by the robust fractional residual width

`res68 = percentile_68(|(E_hat - E) / E|)`.

The pre-registered joint score minimized here is

`S = 0.45 (1 - AUC_PID) + 0.35 res68_energy + 0.20 res68_saturation`.

The saturation term repeats energy res68 inside the ADC-saturation-onset
stratum. All intervals are inherited from the source run-block bootstraps.

## 5. Joint Head-to-Head Benchmark

| joint_method              |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   energy_res68_frac |   energy_res68_ci_low |   energy_res68_ci_high |   saturation_res68_frac |   joint_score |
|:--------------------------|----------:|-----------------:|------------------:|--------------------:|----------------------:|-----------------------:|------------------------:|--------------:|
| traditional_joint         |    1      |           1      |            1      |             0.04024 |               0.03886 |                0.04161 |                 0.0485  |       0.02378 |
| new_residual_architecture |    1      |           1      |            1      |             0.05868 |               0.04902 |                0.07788 |                 0.03877 |       0.02829 |
| gradient_boosted_trees    |    0.928  |           0.9216 |            0.9352 |             0.05668 |               0.0488  |                0.0672  |                 0.05621 |       0.06348 |
| ridge                     |    0.8513 |           0.8448 |            0.8622 |             0.09667 |               0.08872 |                0.1172  |                 0.05495 |       0.1117  |
| 1d_cnn                    |    0.7268 |           0.7076 |            0.7484 |             0.2657  |               0.2493  |                0.2891  |                 0.1898  |       0.2539  |
| mlp                       |    0.9471 |           0.9407 |            0.9541 |             0.6923  |               0.6842  |                0.6996  |                 0.5733  |       0.3808  |

The traditional physics/range method wins because the PID proxy is explicitly
range-depth anchored and the energy endpoint is best explained by a Birks-style
truth prior. The best ML-only energy point estimate is competitive in MAE, but
the robust run-held-out fractional width and saturation stratum favor the
physics baseline.

## 6. PID Benchmark Table

| method                                |     n |   runs |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   purity_at_80pct_eff |       ece |
|:--------------------------------------|------:|-------:|----------:|-----------------:|------------------:|--------------------:|----------------------:|----------:|
| traditional_charge_depth_logistic     | 19424 |     32 |    1      |           1      |            1      |              1      |                1      | 0.0001501 |
| ML_ridge_waveform                     | 19424 |     32 |    0.8513 |           0.8448 |            0.8622 |              0.7788 |                0.7592 | 0.03178   |
| ML_gradient_boosted_trees             | 19424 |     32 |    0.928  |           0.9216 |            0.9352 |              0.8943 |                0.8815 | 0.03402   |
| ML_mlp                                | 19424 |     32 |    0.9471 |           0.9407 |            0.9541 |              0.9221 |                0.9106 | 0.01314   |
| NN_1d_cnn                             | 19424 |     32 |    0.7268 |           0.7076 |            0.7484 |              0.6389 |                0.6466 | 0.1409    |
| NN_action_gated_residual_ensemble_new | 19424 |     32 |    1      |           1      |            1      |              1      |                1      | 0.001803  |
| control_charge_only                   | 19424 |     32 |    1      |           1      |            1      |              1      |                1      | 0.0003918 |
| control_depth_only                    | 19424 |     32 |    1      |           1      |            1      |              1      |                1      | 0.0003337 |
| control_action_only                   | 19424 |     32 |    0.5767 |           0.562  |            0.5978 |              0.5362 |                0.5508 | 0.003817  |
| control_run_family_only               | 19424 |     32 |    0.5    |           0.5    |            0.5    |              0.5    |                0.5    | 0         |
| control_shuffled_label_hgb            | 19424 |     32 |    0.5086 |           0.4611 |            0.5569 |              0.4752 |                0.5209 | 0.006203  |

## 7. Energy Benchmark Table

| method                 | family                    |      n |   bias_frac |   res68_frac |   mae_mev |
|:-----------------------|:--------------------------|-------:|------------:|-------------:|----------:|
| geant4_birks_lookup    | traditional_geant4_birks  | 332852 |    -0.0231  |      0.04024 |     1.082 |
| gradient_boosted_trees | ml_tree                   | 332852 |    -0.01674 |      0.05668 |     1.003 |
| physics_residual_mlp   | neural_physics_residual   | 332852 |    -0.01457 |      0.05868 |     1.052 |
| ridge                  | ml_linear                 | 332852 |    -0.02357 |      0.09667 |     1.411 |
| transformer            | neural_waveform_attention | 332852 |     0.03261 |      0.1264  |     1.929 |
| 1d_cnn                 | neural_waveform           | 332852 |    -0.1777  |      0.2657  |     3.862 |
| old_power_law          | traditional_empirical     | 332852 |    -0.2976  |      0.4624  |     7.863 |
| mlp                    | neural_tabular            | 332852 |    -0.5827  |      0.6923  |    10.62  |

## 8. Saturation and Pile-up Stress

The saturation-onset table below is the explicit stress endpoint used in the
joint score. Pile-up and pedestal robustness are covered in S24a by
`pileup_or_multihit`, `pedestal_drift_proxy_high`, and `late_pulse_shape`
strata; their detailed rows are preserved in `saturation_shape_strata_metrics.csv`.

| method                 |      n |   bias_frac |   res68_frac |   mae_mev |
|:-----------------------|-------:|------------:|-------------:|----------:|
| physics_residual_mlp   | 106217 |    -0.01276 |      0.03877 |    0.9503 |
| geant4_birks_lookup    | 106217 |    -0.0404  |      0.0485  |    1.285  |
| ridge                  | 106217 |    -0.02568 |      0.05495 |    1.286  |
| gradient_boosted_trees | 106217 |    -0.03792 |      0.05621 |    1.428  |
| transformer            | 106217 |     0.07545 |      0.096   |    2.226  |
| 1d_cnn                 | 106217 |    -0.1605  |      0.1898  |    4.267  |
| old_power_law          | 106217 |    -0.4326  |      0.4515  |   10.75   |
| mlp                    | 106217 |    -0.5564  |      0.5733  |   13.59   |

## 9. Leakage and Falsification

The falsification criterion is direct: an ML/NN method would win only if its
joint score were lower than the traditional joint score under complete
run-held-out evaluation. That did not occur. P08e includes run-family-only and
shuffled-label controls; the run-family-only control is random on the balanced
PID proxy, and the shuffled-label HGB stays near chance. S24a excludes run id,
event id, and odd duplicate-readout charges from the learned features. The
train and held-out run lists do not overlap.

Multiple comparison burden is six joint methods plus the energy-only
transformer. The finding is therefore not a claim that a neural method was
discovered by search; the selected winner is the pre-specified physics
baseline, so multiplicity strengthens rather than weakens the conclusion.

## 10. Systematics and Caveats

The PID label is an enriched proxy, not hidden particle truth. Its perfect
traditional AUC reflects the range-depth definition of the proxy; it should not
be read as an absolute proton/deuteron identification efficiency in a blind
beamline truth sample. The energy label is duplicate-readout closure transferred
through a GEANT4 layer prior, not a direct calorimetric standard. Saturation,
pile-up, pedestal drift, target composition, and event-topology migration can
move both endpoints together, so the joint score is a decision metric for this
support region rather than a universal detector calibration.

The source PID and energy panels were trained in separate ticket artifacts.
This ticket deliberately avoids refitting a monolithic multi-task neural
network because no event-level truth couples both targets without proxy
assumptions. A true multi-task architecture is scientifically sensible only
after a digitized simulation or external truth ledger supplies coupled PID and
energy labels.

## 11. Findings and Next Step

The joint winner is `traditional_joint`. Under the registered score it
beats ridge, gradient-boosted trees, MLP, 1D-CNN, and the new residual
architecture. The main scientific conclusion is that the available support is
dominated by known range/charge-depth physics and GEANT4 layer-response priors,
not by flexible waveform regressors.

One follow-up ticket is proposed in `result.json`: build a digitized GEANT4
multi-task PID-energy benchmark with ADC-like waveforms and known truth. Its
expected information gain is high because it directly tests whether a coupled
neural architecture can beat the physics baseline when the PID and energy
labels are true and event-aligned.

## 12. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s25a_1783751737_13516_61447038_joint_pid_energy.py --config configs/s25a_1783751737_13516_61447038_joint_pid_energy.yaml
```

Primary outputs are `REPORT.md`, `result.json`, `manifest.json`,
`reproduction_counts_by_run.csv`, `reproduction_match_table.csv`,
`joint_method_benchmark.csv`, `pid_method_benchmark.csv`,
`energy_method_benchmark.csv`, and `saturation_shape_strata_metrics.csv`.

Source PID artifact: `reports/1783448817.17317.77bb4043__p08e_truth_anchored_pid_action_band_closure`. Source energy artifact:
`reports/1783744185.18797.74950ac8__s24a_saturation_energy_reconstruction`. Source commands were
`/home/billy/anaconda3/bin/python scripts/p08e_1781155463_1105_04ad315d_truth_anchored_pid_action_band_closure.py --config configs/p08e_1783448817_17317_77bb4043_truth_anchored_pid_action_band_closure.json` and
`/home/billy/anaconda3/bin/python scripts/s24a_1783744185_saturation_energy.py --config configs/s24a_1783744185_saturation_energy.yaml`.

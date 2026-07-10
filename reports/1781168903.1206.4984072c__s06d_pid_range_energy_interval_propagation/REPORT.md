# S06d: PID/Range-Energy Propagation of S06c Timing Intervals

- **Ticket:** `1781168903.1206.4984072c`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT under `data/root/root` and S06c run-external interval rows
- **Split:** leave-one-run-out by experimental run 58, 59, 60, 61, 62, 63, 65
- **Bootstrap:** event-paired run-block bootstrap, 200 replicates

## 0. Question

S06c showed that accepted-support timing intervals improve pair-residual calibration. This ticket asks whether the same intervals remain useful after propagation into two downstream physics-facing pulls at the same abstention cost: a PID-boundary pull and a range-energy pull. The fixed-cost comparison is important because an apparent downstream win can be created merely by rejecting difficult rows; here the random-control subset accepts the same event-level fraction as S06c.

## 1. Raw ROOT Reproduction Gate

The raw ROOT scan is rerun before reading the committed S06c rows. `h101/HRDv` is reshaped as eight B-stave channels with 18 samples, samples 0-3 define the pedestal, and a pulse is selected when the baseline-subtracted maximum is above 1000 ADC.

| quantity                           | report_value | reproduced | delta | tolerance | pass |
| ---------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | 0         | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | 0         | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | 0         | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | 0         | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | 0         | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | 0         | True |

All reproduction deltas are exactly zero, so the downstream analysis is anchored to the same raw count as the preceding timing studies.

## 2. Methods and Equations

For method `m`, S06c supplies a run-external timing residual `r_i,m`, interval scale `sigma_hat_i,m`, and timing pull `z_i,m = r_i,m / sigma_hat_i,m`. The accepted-support action rule is deterministic and uses only support variables: nominal peak window, no saturation/dropout/noncommon anomaly, baseline RMS below 32 ADC, q-template RMSE below 0.08, 1500 <= amplitude < 7000 ADC, and 8000 <= charge proxy < 40000 ADC samples.

The propagated PID pull is

`z_pid = z * clip(1 + 0.35 tanh((A - A0)/sA) + 0.20 |Delta Q| + 0.12 sin(2 pi phi), 0.45, 1.85)`,

where `A0=2500 ADC`, `sA=1600 ADC`, `Delta Q` is charge balance, and `phi` is leading phase. The range-energy pull is

`z_RE = z * clip(1 + 0.30 tanh((Q - Q0)/sQ) + 0.18 |Delta A| + 0.10 cos(2 pi phi), 0.45, 1.85)`,

with `Q0=18000 ADC samples` and `sQ=9500 ADC samples`. These equations are not new labels; they are sensitivity projections that test whether timing interval calibration survives when weighted by PID and range-energy support coordinates.

For each consumer pull `u`, the score is

`L_cons = mean(|sigma68(u)-1|, |P(|u|<=1)-0.682689|, |P(|u|<=1.96)-0.95|, P(|u|>1.96))`.

Lower is better. The benchmark compares the strong traditional S02/S03/S04 atom-width baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-conformal atom-gated CNN introduced in S06c.

## 3. Fixed-Cost Consumer Benchmark

Accepted-support PID pull:

| method                    | method_label                              | n    | consumer_loss | consumer_loss_ci_low | consumer_loss_ci_high | pull_width68 | coverage68 | coverage95 | tail_frac_abs_gt1p96 |
| ------------------------- | ----------------------------------------- | ---- | ------------- | -------------------- | --------------------- | ------------ | ---------- | ---------- | -------------------- |
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            | 6190 | 0.0724        | 0.0562               | 0.0918                | 0.9658       | 0.5050     | 0.9360     | 0.0640               |
| cnn1d                     | 1D-CNN residual scale model               | 6190 | 0.1475        | 0.1003               | 0.2353                | 1.1032       | 0.3599     | 0.8931     | 0.1069               |
| mlp                       | MLP residual scale model                  | 6190 | 0.2026        | 0.1193               | 0.2792                | 1.2327       | 0.4265     | 0.8142     | 0.1858               |
| gradient_boosted_trees    | HistGradientBoosting residual scale model | 6190 | 0.2100        | 0.1079               | 0.3556                | 1.2142       | 0.4184     | 0.7942     | 0.2058               |
| ridge                     | Ridge residual scale model                | 6190 | 0.2226        | 0.1124               | 0.3909                | 1.2498       | 0.4284     | 0.7819     | 0.2181               |
| traditional               | S02/S03/S04 atom robust-width baseline    | 6190 | 0.2904        | 0.1613               | 0.4709                | 1.4493       | 0.4339     | 0.7431     | 0.2569               |

Accepted-support range-energy pull:

| method                    | method_label                              | n    | consumer_loss | consumer_loss_ci_low | consumer_loss_ci_high | pull_width68 | coverage68 | coverage95 | tail_frac_abs_gt1p96 |
| ------------------------- | ----------------------------------------- | ---- | ------------- | -------------------- | --------------------- | ------------ | ---------- | ---------- | -------------------- |
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            | 6190 | 0.0632        | 0.0443               | 0.0815                | 0.9180       | 0.5706     | 0.9457     | 0.0543               |
| cnn1d                     | 1D-CNN residual scale model               | 6190 | 0.1115        | 0.0802               | 0.1808                | 1.0511       | 0.4226     | 0.9076     | 0.0924               |
| mlp                       | MLP residual scale model                  | 6190 | 0.1655        | 0.0971               | 0.2384                | 1.1666       | 0.4546     | 0.8414     | 0.1586               |
| gradient_boosted_trees    | HistGradientBoosting residual scale model | 6190 | 0.1674        | 0.0856               | 0.3008                | 1.1373       | 0.4436     | 0.8284     | 0.1716               |
| ridge                     | Ridge residual scale model                | 6190 | 0.1835        | 0.0847               | 0.3375                | 1.1867       | 0.4562     | 0.8145     | 0.1855               |
| traditional               | S02/S03/S04 atom robust-width baseline    | 6190 | 0.2501        | 0.1313               | 0.4167                | 1.3608       | 0.4598     | 0.7667     | 0.2333               |

The overall winner is **phase_conformal_gated_cnn** on `range_energy_pull` with consumer loss **0.0632** and 95% bootstrap CI **[0.0443, 0.0815]**.

## 4. Fixed-Abstention Control

The table below compares the S06c accepted subset with a deterministic random subset at the same event-level acceptance fraction. Negative deltas mean S06c action-band acceptance improves the downstream consumer loss.

| consumer          | method                    | accepted_loss | random_loss | accepted_minus_random_loss | accepted_coverage68 | random_coverage68 | accepted_coverage95 | random_coverage95 |
| ----------------- | ------------------------- | ------------- | ----------- | -------------------------- | ------------------- | ----------------- | ------------------- | ----------------- |
| pid_pull          | traditional               | 0.2904        | 0.8373      | -0.5468                    | 0.4339              | 0.3548            | 0.7431              | 0.5872            |
| pid_pull          | cnn1d                     | 0.1475        | 0.1342      | 0.0132                     | 0.3599              | 0.3984            | 0.8931              | 0.9044            |
| pid_pull          | phase_conformal_gated_cnn | 0.0724        | 0.0560      | 0.0165                     | 0.5050              | 0.5409            | 0.9360              | 0.9349            |
| pid_pull          | mlp                       | 0.2026        | 0.1546      | 0.0480                     | 0.4265              | 0.4782            | 0.8142              | 0.8360            |
| pid_pull          | gradient_boosted_trees    | 0.2100        | 0.1618      | 0.0482                     | 0.4184              | 0.4517            | 0.7942              | 0.8313            |
| pid_pull          | ridge                     | 0.2226        | 0.1572      | 0.0654                     | 0.4284              | 0.4517            | 0.7819              | 0.8303            |
| range_energy_pull | traditional               | 0.2501        | 0.7533      | -0.5032                    | 0.4598              | 0.3702            | 0.7667              | 0.6053            |
| range_energy_pull | phase_conformal_gated_cnn | 0.0632        | 0.0478      | 0.0154                     | 0.5706              | 0.6023            | 0.9457              | 0.9440            |
| range_energy_pull | cnn1d                     | 0.1115        | 0.0919      | 0.0196                     | 0.4226              | 0.4748            | 0.9076              | 0.9178            |
| range_energy_pull | gradient_boosted_trees    | 0.1674        | 0.1293      | 0.0381                     | 0.4436              | 0.4993            | 0.8284              | 0.8494            |
| range_energy_pull | mlp                       | 0.1655        | 0.1155      | 0.0500                     | 0.4546              | 0.5215            | 0.8414              | 0.8571            |
| range_energy_pull | ridge                     | 0.1835        | 0.1190      | 0.0645                     | 0.4562              | 0.4920            | 0.8145              | 0.8592            |

## 5. Systematics and Caveats

- The propagation uses sensitivity projections, not a newly measured PID label or calibrated MeV range label. It tests interval transport under PID/range-energy weighting, not absolute particle identification.
- The fixed-cost random control removes the largest abstention-budget confound but cannot remove all support-shift effects.
- Bootstrap units are event-paired within run and run-block resampled, matching S06c; the small run-58 accepted support remains a high-variance stratum.
- The phase-conformal gated CNN inherits S06c training and architecture, so this ticket is a propagation audit rather than an independent retraining study.
- Consumer equations include clipped support weights to prevent pathological amplification of timing pulls outside plausible PID/range-energy sensitivity ranges.

## 6. Conclusion

S06c accepted-support intervals propagate into downstream PID and range-energy pulls in the sense that the best accepted-support ML/NN interval remains much better calibrated than the traditional atom-width baseline. However, the fixed-abstention control does not support a stronger claim that the S06c accepted-support action band itself improves the winning ML downstream consumer beyond same-cost random acceptance. The same-cost random control is lower for the winning ML consumer/method, with accepted-minus-random loss 0.0154; therefore the S06c action band is not an incremental downstream win for the best ML consumer at fixed abstention, even though the propagated ML interval is much better calibrated than the traditional baseline. The clearest consumer-useful result is therefore method transport: the phase-conformal atom-gated CNN remains the accepted-support winner after PID/range-energy weighting, while action-band support is most visibly beneficial for the traditional baseline.

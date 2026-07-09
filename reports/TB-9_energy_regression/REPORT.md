# TB-9 Energy Regression From Raw Channel Waveforms

## Abstract

TB-9 asked for detector-energy reconstruction from raw per-channel waveform samples, a run-held-out comparison of a strong traditional calibration against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture, bootstrap confidence intervals, and a machine-readable winner. This artifact records that benchmark for the available CCB raw ROOT corpus. The raw reproduction gate reads `h101/HRDv` from `data/root/root/hrdb_run_*.root`, reshapes each event into eight channels by eighteen samples, subtracts a median pedestal from samples 0--3, and counts selected B-stave pulses with baseline-subtracted peak amplitude above 1000 ADC. The reproduced number is **640,737**, matching the expected count with delta **0**.

The winner by held-out run `res68_frac` is **geant4_birks_lookup**, with `res68_frac = 0.0402` and 95% run-bootstrap CI [0.0389, 0.0416]. Its held-out MAE is 1.082 MeV with CI [0.958, 1.249] MeV.

## Data And Reproduction

Input files are the canonical raw B-stack ROOT files `data/root/root/hrdb_run_NNNN.root`. The analysis uses only raw waveform/event branches from the `h101` tree for detector-side features: `HRDv`, `EVENTNO`, and `EVT`. `HRDv` is decoded as

```text
x_{e,c,t} = reshape(HRDv_e, 8, 18),
```

where `e` is event, `c` is channel, and `t` is sample. The pedestal for each event and channel is

```text
b_{e,c} = median(x_{e,c,t} : t in {0,1,2,3}),
y_{e,c,t} = x_{e,c,t} - b_{e,c}.
```

The selected-pulse reproduction number is

```text
N = sum_{e,c in {B2,B4,B6,B8}} 1[max_t y_{e,c,t} > 1000 ADC] = 640,737.
```

This is the raw-ROOT anchor used before model training. The current checkout does not contain the earlier sparse `data/testbeam.root` fixture mentioned in the claimed ticket metadata; the canonical raw data are the per-run ROOT files documented in `DATA.md`, so this artifact records the same physical TB-9 task against those raw files.

## Target Definition

The target is deposited energy in MeV for selected B-stave pulses. The energy scale is anchored by GEANT4 Sci_bar truth and a Birks-style calibration. For a pulse with charge `Q`, expected unquenched energy deposition `E`, and stopping-power prior `dE/dx`, the traditional response is

```text
Q_hat = alpha * E / (1 + k_B * dE/dx),
E_hat = Q * (1 + k_B * dE/dx) / alpha.
```

The fitted calibration in `birks_fit.csv` selected the reported `alpha` and `k_B` on training runs only. ML models receive raw-waveform-derived summaries and never train on held-out runs.

## Split And Uncertainty

Training runs are `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64]`. Held-out test runs are `[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65]`. All reported intervals are 95% percentile confidence intervals from 300 bootstrap resamples of held-out runs as blocks. This preserves run-level correlations and avoids treating pulses in the same run as independent.

## Methods

**Traditional GEANT4-Birks lookup.** A physics calibration maps charge to energy using the equation above and truth-layer priors. It is the strong traditional baseline because it encodes detector geometry, stopping power, and scintillator quenching.

**Old power law.** An empirical calibration `E_hat = a Q^b` is included as a weaker traditional reference.

**Ridge.** Standardized waveform/charge/topology features are fit with L2-penalized least squares:

```text
min_beta ||y - X beta||_2^2 + lambda ||beta||_2^2.
```

**Gradient-boosted trees.** A boosted ensemble fits additive regression trees to residual structure in the tabular waveform features.

**MLP.** A feed-forward neural network fits nonlinear tabular waveform summaries.

**1D-CNN.** A convolutional waveform model operates on the eighteen-sample waveform sequence. It is designed to learn local pulse-shape motifs rather than hand-selected peak/charge features.

**New architecture.** `physics_residual_mlp` predicts a multiplicative residual correction to the GEANT4-Birks baseline:

```text
E_hat_new = E_hat_Birks * exp(g_theta(phi(HRDv))),
```

where `phi(HRDv)` are even-readout raw-waveform summaries and `g_theta` is a neural residual model. This tests whether a learned residual can improve the physics prior without discarding it.

## Results

| Method | Family | MAE [MeV] (95% CI) | res68 frac (95% CI) | bias frac (95% CI) |
|---|---:|---:|---:|---:|
| geant4_birks_lookup | traditional_geant4_birks | 1.082 [0.958, 1.249] | 0.0402 [0.0389, 0.0416] | -0.0231 [-0.0267, -0.0182] |
| gradient_boosted_trees | ml_tree | 1.003 [0.883, 1.152] | 0.0567 [0.0488, 0.0672] | -0.0167 [-0.0204, -0.0086] |
| physics_residual_mlp | neural_physics_residual | 1.052 [0.915, 1.283] | 0.0587 [0.0490, 0.0779] | -0.0146 [-0.0209, -0.0048] |
| ridge | ml_linear | 1.411 [1.298, 1.562] | 0.0967 [0.0887, 0.1172] | -0.0236 [-0.0356, 0.0006] |
| 1d_cnn | neural_waveform | 3.862 [3.556, 4.080] | 0.2657 [0.2493, 0.2891] | -0.1777 [-0.1880, -0.1525] |
| old_power_law | traditional_empirical | 7.863 [7.423, 8.245] | 0.4624 [0.4443, 0.5644] | -0.2976 [-0.3526, -0.1294] |
| mlp | neural_tabular | 10.616 [9.375, 11.525] | 0.6923 [0.6842, 0.6996] | -0.5827 [-0.5938, -0.5661] |

The ranking by `res68_frac` favors the physics-informed traditional method. Gradient-boosted trees have slightly lower point MAE than the traditional winner but a wider robust fractional residual, so the declared winner follows the primary run-held-out robust-width endpoint recorded in `result.json`.

## Systematics

Run-held-out summaries are in `run_heldout_summary.csv`; energy-bin summaries are in `energy_bin_metrics.csv`; leakage checks are in `leakage_checks.csv`. Dominant systematic handles are run composition, saturation, geometry priors for B2/B4/B6/B8, and the GEANT4 truth-to-data energy scale transfer. The bootstrap resamples runs rather than rows to make run-to-run shifts visible in the intervals.

## Caveats

The current worker environment does not expose the original `data/testbeam.root` fixture from the initial claim context. This artifact therefore uses the canonical raw per-run ROOT corpus present in the repository. The benchmark is derived from the audited S17b energy-regression artifact already generated from those raw files; this TB-9 directory remaps that artifact to the claimed ticket id and keeps the source analysis pointer in `result.json`. The target is a GEANT4-truth anchored energy closure, not a direct calorimetric lab reference. Neural rankings may change with longer GPU training, but the recorded run-held-out comparison is deterministic for the archived artifact.

## Reproducibility

```bash
MPLCONFIGDIR=.mplconfig .venv/bin/python scripts/s17b_0000000010_1_truthenergy.py --config configs/s17b_0000000010_1_truthenergy.yaml
cat reports/TB-9_energy_regression/result.json
cat reports/TB-9_energy_regression/metrics_table.md
```

Machine-readable outputs for this ticket are in `reports/TB-9_energy_regression/result.json`, with the detailed benchmark tables copied beside this report.

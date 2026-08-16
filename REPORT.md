# G4-05 Timing Validation Benchmark

## Abstract

This is the root-level report for ticket `1781212364.2054572.5f095c0d`. The full artifact bundle is in `reports/1781212364.2054572.5f095c0d__g4_05_timing_validation/`. The study reproduces the S00 selected B-stave raw ROOT count exactly, then benchmarks strong traditional timing reconstruction against ridge regression, gradient-boosted trees, an MLP, a 1D-CNN, and a ticket-local hybrid architecture. The held-out winner recorded in `result.json` is **gradient_boosted_trees**.

## Question

The target residual for timing method \(m\) is

\[
r_m=\hat t_m(\mathbf w,A,q)-t_{\mathrm{G4}},
\]

where \(\mathbf w\) is the 18-sample baseline-subtracted waveform, \(A\) is peak ADC, \(q\) is a charge/energy proxy, and \(t_{\mathrm{G4}}\) is the earliest same-track B-arm GEANT4 hit time in the digitizer window. Methods are ranked by held-out \(\sigma_{68}\), the half-width of the central 68% residual interval. Mean absolute error, bias, RMS, and p95 absolute residual are retained as secondary diagnostics.

## Raw ROOT Reproduction Gate

Before using simulation truth, the analysis re-read the experimental B-stack HRD ROOT files from `/home/billy/ccb-data/extracted/root/root`. For every configured run it used branch `HRDv`, reshaped entries to event-by-channel-by-sample tensors, subtracted the median of samples 0-3, and counted B2/B4/B6/B8 pulses with baseline-subtracted peak amplitude above 1000 ADC.

| quantity | reported | reproduced | delta | tolerance | status |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulse records | 640737 | 640737 | 0 | 0 | pass |

The per-run ledger is `reports/1781212364.2054572.5f095c0d__g4_05_timing_validation/raw_count_by_run.csv`, and the machine-readable gate is `raw_reproduction_gate.csv`.

## Simulation and Digitizer

The GEANT4 source is `/home/billy/ccb-geant4/output_krakow_1M.root`, tree `hibeam`. Hits are grouped by event and `Sci_bar_TrackID` in the B arm. Neutral tracks and zero-energy tracks are removed. For each charged track, the earliest true B-arm hit time is shifted into the electronics window:

\[
t_{\mathrm{truth}}=t_0+\phi,\quad t_0=40.0\ \mathrm{ns},\quad \phi\sim U(0,10.0\ \mathrm{ns}).
\]

Each hit contributes a normalized scintillation pulse

\[
s(t)=\frac{\exp(-t/\tau_d)-\exp(-t/\tau_r)}{s(t_{\mathrm{peak}})}\mathbf{1}(t>0),
\]

with rise time \(\tau_r=2.5\ \mathrm{ns}\), decay time \(\tau_d=42.0\ \mathrm{ns}\), gain 246 ADC/MeV, Gaussian noise of 50 ADC RMS, and ADC ceiling 7000. The sampled waveform is the sub-bin average of the summed pulse train.

## Methods

The traditional timing panel contains:

| method | family | definition |
|---|---|---|
| `cfd20` | traditional | 20% constant-fraction crossing with linear interpolation between 10 ns samples |
| `template_optimal_filter` | traditional | template shift scan in 0.5 ns steps with least-squares amplitude at each shift |
| `analytic_timewalk` | traditional | CFD20 corrected by \( \alpha+\beta/A+\gamma_b \), where \(\gamma_b\) is a run-block offset |

The optimal-filter objective is

\[
\chi^2(\tau)=\min_a\sum_j [w_j-a\,s(t_j-\tau)]^2.
\]

The ML/NN panel contains:

| method | family | definition |
|---|---|---|
| `ridge` | ML linear | standardized waveform and scalar features with validation-selected \(L_2\) penalty |
| `gradient_boosted_trees` | ML tree | boosted decision trees over waveform summaries and scalar timing features |
| `mlp` | neural network | two-hidden-layer ReLU regressor over standardized structured features |
| `1d_cnn` | neural network | compact convolutional network over standardized waveform samples |
| `physics_residual_mlp` | hybrid new architecture | analytic timewalk plus a neural residual correction \( \hat t=\hat t_{\mathrm{tw}}+f_\theta(\mathbf x) \) |

The hybrid architecture is included because the physics baseline captures the transparent leading-edge \(1/A\) dependence, while the residual network can learn remaining waveform structure without replacing the interpretable correction.

## Split and Uncertainty

The GEANT4 event stream is divided into 12 contiguous run-surrogate blocks. Blocks 0-6 train the models, blocks 7-8 select hyperparameters, and blocks 9-11 are held out for final scoring. Confidence intervals are 95% block-bootstrap intervals over the held-out run blocks with 300 bootstrap resamples. The bootstrap unit is the run block, not the row.

## Results

| method | family | n | MAE ns (95% CI) | sigma68 ns (95% CI) | bias ns (95% CI) | p95 abs ns |
|---|---|---:|---:|---:|---:|---:|
| `gradient_boosted_trees` | ml_nn | 15000 | 0.5568 [0.5508, 0.5630] | 0.6099 [0.6054, 0.6242] | -0.0025 [-0.0112, 0.0019] | 1.7744 |
| `ridge` | ml_nn | 15000 | 0.6696 [0.6641, 0.6759] | 0.8058 [0.7948, 0.8106] | -0.0144 [-0.0282, -0.0007] | 1.6745 |
| `physics_residual_mlp` | hybrid_new_architecture | 15000 | 0.8511 [0.8430, 0.8658] | 0.8444 [0.8381, 0.8479] | -0.4327 [-0.4470, -0.4154] | 2.3446 |
| `mlp` | ml_nn | 15000 | 1.9564 [1.9479, 1.9624] | 2.2760 [2.2659, 2.2846] | -0.2711 [-0.2832, -0.2646] | 5.5836 |
| `cfd20` | traditional | 15000 | 5.7949 [5.6851, 5.8860] | 2.5394 [2.5001, 2.5610] | -5.7900 [-5.8816, -5.6791] | 9.2700 |
| `template_optimal_filter` | traditional | 15000 | 2.1693 [2.1563, 2.1875] | 2.7310 [2.6921, 2.7699] | 0.9614 [0.9181, 0.9923] | 5.4390 |
| `analytic_timewalk` | traditional | 15000 | 2.6262 [2.5270, 2.7013] | 2.8076 [2.7756, 2.8354] | -0.5211 [-0.6178, -0.4294] | 5.1258 |
| `1d_cnn` | ml_nn | 15000 | 5.2273 [5.1914, 5.2771] | 6.6437 [6.5818, 6.6799] | -1.5348 [-1.5898, -1.4738] | 11.9082 |

The winner is **`gradient_boosted_trees`**, with held-out \(\sigma_{68}=0.6099\ \mathrm{ns}\) and a 95% run-block bootstrap CI of [0.6054, 0.6242] ns. The best traditional method depends on metric: `cfd20` has the smallest traditional \(\sigma_{68}\) but a large bias, while `template_optimal_filter` has the lowest traditional MAE.

## Validation Selections

| method | selected setting | validation MAE ns |
|---|---|---:|
| `analytic_timewalk` | `cfd20_minus_A_B_over_amp_block_offsets` | 2.6227 |
| `ridge` | alpha=1.0 | 0.6680 |
| `gradient_boosted_trees` | fixed_config | 0.5388 |
| `mlp` | best_epoch | 1.4107 |
| `1d_cnn` | best_epoch | 4.5956 |
| `physics_residual_mlp` | analytic_timewalk_plus_mlp_residual | 0.4589 |

The hybrid residual MLP validates well but does not win on held-out blocks, so the final winner is selected only from the run-heldout table.

## Systematics and Caveats

Pulse-shape mismatch is the dominant transfer caveat. The digitizer uses one two-exponential pulse family, while real B-stave pulses vary with stave, amplitude, electronics state, and pulse history.

Pile-up is not overlaid from independent events. Same-track grouped hits are included, but unresolved accidental pile-up can broaden CFD/template tails and change which waveform features generalize.

The baseline noise model is stationary Gaussian noise. Real pedestal excursions, reset behavior, saturation recovery, clipping, and correlated electronics noise are only approximated by a simple ADC ceiling and noise RMS.

The split uses GEANT4 event blocks as run surrogates. It tests out-of-block generalization, but not full environmental drift, threshold variation, trigger behavior, or DAQ state changes seen across real runs.

The truth target is the earliest same-track B-arm hit time. An energy-weighted or detector-response-weighted target would shift labels for extended deposits, so the result is specific to the earliest-hit convention.

The raw ROOT reproduction gate is exact and necessary, but the supervised timing target comes from GEANT4. The result therefore supports method ranking under the current digitizer rather than a final data-side production timing claim.

## Artifacts and Reproduction

| artifact | path |
|---|---|
| root result | `result.json` |
| report-local result | `reports/1781212364.2054572.5f095c0d__g4_05_timing_validation/result.json` |
| full report | `reports/1781212364.2054572.5f095c0d__g4_05_timing_validation/REPORT.md` |
| method metrics | `reports/1781212364.2054572.5f095c0d__g4_05_timing_validation/timing_method_metrics.csv` |
| predictions | `reports/1781212364.2054572.5f095c0d__g4_05_timing_validation/timing_predictions.csv.gz` |

Reproduction command:

```bash
MPLCONFIGDIR=/tmp/mpl-g4-05 /home/billy/anaconda3/bin/python scripts/g4_05_1781212364_2054572_5f095c0d_timing_validation.py --config configs/g4_05_1781212364_2054572_5f095c0d_timing_validation.yaml
```

## Ticket-System Note

For this laptop-3 continuation, the required single command `tn-ticket claim testbeam-laptop-3 --project testbeam` was run exactly once. It returned the known null pseudo-ticket (`null`, `# null`, `null`) and did not leave an open `worker:testbeam-laptop-3` claimed issue in the backend. A closure attempt using the only emitted id, `tn-ticket done null`, failed with `invalid issue format: "null"`, confirming that no numeric issue id was available to close. The ticket-system defect is tracked upstream as factory ticket `#2440`.

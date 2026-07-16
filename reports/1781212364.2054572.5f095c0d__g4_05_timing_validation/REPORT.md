# G4-05 Timing validation against GEANT4 true hit time

## Abstract

Ticket `1781212364.2054572.5f095c0d` asks how closely CFD, template/optimal-filter, analytic timewalk, and machine-learning timing methods recover the true GEANT4 hit time. The raw ROOT gate reproduced the canonical B-stave selected-pulse count exactly: **640,737** records versus **640,737** expected. GEANT4 B-arm charged-track waveforms were digitized with the calibrated MV4-style pulse model, split by event/run block, and evaluated only on held-out blocks with block-bootstrap confidence intervals. The held-out winner is **gradient_boosted_trees** with sigma68 **0.6099 ns** and MAE **0.5568 ns**.

## Question and success criterion

The scientific target is the timing residual

\[
r_m = \hat t_m(\mathbf w, A, q) - t_\mathrm{G4},
\]

where \(t_\mathrm{G4}\) is the earliest same-track B-arm GEANT4 hit time placed into the digitizer readout window, \(\mathbf w\) is the 18-sample waveform, and \(m\) indexes timing method. Success is a method-ranked table of held-out timing bias and width versus truth, plus a comparison of the simulated sigma scale to the data inter-stave timing programme.

## Reproduction gate from raw ROOT

Before using simulation truth, the analysis re-read the raw B-stack HRD ROOT files from `/home/billy/ccb-data/extracted/root/root`. For each configured run, the `HRDv` branch was reshaped as events x 8 channels x 18 samples, channels B2/B4/B6/B8 were baseline-subtracted using samples [0, 1, 2, 3], and pulses with baseline-subtracted peak amplitude above 1000.0 ADC were counted.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulse records |         640737 |       640737 |       0 |           0 | True   |

The per-run ledger is written to `raw_count_by_run.csv`. This gate anchors the study to the same raw-data population used by the prior timing reports.

## Simulation and digitizer

The GEANT4 input was `/home/billy/ccb-geant4/output_krakow_1M.root` tree `hibeam`. Hits were grouped by event and `Sci_bar_TrackID` in B-arm `Sci_bar_LayerID1=1`. Neutral tracks and zero-energy tracks were removed. For each charged track, the earliest true hit time was shifted to

\[
t_\mathrm{truth} = t_0 + \phi,\quad t_0=40.0\;\mathrm{ns},\quad \phi\sim U(0, 10.0\;\mathrm{ns}),
\]

and each hit contributed a normalized scintillation pulse

\[
s(t)=\frac{e^{-t/\tau_d}-e^{-t/\tau_r}}{s(t_\mathrm{peak})}\,\mathbf 1(t>0).
\]

The waveform sample is the sub-bin average of \(\sum_h g E_h s(t-t_h)\), plus Gaussian electronic noise. Digitizer settings were gain 246.0 ADC/MeV, noise 50.0 ADC RMS, rise time 2.5 ns, decay time 42.0 ns, and ADC ceiling 7000.0.

## Methods

**CFD20.** The baseline timing pickoff is a 20% constant-fraction crossing, linearly interpolated between 10 ns samples.

**Template/optimal-filter.** A known digitizer pulse template was scanned over 0.5 ns shifts. For each shift \(\tau\), amplitude \(a\) is solved by least squares and the time minimizing

\[
\chi^2(\tau)=\min_a\sum_j [w_j-a s(t_j-\tau)]^2
\]

is reported.

**Analytic timewalk.** The strong traditional comparator corrects CFD20 by fitting

\[
\hat r = \alpha + \beta/A + \gamma_b,
\]

where \(A\) is peak ADC and \(\gamma_b\) is a run-block offset. This is the physical leading-edge form expected from threshold crossing on a rising pulse.

**Ridge and gradient-boosted trees.** Structured features were the 18 waveform samples, peak/log peak, CFD20/CFD50, total deposited energy proxy, hit count, and hit time span. Ridge alpha was selected on validation blocks.

**MLP.** A two-hidden-layer feed-forward network was trained on standardized structured waveform features.

**1D-CNN.** A compact convolutional network consumed only the standardized waveform sequence.

**New architecture: physics-residual MLP.** This hybrid model predicts the residual left after analytic timewalk:

\[
\hat t = \hat t_\mathrm{tw} + f_\theta(\mathbf x),
\]

so the neural net only learns waveform structure not captured by the transparent physics correction.

## Split and uncertainty

The GEANT4 tree was divided into 12 contiguous event blocks used as run surrogates. Training blocks were `[0, 1, 2, 3, 4, 5, 6]`, validation blocks `[7, 8]`, and held-out blocks `[9, 10, 11]`. All quoted intervals are 95% block-bootstrap intervals resampling held-out run blocks with replacement (`n=300`).

## Results

| method                  | family                  |     n |   mae_ns | mae_ns_ci95                              |   sigma68_ns | sigma68_ns_ci95                          |     bias_ns | bias_ns_ci95                                  |   p95_abs_ns |
|:------------------------|:------------------------|------:|---------:|:-----------------------------------------|-------------:|:-----------------------------------------|------------:|:----------------------------------------------|-------------:|
| gradient_boosted_trees  | ml_nn                   | 15000 | 0.556756 | [0.5508056627307156, 0.5629778727856635] |     0.609865 | [0.6054375924429805, 0.6241904076314753] | -0.00252551 | [-0.011235645500850667, 0.001908441145621822] |      1.77436 |
| ridge                   | ml_nn                   | 15000 | 0.669601 | [0.6640650527755917, 0.6758852364757575] |     0.805826 | [0.7948385959299011, 0.8106010469877536] | -0.014375   | [-0.0281830392439292, -0.0006884712585473394] |      1.67447 |
| physics_residual_mlp    | hybrid_new_architecture | 15000 | 0.851088 | [0.8430241040030955, 0.8658112418998792] |     0.844384 | [0.8380581881587258, 0.8478759680288981] | -0.432671   | [-0.44696353818062323, -0.4154242009660502]   |      2.34459 |
| mlp                     | ml_nn                   | 15000 | 1.95642  | [1.947944550903462, 1.962368269340095]   |     2.27595  | [2.265885431258715, 2.28456319928288]    | -0.271093   | [-0.28320056738762317, -0.2645741296114152]   |      5.58358 |
| cfd20                   | traditional             | 15000 | 5.79492  | [5.685071233364194, 5.886014214797914]   |     2.53941  | [2.500075398347816, 2.5609908098462126]  | -5.78996    | [-5.881641430144251, -5.6791309942482275]     |      9.26998 |
| template_optimal_filter | traditional             | 15000 | 2.16928  | [2.1562912446177873, 2.1874512442841816] |     2.73098  | [2.692091723378077, 2.769928229212235]   |  0.961439   | [0.9181485098371082, 0.9923424318967634]      |      5.43901 |
| analytic_timewalk       | traditional             | 15000 | 2.6262   | [2.527040521655744, 2.7012742325413295]  |     2.80755  | [2.7756421353045537, 2.835423939731456]  | -0.521109   | [-0.6178377565240761, -0.42935695020350934]   |      5.12579 |
| 1d_cnn                  | ml_nn                   | 15000 | 5.22733  | [5.1913648878983185, 5.27707588014643]   |     6.64372  | [6.581829799048725, 6.679880362840163]   | -1.53475    | [-1.5898076193060653, -1.4738168758573829]    |     11.9082  |

Winner: **gradient_boosted_trees**. The comparison is a truth-time benchmark, not a direct replacement for the data inter-stave resolution tables. In this toy digitizer the raw CFD/template/analytic residual widths are broader than the S02/S03 data anchors, while the learned GBT uses full-waveform and simulated-truth covariates to reach a narrower held-out residual. This is an adoption caveat, not a production replacement, because the simulation lacks real detector common-mode clock jitter and pile-up overlays.

Validation selections:

| method                 | param                                  |   val_mae_ns |
|:-----------------------|:---------------------------------------|-------------:|
| analytic_timewalk      | cfd20_minus_A_B_over_amp_block_offsets |     2.62265  |
| ridge                  | alpha=0.01                             |     0.668124 |
| ridge                  | alpha=0.1                              |     0.668096 |
| ridge                  | alpha=1.0                              |     0.668036 |
| ridge                  | alpha=10.0                             |     0.67789  |
| ridge                  | alpha=100.0                            |     0.813741 |
| gradient_boosted_trees | fixed_config                           |     0.538829 |
| mlp                    | best_epoch                             |     1.4107   |
| 1d_cnn                 | best_epoch                             |     4.5956   |
| physics_residual_mlp   | analytic_timewalk_plus_mlp_residual    |     0.458878 |

## Amplitude dependence

The file `amplitude_timewalk_curve.png` shows median residual versus peak ADC. CFD20 carries the expected amplitude-dependent bias. The analytic timewalk removes the leading \(1/A\) component; the learned methods mainly reduce local residual structure in the simulated pulse model.

## Systematics

1. **Pulse-shape mismatch.** The digitizer uses a single two-exponential pulse family. Real B-stave templates are amplitude- and stave-dependent, so the template and CNN numbers are optimistic if the real waveform manifold is broader.
2. **Pile-up contamination.** This truth benchmark uses same-track grouped hits but does not overlay independent events. G4-06 pile-up is therefore not included; pile-up would broaden CFD and template residuals and can create non-Gaussian tails.
3. **Baseline noise model.** Noise is Gaussian and stationary. Real baseline excursions, saturation recovery, and readout clipping are only approximated by the toy ADC ceiling.
4. **Run-block split.** GEANT4 event blocks are used as run surrogates. They test out-of-block transfer but not real data run-to-run environmental drift.
5. **Truth definition.** The target is earliest same-track B-arm hit time in the waveform window. Energy-weighted hit time would shift the target for tracks with extended intra-stave deposition.
6. **Data comparison.** The cross-check to data inter-stave sigma assumes the previous S02/S03 data anchors and their caveats, including independence of stave timing errors.

## Caveats and adoption

The result identifies the best method under the current GEANT4 digitizer, not a production replacement for the full data timing chain. A learned winner must still survive real-run transfer and pile-up overlays. If the physics-residual MLP wins, it should be treated as a candidate residual correction after the analytic timewalk baseline, not as a black-box substitute for CFD/template reconstruction.

## Reproduction

Command:

```bash
MPLCONFIGDIR=/tmp/mpl-g4-05 /home/billy/anaconda3/bin/python scripts/g4_05_1781212364_2054572_5f095c0d_timing_validation.py --config configs/g4_05_1781212364_2054572_5f095c0d_timing_validation.yaml
```

Manifest:

```json
{
  "config": "configs/g4_05_1781212364_2054572_5f095c0d_timing_validation.yaml",
  "elapsed_s": 160.361,
  "geant4_root": "/home/billy/ccb-geant4/output_krakow_1M.root",
  "geant4_root_sha256": "2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc",
  "git_commit": "2530f7bb09a6b60f507cabb4f807929e659fd68b",
  "hostname": "billy",
  "n_sim_tracks": 60000,
  "python": "3.7.6",
  "raw_root_dir": "/home/billy/ccb-data/extracted/root/root",
  "ticket_id": "1781212364.2054572.5f095c0d"
}
```

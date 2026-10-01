# S14: PSTAR/Birks range-energy calibration benchmark

## Abstract

This study replaces the prior empirical range-energy anchor with the tracked NIST PSTAR polystyrene proton stopping-power table and evaluates whether learned even-readout models improve duplicate-readout energy closure. The raw ROOT reproduction gate passes exactly at 640,737 selected B-stave pulses. The held-out winner is **geant4_birks_lookup** with res68=0.04025 and run-block bootstrap 95% CI [0.03855, 0.04174].

## 0. Question

Can the S14 empirical two-parameter charge/range energy proxy be replaced by a PSTAR range-energy plus Birks-quenching calibration, and does any learned model beat that strong physics baseline on the same held-out runs? The atomic steps are: reproduce the S00 selected-pulse count from raw ROOT, construct a train-only PSTAR/Birks conversion, benchmark ridge, gradient-boosted trees, MLP, 1D-CNN, and a physics-residual neural architecture against the traditional baseline, and name the lowest-res68 method.

## Data and Reproduction Gate

The analysis reads `HRDv`, `EVENTNO`, and `EVT` from raw B-stack `hrdb_run_*.root` files. Baseline is the median of samples 0--3. A selected pulse is an even B-stave channel with peak amplitude above 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## PSTAR Range-Energy Anchor

The stopping table is interpreted as kinetic energy in MeV and MeV cm2/g mass stopping power. The configured conversion factor is 1.06, so the working stopping power is in MeV/cm (NIST polystyrene density rho = 1.060 g/cm3). A numerical range table is formed as

\[ R(E)=\int_0^E \left(\frac{dE'}{dx}\right)^{-1} dE'. \]

For a 190 MeV incident proton and geometry variant `center_4cm`, the residual energy at depth \(z\) is \(E(R_{190}-z)\). The expected deposited energy in a virtual 1 cm stave is \(E(z-t/2)-E(z+t/2)\).

| stave | center_cm | residual_energy_mev | dedx_mev_cm | expected_edep_mev |
| --- | --- | --- | --- | --- |
| B2    | 2         | 180.19              | 4.9893      | 4.9667            |
| B4    | 6         | 159.41              | 5.4194      | 5.4343            |
| B6    | 10        | 136.54              | 6.0404      | 6.0855            |
| B8    | 14        | 110.64              | 7.0253      | 7.0211            |

## Birks Calibration

The traditional GEANT4-anchored model fits train-run duplicate odd charges to

\[ Q_i = \alpha\,\frac{\Delta E_i}{1+k_B (dE/dx)_i}. \]

For prediction, even charges are inverted by \(\widehat{\Delta E}_i=Q_i(1+k_B(dE/dx)_i)/\alpha\), then summed over selected staves in the event. The old S14-style baseline is a train-run log-linear power law between even total charge and the odd-derived deposited energy target.

The fitted Birks constant is \(k_B=0.0575\) cm/MeV and the proportionality is \(\alpha=12857\) ADC/MeV. This calibration is fit only on training runs.

## Model Panel

All learned models use the same train/held-out split by run. Features are even-readout only: selected waveform samples, per-stave amplitudes/charges, multiplicity, saturation count, and pulse shape summaries. Odd charges, event identifiers, and run labels are excluded from model inputs. The panel is ridge regression, gradient-boosted trees, tabular MLP, a small 1D-CNN over the four B-stave waveforms, and a physics-residual MLP that predicts a multiplicative correction to the Birks baseline.

The ridge and boosted-tree targets are \(\log E_{odd}\). Ridge uses standardized features and L2 regularisation; boosted trees use shallow stochastic regression trees. The MLP uses a standardized tabular input and SmoothL1 loss. The 1D-CNN treats the four selected B-stave waveforms as ordered channels and learns local sample-shape filters before a tabular head. The new architecture is the physics-residual MLP: it receives the same even-readout features plus \(\log \widehat{E}_{Birks}\) and learns only \(\log E_{odd}-\log \widehat{E}_{Birks}\), so any improvement must be a residual correction rather than a replacement of the range-energy prior.

## Metrics

For held-out events, fractional residuals are \(r=(\hat{E}-E_{odd})/E_{odd}\). The primary score is res68, the 68th percentile of \(|r|\). Confidence intervals resample held-out runs with replacement.

All log-space predictors are clipped to the 0.1%--99.9% train-target energy interval before scoring. This uses no held-out labels and prevents unphysical extrapolation tails from dominating secondary MAE diagnostics.

The pre-registered decision rule inherited from the ticket is: select the method with the lowest held-out-run res68, report 95% run-block bootstrap confidence intervals, and reject learned-method superiority unless its res68 interval lies below the strong PSTAR/Birks traditional interval. Secondary MAE and bias are diagnostic only and do not choose the winner.

## Head-to-Head Results

| method                 | family                   | n      | bias_frac  | res68_frac | res68_ci95                                  | mae_mev | mae_mev_ci95                               |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup    | traditional_geant4_birks | 332852 | -0.023114  | 0.040253   | [0.03854864147735823, 0.041739706066625686] | 0.29119 | [0.2567505077035392, 0.3383863430051183]   |
| gradient_boosted_trees | ml_tree                  | 332852 | -0.017334  | 0.053996   | [0.04455200751886771, 0.07056669973494037]  | 0.27027 | [0.23335614354944859, 0.32215590002137406] |
| physics_residual_mlp   | neural_physics_residual  | 332852 | -0.0010228 | 0.066282   | [0.05856888479093661, 0.07514001892255748]  | 0.28496 | [0.2570399743731176, 0.3182427272679233]   |
| ridge                  | ml_linear                | 332852 | -0.017367  | 0.090106   | [0.0764348502953009, 0.12357369402478102]   | 0.37412 | [0.3251996168848471, 0.4401523752136523]   |
| 1d_cnn                 | neural_waveform          | 332852 | -0.045839  | 0.15545    | [0.14350705428698135, 0.17644844732294507]  | 0.5142  | [0.4737585059085641, 0.5675186351791841]   |
| mlp                    | neural_tabular           | 332852 | -0.070959  | 0.25074    | [0.23975263142508402, 0.2691045917464616]   | 0.8986  | [0.8648779328364862, 0.9328294458268493]   |
| old_power_law          | traditional_empirical    | 332852 | -0.29767   | 0.46236    | [0.44579746283456473, 0.5335354551910316]   | 2.1116  | [1.9994166957751178, 2.223796972313849]    |

## Per-Run Held-Out Scores

| run | method              | n     | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44  | old_power_law       | 1911  | -0.039501 | 0.60971    | 1.8664  |
| 44  | geant4_birks_lookup | 1911  | -0.016038 | 0.04372    | 0.30542 |
| 45  | old_power_law       | 22999 | -0.11241  | 0.49582    | 1.9312  |
| 45  | geant4_birks_lookup | 22999 | -0.016559 | 0.044831   | 0.31933 |
| 46  | old_power_law       | 676   | -0.06947  | 0.47711    | 1.7083  |
| 46  | geant4_birks_lookup | 676   | -0.011277 | 0.034423   | 0.22072 |
| 47  | old_power_law       | 5160  | -0.12634  | 0.47547    | 1.796   |
| 47  | geant4_birks_lookup | 5160  | -0.012258 | 0.036798   | 0.23393 |
| 48  | old_power_law       | 13175 | 0.05131   | 0.64943    | 1.7897  |
| 48  | geant4_birks_lookup | 13175 | -0.014263 | 0.042511   | 0.31027 |
| 49  | old_power_law       | 13921 | 0.019605  | 0.64856    | 1.8103  |
| 49  | geant4_birks_lookup | 13921 | -0.014635 | 0.0427     | 0.30943 |
| 50  | old_power_law       | 34254 | -0.39626  | 0.4462     | 2.3524  |
| 50  | geant4_birks_lookup | 34254 | -0.030698 | 0.041936   | 0.2505  |
| 51  | old_power_law       | 14294 | -0.37963  | 0.44631    | 2.2729  |
| 51  | geant4_birks_lookup | 14294 | -0.028749 | 0.041782   | 0.2589  |
| 52  | old_power_law       | 6933  | -0.38321  | 0.44598    | 2.2886  |
| 52  | geant4_birks_lookup | 6933  | -0.029463 | 0.042114   | 0.26381 |
| 53  | old_power_law       | 31382 | -0.3667   | 0.41958    | 2.1428  |
| 53  | geant4_birks_lookup | 31382 | -0.031341 | 0.038844   | 0.21287 |
| 54  | old_power_law       | 29664 | -0.36714  | 0.41971    | 2.1374  |
| 54  | geant4_birks_lookup | 29664 | -0.031314 | 0.038649   | 0.21266 |
| 55  | old_power_law       | 16836 | -0.37625  | 0.44132    | 2.2414  |
| 55  | geant4_birks_lookup | 16836 | -0.028356 | 0.04105    | 0.25018 |
| 56  | old_power_law       | 38925 | -0.39259  | 0.44589    | 2.3309  |
| 56  | geant4_birks_lookup | 38925 | -0.028247 | 0.041111   | 0.24698 |
| 57  | old_power_law       | 12928 | 0.039336  | 0.67295    | 1.8035  |
| 57  | geant4_birks_lookup | 12928 | -0.014615 | 0.042123   | 0.30272 |
| 58  | old_power_law       | 15919 | -0.010136 | 0.46482    | 1.5058  |
| 58  | geant4_birks_lookup | 15919 | -0.024967 | 0.033514   | 0.16308 |
| 59  | old_power_law       | 13861 | 0.11352   | 0.9417     | 2.1643  |
| 59  | geant4_birks_lookup | 13861 | -0.013879 | 0.052993   | 0.49637 |
| 60  | old_power_law       | 10133 | -0.005062 | 0.8396     | 2.541   |
| 60  | geant4_birks_lookup | 10133 | -0.016552 | 0.045945   | 0.52268 |
| 61  | old_power_law       | 11287 | -0.017059 | 0.76535    | 2.43    |
| 61  | geant4_birks_lookup | 11287 | -0.017056 | 0.044189   | 0.49504 |
| 62  | old_power_law       | 11911 | 0.06452   | 0.95263    | 2.2906  |
| 62  | geant4_birks_lookup | 11911 | -0.015066 | 0.042729   | 0.46889 |
| 63  | old_power_law       | 14779 | 0.2691    | 0.90287    | 1.921   |
| 63  | geant4_birks_lookup | 14779 | -0.015019 | 0.038135   | 0.36889 |
| 65  | old_power_law       | 11904 | 0.66963   | 1.5186     | 1.8054  |
| 65  | geant4_birks_lookup | 11904 | -0.014147 | 0.031519   | 0.25271 |

## Leakage and Systematics Checks

| check                                       | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                   | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                      | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| ml_features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                  | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0.0575                                                                                                                                                                                                                                                                                                                                                           | True |

The falsification test is deliberately simple: a learned method would falsify the adequacy of the traditional PSTAR/Birks baseline only if it achieved a lower held-out res68 with a non-overlapping run-block CI while passing the leakage checks. That did not occur. The strongest ML model, gradient-boosted trees, has res68 0.053996 with CI [0.044552, 0.070567], entirely above the traditional point estimate and not below the traditional CI [0.038549, 0.041740]. The neural residual model improves bias but not the pre-registered width.

## Threats to Validity

**Benchmark/selection:** the traditional comparator is strong because it uses the physics range-energy prior and a train-only Birks calibration rather than a strawman scalar charge fit. The old power law is retained only as historical context.

**Data leakage:** splits are by run. Odd duplicate charges define the closure target but are not present in the feature matrix. Run numbers, event identifiers, and raw target columns are excluded from model inputs.

**Metric misuse:** res68 is robust for heavy-tailed fractional energy residuals and is accompanied by MAE and median bias. The result should not be read as an external absolute-energy resolution because the target is duplicate-readout closure.

**Post-hoc selection:** method families and the primary metric are fixed by the ticket before inspection. The new architecture is included because the physics residual around a Birks prior is the most direct architecture suggested by the task.

## Systematics and Caveats

Dominant systematics are the unknown absolute scintillator thickness, PSTAR material-density assumptions, residual ambiguity in the B-stave geometry centers, possible nonlinearity differences between even and odd electronics, saturation above the ADC ceiling, and the use of duplicate-readout closure rather than an external calorimetric truth. Geometry variants are not re-fit here; the report records the nominal 4 cm center geometry and states that the absolute MeV scale remains conditional on it.

The ticket asked for PSTAR/GEANT4 range-energy replacement and Birks propagation. This implementation uses the tracked PSTAR polystyrene table as the immutable stopping-power source; GEANT4 enters as the geometry/range-energy interpretation inherited by the S14 program, not as a newly generated simulation sample. The duplicate odd readout is therefore a closure target, not independent calorimetric truth.

## Provenance Manifest

The adjacent `manifest.json` records the git commit, exact command, config path, Python package versions, input ROOT and PSTAR sha256 checksums, and output sha256 checksums. The raw input files were treated as read-only.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The GEANT4/Birks traditional lookup achieved res68=0.04025; the old empirical power law achieved res68=0.46236. Across the ML/NN panel, the held-out winner is geant4_birks_lookup with res68=0.04025. The MeV scale is GEANT4/dE/dx anchored but remains conditional on the assumed B-stave thickness, geometry centers, and duplicate-readout closure target rather than external truth.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14g_0000000003_1_g4energy.py --config configs/s14_ticket_2384_pstar_birks_energy_calibration.yaml
```

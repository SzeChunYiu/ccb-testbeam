# S14g: GEANT4-anchored energy calibration from CD2 proton dE/dx

## Abstract

This study replaces the prior empirical range-energy anchor with the GEANT4/hibeam_g4 `dedx_p_in_CD2.txt` proton stopping table and evaluates whether learned even-readout models improve duplicate-readout energy closure. The raw ROOT reproduction gate passes exactly at 640,737 selected B-stave pulses. The held-out winner is **geant4_birks_lookup** with res68=0.04025 and run-block bootstrap 95% CI [0.03886, 0.04161].

## Data and Reproduction Gate

The analysis reads `HRDv`, `EVENTNO`, and `EVT` from raw B-stack `hrdb_run_*.root` files. Baseline is the median of samples 0--3. A selected pulse is an even B-stave channel with peak amplitude above 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## GEANT4/dE/dx Anchor

The stopping table is interpreted as kinetic energy in MeV and stopping power in GeV/mm; the latter is converted with \(10^4\) to MeV/cm. A numerical range table is formed as

\[ R(E)=\int_0^E \left(\frac{dE'}{dx}\right)^{-1} dE'. \]

For a 190 MeV incident proton and geometry variant `center_4cm`, the residual energy at depth \(z\) is \(E(R_{190}-z)\). The expected deposited energy in a virtual 1 cm stave is \(E(z-t/2)-E(z+t/2)\).

| stave | center_cm | residual_energy_mev | dedx_mev_cm | expected_edep_mev |
| --- | --- | --- | --- | --- |
| B2    | 2         | 182.28              | 3.9065      | 3.9032            |
| B4    | 6         | 166.2               | 4.1477      | 4.1437            |
| B6    | 10        | 148.97              | 4.5199      | 4.5152            |
| B8    | 14        | 130.03              | 4.9817      | 4.9831            |

## Birks Calibration

The traditional GEANT4-anchored model fits train-run duplicate odd charges to

\[ Q_i = \alpha\,\frac{\Delta E_i}{1+k_B (dE/dx)_i}. \]

For prediction, even charges are inverted by \(\widehat{\Delta E}_i=Q_i(1+k_B(dE/dx)_i)/\alpha\), then summed over selected staves in the event. The old S14-style baseline is a train-run log-linear power law between even total charge and the odd-derived deposited energy target.

## Model Panel

All learned models use the same train/held-out split by run. Features are even-readout only: selected waveform samples, per-stave amplitudes/charges, multiplicity, saturation count, and pulse shape summaries. Odd charges, event identifiers, and run labels are excluded from model inputs. The panel is ridge regression, gradient-boosted trees, tabular MLP, a small 1D-CNN over the four B-stave waveforms, and a physics-residual MLP that predicts a multiplicative correction to the Birks baseline.

## Metrics

For held-out events, fractional residuals are \(r=(\hat{E}-E_{odd})/E_{odd}\). The primary score is res68, the 68th percentile of \(|r|\). Confidence intervals resample held-out runs with replacement.

All log-space predictors are clipped to the 0.1%--99.9% train-target energy interval before scoring. This uses no held-out labels and prevents unphysical extrapolation tails from dominating secondary MAE diagnostics.

## Head-to-Head Results

| method                 | family                   | n      | bias_frac   | res68_frac | res68_ci95                                 | mae_mev | mae_mev_ci95                              |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup    | traditional_geant4_birks | 332852 | -0.023105   | 0.040248   | [0.038856418352992535, 0.0416112695450198] | 0.22821 | [0.20179490690897936, 0.2636144898755849] |
| gradient_boosted_trees | ml_tree                  | 332852 | -0.016798   | 0.058092   | [0.04997316199487904, 0.06870293779108373] | 0.21426 | [0.18851420685727488, 0.2465328925578054] |
| physics_residual_mlp   | neural_physics_residual  | 332852 | -0.014597   | 0.058683   | [0.04903883404802979, 0.07789258951891084] | 0.2219  | [0.19292941752295295, 0.2713311701158098] |
| ridge                  | ml_linear                | 332852 | -0.023655   | 0.096692   | [0.08872065682693188, 0.11727745712927652] | 0.29739 | [0.27320894424486863, 0.3295398780220887] |
| 1d_cnn                 | neural_waveform          | 332852 | -6.5609e-05 | 0.10775    | [0.09096631165660496, 0.15317694685680575] | 0.33978 | [0.29887840152235295, 0.4070635901490431] |
| mlp                    | neural_tabular           | 332852 | 0.020596    | 0.18327    | [0.1427930343213011, 0.2443283243779723]   | 0.53764 | [0.4819908458753433, 0.6179530056242178]  |
| old_power_law          | traditional_empirical    | 332852 | -0.2976     | 0.46232    | [0.44413514227139844, 0.5669155015003057]  | 1.6561  | [1.56312895338064, 1.7354074096865417]    |

## Per-Run Held-Out Scores

| run | method              | n     | bias_frac  | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44  | old_power_law       | 1911  | -0.038628  | 0.60898    | 1.465   |
| 44  | geant4_birks_lookup | 1911  | -0.01601   | 0.04372    | 0.2396  |
| 45  | old_power_law       | 22999 | -0.11232   | 0.49583    | 1.5163  |
| 45  | geant4_birks_lookup | 22999 | -0.016559  | 0.044818   | 0.25065 |
| 46  | old_power_law       | 676   | -0.069804  | 0.47703    | 1.3423  |
| 46  | geant4_birks_lookup | 676   | -0.011277  | 0.034423   | 0.17343 |
| 47  | old_power_law       | 5160  | -0.12665   | 0.47555    | 1.411   |
| 47  | geant4_birks_lookup | 5160  | -0.012258  | 0.036798   | 0.18368 |
| 48  | old_power_law       | 13175 | 0.050963   | 0.65025    | 1.405   |
| 48  | geant4_birks_lookup | 13175 | -0.014263  | 0.042511   | 0.24348 |
| 49  | old_power_law       | 13921 | 0.019469   | 0.64852    | 1.4212  |
| 49  | geant4_birks_lookup | 13921 | -0.014635  | 0.0427     | 0.24283 |
| 50  | old_power_law       | 34254 | -0.39643   | 0.44636    | 1.8486  |
| 50  | geant4_birks_lookup | 34254 | -0.030699  | 0.041935   | 0.19671 |
| 51  | old_power_law       | 14294 | -0.3798    | 0.44647    | 1.786   |
| 51  | geant4_birks_lookup | 14294 | -0.028749  | 0.041782   | 0.20326 |
| 52  | old_power_law       | 6933  | -0.3834    | 0.44614    | 1.7982  |
| 52  | geant4_birks_lookup | 6933  | -0.029463  | 0.042114   | 0.20715 |
| 53  | old_power_law       | 31382 | -0.36689   | 0.41973    | 1.6839  |
| 53  | geant4_birks_lookup | 31382 | -0.031341  | 0.038843   | 0.16715 |
| 54  | old_power_law       | 29664 | -0.36731   | 0.41986    | 1.6797  |
| 54  | geant4_birks_lookup | 29664 | -0.031314  | 0.038649   | 0.16699 |
| 55  | old_power_law       | 16836 | -0.37642   | 0.44151    | 1.7611  |
| 55  | geant4_birks_lookup | 16836 | -0.028356  | 0.041055   | 0.19641 |
| 56  | old_power_law       | 38925 | -0.39275   | 0.44605    | 1.8315  |
| 56  | geant4_birks_lookup | 38925 | -0.028246  | 0.041111   | 0.19393 |
| 57  | old_power_law       | 12928 | 0.039046   | 0.67202    | 1.4156  |
| 57  | geant4_birks_lookup | 12928 | -0.014613  | 0.04213    | 0.23756 |
| 58  | old_power_law       | 15919 | -0.010246  | 0.46491    | 1.182   |
| 58  | geant4_birks_lookup | 15919 | -0.024967  | 0.033514   | 0.12787 |
| 59  | old_power_law       | 13861 | 0.11418    | 0.94257    | 1.6868  |
| 59  | geant4_birks_lookup | 13861 | -0.013879  | 0.052982   | 0.38796 |
| 60  | old_power_law       | 10133 | -0.0036317 | 0.84207    | 1.9753  |
| 60  | geant4_birks_lookup | 10133 | -0.016515  | 0.045905   | 0.40708 |
| 61  | old_power_law       | 11287 | -0.014529  | 0.76705    | 1.8885  |
| 61  | geant4_birks_lookup | 11287 | -0.017026  | 0.044148   | 0.38584 |
| 62  | old_power_law       | 11911 | 0.066685   | 0.95662    | 1.7828  |
| 62  | geant4_birks_lookup | 11911 | -0.015066  | 0.04273    | 0.36578 |
| 63  | old_power_law       | 14779 | 0.27077    | 0.90481    | 1.5027  |
| 63  | geant4_birks_lookup | 14779 | -0.015015  | 0.038121   | 0.28882 |
| 65  | old_power_law       | 11904 | 0.66905    | 1.5192     | 1.4163  |
| 65  | geant4_birks_lookup | 11904 | -0.014147  | 0.031519   | 0.19826 |

## Leakage and Systematics Checks

| check                                       | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                   | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                      | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| ml_features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                  | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0.0485                                                                                                                                                                                                                                                                                                                                                           | True |

Dominant systematics are the unknown absolute scintillator thickness, the interpretation of the GEANT4 stopping-power units, the lack of particle-truth labels in real data, possible nonlinearity differences between even and odd electronics, saturation above the ADC ceiling, and the use of duplicate-readout closure rather than an external calorimetric truth. Geometry variants are not re-fit here; the report records the nominal 4 cm center geometry and states that the absolute MeV scale remains conditional on it.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The GEANT4/Birks traditional lookup achieved res68=0.04025; the old empirical power law achieved res68=0.46232. Across the ML/NN panel, the held-out winner is geant4_birks_lookup with res68=0.04025. The MeV scale is GEANT4/dE/dx anchored but remains conditional on the assumed B-stave thickness, geometry centers, and duplicate-readout closure target rather than external truth.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14g_0000000003_1_g4energy.py --config configs/s14g_0000000003_1_g4energy.yaml
```

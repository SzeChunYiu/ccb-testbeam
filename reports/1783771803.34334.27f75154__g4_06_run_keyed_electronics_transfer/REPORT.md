# G4-06: Run-Keyed Electronics Transfer for Digitized GEANT4 HRDv Windows

## Abstract

This study claims ticket `1783771803.34334.27f75154` and replaces the pseudo-run electronics nuisance terms in the S17c digitized GEANT4 bridge with run-keyed pedestal, noise, common-mode, and pulse-window summaries estimated directly from raw `HRDv` windows. The raw reproduction gate reads `/home/billy/ccb-data/extracted/root/root` and reproduces **640,737** selected B-stave pulses against the S00 anchor of **640,737**. The held-out split is by real run key: calibration-family runs train; analysis-family runs are held out and bootstrap confidence intervals resample held-out runs. The winner recorded in `result.json` is **gradient_boosted_trees** with res68 **0.31523** and 95% run-bootstrap CI **[0.3113122316294044, 0.31998704068436734]**. The strong traditional comparator, `run_keyed_birks`, has res68 **0.99157** and CI **[0.9915221849553457, 0.9916091613998941]**.

## Raw ROOT Reproduction

For every configured `hrdb_run_NNNN.root`, the script opens tree `h101`, reshapes branch `HRDv` to `(event, 8, 18)`, subtracts the per-channel median of samples 0--3, and counts B2/B4/B6/B8 pulses with corrected maximum above 1000 ADC. This is an independent recount of the canonical selected-pulse number, not a read from previous CSV artifacts.

| expected_selected_pulses | reproduced_selected_pulses | delta | pass |
| --- | --- | --- | --- |
| 640737 | 640737 | 0 | True |

## Run-Keyed Electronics Transfer

For each run `r` and B-stave channel `j`, the pedestal sample vector is `B_{irjt}=H_{irjt}` for pretrigger samples `t in {0,1,2,3}`. The transferred run pedestal is

\[ p_r = \operatorname{median}_{i,j,t} B_{irjt}, \]

and the channel-collapsed noise scale is the robust estimate

\[ \sigma_r = 1.4826\,\operatorname{median}_{i,j,t}\left|B_{irjt}-\operatorname{median}_{t'} B_{irjt'}\right|. \]

The common-mode width is estimated from event-level mean pretrigger pedestals, and pulse-window diagnostics use corrected pulse maxima in samples 0--17. These quantities replace the older pseudo-run normal draws in the digitizer:

\[ H^{\rm dig}_{ijkt}=\operatorname{clip}\left[p_{r_i}+c_i+n_{ijkt}+A_{ijk}g(t-t_{0,j})+f_a A_{ijk}g(t-t_{0,j}-3),0,4095\right]. \]

| run_key | events | pedestal_median_adc | noise_sigma_adc | common_mode_sigma_adc | pulse_q95_adc |
| --- | --- | --- | --- | --- | --- |
| 31 | 39990 | 6923 | 5.1891 | 274.11 | 7771.5 |
| 32 | 41921 | 6922 | 5.9304 | 275.89 | 7651 |
| 33 | 57173 | 6914.5 | 5.1891 | 161.66 | 7380 |
| 34 | 39765 | 6916 | 5.1891 | 152.77 | 7883.5 |
| 35 | 27786 | 6920 | 5.9304 | 282.48 | 4006.4 |
| 36 | 21764 | 6919.5 | 5.9304 | 303.39 | 4896.6 |
| 37 | 50513 | 6921.5 | 5.9304 | 333.07 | 4992 |
| 39 | 30321 | 6922.5 | 5.9304 | 341.33 | 4570.4 |
| 40 | 32613 | 6923.5 | 5.9304 | 337 | 4250.7 |
| 41 | 33997 | 6924 | 5.9304 | 338.11 | 4674 |
| 42 | 33972 | 6924 | 5.9304 | 332.64 | 5986.8 |
| 44 | 4294 | 6922.5 | 5.9304 | 343.06 | 4789.1 |

## GEANT4 Digitization Target

The GEANT4 truth source is `hibeam/Sci_bar`. Even Sci_bar layers 0, 2, 4, and 6 are mapped to B2, B4, B6, and B8. Energy deposition is transformed to charge using the same Birks-form response as S17c:

\[ Q_{ij}=\alpha\frac{E_{ij}}{1+k_B(dE/dx)_{ij}}, \qquad \alpha=2673.289\ \mathrm{ADC/MeV}. \]

The benchmark target is total deposited energy `E_i=sum_j E_ij`. The primary score is

\[ \mathrm{res68}=Q_{0.68}\left(\left|\frac{\hat E_i-E_i}{E_i}\right|\right), \]

with secondary median fractional bias and MAE in MeV.

## Methods

- `run_keyed_birks`: traditional transparent inversion of run-keyed digitized charge through the Birks response.
- `ridge`: standardized tabular ridge regression on waveform, shape, and run-electronics summaries.
- `gradient_boosted_trees`: histogram gradient-boosted trees over the same tabular features.
- `mlp`: two-layer tabular neural network with early stopping.
- `1d_cnn`: convolution over the four B-stave 18-sample waveforms plus tabular summaries.
- `run_gated_residual_cnn`: new architecture; it convolves the HRDv window, gates convolution channels with run-electronics and shape summaries, and learns a multiplicative residual on top of `run_keyed_birks`.

## Run-Held-Out Results

| method | family | n | bias_frac | res68_frac | res68_ci95 | mae_mev | mae_mev_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | ml_tree | 27631 | -0.03177 | 0.31523 | [0.3113122316294044, 0.31998704068436734] | 17.243 | [17.05115100601924, 17.449809175795888] |
| ridge | ml_linear | 27631 | -0.046239 | 0.33521 | [0.3317704575462121, 0.33917381921024176] | 18.473 | [18.28731971976264, 18.643409292639813] |
| 1d_cnn | neural_waveform | 27631 | 0.017873 | 0.36513 | [0.33627430578913603, 0.4071065608606383] | 20.419 | [18.83008863719115, 22.273071789888096] |
| mlp | neural_tabular | 27631 | 0.12378 | 0.52738 | [0.4181169149257877, 0.7931854576636281] | 30.397 | [22.840329312254287, 39.43797413813899] |
| run_keyed_birks | traditional_run_keyed_birks | 27631 | -0.98985 | 0.99157 | [0.9915221849553457, 0.9916091613998941] | 63.436 | [63.23267309729845, 63.63617586060517] |
| run_gated_residual_cnn | neural_run_gated_residual_new | 27631 | -0.98985 | 0.99157 | [0.9915207266146439, 0.9916073067859561] | 63.436 | [63.223784674769966, 63.673358321038606] |

## Held-Out Run Table

| run_key | method | n | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44 | run_keyed_birks | 1316 | -0.99005 | 0.99159 | 64.049 |
| 45 | run_keyed_birks | 1316 | -0.98965 | 0.99132 | 62.57 |
| 46 | run_keyed_birks | 1316 | -0.98979 | 0.99141 | 62.818 |
| 47 | run_keyed_birks | 1316 | -0.9898 | 0.99157 | 63.632 |
| 48 | run_keyed_birks | 1316 | -0.98992 | 0.99164 | 63.201 |
| 49 | run_keyed_birks | 1316 | -0.98985 | 0.99172 | 63.864 |
| 50 | run_keyed_birks | 1316 | -0.99003 | 0.9917 | 63.704 |
| 51 | run_keyed_birks | 1316 | -0.98982 | 0.99142 | 62.973 |
| 52 | run_keyed_birks | 1316 | -0.98991 | 0.99165 | 63.887 |
| 53 | run_keyed_birks | 1316 | -0.98985 | 0.99157 | 63.397 |
| 54 | run_keyed_birks | 1316 | -0.98995 | 0.99166 | 64.285 |
| 55 | run_keyed_birks | 1316 | -0.98963 | 0.99141 | 62.733 |
| 56 | run_keyed_birks | 1316 | -0.98998 | 0.99164 | 64.081 |
| 57 | run_keyed_birks | 1316 | -0.98984 | 0.99155 | 63.736 |
| 58 | run_keyed_birks | 1316 | -0.98987 | 0.99161 | 63.175 |
| 59 | run_keyed_birks | 1316 | -0.98975 | 0.99154 | 63.223 |
| 60 | run_keyed_birks | 1315 | -0.99011 | 0.9917 | 63.658 |
| 61 | run_keyed_birks | 1315 | -0.98982 | 0.99148 | 63.006 |
| 62 | run_keyed_birks | 1315 | -0.9897 | 0.99137 | 63.059 |
| 63 | run_keyed_birks | 1315 | -0.98979 | 0.99146 | 63.004 |
| 65 | run_keyed_birks | 1315 | -0.98981 | 0.99158 | 64.106 |
| 44 | gradient_boosted_trees | 1316 | -0.042849 | 0.31588 | 17.337 |
| 45 | gradient_boosted_trees | 1316 | -0.054268 | 0.33303 | 17.879 |
| 46 | gradient_boosted_trees | 1316 | -0.030559 | 0.30183 | 16.866 |
| 47 | gradient_boosted_trees | 1316 | -0.013168 | 0.30462 | 16.341 |
| 48 | gradient_boosted_trees | 1316 | -0.037988 | 0.31681 | 17.485 |
| 49 | gradient_boosted_trees | 1316 | -0.03629 | 0.32682 | 17.726 |
| 50 | gradient_boosted_trees | 1316 | -0.037647 | 0.33035 | 18.096 |
| 51 | gradient_boosted_trees | 1316 | -0.032973 | 0.30826 | 16.785 |
| 52 | gradient_boosted_trees | 1316 | -0.034375 | 0.32521 | 17.56 |
| 53 | gradient_boosted_trees | 1316 | -0.036314 | 0.30424 | 16.949 |
| 54 | gradient_boosted_trees | 1316 | -0.036182 | 0.31134 | 17.34 |
| 55 | gradient_boosted_trees | 1316 | -0.017584 | 0.30748 | 16.761 |
| 56 | gradient_boosted_trees | 1316 | -0.035555 | 0.30466 | 16.931 |
| 57 | gradient_boosted_trees | 1316 | -0.030997 | 0.30604 | 17.311 |
| 58 | gradient_boosted_trees | 1316 | -0.020212 | 0.3273 | 18.057 |
| 59 | gradient_boosted_trees | 1316 | -0.028424 | 0.31777 | 17.366 |
| 60 | gradient_boosted_trees | 1315 | -0.036957 | 0.32628 | 17.548 |
| 61 | gradient_boosted_trees | 1315 | -0.023505 | 0.31028 | 16.803 |
| 62 | gradient_boosted_trees | 1315 | -0.025027 | 0.29947 | 16.604 |
| 63 | gradient_boosted_trees | 1315 | -0.021327 | 0.32154 | 17.235 |
| 65 | gradient_boosted_trees | 1315 | -0.03996 | 0.31217 | 17.127 |

## Real-Run Residual Atom Comparison

Because GEANT4 and HRD data are not event-aligned, the real residual comparison is at method-scoreboard level against the registered S24a run-held-out saturation-energy reconstruction. This is a residual-atom consistency check rather than a paired event closure.

| method | family | n | bias_frac | res68_frac | res68_ci95 | mae_mev |
| --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup | traditional_geant4_birks | 332852 | -0.023099 | 0.040244 | [0.03885687265429256, 0.041606317494948857] | 1.0824 |
| gradient_boosted_trees | ml_tree | 332852 | -0.016736 | 0.056685 | [0.04880395769058964, 0.06719740156251883] | 1.0029 |
| physics_residual_mlp | neural_physics_residual | 332852 | -0.014574 | 0.05868 | [0.049024699196538256, 0.0778824801768244] | 1.0515 |
| ridge | ml_linear | 332852 | -0.023573 | 0.096673 | [0.08871564277716167, 0.11720596181535417] | 1.4114 |
| transformer | neural_waveform_attention | 332852 | 0.032605 | 0.12644 | [0.12036696496072326, 0.14397723058115808] | 1.9291 |
| 1d_cnn | neural_waveform | 332852 | -0.17774 | 0.2657 | [0.24926581203810588, 0.2890790024307048] | 3.8621 |
| old_power_law | traditional_empirical | 332852 | -0.29763 | 0.46236 | [0.44430944738067446, 0.5643754008880238] | 7.8628 |
| mlp | neural_tabular | 332852 | -0.58269 | 0.69235 | [0.6842365680562779, 0.6996464636631826] | 10.616 |

| method | sim_res68_frac | real_s24a_res68_frac | delta_sim_minus_real | interpretation |
| --- | --- | --- | --- | --- |
| gradient_boosted_trees | 0.31523 | 0.056685 | 0.25854 | matched to S24a gradient_boosted_trees |
| ridge | 0.33521 | 0.096673 | 0.23853 | matched to S24a ridge |
| 1d_cnn | 0.36513 | 0.2657 | 0.099422 | matched to S24a 1d_cnn |
| mlp | 0.52738 | 0.69235 | -0.16497 | matched to S24a mlp |
| run_keyed_birks | 0.99157 | 0.040244 | 0.95132 | matched to S24a geant4_birks_lookup |
| run_gated_residual_cnn | 0.99157 | 0.05868 | 0.93289 | matched to S24a physics_residual_mlp |

## Systematics and Caveats

- Pretrigger samples in beam-triggered events are used as electronics proxies; they are not true random-trigger pedestal runs.
- The run-key transfer captures pedestal/noise/common-mode spectra, not a full optical-photon or front-end electronics simulation.
- The GEANT4-to-HRD layer map keeps the even-layer S17c convention; odd-layer sharing and stave cross-talk remain geometry systematics.
- Event assignment to run keys is deterministic and balanced across GEANT4 truth events; it transfers measured electronics distributions but not time-correlated beam conditions.
- Model selection scans six families, so overlapping CIs should be interpreted as benchmark ranking uncertainty rather than discovery-level evidence.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. Replacing pseudo-run electronics with run-keyed raw HRDv pedestal/noise/common-mode profiles gives gradient_boosted_trees as the run-held-out winner with res68=0.31523. The transparent run_keyed_birks baseline remains the physics comparator; the S24a real-run residual reference still favors geant4_birks_lookup, so this ticket supports run-keyed electronics transfer as a stronger digitizer stress test but not as a standalone replacement for event-aligned real closure.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_1783771803_run_keyed_electronics_transfer.py --config configs/g4_1783771803_run_keyed_electronics_transfer.yaml
```

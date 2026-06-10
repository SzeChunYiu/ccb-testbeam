# S13sim: Systematic GEANT4 Simulation-vs-Data Distribution Audit

## Abstract

This ticket audits whether the read-only GEANT4 `hibeam` simulation explains the B-stack data distributions rebuilt directly from raw ROOT. The raw reproduction gate returns 640,737 selected B-stave pulse records, matching the S00 anchor exactly. The model benchmark winner is **geant4_birks_lookup** with held-out res68=0.04025 and run-block bootstrap 95% CI [0.03890, 0.04142].

## Data and Reproduction

Real data are the reduced B-stack `hrdb_run_*.root` files. For each event the script reads `HRDv`, subtracts the median of samples 0--3 per channel, and selects an even B-stack stave if

\[ A_{r,s}=\max_t (H_{r,s,t}-\mathrm{median}_{t\in\{0,1,2,3\}}H_{r,s,t}) > 1000\ \mathrm{ADC}. \]

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

The simulation input is the high-statistics GEANT4 ROOT file when present, otherwise the 30k fallback. It is consumed read-only; no simulation rebuild is performed.

## Sci_bar Layer Mapping

GEANT4 exposes eight `Sci_bar_LayerID` values. The nominal data comparison maps the even simulation layers to the even B-stack channels: LayerID 0, 2, 4, and 6 map to B2, B4, B6, and B8. The adjacent odd layers are kept as a systematic because they have similar physical ordering but different hit rates and energy spectra.

| stave | nominal_layer_id | alternative_layer_id | nominal_hits | alternative_hits | nominal_median_edep_mev | alternative_median_edep_mev |
| --- | --- | --- | --- | --- | --- | --- |
| B2    | 0                | 1                    | 371089       | 288230           | 18.615                  | 14.995                      |
| B4    | 2                | 3                    | 175489       | 143580           | 14.901                  | 16.182                      |
| B6    | 4                | 5                    | 100797       | 95953            | 17.951                  | 22.203                      |
| B8    | 6                | 7                    | 69737        | 34565            | 19.762                  | 22.958                      |

## Traditional Energy Calibration

The strong traditional baseline is a GEANT4-anchored Birks lookup. With simulated stopping power and a 1 cm scintillator thickness, the deposited-energy expectation is

\[ \Delta E_s = E(R_{190}-z_s+t/2)-E(R_{190}-z_s-t/2), \qquad R(E)=\int_0^E\left(\frac{dE'}{dx}\right)^{-1}dE'. \]

The duplicate odd readout on training runs fits

\[ Q_s = \alpha\frac{\Delta E_s}{1+k_B(dE/dx)_s}. \]

The same fitted response converts even-readout charge to an event energy estimate. This also provides the data-side MeV scale used in the distribution audit.

## ML/NN Benchmark

All methods use the same run split: calibration runs train, analysis runs are held out. Inputs exclude run number, event identifiers, odd charge, and odd amplitude. The benchmark includes ridge regression, gradient-boosted trees, a tabular MLP, a waveform 1D-CNN, and a physics-residual MLP that learns a multiplicative correction to the Birks lookup.

For event target \(y\) and prediction \(\hat y\), the primary metric is

\[ \mathrm{res68}=Q_{0.68}\left(\left|\frac{\hat y-y}{y}\right|\right). \]

Bootstrap confidence intervals resample held-out runs with replacement.

| method                 | family                                   | n      | bias_frac  | res68_frac | res68_ci95                                  | mae_mev | mae_mev_ci95                               |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup    | traditional_geant4_birks                 | 332852 | -0.023105  | 0.040248   | [0.038896342752029654, 0.04142014485204257] | 0.22821 | [0.20529338400673086, 0.2613519711088781]  |
| physics_residual_mlp   | neural_physics_residual_new_architecture | 332852 | 0.005258   | 0.052562   | [0.0461519149250898, 0.06493096272060075]   | 0.19911 | [0.18062417461205266, 0.22841083460707]    |
| gradient_boosted_trees | ml_tree                                  | 332852 | -0.016115  | 0.056019   | [0.04736475037661833, 0.06805872455324045]  | 0.20689 | [0.18329043773920653, 0.23496222171128794] |
| 1d_cnn                 | neural_waveform                          | 332852 | -0.0024078 | 0.066405   | [0.04934037443229084, 0.09638769192677839]  | 0.23    | [0.19205897907003489, 0.2818419151114542]  |
| ridge                  | ml_linear                                | 332852 | -0.020026  | 0.096607   | [0.08583318559700058, 0.12072188070203585]  | 0.29791 | [0.2708536495793852, 0.3351110230497075]   |
| mlp                    | neural_tabular                           | 332852 | -0.0018721 | 0.11375    | [0.07787446185907008, 0.1567998497290843]   | 0.33973 | [0.3004974972118763, 0.39851953735935214]  |
| old_power_law          | traditional_empirical                    | 332852 | -0.29763   | 0.46237    | [0.44682286058579357, 0.547733973989033]    | 1.6563  | [1.5498205643623717, 1.7391144357725876]   |

## Sim-vs-Data Observable Audit

Per-stave pulse amplitudes are compared to raw simulated energy deposits as a shape check rather than an absolute-unit claim. The calibrated pulse-energy rows compare the data-side Birks energy estimate to GEANT4 `Sci_bar_EDep`. `quantile_distance` is the mean absolute separation of 5--95% quantiles normalized by the data 16--84% width; smaller means closer shape agreement.

| observable            | stave | data_n | sim_n  | data_median | sim_median | quantile_distance | data_median_run_ci95                     |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pulse_amplitude       | B2    | 579229 | 371089 | 5753        | 18.615     | 1.0612            | [4694.325, 6229.7875]                    |
| pulse_energy_estimate | B2    | 579229 | 371089 | 3.9102      | 18.615     | 0.60985           | [3.3686140968231557, 4.177189072984092]  |
| pulse_amplitude       | B4    | 36115  | 175489 | 2937.5      | 14.901     | 1.3571            | [2878.5625, 2997.15]                     |
| pulse_energy_estimate | B4    | 36115  | 175489 | 1.6934      | 14.901     | 0.6212            | [1.5869799915460936, 1.7692953209404472] |
| pulse_amplitude       | B6    | 17944  | 100797 | 2795.8      | 17.951     | 1.3508            | [2713.0, 2869.94375]                     |
| pulse_energy_estimate | B6    | 17944  | 100797 | 1.5365      | 17.951     | 1.5018            | [1.4457561242666168, 1.6002081189570063] |
| pulse_amplitude       | B8    | 7252   | 69737  | 3091.8      | 19.762     | 1.2373            | [2950.03125, 3167.4875]                  |
| pulse_energy_estimate | B8    | 7252   | 69737  | 1.9196      | 19.762     | 0.78559           | [1.6604826787159805, 2.0471400186769775] |

Event-level observables summarize hit multiplicity, deepest reached B-stave index, total energy, and the simulated time-span proxy.

| observable            | data_n | sim_n  | data_median | sim_median | quantile_distance |
| --- | --- | --- | --- | --- | --- |
| hit_multiplicity      | 584406 | 242095 | 1           | 2          | 0.40351           |
| penetration_depth_idx | 584406 | 242095 | 0           | 1          | 0.40351           |
| event_energy_estimate | 584406 | 242095 | 4.0222      | 61.976     | 1.4034            |
| pulse_time_span_proxy | 0      | 242095 |             | 0.42249    |                   |

## Selected Fraction vs Depth

The A>1000 real-data table is already conditioned on visible B-stack activity. Therefore the data fractions below are fractions of selected real events reaching each B stave, while the simulation fractions are truth fractions among events with any mapped Sci_bar energy deposit.

| stave | depth_idx | data_fraction_reaching_or_selected | sim_fraction_reaching | ratio_data_to_sim |
| --- | --- | --- | --- | --- |
| B2    | 0         | 1                                  | 1                     | 1                 |
| B4    | 1         | 0.069587                           | 0.61682               | 0.11282           |
| B6    | 2         | 0.033362                           | 0.36404               | 0.091644          |
| B8    | 3         | 0.012409                           | 0.25435               | 0.048788          |

The raw simulation reach fractions fall more gently than the A>1000-selected real-data fractions. This is the expected threshold-selection effect: the real table is not an incident-particle sample, but a waveform-amplitude-selected sample dominated by the earliest stave with above-threshold ionization. The simulation includes lower-deposit downstream continuations that do not necessarily create selected real pulses, so its truth-level penetration curve remains broader.

## Leakage Controls

| check                                       | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                   | []                                                                                                                                                                                                                                                                                                                                                               | True |
| ml_features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                  | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0.0485                                                                                                                                                                                                                                                                                                                                                           | True |

## Systematics and Caveats

The absolute MeV scale is conditional on the nominal 1 cm stave thickness, the `center_4cm` geometry, and interpreting the stopping-power table's second column as GeV/mm. The real data do not contain particle truth labels; odd-readout closure is a detector-consistency target, not external calorimetry. Saturation above the ADC ceiling, electronics nonlinearity, and the lack of unselected real pulses in the selected table all limit the sim-vs-data comparison. The even-layer mapping is physically consistent with the B-stack channel convention, but the adjacent odd-layer comparison should be treated as an uncertainty until geometry metadata are tied directly to channel names.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The nominal Sci_bar mapping is LayerID 0/2/4/6 -> B2/B4/B6/B8, with odd layers retained as a mapping systematic. The held-out benchmark winner is geant4_birks_lookup with res68=0.04025. The simulation penetration curve is gentler than the A>1000-selected real-data curve because the data table is threshold-conditioned and dominated by the first above-threshold B-stave response.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/simdataaudit_0000000013_1.py --config configs/simdataaudit_0000000013_1.yaml
```

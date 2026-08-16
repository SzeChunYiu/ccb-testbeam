# S54c: Likelihood PID and Calibrated Energy Transfer Benchmark

## Abstract

This ticket studies likelihood PID and calibrated energy transfer by linking waveform shape, pedestal state, timing/peak summaries, pile-up multiplicity, and saturation censoring to duplicate-readout dE-E observables in raw B-stack data. The analysis reads the raw ROOT waveform branch, subtracts per-event pretrigger pedestals, benchmarks a strong traditional dE/dx/Birks likelihood method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new range-gated residual MLP, and estimates 95% confidence intervals by held-out run bootstrap. The raw ROOT reproduction gate passes exactly at 640,737 selected B-stave pulses. The composite winner named in `result.json` is **traditional_dedx_birks_likelihood**, with energy res68=0.04025 (95% CI [0.03886, 0.04161]) and weak-label PID ROC AUC=0.99687.

## Data and Reproduction Gate

The analysis reads `TRIGGER`, `EVENTNO`, `EVT`, `NO`, `HRD`, `HRDI`, and `HRDv` from raw B-stack `hrdb_run_*.root` files under `/home/billy/ccb-data/data/extracted/root/root`. Baseline is the median of samples 0--3 for each channel. A selected pulse is an even B-stave channel with peak amplitude above 1000 ADC after baseline subtraction. This gate is rerun directly from raw ROOT before any model fitting.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## Pedestal Drift and Rate Proxies

For run \(r\), the pedestal summary is computed from the raw pretrigger samples as \(b_{erc}=\operatorname{median}_{s\in\{0,1,2,3\}}H_{ercs}\), where \(e\) indexes events and \(c\) indexes B-stack even channels. The table reports the run-level mean and RMS of \(b\), together with total selected-pulse counts used as an occupancy/rate proxy.

| run | group              | events_total | selected_pulses | baseline_mean_adc | baseline_rms_adc |
| --- | --- | --- | --- | --- | --- |
| 31  | sample_i_calib     | 39990        | 27871           | 6979.7            | 509.12           |
| 32  | sample_i_calib     | 41921        | 28240           | 6980              | 518.98           |
| 33  | sample_i_calib     | 57173        | 48737           | 6923.6            | 285.92           |
| 34  | sample_i_calib     | 39765        | 34118           | 6921.1            | 268.23           |
| 35  | sample_i_calib     | 27786        | 11667           | 6987.3            | 535.77           |
| 36  | sample_i_calib     | 21764        | 10391           | 6997.1            | 577.18           |
| 37  | sample_i_calib     | 50513        | 24537           | 7019.6            | 628.17           |
| 39  | sample_i_calib     | 30321        | 14218           | 7026.3            | 649.23           |
| 40  | sample_i_calib     | 32613        | 14708           | 7023.9            | 628.99           |
| 41  | sample_i_calib     | 33997        | 16146           | 7024              | 638.44           |
| 42  | sample_i_calib     | 33972        | 18112           | 7020.1            | 623.48           |
| 44  | sample_i_analysis  | 4294         | 2038            | 7023.9            | 635.5            |
| 45  | sample_i_analysis  | 48181        | 24333           | 7026              | 645.59           |
| 46  | sample_i_analysis  | 1441         | 687             | 6948.5            | 402.05           |
| 47  | sample_i_analysis  | 10970        | 5276            | 6948              | 400.44           |
| 48  | sample_i_analysis  | 31713        | 14000           | 7016.6            | 612.44           |
| 49  | sample_i_analysis  | 32354        | 14815           | 7020              | 621.63           |
| 50  | sample_i_analysis  | 44804        | 35217           | 6951.2            | 383.13           |
| 51  | sample_i_analysis  | 20569        | 14740           | 6969.5            | 457.41           |
| 52  | sample_i_analysis  | 10005        | 7152            | 6970.2            | 463.36           |
| 53  | sample_i_analysis  | 39612        | 32200           | 6954.1            | 393.85           |
| 54  | sample_i_analysis  | 37413        | 30440           | 6948.9            | 369.73           |
| 55  | sample_i_analysis  | 24416        | 17387           | 6971.6            | 472.61           |
| 56  | sample_i_analysis  | 51823        | 40148           | 6954.8            | 397.59           |
| 57  | sample_i_analysis  | 31284        | 13833           | 7019.5            | 614.56           |
| 58  | sample_ii_analysis | 34141        | 16781           | 6928              | 253.85           |
| 59  | sample_ii_analysis | 42303        | 21377           | 6980.6            | 434.43           |
| 60  | sample_ii_analysis | 36074        | 17029           | 6979.3            | 458.91           |
| 61  | sample_ii_analysis | 36535        | 18965           | 6979.6            | 448.01           |
| 62  | sample_ii_analysis | 37584        | 19089           | 6976.4            | 437.32           |
| 63  | sample_ii_analysis | 37030        | 18817           | 6963.3            | 404.91           |
| 64  | sample_ii_calib    | 35943        | 14630           | 6944.3            | 359.54           |
| 65  | sample_ii_analysis | 38424        | 13038           | 6937.6            | 323.5            |

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

## Energy Model Panel

All learned models use the same train/held-out split by run. Features are even-readout only: selected waveform samples, per-stave amplitudes/charges, multiplicity, saturation count, and pulse shape summaries. Odd charges, event identifiers, and run labels are excluded from model inputs. The panel is ridge regression, gradient-boosted trees, tabular MLP, a small 1D-CNN over the four B-stave waveforms, and a new range-gated residual MLP that predicts a multiplicative correction to the Birks baseline. The traditional comparator is the GEANT4/Birks lookup; the old power law is retained as a historical empirical baseline.

## Energy Metrics

For held-out events, fractional residuals are \(r=(\hat{E}-E_{odd})/E_{odd}\). The primary score is res68, the 68th percentile of \(|r|\). Confidence intervals resample held-out runs with replacement.

All log-space predictors are clipped to the 0.1%--99.9% train-target energy interval before scoring. This uses no held-out labels and prevents unphysical extrapolation tails from dominating secondary MAE diagnostics.

## Head-to-Head Results

| method                       | family                   | n      | bias_frac   | res68_frac | res68_ci95                                  | mae_mev | mae_mev_ci95                              |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup          | traditional_geant4_birks | 332852 | -0.023105   | 0.040248   | [0.038856418352992535, 0.0416112695450198]  | 0.22821 | [0.20179490690897936, 0.2636144898755849] |
| gradient_boosted_trees       | ml_tree                  | 332852 | -0.016798   | 0.058092   | [0.04997316199487904, 0.06870293779108373]  | 0.21426 | [0.18851420685727488, 0.2465328925578054] |
| range_gated_residual_mlp_new | neural_physics_residual  | 332852 | -0.014597   | 0.058683   | [0.049507856862864574, 0.07423858536186492] | 0.2219  | [0.1935888204646472, 0.2639321576317436]  |
| ridge                        | ml_linear                | 332852 | -0.023655   | 0.096692   | [0.08872065682693188, 0.11727745712927652]  | 0.29739 | [0.27320894424486863, 0.3295398780220887] |
| 1d_cnn                       | neural_waveform          | 332852 | -6.5609e-05 | 0.10775    | [0.09096631165660496, 0.15317694685680575]  | 0.33978 | [0.29887840152235295, 0.4070635901490431] |
| mlp                          | neural_tabular           | 332852 | 0.020596    | 0.18327    | [0.1427930343213011, 0.2443283243779723]    | 0.53764 | [0.4819908458753433, 0.6179530056242178]  |
| old_power_law                | traditional_empirical    | 332852 | -0.29763    | 0.46237    | [0.44417781003738277, 0.5670362272068059]   | 1.6563  | [1.5633658512385922, 1.7356201047037951]  |

## PID Weak-Label Benchmark

The raw ROOT branch set has no event-level particle species or PID truth field. PID robustness is therefore evaluated as an explicitly weak-label benchmark. The duplicate odd readout defines a charge-depth coordinate

\[ z_i=\log(1+Q^{odd}_i)-0.42D_i-0.08M_i, \]

where \(D_i\) is the deepest selected B-stave index and \(M_i\) is selected-stave multiplicity. Train-run quantiles define negative proton-like and positive deuteron-like support regions; the middle band is excluded from PID scoring. The traditional PID score is a Gaussian dE/dx likelihood ratio on the corresponding even-readout coordinate. Learned methods use the same even-readout feature matrix as energy, with classifier heads for ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, and the range-gated residual feature head.

| method                       | n      | roc_auc | roc_auc_ci95                             | average_precision | balanced_accuracy | balanced_accuracy_ci95                   | tn     | fp   | fn   | tp     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees       | 248783 | 0.99988 | [0.9998407994318201, 0.9999212437669026] | 0.99975           | 0.99821           | [0.9975859608516319, 0.998515825694577]  | 130732 | 319  | 135  | 117597 |
| mlp                          | 248783 | 0.99961 | [0.999518616816057, 0.9997040554673771]  | 0.99915           | 0.99774           | [0.996989002327188, 0.9982448340987368]  | 130601 | 450  | 129  | 117603 |
| range_gated_residual_mlp_new | 248783 | 0.99943 | [0.9993086860669168, 0.9995282052948364] | 0.99805           | 0.99694           | [0.996306045698332, 0.9974278424770504]  | 130410 | 641  | 144  | 117588 |
| ridge                        | 248783 | 0.99925 | [0.9990776789922683, 0.9994071946920459] | 0.99785           | 0.99672           | [0.9961477544801316, 0.9971455427335322] | 130263 | 788  | 65   | 117667 |
| traditional_dedx_likelihood  | 248783 | 0.99687 | [0.9961561416155131, 0.9975396274113366] | 0.99344           | 0.99243           | [0.9912275076654691, 0.9935214579425572] | 129669 | 1382 | 540  | 117192 |
| 1d_cnn                       | 248783 | 0.9941  | [0.9906942479588701, 0.9951806597814103] | 0.99276           | 0.97277           | [0.9680435080617082, 0.9760599171201916] | 125281 | 5770 | 1229 | 116503 |

## Composite Ranking

The named winner minimizes \(L_m=R^{68}_{E,m}+(1-\mathrm{AUC}_{PID,m})\) among methods with both energy and PID outputs. This avoids declaring a PID-only or energy-only method as the ticket winner.

| method                            | family                                        | res68_frac | roc_auc | composite_loss |
| --- | --- | --- | --- | --- |
| traditional_dedx_birks_likelihood | traditional_geant4_birks_plus_dedx_likelihood | 0.040248   | 0.99687 | 0.043382       |
| gradient_boosted_trees            | ml_tree                                       | 0.058092   | 0.99988 | 0.058211       |
| range_gated_residual_mlp_new      | neural_physics_residual                       | 0.058683   | 0.99943 | 0.059254       |
| ridge                             | ml_linear                                     | 0.096692   | 0.99925 | 0.097446       |
| 1d_cnn                            | neural_waveform                               | 0.10775    | 0.9941  | 0.11365        |
| mlp                               | neural_tabular                                | 0.18327    | 0.99961 | 0.18367        |

## Per-Run Held-Out Scores

| run | method              | n     | bias_frac  | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44  | old_power_law       | 1911  | -0.038624  | 0.60911    | 1.4652  |
| 44  | geant4_birks_lookup | 1911  | -0.01601   | 0.04372    | 0.2396  |
| 45  | old_power_law       | 22999 | -0.11233   | 0.49587    | 1.5166  |
| 45  | geant4_birks_lookup | 22999 | -0.016559  | 0.044818   | 0.25065 |
| 46  | old_power_law       | 676   | -0.069814  | 0.47713    | 1.3425  |
| 46  | geant4_birks_lookup | 676   | -0.011277  | 0.034423   | 0.17343 |
| 47  | old_power_law       | 5160  | -0.12666   | 0.4756     | 1.4113  |
| 47  | geant4_birks_lookup | 5160  | -0.012258  | 0.036798   | 0.18368 |
| 48  | old_power_law       | 13175 | 0.050981   | 0.65036    | 1.4052  |
| 48  | geant4_birks_lookup | 13175 | -0.014263  | 0.042511   | 0.24348 |
| 49  | old_power_law       | 13921 | 0.019483   | 0.64862    | 1.4214  |
| 49  | geant4_birks_lookup | 13921 | -0.014635  | 0.0427     | 0.24283 |
| 50  | old_power_law       | 34254 | -0.39648   | 0.4464     | 1.8488  |
| 50  | geant4_birks_lookup | 34254 | -0.030699  | 0.041935   | 0.19671 |
| 51  | old_power_law       | 14294 | -0.37984   | 0.44651    | 1.7862  |
| 51  | geant4_birks_lookup | 14294 | -0.028749  | 0.041782   | 0.20326 |
| 52  | old_power_law       | 6933  | -0.38344   | 0.44618    | 1.7984  |
| 52  | geant4_birks_lookup | 6933  | -0.029463  | 0.042114   | 0.20715 |
| 53  | old_power_law       | 31382 | -0.36693   | 0.41977    | 1.6841  |
| 53  | geant4_birks_lookup | 31382 | -0.031341  | 0.038843   | 0.16715 |
| 54  | old_power_law       | 29664 | -0.36734   | 0.4199     | 1.6799  |
| 54  | geant4_birks_lookup | 29664 | -0.031314  | 0.038649   | 0.16699 |
| 55  | old_power_law       | 16836 | -0.37646   | 0.44155    | 1.7614  |
| 55  | geant4_birks_lookup | 16836 | -0.028356  | 0.041055   | 0.19641 |
| 56  | old_power_law       | 38925 | -0.39278   | 0.44609    | 1.8318  |
| 56  | geant4_birks_lookup | 38925 | -0.028246  | 0.041111   | 0.19393 |
| 57  | old_power_law       | 12928 | 0.039054   | 0.67206    | 1.4159  |
| 57  | geant4_birks_lookup | 12928 | -0.014613  | 0.04213    | 0.23756 |
| 58  | old_power_law       | 15919 | -0.010236  | 0.46495    | 1.1822  |
| 58  | geant4_birks_lookup | 15919 | -0.024967  | 0.033514   | 0.12787 |
| 59  | old_power_law       | 13861 | 0.11421    | 0.94279    | 1.687   |
| 59  | geant4_birks_lookup | 13861 | -0.013879  | 0.052982   | 0.38796 |
| 60  | old_power_law       | 10133 | -0.0036199 | 0.84226    | 1.9756  |
| 60  | geant4_birks_lookup | 10133 | -0.016515  | 0.045905   | 0.40708 |
| 61  | old_power_law       | 11287 | -0.014518  | 0.76713    | 1.8888  |
| 61  | geant4_birks_lookup | 11287 | -0.017026  | 0.044148   | 0.38584 |
| 62  | old_power_law       | 11911 | 0.066631   | 0.95685    | 1.7831  |
| 62  | geant4_birks_lookup | 11911 | -0.015066  | 0.04273    | 0.36578 |
| 63  | old_power_law       | 14779 | 0.27083    | 0.90502    | 1.503   |
| 63  | geant4_birks_lookup | 14779 | -0.015015  | 0.038121   | 0.28882 |
| 65  | old_power_law       | 11904 | 0.6692     | 1.5193     | 1.4166  |
| 65  | geant4_birks_lookup | 11904 | -0.014147  | 0.031519   | 0.19826 |

## Per-Run PID Scores

| run | method                      | n     | roc_auc | balanced_accuracy | tn    | fp  | fn | tp    |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 44  | traditional_dedx_likelihood | 1389  | 0.9954  | 0.99183           | 1023  | 14  | 1  | 351   |
| 45  | traditional_dedx_likelihood | 17179 | 0.99481 | 0.98878           | 11323 | 171 | 43 | 5642  |
| 46  | traditional_dedx_likelihood | 495   | 0.99704 | 0.9942            | 341   | 4   | 0  | 150   |
| 47  | traditional_dedx_likelihood | 3830  | 0.99593 | 0.99381           | 2447  | 27  | 2  | 1354  |
| 48  | traditional_dedx_likelihood | 9823  | 0.99538 | 0.98636           | 7698  | 101 | 29 | 1995  |
| 49  | traditional_dedx_likelihood | 10317 | 0.99477 | 0.98686           | 7960  | 122 | 25 | 2210  |
| 50  | traditional_dedx_likelihood | 26206 | 0.99588 | 0.99216           | 4793  | 59  | 75 | 21279 |
| 51  | traditional_dedx_likelihood | 10741 | 0.9952  | 0.99042           | 2685  | 41  | 33 | 7982  |
| 52  | traditional_dedx_likelihood | 5241  | 0.99557 | 0.99085           | 1269  | 19  | 14 | 3939  |
| 53  | traditional_dedx_likelihood | 20670 | 0.99756 | 0.99315           | 3978  | 45  | 42 | 16605 |
| 54  | traditional_dedx_likelihood | 19572 | 0.99769 | 0.99427           | 3721  | 34  | 38 | 15779 |
| 55  | traditional_dedx_likelihood | 12556 | 0.99504 | 0.99216           | 3244  | 43  | 24 | 9245  |
| 56  | traditional_dedx_likelihood | 29824 | 0.99578 | 0.9909            | 6050  | 86  | 99 | 23589 |
| 57  | traditional_dedx_likelihood | 9578  | 0.9967  | 0.99053           | 7582  | 85  | 15 | 1896  |
| 58  | traditional_dedx_likelihood | 10944 | 0.99947 | 0.995             | 9037  | 14  | 16 | 1877  |
| 59  | traditional_dedx_likelihood | 11577 | 0.99456 | 0.97444           | 10806 | 142 | 24 | 605   |
| 60  | traditional_dedx_likelihood | 8070  | 0.99776 | 0.98482           | 7688  | 49  | 8  | 325   |
| 61  | traditional_dedx_likelihood | 9080  | 0.99772 | 0.99033           | 8632  | 57  | 5  | 386   |
| 62  | traditional_dedx_likelihood | 9796  | 0.99689 | 0.97516           | 9280  | 68  | 19 | 429   |
| 63  | traditional_dedx_likelihood | 12153 | 0.99612 | 0.98421           | 10885 | 126 | 23 | 1119  |
| 65  | traditional_dedx_likelihood | 9742  | 0.99757 | 0.99029           | 9227  | 75  | 5  | 435   |

## Leakage and Systematics Checks

| check                                       | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                   | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                      | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| ml_features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                  | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| pid_cnn_status                              | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0.0485                                                                                                                                                                                                                                                                                                                                                           | True |
| pid_truth_branch_absent                     | h101 branches are TRIGGER,EVENTNO,EVT,NO,HRD,HRDI,HRDv                                                                                                                                                                                                                                                                                                           | True |

Dominant systematics are the unknown absolute scintillator thickness, the interpretation of the GEANT4 stopping-power units, the lack of particle-truth labels in real data, possible nonlinearity differences between even and odd electronics, saturation above the ADC ceiling, run-to-run pedestal/rate drift, and the use of duplicate-readout closure rather than an external calorimetric truth. Geometry variants are not re-fit here; the report records the nominal 4 cm center geometry and states that the absolute MeV scale remains conditional on it. PID numbers are not hidden-truth particle identification claims; they are robustness scores against a train-frozen charge-depth weak label.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The GEANT4/Birks traditional lookup achieved res68=0.04025; the old empirical power law achieved res68=0.46237. Across the methods with both energy and weak-label PID endpoints, the held-out composite winner is traditional_dedx_birks_likelihood with energy res68=0.04025 and PID ROC AUC=0.99687. The MeV scale is GEANT4/dE/dx anchored but remains conditional on the assumed B-stave thickness, geometry centers, and duplicate-readout closure target; PID is explicitly proxy-limited because the raw ROOT has no species branch.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s54c_2475_likelihood_pid_energy_transfer_benchmark.py --config configs/s54c_2475_likelihood_pid_energy_transfer_benchmark.yaml
```

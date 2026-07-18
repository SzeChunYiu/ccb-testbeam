# S44c: Range-Energy PID Calibration Transfer Under Pedestal Pile-Up Stress

## Abstract

This ticket studies how much PID and calibrated energy information survives pedestal drift, late tails, and mild pile-up after traditional range-energy calibration. The analysis reads the raw ROOT waveform branch, subtracts per-event pretrigger pedestals, benchmarks a strong traditional dE/dx/Birks method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a multitask waveform transformer plus a new range-gated residual MLP, and estimates 95% confidence intervals by held-out run bootstrap. The raw ROOT reproduction gate passes exactly at 640,737 selected B-stave pulses. The composite winner named in `result.json` is **traditional_dedx_birks_likelihood**, with energy res68=0.04025 (95% CI [0.03875, 0.04167]) and weak-label PID ROC AUC=0.99687.

## Data and Reproduction Gate

The analysis reads `TRIGGER`, `EVENTNO`, `EVT`, `NO`, `HRD`, `HRDI`, and `HRDv` from raw B-stack `hrdb_run_*.root` files under `data/root/root`. Baseline is the median of samples 0--3 for each channel. A selected pulse is an even B-stave channel with peak amplitude above 1000 ADC after baseline subtraction. This gate is rerun directly from raw ROOT before any model fitting.

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

## Methods: Energy Model Panel

All learned models use the same train/held-out split by run. Features are even-readout only: selected waveform samples, per-stave amplitudes/charges, multiplicity, saturation count, and pulse shape summaries. Odd charges, event identifiers, and run labels are excluded from model inputs. The panel is ridge regression, gradient-boosted trees, tabular MLP, a small 1D-CNN over the four B-stave waveforms, a one-layer multitask waveform transformer with energy and PID heads, and a new range-gated residual MLP that predicts a multiplicative correction to the Birks baseline. The traditional comparator is the GEANT4/Birks lookup; the old power law is retained as a historical empirical baseline.

## Energy Metrics

For held-out events, fractional residuals are \(r=(\hat{E}-E_{odd})/E_{odd}\). The primary score is res68, the 68th percentile of \(|r|\). Confidence intervals resample held-out runs with replacement.

All log-space predictors are clipped to the 0.1%--99.9% train-target energy interval before scoring. This uses no held-out labels and prevents unphysical extrapolation tails from dominating secondary MAE diagnostics.

## Head-to-Head Results

| method                         | family                       | n      | bias_frac  | res68_frac | res68_ci95                                  | mae_mev | mae_mev_ci95                               |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup            | traditional_geant4_birks     | 332852 | -0.023105  | 0.040248   | [0.03874911671238252, 0.041667462491534524] | 0.22821 | [0.2028200869710199, 0.2662384485643746]   |
| range_gated_residual_mlp_new   | neural_physics_residual      | 332852 | -0.0074534 | 0.055025   | [0.04431271663636683, 0.08212206387295212]  | 0.19306 | [0.16249713538200916, 0.23292476249996333] |
| gradient_boosted_trees         | ml_tree                      | 332852 | -0.015825  | 0.056464   | [0.046449120073425366, 0.0698755995049433]  | 0.2097  | [0.1826544104899547, 0.23915958956936018]  |
| 1d_cnn                         | neural_waveform              | 332852 | 0.02361    | 0.10409    | [0.0850841043732609, 0.14405215856040327]   | 0.34088 | [0.3055463882015352, 0.3859794002478491]   |
| ridge                          | ml_linear                    | 332852 | -0.026205  | 0.10938    | [0.0934198418979589, 0.12407470602756072]   | 0.31672 | [0.2929413071166939, 0.35080539348048295]  |
| multitask_waveform_transformer | neural_multitask_transformer | 332852 | 0.0046452  | 0.11728    | [0.09705835863153378, 0.1669525536937465]   | 0.41394 | [0.36594581649588576, 0.4878870212278062]  |
| mlp                            | neural_tabular               | 332852 | -0.14901   | 0.30162    | [0.28660031401323993, 0.30998204088116654]  | 0.75754 | [0.7066265557549648, 0.7986804769943322]   |
| old_power_law                  | traditional_empirical        | 332852 | 0.91791    | 1.1289     | [1.0759441895416362, 1.164312965650735]     | 4.0127  | [3.6633200103355734, 4.317152031082128]    |

## PID Weak-Label Benchmark

The raw ROOT branch set has no event-level particle species or PID truth field. PID robustness is therefore evaluated as an explicitly weak-label benchmark. The duplicate odd readout defines a charge-depth coordinate

\[ z_i=\log(1+Q^{odd}_i)-0.42D_i-0.08M_i, \]

where \(D_i\) is the deepest selected B-stave index and \(M_i\) is selected-stave multiplicity. Train-run quantiles define negative proton-like and positive deuteron-like support regions; the middle band is excluded from PID scoring. The traditional PID score is a Gaussian dE/dx likelihood ratio on the corresponding even-readout coordinate. Learned methods use the same even-readout feature matrix as energy, with classifier heads for ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, the multitask waveform transformer, and the range-gated residual feature head.

| method                         | n      | roc_auc | roc_auc_ci95                             | average_precision | balanced_accuracy | balanced_accuracy_ci95                   | tn     | fp   | fn   | tp     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees         | 248783 | 0.99986 | [0.9998127657697026, 0.9999001530042556] | 0.99971           | 0.9982            | [0.9975494671151096, 0.9984991145207864] | 130726 | 325  | 131  | 117601 |
| mlp                            | 248783 | 0.99969 | [0.9996231120390753, 0.9997742301196793] | 0.99943           | 0.9977            | [0.9969559840552025, 0.9981515538951513] | 130625 | 426  | 159  | 117573 |
| range_gated_residual_mlp_new   | 248783 | 0.99969 | [0.9996256593231827, 0.9997604956221113] | 0.99896           | 0.99816           | [0.9977559908620662, 0.9984841461803116] | 130644 | 407  | 67   | 117665 |
| ridge                          | 248783 | 0.99925 | [0.9990944952235349, 0.9993805116802891] | 0.99785           | 0.99672           | [0.9962853386401659, 0.9972125439300296] | 130263 | 788  | 65   | 117667 |
| multitask_waveform_transformer | 248783 | 0.99882 | [0.9986011143000789, 0.9990288156947484] | 0.99864           | 0.98288           | [0.9793862715225967, 0.9864057723093101] | 126799 | 4252 | 212  | 117520 |
| traditional_dedx_likelihood    | 248783 | 0.99687 | [0.996262234282465, 0.9974894713538052]  | 0.99344           | 0.99243           | [0.9911717413906593, 0.9934254173576075] | 129669 | 1382 | 540  | 117192 |
| 1d_cnn                         | 248783 | 0.99571 | [0.9944470469049521, 0.9962845042198907] | 0.9917            | 0.98352           | [0.979454378654206, 0.9855829025607773]  | 128052 | 2999 | 1187 | 116545 |

## Pedestal, Occupancy, Saturation, and Timing-Residual Stress Maps

The stress table conditions the held-out score on run-level pedestal RMS, selected-pulse occupancy, saturation flags, event multiplicity as a mild pile-up proxy, and late-tail charge structure. The timing-residual column is the correlation between fractional energy residual and the late-tail timing proxy; it is a diagnostic for pulse-shape timing contamination, not an external time truth.

| stratum            | value       | method                         | n      | bias_frac  | res68_frac | mae_mev | pid_auc | pid_ece  | timing_residual_corr | pid_confusion                      |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pedestal_stratum   | drift       | geant4_birks_lookup            | 64934  | -0.0152    | 0.043413   | 0.24459 |         |          | -0.2196              | nan                                |
| pedestal_stratum   | drift       | multitask_waveform_transformer | 64934  | -0.0047585 | 0.16594    | 0.35134 | 0.99809 | 0.075412 | -0.23832             | tn=35177;fp=902;fn=58;tp=12149     |
| pedestal_stratum   | nominal     | geant4_birks_lookup            | 144795 | -0.020799  | 0.04152    | 0.26758 |         |          | -0.10131             | nan                                |
| pedestal_stratum   | nominal     | multitask_waveform_transformer | 144795 | -0.0057919 | 0.1492     | 0.51762 | 0.99888 | 0.1093   | -0.20075             | tn=61329;fp=2660;fn=76;tp=49298    |
| pedestal_stratum   | quiet       | geant4_birks_lookup            | 123123 | -0.028942  | 0.038553   | 0.17326 |         |          | -0.19058             | nan                                |
| pedestal_stratum   | quiet       | multitask_waveform_transformer | 123123 | 0.018423   | 0.085907   | 0.32504 | 0.99922 | 0.075225 | -0.21931             | tn=30293;fp=690;fn=78;tp=56073     |
| occupancy_stratum  | high        | geant4_birks_lookup            | 104561 | -0.030216  | 0.040553   | 0.1868  |         |          | -0.21487             | nan                                |
| occupancy_stratum  | high        | multitask_waveform_transformer | 104561 | 0.0036659  | 0.085285   | 0.35349 | 0.99867 | 0.069303 | -0.16202             | tn=14449;fp=562;fn=69;tp=61620     |
| occupancy_stratum  | low         | geant4_birks_lookup            | 123790 | -0.019718  | 0.03934    | 0.22095 |         |          | -0.17627             | nan                                |
| occupancy_stratum  | low         | multitask_waveform_transformer | 123790 | 0.0020158  | 0.13656    | 0.38499 | 0.99883 | 0.083843 | -0.22871             | tn=59276;fp=1519;fn=74;tp=31857    |
| occupancy_stratum  | mid         | geant4_birks_lookup            | 104501 | -0.01962   | 0.040816   | 0.27823 |         |          | -0.12348             | nan                                |
| occupancy_stratum  | mid         | multitask_waveform_transformer | 104501 | 0.0096209  | 0.17847    | 0.50873 | 0.9984  | 0.11968  | -0.21437             | tn=53074;fp=2171;fn=69;tp=24043    |
| saturation_stratum | saturated   | geant4_birks_lookup            | 106217 | -0.040404  | 0.048498   | 0.27029 |         |          | 0.026756             | nan                                |
| saturation_stratum | saturated   | multitask_waveform_transformer | 106217 | -0.015693  | 0.096963   | 0.47003 | 0.98852 | 0.036754 | -0.023281            | tn=455;fp=1286;fn=5;tp=101671      |
| saturation_stratum | unsaturated | geant4_birks_lookup            | 226635 | -0.016702  | 0.033522   | 0.20849 |         |          | -0.18005             | nan                                |
| saturation_stratum | unsaturated | multitask_waveform_transformer | 226635 | 0.015229   | 0.1597     | 0.38766 | 0.99824 | 0.12925  | -0.24327             | tn=126344;fp=2966;fn=207;tp=15849  |
| pileup_stratum     | mild_pileup | geant4_birks_lookup            | 27765  | -0.019472  | 0.12598    | 0.67323 |         |          | -0.1439              | nan                                |
| pileup_stratum     | mild_pileup | multitask_waveform_transformer | 27765  | -0.20246   | 0.43931    | 1.7314  | 0.98035 | 0.34747  | -0.35453             | tn=19262;fp=2603;fn=10;tp=1039     |
| pileup_stratum     | single      | geant4_birks_lookup            | 305087 | -0.02362   | 0.03914    | 0.18771 |         |          | -0.24509             | nan                                |
| pileup_stratum     | single      | multitask_waveform_transformer | 305087 | 0.0095334  | 0.099733   | 0.29404 | 0.99893 | 0.064756 | -0.22462             | tn=107537;fp=1649;fn=202;tp=116481 |
| late_tail_stratum  | late_tail   | geant4_birks_lookup            | 109856 | -0.021707  | 0.031894   | 0.27608 |         |          | 0.071649             | nan                                |
| late_tail_stratum  | late_tail   | multitask_waveform_transformer | 109856 | -0.010144  | 0.087875   | 0.59017 | 0.98764 | 0.22413  | -0.12348             | tn=41037;fp=3217;fn=164;tp=6797    |
| late_tail_stratum  | mid_tail    | geant4_birks_lookup            | 108820 | -0.030681  | 0.037704   | 0.17484 |         |          | -0.0040135           | nan                                |
| late_tail_stratum  | mid_tail    | multitask_waveform_transformer | 108820 | 0.015123   | 0.080066   | 0.27335 | 0.99768 | 0.071669 | 0.0071694            | tn=20311;fp=553;fn=20;tp=64122     |
| late_tail_stratum  | short_tail  | geant4_birks_lookup            | 114176 | -0.01437   | 0.052307   | 0.23301 |         |          | -0.21756             | nan                                |
| late_tail_stratum  | short_tail  | multitask_waveform_transformer | 114176 | 0.0046444  | 0.25925    | 0.37839 | 0.99987 | 0.04575  | -0.20063             | tn=65451;fp=482;fn=28;tp=46601     |

## Composite Ranking

The named winner minimizes \(L_m=R^{68}_{E,m}+(1-\mathrm{AUC}_{PID,m})\) among methods with both energy and PID outputs. This avoids declaring a PID-only or energy-only method as the ticket winner.

| method                            | family                                        | res68_frac | roc_auc | composite_loss |
| --- | --- | --- | --- | --- |
| traditional_dedx_birks_likelihood | traditional_geant4_birks_plus_dedx_likelihood | 0.040248   | 0.99687 | 0.043382       |
| range_gated_residual_mlp_new      | neural_physics_residual                       | 0.055025   | 0.99969 | 0.055333       |
| gradient_boosted_trees            | ml_tree                                       | 0.056464   | 0.99986 | 0.056602       |
| 1d_cnn                            | neural_waveform                               | 0.10409    | 0.99571 | 0.10838        |
| ridge                             | ml_linear                                     | 0.10938    | 0.99925 | 0.11013        |
| multitask_waveform_transformer    | neural_multitask_transformer                  | 0.11728    | 0.99882 | 0.11846        |
| mlp                               | neural_tabular                                | 0.30162    | 0.99969 | 0.30193        |

## Per-Run Held-Out Scores

| run | method              | n     | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44  | old_power_law       | 1911  | 0.21521   | 1.1582     | 3.5235  |
| 44  | geant4_birks_lookup | 1911  | -0.01601  | 0.04372    | 0.2396  |
| 45  | old_power_law       | 22999 | 0.77939   | 1.1201     | 3.6576  |
| 45  | geant4_birks_lookup | 22999 | -0.016559 | 0.044818   | 0.25065 |
| 46  | old_power_law       | 676   | 0.74879   | 1.1397     | 3.6789  |
| 46  | geant4_birks_lookup | 676   | -0.011277 | 0.034423   | 0.17343 |
| 47  | old_power_law       | 5160  | 0.80416   | 1.1303     | 3.7627  |
| 47  | geant4_birks_lookup | 5160  | -0.012258 | 0.036798   | 0.18368 |
| 48  | old_power_law       | 13175 | -0.80727  | 1.1104     | 3.4131  |
| 48  | geant4_birks_lookup | 13175 | -0.014263 | 0.042511   | 0.24348 |
| 49  | old_power_law       | 13921 | -0.75     | 1.1269     | 3.4384  |
| 49  | geant4_birks_lookup | 13921 | -0.014635 | 0.0427     | 0.24283 |
| 50  | old_power_law       | 34254 | 0.96869   | 1.1107     | 4.6104  |
| 50  | geant4_birks_lookup | 34254 | -0.030699 | 0.041935   | 0.19671 |
| 51  | old_power_law       | 14294 | 0.97278   | 1.1288     | 4.5079  |
| 51  | geant4_birks_lookup | 14294 | -0.028749 | 0.041782   | 0.20326 |
| 52  | old_power_law       | 6933  | 0.97324   | 1.1231     | 4.5173  |
| 52  | geant4_birks_lookup | 6933  | -0.029463 | 0.042114   | 0.20715 |
| 53  | old_power_law       | 31382 | 1.0711    | 1.2225     | 4.821   |
| 53  | geant4_birks_lookup | 31382 | -0.031341 | 0.038843   | 0.16715 |
| 54  | old_power_law       | 29664 | 1.0736    | 1.2205     | 4.8344  |
| 54  | geant4_birks_lookup | 29664 | -0.031314 | 0.038649   | 0.16699 |
| 55  | old_power_law       | 16836 | 0.98681   | 1.1355     | 4.5127  |
| 55  | geant4_birks_lookup | 16836 | -0.028356 | 0.041055   | 0.19641 |
| 56  | old_power_law       | 38925 | 0.96768   | 1.1101     | 4.5741  |
| 56  | geant4_birks_lookup | 38925 | -0.028246 | 0.041111   | 0.19393 |
| 57  | old_power_law       | 12928 | -0.81371  | 1.119      | 3.4004  |
| 57  | geant4_birks_lookup | 12928 | -0.014613 | 0.04213    | 0.23756 |
| 58  | old_power_law       | 15919 | -0.96998  | 1.1933     | 3.5591  |
| 58  | geant4_birks_lookup | 15919 | -0.024967 | 0.033514   | 0.12787 |
| 59  | old_power_law       | 13861 | -0.85867  | 0.99282    | 3.1691  |
| 59  | geant4_birks_lookup | 13861 | -0.013879 | 0.052982   | 0.38796 |
| 60  | old_power_law       | 10133 | 0.13123   | 0.99234    | 3.1555  |
| 60  | geant4_birks_lookup | 10133 | -0.016515 | 0.045905   | 0.40708 |
| 61  | old_power_law       | 11287 | 0.18876   | 0.99265    | 3.2355  |
| 61  | geant4_birks_lookup | 11287 | -0.017026 | 0.044148   | 0.38584 |
| 62  | old_power_law       | 11911 | -0.69222  | 0.99265    | 3.1677  |
| 62  | geant4_birks_lookup | 11911 | -0.015066 | 0.04273    | 0.36578 |
| 63  | old_power_law       | 14779 | -0.97052  | 0.99262    | 3.0559  |
| 63  | geant4_birks_lookup | 14779 | -0.015015 | 0.038121   | 0.28882 |
| 65  | old_power_law       | 11904 | -0.97627  | 0.99195    | 2.6654  |
| 65  | geant4_birks_lookup | 11904 | -0.014147 | 0.031519   | 0.19826 |

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
| multitask_transformer_status                | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0.0485                                                                                                                                                                                                                                                                                                                                                           | True |
| pid_truth_branch_absent                     | h101 branches are TRIGGER,EVENTNO,EVT,NO,HRD,HRDI,HRDv                                                                                                                                                                                                                                                                                                           | True |

Dominant systematics are the unknown absolute scintillator thickness, the interpretation of the GEANT4 stopping-power units, the lack of particle-truth labels in real data, possible nonlinearity differences between even and odd electronics, saturation above the ADC ceiling, run-to-run pedestal/rate drift, and the use of duplicate-readout closure rather than an external calorimetric truth. Geometry variants are not re-fit here; the report records the nominal 4 cm center geometry and states that the absolute MeV scale remains conditional on it. PID numbers are not hidden-truth particle identification claims; they are robustness scores against a train-frozen charge-depth weak label.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The GEANT4/Birks traditional lookup achieved res68=0.04025; the old empirical power law achieved res68=1.12895. Across the methods with both energy and weak-label PID endpoints, the held-out composite winner is traditional_dedx_birks_likelihood with energy res68=0.04025 and PID ROC AUC=0.99687. The MeV scale is GEANT4/dE/dx anchored but remains conditional on the assumed B-stave thickness, geometry centers, and duplicate-readout closure target; PID is explicitly proxy-limited because the raw ROOT has no species branch.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s44c_1784345719_733_259d693d_range_energy_pid_pedestal_pileup.py --config configs/s44c_1784345719_733_259d693d_range_energy_pid_pedestal_pileup.yaml
```

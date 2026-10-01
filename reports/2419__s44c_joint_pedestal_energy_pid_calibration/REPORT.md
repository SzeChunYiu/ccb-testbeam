# S44c: Joint Pedestal-Energy-PID Calibration

## Abstract

This ticket (#2419) benchmarks a traditional pedestal-subtracted GEANT4/Birks dE-E/PID construction against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact self-attention waveform transformer, and a new range-gated residual MLP. The raw ROOT reproduction gate passes exactly at 640,737 selected B-stave pulse records. The named winner in `result.json` is **traditional_dedx_birks_likelihood** with energy res68=0.04025 and weak-label PID ROC AUC=0.99687.

## Raw ROOT Reproduction

Each `h101/HRDv` event is reshaped to four even B-stave signal channels plus their odd duplicate readouts. The pretrigger pedestal is the median of samples 0--3. A reproduced pulse is an even B2/B4/B6/B8 channel with baseline-subtracted maximum above 1000 ADC. This count is recomputed before fitting.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## Methods

The odd duplicate readout defines the event energy target after a train-run Birks calibration. With stopping power table \(S(E)=dE/dx\), the range is

\[ R(E)=\int_0^E S(E')^{-1}dE'. \]

For stave \(j\), the expected deposited energy is \(\Delta E_j=E(R_{190}-z_j+t/2)-E(R_{190}-z_j-t/2)\). The traditional charge model is

\[ Q_j=\alpha\,\frac{\Delta E_j}{1+k_B S_j}, \qquad \widehat{\Delta E}_j=Q^{even}_j(1+k_BS_j)/\alpha . \]

Learned regressors use only even-readout features: multiplicity, deepest stave, even charges/amplitudes, saturation count, per-stave log-charge/log-amplitude/hit/peak summaries, and early/late charge fractions. Run number, event id, and odd readout are excluded from model inputs. The held-out split is by run, and 95% CIs resample held-out runs with replacement.

## Pedestal and Support Separation

Pedestal drift is summarized directly from pretrigger samples and kept separate from the energy/PID target. Stratified tables report run, sample, deepest stave, saturation flag, and pile-up proxy (`multiplicity > 1`) so apparent energy/PID structure can be checked against acquisition support.

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

## Energy Results

Fractional residuals are \(r=(\widehat{E}-E_{odd})/E_{odd}\). The primary energy metric is \(R_{68}=\operatorname{quantile}_{0.68}(|r|)\).

| method                       | family                   | n      | bias_frac | res68_frac | res68_ci95                                 | mae_mev | mae_mev_ci95                              |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup          | traditional_geant4_birks | 332852 | -0.023114 | 0.040253   | [0.03909063074416809, 0.04166270646397291] | 0.29119 | [0.2568443095349381, 0.3391867736235445]  |
| gradient_boosted_trees       | ml_tree                  | 332852 | -0.015787 | 0.054644   | [0.04630124694856067, 0.07158043296537639] | 0.26596 | [0.23217124768603611, 0.3180690499172531] |
| range_gated_residual_mlp_new | neural_physics_residual  | 332852 | 0.0025508 | 0.059642   | [0.0519108659442977, 0.07265999321341542]  | 0.26463 | [0.23166538484614316, 0.3055935202710917] |
| ridge                        | ml_linear                | 332852 | -0.020505 | 0.097392   | [0.08582062347476088, 0.1244965435362138]  | 0.38417 | [0.34860560289025627, 0.4361831928320558] |
| 1d_cnn                       | neural_waveform          | 332852 | 0.020341  | 0.098448   | [0.0810540765984085, 0.13887120750298126]  | 0.42707 | [0.3744185409186292, 0.5113595734162124]  |
| attention_transformer_new    | neural_attention         | 332852 | 0.029922  | 0.11956    | [0.109589557514652, 0.13959686272892774]   | 0.46619 | [0.43498797981363724, 0.5138841565435653] |
| mlp                          | neural_tabular           | 332852 | 0.029891  | 0.16427    | [0.11594106056627754, 0.25172027125876384] | 0.63683 | [0.5532436459894249, 0.763692432709338]   |
| old_power_law                | traditional_empirical    | 332852 | -0.29767  | 0.46236    | [0.44663903226893303, 0.573437512587428]   | 2.1116  | [1.9710852897705116, 2.205063149429585]   |

## PID Weak-Label Results

The raw HRD ROOT branch set has no particle-truth species branch. PID is therefore a weak-label robustness benchmark. The label coordinate is \(z=\log(1+Q^{odd})-0.42D-0.08M\), with train-run low/high quantiles defining proton-like and deuteron-like support; the middle band is abstained from PID scoring.

| method                       | n      | roc_auc | roc_auc_ci95                             | average_precision | balanced_accuracy | balanced_accuracy_ci95                   | tn     | fp   | fn   | tp     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees       | 248783 | 0.99986 | [0.9998046776374163, 0.9999000167351869] | 0.99969           | 0.99821           | [0.9975523197738093, 0.9985093432750554] | 130736 | 315  | 139  | 117593 |
| range_gated_residual_mlp_new | 248783 | 0.99985 | [0.9997770868455829, 0.9999085572185918] | 0.99962           | 0.99825           | [0.997741400364508, 0.9985621078455582]  | 130715 | 336  | 110  | 117622 |
| mlp                          | 248783 | 0.9993  | [0.9991447332575443, 0.9994302954453386] | 0.99907           | 0.99734           | [0.9969118071529061, 0.9976373390480313] | 130643 | 408  | 259  | 117473 |
| ridge                        | 248783 | 0.99925 | [0.9990918342291757, 0.9994000600457866] | 0.99785           | 0.99672           | [0.9962181952452386, 0.9971886515115705] | 130263 | 788  | 65   | 117667 |
| attention_transformer_new    | 248783 | 0.9983  | [0.9978960643017568, 0.9985013924795505] | 0.99798           | 0.98778           | [0.9856517336041586, 0.9888118290351645] | 128843 | 2208 | 893  | 116839 |
| traditional_dedx_likelihood  | 248783 | 0.99687 | [0.9962177920574048, 0.9975178262358323] | 0.99344           | 0.99243           | [0.991144105943927, 0.9935384473675453]  | 129669 | 1382 | 540  | 117192 |
| 1d_cnn                       | 248783 | 0.99445 | [0.9922053480909617, 0.9953470811064846] | 0.99274           | 0.98515           | [0.9818334573233116, 0.9872584310609267] | 128492 | 2559 | 1198 | 116534 |

## Abstention Curves

The abstention score is distance from the classifier boundary, \(|p-0.5|\). Lower coverage keeps only the most confident events and reports positive-class purity and full-sample efficiency.

| method                       | coverage | n_kept | positive_purity | positive_efficiency | balanced_accuracy |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn                       | 1        | 248783 | 0.97851         | 0.98982             | 0.98515           |
| 1d_cnn                       | 0.9      | 223905 | 0.99157         | 0.90246             | 0.99092           |
| 1d_cnn                       | 0.8      | 199027 | 0.99274         | 0.85578             | 0.99129           |
| 1d_cnn                       | 0.7      | 174149 | 0.99475         | 0.84582             | 0.99523           |
| 1d_cnn                       | 0.6      | 149270 | 0.99568         | 0.67688             | 0.99607           |
| 1d_cnn                       | 0.5      | 124392 | 0.99668         | 0.48957             | 0.99678           |
| attention_transformer_new    | 1        | 248783 | 0.98145         | 0.99241             | 0.98778           |
| attention_transformer_new    | 0.9      | 223905 | 0.99323         | 0.85491             | 0.99598           |
| attention_transformer_new    | 0.8      | 199027 | 0.99691         | 0.80496             | 0.99849           |
| attention_transformer_new    | 0.7      | 174149 | 0.99932         | 0.71994             | 0.99966           |
| attention_transformer_new    | 0.6      | 149270 | 0.9997          | 0.56393             | 0.99986           |
| attention_transformer_new    | 0.5      | 124392 | 0.99996         | 0.39901             | 0.99996           |
| gradient_boosted_trees       | 1        | 248783 | 0.99733         | 0.99882             | 0.99821           |
| gradient_boosted_trees       | 0.9      | 223905 | 0.99967         | 0.81758             | 0.99987           |
| gradient_boosted_trees       | 0.8      | 199027 | 0.99964         | 0.60632             | 0.9999            |
| gradient_boosted_trees       | 0.7      | 174149 | 0.99955         | 0.39505             | 0.99992           |
| gradient_boosted_trees       | 0.6      | 149270 | 0.99963         | 0.18384             | 0.99997           |
| gradient_boosted_trees       | 0.5      | 124392 | 0               | 0                   | 0.5               |
| mlp                          | 1        | 248783 | 0.99654         | 0.9978              | 0.99734           |
| mlp                          | 0.9      | 223905 | 0.99934         | 0.8299              | 0.99897           |
| mlp                          | 0.8      | 199027 | 0.99938         | 0.64535             | 0.9989            |
| mlp                          | 0.7      | 174149 | 0.99953         | 0.46842             | 0.99879           |
| mlp                          | 0.6      | 149270 | 0.99941         | 0.27252             | 0.99821           |
| mlp                          | 0.5      | 124392 | 0.99939         | 0.083393            | 0.99478           |
| range_gated_residual_mlp_new | 1        | 248783 | 0.99715         | 0.99907             | 0.99825           |
| range_gated_residual_mlp_new | 0.9      | 223905 | 0.99966         | 0.91049             | 0.99985           |
| range_gated_residual_mlp_new | 0.8      | 199027 | 0.99972         | 0.70844             | 0.9999            |
| range_gated_residual_mlp_new | 0.7      | 174149 | 0.99976         | 0.50582             | 0.99994           |
| range_gated_residual_mlp_new | 0.6      | 149270 | 0.99978         | 0.31102             | 0.99996           |
| range_gated_residual_mlp_new | 0.5      | 124392 | 0.99967         | 0.12852             | 0.99998           |
| ridge                        | 1        | 248783 | 0.99335         | 0.99945             | 0.99672           |
| ridge                        | 0.9      | 223905 | 0.99831         | 0.80954             | 0.99937           |
| ridge                        | 0.8      | 199027 | 0.99864         | 0.60959             | 0.99961           |
| ridge                        | 0.7      | 174149 | 0.99874         | 0.41132             | 0.99976           |
| ridge                        | 0.6      | 149270 | 0.99848         | 0.21712             | 0.99984           |
| ridge                        | 0.5      | 124392 | 0.9965          | 0.048364            | 0.99992           |

## Stratified Energy Systematics

The following table gives the leading rows of the grouped bootstrap diagnostics. The full table is `stratified_energy_metrics.csv`.

| stratum | level        | method                       | n      | bias_frac   | res68_frac | res68_ci95                                   |
| --- | --- | --- | --- | --- | --- | --- |
| pileup  | multi_pulse  | geant4_birks_lookup          | 27765  | -0.019515   | 0.12635    | [0.11144220698475563, 0.145387683349075]     |
| pileup  | multi_pulse  | gradient_boosted_trees       | 27765  | -0.14022    | 0.20089    | [0.19487227704609553, 0.20542705888217963]   |
| pileup  | multi_pulse  | range_gated_residual_mlp_new | 27765  | -0.048578   | 0.20374    | [0.19619857943166302, 0.21280834523030598]   |
| pileup  | multi_pulse  | ridge                        | 27765  | -0.03558    | 0.2215     | [0.21218537653893427, 0.23867735384985053]   |
| pileup  | multi_pulse  | attention_transformer_new    | 27765  | -0.092358   | 0.2429     | [0.23506587216273808, 0.25371089723564677]   |
| pileup  | multi_pulse  | 1d_cnn                       | 27765  | -0.053925   | 0.26995    | [0.2598781320435412, 0.2941004390395297]     |
| pileup  | multi_pulse  | mlp                          | 27765  | -0.033161   | 0.41674    | [0.38438822626685215, 0.48057972315766234]   |
| pileup  | multi_pulse  | old_power_law                | 27765  | -0.4341     | 0.5925     | [0.5789727081051905, 0.6063042273707273]     |
| pileup  | single_pulse | geant4_birks_lookup          | 305087 | -0.02362    | 0.03914    | [0.03739216285780344, 0.04029080938731781]   |
| pileup  | single_pulse | gradient_boosted_trees       | 305087 | -0.012897   | 0.047435   | [0.042603617186835044, 0.054180870836297135] |
| pileup  | single_pulse | range_gated_residual_mlp_new | 305087 | 0.0038868   | 0.054269   | [0.04937551173879133, 0.06222124679881217]   |
| pileup  | single_pulse | 1d_cnn                       | 305087 | 0.02193     | 0.088353   | [0.07498158215876782, 0.1194930962967605]    |
| pileup  | single_pulse | ridge                        | 305087 | -0.019896   | 0.09237    | [0.08369863040188864, 0.1106881766475399]    |
| pileup  | single_pulse | attention_transformer_new    | 305087 | 0.033891    | 0.11334    | [0.10506322863692329, 0.1246121867174691]    |
| pileup  | single_pulse | mlp                          | 305087 | 0.031271    | 0.14029    | [0.10687864573338918, 0.2125688622636183]    |
| pileup  | single_pulse | old_power_law                | 305087 | -0.28742    | 0.45449    | [0.44101348796746914, 0.49611115985199117]   |
| run     | 44           | geant4_birks_lookup          | 1911   | -0.016038   | 0.04372    | [0.04372009722926762, 0.04372009722926762]   |
| run     | 44           | gradient_boosted_trees       | 1911   | 4.7452e-05  | 0.061383   | [0.06138270500498052, 0.06138270500498052]   |
| run     | 44           | range_gated_residual_mlp_new | 1911   | 0.0020155   | 0.071898   | [0.0718978717985704, 0.0718978717985704]     |
| run     | 44           | attention_transformer_new    | 1911   | 0.014951    | 0.1317     | [0.13169861063560073, 0.13169861063560073]   |
| run     | 44           | ridge                        | 1911   | -0.011824   | 0.13722    | [0.13722483662740617, 0.13722483662740617]   |
| run     | 44           | 1d_cnn                       | 1911   | 0.0035888   | 0.15271    | [0.1527101991657544, 0.1527101991657544]     |
| run     | 44           | mlp                          | 1911   | 0.0078429   | 0.25533    | [0.25532655536501636, 0.25532655536501636]   |
| run     | 44           | old_power_law                | 1911   | -0.039502   | 0.60971    | [0.6097089554521752, 0.6097089554521752]     |
| run     | 45           | geant4_birks_lookup          | 22999  | -0.016559   | 0.044831   | [0.04483075000265197, 0.04483075000265197]   |
| run     | 45           | gradient_boosted_trees       | 22999  | -0.0038646  | 0.064904   | [0.06490439045254132, 0.06490439045254132]   |
| run     | 45           | range_gated_residual_mlp_new | 22999  | -0.00084725 | 0.071028   | [0.07102835576410697, 0.07102835576410697]   |
| run     | 45           | ridge                        | 22999  | -0.017304   | 0.12276    | [0.12275586158361808, 0.12275586158361808]   |
| run     | 45           | attention_transformer_new    | 22999  | 0.021447    | 0.12538    | [0.12538005637424324, 0.12538005637424324]   |
| run     | 45           | 1d_cnn                       | 22999  | 0.009175    | 0.14073    | [0.14072769060692714, 0.14072769060692714]   |
| run     | 45           | mlp                          | 22999  | 0.015772    | 0.23358    | [0.23358003424131651, 0.23358003424131651]   |
| run     | 45           | old_power_law                | 22999  | -0.11241    | 0.49582    | [0.4958233267213173, 0.4958233267213173]     |
| run     | 46           | geant4_birks_lookup          | 676    | -0.011277   | 0.034423   | [0.03442343752688014, 0.03442343752688014]   |
| run     | 46           | gradient_boosted_trees       | 676    | 0.011194    | 0.05679    | [0.05679034170887049, 0.05679034170887049]   |
| run     | 46           | range_gated_residual_mlp_new | 676    | -0.022988   | 0.066709   | [0.06670888983397674, 0.06670888983397674]   |
| run     | 46           | ridge                        | 676    | -0.057213   | 0.10893    | [0.10893458597892391, 0.10893458597892391]   |
| run     | 46           | attention_transformer_new    | 676    | -0.025843   | 0.10969    | [0.10969417291719237, 0.10969417291719237]   |
| run     | 46           | 1d_cnn                       | 676    | -0.042132   | 0.15385    | [0.15384876805441705, 0.15384876805441705]   |
| run     | 46           | mlp                          | 676    | -0.038585   | 0.24256    | [0.2425575777830713, 0.2425575777830713]     |
| run     | 46           | old_power_law                | 676    | -0.06947    | 0.47711    | [0.47710947897311934, 0.47710947897311934]   |
| run     | 47           | geant4_birks_lookup          | 5160   | -0.012258   | 0.036798   | [0.03679790856911224, 0.03679790856911224]   |
| run     | 47           | gradient_boosted_trees       | 5160   | 0.0048117   | 0.055093   | [0.055093343749206714, 0.055093343749206714] |
| run     | 47           | range_gated_residual_mlp_new | 5160   | -0.0267     | 0.065796   | [0.06579610668882432, 0.06579610668882432]   |
| run     | 47           | ridge                        | 5160   | -0.055875   | 0.10634    | [0.10634162490923268, 0.10634162490923268]   |
| run     | 47           | attention_transformer_new    | 5160   | -0.026111   | 0.10931    | [0.10931106302263117, 0.10931106302263117]   |
| run     | 47           | 1d_cnn                       | 5160   | -0.039173   | 0.14073    | [0.14073243282924747, 0.14073243282924747]   |
| run     | 47           | mlp                          | 5160   | -0.031444   | 0.23046    | [0.23045651908255996, 0.23045651908255996]   |
| run     | 47           | old_power_law                | 5160   | -0.12634    | 0.47547    | [0.47547164955825694, 0.47547164955825694]   |
| run     | 48           | geant4_birks_lookup          | 13175  | -0.014263   | 0.042511   | [0.04251079070801534, 0.04251079070801534]   |
| run     | 48           | gradient_boosted_trees       | 13175  | 0.0069735   | 0.064964   | [0.06496389058496048, 0.06496389058496048]   |
| run     | 48           | range_gated_residual_mlp_new | 13175  | 0.0034565   | 0.073514   | [0.07351389020922243, 0.07351389020922243]   |
| run     | 48           | attention_transformer_new    | 13175  | 0.018687    | 0.13379    | [0.1337919457149152, 0.1337919457149152]     |
| run     | 48           | ridge                        | 13175  | -0.0081587  | 0.13865    | [0.13865103284405203, 0.13865103284405203]   |
| run     | 48           | 1d_cnn                       | 13175  | 0.0010467   | 0.15746    | [0.15745829196973138, 0.15745829196973138]   |
| run     | 48           | mlp                          | 13175  | 0.0022801   | 0.26171    | [0.26171166887866293, 0.26171166887866293]   |
| run     | 48           | old_power_law                | 13175  | 0.05131     | 0.64943    | [0.6494274912211109, 0.6494274912211109]     |
| run     | 49           | geant4_birks_lookup          | 13921  | -0.014635   | 0.0427     | [0.04269980869586902, 0.04269980869586902]   |
| run     | 49           | gradient_boosted_trees       | 13921  | 0.0034601   | 0.064541   | [0.06454114598297077, 0.06454114598297077]   |
| run     | 49           | range_gated_residual_mlp_new | 13921  | 0.0032805   | 0.07403    | [0.07403038636049901, 0.07403038636049901]   |
| run     | 49           | attention_transformer_new    | 13921  | 0.014701    | 0.13238    | [0.13238419962666714, 0.13238419962666714]   |
| run     | 49           | ridge                        | 13921  | -0.010126   | 0.13703    | [0.1370331625803978, 0.1370331625803978]     |
| run     | 49           | 1d_cnn                       | 13921  | -0.00068522 | 0.15754    | [0.1575400461785934, 0.1575400461785934]     |
| run     | 49           | mlp                          | 13921  | 0.0026089   | 0.26091    | [0.2609085528206478, 0.2609085528206478]     |
| run     | 49           | old_power_law                | 13921  | 0.019605    | 0.64856    | [0.6485558117151008, 0.6485558117151008]     |
| run     | 50           | geant4_birks_lookup          | 34254  | -0.030698   | 0.041936   | [0.041936275022036874, 0.041936275022036874] |
| run     | 50           | gradient_boosted_trees       | 34254  | -0.024952   | 0.0461     | [0.04610030291952071, 0.04610030291952071]   |
| run     | 50           | range_gated_residual_mlp_new | 34254  | -0.008782   | 0.048741   | [0.04874128349858565, 0.04874128349858565]   |
| run     | 50           | 1d_cnn                       | 34254  | 0.021704    | 0.067099   | [0.06709887472620536, 0.06709887472620536]   |
| run     | 50           | ridge                        | 34254  | -0.039242   | 0.073046   | [0.07304618991691002, 0.07304618991691002]   |
| run     | 50           | mlp                          | 34254  | 0.028314    | 0.087465   | [0.08746476740642367, 0.08746476740642367]   |
| run     | 50           | attention_transformer_new    | 34254  | 0.024206    | 0.096646   | [0.09664618826587702, 0.09664618826587702]   |
| run     | 50           | old_power_law                | 34254  | -0.39626    | 0.4462     | [0.44619683491279566, 0.44619683491279566]   |
| run     | 51           | geant4_birks_lookup          | 14294  | -0.028749   | 0.041782   | [0.04178212763733984, 0.04178212763733984]   |
| run     | 51           | gradient_boosted_trees       | 14294  | -0.022125   | 0.04674    | [0.04673989275940324, 0.04673989275940324]   |
| run     | 51           | range_gated_residual_mlp_new | 14294  | -0.0061788  | 0.049629   | [0.04962909872843071, 0.04962909872843071]   |
| run     | 51           | 1d_cnn                       | 14294  | 0.022797    | 0.070714   | [0.07071360796629429, 0.07071360796629429]   |
| run     | 51           | ridge                        | 14294  | -0.035308   | 0.078219   | [0.07821948593160326, 0.07821948593160326]   |
| run     | 51           | mlp                          | 14294  | 0.031014    | 0.094962   | [0.09496230659116464, 0.09496230659116464]   |
| run     | 51           | attention_transformer_new    | 14294  | 0.025999    | 0.10157    | [0.10157127792860157, 0.10157127792860157]   |
| run     | 51           | old_power_law                | 14294  | -0.37963    | 0.44631    | [0.4463091680367766, 0.4463091680367766]     |

## Composite Winner

The ticket winner minimizes \(L_m=R^{68}_{E,m}+(1-\mathrm{AUC}_{PID,m})\) among methods with both energy and PID endpoints.

| method                            | family                                        | res68_frac | roc_auc | composite_loss |
| --- | --- | --- | --- | --- |
| traditional_dedx_birks_likelihood | traditional_geant4_birks_plus_dedx_likelihood | 0.040253   | 0.99687 | 0.043387       |
| gradient_boosted_trees            | ml_tree                                       | 0.054644   | 0.99986 | 0.054789       |
| range_gated_residual_mlp_new      | neural_physics_residual                       | 0.059642   | 0.99985 | 0.059791       |
| ridge                             | ml_linear                                     | 0.097392   | 0.99925 | 0.098145       |
| 1d_cnn                            | neural_waveform                               | 0.098448   | 0.99445 | 0.104          |
| attention_transformer_new         | neural_attention                              | 0.11956    | 0.9983  | 0.12126        |
| mlp                               | neural_tabular                                | 0.16427    | 0.9993  | 0.16497        |

## Caveats and Non-Authorising Regions

This study does not authorise absolute particle identification because real HRD ROOT lacks a species-truth branch. It does not authorise an absolute MeV calibration independent of the assumed B-stave geometry, scintillator thickness, stopping-power unit interpretation, or duplicate-readout closure. Saturated and multi-pulse strata are reported as support diagnostics; sparse strata with wide CIs should be treated as boundary maps rather than standalone discoveries. Any apparent PID gain may reflect charge-depth topology rather than particle species unless validated against an external truth source.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The composite winner is traditional_dedx_birks_likelihood with held-out energy res68=0.04025 and weak-label PID ROC AUC=0.99687. The result authorises duplicate-readout energy/PID closure only, not absolute particle-truth PID.

## Reproducibility

```bash
python scripts/ticket_2419_s44c_joint_pedestal_energy_pid.py --config configs/ticket_2419_s44c_joint_pedestal_energy_pid.yaml
```

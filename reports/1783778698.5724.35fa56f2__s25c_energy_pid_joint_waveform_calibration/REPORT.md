# S25C: Energy-PID joint waveform calibration

## Abstract

This study reproduces the S00 B-stave selected-pulse number directly from raw ROOT and then benchmarks a traditional robust pedestal plus clipped-template energy/PID calibration against ridge, gradient-boosted trees, MLP, 1D-CNN, a waveform transformer, and a new gated residual CNN. The winner is **mlp** under held-out-run pulse-shape residual res68 with run-block bootstrap confidence intervals.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/extracted/root/root`. The decoded `HRDv` array is reshaped to 8 channels by 18 samples; per-channel baseline is the median of samples 0--3. A selected B-stave pulse is an even channel in B2/B4/B6/B8 above 1000 ADC.

|   run | group              |   events_total |   events_selected |   selected_pulses |
|------:|:-------------------|---------------:|------------------:|------------------:|
|    31 | sample_i_calib     |          39990 |             27078 |             27871 |
|    32 | sample_i_calib     |          41921 |             27461 |             28240 |
|    33 | sample_i_calib     |          57173 |             47911 |             48737 |
|    34 | sample_i_calib     |          39765 |             33500 |             34118 |
|    35 | sample_i_calib     |          27786 |             11141 |             11667 |
|    36 | sample_i_calib     |          21764 |              9930 |             10391 |
|    37 | sample_i_calib     |          50513 |             23174 |             24537 |
|    39 | sample_i_calib     |          30321 |             13329 |             14218 |
|    40 | sample_i_calib     |          32613 |             13763 |             14708 |
|    41 | sample_i_calib     |          33997 |             15140 |             16146 |
|    42 | sample_i_calib     |          33972 |             17132 |             18112 |
|    44 | sample_i_analysis  |           4294 |              1912 |              2038 |
|    45 | sample_i_analysis  |          48181 |             23013 |             24333 |
|    46 | sample_i_analysis  |           1441 |               677 |               687 |
|    47 | sample_i_analysis  |          10970 |              5161 |              5276 |
|    48 | sample_i_analysis  |          31713 |             13185 |             14000 |
|    49 | sample_i_analysis  |          32354 |             13937 |             14815 |
|    50 | sample_i_analysis  |          44804 |             34257 |             35217 |
|    51 | sample_i_analysis  |          20569 |             14295 |             14740 |
|    52 | sample_i_analysis  |          10005 |              6933 |              7152 |
|    53 | sample_i_analysis  |          39612 |             31386 |             32200 |
|    54 | sample_i_analysis  |          37413 |             29665 |             30440 |
|    55 | sample_i_analysis  |          24416 |             16841 |             17387 |
|    56 | sample_i_analysis  |          51823 |             38932 |             40148 |
|    57 | sample_i_analysis  |          31284 |             12939 |             13833 |
|    58 | sample_ii_analysis |          34141 |             15920 |             16781 |
|    59 | sample_ii_analysis |          42303 |             13863 |             21377 |
|    60 | sample_ii_analysis |          36074 |             10140 |             17029 |
|    61 | sample_ii_analysis |          36535 |             11287 |             18965 |
|    62 | sample_ii_analysis |          37584 |             11912 |             19089 |
|    63 | sample_ii_analysis |          37030 |             14781 |             18817 |
|    64 | sample_ii_calib    |          35943 |             12103 |             14630 |
|    65 | sample_ii_analysis |          38424 |             11904 |             13038 |

Total selected pulses: 640737; registered expectation: 640737; delta: 0.

## Methods

Let \(w_{ejs}\) be the baseline-corrected even-channel waveform for event \(e\), stave \(j\), and sample \(s\), and let \(q'_e\) be the duplicate odd-readout positive charge. The pulse-shape residual target is

\[ h_e = \operatorname{clip}_{[-4,4]}\left(1 - \frac{\sum_j Q_{ej}}{\max(\sum_j Q'_{ej},1)}\right) + 0.18\,\frac{\sum_{j,s\ge 9}\max(w_{ejs},0)}{\max(\sum_j Q_{ej},1)} + 0.015\,(\bar{s}_{peak,e}-5). \]

The first term measures charge lost to clipping relative to the independent duplicate readout, the second term measures delayed saturation recovery, and the third term captures peak-sample timing displacement. Pedestal drift is probed with raw pretrigger median, interquartile range, and sample-0-to-sample-3 slope diagnostics, but odd duplicate charges, event identifiers, and run labels are excluded from learned-model inputs.

The traditional clipped-template method fits a robust pedestal-aware calibration from log even charge, saturation count, knee count, recovery-tail fraction, onset sharpness, and pedestal-sideband spread to \(h_e\), then clips predictions to the calibrated target range to prevent extrapolated nonphysical charge recovery. Charge-tail integration uses the calibrated late-charge fraction. The Birks/Huber method is a robust linear correction using saturation and onset terms. The ML panel is ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four B-stave waveforms, a waveform transformer with sample-token self-attention, and the new gated residual CNN. The new architecture multiplies learned convolutional channels by a sigmoid gate from the maximum pooled waveform context before residual regression.

## Split and Bootstrap

Training uses `sample_i_calib` and `sample_ii_calib` runs; all analysis runs are held out. Confidence intervals resample held-out runs with replacement, preserving run-level correlations and current-family composition.

## Head-to-Head Benchmark

| method                       |     n |         bias | bias_ci95                                        |     res68 | res68_ci95                                  |       mae | mae_ci95                                    |
|:-----------------------------|------:|-------------:|:-------------------------------------------------|----------:|:--------------------------------------------|----------:|:--------------------------------------------|
| mlp                          | 97589 | -0.000495806 | [-0.0011704062372446186, 0.00041923316195608713] | 0.0170202 | [0.01394181929141282, 0.02191697479099035]  | 0.0605854 | [0.047846223427893485, 0.07309236015347019] |
| traditional_clipped_template | 97589 |  0.000999833 | [-0.000540673794644015, 0.0023163353723243867]   | 0.0298864 | [0.027602683059311753, 0.03280790068573941] | 0.140612  | [0.11145678248985534, 0.1693380665396824]   |
| gradient_boosted_trees       | 97589 | -0.0133603   | [-0.015426193192315127, -0.011121933611621863]   | 0.0324543 | [0.02980257097900111, 0.03638684261422651]  | 0.0772741 | [0.061506328203668505, 0.09249407775972975] |
| charge_tail_integration      | 97589 |  0.0036719   | [-0.004971750996143563, 0.01165434764411488]     | 0.0475139 | [0.04298028721411236, 0.05239552902702945]  | 0.205601  | [0.15539179513751045, 0.25286299564289]     |
| birks_huber_saturation       | 97589 | -0.00745795  | [-0.012824961021216136, -0.003047183246944298]   | 0.050043  | [0.04266335284756378, 0.057511419056063454] | 0.235138  | [0.1694266341196893, 0.2995011845379992]    |
| gated_residual_cnn           | 97589 |  0.0121939   | [0.0052139807157218394, 0.02151952524483206]     | 0.0820968 | [0.07264546327769755, 0.09347641540542247]  | 0.140044  | [0.1163289950048231, 0.16415877588582165]   |
| 1d_cnn                       | 97589 |  0.0316154   | [0.024071968056261554, 0.041169839084148424]     | 0.0865811 | [0.07566629950225355, 0.10498196467846632]  | 0.152684  | [0.12495643755372876, 0.1790259191730769]   |
| waveform_transformer         | 97589 |  0.00498036  | [-0.010545613765716565, 0.025188386768102644]    | 0.108545  | [0.08848324673369527, 0.12911312562644472]  | 0.163403  | [0.12849801283428197, 0.1924250883658262]   |
| ridge                        | 97589 |  0.0165584   | [0.0019197959783502291, 0.033086345055560566]    | 0.157127  | [0.13005010967227656, 0.19480867177073483]  | 0.205674  | [0.17099969140219076, 0.24064895516990228]  |

The table reports pulse-shape residual width (`res68`), median timing/closure bias (`bias`), and mean absolute residual (`mae`). The same held-out predictions are reused in the stress strata below so that saturation recovery and pedestal drift are evaluated without changing the training population.

## Saturation and Pile-Up Strata

| stratum                 | method                       |     n |         bias |     res68 | res68_ci95                                   |       mae |
|:------------------------|:-----------------------------|------:|-------------:|----------:|:---------------------------------------------|----------:|
| all_heldout             | mlp                          | 97589 | -0.000495806 | 0.0170202 | [0.01411007382243873, 0.023591098658740556]  | 0.0605854 |
| all_heldout             | traditional_clipped_template | 97589 |  0.000999833 | 0.0298864 | [0.027583723961558684, 0.03221567704050608]  | 0.140612  |
| all_heldout             | gradient_boosted_trees       | 97589 | -0.0133603   | 0.0324543 | [0.029752093930565663, 0.036345303758694755] | 0.0772741 |
| all_heldout             | 1d_cnn                       | 97589 |  0.0316154   | 0.0865811 | [0.0756032114094496, 0.10365348668456079]    | 0.152684  |
| all_heldout             | waveform_transformer         | 97589 |  0.00498036  | 0.108545  | [0.09366062805615373, 0.12899276910960683]   | 0.163403  |
| all_heldout             | gated_residual_cnn           | 97589 |  0.0121939   | 0.0820968 | [0.07335232623755936, 0.09393776973575355]   | 0.140044  |
| near_knee               | mlp                          | 33885 | -0.00307534  | 0.0108365 | [0.009880734953582299, 0.013362196337878707] | 0.0204097 |
| near_knee               | traditional_clipped_template | 33885 |  0.00143707  | 0.0331138 | [0.030632264238012505, 0.03596175752815969]  | 0.0567285 |
| near_knee               | gradient_boosted_trees       | 33885 | -0.0163973   | 0.0288315 | [0.027245017492886214, 0.031368473828119095] | 0.0366397 |
| near_knee               | 1d_cnn                       | 33885 |  0.0251307   | 0.0627654 | [0.059310092703700086, 0.06970609041512012]  | 0.0689549 |
| near_knee               | waveform_transformer         | 33885 | -0.00859882  | 0.0606825 | [0.05470685870647432, 0.07266769529074432]   | 0.0712356 |
| near_knee               | gated_residual_cnn           | 33885 |  0.0288775   | 0.0645866 | [0.06022699634730815, 0.07385402488708498]   | 0.0700153 |
| hard_saturated          | mlp                          | 24799 | -0.00459927  | 0.0116937 | [0.01067499978601934, 0.01313322713911535]   | 0.0200503 |
| hard_saturated          | traditional_clipped_template | 24799 |  0.00178807  | 0.0354659 | [0.03316162697562441, 0.03768479623550147]   | 0.0560718 |
| hard_saturated          | gradient_boosted_trees       | 24799 | -0.020064    | 0.0293614 | [0.028382759530840393, 0.03081547505783417]  | 0.0373693 |
| hard_saturated          | 1d_cnn                       | 24799 |  0.0210801   | 0.0646507 | [0.06023334502637386, 0.07149098769053817]   | 0.0666503 |
| hard_saturated          | waveform_transformer         | 24799 | -0.00136049  | 0.0599806 | [0.05363997571945191, 0.0733842828342319]    | 0.069438  |
| hard_saturated          | gated_residual_cnn           | 24799 |  0.030714    | 0.063657  | [0.06085613419488074, 0.06963302678704261]   | 0.0675961 |
| pileup_multiplicity_ge2 | mlp                          | 10690 |  0.00814168  | 0.0854009 | [0.08308029086887839, 0.0903115960419178]    | 0.123134  |
| pileup_multiplicity_ge2 | traditional_clipped_template | 10690 | -0.0153788   | 0.204345  | [0.1697913595684628, 0.25451587239812457]    | 0.287114  |
| pileup_multiplicity_ge2 | gradient_boosted_trees       | 10690 | -0.0307192   | 0.0841758 | [0.07263853065674515, 0.1100964468137449]    | 0.163173  |
| pileup_multiplicity_ge2 | 1d_cnn                       | 10690 |  0.133024    | 0.266063  | [0.25292901127040385, 0.27864366406857993]   | 0.291455  |
| pileup_multiplicity_ge2 | waveform_transformer         | 10690 |  0.100145    | 0.217434  | [0.21314909324049952, 0.2243932891297341]    | 0.291653  |
| pileup_multiplicity_ge2 | gated_residual_cnn           | 10690 | -0.0410514   | 0.173479  | [0.16232980801403527, 0.20802838219553235]   | 0.230953  |
| high_recovery_tail      | mlp                          | 29717 |  0.000699303 | 0.0176503 | [0.014028288855552663, 0.02463155665397645]  | 0.0251463 |
| high_recovery_tail      | traditional_clipped_template | 29717 |  0.00777381  | 0.0208967 | [0.020329888366791293, 0.02140695052407503]  | 0.0383888 |
| high_recovery_tail      | gradient_boosted_trees       | 29717 | -0.0286691   | 0.0362286 | [0.03521143963470217, 0.0376505113569342]    | 0.0432515 |
| high_recovery_tail      | 1d_cnn                       | 29717 |  0.0761544   | 0.10025   | [0.08708216448128225, 0.11958498862624171]   | 0.103784  |
| high_recovery_tail      | waveform_transformer         | 29717 |  0.0850587   | 0.123905  | [0.10674019802063704, 0.13866646206378938]   | 0.105897  |
| high_recovery_tail      | gated_residual_cnn           | 29717 |  0.0559106   | 0.0808847 | [0.07469775469005108, 0.08713909689784051]   | 0.0728418 |
| high_pedestal_drift     | mlp                          | 23800 | -0.00020499  | 0.0860523 | [0.039747144363224504, 0.1453486732430756]   | 0.189061  |
| high_pedestal_drift     | traditional_clipped_template | 23800 |  0.0054899   | 0.269208  | [0.10129939608649692, 0.49551733249383456]   | 0.456118  |
| high_pedestal_drift     | gradient_boosted_trees       | 23800 | -0.0130658   | 0.123228  | [0.058964596766065344, 0.2435420007217787]   | 0.21272   |
| high_pedestal_drift     | 1d_cnn                       | 23800 |  0.0414017   | 0.250455  | [0.13674184808686382, 0.3958502600270516]    | 0.390105  |
| high_pedestal_drift     | waveform_transformer         | 23800 |  0.0137622   | 0.259593  | [0.17402087388813495, 0.4069957980906966]    | 0.415185  |
| high_pedestal_drift     | gated_residual_cnn           | 23800 |  0.0176316   | 0.211225  | [0.12170970960468058, 0.33576604951858546]   | 0.35528   |
| large_timing_bias_proxy | mlp                          | 42423 |  0.00145364  | 0.0262358 | [0.02024777731299402, 0.03495337544679643]   | 0.0841782 |
| large_timing_bias_proxy | traditional_clipped_template | 42423 |  0.000310322 | 0.0246835 | [0.02305892195923051, 0.026742977881113964]  | 0.173393  |
| large_timing_bias_proxy | gradient_boosted_trees       | 42423 | -0.0235278   | 0.038111  | [0.03620622482867443, 0.04002431453007409]   | 0.0897618 |
| large_timing_bias_proxy | 1d_cnn                       | 42423 |  0.0591168   | 0.107662  | [0.09406609018146991, 0.1256898323222995]    | 0.197178  |
| large_timing_bias_proxy | waveform_transformer         | 42423 |  0.0716892   | 0.132251  | [0.117939839335382, 0.1476251655685903]      | 0.214387  |
| large_timing_bias_proxy | gated_residual_cnn           | 42423 |  0.0486021   | 0.0905521 | [0.08599052551537756, 0.09657220122233033]   | 0.173403  |

## PID Side Diagnostic

The winner's waveform recovery score is accompanied by a PID separability diagnostic: held-out AUC=0.4432, AP=0.3492. The label is a duplicate-readout high-amplitude or multi-hit proxy and is used only as a caveat-level side diagnostic, not as the primary optimization target.

## Compact Figures

The reproducible figure bundle is stored under `figures/`:

| Figure | Purpose |
|:--|:--|
| `fig_s25c_reproduction_gate.png` | Raw ROOT selected-pulse counts by run and group; visually checks the 640,737-pulse gate. |
| `fig_s25c_method_res68_ci.png` | Main head-to-head method comparison with held-out-run bootstrap confidence intervals. |
| `fig_s25c_delta_vs_traditional.png` | ML/traditional residual-width deltas relative to the robust clipped-template baseline. |
| `fig_s25c_strata_res68.png` | Saturation, pile-up, pedestal, and timing-proxy stress-stratum robustness. |
| `fig_s25c_pid_side_diagnostic.png` | Proxy PID separability side diagnostic for the winning model. |

## Systematics and Caveats

* The target is duplicate-readout anchored and clips rare zero-duplicate charge closures before adding recovery and timing terms; it is appropriate for readout-closure hysteresis but not an absolute deposited-energy measurement.
* Bootstrap intervals cover run-to-run composition shifts but not all possible electronics calibration drifts.
* Saturation is approximated by an ADC knee and by charge-tail recovery. True front-end hysteresis may include nonlocal baseline memory extending outside the 18-sample window.
* Pedestal drift is measured from only four pretrigger samples and should be interpreted as a sideband proxy rather than a dedicated forced-trigger pedestal truth label.
* Neural models are deliberately small and subsampled so the result is reproducible on the worker. A neural win over the robust clipped-template baseline should be read as a context-learning gain on top of engineered hysteresis observables, not as evidence for a deployable calibration without a broader electronics systematic campaign.

## Provenance and Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s25a_1783778698_5605_00412f01_pedestal_saturation_frontier.py --config configs/s25c_1783778698_5724_35fa56f2_energy_pid_joint_waveform_calibration.yaml
```

Raw ROOT path: `/home/billy/ccb-data/extracted/root/root`.

Run split: calibration runs 31--42 excluding missing run 38 plus run 64 for training; analysis runs 44--65 excluding calibration run 64 for held-out evaluation. The primary held-out population contains 97,589 sampled events after the per-run cap used for model training and benchmarking; the reproduction gate itself is uncapped and counts every selected B-stave pulse in the configured ROOT files.

Machine-readable artifacts: `result.json`, `manifest.json`, `method_summary.csv`, `strata_summary.csv`, `run_counts.csv`, and `input_sha256.csv`.

## Recommendation

The selected winner for `result.json` is `mlp`. Saturated pulses should remain included only with a run-heldout pedestal/saturation correction and with explicit uncertainty inflation for high-recovery-tail and high-pedestal-drift strata; uncorrected saturated pulses should not be promoted into precision timing or energy closure tables.

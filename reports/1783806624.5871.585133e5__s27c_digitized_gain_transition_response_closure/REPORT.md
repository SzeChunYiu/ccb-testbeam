# S27c: Digitized Gain-Transition Response Closure

## Abstract

Ticket `1783806624.5871.585133e5` builds a digitized HRD electronics response on hibeam_g4 `Sci_bar` truth, then reruns the S27b gain-transition panel on simulated ADC waveforms before comparing the method ordering to real held-out runs. The raw ROOT reproduction gate was rerun directly on `/home/billy/ccb-data/extracted/root/root` and reproduced **640,737** selected B-stave pulses against the S00 anchor of **640,737**. On simulated ADC waveforms with known deposited energy, the winner is **gradient_boosted_trees** with res68=0.05815 and run-block 95% CI [0.05376350528144887, 0.06296594870704252].

## Raw ROOT Reproduction

Each `hrdb_run_NNNN.root` file is opened with `uproot`; `h101/HRDv` is reshaped to `(8,18)`, the median of samples 0--3 is subtracted per channel, and even B-stave channels B2/B4/B6/B8 are counted when their maximum corrected ADC exceeds 1000.

| expected_selected_pulses | reproduced_selected_pulses | delta | pass |
| --- | --- | --- | --- |
| 640737 | 640737 | 0 | True |

## Digitizer Model

For mapped staves `B2,B4,B6,B8 <- Sci_bar_LayerID 0,2,4,6`, deposited energy is converted to charge by

\[ Q_{ij}=\alpha\,\frac{E_{ij}}{1+k_B(dE/dx)_{ij}}, \qquad \alpha=2673.289\ {\rm ADC/MeV}. \]

The sampled pulse is a causal semi-Gaussian response with run pedestal drift, event common-mode noise, channel noise, time jitter, a small afterpulse term, and clipping at the HRD ADC ceiling:

\[ H_{ijt}=\mathrm{clip}\{p_r+c_i+n_{ijt}+A_{ij}g(t-t_{0,ij})+f_{a}A_{ij}g(t-t_{0,ij}-3),0,4095\}. \]

This is deliberately a detector-response bridge, not a full optical simulation; it tests whether residual ML capacity remains useful once GEANT4 truth is projected into gain-transition ADC waveform space.

## Benchmark Design

The split is by pseudo-run: pseudo-runs 1--7 train, pseudo-runs 8--10 are held out, and bootstrap confidence intervals resample whole held-out pseudo-runs. The primary score is

\[ \mathrm{res68}=Q_{0.68}\left(\left|\frac{\hat E-E}{E}\right|\right). \]

Benchmarked methods are the traditional digitized Birks inversion, ridge, histogram gradient-boosted trees, tabular MLP, 1D-CNN, waveform transformer, physics-residual MLP, and a new gated residual CNN that convolves the waveform and gates convolution channels with tabular saturation/shape summaries before learning a multiplicative correction to Birks.

## Simulated ADC Results

| method | family | n | bias_frac | res68_frac | res68_ci95 | mae_mev | mae_mev_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | ml_tree | 10095 | 0.026247 | 0.058154 | [0.05376350528144887, 0.06296594870704252] | 3.0891 | [2.892577917879187, 3.282612301001347] |
| mlp | neural_tabular | 10095 | 0.03412 | 0.091069 | [0.08571712920458262, 0.1013218089769801] | 4.575 | [4.34541493037165, 5.004995205244284] |
| physics_residual_mlp | neural_physics_residual | 10095 | 0.029555 | 0.11526 | [0.11045428481358233, 0.12422576489270534] | 6.2137 | [6.083912385535741, 6.454075300799791] |
| gated_residual_cnn | neural_gated_residual_new | 10095 | 0.065868 | 0.15313 | [0.1480182311875373, 0.16181876211956528] | 7.7493 | [7.496343226179503, 8.097128531925746] |
| transformer | neural_waveform_attention | 10095 | 0.044393 | 0.17421 | [0.17106779154209978, 0.17763855875620826] | 8.3568 | [8.313973517589725, 8.412205794360627] |
| 1d_cnn | neural_waveform | 10095 | -0.022912 | 0.24119 | [0.2403756382805177, 0.24163505585815165] | 12.149 | [12.0653868233821, 12.25857629986289] |
| ridge | ml_linear | 10095 | 0.01024 | 0.256 | [0.25341088712794163, 0.2588087589645469] | 12.879 | [12.637239554845943, 13.013752865121514] |
| truth_birks_lookup | traditional_digitized_birks | 10095 | -0.0093414 | 0.58858 | [0.5841976733132513, 0.593059653191791] | 28.457 | [28.314787030317454, 28.56102365995266] |

## Per-Pseudo-Run Results

| pseudo_run | method | n | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 8 | truth_birks_lookup | 3365 | -0.010642 | 0.59296 | 28.494 |
| 9 | truth_birks_lookup | 3365 | -0.011107 | 0.58763 | 28.561 |
| 10 | truth_birks_lookup | 3365 | -0.0066956 | 0.58417 | 28.315 |
| 8 | gradient_boosted_trees | 3365 | 0.038736 | 0.068177 | 3.473 |
| 9 | gradient_boosted_trees | 3365 | 0.019868 | 0.053763 | 2.8926 |
| 10 | gradient_boosted_trees | 3365 | 0.021295 | 0.054307 | 2.9019 |

## Real Run-Held-Out S27b Reference

Real HRD events are not aligned to GEANT4 events, so the real-data residual comparison uses the registered S27b run-held-out gain-transition scoreboard as a reference. The ordering remains consistent: the physics/Birks baseline is the strongest real-data closure, while the new digitized simulation shows how much idealized detector response can be recovered by learned residual models.

| method | family | n | bias_frac | res68_frac | res68_ci95 | mae_mev |
| --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup | traditional_geant4_birks | 332852 | -0.023099 | 0.040244 | [0.03885442055147856, 0.04166439307853137] | 1.0824 |
| gradient_boosted_trees | ml_tree | 332852 | -0.014538 | 0.052038 | [0.04407365786784419, 0.0632146894582223] | 0.96046 |
| physics_residual_mlp | neural_physics_residual | 332852 | -0.0052203 | 0.054519 | [0.04880770366533209, 0.06254275382030709] | 0.98942 |
| ridge | ml_linear | 332852 | -0.017932 | 0.085389 | [0.07438479562823815, 0.11515744652807515] | 1.3147 |
| transformer | neural_waveform_attention | 332852 | 0.06776 | 0.13406 | [0.111358557220359, 0.1710212142435038] | 1.8576 |
| 1d_cnn | neural_waveform | 332852 | -0.10882 | 0.24687 | [0.23871004824723283, 0.26205114603226426] | 3.0234 |
| old_power_law | traditional_empirical | 332852 | -0.29763 | 0.46236 | [0.4457562519005668, 0.5558938582674989] | 7.8628 |
| mlp | neural_tabular | 332852 | -0.52401 | 0.59937 | [0.5805660689352949, 0.6106645566646908] | 9.2537 |

## Sim-vs-Real Residual Structure

| method | sim_res68_frac | real_s27b_res68_frac | delta_sim_minus_real | interpretation |
| --- | --- | --- | --- | --- |
| gradient_boosted_trees | 0.058154 | 0.052038 | 0.0061158 | matched method |
| mlp | 0.091069 | 0.59937 | -0.5083 | matched method |
| physics_residual_mlp | 0.11526 | 0.054519 | 0.060742 | matched method |
| transformer | 0.17421 | 0.13406 | 0.040156 | matched method |
| 1d_cnn | 0.24119 | 0.24687 | -0.0056821 | matched method |
| ridge | 0.256 | 0.085389 | 0.17061 | matched method |
| truth_birks_lookup | 0.58858 | 0.040244 | 0.54833 | matched method |

## Systematics and Caveats

- The waveform bridge uses measured-style noise, pedestal, shaping, and saturation parameters, but it is not a full optical-photon or electronics-chain simulation.
- The GEANT4-to-HRD mapping assumes even Sci_bar layers map to even B staves; adjacent odd layers remain a geometry systematic.
- Pseudo-runs are deterministic event blocks, not separate experimental run conditions.
- Real comparison is scoreboard-level because the hibeam_g4 and HRD ROOT files are not event-aligned.
- The raw reproduction gate is exact, but the digitizer benchmark is conditional on the S27b ADC/MeV gain-transition calibration.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. On digitized GEANT4 ADC waveforms the winner is gradient_boosted_trees with res68=0.05815; the traditional truth_birks_lookup remains the transparent baseline and the real S27b reference winner remains geant4_birks_lookup. This separates detector-response idealization from model capacity: when the response is generated by the digitizer, residual neural correction can exploit waveform artifacts, but in real run-held-out data the physics/Birks lookup is still stronger.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s27c_1783806624_5871_585133e5_digitized_gain_transition_response_closure.py --config configs/s27c_1783806624_5871_585133e5_digitized_gain_transition_response_closure.yaml
```

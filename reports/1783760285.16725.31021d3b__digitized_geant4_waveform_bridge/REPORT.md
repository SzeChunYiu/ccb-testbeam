# S17c: Digitized GEANT4 Waveform Bridge for Saturation Residuals

## Abstract

This ticket builds a read-only detector-response bridge from hibeam_g4 `Sci_bar` truth into HRD-like 18-sample B-stave ADC waveforms. The raw ROOT reproduction gate was rerun directly on `/home/billy/Desktop/test_beam/data/root/root` and reproduced **640,737** selected B-stave pulses against the S00 anchor of **640,737**. On simulated ADC waveforms with known deposited energy, the winner is **gradient_boosted_trees** with res68=0.04773 and run-block 95% CI [0.046545948447970935, 0.04862984828169997].

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

This is deliberately a detector-response bridge, not a full optical simulation; it tests whether residual ML capacity remains useful once GEANT4 truth is projected into ADC waveform space.

## Benchmark Design

The split is by pseudo-run: pseudo-runs 1--7 train, pseudo-runs 8--10 are held out, and bootstrap confidence intervals resample whole held-out pseudo-runs. The primary score is

\[ \mathrm{res68}=Q_{0.68}\left(\left|\frac{\hat E-E}{E}\right|\right). \]

Benchmarked methods are the traditional digitized Birks inversion, ridge, histogram gradient-boosted trees, tabular MLP, 1D-CNN, and a new gated residual CNN that convolves the waveform and gates convolution channels with tabular saturation/shape summaries before learning a multiplicative correction to Birks.

## Simulated ADC Results

| method | family | n | bias_frac | res68_frac | res68_ci95 | mae_mev | mae_mev_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | ml_tree | 13026 | 0.0027876 | 0.047727 | [0.046545948447970935, 0.04862984828169997] | 2.5424 | [2.5102166231126337, 2.577691207723943] |
| mlp | neural_tabular | 13026 | -0.0033189 | 0.068279 | [0.06789669399850855, 0.06902161018062199] | 3.5893 | [3.533949269293881, 3.677246743323393] |
| gated_residual_cnn | neural_gated_residual_new | 13026 | 0.0021065 | 0.087244 | [0.08720240548179549, 0.08738449234856356] | 4.648 | [4.6041108081962365, 4.719421308410436] |
| 1d_cnn | neural_waveform | 13026 | -0.018224 | 0.21196 | [0.20923492500173652, 0.21555680606579083] | 10.761 | [10.686476767873062, 10.840167477575934] |
| ridge | ml_linear | 13026 | 0.0077723 | 0.25055 | [0.2495436395852462, 0.2531123783124238] | 12.894 | [12.731933622537339, 13.032561334826324] |
| truth_birks_lookup | traditional_digitized_birks | 13026 | -0.5095 | 0.66634 | [0.6655800280345259, 0.6667011530817545] | 33.499 | [33.23602172229928, 33.69495252747379] |

## Per-Pseudo-Run Results

| pseudo_run | method | n | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 8 | truth_birks_lookup | 4342 | -0.50804 | 0.66669 | 33.236 |
| 9 | truth_birks_lookup | 4342 | -0.51079 | 0.66666 | 33.567 |
| 10 | truth_birks_lookup | 4342 | -0.5093 | 0.66557 | 33.695 |
| 8 | gradient_boosted_trees | 4342 | 0.0071554 | 0.047876 | 2.5102 |
| 9 | gradient_boosted_trees | 4342 | 0.0065172 | 0.048628 | 2.5777 |
| 10 | gradient_boosted_trees | 4342 | -0.0046534 | 0.046537 | 2.5392 |

## Real Run-Held-Out Reference

Real HRD events are not aligned to GEANT4 events, so the real-data residual comparison uses the registered S24a run-held-out scoreboard as a reference. The ordering remains consistent: the physics/Birks baseline is the strongest real-data closure, while the new digitized simulation shows how much idealized detector response can be recovered by learned residual models.

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

## Sim-vs-Real Residual Structure

| method | sim_res68_frac | real_s24a_res68_frac | delta_sim_minus_real | interpretation |
| --- | --- | --- | --- | --- |
| gradient_boosted_trees | 0.047727 | 0.056685 | -0.0089577 | matched method |
| mlp | 0.068279 | 0.69235 | -0.62407 | matched method |
| 1d_cnn | 0.21196 | 0.2657 | -0.053746 | matched method |
| ridge | 0.25055 | 0.096673 | 0.15388 | matched method |
| truth_birks_lookup | 0.66634 | 0.040244 | 0.6261 | matched method |

## Systematics and Caveats

- The waveform bridge uses measured-style noise, pedestal, shaping, and saturation parameters, but it is not a full optical-photon or electronics-chain simulation.
- The GEANT4-to-HRD mapping assumes even Sci_bar layers map to even B staves; adjacent odd layers remain a geometry systematic.
- Pseudo-runs are deterministic event blocks, not separate experimental run conditions.
- Real comparison is scoreboard-level because the hibeam_g4 and HRD ROOT files are not event-aligned.
- The raw reproduction gate is exact, but the digitizer benchmark is conditional on the S24a ADC/MeV calibration.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. On digitized GEANT4 ADC waveforms the winner is gradient_boosted_trees with res68=0.04773; the traditional truth_birks_lookup remains the transparent baseline and the real S24a reference winner remains geant4_birks_lookup. This separates detector-response idealization from model capacity: when the response is generated by the digitizer, residual neural correction can exploit waveform artifacts, but in real run-held-out data the physics/Birks lookup is still stronger.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s17c_1783760285_digitized_g4_waveform_bridge.py --config configs/s17c_1783760285_digitized_g4_waveform_bridge.yaml
```

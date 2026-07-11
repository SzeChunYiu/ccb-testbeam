# S27b - Gain-Transition Energy PID Pulse Linearity Study
- Study ID:      S27b
- Ticket:        1783780901.11483.5d68764b
- Date:          2026-07-11
- Status:        DONE
- Authors:       CCB analysis fleet
- Worker:        testbeam-laptop-3
- Dependencies:  S00, S14g, S24a, S25a
- Data anchor:   640,737 selected B-stave pulses

**ML loses: traditional 0.04024 beats best ML gradient_boosted_trees 0.05204; the GEANT4-truth Birks/gain calibration is the production candidate for this closure task.**

## 1. Reproduction Gate

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s27b_1783780901_11483_5d68764b_gain_transition_energy_pid.py --config configs/s27b_1783780901_11483_5d68764b_gain_transition_energy_pid.yaml
```

Expected and reproduced raw ROOT count: **640,737** selected B-stave pulse records with baseline median samples 0--3 and even-channel amplitude above 1000 ADC. Delta = **0**. Seed = 2727.

## 2. Physics Motivation

S27b asks whether learned pulse representations improve energy reconstruction and PID separation at the electronics gain transition, where charge integration, saturation, pedestal motion, and pile-up can all distort linearity. The incumbent is a strong conventional model: train-run duplicate-readout charge integration with a GEANT4-truth Birks-like nonlinearity correction. ML is only useful here if it preserves physical linearity and class separation on complete held-out runs.

## 3. Methods and Equations

Raw HRD waveforms are decoded as eight channels by eighteen samples. For channel waveform \(V_{c,t}\), the baseline-subtracted waveform is \(x_{c,t}=V_{c,t}-\mathrm{median}(V_{c,0:3})\), amplitude is \(A_c=\max_t x_{c,t}\), and positive charge is \(Q_c=\sum_t \max(x_{c,t},0)\). The selected even B staves are B2/B4/B6/B8 = channels 0/2/4/6; duplicate odd readout channels 1/3/5/7 define the closure target.

The traditional calibration fits the train-run duplicate odd charges to a Birks-like response

\[ Q_i = \alpha\,\frac{\Delta E_i}{1+k_B(dE/dx)_i}, \]

where \(\Delta E_i\) and \((dE/dx)_i\) are layer priors from `hibeam_g4` `Sci_bar_EDep` and `Sci_bar_TrackLength`. The prediction inverts this equation on the even readout and sums over selected staves. Learned methods use only even-readout features and waveforms: ridge, gradient-boosted trees, tabular MLP, 1D-CNN, a waveform transformer, and a new physics-residual MLP. The transformer is the ticket's new architecture: attention over the 18 time samples after projecting the four B-stave channels.

PID separation is evaluated with the matching S25a all-pre-action run-held-out PID benchmark, copied into this S27b artifact. That table compares the conventional charge-depth logistic score against ridge, gradient-boosted trees, MLP, 1D-CNN, and an action-gated residual ensemble. It is included here because the S27b ticket explicitly couples energy linearity to PID class separation under the same raw-pulse anchor and run-split discipline.

## 4. Run Split and Bootstrap

Training runs: [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64]. Held-out runs: [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65]. All confidence intervals are 95% percentile intervals from 300 complete-run bootstrap resamples; no event from a held-out run appears in training.

## 5. Energy Head-to-Head

| method                 | family                    | n      | bias_frac  | res68_frac | res68_ci95                                 | mae_mev | mae_mev_ci95                             |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup    | traditional_geant4_birks  | 332852 | -0.023099  | 0.040244   | [0.03885442055147856, 0.04166439307853137] | 1.0824  | [0.9594800872478235, 1.258193699308261]  |
| gradient_boosted_trees | ml_tree                   | 332852 | -0.014538  | 0.052038   | [0.04407365786784419, 0.0632146894582223]  | 0.96046 | [0.8401409537081808, 1.096858319660444]  |
| physics_residual_mlp   | neural_physics_residual   | 332852 | -0.0052203 | 0.054519   | [0.04880770366533209, 0.06254275382030709] | 0.98942 | [0.8872438671430233, 1.1170681222659633] |
| ridge                  | ml_linear                 | 332852 | -0.017932  | 0.085389   | [0.07438479562823815, 0.11515744652807515] | 1.3147  | [1.1774236799246565, 1.4779674403059078] |
| transformer            | neural_waveform_attention | 332852 | 0.06776    | 0.13406    | [0.111358557220359, 0.1710212142435038]    | 1.8576  | [1.7249010401339766, 2.0463347096539954] |
| 1d_cnn                 | neural_waveform           | 332852 | -0.10882   | 0.24687    | [0.23871004824723283, 0.26205114603226426] | 3.0234  | [2.9267786884060714, 3.0973532227524245] |
| old_power_law          | traditional_empirical     | 332852 | -0.29763   | 0.46236    | [0.4457562519005668, 0.5558938582674989]   | 7.8628  | [7.385822567380821, 8.284146134914257]   |
| mlp                    | neural_tabular            | 332852 | -0.52401   | 0.59937    | [0.5805660689352949, 0.6106645566646908]   | 9.2537  | [7.665600110972426, 10.317401025040489]  |

ML-minus-traditional deltas use `geant4_birks_lookup` as the conventional incumbent. Negative deltas would favor the alternative method.

| method                 | res68_frac | res68_ci_low | res68_ci_high | delta_vs_birks | delta_ci_conservative_low | delta_ci_conservative_high | beats_birks_ci |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup    | 0.040244   | 0.038854     | 0.041664      | 0              | -0.00281                  | 0.00281                    | False          |
| gradient_boosted_trees | 0.052038   | 0.044074     | 0.063215      | 0.011794       | 0.0024093                 | 0.02436                    | False          |
| physics_residual_mlp   | 0.054519   | 0.048808     | 0.062543      | 0.014275       | 0.0071433                 | 0.023688                   | False          |
| ridge                  | 0.085389   | 0.074385     | 0.11516       | 0.045145       | 0.03272                   | 0.076303                   | False          |
| transformer            | 0.13406    | 0.11136      | 0.17102       | 0.093814       | 0.069694                  | 0.13217                    | False          |
| 1d_cnn                 | 0.24687    | 0.23871      | 0.26205       | 0.20662        | 0.19705                   | 0.2232                     | False          |
| old_power_law          | 0.46236    | 0.44576      | 0.55589       | 0.42211        | 0.40409                   | 0.51704                    | False          |
| mlp                    | 0.59937    | 0.58057      | 0.61066       | 0.55913        | 0.5389                    | 0.57181                    | False          |

## 6. Gain-Transition and Systematics Bins

The gain-transition table reuses the raw-waveform stratification from this run: saturation onset (`A >= 7000 ADC`), pile-up or multihit, pedestal proxy (`charge/peak` above the held-out median), and late/deep pulse topology. These are not post-hoc training cuts; they are reporting strata scored after model fitting.

| bin_family                         | subset     | method                 | n      | bias_frac   | res68_frac | res68_ci_low | res68_ci_high | mae_mev |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_gain_to_saturation_transition | in_stratum | geant4_birks_lookup    | 106217 | -0.040403   | 0.048498   | 0.047484     | 0.05084       | 1.2846  |
| high_gain_to_saturation_transition | in_stratum | gradient_boosted_trees | 106217 | -0.032872   | 0.048864   | 0.044475     | 0.054174      | 1.2979  |
| high_gain_to_saturation_transition | in_stratum | 1d_cnn                 | 106217 | -0.043759   | 0.083469   | 0.075228     | 0.10115       | 2.0838  |
| high_gain_to_saturation_transition | in_stratum | transformer            | 106217 | 0.088833    | 0.11532    | 0.10781      | 0.12753       | 2.5064  |
| high_gain_to_saturation_transition | in_stratum | physics_residual_mlp   | 106217 | -0.0056952  | 0.045226   | 0.042058     | 0.052095      | 1.0727  |
| high_gain_to_saturation_transition | complement | geant4_birks_lookup    | 226635 | -0.016697   | 0.033521   | 0.03274      | 0.034702      | 0.9877  |
| high_gain_to_saturation_transition | complement | gradient_boosted_trees | 226635 | -0.00099279 | 0.054918   | 0.042634     | 0.072957      | 0.80231 |
| high_gain_to_saturation_transition | complement | 1d_cnn                 | 226635 | -0.20467    | 0.29013    | 0.27595      | 0.30136       | 3.4638  |
| high_gain_to_saturation_transition | complement | transformer            | 226635 | 0.038247    | 0.1603     | 0.10409      | 0.20232       | 1.5535  |
| high_gain_to_saturation_transition | complement | physics_residual_mlp   | 226635 | -0.0049402  | 0.061238   | 0.054463     | 0.068251      | 0.95038 |
| pileup_bin                         | in_stratum | geant4_birks_lookup    | 27765  | -0.019433   | 0.12595    | 0.11211      | 0.14337       | 3.1683  |
| pileup_bin                         | in_stratum | gradient_boosted_trees | 27765  | -0.098738   | 0.18723    | 0.17954      | 0.1981        | 3.7326  |
| pileup_bin                         | in_stratum | 1d_cnn                 | 27765  | -0.06466    | 0.30575    | 0.26697      | 0.37292       | 5.3502  |
| pileup_bin                         | in_stratum | transformer            | 27765  | -0.057086   | 0.23924    | 0.23368      | 0.24792       | 4.0835  |
| pileup_bin                         | in_stratum | physics_residual_mlp   | 27765  | 0.014514    | 0.17345    | 0.17012      | 0.17678       | 3.0906  |
| pileup_bin                         | complement | geant4_birks_lookup    | 305087 | -0.02362    | 0.03914    | 0.037702     | 0.040369      | 0.89261 |
| pileup_bin                         | complement | gradient_boosted_trees | 305087 | -0.013087   | 0.046484   | 0.041642     | 0.053218      | 0.70818 |
| pileup_bin                         | complement | 1d_cnn                 | 305087 | -0.11294    | 0.24485    | 0.23723      | 0.26191       | 2.8117  |
| pileup_bin                         | complement | transformer            | 305087 | 0.071226    | 0.12548    | 0.107        | 0.16014       | 1.655   |
| pileup_bin                         | complement | physics_residual_mlp   | 305087 | -0.0058146  | 0.049738   | 0.046197     | 0.055677      | 0.7982  |
| pedestal_bin                       | in_stratum | geant4_birks_lookup    | 166426 | -0.023258   | 0.033216   | 0.032542     | 0.034476      | 1.1235  |
| pedestal_bin                       | in_stratum | gradient_boosted_trees | 166426 | -0.011901   | 0.034422   | 0.030237     | 0.044127      | 1.0635  |
| pedestal_bin                       | in_stratum | 1d_cnn                 | 166426 | -0.21884    | 0.26296    | 0.252        | 0.27297       | 3.9592  |
| pedestal_bin                       | in_stratum | transformer            | 166426 | 0.024974    | 0.097418   | 0.077438     | 0.1377        | 1.7766  |
| pedestal_bin                       | in_stratum | physics_residual_mlp   | 166426 | -0.014013   | 0.049344   | 0.045568     | 0.057331      | 1.1315  |
| pedestal_bin                       | complement | geant4_birks_lookup    | 166426 | -0.02208    | 0.048584   | 0.047319     | 0.050096      | 1.0414  |
| pedestal_bin                       | complement | gradient_boosted_trees | 166426 | -0.018841   | 0.066599   | 0.059795     | 0.077368      | 0.85739 |
| pedestal_bin                       | complement | 1d_cnn                 | 166426 | -0.036456   | 0.20274    | 0.15162      | 0.27162       | 2.0877  |
| pedestal_bin                       | complement | transformer            | 166426 | 0.10006     | 0.16304    | 0.13262      | 0.23092       | 1.9385  |
| pedestal_bin                       | complement | physics_residual_mlp   | 166426 | 0.0043707   | 0.062283   | 0.054449     | 0.076634      | 0.84734 |
| pulse_shape_depth_bin              | in_stratum | geant4_birks_lookup    | 15256  | -0.017026   | 0.11667    | 0.10319      | 0.13379       | 3.0832  |
| pulse_shape_depth_bin              | in_stratum | gradient_boosted_trees | 15256  | -0.12771    | 0.22691    | 0.21149      | 0.24464       | 4.4057  |
| pulse_shape_depth_bin              | in_stratum | 1d_cnn                 | 15256  | -0.036963   | 0.3347     | 0.28672      | 0.40629       | 5.1718  |
| pulse_shape_depth_bin              | in_stratum | transformer            | 15256  | -0.017511   | 0.27682    | 0.25806      | 0.31728       | 4.1279  |
| pulse_shape_depth_bin              | in_stratum | physics_residual_mlp   | 15256  | 0.072354    | 0.26387    | 0.24612      | 0.30929       | 3.9757  |
| pulse_shape_depth_bin              | complement | geant4_birks_lookup    | 317596 | -0.02365    | 0.039799   | 0.038367     | 0.041104      | 0.98633 |
| pulse_shape_depth_bin              | complement | gradient_boosted_trees | 317596 | -0.013447   | 0.04837    | 0.04245      | 0.057306      | 0.79496 |
| pulse_shape_depth_bin              | complement | 1d_cnn                 | 317596 | -0.11185    | 0.24549    | 0.23831      | 0.26152       | 2.9202  |
| pulse_shape_depth_bin              | complement | transformer            | 317596 | 0.06926     | 0.13007    | 0.10797      | 0.16651       | 1.7485  |
| pulse_shape_depth_bin              | complement | physics_residual_mlp   | 317596 | -0.005952   | 0.051216   | 0.047069     | 0.057632      | 0.84598 |

## 7. PID Linearity and Class Separation

| s27b_method                        | n     | runs | roc_auc | roc_auc_ci_low | roc_auc_ci_high | average_precision | purity_at_80pct_eff | ece        | bootstrap_valid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_charge_depth_logistic  | 19424 | 32   | 1       | 1              | 1               | 1                 | 1                   | 0.00015007 | 300             |
| ridge                              | 19424 | 32   | 0.85132 | 0.84477        | 0.86219         | 0.77875           | 0.75921             | 0.031782   | 300             |
| gradient_boosted_trees             | 19424 | 32   | 0.92801 | 0.92161        | 0.93523         | 0.89427           | 0.88154             | 0.034018   | 300             |
| mlp                                | 19424 | 32   | 0.94709 | 0.94072        | 0.95407         | 0.92213           | 0.91057             | 0.013142   | 300             |
| 1d_cnn                             | 19424 | 32   | 0.72677 | 0.70758        | 0.74843         | 0.6389            | 0.64655             | 0.14087    | 300             |
| action_gated_residual_ensemble_new | 19424 | 32   | 1       | 1              | 1               | 1                 | 1                   | 0.0018029  | 300             |
| shuffled_label_hgb_control         | 19424 | 32   | 0.50858 | 0.46113        | 0.55695         | 0.47523           | 0.52092             | 0.0062031  | 300             |

The perfect conventional charge-depth PID score is a useful operational separation but also a warning: the PID proxy is very close to the charge/depth definition, so the report treats PID as a closure and linearity diagnostic rather than external particle truth.

## 8. Leakage Controls

| check                                       | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                   | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                      | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| ml_features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                  | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| transformer_status                          | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0                                                                                                                                                                                                                                                                                                                                                                | True |
| truth_root_used                             | /home/billy/ccb-geant4/output_krakow_1M.root                                                                                                                                                                                                                                                                                                                     | True |
| truth_layers_mapped_to_even_b_staves        | B2->0,B4->2,B6->4,B8->6                                                                                                                                                                                                                                                                                                                                          | True |

The energy benchmark excludes odd charge, run number, event number, and EVT from ML features. The PID table includes an HGB shuffled-label control near chance, and run-family-only controls from S25a. The traditional PID score being exactly separable is therefore interpreted as definition-level separability, not as independent truth discovery.

## 9. Interpretation

The winner named in `result.json` is **geant4_birks_lookup**. Its energy res68 is 0.04024, while the conventional GEANT4/Birks lookup is 0.04024. Since the conventional method wins on the primary energy-linearity endpoint and also gives exact proxy PID separation in the paired PID benchmark, S27b does not justify replacing the physical charge-integration calibration with a generic neural waveform model at the gain transition.

## 10. Systematics and Caveats

The dominant caveats are the lack of event-level alignment between GEANT4 and real HRD runs, the layer-level truth prior, possible optical/electronics response mismatch, saturation at the ADC ceiling, duplicate-readout closure rather than external calorimetric truth, and PID labels that are partly charge/depth defined. The bootstrap unit is run, not row, so intervals represent run-to-run stability but not all hardware systematics.

## 11. MC Verdict

MC validation available as a layer-level `hibeam_g4` `Sci_bar_EDep` prior, but not as a digitized HRD waveform simulation. The data result is therefore MC-anchored for energy scale and nonlinearity, but a digitized MC response is still required to close waveform-model claims.

## 12. Open Questions

1. S27c: digitized gain-transition response closure. Hypothesis: a simulated HRD electronics response removes the residual mismatch that generic waveform ML currently tries to absorb. Falsifying test: train on digitized GEANT4 ADC waveforms and require the residual-ML gain to persist on real held-out runs without retuning.

## 13. Provenance

- Git commit: de618c7fe19b4ab456214144e89f85f9d2ee5180
- Data SHA256: see `input_sha256.csv`.
- Python: 3.7.6
- Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `method_metrics.csv`, `gain_transition_systematics.csv`, `pid_linearity_benchmark.csv`, `reproduction_match_table.csv`, `input_sha256.csv`.

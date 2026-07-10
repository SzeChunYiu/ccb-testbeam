# S22 Supervised p/d PID from GEANT4 Truth Transferred to Real CCB Pulses

- **Ticket:** `1781181864.166893.491f3bde`
- **Worker:** `testbeam-laptop-3`
- **Git commit:** `d2a393d37665c6bd7a95bac48a623950f58758a6`
- **GEANT4 ROOT:** `/home/billy/ccb-geant4/output_krakow_1M.root`
- **Experimental raw ROOT:** `data/root/root/hrdb_run_*.root`
- **Preregistered winner metric:** deuteron average precision on held-out run-like blocks

## Abstract

This study tests whether proton/deuteron labels from GEANT4 truth can train a useful PID discriminator and whether modern ML/NN models improve over a transparent range-telescope dE-E rule. The analysis first reruns the experimental raw-ROOT B-stave gate from `HRDv` and reproduces the selected-pulse anchor exactly. It then reads the 1M-event GEANT4 `hibeam` tree, builds primary p/d Sci_bar energy profiles, compares a fold-local traditional dE-E threshold against ridge logistic regression, histogram gradient-boosted trees, an MLP, a 1D-CNN, and a new physics-gated CNN, and reports run-block bootstrap confidence intervals. The transfer-to-real-data claim is deliberately limited: real ROOT supports the selected-pulse and depth-support comparison, but it lacks truth PID labels and an ADC-to-MeV detector-response bridge.

## 1. Reproduction Gates

### 1.1 Experimental raw ROOT selected-pulse count

For each B-stack raw file, each event waveform is reshaped as \(x_{i,c,t}\in\mathbb{R}^{8	imes18}\). Physical B staves are even channels \(c\in\{0,2,4,6\}\), mapped to B2/B4/B6/B8. The pedestal is
\[
b_{i,c} = \operatorname{median}(x_{i,c,0},x_{i,c,1},x_{i,c,2},x_{i,c,3}),
\]
and the selected-pulse amplitude is
\[
A_{i,c}=\max_t x_{i,c,t} - b_{i,c}.
\]
A pulse is selected when \(A_{i,c}>1000\) ADC. This is recomputed directly from `data/root/root/hrdb_run_*.root`, not from sorted tables.

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses from raw HRDv | 640737 | 640737 | 0 | 0 | true |
| sample_i_calib selected B-stave pulses |  | 248745 |  | descriptive | true |
| sample_i_analysis selected B-stave pulses |  | 252266 |  | descriptive | true |
| sample_ii_calib selected B-stave pulses |  | 14630 |  | descriptive | true |
| sample_ii_analysis selected B-stave pulses |  | 125096 |  | descriptive | true |

The sample/stave support used for transfer diagnostics is:

| sample | events | selected_pulses | B2_selected | B4_selected | B6_selected | B8_selected |
| --- | --- | --- | --- | --- | --- | --- |
| sample_i_analysis | 388879 | 252266 | 241422 | 6451 | 3094 | 1299 |
| sample_i_calib | 409815 | 248745 | 237882 | 6747 | 2940 | 1176 |
| sample_ii_analysis | 262091 | 125096 | 88213 | 21229 | 11148 | 4506 |
| sample_ii_calib | 35943 | 14630 | 11907 | 1689 | 763 | 271 |

### 1.2 GEANT4 truth reproduction

The simulation input is the ticket-specified `/home/billy/ccb-geant4/output_krakow_1M.root`. The ROOT metadata reproduces the full 1M-event tree count. To keep this ticket executable on the worker, truth features are materialized for the first `120000` events and the benchmark uses a deterministic stratified cap of `24000` labelled primary tracks, balanced across pseudo-run and p/d class cells where possible. The ROOT tree has no acquisition-run branch, so contiguous event-id blocks define `8` pseudo-runs. Those blocks are used both for leave-one-block-out evaluation and for bootstrap confidence intervals.

| quantity | reference_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| hibeam tree entries | 1000000 | 1000000 | 0 | 0 | true |
| GEANT4 events materialized for truth features | bounded by config max_geant4_events_materialized=120000 | 120000 |  | descriptive | true |
| Sci_bar truth hits |  | 152323 |  | descriptive | true |
| primary p/d tracks with Sci_bar deposit |  | 36419 |  | descriptive | true |
| GEANT4 input path | /home/billy/ccb-geant4/output_krakow_1M.root | /home/billy/ccb-geant4/output_krakow_1M.root |  | identity | true |
| truth-labelled primary p/d tracks |  | 36419 |  | descriptive | true |
| Sci_bar truth hits used for transfer summaries |  | 152323 |  | descriptive | true |

## 2. Dataset and Estimands

The labelled unit is a primary GEANT4 proton or deuteron track with nonzero Sci_bar deposited energy. Secondary p/d fragments are excluded from the target to avoid training on shower taxonomy. The saved `pid_track_dataset.csv` is the benchmark sample; the GEANT4 reproduction table records the larger materialized truth-feature support. For layers \(l=0,\ldots,7\), the raw sequence is \(E_l\), and the NN sequence input is \(z_l=\log(1+E_l)\). Engineered tabular features are
\[
E_{tot}=\sum_l E_l,\quad
f_{early}=(E_0+E_1)/E_{tot},\quad
L_{max}=\max\{l:E_l>0\},
\]
plus downstream energy, hit-layer multiplicity, layer centroid \(\sum_l lE_l/E_{tot}\), maximum layer EDep, and B2/B4/B6/B8 depth sums.

The positive class is deuteron. Purity is \(TP/(TP+FP)\), efficiency is \(TP/(TP+FN)\), and ranking quality is average precision. Winner selection uses average precision because no real-data operating threshold is yet externally calibrated.

## 3. Methods

### Traditional dE-E/range baseline

The transparent comparator is a fold-local range telescope score:

```text
s = f_early - 0.060 L_max - 0.035 log(1 + E_downstream) + 0.020 log(1 + E_early)
```

The threshold is chosen only on training pseudo-runs by maximizing deuteron F1, then applied unchanged to the held-out pseudo-run. This is a strong non-ML baseline because it encodes the expected deuteron signature: high early energy fraction and shorter range.

### ML/NN comparators

Ridge logistic regression uses L2-regularized logistic loss on standardized features. Histogram gradient-boosted trees use shallow leaf-limited additive trees. The MLP is a two-hidden-layer neural classifier with early stopping. The 1D-CNN sees only the ordered eight-layer energy sequence. The new architecture is a physics-gated CNN: the first convolutional representation is multiplied by a learned sigmoid gate and the final head also receives total EDep and layer centroid. This injects the same range/depth inductive bias as the traditional dE-E rule while still learning nonlinear overlap regions.

All models are trained in leave-one-pseudo-run-out folds. For metric \(m\), bootstrap intervals resample the held-out pseudo-run identifiers with replacement and recompute \(m\) on the concatenated tracks in the sampled blocks.

## 4. Head-to-Head Benchmark

| method | purity_precision | purity_precision_ci_low | purity_precision_ci_high | efficiency_recall | efficiency_recall_ci_low | efficiency_recall_ci_high | average_precision | average_precision_ci_low | average_precision_ci_high | roc_auc | roc_auc_ci_low | roc_auc_ci_high | brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosted_trees | 0.9345 | 0.9272 | 0.9442 | 0.9562 | 0.9447 | 0.9644 | 0.9930 | 0.9925 | 0.9934 | 0.9928 | 0.9924 | 0.9933 | 0.0337 |
| sklearn_mlp | 0.9263 | 0.9185 | 0.9344 | 0.9610 | 0.9492 | 0.9735 | 0.9926 | 0.9921 | 0.9931 | 0.9924 | 0.9919 | 0.9928 | 0.0349 |
| ridge_logistic_l2 | 0.8494 | 0.8443 | 0.8548 | 0.9313 | 0.9272 | 0.9359 | 0.9502 | 0.9474 | 0.9528 | 0.9545 | 0.9525 | 0.9567 | 0.0913 |
| torch_1d_cnn | 0.7079 | 0.6740 | 0.7665 | 0.7239 | 0.4841 | 0.9045 | 0.8737 | 0.8625 | 0.8928 | 0.8744 | 0.8600 | 0.8947 | 0.1482 |
| traditional_deltae_range_cut | 0.6677 | 0.6640 | 0.6721 | 0.9988 | 0.9976 | 0.9998 | 0.7871 | 0.7800 | 0.7929 | 0.8186 | 0.8121 | 0.8250 | 0.2183 |
| physics_gated_cnn | 0.5538 | 0.5233 | 0.6106 | 0.9111 | 0.8457 | 0.9590 | 0.6169 | 0.5708 | 0.6482 | 0.6343 | 0.4928 | 0.7287 | 0.3180 |

**Winner:** `hist_gradient_boosted_trees`. Its average-precision gain over the traditional dE-E/range score is `0.2058` with run-block 95% CI `[0.1997, 0.2121]`.

## 5. Held-Out Run-Like Stability

| method | pseudo_run | average_precision | roc_auc | f1 | balanced_accuracy |
| --- | --- | --- | --- | --- | --- |
| hist_gradient_boosted_trees | 0 | 0.9935 | 0.9935 | 0.9497 | 0.9493 |
| hist_gradient_boosted_trees | 1 | 0.9931 | 0.9934 | 0.9463 | 0.9467 |
| hist_gradient_boosted_trees | 2 | 0.9920 | 0.9923 | 0.9412 | 0.9393 |
| hist_gradient_boosted_trees | 3 | 0.9918 | 0.9920 | 0.9411 | 0.9400 |
| hist_gradient_boosted_trees | 4 | 0.9935 | 0.9936 | 0.9466 | 0.9460 |
| hist_gradient_boosted_trees | 5 | 0.9932 | 0.9934 | 0.9455 | 0.9447 |
| hist_gradient_boosted_trees | 6 | 0.9921 | 0.9927 | 0.9500 | 0.9487 |
| hist_gradient_boosted_trees | 7 | 0.9926 | 0.9927 | 0.9414 | 0.9420 |
| physics_gated_cnn | 0 | 0.6533 | 0.7341 | 0.7327 | 0.6950 |
| physics_gated_cnn | 1 | 0.6617 | 0.7436 | 0.6667 | 0.5000 |
| physics_gated_cnn | 2 | 0.6384 | 0.7166 | 0.7098 | 0.6697 |
| physics_gated_cnn | 3 | 0.6480 | 0.7288 | 0.7160 | 0.6710 |
| physics_gated_cnn | 4 | 0.6347 | 0.7125 | 0.7131 | 0.6720 |
| physics_gated_cnn | 5 | 0.5065 | 0.3482 | 0.6667 | 0.5000 |
| physics_gated_cnn | 6 | 0.6437 | 0.7230 | 0.6667 | 0.5000 |
| physics_gated_cnn | 7 | 0.5061 | 0.3510 | 0.6667 | 0.5000 |
| ridge_logistic_l2 | 0 | 0.9512 | 0.9578 | 0.8962 | 0.8913 |
| ridge_logistic_l2 | 1 | 0.9513 | 0.9555 | 0.8936 | 0.8900 |
| ridge_logistic_l2 | 2 | 0.9507 | 0.9550 | 0.8878 | 0.8820 |
| ridge_logistic_l2 | 3 | 0.9566 | 0.9586 | 0.8914 | 0.8857 |
| ridge_logistic_l2 | 4 | 0.9445 | 0.9504 | 0.8844 | 0.8780 |
| ridge_logistic_l2 | 5 | 0.9565 | 0.9587 | 0.8918 | 0.8860 |
| ridge_logistic_l2 | 6 | 0.9472 | 0.9521 | 0.8796 | 0.8737 |
| ridge_logistic_l2 | 7 | 0.9443 | 0.9492 | 0.8832 | 0.8783 |
| sklearn_mlp | 0 | 0.9934 | 0.9930 | 0.9472 | 0.9453 |
| sklearn_mlp | 1 | 0.9915 | 0.9914 | 0.9443 | 0.9440 |
| sklearn_mlp | 2 | 0.9919 | 0.9916 | 0.9400 | 0.9397 |
| sklearn_mlp | 3 | 0.9925 | 0.9922 | 0.9395 | 0.9383 |
| sklearn_mlp | 4 | 0.9937 | 0.9935 | 0.9456 | 0.9447 |
| sklearn_mlp | 5 | 0.9934 | 0.9932 | 0.9437 | 0.9417 |
| sklearn_mlp | 6 | 0.9923 | 0.9922 | 0.9474 | 0.9453 |
| sklearn_mlp | 7 | 0.9920 | 0.9919 | 0.9384 | 0.9390 |
| torch_1d_cnn | 0 | 0.8989 | 0.8795 | 0.8015 | 0.7523 |
| torch_1d_cnn | 1 | 0.9241 | 0.9213 | 0.8212 | 0.8187 |
| torch_1d_cnn | 2 | 0.8914 | 0.8788 | 0.6838 | 0.7090 |
| torch_1d_cnn | 3 | 0.9146 | 0.9126 | 0.7989 | 0.7513 |
| torch_1d_cnn | 4 | 0.8737 | 0.8686 | 0.6651 | 0.7140 |
| torch_1d_cnn | 5 | 0.8909 | 0.8690 | 0.7211 | 0.6847 |
| torch_1d_cnn | 6 | 0.8562 | 0.8401 | 0.0000 | 0.5000 |
| torch_1d_cnn | 7 | 0.8803 | 0.8816 | 0.8069 | 0.7707 |
| traditional_deltae_range_cut | 0 | 0.7889 | 0.8235 | 0.7995 | 0.7497 |
| traditional_deltae_range_cut | 1 | 0.7989 | 0.8323 | 0.8077 | 0.7620 |
| traditional_deltae_range_cut | 2 | 0.7706 | 0.8037 | 0.7981 | 0.7470 |
| traditional_deltae_range_cut | 3 | 0.7895 | 0.8185 | 0.8013 | 0.7520 |
| traditional_deltae_range_cut | 4 | 0.7751 | 0.8061 | 0.7939 | 0.7403 |
| traditional_deltae_range_cut | 5 | 0.7937 | 0.8254 | 0.8060 | 0.7597 |
| traditional_deltae_range_cut | 6 | 0.7859 | 0.8160 | 0.7983 | 0.7487 |
| traditional_deltae_range_cut | 7 | 0.7958 | 0.8228 | 0.7985 | 0.7477 |

The table is intentionally block-level rather than event-random. It should be read as stability across simulation event regions, not as true beam-run stability.

## 6. Transfer to Real CCB Pulse Support

Because the real data have no p/d truth label in the raw files, a simulation-trained PID cannot be validated on real events in this ticket. The defensible transfer test is support compatibility: compare real selected-pulse depth support with simulated active Sci_bar depth support.

| stave | data_selected_pulses | data_fraction_relative_to_B2 | sim_primary_tracks_active | sim_active_fraction | sim_median_active_edep_MeV |
| --- | --- | --- | --- | --- | --- |
| B2 | 579424 | 1.0000 | 36410 | 0.9998 | 43.4320 |
| B4 | 36116 | 0.0623 | 17093 | 0.4693 | 32.4556 |
| B6 | 17945 | 0.0310 | 10035 | 0.2755 | 42.1958 |
| B8 | 7252 | 0.0125 | 7108 | 0.1952 | 40.0990 |

Layer-level truth composition and depth:

| layer | mapped_stave | n_hits | n_hits_gt10MeV | mean_edep_MeV | p_frac | d_frac | p_over_d_fraction_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | B2 | 44218 | 37052 | 23.3622 | 0.4964 | 0.3932 | 1.2624 |
| 1 | B2 | 34316 | 29224 | 20.9488 | 0.5508 | 0.3623 | 1.5203 |
| 2 | B4 | 20886 | 17610 | 20.6228 | 0.6943 | 0.1995 | 3.4802 |
| 3 | B4 | 17076 | 14441 | 17.6099 | 0.7282 | 0.1882 | 3.8690 |
| 4 | B6 | 11996 | 10252 | 16.9525 | 0.8955 | 0.0071 | 126.3765 |
| 5 | B6 | 11445 | 9695 | 23.1482 | 0.8843 | 0.0052 | 168.6833 |
| 6 | B8 | 8270 | 6951 | 22.6641 | 0.9034 | 0.0039 | 233.4688 |
| 7 | B8 | 4116 | 3362 | 19.9300 | 0.8899 | 0.0056 | 159.2609 |

The real selected support falls much faster with depth than the simulation active-track support. This is compatible with threshold, Bragg, light-yield, electronics, and trigger effects, but it prevents a direct claim that the GEANT4 score is calibrated on real CCB pulses.

## 7. Leakage, Calibration, and Systematics

| check | value | pass | interpretation |
| --- | --- | --- | --- |
| feature_excludes_event_track_run_and_label | 1.0000 | true | Only Sci_bar EDep depth vectors and derived range summaries enter models. |
| shuffled_training_label_logistic_auc | 0.5238 | true | Chance-like ranking when training labels are permuted inside the same folds. |
| intentional_label_oracle_auc | 1.0000 | true | A direct-label oracle is detected as perfect, validating the sentinel. |

### 7.1 Caveats

| claim | evidence | severity |
| --- | --- | --- |
| GEANT4 p/d score is trained on MeV EDep truth, not ADC waveforms | real raw ROOT provides selected-pulse counts but no truth PID label or calibrated ADC-to-MeV response | high |
| simulation penetration is much gentler than selected real B-stack support | compare sim_active_fraction and data_fraction_relative_to_B2 by stave | high |
| winner score operating range in truth benchmark | hist_gradient_boosted_trees score q10/q50/q90 = 0.001/0.506/0.999 | context |

Main systematics:

- **No real PID truth:** real raw ROOT validates support and count reproduction, not p/d accuracy.
- **Detector response missing:** GEANT4 EDep is MeV truth; real pulse amplitudes are ADC after scintillation, electronics, saturation, thresholding, and triggering.
- **Pseudo-runs are not acquisition runs:** CIs capture block variation in one simulation campaign, not environmental run-to-run drift.
- **Primary-track label only:** clean supervision excludes secondaries and pile-up mixtures that may matter in real data.
- **Architecture selection:** the physics-gated CNN is sensible for an ordered layer sequence but should be treated as a hypothesis until tested on independent simulation or external truth.

## 8. Conclusion

The raw experimental gate reproduces exactly at `640,737` selected B-stave pulses, and the 1M-event GEANT4 file provides a large supervised p/d truth sample. The named winner in `result.json` is `hist_gradient_boosted_trees` by held-out average precision. It beats the traditional dE-E/range rule on the simulation truth benchmark, but the result is not a real-data PID calibration: the real-data transfer evidence is support-level only, and absolute deployment requires an ADC-to-MeV response bridge or an external labelled real subset.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s22_1781181864_166893_491f3bde_g4_truth_real_pid_transfer.py --config configs/s22_1781181864_166893_491f3bde_g4_truth_real_pid_transfer.json
```

Primary artifacts are `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `geant4_reproduction_match_table.csv`, `pid_benchmark.csv`, `pid_per_pseudo_run.csv`, `pid_predictions.csv`, `real_transfer_stave_support.csv`, `leakage_checks.csv`, `input_sha256.csv`, and PNG diagnostics.

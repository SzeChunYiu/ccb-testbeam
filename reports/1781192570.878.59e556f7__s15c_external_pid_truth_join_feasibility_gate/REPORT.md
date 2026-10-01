# S15c: external PID truth join feasibility gate

Claimed queue ticket: GitHub issue `#2415`.

## Abstract

This study tests whether the S15 real-data weak-label PID rows can be converted into an event-level proton/deuteron truth benchmark by joining beamline metadata, GEANT4 truth, or external detector products.  The answer is **no with the current repository/data mirror**.  The raw B-stack ROOT files reproduce the selected-pulse count exactly, but the real HRD trees expose only acquisition/event counters and waveform arrays, while available GEANT4/PID-truth products are simulation-side or summary tables without a real-data run-plus-event PID label join.

The winner written to `result.json` is therefore `no_event_level_pid_truth_join_feasible`.  This is a feasibility winner, not a classifier: all requested supervised methods are explicitly marked blocked because no event-level PID truth target exists for the real S15 rows.

## Reproduction Gate

The raw reproduction uses `data/root/root/hrdb_run_*.root` through the same `HRDv` loader used by P08b/S15b.  For each event, channels B2/B4/B6/B8 are baseline-subtracted using samples 0--3; a selected pulse is any B-stave even readout with maximum amplitude above 1000 ADC.

Let \(x_{ic}\) be waveform sample \(c\) for channel \(i\), \(b_i=\mathrm{median}(x_{i0},\ldots,x_{i3})\), and \(a_i=\max_c(x_{ic}-b_i)\).  A pulse is selected when \(a_i>1000\).  The reproduced count is

\[
N_\mathrm{sel} = \sum_{r} \sum_{e} \sum_{i\in\{B2,B4,B6,B8\}} \mathbf{1}[a_{rei}>1000].
\]

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

## Raw ROOT Schema Audit

The real-data HRD files contain event counters (`EVENTNO`, `EVT`) and waveform arrays (`HRD`, `HRDI`, `HRDv`), but no particle identity, PDG, truth, species, beamline tag, time-of-flight, Cherenkov, or external detector PID branch.

|   run |   entries | event_key_branches   | truth_like_branches   | verdict                                     |
|------:|----------:|:---------------------|:----------------------|:--------------------------------------------|
|    31 |     39990 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    32 |     41921 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    33 |     57173 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    34 |     39765 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    35 |     27786 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    36 |     21764 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    37 |     50513 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    39 |     30321 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    40 |     32613 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    41 |     33997 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    42 |     33972 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    44 |      4294 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    45 |     48181 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    46 |      1441 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    47 |     10970 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    48 |     31713 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    49 |     32354 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    50 |     44804 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    51 |     20569 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    52 |     10005 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    53 |     39612 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    54 |     37413 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    55 |     24416 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    56 |     51823 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    57 |     31284 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    58 |     34141 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    59 |     42303 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    60 |     36074 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    61 |     36535 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    62 |     37584 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    63 |     37030 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    64 |     35943 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |
|    65 |     38424 | EVENTNO, EVT         |                       | no PID/truth/species branch in raw HRD tree |

## Candidate External/GEANT4 Source Audit

The feasibility rule was intentionally strict.  A source is joinable only if it contains at least one PID/truth/species-like column and both a real-data run key and a real-data event key (`run` plus `event_index`, `EVENTNO`, `EVT`, or equivalent).  Simulation-only event numbers are not accepted as real-data event keys.

| path                                                                                              | type   | readable   | truth_like_columns                         | join_key_columns   | joinable_to_real_s15_rows   | verdict                                 |
|:--------------------------------------------------------------------------------------------------|:-------|:-----------|:-------------------------------------------|:-------------------|:----------------------------|:----------------------------------------|
| reports/0000000004.1.g4truth/event_pid_edep_summary.csv                                           | .csv   | True       | ['pdg', 'particle']                        | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/input_sha256.csv                                                     | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/manifest.json                                                        | .json  | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/primary_truth_summary.csv                                            | .csv   | True       | ['pdg', 'particle', 'n_primary_particles'] | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/result.json                                                          | .json  | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/run_feasibility.csv                                                  | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/sci_bar_layer_pid_summary.csv                                        | .csv   | True       | ['pdg', 'particle']                        | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/sci_bar_pid_summary.csv                                              | .csv   | True       | ['pdg', 'particle']                        | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/truth_schema.csv                                                     | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/validation_metadata.json                                             | .json  | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000004.1.g4truth/validation_metrics.csv                                               | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/energy_scale_validation.csv                                           | .csv   | True       | ['sim_truth_comparison']                   | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/input_sha256.csv                                                      | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/layer_mapping_truth.csv                                               | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/leakage_checks.csv                                                    | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/manifest.json                                                         | .json  | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/pid_benchmark.csv                                                     | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/pid_per_pseudo_run.csv                                                | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/pid_predictions.csv                                                   | .csv   | True       | ['pdg', 'particle', 'y_deuteron']          | ['track_id']       | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/pid_thresholds.csv                                                    | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/pid_track_dataset.csv                                                 | .csv   | True       | ['pdg', 'particle', 'y_deuteron']          | ['track_id']       | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/reproduction_match_table.csv                                          | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/result.json                                                           | .json  | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/stave_mapping_data_vs_sim.csv                                         | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000008.1.usesim/winner_reliability.csv                                                | .csv   | True       | ['observed_deuteron_fraction']             | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/class_counts.csv                                                     | .csv   | True       | ['truth_class', 'truth_pdg']               | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/confusion_matrix_winner.csv                                          | .csv   | True       | ['pred_proton', 'pred_deuteron']           | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/fold_metrics.csv                                                     | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/input_sha256.csv                                                     | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/leakage_checks.csv                                                   | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/manifest.json                                                        | .json  | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/method_metrics.csv                                                   | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/per_species_metrics.csv                                              | .csv   | True       | ['species', 'truth_n']                     | []                 | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/raw_reproduction_by_run.csv                                          | .csv   | True       | []                                         | ['run']            | False                       | not event-key joinable to real S15 rows |
| reports/0000000009.1.pidfull/result.json                                                          | .json  | True       | ['truth_definition']                       | []                 | False                       | not event-key joinable to real S15 rows |
| reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/energy_scale_validation.csv  | .csv   | True       | ['sim_truth_comparison']                   | []                 | False                       | not event-key joinable to real S15 rows |
| reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/geant4_reproduction_gate.csv | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/input_sha256.csv             | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/layer_mapping_truth.csv      | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |
| reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/leakage_checks.csv           | .csv   | True       | []                                         | []                 | False                       | not event-key joinable to real S15 rows |

No candidate passed this rule.  GEANT4 truth reports can benchmark simulated tracks, but their event identifiers describe simulation events, not raw HRD events.  S15b and P08-style tables provide weak labels derived from duplicate-readout charge/depth residuals, not external PID truth.

## Requested Benchmark Panel

The requested methods were enumerated and then blocked before training because the target \(Y_i^\mathrm{PID}\) is unobserved for every real S15 row.  Formally, the intended supervised benchmark would require joined rows

\[
\mathcal{D}=\{(X_i,Y_i^\mathrm{PID},r_i): Y_i^\mathrm{PID}\in\{p,d\}\},
\]

with folds \(\mathcal{D}_{\mathrm{test},r}=\{i:r_i=r\}\).  Here \(|\mathcal{D}|=0\), so ROC AUC, average precision, and bootstrap intervals are undefined rather than poor.

| method                          | family                     | status                           |   n_joined_truth_rows |   n_runs |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high | notes                                                                             |
|:--------------------------------|:---------------------------|:---------------------------------|----------------------:|---------:|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|:----------------------------------------------------------------------------------|
| traditional_deltae_depth_ridge  | truth_supervised_requested | blocked_no_event_level_pid_truth |                     0 |        0 |       nan |              nan |               nan |                 nan |                        nan |                         nan | Not fit: no candidate source provides real-data run+event PID truth for S15 rows. |
| ridge                           | truth_supervised_requested | blocked_no_event_level_pid_truth |                     0 |        0 |       nan |              nan |               nan |                 nan |                        nan |                         nan | Not fit: no candidate source provides real-data run+event PID truth for S15 rows. |
| gradient_boosted_trees          | truth_supervised_requested | blocked_no_event_level_pid_truth |                     0 |        0 |       nan |              nan |               nan |                 nan |                        nan |                         nan | Not fit: no candidate source provides real-data run+event PID truth for S15 rows. |
| mlp                             | truth_supervised_requested | blocked_no_event_level_pid_truth |                     0 |        0 |       nan |              nan |               nan |                 nan |                        nan |                         nan | Not fit: no candidate source provides real-data run+event PID truth for S15 rows. |
| cnn_1d                          | truth_supervised_requested | blocked_no_event_level_pid_truth |                     0 |        0 |       nan |              nan |               nan |                 nan |                        nan |                         nan | Not fit: no candidate source provides real-data run+event PID truth for S15 rows. |
| support_residual_hybrid_mlp_new | truth_supervised_requested | blocked_no_event_level_pid_truth |                     0 |        0 |       nan |              nan |               nan |                 nan |                        nan |                         nan | Not fit: no candidate source provides real-data run+event PID truth for S15 rows. |

For context only, S15b previously ran the same family names against calibrated weak labels.  Those numbers are not promoted here:

| method                          | prior_scope          |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high | caveat                                                                            |
|:--------------------------------|:---------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|:----------------------------------------------------------------------------------|
| traditional_deltae_depth_ridge  | S15b weak-label only |  0.986032 |         0.976354 |          0.994047 |            0.984968 |                   0.975265 |                    0.993691 | Not event-level PID truth; included only to show what cannot be promoted by S15c. |
| ridge                           | S15b weak-label only |  0.960544 |         0.944837 |          0.973851 |            0.931921 |                   0.919782 |                    0.944611 | Not event-level PID truth; included only to show what cannot be promoted by S15c. |
| gradient_boosted_trees          | S15b weak-label only |  0.988335 |         0.98082  |          0.994763 |            0.98908  |                   0.982339 |                    0.995034 | Not event-level PID truth; included only to show what cannot be promoted by S15c. |
| mlp                             | S15b weak-label only |  0.987591 |         0.979743 |          0.994289 |            0.988407 |                   0.981395 |                    0.994312 | Not event-level PID truth; included only to show what cannot be promoted by S15c. |
| cnn_1d                          | S15b weak-label only |  0.903371 |         0.867762 |          0.940793 |            0.857099 |                   0.81106  |                    0.910179 | Not event-level PID truth; included only to show what cannot be promoted by S15c. |
| support_residual_hybrid_mlp_new | S15b weak-label only |  0.99674  |         0.994144 |          0.998663 |            0.99638  |                   0.993969 |                    0.998423 | Not event-level PID truth; included only to show what cannot be promoted by S15c. |

## Bootstrap and Confidence Intervals

If a joinable target existed, each method would be scored in leave-one-run-out folds, and the primary CI would be a run-block bootstrap:

\[
\hat m^*_b = M\left(\bigcup_{r\in R_b^*} \mathcal{D}_{\mathrm{test},r}\right),\quad R_b^*\sim \mathrm{Multiset}(R, |R|).
\]

Because \(R=\varnothing\) for truth-labelled real rows, the CI endpoints are reported as null in `truth_benchmark_blocked.csv`.  This is an identifiability failure, not a statistical fluctuation.

## Systematics

- **Raw-data schema limitation:** the accessible HRD ROOT contains waveform and event-counter branches but no external particle labels.
- **Simulation/data non-isomorphism:** GEANT4 truth labels simulated particles; no event-level mapping from simulated events to HRD acquisition events exists.
- **Weak-label circularity:** S15b labels are charge/depth residual proxies.  They are useful support diagnostics but cannot validate proton/deuteron PID.
- **Run-block inference:** a truth benchmark would need multiple labelled real runs; with zero joined truth rows, run-split inference is undefined.
- **Metadata search incompleteness:** this audit covers repository data products and configured external/GEANT4 locations.  A private beamline log not present in these locations could change the conclusion, but it is not available to this reproducible analysis.

## Caveats

The conclusion is negative but actionable.  S15 scores should continue to be described as weak-label support-proxy closure until a new source provides `(run, event)`-level particle identity for raw HRD events.  A valid future source would need immutable checksums, documented synchronization to HRD `EVENTNO`/`EVT`, and enough per-run p/d support to fit the traditional, ridge, gradient-boosted tree, MLP, 1D-CNN, and residual-hybrid methods under the same run-block bootstrap.

## Conclusion

S15c finds **no feasible event-level PID truth join** for the S15 weak-label rows.  The named winner is the abstaining feasibility gate `no_event_level_pid_truth_join_feasible`; no ML/NN method is eligible for a truth-PID win because there are no joined truth-labelled real events.

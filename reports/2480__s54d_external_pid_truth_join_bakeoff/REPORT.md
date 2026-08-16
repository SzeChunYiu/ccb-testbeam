# S54d/#2480: External PID Truth Join for S54c Boundary Validation

## Abstract

This study asks whether the S54c deltaE/E-depth boundary rows can be validated
against event-level proton/deuteron truth from beamline, GEANT4, or external
detector metadata.  The real-data answer is **not yet**: the audited HRD raw
ROOT files and corrected deltaE/E data table expose run/event keys but no
external PID branch.  Where truth is available, it is simulation-side GEANT4
truth in `reports/paper_956_deltaE_E_20260814T090700Z/deltaE_E_events_mc.csv.gz`, so the classifier benchmark below is a
GEANT4 transfer rehearsal rather than a real-data PID validation.

The simulation-side winner in `result.json` is **`gradient_boosted_trees`**.  Its ROC AUC is
`0.9999` with run-block bootstrap 95% CI
[`0.9997`, `1.0000`].

## Raw ROOT Reproduction

The reproduction gate reads `/home/billy/ccb-data/data/extracted/root/root` directly.  For each event and
B-stack even stave `s in {B2,B4,B6,B8}`, the pedestal is

`b_es = median(x_es0, x_es1, x_es2, x_es3)`,

and a selected pulse is

`I_es = 1[max_t(x_est - b_es) > 1000 ADC]`.

Thus

`N_sel = sum_e sum_s I_es`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |       0 |           0 | True   |

## Joinability Audit

An event-level external PID join requires a particle/truth/species-like label
and keys that identify the same real event: `run_id` plus `event_id`, `EVENTNO`,
or `EVT`.  The raw HRD files have event counters and waveform arrays but no PID
truth branch.  The MC table has truth labels, but its event identifiers are
simulation event identifiers, not HRD event keys.

| source                                                                                                            | run_id   | event_key_branches   | truth_like_branches      | joinable_event_level_pid_truth   | verdict                                                      |
|:------------------------------------------------------------------------------------------------------------------|:---------|:---------------------|:-------------------------|:---------------------------------|:-------------------------------------------------------------|
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0044.root                                                  | 44       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0045.root                                                  | 45       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0046.root                                                  | 46       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0047.root                                                  | 47       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0048.root                                                  | 48       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0049.root                                                  | 49       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0050.root                                                  | 50       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0051.root                                                  | 51       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0052.root                                                  | 52       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0053.root                                                  | 53       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0054.root                                                  | 54       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0055.root                                                  | 55       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0056.root                                                  | 56       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0057.root                                                  | 57       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0058.root                                                  | 58       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0059.root                                                  | 59       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0060.root                                                  | 60       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0061.root                                                  | 61       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0062.root                                                  | 62       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0063.root                                                  | 63       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0064.root                                                  | 64       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0065.root                                                  | 65       | EVENTNO, EVT         |                          | False                            | no event-level PID/truth branch in real HRD tree             |
| /home/billy/.tb-workers/testbeam-laptop-1/reports/paper_956_deltaE_E_20260814T090700Z/deltaE_E_events_data.csv.gz | table    | run_id, event_id     |                          | False                            | real data table has no truth label                           |
| /home/billy/.tb-workers/testbeam-laptop-1/reports/paper_956_deltaE_E_20260814T090700Z/deltaE_E_events_mc.csv.gz   | table    | run_id, event_id     | truth_pdg, truth_species | True                             | simulation truth only; event ids are not real HRD event keys |

## Benchmark Design

Because no real event-level PID truth joins to S54c rows, the supervised bakeoff
is run only on GEANT4 deltaE/E rows with `truth_species in {p,d}`.  The groups
are deterministic pseudo-run shards `floor(event_id/25000)`, used only to
estimate run-like transfer variability.  All reported confidence intervals are
percentile intervals from 600 bootstrap resamples of those shards.

The feature vector is

`x = [DeltaE, E_4, E_full, edep_B2, edep_B4, edep_B6, edep_B8, w, edep_layer_0,...,edep_layer_7]`,

and the binary target is

`y = 1[truth_species = d]`.

The traditional comparator is a Bayesian deltaE/E-depth template:

`log p(x|c) = -1/2 sum_j ((z_j - mu_cj)^2 / sigma_cj^2 + log sigma_cj^2)`,

where `z = [log(1+DeltaE), log(1+E_4), log(1+E_full), DeltaE/(DeltaE+E_4), n_hit]`.
The ML panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, a tiny
transformer sequence encoder, and a new `deltae_residual_fusion_new` architecture
that calibrates the physical feature vector together with the traditional
log-likelihood ratio.

## Overall Results

| method                                 |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |   balanced_accuracy |   balanced_accuracy_ci_low |   balanced_accuracy_ci_high |   error_rate |   winner_score |
|:---------------------------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|--------------------:|---------------------------:|----------------------------:|-------------:|---------------:|
| gradient_boosted_trees                 |    0.9999 |           0.9997 |            1      |              0.9999 |                     0.9996 |                      1      |              0.9993 |                     0.9988 |                      0.9996 |       0.0007 |         1.3497 |
| mlp                                    |    0.9998 |           0.9996 |            1      |              0.9997 |                     0.9993 |                      1      |              0.9988 |                     0.9982 |                      0.9994 |       0.0012 |         1.3495 |
| tiny_transformer                       |    0.9999 |           0.9997 |            1      |              0.9998 |                     0.9996 |                      1      |              0.9986 |                     0.998  |                      0.9991 |       0.0014 |         1.3495 |
| 1d_cnn                                 |    0.9998 |           0.9996 |            1      |              0.9996 |                     0.9988 |                      1      |              0.9985 |                     0.9979 |                      0.9991 |       0.0015 |         1.3494 |
| deltae_residual_fusion_new             |    0.9997 |           0.9995 |            0.9999 |              0.9994 |                     0.9985 |                      0.9999 |              0.9982 |                     0.9975 |                      0.9989 |       0.0018 |         1.3492 |
| ridge                                  |    0.9964 |           0.9951 |            0.9976 |              0.9866 |                     0.9811 |                      0.9924 |              0.9846 |                     0.9829 |                      0.9863 |       0.0154 |         1.3399 |
| bayesian_deltae_e_template_traditional |    0.9546 |           0.951  |            0.958  |              0.9134 |                     0.904  |                      0.9215 |              0.8539 |                     0.8492 |                      0.8587 |       0.1461 |         1.2537 |

## Run-Block Stability

| method                                 |   pseudo_run |   roc_auc |   average_precision |   balanced_accuracy |   error_rate |   n_events |   n_deuteron |
|:---------------------------------------|-------------:|----------:|--------------------:|--------------------:|-------------:|-----------:|-------------:|
| 1d_cnn                                 |            0 |    1      |              1      |              1      |       0      |        347 |          170 |
| 1d_cnn                                 |            1 |    1      |              1      |              1      |       0      |        332 |          169 |
| 1d_cnn                                 |            2 |    1      |              1      |              0.9953 |       0.0052 |        388 |          214 |
| 1d_cnn                                 |            3 |    1      |              1      |              1      |       0      |        350 |          164 |
| 1d_cnn                                 |            4 |    1      |              1      |              1      |       0      |        372 |          186 |
| 1d_cnn                                 |            5 |    1      |              1      |              1      |       0      |        326 |          176 |
| 1d_cnn                                 |            6 |    1      |              1      |              1      |       0      |        327 |          165 |
| 1d_cnn                                 |            7 |    1      |              1      |              1      |       0      |        345 |          158 |
| 1d_cnn                                 |            8 |    1      |              1      |              1      |       0      |        335 |          172 |
| 1d_cnn                                 |            9 |    0.994  |              0.9778 |              0.997  |       0.0029 |        341 |          177 |
| 1d_cnn                                 |           10 |    1      |              1      |              0.9971 |       0.003  |        335 |          164 |
| 1d_cnn                                 |           11 |    1      |              1      |              1      |       0      |        349 |          170 |
| 1d_cnn                                 |           12 |    1      |              1      |              1      |       0      |        372 |          190 |
| 1d_cnn                                 |           13 |    0.9994 |              0.9993 |              0.9942 |       0.0058 |        346 |          173 |
| 1d_cnn                                 |           14 |    1      |              1      |              1      |       0      |        359 |          177 |
| 1d_cnn                                 |           15 |    1      |              1      |              1      |       0      |        369 |          188 |
| 1d_cnn                                 |           16 |    1      |              1      |              0.9968 |       0.0031 |        327 |          173 |
| 1d_cnn                                 |           17 |    1      |              1      |              1      |       0      |        343 |          173 |
| 1d_cnn                                 |           18 |    1      |              1      |              1      |       0      |        367 |          184 |
| 1d_cnn                                 |           19 |    1      |              1      |              0.9975 |       0.0029 |        345 |          143 |
| 1d_cnn                                 |           20 |    1      |              1      |              0.9974 |       0.0027 |        377 |          187 |
| 1d_cnn                                 |           21 |    1      |              1      |              1      |       0      |        332 |          154 |
| 1d_cnn                                 |           22 |    1      |              1      |              1      |       0      |        384 |          188 |
| 1d_cnn                                 |           23 |    1      |              1      |              1      |       0      |        340 |          198 |
| 1d_cnn                                 |           24 |    1      |              1      |              1      |       0      |        340 |          170 |
| 1d_cnn                                 |           25 |    1      |              1      |              1      |       0      |        329 |          153 |
| 1d_cnn                                 |           26 |    1      |              1      |              1      |       0      |        313 |          153 |
| 1d_cnn                                 |           27 |    1      |              1      |              0.9944 |       0.0056 |        357 |          177 |
| 1d_cnn                                 |           28 |    0.9998 |              0.9998 |              0.9945 |       0.0057 |        352 |          171 |
| 1d_cnn                                 |           29 |    1      |              1      |              0.9972 |       0.0028 |        351 |          180 |
| 1d_cnn                                 |           30 |    0.9998 |              0.9999 |              0.997  |       0.0028 |        356 |          190 |
| 1d_cnn                                 |           31 |    1      |              1      |              1      |       0      |        388 |          199 |
| 1d_cnn                                 |           32 |    0.9999 |              0.9999 |              0.9945 |       0.0058 |        342 |          161 |
| 1d_cnn                                 |           33 |    1      |              1      |              1      |       0      |        361 |          187 |
| 1d_cnn                                 |           34 |    1      |              1      |              0.997  |       0.0029 |        347 |          181 |
| 1d_cnn                                 |           35 |    1      |              1      |              1      |       0      |        326 |          171 |
| 1d_cnn                                 |           36 |    0.9999 |              0.9999 |              0.9974 |       0.0029 |        347 |          158 |
| 1d_cnn                                 |           37 |    1      |              1      |              0.9974 |       0.0027 |        373 |          179 |
| 1d_cnn                                 |           38 |    1      |              1      |              1      |       0      |        356 |          179 |
| 1d_cnn                                 |           39 |    1      |              1      |              0.9972 |       0.0028 |        354 |          178 |
| bayesian_deltae_e_template_traditional |            0 |    0.9621 |              0.9385 |              0.8607 |       0.1383 |        347 |          170 |
| bayesian_deltae_e_template_traditional |            1 |    0.9578 |              0.9479 |              0.8592 |       0.1416 |        332 |          169 |

## Strata and Systematics

| stratum    | value   | method                                 |   roc_auc |   average_precision |   balanced_accuracy |   error_rate |   n_events |
|:-----------|:--------|:---------------------------------------|----------:|--------------------:|--------------------:|-------------:|-----------:|
| sample     | I       | 1d_cnn                                 |    0.9997 |              1      |              0.9924 |       0.0026 |       3104 |
| sample     | II      | 1d_cnn                                 |    0.9998 |              0.9992 |              0.9989 |       0.0012 |      10896 |
| sample     | I       | bayesian_deltae_e_template_traditional |    0.9765 |              0.992  |              0.959  |       0.0116 |       3104 |
| sample     | II      | bayesian_deltae_e_template_traditional |    0.9402 |              0.8395 |              0.7896 |       0.1844 |      10896 |
| sample     | I       | deltae_residual_fusion_new             |    0.9993 |              0.9999 |              0.9913 |       0.0023 |       3104 |
| sample     | II      | deltae_residual_fusion_new             |    0.9998 |              0.9991 |              0.9986 |       0.0017 |      10896 |
| sample     | I       | gradient_boosted_trees                 |    0.9985 |              0.9998 |              0.994  |       0.0019 |       3104 |
| sample     | II      | gradient_boosted_trees                 |    1      |              0.9999 |              0.9996 |       0.0004 |      10896 |
| sample     | I       | mlp                                    |    0.9995 |              0.9999 |              0.994  |       0.0019 |       3104 |
| sample     | II      | mlp                                    |    0.9999 |              0.9997 |              0.999  |       0.001  |      10896 |
| sample     | I       | ridge                                  |    0.9969 |              0.9985 |              0.9804 |       0.0064 |       3104 |
| sample     | II      | ridge                                  |    0.9961 |              0.9791 |              0.9845 |       0.0179 |      10896 |
| sample     | I       | tiny_transformer                       |    0.9991 |              0.9999 |              0.9928 |       0.0019 |       3104 |
| sample     | II      | tiny_transformer                       |    0.9999 |              0.9998 |              0.9989 |       0.0013 |      10896 |
| deltae_bin | q1      | 1d_cnn                                 |    1      |              0.9998 |              0.9923 |       0.0029 |       3500 |
| deltae_bin | q2      | 1d_cnn                                 |    0.9998 |              0.9894 |              0.9999 |       0.0003 |       3500 |
| deltae_bin | q3      | 1d_cnn                                 |    0.9996 |              0.9999 |              0.9955 |       0.0011 |       3500 |
| deltae_bin | q4      | 1d_cnn                                 |    0.9999 |              1      |              0.9818 |       0.0017 |       3500 |
| deltae_bin | q1      | bayesian_deltae_e_template_traditional |    0.9613 |              0.6777 |              0.9555 |       0.0751 |       3500 |
| deltae_bin | q2      | bayesian_deltae_e_template_traditional |    0.9882 |              0.5873 |              0.9846 |       0.0297 |       3500 |
| deltae_bin | q3      | bayesian_deltae_e_template_traditional |    0.8076 |              0.9544 |              0.6399 |       0.4323 |       3500 |
| deltae_bin | q4      | bayesian_deltae_e_template_traditional |    0.4911 |              0.9301 |              0.5202 |       0.0471 |       3500 |
| deltae_bin | q1      | deltae_residual_fusion_new             |    0.9995 |              0.9951 |              0.9956 |       0.0031 |       3500 |
| deltae_bin | q2      | deltae_residual_fusion_new             |    1      |              0.9999 |              0.9999 |       0.0003 |       3500 |
| deltae_bin | q3      | deltae_residual_fusion_new             |    0.9993 |              0.9999 |              0.9955 |       0.0011 |       3500 |
| deltae_bin | q4      | deltae_residual_fusion_new             |    0.9999 |              1      |              0.9727 |       0.0026 |       3500 |
| deltae_bin | q1      | gradient_boosted_trees                 |    1      |              1      |              0.998  |       0.0006 |       3500 |
| deltae_bin | q2      | gradient_boosted_trees                 |    0.9999 |              0.997  |              0.9999 |       0.0003 |       3500 |
| deltae_bin | q3      | gradient_boosted_trees                 |    0.999  |              0.9998 |              0.9987 |       0.0006 |       3500 |
| deltae_bin | q4      | gradient_boosted_trees                 |    0.9999 |              1      |              0.9877 |       0.0014 |       3500 |
| deltae_bin | q1      | mlp                                    |    1      |              0.9999 |              0.9956 |       0.0017 |       3500 |
| deltae_bin | q2      | mlp                                    |    0.9997 |              0.9783 |              0.9999 |       0.0003 |       3500 |
| deltae_bin | q3      | mlp                                    |    0.9994 |              0.9999 |              0.9966 |       0.0009 |       3500 |
| deltae_bin | q4      | mlp                                    |    1      |              1      |              0.9845 |       0.002  |       3500 |
| deltae_bin | q1      | ridge                                  |    0.9983 |              0.969  |              0.9729 |       0.0097 |       3500 |
| deltae_bin | q2      | ridge                                  |    0.9999 |              0.9966 |              0.9942 |       0.0111 |       3500 |
| deltae_bin | q3      | ridge                                  |    0.9825 |              0.9915 |              0.9442 |       0.0143 |       3500 |
| deltae_bin | q4      | ridge                                  |    0.9346 |              0.9856 |              0.7212 |       0.0263 |       3500 |
| deltae_bin | q1      | tiny_transformer                       |    1      |              0.9999 |              0.9959 |       0.0026 |       3500 |
| deltae_bin | q2      | tiny_transformer                       |    0.9998 |              0.992  |              0.9999 |       0.0003 |       3500 |
| deltae_bin | q3      | tiny_transformer                       |    0.9994 |              0.9999 |              0.9966 |       0.0009 |       3500 |
| deltae_bin | q4      | tiny_transformer                       |    0.9991 |              1      |              0.9788 |       0.002  |       3500 |
| depth_bin  | none    | 1d_cnn                                 |    0.9993 |              0.9999 |              0.9881 |       0.0028 |       5704 |
| depth_bin  | low     | 1d_cnn                                 |    0.9961 |              0.9843 |              0.998  |       0.002  |        490 |
| depth_bin  | mid     | 1d_cnn                                 |    1      |              1      |              0.998  |       0.0021 |       1932 |
| depth_bin  | high    | 1d_cnn                                 |    1      |              1      |              1      |       0      |       5874 |
| depth_bin  | none    | bayesian_deltae_e_template_traditional |    0.6978 |              0.9207 |              0.5    |       0.0978 |       5704 |
| depth_bin  | low     | bayesian_deltae_e_template_traditional |    0.8935 |              0.8287 |              0.8774 |       0.1245 |        490 |
| depth_bin  | mid     | bayesian_deltae_e_template_traditional |    0.9748 |              0.9241 |              0.5952 |       0.4136 |       1932 |
| depth_bin  | high    | bayesian_deltae_e_template_traditional |    0.9984 |              0.9447 |              0.4998 |       0.1067 |       5874 |
| depth_bin  | none    | deltae_residual_fusion_new             |    0.9966 |              0.9992 |              0.9827 |       0.0039 |       5704 |
| depth_bin  | low     | deltae_residual_fusion_new             |    0.9998 |              0.9998 |              0.996  |       0.0041 |        490 |
| depth_bin  | mid     | deltae_residual_fusion_new             |    1      |              1      |              0.9995 |       0.0005 |       1932 |
| depth_bin  | high    | deltae_residual_fusion_new             |    1      |              1      |              1      |       0      |       5874 |
| depth_bin  | none    | gradient_boosted_trees                 |    0.9991 |              0.9999 |              0.9951 |       0.0016 |       5704 |
| depth_bin  | low     | gradient_boosted_trees                 |    0.999  |              0.9989 |              0.998  |       0.002  |        490 |
| depth_bin  | mid     | gradient_boosted_trees                 |    1      |              1      |              1      |       0      |       1932 |
| depth_bin  | high    | gradient_boosted_trees                 |    1      |              1      |              1      |       0      |       5874 |
| depth_bin  | none    | mlp                                    |    0.9993 |              0.9999 |              0.9907 |       0.0025 |       5704 |
| depth_bin  | low     | mlp                                    |    0.9962 |              0.9886 |              0.9959 |       0.0041 |        490 |
| depth_bin  | mid     | mlp                                    |    1      |              1      |              0.9995 |       0.0005 |       1932 |
| depth_bin  | high    | mlp                                    |    1      |              1      |              1      |       0      |       5874 |
| depth_bin  | none    | ridge                                  |    0.9645 |              0.9853 |              0.8859 |       0.0258 |       5704 |
| depth_bin  | low     | ridge                                  |    0.9934 |              0.9819 |              0.9758 |       0.0245 |        490 |
| depth_bin  | mid     | ridge                                  |    0.9959 |              0.9841 |              0.9863 |       0.0135 |       1932 |
| depth_bin  | high    | ridge                                  |    0.9998 |              0.9903 |              0.9964 |       0.0051 |       5874 |
| depth_bin  | none    | tiny_transformer                       |    0.9987 |              0.9998 |              0.9863 |       0.0032 |       5704 |
| depth_bin  | low     | tiny_transformer                       |    0.9981 |              0.9973 |              0.996  |       0.0041 |        490 |
| depth_bin  | mid     | tiny_transformer                       |    1      |              1      |              1      |       0      |       1932 |
| depth_bin  | high    | tiny_transformer                       |    1      |              1      |              1      |       0      |       5874 |

## Caveats

The result does not establish real-data proton/deuteron labels for S54c.  It
establishes that the current mirror lacks the necessary external event-level PID
join and that the simulation-side model panel is technically ready once such a
join appears.  Pseudo-run bootstrap intervals are not a substitute for true DAQ
run transfer.  The GEANT4 table uses energy-deposition features that may be
cleaner than real ADC waveforms, so absolute classifier scores should not be
quoted as real detector PID performance.

## Recommendation

Do not adopt S54c real-data PID boundaries as externally validated.  If a
beamline or detector table with `(run_id, event_id, pid)` becomes available,
rerun the same panel with real runs as groups.  Until then, use
`gradient_boosted_trees` only as the strongest simulation-side architecture candidate.

# G4-08: native GEANT4-to-DAQ event-id bridge audit and run-keyed closure benchmark

## Abstract

Ticket `1783825724.33022.709b07a8` asked for a native event-id bridge or trigger metadata export pairing
GEANT4 digitized windows to DAQ `EVENTNO`/`EVT`/`TRIGGER` keys, followed by a
run-keyed closure benchmark that separates deterministic-overlay alignment uncertainty
from electronics-transfer residuals. The raw ROOT reproduction gate passes exactly:
`640737` selected B-stave pulses versus the reference
`640737`, delta `0`.

The visible inputs do **not** contain a positive native event-id bridge: DAQ ROOT files
contain `EVENTNO`, `EVT`, and `TRIGGER`, but the GEANT4 `hibeam` tree contains no run,
event, EVT, or trigger branch. This report therefore builds the missing bridge contract
as a machine-readable metadata export specification and reruns the closure benchmark
with the strongest currently possible non-deterministic substitute: a run-keyed
GEANT4 pseudo-bridge that samples truth rows only within source-run-matched simulation
blocks rather than assigning exact deterministic event overlays.

The benchmark winner is **`template_residual_boosted_stack_new`** by the predeclared composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy sigma68 `0.07529` with 95% run-block
bootstrap CI [0.06789,
0.08208], timing sigma68
`7.939` ns, and PID balanced accuracy
`0.8612`.

## Raw ROOT reproduction

The gate reads `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`, reshapes `h101/HRDv` to
event-channel-sample tensors, subtracts `b_c=median(x_c[0:4])`, and counts B2/B4/B6/B8
channels satisfying `max_t (x_c(t)-b_c)>1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Native key audit

The DAQ-side reduced ROOT stream exposes the required event-key columns; all non-empty
visible B-stack entries have `TRIGGER=1`. The simulation-side tree does not expose any
DAQ join key. The necessary condition for a native bridge,

`K_DAQ = (run, EVENTNO, EVT, TRIGGER) == K_G4`,

therefore has zero satisfiable fields on the GEANT4 side.

| key     | daq_available   | geant4_available   | native_joinable   | meaning                              |
|:--------|:----------------|:-------------------|:------------------|:-------------------------------------|
| run     | True            | False              | False             | required to split by acquisition run |
| EVENTNO | True            | False              | False             | primary DAQ event counter            |
| EVT     | True            | False              | False             | secondary DAQ event or trigger key   |
| TRIGGER | True            | False              | False             | DAQ trigger metadata                 |

GEANT4 branch inventory summary:

| tree   |   entries |   branch_count | candidate_native_daq_key_branches   | joinable_to_daq_native_keys   |
|:-------|----------:|---------------:|:------------------------------------|:------------------------------|
| hibeam |     30000 |             62 |                                     | False                         |

The metadata export contract written in `future_metadata_export_contract.csv` is the
minimal native bridge that the digitizer should emit in the next production:

| field          | dtype   | required   | description                                        |
|:---------------|:--------|:-----------|:---------------------------------------------------|
| daq_run        | int32   | True       | HRD acquisition run number                         |
| EVENTNO        | int64   | True       | DAQ event counter copied from h101                 |
| EVT            | int64   | True       | DAQ event/trigger key copied from h101             |
| TRIGGER        | int32   | True       | DAQ trigger word before any reduction              |
| g4_entry       | int64   | True       | GEANT4 event index after simulation                |
| digitizer_seed | uint64  | True       | seed linking digitized windows to simulation event |
| bridge_version | string  | True       | schema version for reproducible joins              |

## Run-keyed pseudo-bridge

Because a positive native bridge is impossible with the mounted files, this study
uses a conservative pseudo-bridge. GEANT4 truth rows are partitioned into contiguous
simulation blocks whose labels are mapped one-to-one to source runs. Raw-template
benchmark events from a given source run sample only from the matching GEANT4 block.
This removes exact deterministic event-overlay alignment while retaining run-level
composition constraints. The matched table records `(source_run, g4_pseudo_run, g4_entry)`.

| quantity                                 | value                          |
|:-----------------------------------------|:-------------------------------|
| alignment_policy                         | run_keyed_geant4_pseudo_bridge |
| exact_native_event_matches               | 0                              |
| source_runs                              | 13                             |
| matched_benchmark_events                 | 1396                           |
| unique_geant4_entries_sampled            | 1285                           |
| source_run_equals_g4_pseudo_run_fraction | 1.0                            |

GEANT4 truth summary:

| quantity                       |   value |
|:-------------------------------|--------:|
| usable_geant4_sci_bar_events   | 7101    |
| proton_truth_rows              | 3571    |
| deuteron_truth_rows            | 3485    |
| median_total_edep_mev          |   62    |
| median_energy_weighted_time_ns |   10.57 |

## Methods

The traditional comparator is `deltaE_over_E_likelihood_template`, a bounded
two-pulse template/CFD reconstruction plus diagonal Gaussian PID likelihood. With
standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The required ML/NN panel is ridge, histogram gradient-boosted trees, MLP, and a
compact 1D-CNN. The new architecture is `joint_sequence_transformer`, and the
ticket also retains `template_residual_boosted_stack_new`, a physics-residual
stack that learns corrections to the traditional template output.

For event `i`, the GEANT4 energy target is

`E_i = sum_h EDep_ih`,

the timing target is

`t_i = (sum_h EDep_ih t_ih) / (sum_h EDep_ih)`,

and the reported robust residual widths are

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

All scalers, templates, likelihood moments, and models are trained only on train
runs `[50, 51, 52, 53, 54, 55, 56, 57]` and evaluated on held-out runs
`[58, 60, 62, 64, 65]`. Confidence intervals are percentile intervals
over `320` held-out run-block bootstrap resamples.
Run id, DAQ event keys, and GEANT4 entry number are excluded from model features.

Train-only template summaries:

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              672 |                   2.685 |                      5 |           9.195 |
| B4      |              672 |                   3.014 |                      6 |          10.69  |
| B6      |              639 |                   3.709 |                      6 |           9.698 |
| B8      |              464 |                   4.235 |                      8 |           9.261 |

## Overall held-out results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new |         0.217  |    0.9076 |                  0.8612 |           0.9224 |       0.8262 |                     0.07529 |                            0.06789 |                             0.08208 |             7.939 |                    6.819 |                     9.065 |             0.303  |             0.2485 |
| gradient_boosted_trees              |         0.2254 |    0.9172 |                  0.8631 |           0.8985 |       0.8431 |                     0.08527 |                            0.07714 |                             0.08864 |             7.985 |                    7.256 |                     9.163 |             0.2697 |             0.2515 |
| ridge                               |         0.2799 |    0.8002 |                  0.7069 |           0.6507 |       0.739  |                     0.07904 |                            0.06125 |                             0.09441 |             9.927 |                    8.915 |                    11.62  |             0.3121 |             0.2545 |
| deltaE_over_E_likelihood_template   |         0.2885 |    0.8136 |                  0.7905 |           0.8149 |       0.7822 |                     0.07801 |                            0.06754 |                             0.1024  |            12.18  |                   10.04  |                    12.99  |             0.6091 |             0.1182 |
| 1d_cnn                              |         0.3151 |    0.7286 |                  0.677  |           0.6925 |       0.6784 |                     0.09591 |                            0.08358 |                             0.1195  |            10.95  |                   10.01  |                    12.19  |             0.3485 |             0.2303 |
| mlp                                 |         0.3563 |    0.8317 |                  0.7772 |           0.7791 |       0.7814 |                     0.1486  |                            0.127   |                             0.169   |            12.38  |                   11.2   |                    13.15  |             0.3576 |             0.2061 |
| joint_sequence_transformer          |         0.3915 |    0.4895 |                  0.4946 |           0.5522 |       0.5027 |                     0.1021  |                            0.09324 |                             0.115   |            13.45  |                   11.77  |                    14.09  |             0.3455 |             0.2273 |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes energy sigma68 by
`-0.002721`,
timing sigma68 by `-4.239` ns,
and PID balanced accuracy by `0.07065`.

## Run-held-out stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.6364 |           0.6212 |       0.6406 |                     0.07985 |             9.889 |             0.3182 |            0.2576  |
| 1d_cnn                              |            60 |                  0.7462 |           0.6711 |       0.8361 |                     0.125   |            12.81  |             0.3636 |            0.303   |
| 1d_cnn                              |            62 |                  0.6691 |           0.7097 |       0.6286 |                     0.1195  |            11.09  |             0.2273 |            0.1818  |
| 1d_cnn                              |            64 |                  0.6647 |           0.7581 |       0.6104 |                     0.09122 |             9.427 |             0.3485 |            0.1364  |
| 1d_cnn                              |            65 |                  0.6884 |           0.7101 |       0.7    |                     0.06857 |            10.79  |             0.4848 |            0.2727  |
| deltaE_over_E_likelihood_template   |            58 |                  0.75   |           0.7121 |       0.7705 |                     0.05721 |            13.35  |             0.5758 |            0.2273  |
| deltaE_over_E_likelihood_template   |            60 |                  0.8163 |           0.8289 |       0.8514 |                     0.07406 |            13.52  |             0.6061 |            0.1364  |
| deltaE_over_E_likelihood_template   |            62 |                  0.7666 |           0.7903 |       0.7313 |                     0.1162  |            12.02  |             0.5758 |            0.06061 |
| deltaE_over_E_likelihood_template   |            64 |                  0.8088 |           0.9032 |       0.7368 |                     0.06914 |             9.521 |             0.6212 |            0.06061 |
| deltaE_over_E_likelihood_template   |            65 |                  0.8171 |           0.8406 |       0.8169 |                     0.09078 |             9.915 |             0.6667 |            0.1061  |
| gradient_boosted_trees              |            58 |                  0.8939 |           0.9091 |       0.8824 |                     0.08905 |             7.064 |             0.2576 |            0.303   |
| gradient_boosted_trees              |            60 |                  0.8825 |           0.9079 |       0.8961 |                     0.08342 |             9.428 |             0.2576 |            0.2727  |
| gradient_boosted_trees              |            62 |                  0.8641 |           0.871  |       0.8438 |                     0.08868 |             9.118 |             0.2424 |            0.197   |
| gradient_boosted_trees              |            64 |                  0.823  |           0.9032 |       0.7568 |                     0.08348 |             7.724 |             0.2576 |            0.1818  |
| gradient_boosted_trees              |            65 |                  0.854  |           0.8986 |       0.8378 |                     0.0652  |             7.43  |             0.3333 |            0.303   |
| joint_sequence_transformer          |            58 |                  0.4924 |           0.5606 |       0.4933 |                     0.08373 |            12.95  |             0.3333 |            0.3182  |
| joint_sequence_transformer          |            60 |                  0.4883 |           0.5658 |       0.5658 |                     0.09577 |            14.84  |             0.3636 |            0.2121  |
| joint_sequence_transformer          |            62 |                  0.4751 |           0.5645 |       0.4487 |                     0.1232  |            14.16  |             0.2727 |            0.1818  |
| joint_sequence_transformer          |            64 |                  0.5099 |           0.5484 |       0.4789 |                     0.1075  |            11.65  |             0.303  |            0.1364  |
| joint_sequence_transformer          |            65 |                  0.5069 |           0.5217 |       0.5294 |                     0.08626 |            11.68  |             0.4545 |            0.2879  |
| mlp                                 |            58 |                  0.75   |           0.7273 |       0.7619 |                     0.1632  |            10.7   |             0.2727 |            0.2879  |
| mlp                                 |            60 |                  0.8163 |           0.8289 |       0.8514 |                     0.1778  |            12.48  |             0.3182 |            0.2879  |
| mlp                                 |            62 |                  0.7638 |           0.7419 |       0.7541 |                     0.1371  |            13.81  |             0.303  |            0.1364  |
| mlp                                 |            64 |                  0.7756 |           0.8226 |       0.7286 |                     0.1138  |            11.26  |             0.4697 |            0.04545 |
| mlp                                 |            65 |                  0.7809 |           0.7681 |       0.803  |                     0.1373  |            10.76  |             0.4242 |            0.2727  |
| ridge                               |            58 |                  0.6061 |           0.5    |       0.6346 |                     0.06222 |             9.213 |             0.2879 |            0.2727  |
| ridge                               |            60 |                  0.7505 |           0.6974 |       0.8281 |                     0.1009  |            12.63  |             0.3182 |            0.3636  |
| ridge                               |            62 |                  0.7235 |           0.6613 |       0.7321 |                     0.09132 |            10.78  |             0.2727 |            0.1364  |
| ridge                               |            64 |                  0.7514 |           0.7742 |       0.7164 |                     0.06789 |             8.241 |             0.3636 |            0.1818  |
| ridge                               |            65 |                  0.7084 |           0.6232 |       0.7679 |                     0.05543 |             9.483 |             0.3182 |            0.3182  |
| template_residual_boosted_stack_new |            58 |                  0.8561 |           0.9091 |       0.8219 |                     0.06263 |             6.97  |             0.3182 |            0.303   |
| template_residual_boosted_stack_new |            60 |                  0.8933 |           0.9474 |       0.8889 |                     0.08448 |             9.514 |             0.2879 |            0.2879  |
| template_residual_boosted_stack_new |            62 |                  0.8426 |           0.871  |       0.806  |                     0.07343 |             9.492 |             0.2576 |            0.197   |
| template_residual_boosted_stack_new |            64 |                  0.8472 |           0.9516 |       0.7662 |                     0.06422 |             7.242 |             0.3182 |            0.1667  |
| template_residual_boosted_stack_new |            65 |                  0.8685 |           0.9275 |       0.8421 |                     0.06522 |             6.732 |             0.3333 |            0.2879  |

## Strata and systematics

| stratum     | value                  | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:------------|:-----------------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|
| spacing_bin | (-0.001, 10.0]         | 1d_cnn                              |                  0.698  |                     0.0822  |            10.62  |             0.4851 |
| spacing_bin | (10.0, 25.0]           | 1d_cnn                              |                  0.705  |                     0.07798 |             7.44  |             0.4769 |
| spacing_bin | (25.0, 45.0]           | 1d_cnn                              |                  0.7049 |                     0.09782 |             9.595 |             0.2045 |
| spacing_bin | (45.0, 70.0]           | 1d_cnn                              |                  0.7138 |                     0.1045  |            14.12  |             0.2237 |
| spacing_bin | (-0.001, 10.0]         | deltaE_over_E_likelihood_template   |                  0.8441 |                     0.07667 |            16     |             0.703  |
| spacing_bin | (10.0, 25.0]           | deltaE_over_E_likelihood_template   |                  0.8375 |                     0.1017  |            16.15  |             0.6769 |
| spacing_bin | (25.0, 45.0]           | deltaE_over_E_likelihood_template   |                  0.715  |                     0.06283 |            11.26  |             0.5682 |
| spacing_bin | (45.0, 70.0]           | deltaE_over_E_likelihood_template   |                  0.7786 |                     0.1039  |            10.12  |             0.4737 |
| spacing_bin | (-0.001, 10.0]         | gradient_boosted_trees              |                  0.8983 |                     0.05305 |             7.947 |             0.3861 |
| spacing_bin | (10.0, 25.0]           | gradient_boosted_trees              |                  0.85   |                     0.07869 |             7.183 |             0.2615 |
| spacing_bin | (25.0, 45.0]           | gradient_boosted_trees              |                  0.8176 |                     0.07858 |             8.439 |             0.2045 |
| spacing_bin | (45.0, 70.0]           | gradient_boosted_trees              |                  0.9082 |                     0.08806 |             9.426 |             0.1974 |
| spacing_bin | (-0.001, 10.0]         | joint_sequence_transformer          |                  0.4775 |                     0.1005  |            12.4   |             0.4653 |
| spacing_bin | (10.0, 25.0]           | joint_sequence_transformer          |                  0.42   |                     0.08119 |             8.247 |             0.4    |
| spacing_bin | (25.0, 45.0]           | joint_sequence_transformer          |                  0.5452 |                     0.09809 |            11.65  |             0.2159 |
| spacing_bin | (45.0, 70.0]           | joint_sequence_transformer          |                  0.5738 |                     0.09341 |            15.16  |             0.2895 |
| spacing_bin | (-0.001, 10.0]         | mlp                                 |                  0.8441 |                     0.1413  |            10.53  |             0.495  |
| spacing_bin | (10.0, 25.0]           | mlp                                 |                  0.825  |                     0.1509  |            11.71  |             0.4154 |
| spacing_bin | (25.0, 45.0]           | mlp                                 |                  0.6928 |                     0.1786  |            12.83  |             0.2727 |
| spacing_bin | (45.0, 70.0]           | mlp                                 |                  0.7394 |                     0.1375  |            13.79  |             0.2237 |
| spacing_bin | (-0.001, 10.0]         | ridge                               |                  0.7584 |                     0.07441 |            10.65  |             0.4356 |
| spacing_bin | (10.0, 25.0]           | ridge                               |                  0.755  |                     0.07229 |             8.434 |             0.3846 |
| spacing_bin | (25.0, 45.0]           | ridge                               |                  0.6372 |                     0.06896 |             7.973 |             0.1932 |
| spacing_bin | (45.0, 70.0]           | ridge                               |                  0.7131 |                     0.08392 |            12.16  |             0.2237 |
| spacing_bin | (-0.001, 10.0]         | template_residual_boosted_stack_new |                  0.8896 |                     0.05868 |             7.177 |             0.4059 |
| spacing_bin | (10.0, 25.0]           | template_residual_boosted_stack_new |                  0.8825 |                     0.06159 |             6.128 |             0.3692 |
| spacing_bin | (25.0, 45.0]           | template_residual_boosted_stack_new |                  0.8054 |                     0.06729 |             8.407 |             0.2386 |
| spacing_bin | (45.0, 70.0]           | template_residual_boosted_stack_new |                  0.9473 |                     0.1269  |             9.692 |             0.1842 |
| energy_bin  | (856.011, 13155.664]   | 1d_cnn                              |                  0.662  |                     0.08075 |            11.05  |             0.2941 |
| energy_bin  | (13155.664, 15539.875] | 1d_cnn                              |                  0.7177 |                     0.09247 |            10.96  |             0.4118 |
| energy_bin  | (15539.875, 16000.0]   | 1d_cnn                              |                  0.6456 |                     0.1202  |            10.89  |             0.3438 |
| energy_bin  | (856.011, 13155.664]   | deltaE_over_E_likelihood_template   |                  0.8131 |                     0.07457 |             7.461 |             0.5294 |
| energy_bin  | (13155.664, 15539.875] | deltaE_over_E_likelihood_template   |                  0.9155 |                     0.09925 |            14.49  |             0.6588 |
| energy_bin  | (15539.875, 16000.0]   | deltaE_over_E_likelihood_template   |                  0.7    |                     0.0763  |            12.54  |             0.625  |
| energy_bin  | (856.011, 13155.664]   | gradient_boosted_trees              |                  0.8419 |                     0.08629 |             7.502 |             0.3529 |
| energy_bin  | (13155.664, 15539.875] | gradient_boosted_trees              |                  0.977  |                     0.07593 |             8.191 |             0.2471 |
| energy_bin  | (15539.875, 16000.0]   | gradient_boosted_trees              |                  0.8122 |                     0.08157 |             7.934 |             0.2375 |
| energy_bin  | (856.011, 13155.664]   | joint_sequence_transformer          |                  0.5026 |                     0.1026  |            12.63  |             0.2941 |
| energy_bin  | (13155.664, 15539.875] | joint_sequence_transformer          |                  0.4821 |                     0.09554 |            14.41  |             0.3529 |
| energy_bin  | (15539.875, 16000.0]   | joint_sequence_transformer          |                  0.4967 |                     0.11    |            12.58  |             0.3688 |
| energy_bin  | (856.011, 13155.664]   | mlp                                 |                  0.8545 |                     0.1469  |            11.26  |             0.4471 |
| energy_bin  | (13155.664, 15539.875] | mlp                                 |                  0.8045 |                     0.1436  |            11.39  |             0.3765 |
| energy_bin  | (15539.875, 16000.0]   | mlp                                 |                  0.7028 |                     0.1343  |            12.44  |             0.3    |
| energy_bin  | (856.011, 13155.664]   | ridge                               |                  0.8291 |                     0.07383 |             9.6   |             0.4    |
| energy_bin  | (13155.664, 15539.875] | ridge                               |                  0.7817 |                     0.07294 |             9.686 |             0.3294 |
| energy_bin  | (15539.875, 16000.0]   | ridge                               |                  0.5928 |                     0.1064  |             9.915 |             0.2562 |
| energy_bin  | (856.011, 13155.664]   | template_residual_boosted_stack_new |                  0.8417 |                     0.0753  |             6.679 |             0.3412 |
| energy_bin  | (13155.664, 15539.875] | template_residual_boosted_stack_new |                  0.97   |                     0.06781 |             7.863 |             0.3176 |
| energy_bin  | (15539.875, 16000.0]   | template_residual_boosted_stack_new |                  0.8078 |                     0.07562 |             8.568 |             0.275  |
| stave       | B2                     | 1d_cnn                              |                  0.7056 |                     0.07339 |            10.82  |             0.5    |
| stave       | B4                     | 1d_cnn                              |                  0.6735 |                     0.1529  |            10.59  |             0.4328 |
| stave       | B6                     | 1d_cnn                              |                  0.6151 |                     0.1445  |             8.973 |             0.2963 |
| stave       | B8                     | 1d_cnn                              |                  0.7163 |                     0.08475 |             9.328 |             0.1548 |
| stave       | B2                     | deltaE_over_E_likelihood_template   |                  0.7794 |                     0.06758 |            15.64  |             0.6735 |
| stave       | B4                     | deltaE_over_E_likelihood_template   |                  0.8187 |                     0.06713 |            18.6   |             0.8657 |
| stave       | B6                     | deltaE_over_E_likelihood_template   |                  0.8086 |                     0.09838 |             8.878 |             0.5309 |
| stave       | B8                     | deltaE_over_E_likelihood_template   |                  0.7595 |                     0.06796 |             6.715 |             0.4048 |
| stave       | B2                     | gradient_boosted_trees              |                  0.865  |                     0.06583 |             8.87  |             0.3469 |
| stave       | B4                     | gradient_boosted_trees              |                  0.8691 |                     0.08796 |             7.001 |             0.2687 |
| stave       | B6                     | gradient_boosted_trees              |                  0.8474 |                     0.1098  |             6.966 |             0.2963 |
| stave       | B8                     | gradient_boosted_trees              |                  0.8715 |                     0.07221 |             7.859 |             0.1548 |
| stave       | B2                     | joint_sequence_transformer          |                  0.5161 |                     0.08521 |            11.69  |             0.4898 |
| stave       | B4                     | joint_sequence_transformer          |                  0.4754 |                     0.1327  |            15.18  |             0.3881 |
| stave       | B6                     | joint_sequence_transformer          |                  0.5737 |                     0.1337  |            12.73  |             0.321  |
| stave       | B8                     | joint_sequence_transformer          |                  0.4244 |                     0.1018  |            11.95  |             0.1667 |
| stave       | B2                     | mlp                                 |                  0.785  |                     0.175   |            15.68  |             0.4592 |
| stave       | B4                     | mlp                                 |                  0.7721 |                     0.1773  |            13.27  |             0.3582 |
| stave       | B6                     | mlp                                 |                  0.7562 |                     0.1255  |             9.214 |             0.3333 |
| stave       | B8                     | mlp                                 |                  0.7941 |                     0.1269  |             9.491 |             0.2619 |
| stave       | B2                     | ridge                               |                  0.7072 |                     0.07652 |             9.532 |             0.398  |
| stave       | B4                     | ridge                               |                  0.7346 |                     0.07704 |             9.6   |             0.2388 |
| stave       | B6                     | ridge                               |                  0.6845 |                     0.1089  |             9.815 |             0.3457 |
| stave       | B8                     | ridge                               |                  0.7025 |                     0.07941 |             7.82  |             0.2381 |
| stave       | B2                     | template_residual_boosted_stack_new |                  0.8711 |                     0.06418 |             9.286 |             0.398  |
| stave       | B4                     | template_residual_boosted_stack_new |                  0.868  |                     0.08227 |             6.3   |             0.2985 |
| stave       | B6                     | template_residual_boosted_stack_new |                  0.8549 |                     0.1172  |             6.583 |             0.2963 |
| stave       | B8                     | template_residual_boosted_stack_new |                  0.8512 |                     0.06574 |             7.359 |             0.2024 |
| pid_truth   | deuteron_like          | 1d_cnn                              |                  0.6925 |                     0.09853 |            10.55  |             0.3512 |
| pid_truth   | proton_like            | 1d_cnn                              |                  0.6615 |                     0.0858  |            11.61  |             0.3457 |
| pid_truth   | deuteron_like          | deltaE_over_E_likelihood_template   |                  0.8149 |                     0.07138 |            11.27  |             0.5952 |
| pid_truth   | proton_like            | deltaE_over_E_likelihood_template   |                  0.7662 |                     0.09455 |            13.16  |             0.6235 |
| pid_truth   | deuteron_like          | gradient_boosted_trees              |                  0.8985 |                     0.08353 |             7.602 |             0.2619 |
| pid_truth   | proton_like            | gradient_boosted_trees              |                  0.8277 |                     0.0759  |             8.391 |             0.2778 |
| pid_truth   | deuteron_like          | joint_sequence_transformer          |                  0.5522 |                     0.1212  |            12.82  |             0.369  |
| pid_truth   | proton_like            | joint_sequence_transformer          |                  0.4369 |                     0.09032 |            13.85  |             0.321  |
| pid_truth   | deuteron_like          | mlp                                 |                  0.7791 |                     0.1549  |            11.08  |             0.3571 |
| pid_truth   | proton_like            | mlp                                 |                  0.7754 |                     0.142   |            12.75  |             0.358  |
| pid_truth   | deuteron_like          | ridge                               |                  0.6507 |                     0.07207 |             9.679 |             0.2857 |
| pid_truth   | proton_like            | ridge                               |                  0.7631 |                     0.08119 |            10.21  |             0.3395 |
| pid_truth   | deuteron_like          | template_residual_boosted_stack_new |                  0.9224 |                     0.07941 |             7.733 |             0.2917 |
| pid_truth   | proton_like            | template_residual_boosted_stack_new |                  0.8    |                     0.06743 |             8.147 |             0.3148 |

Dominant systematics:

- Native bridge absence is a provenance limitation, not a modeling failure. The
  current GEANT4 file cannot prove event-by-event DAQ alignment.
- The run-keyed pseudo-bridge quantifies electronics-transfer residuals under
  run-composition constraints but still contains within-run GEANT4 assignment
  uncertainty.
- ADC/MeV conversion is fixed for ranking and should not be interpreted as an
  external energy calibration.
- Bootstrap CIs cover held-out run variation, not GEANT4 physics-list, material,
  light-yield, or trigger-emulation uncertainty.
- A future positive bridge must persist `daq_run`, `EVENTNO`, `EVT`, `TRIGGER`,
  `g4_entry`, `digitizer_seed`, and `bridge_version` before digitization.

## Conclusion

G4-08 is a negative native-bridge result with a concrete export path. The visible
DAQ ROOT files provide the needed event keys, but the visible GEANT4 ROOT file does
not. The report therefore writes a bridge contract and reruns the benchmark using
the best available non-deterministic run-keyed pseudo-bridge. Under that design,
`template_residual_boosted_stack_new` is the named winner in `result.json`; the residuals should be interpreted
as run-keyed electronics-transfer performance plus remaining within-run alignment
uncertainty, not as a completed event-by-event GEANT4-to-DAQ closure.

Runtime was `73.1` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

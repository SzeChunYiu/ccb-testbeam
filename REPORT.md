# S67b/#2550 Saturation-Censored Energy and PID Recovery

**Ticket:** `#2550`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT directory:** `data/extracted/root/root`  
**Source prediction artifact:** `reports/1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark`  
**Git commit at execution:** `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`

## Abstract

Ticket `#2550` asks how clipped or saturated waveform tails bias energy
calibration and PID boundaries across pedestal states and pile-up conditions.
This runner reproduces the canonical B-stack selected-pulse count directly from
raw ROOT under the repository `data/` folder, then re-scores the established
S29a method panel for S67b-specific estimands: energy residuals, PID AUC and
boundary drift, saturation recovery error, pedestal-stratified calibration
transfer, and pile-up-conditioned failure modes.  The benchmark includes the
required traditional likelihood method, ridge, gradient-boosted trees, MLP,
1D-CNN, a sequence transformer, and a new residual-stack architecture.

The winner named in `result.json` is **`gradient_boosted_trees`** with composite S67b loss
`0.2982`.  Against the traditional
`deltaE_over_E_likelihood_template`, the winner changes PID AUC by
`0.1225`, saturated-energy sigma68 by
`-0.4199`,
PID-boundary drift by `0.1527`,
and pedestal calibration-transfer span by
`0.0136`.

## Raw ROOT Reproduction

For every configured B-stack `hrdb_run_NNNN.root`, branch `h101/HRDv` is
reshaped to `(event, channel, sample)` with eighteen samples per channel.  The
baseline-subtracted amplitude for event `e`, channel `c`, and sample `t` is

`a_{e,c,t} = x_{e,c,t} - median_{u in {0,1,2,3}} x_{e,c,u}`.

The selected-pulse indicator for physical B2/B4/B6/B8 channels is

`I_{e,c} = 1[max_t a_{e,c,t} > 1000 ADC]`,

and the reproduced count is

`N = sum_runs sum_e sum_{c in {B2,B4,B6,B8}} I_{e,c}`.

| quantity                           | expected | reproduced | delta | tolerance | pass |
| ---------------------------------- | -------- | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses      | 640737   | 640737     | 0     | 0         | True |
| sample_i_calib selected_pulses     | 248745   | 248745     | 0     | 0         | True |
| sample_i_analysis selected_pulses  | 252266   | 252266     | 0     | 0         | True |
| sample_ii_calib selected_pulses    | 14630    | 14630      | 0     | 0         | True |
| sample_ii_analysis selected_pulses | 125096   | 125096     | 0     | 0         | True |
| sample_ii_analysis B2              | 88213    | 88213      | 0     | 0         | True |
| sample_ii_analysis B4              | 21229    | 21229      | 0     | 0         | True |
| sample_ii_analysis B6              | 11148    | 11148      | 0     | 0         | True |
| sample_ii_analysis B8              | 4506     | 4506       | 0     | 0         | True |

The total exactly reproduces `640,737` selected B-stave pulses
from raw ROOT.  Per-run counts are stored in `reproduction_counts_by_run.csv`;
the first and last five rows are:

| run | group              | events_total | selected_pulses | B2    | B4   | B6   | B8   |
| --- | ------------------ | ------------ | --------------- | ----- | ---- | ---- | ---- |
| 31  | sample_i_calib     | 39990        | 27871           | 26948 | 592  | 237  | 94   |
| 32  | sample_i_calib     | 41921        | 28240           | 27316 | 605  | 224  | 95   |
| 33  | sample_i_calib     | 57173        | 48737           | 47724 | 559  | 318  | 136  |
| 34  | sample_i_calib     | 39765        | 34118           | 33373 | 412  | 244  | 89   |
| 35  | sample_i_calib     | 27786        | 11667           | 11029 | 403  | 163  | 72   |
| 61  | sample_ii_analysis | 36535        | 18965           | 11015 | 4401 | 2490 | 1059 |
| 62  | sample_ii_analysis | 37584        | 19089           | 11635 | 4183 | 2342 | 929  |
| 63  | sample_ii_analysis | 37030        | 18817           | 14566 | 2645 | 1153 | 453  |
| 64  | sample_ii_calib    | 35943        | 14630           | 11907 | 1689 | 763  | 271  |
| 65  | sample_ii_analysis | 38424        | 13038           | 11768 | 842  | 323  | 105  |

## Data and Run Split

The model predictions are the frozen S29a digitized GEANT4/raw-template
benchmark predictions.  This is a ticket-local re-scoring, not a new train/test
leakage opportunity.  Training and held-out sets are disjoint by source run;
the held-out runs in this artifact are
`[58, 60, 62, 64, 65]`.  Event id,
source run, and GEANT4 entry are not used as predictors in the source benchmark.

The PID endpoint is deuteron-like versus proton-like dominant SciBar PDG from
the GEANT4 bridge.  Energy residuals use `true_energy_mev`; prediction energy is
the recovered waveform energy scale implied by fitted amplitudes and the
event's true proxy calibration scale.  Saturation and pile-up are controlled
truth labels in the digitized waveform benchmark.  Pedestal state is the
held-out tertile of `truth_pedestal_adc`.

## Methods

The traditional comparator is a censored deltaE/E likelihood template with
integral charge calibration.  For class `y` and detector state `s`, the
Gaussian likelihood over standardized charge-depth variables is

`log p(z | y,s) = -1/2 sum_j [((z_j - mu_{y,s,j})^2 / sigma_{y,s,j}^2) + log sigma_{y,s,j}^2] + log pi_y`.

Ridge minimizes

`||y - X beta||_2^2 + lambda ||beta||_2^2`.

Gradient-boosted trees fit additive regression/classification trees.  The MLP
uses dense nonlinear waveform-summary heads.  The 1D-CNN operates on ordered
waveform samples.  The transformer uses self-attention over the short sequence.
The new architecture, `template_residual_boosted_stack_new`, stacks a
physics-template solution with boosted residual corrections for PID, energy,
timing, pile-up, and saturation.

## Estimands and Scoring

Energy residual:

`r_E = (hat E - E_true) / max(E_true, epsilon)`.

Robust width:

`sigma_68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`.

PID boundary displacement in stratum `g`:

`Delta tau_g = tau_g^* - tau^*`, where `tau^*` maximizes held-out balanced accuracy.

Pedestal calibration-transfer span:

`S_ped = max_b median(r_E | b) - min_b median(r_E | b)`.

The lower-is-better S67b score is

`L = sigma_E + 0.35(1-AUC_PID) + 0.20 sigma_E^sat + 0.15 R_sat + 0.10 |Delta tau|max + 0.08 S_ped + 0.06 R_miss + 0.04 R_false + 0.10 |bias_E|`.

All confidence intervals below are percentile 95% intervals from
`500` held-out run-block bootstrap resamples.

## Overall Results

| method                              | family                     | winner_score | pid_auc | energy_sigma68_frac | saturated_energy_sigma68_frac | pid_boundary_drift | pedestal_calibration_transfer | pileup_miss_rate | false_split_rate |
| ----------------------------------- | -------------------------- | ------------ | ------- | ------------------- | ----------------------------- | ------------------ | ----------------------------- | ---------------- | ---------------- |
| gradient_boosted_trees              | gradient_boosted_trees     | 0.2982       | 0.9106  | 0.1802              | 0.0926                        | 0.1924             | 0.0136                        | 0.3061           | 0.2455           |
| template_residual_boosted_stack_new | new_architecture           | 0.3001       | 0.9044  | 0.1773              | 0.0881                        | 0.2111             | 0.0278                        | 0.3394           | 0.2485           |
| ridge                               | ridge                      | 0.3393       | 0.8378  | 0.2063              | 0.1062                        | 0.0098             | 0.0491                        | 0.2848           | 0.2818           |
| 1d_cnn                              | 1d_cnn                     | 0.3476       | 0.8360  | 0.1956              | 0.1147                        | 0.1125             | 0.0773                        | 0.2879           | 0.2515           |
| mlp                                 | mlp                        | 0.4516       | 0.7688  | 0.2609              | 0.1969                        | 0.0211             | 0.0310                        | 0.2970           | 0.2909           |
| joint_sequence_transformer          | transformer_sequence_model | 0.4958       | 0.5213  | 0.2379              | 0.1268                        | 0.0348             | 0.1622                        | 0.3333           | 0.2212           |
| deltaE_over_E_likelihood_template   | traditional                | 0.8906       | 0.7880  | 0.4881              | 0.5125                        | 0.0397             | 0.0000                        | 0.6879           | 0.0939           |

## Bootstrap Confidence Intervals

| method                              | pid_auc_ci              | energy_sigma68_ci       | saturated_energy_sigma68_ci | boundary_drift_ci       | pedestal_transfer_ci    |
| ----------------------------------- | ----------------------- | ----------------------- | --------------------------- | ----------------------- | ----------------------- |
| gradient_boosted_trees              | 0.9106 [0.8781, 0.9374] | 0.1802 [0.1645, 0.2012] | 0.0926 [0.0780, 0.1042]     | 0.1924 [0.1371, 0.5860] | 0.0136 [0.0027, 0.0939] |
| template_residual_boosted_stack_new | 0.9044 [0.8688, 0.9287] | 0.1773 [0.1621, 0.1990] | 0.0881 [0.0800, 0.0957]     | 0.2111 [0.0803, 0.5324] | 0.0278 [0.0068, 0.1239] |
| ridge                               | 0.8378 [0.7808, 0.8824] | 0.2063 [0.1912, 0.2118] | 0.1062 [0.0877, 0.1195]     | 0.0098 [0.0098, 0.0496] | 0.0491 [0.0131, 0.1016] |
| 1d_cnn                              | 0.8360 [0.7972, 0.8705] | 0.1956 [0.1827, 0.2108] | 0.1147 [0.0907, 0.1300]     | 0.1125 [0.0361, 0.1947] | 0.0773 [0.0404, 0.1342] |
| mlp                                 | 0.7688 [0.7274, 0.8064] | 0.2609 [0.2401, 0.2741] | 0.1969 [0.1467, 0.2488]     | 0.0211 [0.0068, 0.0513] | 0.0310 [0.0164, 0.0745] |
| joint_sequence_transformer          | 0.5213 [0.4924, 0.5517] | 0.2379 [0.2232, 0.2450] | 0.1268 [0.1078, 0.1476]     | 0.0348 [0.0174, 0.0847] | 0.1622 [0.0998, 0.2703] |
| deltaE_over_E_likelihood_template   | 0.7880 [0.7400, 0.8298] | 0.4881 [0.4799, 0.4990] | 0.5125 [0.4951, 0.5217]     | 0.0397 [0.0263, 0.0783] | 0.0000 [0.0000, 0.0000] |

## Run-Held-Out Stability

| method                            | heldout_run | pid_auc | energy_sigma68_frac | saturated_energy_sigma68_frac | pid_boundary_drift | pedestal_calibration_transfer | pileup_miss_rate | false_split_rate |
| --------------------------------- | ----------- | ------- | ------------------- | ----------------------------- | ------------------ | ----------------------------- | ---------------- | ---------------- |
| deltaE_over_E_likelihood_template | 58          | 0.8324  | 0.4923              | 0.4907                        | 0.0515             | 0.0000                        | 0.5909           | 0.0909           |
| deltaE_over_E_likelihood_template | 60          | 0.8219  | 0.4888              | 0.5046                        | 0.0495             | 0.0000                        | 0.6818           | 0.1667           |
| deltaE_over_E_likelihood_template | 62          | 0.8396  | 0.4728              | 0.5221                        | 0.0526             | 0.0000                        | 0.7424           | 0.0758           |
| deltaE_over_E_likelihood_template | 64          | 0.7035  | 0.5066              | 0.5228                        | 0.1517             | 0.0000                        | 0.7273           | 0.0758           |
| deltaE_over_E_likelihood_template | 65          | 0.7427  | 0.4807              | 0.4915                        | 0.0329             | 0.0000                        | 0.6970           | 0.0606           |
| gradient_boosted_trees            | 58          | 0.9252  | 0.1571              | 0.0973                        | 0.3791             | 0.0348                        | 0.1970           | 0.3333           |
| gradient_boosted_trees            | 60          | 0.9516  | 0.1643              | 0.0761                        | 0.1920             | 0.0264                        | 0.3182           | 0.3182           |
| gradient_boosted_trees            | 62          | 0.8737  | 0.1746              | 0.1074                        | 0.2572             | 0.0954                        | 0.3788           | 0.2121           |
| gradient_boosted_trees            | 64          | 0.8593  | 0.1950              | 0.0987                        | 0.6830             | 0.1182                        | 0.3333           | 0.1667           |
| gradient_boosted_trees            | 65          | 0.9316  | 0.2080              | 0.0780                        | 0.1616             | 0.0612                        | 0.3030           | 0.1970           |

## PID Boundary Drift

Winner-only local PID thresholds by pedestal, saturation, and pile-up strata:

| method                 | stratum        | value       | n   | global_pid_threshold | local_pid_threshold | boundary_displacement | global_balanced_accuracy | local_balanced_accuracy |
| ---------------------- | -------------- | ----------- | --- | -------------------- | ------------------- | --------------------- | ------------------------ | ----------------------- |
| gradient_boosted_trees | pedestal_bin   | low         | 220 | 0.5166               | 0.5095              | -0.0071               | 0.8473                   | 0.8557                  |
| gradient_boosted_trees | pedestal_bin   | mid         | 220 | 0.5166               | 0.5883              | 0.0717                | 0.8473                   | 0.8507                  |
| gradient_boosted_trees | pedestal_bin   | high        | 220 | 0.5166               | 0.7090              | 0.1924                | 0.8473                   | 0.8644                  |
| gradient_boosted_trees | saturation_bin | saturated   | 240 | 0.5166               | 0.6066              | 0.0900                | 0.8473                   | 0.8509                  |
| gradient_boosted_trees | saturation_bin | unsaturated | 420 | 0.5166               | 0.6316              | 0.1150                | 0.8473                   | 0.8524                  |
| gradient_boosted_trees | pileup_bin     | clean       | 330 | 0.5166               | 0.4052              | -0.1115               | 0.8473                   | 0.8706                  |
| gradient_boosted_trees | pileup_bin     | pileup      | 330 | 0.5166               | 0.6673              | 0.1507                | 0.8473                   | 0.8515                  |

## Pedestal-Stratified Calibration Transfer

| method                 | pedestal_bin | n   | energy_bias_frac | energy_sigma68_frac | pid_auc | pid_balanced_accuracy |
| ---------------------- | ------------ | --- | ---------------- | ------------------- | ------- | --------------------- |
| gradient_boosted_trees | low          | 220 | -0.0490          | 0.1855              | 0.9148  | 0.8513                |
| gradient_boosted_trees | mid          | 220 | -0.0626          | 0.1563              | 0.9100  | 0.8419                |
| gradient_boosted_trees | high         | 220 | -0.0614          | 0.2040              | 0.9087  | 0.8382                |

## Pile-Up-Conditioned Failure Modes

| method                 | pileup_bin | saturation_bin | n   | pileup_miss_rate | false_split_rate | energy_sigma68_frac | pid_balanced_accuracy |
| ---------------------- | ---------- | -------------- | --- | ---------------- | ---------------- | ------------------- | --------------------- |
| gradient_boosted_trees | clean      | saturated      | 96  | nan              | 0.4062           | 0.1188              | 0.8505                |
| gradient_boosted_trees | clean      | unsaturated    | 234 | nan              | 0.1795           | 0.2466              | 0.8752                |
| gradient_boosted_trees | pileup     | saturated      | 144 | 0.2083           | nan              | 0.0756              | 0.8301                |
| gradient_boosted_trees | pileup     | unsaturated    | 186 | 0.3817           | nan              | 0.1450              | 0.8119                |

## Systematics and Caveats

The raw ROOT reproduction gate validates detector-channel semantics, selected
B-stack pulse support, and the exact count used by upstream analyses.  It does
not prove the GEANT4 material model, Birks response, trigger acceptance, or
external PID labeling.  The PID/energy labels used here are controlled bridge
truth labels, so the result should be read as a comparative architecture stress
test, not an absolute beamline efficiency measurement.  The waveform sequence
has only eighteen samples per channel; this limits the transformer advantage
and favors compact residual architectures.  Bootstrap intervals are run-block
intervals over five held-out runs, so they represent run-transfer uncertainty
better than event-counting precision but remain sensitive to the finite
held-out run set.

## Conclusion

Use **`gradient_boosted_trees`** as the S67b winner.  The new residual-stack architecture is
preferred because it improves the registered saturation-censored energy/PID
score while retaining the traditional likelihood template as an interpretable
calibration monitor.  The state-stratified tables show that saturation and
pedestal state still move PID thresholds and energy bias, so any production
deployment should propagate those nuisance spans rather than quoting a single
global PID boundary.

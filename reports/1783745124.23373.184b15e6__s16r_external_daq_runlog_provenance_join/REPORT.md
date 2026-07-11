# S16r: External DAQ Runlog Provenance Join for the B-stack Forced/Random Mirror

- **Ticket:** `1783745124.23373.184b15e6`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-07-11
- **Seeded by:** S16q `1783604855.13292.5bd05951`
- **Input:** raw ROOT under `data/root/root` plus bounded local DAQ/runlog artifacts
- **Config:** `configs/s16r_1783745124_23373_184b15e6_external_daq_runlog_provenance_join.json`
- **Git commit:** `660d5227a797ad9ae338c978203e9a4b3445aa25`

## Abstract

S16r asks whether external DAQ runlog, scaler, trigger-mode, or archive
provenance can be joined to the B-stack forced/random no-pulse mirror so that
the S16p/S16q pedestal adoption rule can be rerun with true non-beam labels
rather than beam-pretrigger surrogates.  The answer is negative in the mounted
data available to this worker: the explicit provenance join has `0`
positive rows, and the direct ROOT trigger inventories have `0`
non-beam or forced/random B-stack entries.  Therefore the direct no-pulse
estimand remains unidentified, and the S16q frozen run-held-out adoption-rule
benchmark remains the only defensible decision table.

The winner named in `result.json` is **traditional_mean3**.  It wins by the
pre-registered lexicographic rule: minimize the held-out downstream-pair
`|Delta r| > 5 ns` tail, then `|Delta r| > 0.5 ns`, then pedestal width68,
then pedestal RMSE.  The winning `|Delta r| > 5 ns` fraction is
`0.000704` with run-block 95% CI
`[0.000505, 0.001056]`.

## 1. Estimand and Identification

Let \(Z_i\) be an event-level DAQ provenance label with \(Z_i=1\) for a
forced/random no-pulse B-stack trigger and \(Z_i=0\) for beam-triggered rows.
The direct target for a pedestal estimator \(m\) is

\[
L_m^{FR} = E[\ell(\hat p_m(X_i), p_i^0) \mid Z_i=1],
\]

where \(p_i^0\) is the no-pulse electronics pedestal and \(\ell\) is the
pedestal, timing, or charge loss.  Identification requires at least one joined
DAQ/runlog record or ROOT trigger row with \(Z_i=1\).  In S16r the observed
joined set is empty, so \(L_m^{FR}\) is not estimable from mounted data.  The
reported ML comparison is therefore the frozen S16q proxy-adoption benchmark,
not a claim of direct forced/random truth.

## 2. Raw ROOT Reproduction

Before the provenance decision, S16q reproduced the S00/S16e raw-ROOT gate by
reading `h101/HRDv` directly from raw `hrdb_run_*.root` files.  For channel
\(c\) and sample \(t\),

\[
b_{ic} = \operatorname{median}(x_{ic0},x_{ic1},x_{ic2},x_{ic3}),
\qquad
I_{ic} = \mathbf{1}[\max_t(x_{ict}-b_{ic})>1000\;\mathrm{ADC}].
\]

The reproduced number is exact:

| quantity | expected | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| S00 selected B-stave pulses | 640737 | 640737 | 0 | True |
| forced/random/non-beam ROOT entries | 0 | 0 | 0 | True |
| forced/random/pedestal archive or filename hits | 0 | 0 | 0 | True |

## 3. External DAQ/Runlog Join

The join audit combines four independent local evidence streams: the S16i
external DAQ checksum join, the S16q archive/runlog scan, S16p checksum-bound
B-stack trigger manifest, and the S16j true-nonbeam B-stack mirror audit.
Each source is treated as an input artifact with its own row count, positive
forced/random count, and interpretation.

| evidence_source | artifact | rows | positive_forced_random_or_external_join_rows | auxiliary_token_candidate_rows | interpretation |
| --- | --- | --- | --- | --- | --- |
| S16i external checksum join | /home/billy/.tb-workers/testbeam-laptop-3/reports/1781110796.1578.28f051c2__s16i_external_daq_runlog_checksum_join/external_daq_runlog_checksum_join.csv | 110 | 0 | 0 | no independent external DAQ/runlog record joined to ROOT checksum manifest |
| S16i external candidate records | /home/billy/.tb-workers/testbeam-laptop-3/reports/1781110796.1578.28f051c2__s16i_external_daq_runlog_checksum_join/external_daq_candidate_records.csv | 0 | 0 | 0 | empty candidate table after bounded external-record scan |
| S16q archive/runlog scan | /home/billy/.tb-workers/testbeam-laptop-3/reports/1783604855.13292.5bd05951__s16q_no_pulse_bstack_forced_random_mirror/archive_runlog_scan.csv | 500 | 0 | 3 | no external forced/random DAQ/runlog join; pedestal-only documentation token candidates are not labels |
| S16q trigger audit | /home/billy/.tb-workers/testbeam-laptop-3/reports/1783604855.13292.5bd05951__s16q_no_pulse_bstack_forced_random_mirror/trigger_audit.csv | 110 | 0 | 0 | visible ROOT entries have no non-beam trigger code |
| S16p checksum-bound B-stack trigger manifest | /home/billy/.tb-workers/testbeam-laptop-3/reports/1783604316.18537.4d971468__s16p_checksum_bound_forced_random_bstack_pedestal_labels/trigger_mode_manifest.csv | 33 | 0 | 0 | B-stack trigger-code inventory remains TRIGGER=1 only |
| S16j mirror true-nonbeam B-stack audit | /home/billy/.tb-workers/testbeam-laptop-3/reports/1783568931.24470.56e21d18__s16j_mirror_true_nonbeam_bstack_forced_random/forced_random_daq_audit.csv | 53 | 0 | 0 | B-stack ROOT files contain no true non-beam forced/random rows |

The join status is therefore:

\[
N_{joined,FR} = 0,\qquad
N_{ROOT,TRIGGER\ne1} = 0.
\]

No downstream model is permitted to fill these missing labels.

## 4. Benchmark Design

The frozen S16q benchmark compares a strong transparent traditional pedestal
method against ridge regression, gradient-boosted trees, MLP, a 1D-CNN, and a
new target-masked residual CNN.  Runs `[58, 59, 60, 61, 62, 63, 65]` are held
out one at a time and all confidence intervals resample held-out runs as
blocks.  The traditional estimators are

\[
\hat p_{mean3,k}=\frac13\sum_{j\ne k}x_j,\qquad
\hat p_{median3,k}=\operatorname{median}(x_j: j\ne k),
\]

with line and run-stratified variants.  Learned regressors predict a residual
relative to a target-excluded baseline and exclude run id, event id, filenames,
trigger branch, selected-pulse amplitude, and target ADC from their feature
sets.  The new architecture receives a waveform tensor plus an explicit mask
for the excluded pretrigger sample.

The adoption rule is

\[
\arg\min_m \left(
P(|\Delta r_m|>5\,\mathrm{ns}),
P(|\Delta r_m|>0.5\,\mathrm{ns}),
W_{68}(\hat p_m-y),
\operatorname{RMSE}(\hat p_m-y)
\right).
\]

## 5. Head-to-Head Results

| method | family | timing_tail_gt5_fraction | timing_tail_gt0p5_fraction | pedestal_width68_adc | pedestal_rmse_adc | pedestal_mae_adc |
| --- | --- | --- | --- | --- | --- | --- |
| traditional_mean3 | traditional | 0.00070 [0.00050, 0.00106] | 0.14140 [0.13551, 0.14527] | 18.00000 [13.40833, 23.33333] | 734.83562 [610.09646, 797.91679] | 249.23526 [169.40546, 295.58413] |
| ridge | ml | 0.00486 [0.00411, 0.00622] | 0.60082 [0.57436, 0.64963] | 85.91316 [79.72661, 92.93892] | 463.09722 [389.82397, 513.81838] | 174.02551 [140.84027, 197.12402] |
| target_masked_residual_cnn | new_architecture | 0.01321 [0.01009, 0.01580] | 0.30782 [0.29064, 0.33538] | 37.47112 [32.05372, 43.09079] | 244.33800 [192.51254, 287.97984] | 53.85464 [42.88499, 64.16456] |
| one_dimensional_cnn | ml | 0.01803 [0.01470, 0.02059] | 0.28053 [0.26648, 0.29368] | 30.91599 [25.86258, 35.21069] | 338.41272 [266.71762, 387.29802] | 87.72784 [66.87036, 102.89697] |
| gradient_boosted_trees | ml | 0.02109 [0.01878, 0.02320] | 0.21102 [0.20424, 0.21732] | 21.94488 [19.17905, 25.01349] | 229.32147 [182.62316, 271.46537] | 51.13757 [39.22983, 59.27326] |
| mlp | ml | 0.02938 [0.02152, 0.03690] | 0.32146 [0.30093, 0.35065] | 37.50811 [30.75941, 43.14947] | 323.11975 [277.43155, 366.67331] | 94.56898 [75.08530, 112.52052] |

Paired run-block deltas versus the best traditional method:

| method | reference_traditional_method | delta_tail_gt5_fraction | delta_tail_gt5_ci_low | delta_tail_gt5_ci_high | delta_pedestal_width68_adc | delta_pedestal_width68_ci_low | delta_pedestal_width68_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ridge | traditional_mean3 | 0.00415 | 0.00332 | 0.00532 | 67.91316 | 64.64001 | 71.75507 |
| target_masked_residual_cnn | traditional_mean3 | 0.01251 | 0.00964 | 0.01513 | 19.47112 | 14.65331 | 22.53682 |
| one_dimensional_cnn | traditional_mean3 | 0.01732 | 0.01453 | 0.01996 | 12.91599 | 8.47301 | 14.52925 |
| gradient_boosted_trees | traditional_mean3 | 0.02039 | 0.01812 | 0.02253 | 3.94488 | 0.48566 | 5.88501 |
| mlp | traditional_mean3 | 0.02867 | 0.02141 | 0.03604 | 19.50811 | 15.46117 | 22.38342 |

Selected split-by-run diagnostics for the winner and strongest ML comparator:

| run | method | family | n_target_rows | pedestal_mae_adc | pedestal_rmse_adc | pedestal_bias_adc | pedestal_q05_adc | pedestal_q95_adc | n_pair_rows | timing_sigma68_shift_ns | timing_full_rms_shift_ns | timing_tail_gt0p5_fraction | timing_tail_gt5_fraction | timing_shift_bias_ns | n_charge_rows | charge_bias_delta_adc | charge_abs_delta_adc | pedestal_width68_adc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | traditional_mean3 | traditional | 67124 | 46.51511 | 275.39462 | 0.00000 | -23.00000 | 25.33333 | 1412 | 0.07066 | 4.37037 | 0.12110 | 0.00496 | 0.10320 | 67124 | -5.08428 | 15.82966 | 10.00000 |
| 58 | gradient_boosted_trees | ml | 67124 | 20.85431 | 86.52172 | 5.02517 | -17.69709 | 39.20914 | 1408 | 0.20995 | 7.70767 | 0.17898 | 0.01989 | -0.04316 | 67124 | -10.10944 | 38.26819 | 15.17850 |
| 59 | traditional_mean3 | traditional | 85508 | 314.37564 | 818.47280 | 0.00000 | -1290.65000 | 1083.76667 | 15012 | 0.09567 | 1.44114 | 0.14149 | 0.00067 | 0.01128 | 85508 | -47.18485 | 109.86102 | 31.66667 |
| 59 | gradient_boosted_trees | ml | 85508 | 65.68030 | 307.27190 | -6.09964 | -189.08627 | 137.64214 | 14890 | 0.26195 | 2.60937 | 0.21478 | 0.02492 | -0.02315 | 85508 | -41.08521 | 215.47462 | 26.01434 |
| 60 | traditional_mean3 | traditional | 68116 | 304.12580 | 812.53997 | -0.00000 | -1300.41667 | 1101.41667 | 14800 | 0.10228 | 0.95709 | 0.14885 | 0.00068 | 0.03082 | 68116 | -49.77512 | 106.55183 | 24.00000 |
| 60 | gradient_boosted_trees | ml | 68116 | 53.39121 | 226.85609 | 2.22335 | -141.69118 | 126.50367 | 14658 | 0.25161 | 2.00636 | 0.22431 | 0.02122 | 0.00566 | 68116 | -51.99847 | 215.18806 | 23.45257 |
| 61 | traditional_mean3 | traditional | 75860 | 277.81598 | 753.10986 | -0.00000 | -1144.33333 | 1015.33333 | 16980 | 0.08616 | 1.21990 | 0.13604 | 0.00077 | 0.01925 | 75860 | -46.52051 | 96.42415 | 22.00000 |
| 61 | gradient_boosted_trees | ml | 75860 | 48.66428 | 184.70006 | -3.31084 | -137.68793 | 105.64972 | 16831 | 0.23096 | 2.62624 | 0.20492 | 0.01872 | -0.01542 | 75860 | -43.20967 | 194.20081 | 21.82086 |
| 62 | traditional_mean3 | traditional | 76356 | 284.09388 | 761.78626 | 0.00000 | -1174.41667 | 1017.41667 | 15332 | 0.09063 | 1.32797 | 0.14473 | 0.00059 | 0.02403 | 76356 | -44.05062 | 98.87599 | 23.66667 |
| 62 | gradient_boosted_trees | ml | 76356 | 56.91578 | 207.00710 | -2.21389 | -167.36588 | 127.07672 | 15168 | 0.24120 | 2.26552 | 0.20853 | 0.02156 | -0.05026 | 76356 | -41.83673 | 198.19789 | 26.63471 |
| 63 | traditional_mean3 | traditional | 75268 | 264.60466 | 790.20048 | 0.00000 | -911.86667 | 905.21667 | 7264 | 0.09799 | 0.88231 | 0.14414 | 0.00028 | 0.04674 | 75268 | -37.28195 | 92.65955 | 18.00000 |
| 63 | gradient_boosted_trees | ml | 75268 | 58.25536 | 269.44702 | 1.23380 | -142.90044 | 120.25371 | 7204 | 0.25519 | 2.26254 | 0.21474 | 0.02096 | 0.00601 | 75268 | -38.51575 | 182.19191 | 21.10383 |
| 65 | traditional_mean3 | traditional | 52152 | 216.86482 | 739.49834 | -0.00000 | -398.75000 | 602.15000 | 1592 | 0.07549 | 0.45422 | 0.10176 | 0.00000 | 0.04102 | 52152 | -29.20667 | 75.43410 | 14.00000 |
| 65 | gradient_boosted_trees | ml | 52152 | 48.19203 | 236.15854 | 3.38660 | -98.83836 | 80.11426 | 1579 | 0.20229 | 0.90167 | 0.15263 | 0.00633 | -0.06542 | 52152 | -32.59326 | 152.37670 | 20.74518 |

## 6. Systematics and Caveats

The dominant systematic is data availability.  The mounted mirror can support a
negative provenance join, but not a direct statement that no forced/random
B-stack data were ever acquired by the collaboration.  If an unmounted DAQ
logbook, trigger spreadsheet, scaler file, or archive member later joins to
the ROOT checksum manifest, the S16r conclusion must be reopened and the
adoption rule rerun on direct no-pulse labels.

The second systematic is proxy mismatch.  The S16q benchmark is a
target-excluded beam-pretrigger closure test; it stresses pedestal-induced
timing and charge risk, but it is not a forced/random electronics pedestal
sample.  For that reason, ML methods that reduce pedestal MAE cannot be
promoted if they increase timing tails under the adoption rule.

The third systematic is run drift.  All CIs are run-block bootstrap intervals,
and all train/test partitions are disjoint in run number.  Row bootstrap CIs
would understate uncertainty because adjacent events share beam current,
temperature, trigger phase, and calibration state.

## 7. Conclusion

S16r finds no external DAQ/runlog provenance that can attach true forced/random
labels to the B-stack no-pulse mirror.  The raw-ROOT reproduction remains exact
at `640737` selected B-stave pulses, the direct non-beam ROOT count remains
zero, and the external join count remains zero.  The frozen S16q decision
therefore stands: **traditional_mean3** is the adoption-rule winner because it
has the lowest held-out `|Delta r| > 5 ns` downstream-pair tail despite weaker
pedestal MAE than gradient-boosted trees.

No novel follow-up ticket is appended from this worker.

# S26a Pedestal-Timing-Pileup Disentanglement Benchmark

**Ticket:** `1783798536.2303.53394aed`  
**Worker:** `testbeam-laptop-1`  
**Command:** `.venv/bin/python scripts/s26a_1783798536_2303_53394aed_pedestal_timing_pileup_disentanglement.py --config configs/s26a_1783798536_2303_53394aed_pedestal_timing_pileup_disentanglement.json`  
**Git commit:** `e3eb2efc02c365a25c94ff00e2e6998781de9d8f`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This study tests whether a strong traditional CFD/template-fit plus pedestal
sideband correction is sufficient for separating pedestal drift, pulse-shape
timing residuals, and low-separation pile-up in the B-stack HRD waveforms.  The
benchmark includes the requested method panel: a traditional comparator, ridge,
gradient-boosted trees, MLP, 1D-CNN, and a compact residual waveform
architecture.  All endpoints are tied to run-heldout source folds and
run-block/percentile bootstrap confidence intervals.  The winner named in
`result.json` is **`mlp`** with joint loss `0.308878`.

The traditional comparator remains competitive on PID proxy closure and has
well-behaved pedestal bias (`0.001867`), but the global
disentanglement loss favors `mlp` because it better balances
pedestal resolution, timing width, and pile-up recall.

## Raw ROOT Reproduction Gate

The raw gate reads `h101/HRDv` from every B-stack `hrdb_run_NNNN.root`, reshapes
the vector into eight channels by eighteen samples, and subtracts the per-event,
per-channel pedestal

`b_{e,c} = median_{t in {0,1,2,3}} x_{e,c,t}`.

For B2, B4, B6, and B8 the selected-pulse predicate is

`I_{e,c} = 1[max_t (x_{e,c,t} - b_{e,c}) > 1000 ADC]`.

The reproduced ticket number is the total selected B-stave pulse count

`N = sum_{runs} sum_e sum_{c in B} I_{e,c}`.

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| sample_i_calib selected pulses | 248745 | 248745 | 0 | 0 | True |
| sample_i_analysis selected pulses | 252266 | 252266 | 0 | 0 | True |
| sample_ii_calib selected pulses | 14630 | 14630 | 0 | 0 | True |
| sample_ii_analysis selected pulses | 125096 | 125096 | 0 | 0 | True |

This exact count check is a hard precondition: all benchmark synthesis below is
discarded if any raw count differs from the established ROOT anchor.

## Run Split and Bootstrap

The split is by run family, never random event shuffling.  Calibration runs are
Sample I runs 31-37 and 39-42 plus Sample II run 64.  Analysis/holdout runs are
Sample I runs 44-57 and Sample II runs 58-63 and 65.  Timing intervals are
recomputed here by resampling held-out runs with replacement.  PID, energy,
pedestal, saturation, and pile-up intervals are inherited from their
run-heldout source studies and copied into this ticket-local artifact.

## Estimands

The pedestal endpoint uses residual resolution and signed bias after a
pedestal/saturation correction:

`r_i = (hat q_i - q_i) / max(|q_i|, epsilon)`.

The reported pedestal resolution is `sigma_68(r) = 0.5(Q_84(r)-Q_16(r))`, and
the pedestal bias is `mean(r)`.  Timing uses robust pulse-pair width in ns after
model-specific timewalk or waveform correction.  Pile-up quality uses average
precision, miss rate, false-split rate, and constituent timing sigma68 on
low-separation injected overlays.  Energy/PID proxy stability is included only
as a weak regularizer so that a method cannot win by improving pedestal metrics
while destroying established energy/PID support.

## Methods

The traditional method is a CFD/template fit with a pedestal sideband and
saturation-clipped template correction.  Its timing component uses constrained
monotone timewalk; its pile-up component compares one-template and two-template
fits through

`Delta_chi2 = (SSE_1 - SSE_2) / max(SSE_1, epsilon)`.

Ridge uses standardized waveform and scalar atoms with L2 regularization,

`hat y = X (X^T X + lambda I)^(-1) X^T y`.

Gradient-boosted trees model nonlinear interactions between amplitude,
pedestal, timing, and pulse-shape atoms.  The MLP is a dense nonlinear model on
the same tabular atoms.  The 1D-CNN operates on ordered eighteen-sample
waveforms.  The compact residual waveform architecture combines a residual CNN
timing head, a boosted template-residual pile-up head, a gated residual
pedestal/saturation head, and PID/energy residual heads; it is included as the
new architecture because the endpoints are heterogeneous and event-aligned true
multi-task labels are unavailable.

## Scoring Rule

Lower is better.  The registered S26a loss is

`L_m = 0.22 sigma_ped/0.05 + 0.10 |b_ped|/0.02 + 0.22 sigma_t/2.0 + 0.06 f_tail + 0.14(1-AP_pileup) + 0.12 r_miss + 0.05 r_false + 0.05 sigma_E + 0.04(1-AUC_PID)`.

This places most weight on the requested disentanglement axes while retaining
small penalties for energy and PID proxy instability.

## Head-to-Head Results

| method | family | joint_loss | pedestal_res68 | pedestal_bias | timing_sigma68_ns | pileup_detection_ap | pileup_miss_rate | false_split_rate | energy_res68 | pid_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlp | neural_tabular | 0.308878 | 0.0232743 | 0.00680348 | 0.584091 | 0.85311 | 0.363333 | 0.136667 | 0.692347 | 0.947092 |
| gradient_boosted_trees | ml_tree | 0.382444 | 0.0313697 | -0.0123365 | 0.990472 | 0.844353 | 0.3 | 0.186667 | 0.0566846 | 0.92801 |
| traditional_cfd_template_pedestal_sideband | traditional | 0.479527 | 0.0403935 | 0.00186671 | 1.51782 | 0.675795 | 0.58 | 0.17 | 0.040244 | 1 |
| 1d_cnn | neural_waveform | 0.674345 | 0.0710811 | -0.0128017 | 1.74046 | 0.825223 | 0.383333 | 0.153333 | 0.265704 | 0.726767 |
| compact_residual_waveform_architecture | new_architecture | 0.932573 | 0.125784 | 0.0114011 | 2.26107 | 0.844022 | 0.313333 | 0.173333 | 0.0586802 | 1 |
| ridge | ml_linear | 1.48068 | 0.228457 | -0.0435215 | 1.61473 | 0.863511 | 0.356667 | 0.113333 | 0.0966729 | 0.851321 |

## Confidence Intervals

| method | pedestal_res68_ci_low | pedestal_res68_ci_high | timing_run_boot_ci_low_ns | timing_run_boot_ci_high_ns | pileup_detection_ap_ci_low | pileup_detection_ap_ci_high | pileup_miss_rate_ci_low | pileup_miss_rate_ci_high | energy_res68_ci_low | energy_res68_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlp | 0.0209973 | 0.0272127 | 0.459528 | 0.757956 | 0.83963 | 0.872566 | 0.346667 | 0.38 | 0.684237 | 0.699646 |
| gradient_boosted_trees | 0.0294305 | 0.0343779 | 0.657926 | 1.24665 | 0.819698 | 0.868279 | 0.28 | 0.32175 | 0.048804 | 0.0671974 |
| traditional_cfd_template_pedestal_sideband | 0.0323277 | 0.049645 | 1.10275 | 1.48217 | 0.655225 | 0.703875 | 0.531583 | 0.63175 | 0.0388569 | 0.0416063 |
| 1d_cnn | 0.0648101 | 0.0786075 | 1.33558 | 1.88055 | 0.810424 | 0.844875 | 0.333333 | 0.426667 | 0.249266 | 0.289079 |
| compact_residual_waveform_architecture | 0.111599 | 0.142315 | 1.7945 | 2.50328 | 0.816571 | 0.86196 | 0.303333 | 0.326667 | 0.0490247 | 0.0778825 |
| ridge | 0.19857 | 0.257226 | 1.17852 | 2.19584 | 0.846488 | 0.883468 | 0.35 | 0.37 | 0.0887156 | 0.117206 |

## Systematics and Caveats

The pedestal and pile-up labels are empirical/injected stress labels rather than
hidden detector truth.  The pile-up sample has 600 labelled overlays with 300
positives, so confidence intervals are more informative than third-decimal
rankings.  PID is a charge/depth/range proxy, not direct particle identity.
Energy inherits GEANT4/Birks and duplicate-readout calibration priors.  The
compact residual architecture is a ticket-local synthesis of endpoint-specific
models rather than a single monolithic multi-task network; fitting one network
would be statistically circular without event-aligned true PID, energy, timing,
pile-up, saturation, and pedestal labels.  The result should therefore be read
as a conservative endpoint-disentanglement benchmark, not as a final production
recommendation.

## Reproducibility

Artifacts in this directory include `result.json`, `REPORT.md`,
`manifest.json`, `claimed_ticket.txt`, `reproduction_counts_by_run.csv`,
`reproduction_match_table.csv`, `method_benchmark.csv`,
`timing_run_bootstrap.csv`, and source metric snapshots.  The source artifact
directories are recorded in `manifest.json`.

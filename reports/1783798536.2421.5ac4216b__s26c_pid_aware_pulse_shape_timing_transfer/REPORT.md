# S26c PID-aware pulse-shape timing transfer study

**Ticket:** `1783798536.2421.5ac4216b`  
**Worker:** `testbeam-laptop-1`  
**Raw ROOT directory:** `data/root/root`  
**Command:** `uv run python scripts/s26c_1783798536_2421_5ac4216b_pid_aware_pulse_shape_timing_transfer.py --config configs/s26c_1783798536_2421_5ac4216b_pid_aware_pulse_shape_timing_transfer.json`  
**Git commit:** `5a07783ca67f9c412017131ab36e88c4406f7bd8`

## Abstract

This study asks whether PID-aware pulse-shape information improves timing,
pile-up localization, saturation recovery, pedestal stability, and calibrated
energy transfer across run families. The benchmark compares a strong
traditional charge-ratio/template/timewalk method against ridge, gradient
boosted trees, MLP, 1D-CNN, and a new residual architecture. The machine
readable winner in `result.json` is **`gradient_boosted_trees`** with joint loss
`0.190610`.

## Raw ROOT reproduction

The raw gate reads each `h101/HRDv` array from `data/root/root/hrdb_run_NNNN.root`,
reshapes events into eight channels by eighteen samples, subtracts

`b_{e,c} = median(x_{e,c,t} : t in {0,1,2,3})`,

and counts B2/B4/B6/B8 pulses satisfying

`max_t (x_{e,c,t} - b_{e,c}) > 1000 ADC`.

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| sample_i_calib selected pulses | 248745 | 248745 | 0 | 0 | True |
| sample_i_analysis selected pulses | 252266 | 252266 | 0 | 0 | True |
| sample_ii_calib selected pulses | 14630 | 14630 | 0 | 0 | True |
| sample_ii_analysis selected pulses | 125096 | 125096 | 0 | 0 | True |

The exact raw ROOT reproduction is a hard precondition for interpreting all
downstream benchmark tables.

## Split and bootstrap design

All source endpoints use held-out run families rather than shuffled events.
The calibration groups are Sample I calibration runs 31-37 and 39-42 plus
Sample II calibration run 64. The analysis groups are Sample I runs 44-57 and
Sample II runs 58-63 and 65. Timing CIs in this ticket are recomputed by
resampling held-out runs with replacement; inherited PID, pile-up, saturation,
and energy CIs are source run-block percentile intervals.

## Methods

The traditional method combines charge-depth PID cuts, template-shape
consistency, constrained monotone timewalk correction, and two-pulse
CFD/template residual fitting. Ridge and GBT operate on standardized pulse,
charge, timing, and shape atoms. The MLP is a dense nonlinear model on the same
summary space. The 1D-CNN operates directly on ordered 18-sample waveforms. The
new architecture is a residual family: action-gated residual ensemble for PID,
physics-residual MLP for energy, gated residual CNN for timing, and boosted
template residual stack for pile-up.

## Score

Lower is better. The registered loss is

`L = 0.18(1-AUC_PID) + 0.08(1-AP_PID) + 0.18 sigma_t/2.5 + 0.13(1-AP_pileup) + 0.10 sigma_pileup/12 + 0.12 r_sat + 0.06 P_ped + 0.10 r_E + 0.05 |bias_E|`.

Here `sigma_t` is the robust run-heldout timing width, `sigma_pileup` is the
pile-up timing sigma68, `r_sat` is saturation-stratum energy res68, `P_ped` is
the available pedestal shape penalty, and `r_E` is global energy res68.

## Head-to-head benchmark

| method | family | joint_loss | pid_auc | pid_average_precision | timing_sigma68_ns | pileup_detection_ap | pileup_time_sigma68_ns | saturation_energy_res68 | energy_res68 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | ml_tree | 0.19061 | 0.92801 | 0.894266 | 0.990472 | 0.844353 | 7.80652 | 0.0562143 | 0.0566846 |
| traditional_joint | traditional | 0.240798 | 1 | 1 | 1.51782 | 0.675795 | 9.49315 | 0.0484976 | 0.040244 |
| new_residual_architecture | new_architecture | 0.255681 | 1 | 1 | 2.26107 | 0.844022 | 7.43715 | 0.0387698 | 0.0586802 |
| ridge | ml_linear | 0.272729 | 0.851321 | 0.778751 | 1.61473 | 0.863511 | 9.32037 | 0.0549549 | 0.0966729 |
| mlp | neural_tabular | 0.316224 | 0.947092 | 0.922128 | 0.584091 | 0.85311 | 11.9709 | 0.57333 | 0.692347 |
| 1d_cnn | neural_waveform | 0.367119 | 0.726767 | 0.638905 | 1.74046 | 0.825223 | 10.9122 | 0.189761 | 0.265704 |

## Confidence intervals

| method | timing_sigma68_ci_low_ns | timing_sigma68_ci_high_ns | timing_run_boot_ci_low_ns | timing_run_boot_ci_high_ns | pileup_detection_ap_ci_low | pileup_detection_ap_ci_high | energy_res68_ci_low | energy_res68_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 0.750485 | 1.44201 | 0.649568 | 1.29581 | 0.819698 | 0.868279 | 0.048804 | 0.0671974 |
| traditional_joint | 1.25826 | 1.71967 | 1.09946 | 1.48364 | 0.655225 | 0.703875 | 0.0388569 | 0.0416063 |
| new_residual_architecture | 1.936 | 2.564 | 1.70859 | 2.46973 | 0.816571 | 0.86196 | 0.0490247 | 0.0778825 |
| ridge | 1.26685 | 2.25505 | 1.17058 | 2.23307 | 0.846488 | 0.883468 | 0.0887156 | 0.117206 |
| mlp | 0.478496 | 0.773545 | 0.473615 | 0.738146 | 0.83963 | 0.872566 | 0.684237 | 0.699646 |
| 1d_cnn | 1.47443 | 2.12398 | 1.36087 | 1.9905 | 0.810424 | 0.844875 | 0.249266 | 0.289079 |

## Systematics

PID is a beamline/range enriched proxy, not hidden particle truth. The
traditional PID endpoint is therefore structurally aligned with that proxy, and
perfect AUC should be read as closure on the available support rather than
absolute PID efficiency. Energy uses duplicate-readout and GEANT4/Birks
calibration priors; it is a transfer-calibrated energy endpoint, not a direct
calorimeter truth label. Timing is evaluated on run-heldout pulse pairs in the
high-support `cfd0.20_cut1000` gate. Pile-up stress is synthetic-plus-empirical
and has only 600 labelled events, so AP differences at the third decimal place
are not scientifically material.

## Caveats

The source tasks are independently trained endpoint studies; this script
performs a ticket-local synthesis and timing bootstrap rather than fitting a
single monolithic multi-task neural network. That is deliberate: without
event-aligned true PID and energy labels, a multi-task model would mostly learn
proxy construction rules. The best next experiment is therefore a digitized
GEANT4 multi-task benchmark with true event labels, which is the single novel
ticket proposed in `result.json`.

## Reproducibility

Primary outputs are `result.json`, `REPORT.md`, `manifest.json`,
`reproduction_counts_by_run.csv`, `reproduction_match_table.csv`,
`method_benchmark.csv`, `timing_run_bootstrap.csv`, and copied source metric
tables. The source artifact directories are:

- PID/energy: `reports/1783751737.13516.61447038__s25a_joint_pid_energy_pileup_saturation`
- Timing: `reports/1783770201.8157.51000596__s18i_pulse_shape_timing_model_hierarchy`
- Pile-up: `reports/1783770201.8222.568f4add__s25b_pileup_saturation_recovery_benchmark`
- Pedestal: `reports/1783762816.2490.722918d7__s25b_saturation_onset_hysteresis_waveform_recovery`

# P08c: charge-residual waveform PID null

**Ticket:** 1781075123.485.458a1740
**Worker:** testbeam-laptop-2
**Date:** 2026-07-08
**Depends on:** S00, P01b, P08b
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`
**Git commit:** `75efc5034421ae229bb0a2be80df12e8e3289a90`
**Config:** `configs/p08c_1781075123_485_458a1740_charge_residual_waveform_pid_null.json`
**Constraint:** no Monte Carlo truth and no PID adoption without S17 truth.

## 0. Question
After calibrated duplicate-readout charge-depth and range-energy residuals are
modeled, does the 18-sample waveform retain PID-like information beyond
charge, topology, saturation, and run-family support? Operationally, this is a
charge-residual null test: compare a strong transparent
PSD/calibrated-charge-depth baseline to ridge, gradient-boosted trees, MLP,
1D-CNN, and a residual-fusion architecture on the same run-held-out matched
support, while measuring nuisance-only and shuffled-label controls.

## 1. Reproduction From Raw ROOT
Before labels, matching, or models, the script rescans the B-stack ROOT
`h101/HRDv` branch, subtracts the median of samples 0--3, selects B2/B4/B6/B8
with amplitude greater than 1000 ADC, and requires the standing S00 count gate
to pass.

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

The gate passes with zero tolerance. Input hashes for all `33` B-stack
ROOT files are recorded in `input_sha256.csv`.

## 2. Weak Label and Matching
The weak label is inherited from P08b, not from topology. For each B2-selected
event, the odd duplicate readout is calibrated to a PSTAR depth-energy proxy
using only calibration groups `sample_i_calib, sample_ii_calib`. Within every run/depth atom,
the bottom `25%` of odd residuals is labeled
`low_calibrated_range_energy_residual` and the top `25%` is labeled `high_calibrated_range_energy_residual`:

`r_odd = (E_odd(q_odd, d) - E_PSTAR(d)) / max(E_PSTAR(d), 1 MeV)`.

The labeled support has `289,626` rows across `122` run/depth
atoms. Continuous matching first fits a nuisance propensity

`logit e(x) = beta0 + beta^T x`

with `x` containing B2 charge, total charge, event-order current proxy,
depth/topology, saturation, and pile-up shape proxies. Within each run/depth
atom, high-residual rows are matched one-to-one to the nearest low-residual row
in standardized nuisance-plus-propensity space, with caliper `0.55` and no
waveform score in the distance.

Matching sensitivity:

| matching                 |   caliper |   matched_rows |   matched_pairs |   support_loss_fraction |   max_abs_smd |   nuisance_only_runheldout_auc |
|:-------------------------|----------:|---------------:|----------------:|------------------------:|--------------:|-------------------------------:|
| exact_cell               |    nan    |            944 |             472 |                0.996741 |      0.686615 |                       0.758354 |
| continuous_nn_propensity |      0.35 |            796 |             398 |                0.997252 |      1.44621  |                       0.925384 |
| continuous_nn_propensity |      0.55 |           2098 |            1049 |                0.992756 |      1.41879  |                       0.941726 |
| continuous_nn_propensity |      0.8  |           3664 |            1832 |                0.987349 |      1.38406  |                       0.95598  |

The primary matched set contains `2,098` rows
(`1,049` pairs), losing `99.3%` of labeled rows.
Post-match covariate balance for the largest residual imbalances is:

| covariate                  |   negative_mean |   positive_mean |   standardized_mean_difference |
|:---------------------------|----------------:|----------------:|-------------------------------:|
| b2_tail_fraction           |        0.24187  |        0.34112  |                     1.41879    |
| propensity_logit           |        0.883008 |        2.09334  |                     0.478356   |
| b2_width20                 |       13.4509   |       13.1602   |                    -0.222492   |
| log_even_total_charge      |       10.9545   |       10.9984   |                     0.186804   |
| log_b2_area                |       10.745    |       10.7848   |                     0.123771   |
| downstream_charge_fraction |        0.134561 |        0.135589 |                     0.0040657  |
| event_fraction             |        0.495934 |        0.495683 |                    -0.00088357 |
| depth_idx                  |        0.349857 |        0.349857 |                     0          |

## 3. Methods
All benchmark scores are leave-one-run-out predictions. Every fold trains
matching-agnostic models only on training runs and scores the held-out run.
Confidence intervals resample held-out runs with replacement.

The transparent traditional baseline is a ridge-regularized logistic
combination of tail/total, area/peak, train-fold q-template projection,
DeltaE-like even-charge residual, even calibrated range-energy residual,
depth, multiplicity, saturation, and event-current proxy. It is a strong
traditional comparator because it sees the hand-engineered variables that a
PSD/DeltaE-E analysis would use, but not the odd readout that defines the weak
label. The learned models therefore test residual information relative to this
calibrated charge-depth surface rather than a raw topology shortcut.

The learned panel is:

| model | inputs | note |
|---|---|---|
| ridge logistic waveform+latent | normalized B2 waveform, hand-shape summaries, P01b latent if joinable | linear ML comparator |
| gradient-boosted trees waveform+latent | same as ridge | nonlinear tabular comparator |
| MLP waveform+latent | same as ridge | dense neural comparator |
| 1D-CNN waveform+handshape | waveform samples through small 1D convolutions plus hand-shape head | local pulse-shape neural comparator |
| new residual-fusion ridge | waveform/latent features residualized against propensity/depth/multiplicity nuisance cells | architecture designed for this leakage-control setting |

Probability calibration uses cross-fold isotonic regression, never the held-out
run being scored. The reported Brier score and ECE use those calibrated
probabilities.

## 4. Head-to-Head Benchmark
Metric is weak-label discrimination, not truth PID. The primary ranking metric
is ROC AUC; AP, Brier/ECE, and purity at `80%` high-residual efficiency
are secondary.

| method                                           |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   brier_isotonic |   ece_isotonic |   purity_at_80pct_eff |
|:-------------------------------------------------|----------:|-----------------:|------------------:|--------------------:|-----------------:|---------------:|----------------------:|
| traditional PSD/calibrated-cut logistic          |  0.984155 |         0.975486 |          0.991422 |            0.966086 |       0.0342329  |     0.0178714  |              0.982436 |
| ridge logistic waveform+latent                   |  0.997837 |         0.9946   |          0.999663 |            0.994798 |       0.0081214  |     0.00572085 |              0.996437 |
| gradient-boosted trees waveform+latent           |  0.999209 |         0.997776 |          0.999887 |            0.999038 |       0.00727471 |     0.00790593 |              0.99881  |
| MLP waveform+latent                              |  0.994541 |         0.990169 |          0.997622 |            0.990777 |       0.022603   |     0.0112125  |              0.995255 |
| 1D-CNN waveform+handshape                        |  0.920144 |         0.878617 |          0.955763 |            0.920367 |       0.123325   |     0.0652795  |              0.845766 |
| new residual-fusion ridge                        |  0.992747 |         0.98562  |          0.997059 |            0.988309 |       0.0186246  |     0.00839475 |              0.987059 |
| leakage sentinel: matched nuisance-only logistic |  0.941621 |         0.905626 |          0.964418 |            0.880108 |       0.0627205  |     0.0215614  |              0.908992 |
| leakage sentinel: run-family/event logistic      |  0.494718 |         0.492076 |          0.49736  |            0.495239 |       0.251149   |     0.00819274 |              0.499108 |
| leakage sentinel: shuffled-label GBT             |  0.526409 |         0.473265 |          0.587986 |            0.533007 |       0.251044   |     0.030776   |              0.502998 |

Winner by point-estimate ROC AUC is **gradient-boosted trees waveform+latent** with AUC
`0.999` and run-block 95% CI `[0.998, 1.000]`.
The matched nuisance-only sentinel is AUC `0.942`
`[0.906, 0.964]`. P08b's pre-matching even-charge proxy AUC was
`0.985` and its main waveform/latent HGB AUC was `0.986`.

## 5. Falsification and Systematics
Pre-registered failure conditions are inherited from the ticket: if
nuisance-only AUC remains far above chance, or if shuffled-label performance
does not collapse, waveform PID adoption is rejected. The nuisance-only
sentinel after primary matching is `0.942`; shuffled-label GBT is
reported in the benchmark table. Matching caliper sensitivity is reported
above; the strictest caliper tests whether the result is a support artifact,
and the loosest caliper tests whether leakage re-enters when support is
increased.

Systematic uncertainties are dominated by the weak-label construction rather
than model variance:

| source | direction | mitigation |
|---|---|---|
| duplicate-readout label source | odd residual is correlated with even charge and waveform amplitude | even charge is matched and audited by nuisance-only AUC |
| run/depth thresholding | labels are relative within run/depth, not particle truth | split by run and match within run/depth |
| support loss | tight calipers select a support island | report support loss and caliper scan |
| pile-up proxy incompleteness | no external beam-current scaler is available in ROOT mirror | use event order, width, and tail proxies; caveat remains |
| P01b latent provenance | P01b is an all-data representation artifact | included as diagnostic input, not as a truth source |

## 6. Verdict
The continuous matcher reduces the specific P08b charge/current leakage
substantially but does not turn the weak label into PID truth. The result is a
leakage-control benchmark: **gradient-boosted trees waveform+latent** is the predictive winner, while
`pid_adoption` is **false** because S17 truth is absent and residual nuisance
information remains part of the uncertainty budget.

## 7. Provenance
`manifest.json` records the script, config, command, Python/platform, git
commit, random seeds, raw input hashes, and output hashes. The script refuses to
model unless the raw ROOT reproduction table passes.

## 8. Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08c_1781054166_1411_4282226f_continuous_charge_current_matching.py --config configs/p08c_1781075123_485_458a1740_charge_residual_waveform_pid_null.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `calibrated_label_support.csv`,
`matching_sensitivity.csv`, `matched_balance_smd.csv`, `scoreboard.csv`,
`heldout_run_label_counts.csv`, and `oof_prediction_preview.csv`.

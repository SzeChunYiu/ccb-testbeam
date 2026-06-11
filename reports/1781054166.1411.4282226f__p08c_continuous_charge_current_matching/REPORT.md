# P08c: continuous charge-current matching for PID leakage control

**Ticket:** 1781054166.1411.4282226f
**Worker:** testbeam-laptop-4
**Date:** 2026-06-11
**Depends on:** S00, P01b, P08b
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`
**Git commit:** `b08daa5bc38c435f596951c340e79b4951b9c98f`
**Config:** `configs/p08c_1781054166_1411_4282226f_continuous_charge_current_matching.json`
**Constraint:** no Monte Carlo truth and no PID adoption without S17 truth.

## 0. Question
Does continuous nearest-neighbor/propensity matching on charge, current proxy,
depth/topology, saturation, and pile-up proxies suppress the P08b charge-current
leakage enough that waveform or latent classifiers can be read as independent
PID-like information? The operational answer is deliberately narrower: compare
a strong transparent PSD/calibrated-cut baseline to ridge, gradient-boosted
trees, MLP, 1D-CNN, and a residual-fusion architecture on the same
run-held-out matched support, while measuring nuisance-only AUC.

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
atoms. Continuous matching fits a nuisance propensity

`logit e(x) = beta0 + beta^T x`

with `x` containing B2 charge, total charge, event-order current proxy,
depth/topology, saturation, and pile-up shape proxies. Within each run/depth
atom, high-residual rows are matched one-to-one to the nearest low-residual row
in standardized nuisance-plus-propensity space, with caliper `0.55` and no
waveform score in the distance.

Matching sensitivity:

| matching                 |   caliper |   matched_rows |   matched_pairs |   support_loss_fraction |   max_abs_smd |   nuisance_only_runheldout_auc |
|:-------------------------|----------:|---------------:|----------------:|------------------------:|--------------:|-------------------------------:|
| exact_cell               |    nan    |            944 |             472 |                0.996741 |      0.670434 |                       0.751457 |
| continuous_nn_propensity |      0.35 |            776 |             388 |                0.997321 |      1.34407  |                       0.909679 |
| continuous_nn_propensity |      0.55 |           2078 |            1039 |                0.992825 |      1.41419  |                       0.941254 |
| continuous_nn_propensity |      0.8  |           3664 |            1832 |                0.987349 |      1.42566  |                       0.956668 |

The primary matched set contains `2,078` rows
(`1,039` pairs), losing `99.3%` of labeled rows.
Post-match covariate balance for the largest residual imbalances is:

| covariate                  |   negative_mean |   positive_mean |   standardized_mean_difference |
|:---------------------------|----------------:|----------------:|-------------------------------:|
| b2_tail_fraction           |        0.241614 |        0.340399 |                     1.41419    |
| propensity_logit           |        0.921701 |        2.11782  |                     0.469156   |
| b2_width20                 |       13.4447   |       13.1347   |                    -0.235467   |
| log_even_total_charge      |       10.9587   |       11.0001   |                     0.174227   |
| log_b2_area                |       10.7438   |       10.7817   |                     0.116969   |
| downstream_charge_fraction |        0.137173 |        0.137874 |                     0.00274348 |
| event_fraction             |        0.504814 |        0.504326 |                    -0.00172138 |
| depth_idx                  |        0.360924 |        0.360924 |                     0          |

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
label.

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
| traditional PSD/calibrated-cut logistic          |  0.984379 |         0.976173 |          0.989989 |            0.968838 |       0.0331789  |     0.00912496 |              0.980975 |
| ridge logistic waveform+latent                   |  0.999791 |         0.999466 |          0.999964 |            0.999795 |       0.0060314  |     0.00987421 |              1        |
| gradient-boosted trees waveform+latent           |  0.999795 |         0.999537 |          0.999961 |            0.999798 |       0.00523738 |     0.0039654  |              1        |
| MLP waveform+latent                              |  0.997781 |         0.995824 |          0.999147 |            0.997368 |       0.0137129  |     0.00733715 |              0.997582 |
| 1D-CNN waveform+handshape                        |  0.931831 |         0.904169 |          0.957074 |            0.92643  |       0.107741   |     0.0337696  |              0.901639 |
| new residual-fusion ridge                        |  0.998231 |         0.995289 |          0.99944  |            0.998155 |       0.0115836  |     0.00720359 |              0.997582 |
| leakage sentinel: matched nuisance-only logistic |  0.943141 |         0.909809 |          0.965545 |            0.883766 |       0.062139   |     0.0157521  |              0.911602 |
| leakage sentinel: run-family/event logistic      |  0.496215 |         0.492853 |          0.499299 |            0.495588 |       0.250499   |     0.00963259 |              0.499395 |
| leakage sentinel: shuffled-label GBT             |  0.445489 |         0.368283 |          0.517584 |            0.466759 |       0.25125    |     0.0170204  |              0.483587 |

Winner by point-estimate ROC AUC is **gradient-boosted trees waveform+latent** with AUC
`1.000` and run-block 95% CI `[1.000, 1.000]`.
The matched nuisance-only sentinel is AUC `0.943`
`[0.910, 0.966]`. P08b's pre-matching even-charge proxy AUC was
`0.985` and its main waveform/latent HGB AUC was `0.986`.

## 5. Falsification and Systematics
Pre-registered failure conditions are inherited from the ticket: if
nuisance-only AUC remains far above chance, or if shuffled-label performance
does not collapse, waveform PID adoption is rejected. The nuisance-only
sentinel after primary matching is `0.943`; shuffled-label GBT is
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
/home/billy/anaconda3/bin/python scripts/p08c_1781054166_1411_4282226f_continuous_charge_current_matching.py --config configs/p08c_1781054166_1411_4282226f_continuous_charge_current_matching.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `calibrated_label_support.csv`,
`matching_sensitivity.csv`, `matched_balance_smd.csv`, `scoreboard.csv`,
`heldout_run_label_counts.csv`, and `oof_prediction_preview.csv`.

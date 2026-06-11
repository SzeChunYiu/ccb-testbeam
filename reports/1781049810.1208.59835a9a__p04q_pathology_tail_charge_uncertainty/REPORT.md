# P04q Pathology-Tail Charge Uncertainty Propagation

- **Ticket:** `1781049810.1208.59835a9a`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT `HRDv` branches only.
- **Split:** leave-one-evaluation-run-out over runs 58-65; calibration runs are removed from the fit set inside each fold.
- **Config:** `configs/p04q_1781049810_1208_59835a9a_pathology_tail_charge_uncertainty.json`
- **Git commit:** `7352d3c9a882ce8bdf3f70c491db7fc154480f42`

## Abstract

The winning P04q method is strong_traditional_huber: retained charge res68 0.0164, full-sample charge res68 0.0322, 90% conformal coverage 0.884, and abstention coverage 0.505. The strong traditional Huber/template baseline gives retained charge res68 0.0164, full-sample charge res68 0.0322, coverage90 0.884, and abstention coverage 0.505. The raw ROOT reproduction gate matched the S00 selected-pulse count 640737 exactly and the dynamic-only pathology support count 65636 exactly.

## 1. Reproduction Gate

The ROOT-level gate is evaluated before duplicate-readout target cleaning, modeling, atom assignment, or interval calibration. The median-first-four selector is the S00 selected-pulse definition; the dynamic-range selector is the S00c pathology-tail support extension.

| quantity                   |   report_value |   reproduced |   delta |   tolerance | pass   |
|:---------------------------|---------------:|-------------:|--------:|------------:|:-------|
| median_first_four_selected |         640737 |       640737 |       0 |           0 | True   |
| dynamic_range_selected     |         706373 |       706373 |       0 |           0 | True   |
| dynamic_only               |          65636 |        65636 |       0 |           0 | True   |
| median_only                |              0 |            0 |       0 |           0 | True   |

Run-level selected-pulse counts are retained in `counts_by_run.csv`; all reproduced quantities have zero tolerance.

## 2. Data, Atoms, and Target

For each selected even B-stack pulse, the target is the positive-lobe charge of the opposite-polarity duplicate readout,

`y_i = sum_t max(-x_odd,i(t), 0)`,

with `y_i >= 100` ADC-samples. Predictors see only the even-channel waveform and even-channel summaries. The support atom is

`a_i = (stave, lowering_axis, anomaly_taxon, saturation_stratum, run_family)`,

where `lowering_axis` separates median-selected from dynamic-only rows, `anomaly_taxon` is assigned from baseline lowering, early/pretrigger fraction, late-tail fraction, and template-charge shift, and `saturation_stratum` marks dynamic amplitude at or above 7000 ADC.

## 3. Methods

All point models predict `log(y_i)`. The strong traditional baseline is a standardized Huber regression on log peak, positive integral, dynamic amplitude, template charge, template loss, baseline lowering, pulse-shape summaries, and one-hot pathology atoms. This is the pre-registered duplicate-readout Huber/template charge closure baseline stratified by lowering axis, anomaly taxon, saturation boundary, and run family.

The ML/NN benchmark includes ridge regression, gradient-boosted trees (`HistGradientBoostingRegressor`), MLP regression, a compact 1D-CNN over the 18-sample waveform plus tabular atoms, and a new `wavegate_interval_net`. The new model gates a convolutional waveform embedding by pathology/support tabular variables before a residual regression head. A shuffled-target GBT sentinel is retained as a leakage/null diagnostic.

## 4. Conformal Uncertainty

For held-out run `r`, fit runs exclude `r`; calibration runs are a deterministic run subset also removed from fitting. For method `m`, calibration residuals are

`e_i^(m) = |hat y_i^(m) - y_i| / max(y_i, 1)`.

The 68% and 90% half-widths are empirical residual quantiles inside the exact support cell when possible, otherwise inside `(lowering_axis, anomaly_taxon, saturation_stratum)`, otherwise globally. The abstention threshold is learned per fold and method as the configured calibration quantile of 90% half-widths; retained rows satisfy `q90 <= tau_m,r`.

## 5. Head-to-Head Results

| method                   | method_family   |      n |   bias_median_frac | bias_median_frac_ci95                            |   charge_res68_abs_frac | charge_res68_abs_frac_ci95                  |   coverage90 | coverage90_ci95                          |   abstention_coverage | abstention_coverage_ci95                  |   retained_charge_res68_abs_frac |   primary_rank |
|:-------------------------|:----------------|-------:|-------------------:|:-------------------------------------------------|------------------------:|:--------------------------------------------|-------------:|:-----------------------------------------|----------------------:|:------------------------------------------|---------------------------------:|---------------:|
| strong_traditional_huber | traditional     | 153148 |        0.000931089 | [-0.00019976540035949165, 0.0023742362994949567] |               0.0321607 | [0.020560976303247054, 0.04636503067254747] |     0.883544 | [0.8625382735576984, 0.9103582131650874] |              0.504773 | [0.29145655971371376, 0.6796995655450049] |                        0.0164108 |              1 |
| gradient_boosted_trees   | ml_nn           | 153148 |        0.00291964  | [0.0016620845164558506, 0.004373670151593267]    |               0.0280019 | [0.022350100551509742, 0.03243074054586971] |     0.890877 | [0.8710051171498053, 0.9116169808511267] |              0.571787 | [0.3751872011091911, 0.7420229418701239]  |                        0.018486  |              2 |
| mlp                      | ml_nn           | 153148 |       -0.0142447   | [-0.059074330567746774, -0.0005490043658393595]  |               0.094764  | [0.054795657281406146, 0.2916364562313793]  |     0.822107 | [0.666085149980014, 0.8969531511783759]  |              0.524506 | [0.3279060828150422, 0.6597741139478164]  |                        0.0698171 |              3 |
| ridge                    | ml_nn           | 153148 |        0.0138222   | [-1.8691245158673067e-05, 0.02847574075960246]   |               0.107548  | [0.09823424783841264, 0.11707229628905017]  |     0.880103 | [0.8593271736246865, 0.9042446610030056] |              0.475847 | [0.31032501160634773, 0.6184369657329273] |                        0.0786385 |              4 |
| wavegate_interval_net    | ml_nn           | 153148 |       -0.0083545   | [-0.10537672900543311, 4.232769051406765]        |               0.438347  | [0.23070276848742235, 8.107202840033851]    |     0.805861 | [0.5958667451414589, 0.9082298181872199] |              0.543272 | [0.3552438099916085, 0.6981133160138335]  |                        0.282366  |              5 |
| cnn_1d                   | ml_nn           | 153148 |       -0.00153336  | [-0.10643386283094287, 3.9754969047900626]       |               0.462376  | [0.26166775467276915, 7.618200398017504]    |     0.799534 | [0.5925252621960829, 0.9006347979609114] |              0.531297 | [0.28331389593267553, 0.6937576238648143] |                        0.315688  |              6 |
| shuffled_target_gbt      | sentinel        | 153148 |        0.0425529   | [-0.05572439572106808, 0.14849090833379336]      |               0.673638  | [0.620268411537081, 0.8346049747727429]     |     0.897184 | [0.8707078164554231, 0.9171800857984312] |              0.631585 | [0.42490956024312426, 0.7918037887148346] |                        0.539101  |              7 |

**Winner:** `strong_traditional_huber`. The winner is selected by the pre-registered lexicographic rule: among real methods with 90% conformal coverage at least 0.84 and abstention coverage at least 0.50, minimize retained charge res68; break ties by full-sample charge res68, downstream proxy abs68, and absolute bias. If no method satisfies the gates, the same ordering is applied after marking gate failure.

## 6. Downstream Range-Energy Proxy

The downstream consumer proxy is an event-level weighted log-charge sum,

`E_proxy = sum_{pulses in event} w_stave log(1 + q_stave)`,

with increasing B2/B4/B6/B8 weights. It is not a calibrated proton energy; it is a monotone stress test for whether charge uncertainty would propagate into a range/PID-like consumer.

| method                   |   event_n |   proxy_bias_median | proxy_bias_median_ci95                          |   proxy_abs68 | proxy_abs68_ci95                            |
|:-------------------------|----------:|--------------------:|:------------------------------------------------|--------------:|:--------------------------------------------|
| gradient_boosted_trees   |     82958 |          0.00417596 | [0.0024114537062170705, 0.00701887436167019]    |     0.0424449 | [0.03039032097203125, 0.06170015392307934]  |
| strong_traditional_huber |     82958 |          0.00031938 | [-0.0010373466301692778, 0.0020241622962806623] |     0.0656084 | [0.027246266259924445, 0.12332354645908307] |
| ridge                    |     82958 |          0.020379   | [-0.0015509052814941522, 0.04117042907834475]   |     0.168446  | [0.12366179695739454, 0.2515935073878664]   |
| mlp                      |     82958 |         -0.0248964  | [-0.14670066672043305, -0.0009749359133508516]  |     0.190859  | [0.08659964790894864, 0.4685846628754431]   |
| shuffled_target_gbt      |     82958 |          0.0310565  | [-0.14179926034545356, 0.23844225991076742]     |     1.14184   | [0.9978715117471141, 1.4645286607367747]    |
| wavegate_interval_net    |     82958 |         -0.0163401  | [-0.16370222238547716, 1.7862294486127985]      |     1.37843   | [0.38989398038342893, 2.8118677986915785]   |
| cnn_1d                   |     82958 |         -0.00665222 | [-0.17623112095669607, 1.6851224139532337]      |     1.45698   | [0.4465884215919843, 2.694208653602101]     |

## 7. Atom Systematics

| lowering_axis   | anomaly_taxon     | saturation_stratum   | method                   |      n |   charge_res68_abs_frac |   coverage90 |   abstention_coverage |
|:----------------|:------------------|:---------------------|:-------------------------|-------:|------------------------:|-------------:|----------------------:|
| median_selected | baseline_lowering | sat_boundary         | strong_traditional_huber |   1791 |              0.378532   |     0.879955 |              0        |
| dynamic_only    | baseline_lowering | below_sat            | strong_traditional_huber |  13180 |              0.709764   |     0.882322 |              0        |
| median_selected | baseline_lowering | below_sat            | strong_traditional_huber |  15345 |              0.793456   |     0.900749 |              0        |
| median_selected | template_shift    | sat_boundary         | strong_traditional_huber |   5309 |              0.00937486 |     0.886796 |              0.46845  |
| median_selected | template_shift    | below_sat            | strong_traditional_huber | 117132 |              0.0180668  |     0.881262 |              0.638024 |
| dynamic_only    | template_shift    | below_sat            | strong_traditional_huber |    250 |              0.407474   |     0.932    |              0        |

Atom tables expose the main systematic: interval widths and abstention are dominated by large-baseline-lowering and saturation-boundary cells, not by nominal median-selected pulses.

## 8. Leakage and Negative Controls

- Feature exclusions: odd_waveform, odd_charge_as_feature, odd_time, event_id_as_feature, heldout_run_labels.
- Train/evaluation run overlap: `False`.
- Torch available: `True`.
- The shuffled-target GBT sentinel is included in all summary tables and is not eligible to win.

## 9. Hypothesis and Next Experiment

Hypothesis: the charge-uncertainty problem is mostly an atom-support problem, not a generic waveform-representation problem. Gradient-boosted trees improve the full-sample and event-proxy residuals, but the traditional Huber/template model wins the retained calibrated region because baseline-lowering atoms force wide conformal intervals and abstention. A decisive follow-up should test whether the same atom-conditional intervals protect a downstream PID decision boundary, not just duplicate-readout charge closure.

- **Proposed ticket:** P04r atom-conditional charge intervals at PID decision boundaries.
- **Question:** do P04q conformal intervals preserve range/PID decisions after propagating B2/B4/B6/B8 charge uncertainty into event-level topology bands?
- **Expected information gain:** distinguishes a merely accurate duplicate-readout charge model from an uncertainty model that is useful to downstream consumers; falsifies P04q if nominal 90% intervals under-cover near PID boundaries.

## 10. Caveats

- The duplicate readout is an external closure target, not a beam-energy truth label.
- Conformal exchangeability is only approximate because support cells can be sparse and run-family dependent; the report therefore gives run-block bootstrap CIs and atom tables.
- The range-energy proxy is deliberately monotone and dimensionless. It tests propagation sensitivity but should not be interpreted as a calibrated energy residual.
- NN models are small and intentionally capped so the benchmark is reproducible in the worker environment; a larger GPU sweep could change model ordering but must preserve the run-held-out design.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04q_1781049810_1208_59835a9a_pathology_tail_charge_uncertainty.py --config configs/p04q_1781049810_1208_59835a9a_pathology_tail_charge_uncertainty.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `method_summary.csv`, `method_by_run.csv`, `event_proxy_metrics.csv`, `atom_systematics.csv`, `fold_diagnostics.csv`, and `heldout_predictions.csv`.

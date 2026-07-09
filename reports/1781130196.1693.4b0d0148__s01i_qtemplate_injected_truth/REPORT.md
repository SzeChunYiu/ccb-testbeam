# S01i - q-template atom transfer to injected pile-up/dropout truth
- Study ID:      S01i
- Title:         q-template atom transfer to injected pile-up/dropout truth
- Date:          2026-07-09
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S01h
- Data anchor:   640,737 selected B-stave pulses

**ML wins: ROC AUC 0.9653 vs 0.5346 (Delta=0.4307); injected truth is external to q_template residuals.**

## Reproduction gate

Command: `/home/billy/anaconda3/bin/python scripts/s01i_1781130196_1693_4b0d0148_qtemplate_injected_truth.py --config configs/s01i_1781130196_1693_4b0d0148_qtemplate_injected_truth.yaml`
Expected: 640,737 selected B-stave pulses from raw ROOT (`HRDv`, baseline median samples 0-3, even B-stave channels B2/B4/B6/B8, amplitude > 1000 ADC).
Seed: numpy/sklearn/torch random_state = 1781130196.

| quantity                                         |   expected |   reproduced |   delta | pass   |
|:-------------------------------------------------|-----------:|-------------:|--------:|:-------|
| selected B-stave pulses with amplitude >1000 ADC |     640737 |       640737 |       0 | True   |

## Key metrics table

| method                           | family           |     n |   positives |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |
|:---------------------------------|:-----------------|------:|------------:|----------:|-------------:|--------------:|--------------------:|------------:|-------------:|
| atom_gated_cnn_new               | new_architecture | 21613 |       10800 |  0.965302 |     0.961328 |      0.96845  |            0.975719 |    0.973844 |     0.977573 |
| mlp                              | nn               | 21613 |       10800 |  0.961729 |     0.958114 |      0.965005 |            0.973242 |    0.971048 |     0.975234 |
| gradient_boosted_trees           | ml               | 21613 |       10800 |  0.952304 |     0.948713 |      0.955311 |            0.964622 |    0.962313 |     0.966895 |
| ridge                            | ml               | 21613 |       10800 |  0.855266 |     0.852725 |      0.858555 |            0.87824  |    0.87474  |     0.881524 |
| 1d_cnn                           | nn               | 21613 |       10800 |  0.844814 |     0.837912 |      0.851134 |            0.857961 |    0.851278 |     0.865    |
| traditional_smoothed_atom_table  | traditional      | 21613 |       10800 |  0.534647 |     0.529219 |      0.540868 |            0.532655 |    0.526287 |     0.5415   |
| traditional_analytic_shape_score | traditional      | 21613 |       10800 |  0.445979 |     0.440779 |      0.452998 |            0.48062  |    0.470663 |     0.490204 |

## Physics motivation

S01h showed that q-template support-risk atoms strongly predict the q-template residual itself. This study replaces that self-referential label with deterministic injected pile-up and dropout truth, asking whether the same atoms and waveform models identify externally imposed pathologies relevant to timing tails and pile-up rejection.

## Methodology

Data selection follows the S00 raw ROOT gate exactly. The balanced benchmark samples at most 900 pulses per `(run, stave)` cell before injection to prevent the largest runs and staves from dominating the classifier. The split is run-blocked by group: Sample I calibration, Sample I analysis, and Sample II calibration train the models; Sample II analysis runs 58, 59, 60, 61, 62, 63, and 65 are held out.

For each selected waveform `x(t)` normalized by its own peak, the truth generator draws `y=0` clean or `y=1` injected. Positive examples are split between two-pulse overlays and dropouts. Pile-up is `x'(t)=x(t)+a d(t-s)`, with donor waveform `d`, scale `a in [0.18,0.55]`, and shift `s in {3,...,8}` samples. Dropout is `x'(t)=x(t)` before a sampled start and `k x(t)-0.20` afterward, with `k in [0.05,0.35]`. The label is therefore external to q_template residuals and event identifiers.

Feature atoms match S01h: stave, amplitude bin, peak phase, saturation, baseline offset, delayed peak, dropout proxy, topology, area/peak, late fraction, post-peak minimum, and derivative extrema. The traditional analytic score is a hand-built secondary-peak plus dropout score. The stronger traditional table estimates smoothed atom risk, `p_c=(n_c+ + alpha p0)/(N_c + alpha)` with `alpha=20`. ML methods are ridge, gradient-boosted trees, MLP, 1D-CNN, and a new atom-gated CNN. The atom-gated CNN multiplies convolutional channels by a learned sigmoid gate from atom features before pooling.

Leakage controls are structural: no numeric run, event number, or q_template residual is a feature; evaluation is leave-run-family-out; CIs resample held-out runs, not pulses. The injected label is generated after raw reproduction with a fixed seed and does not depend on q_template.

## Results

Held-out run diagnostics:

| method                           |   run |    n |   positives |   roc_auc |   average_precision |
|:---------------------------------|------:|-----:|------------:|----------:|--------------------:|
| 1d_cnn                           |    58 | 1890 |         973 |  0.825549 |            0.855926 |
| 1d_cnn                           |    59 | 3600 |        1772 |  0.847118 |            0.851546 |
| 1d_cnn                           |    60 | 3600 |        1760 |  0.837817 |            0.850324 |
| 1d_cnn                           |    61 | 3600 |        1825 |  0.844524 |            0.866966 |
| 1d_cnn                           |    62 | 3600 |        1797 |  0.847253 |            0.855717 |
| 1d_cnn                           |    63 | 3153 |        1619 |  0.863048 |            0.875338 |
| 1d_cnn                           |    65 | 2170 |        1054 |  0.844229 |            0.850518 |
| atom_gated_cnn_new               |    58 | 1890 |         973 |  0.953841 |            0.9707   |
| atom_gated_cnn_new               |    59 | 3600 |        1772 |  0.966166 |            0.975291 |
| atom_gated_cnn_new               |    60 | 3600 |        1760 |  0.971347 |            0.979564 |
| atom_gated_cnn_new               |    61 | 3600 |        1825 |  0.961387 |            0.973682 |
| atom_gated_cnn_new               |    62 | 3600 |        1797 |  0.968088 |            0.977283 |
| atom_gated_cnn_new               |    63 | 3153 |        1619 |  0.965672 |            0.976417 |
| atom_gated_cnn_new               |    65 | 2170 |        1054 |  0.964414 |            0.974233 |
| gradient_boosted_trees           |    58 | 1890 |         973 |  0.946763 |            0.96527  |
| gradient_boosted_trees           |    59 | 3600 |        1772 |  0.955682 |            0.965367 |
| gradient_boosted_trees           |    60 | 3600 |        1760 |  0.952792 |            0.964435 |
| gradient_boosted_trees           |    61 | 3600 |        1825 |  0.945131 |            0.959063 |
| gradient_boosted_trees           |    62 | 3600 |        1797 |  0.957262 |            0.966953 |
| gradient_boosted_trees           |    63 | 3153 |        1619 |  0.956565 |            0.968803 |
| gradient_boosted_trees           |    65 | 2170 |        1054 |  0.949842 |            0.963475 |
| mlp                              |    58 | 1890 |         973 |  0.955504 |            0.970614 |
| mlp                              |    59 | 3600 |        1772 |  0.964077 |            0.974813 |
| mlp                              |    60 | 3600 |        1760 |  0.966554 |            0.975733 |
| mlp                              |    61 | 3600 |        1825 |  0.955076 |            0.968823 |
| mlp                              |    62 | 3600 |        1797 |  0.96636  |            0.97627  |
| mlp                              |    63 | 3153 |        1619 |  0.963062 |            0.974823 |
| mlp                              |    65 | 2170 |        1054 |  0.95743  |            0.969669 |
| ridge                            |    58 | 1890 |         973 |  0.859286 |            0.878233 |
| ridge                            |    59 | 3600 |        1772 |  0.855046 |            0.874393 |
| ridge                            |    60 | 3600 |        1760 |  0.852353 |            0.871816 |
| ridge                            |    61 | 3600 |        1825 |  0.85276  |            0.883337 |
| ridge                            |    62 | 3600 |        1797 |  0.858592 |            0.883664 |
| ridge                            |    63 | 3153 |        1619 |  0.850361 |            0.877613 |
| ridge                            |    65 | 2170 |        1054 |  0.864476 |            0.877967 |
| traditional_analytic_shape_score |    58 | 1890 |         973 |  0.475771 |            0.506739 |
| traditional_analytic_shape_score |    59 | 3600 |        1772 |  0.444559 |            0.488267 |
| traditional_analytic_shape_score |    60 | 3600 |        1760 |  0.436608 |            0.458116 |
| traditional_analytic_shape_score |    61 | 3600 |        1825 |  0.452158 |            0.496771 |
| traditional_analytic_shape_score |    62 | 3600 |        1797 |  0.449084 |            0.482872 |
| traditional_analytic_shape_score |    63 | 3153 |        1619 |  0.438436 |            0.490459 |
| traditional_analytic_shape_score |    65 | 2170 |        1054 |  0.442434 |            0.469684 |
| traditional_smoothed_atom_table  |    58 | 1890 |         973 |  0.539636 |            0.550199 |
| traditional_smoothed_atom_table  |    59 | 3600 |        1772 |  0.532651 |            0.527129 |
| traditional_smoothed_atom_table  |    60 | 3600 |        1760 |  0.546863 |            0.533863 |
| traditional_smoothed_atom_table  |    61 | 3600 |        1825 |  0.52407  |            0.528399 |
| traditional_smoothed_atom_table  |    62 | 3600 |        1797 |  0.528287 |            0.525827 |
| traditional_smoothed_atom_table  |    63 | 3153 |        1619 |  0.536441 |            0.551059 |
| traditional_smoothed_atom_table  |    65 | 2170 |        1054 |  0.540843 |            0.522102 |

Subtype diagnostics compare each injected subtype against clean held-out pulses:

| method                           | subtype_vs_clean   |     n |   positives |   roc_auc |   average_precision |
|:---------------------------------|:-------------------|------:|------------:|----------:|--------------------:|
| 1d_cnn                           | pileup             | 16225 |        5412 |  0.710135 |            0.481837 |
| 1d_cnn                           | dropout            | 16201 |        5388 |  0.980093 |            0.954462 |
| atom_gated_cnn_new               | pileup             | 16225 |        5412 |  0.931193 |            0.920707 |
| atom_gated_cnn_new               | dropout            | 16201 |        5388 |  0.999562 |            0.999271 |
| gradient_boosted_trees           | pileup             | 16225 |        5412 |  0.905884 |            0.880443 |
| gradient_boosted_trees           | dropout            | 16201 |        5388 |  0.998932 |            0.99831  |
| mlp                              | pileup             | 16225 |        5412 |  0.924729 |            0.915869 |
| mlp                              | dropout            | 16201 |        5388 |  0.998895 |            0.99793  |
| ridge                            | pileup             | 16225 |        5412 |  0.741107 |            0.560153 |
| ridge                            | dropout            | 16201 |        5388 |  0.969934 |            0.957439 |
| traditional_analytic_shape_score | pileup             | 16225 |        5412 |  0.579439 |            0.375764 |
| traditional_analytic_shape_score | dropout            | 16201 |        5388 |  0.311925 |            0.265358 |
| traditional_smoothed_atom_table  | pileup             | 16225 |        5412 |  0.51423  |            0.34472  |
| traditional_smoothed_atom_table  | dropout            | 16201 |        5388 |  0.555156 |            0.383766 |

The winner named in `result.json` is `atom_gated_cnn_new`. The AUC difference versus the best traditional baseline is 0.4307.

## Interpretation

The benchmark tests transfer from S01h q-template atoms to labels that are not q-template residuals. If the atom-gated CNN wins, the result supports the interpretation that q-template support atoms capture real waveform morphology useful for pile-up/dropout recognition. It does not prove that natural high-q events are identical to these injected pathologies; it only closes the first external-truth transfer step.

## MC verdict

MC validation not yet run - this observable is an injected-data stress test on real raw waveforms. A future MC/overlay comparison should test whether the same atom response appears under detector-realistic pulse superposition and electronics dropout.

## Open questions

1. S01j: q-template atom transfer to real external overlay hand-scan. Falsifying test: the atom-gated CNN loses its advantage on blinded real-overlay labels while succeeding on S01i injection.

## Provenance

Git commit:        9b02bb7da346f67b2c44033e363d0427a7a2b3db
Data SHA256:       raw ROOT files are immutable under `data/root/root`; per-output hashes are in `manifest.json`.
Python:            3.7.6
scikit-learn / numpy / torch: recorded by the execution environment; model hyperparameters are in the config.
Run host / job:    local worker testbeam-laptop-4
Artifacts:         `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `subtype_metrics.csv`, `heldout_predictions.csv.gz`, `injected_truth_benchmark_sample.csv.gz`, and figures.

## Systematics and caveats

- Injection realism is the leading systematic: deterministic overlays and dropouts are controlled truth, not a full electronics simulation.
- Bootstrap CIs use held-out runs as blocks; pulse-level resampling would understate uncertainty.
- The atom table is interpretable but can only exploit discretized support cells; the CNNs can use detailed waveform shape.
- A win here is an external-truth transfer result, not a recommendation to veto all high-q pulses.

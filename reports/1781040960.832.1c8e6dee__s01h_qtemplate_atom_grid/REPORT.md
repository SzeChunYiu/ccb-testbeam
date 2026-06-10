# S01h: q-template run-stave leakage atom grid

**Ticket:** `1781040960.832.1c8e6dee`  
**Worker:** `testbeam-laptop-4`  
**Date:** 2026-06-11

## Abstract

This study atomizes the S01 q_template residual into run, stave, amplitude, peak-phase, saturation, baseline, delayed-peak, dropout, and topology factors. The raw ROOT selection is reproduced first, then a run-heldout benchmark asks whether a train-defined high-q flag can be predicted from atoms without passing q_template itself as a feature. The held-out winner is **atom_gated_cnn_new** with ROC AUC **0.9980** [0.9975, 0.9984] and AP **0.9890** [0.9867, 0.9911]. The strongest traditional atom table is **traditional_smoothed_atom_table** with AUC **0.9743** [0.9708, 0.9782].

## Raw ROOT Reproduction

For every B-stack ROOT file, `HRDv` was reshaped to `(8,18)`, samples 0-3 defined the channel baseline, even physical B-stave channels B2/B4/B6/B8 were baseline-subtracted, and a row was selected when `max_t(v(t)-baseline)>1000 ADC`. This is the S00 gate used by the q_template source table.

| quantity                                         |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| selected B-stave pulses with amplitude >1000 ADC |         640737 |       640737 |       0 |           0 | True   |

The total selected count is **640,737**, matching the registered **640,737** count with zero delta. The q_template join is one-to-one on `(run,eventno,evt,stave,channel)` and yields **640,737** rows.

## Statistical Target and Split

Let `q_i` be the S01 template RMSE for pulse `i`. The training set is Sample I calibration, Sample I analysis, and Sample II calibration; the held-out set is Sample II analysis runs `58, 59, 60, 61, 62, 63, 65`. The high-q label is defined only from training rows:

`y_i = 1[q_i > Q_0.90({q_j: j in train})]`.

Thus the held-out high-q rate is evaluated against a threshold fixed before reading held-out labels. No model receives `q_i`, event IDs, or numeric run IDs as features. Confidence intervals are 95% nonparametric bootstraps over held-out runs.

## Atom Definitions

The atom set is deliberately conventional: stave; fixed amplitude bin; peak-phase bin (`early`, `nominal`, `late`, `very_late`); saturation proxy `A>=6800 ADC`; baseline proxy top-decile absolute baseline offset within stave; delayed peak proxy `peak_sample>=8`; dropout proxy low area/peak or post-peak undershoot; and topology proxy `B2` versus downstream `B4/B6/B8`. The run atom is reported in grids but withheld from predictive features because the held-out run labels must generalize to unseen runs.

## Methods

The traditional method is a smoothed atom-risk table. In training rows, cells are keyed by `(stave, amplitude bin, peak phase, saturation, baseline, delayed peak, dropout, topology)`. For cell `c`,

`p_hat_c = (n_high,c + alpha p_global) / (n_c + alpha)`,

with `alpha=20.0`; held-out rows receive their train-cell `p_hat_c`, falling back to `p_global` for unseen cells. This is a strong non-ML conditional support map because it directly encodes the requested detector atoms while remaining run-heldout.

ML/NN competitors are ridge, gradient-boosted trees, MLP, 1D-CNN, and a new atom-gated CNN. Ridge/GBT/MLP see engineered atom variables and one-hot categorical atoms; the 1D-CNN sees the normalized 18-sample waveform; the atom-gated CNN combines a temporal convolution with atom gates, which is sensible here because q_template failures can be local shape distortions whose relevance depends on amplitude, stave, and baseline context.

## Head-to-head Benchmark

| method                          | family           |     n |   positives |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |   ap_ci_low |   ap_ci_high |
|:--------------------------------|:-----------------|------:|------------:|----------:|-------------:|--------------:|--------------------:|------------:|-------------:|
| atom_gated_cnn_new              | new_architecture | 36500 |        4539 |  0.997973 |     0.997495 |      0.998391 |            0.989023 |    0.986706 |     0.991059 |
| mlp                             | nn               | 36500 |        4539 |  0.997493 |     0.996932 |      0.998026 |            0.988382 |    0.986062 |     0.990507 |
| gradient_boosted_trees          | ml               | 36500 |        4539 |  0.997184 |     0.996735 |      0.997726 |            0.989383 |    0.988278 |     0.990892 |
| traditional_smoothed_atom_table | traditional      | 36500 |        4539 |  0.974318 |     0.970763 |      0.978248 |            0.897893 |    0.875747 |     0.91175  |
| ridge                           | ml               | 36500 |        4539 |  0.966079 |     0.964575 |      0.968059 |            0.85203  |    0.833854 |     0.868746 |
| 1d_cnn                          | nn               | 36500 |        4539 |  0.922241 |     0.905021 |      0.932776 |            0.886623 |    0.86035  |     0.899866 |

Per-run held-out diagnostics:

| method                          |   run |    n |   positives |   roc_auc |   average_precision |
|:--------------------------------|------:|-----:|------------:|----------:|--------------------:|
| 1d_cnn                          |    58 | 2790 |         157 |  0.832269 |            0.753882 |
| 1d_cnn                          |    59 | 6319 |         901 |  0.918976 |            0.881838 |
| 1d_cnn                          |    60 | 6327 |         830 |  0.941227 |            0.910272 |
| 1d_cnn                          |    61 | 6459 |         810 |  0.912088 |            0.88726  |
| 1d_cnn                          |    62 | 6329 |         862 |  0.944393 |            0.91343  |
| 1d_cnn                          |    63 | 5206 |         682 |  0.913012 |            0.877929 |
| 1d_cnn                          |    65 | 3070 |         297 |  0.903319 |            0.842318 |
| atom_gated_cnn_new              |    58 | 2790 |         157 |  0.999434 |            0.99112  |
| atom_gated_cnn_new              |    59 | 6319 |         901 |  0.997841 |            0.989696 |
| atom_gated_cnn_new              |    60 | 6327 |         830 |  0.998144 |            0.988872 |
| atom_gated_cnn_new              |    61 | 6459 |         810 |  0.996816 |            0.98554  |
| atom_gated_cnn_new              |    62 | 6329 |         862 |  0.998369 |            0.992616 |
| atom_gated_cnn_new              |    63 | 5206 |         682 |  0.998208 |            0.990048 |
| atom_gated_cnn_new              |    65 | 3070 |         297 |  0.997807 |            0.982739 |
| gradient_boosted_trees          |    58 | 2790 |         157 |  0.999485 |            0.992772 |
| gradient_boosted_trees          |    59 | 6319 |         901 |  0.997609 |            0.989289 |
| gradient_boosted_trees          |    60 | 6327 |         830 |  0.99687  |            0.988193 |
| gradient_boosted_trees          |    61 | 6459 |         810 |  0.99758  |            0.988286 |
| gradient_boosted_trees          |    62 | 6329 |         862 |  0.996702 |            0.992543 |
| gradient_boosted_trees          |    63 | 5206 |         682 |  0.996695 |            0.988272 |
| gradient_boosted_trees          |    65 | 3070 |         297 |  0.99592  |            0.988232 |
| mlp                             |    58 | 2790 |         157 |  0.999262 |            0.988128 |
| mlp                             |    59 | 6319 |         901 |  0.997071 |            0.987668 |
| mlp                             |    60 | 6327 |         830 |  0.997977 |            0.989498 |
| mlp                             |    61 | 6459 |         810 |  0.996236 |            0.984281 |
| mlp                             |    62 | 6329 |         862 |  0.997629 |            0.991957 |
| mlp                             |    63 | 5206 |         682 |  0.997854 |            0.99052  |
| mlp                             |    65 | 3070 |         297 |  0.997686 |            0.984507 |
| ridge                           |    58 | 2790 |         157 |  0.96068  |            0.77243  |
| ridge                           |    59 | 6319 |         901 |  0.964217 |            0.84211  |
| ridge                           |    60 | 6327 |         830 |  0.966406 |            0.866313 |
| ridge                           |    61 | 6459 |         810 |  0.963724 |            0.832907 |
| ridge                           |    62 | 6329 |         862 |  0.970197 |            0.884953 |
| ridge                           |    63 | 5206 |         682 |  0.965171 |            0.85773  |
| ridge                           |    65 | 3070 |         297 |  0.969087 |            0.828883 |
| traditional_smoothed_atom_table |    58 | 2790 |         157 |  0.974198 |            0.815378 |
| traditional_smoothed_atom_table |    59 | 6319 |         901 |  0.9735   |            0.909697 |
| traditional_smoothed_atom_table |    60 | 6327 |         830 |  0.976958 |            0.905088 |
| traditional_smoothed_atom_table |    61 | 6459 |         810 |  0.967978 |            0.867789 |
| traditional_smoothed_atom_table |    62 | 6329 |         862 |  0.982098 |            0.925703 |
| traditional_smoothed_atom_table |    63 | 5206 |         682 |  0.968375 |            0.906718 |
| traditional_smoothed_atom_table |    65 | 3070 |         297 |  0.975134 |            0.872657 |

## Atom Grid Results

Largest held-out high-q enrichments by atom:

| atom              | level              |     n |   high_q |     rate |   enrichment_vs_heldout |
|:------------------|:-------------------|------:|---------:|---------:|------------------------:|
| amp_bin           | 6                  |     2 |        2 | 1        |              0.875644   |
| peak_phase_bin    | early              |  4095 |     2915 | 0.711844 |              0.587488   |
| baseline_atom     | 1                  |  6165 |     3916 | 0.635199 |              0.510843   |
| dropout_atom      | 1                  |  6040 |     3558 | 0.589073 |              0.464717   |
| amp_bin           | 0                  |  3241 |     1398 | 0.431348 |              0.306992   |
| amp_bin           | 1                  |  5248 |     1383 | 0.263529 |              0.139173   |
| delayed_peak_atom | 0                  | 19940 |     4149 | 0.208074 |              0.0837181  |
| saturation_atom   | 1                  |   863 |      143 | 0.165701 |              0.0413449  |
| amp_bin           | 5                  |   861 |      141 | 0.163763 |              0.0394069  |
| run               | 59                 |  6319 |      901 | 0.142586 |              0.0182297  |
| run               | 62                 |  6329 |      862 | 0.136198 |              0.0118423  |
| run               | 60                 |  6327 |      830 | 0.131184 |              0.00682765 |
| stave             | B4                 | 10433 |     1367 | 0.131027 |              0.00667039 |
| run               | 63                 |  5206 |      682 | 0.131003 |              0.00664652 |
| topology_atom     | downstream_B468    | 23900 |     3016 | 0.126192 |              0.0018363  |
| peak_phase_bin    | nominal            |  6993 |      880 | 0.12584  |              0.00148396 |
| stave             | B8                 |  4506 |      567 | 0.125832 |              0.00147606 |
| run               | 61                 |  6459 |      810 | 0.125406 |              0.00105025 |
| group             | sample_ii_analysis | 36500 |     4539 | 0.124356 |              0          |
| saturation_atom   | 0                  | 35637 |     4396 | 0.123355 |             -0.00100122 |

Run-stave leakage grid:

|   run | stave   |    n |   high_q |   high_q_rate |   q_median |     q_p90 |   amp_median |   peak_median |
|------:|:--------|-----:|---------:|--------------:|-----------:|----------:|-------------:|--------------:|
|    58 | B2      | 1800 |       72 |     0.04      |  0.0378863 | 0.0778274 |      4145.75 |             7 |
|    58 | B4      |  591 |       64 |     0.108291  |  0.0352624 | 0.147927  |      3037    |             8 |
|    58 | B6      |  285 |       15 |     0.0526316 |  0.0324099 | 0.0848731 |      2723    |             8 |
|    58 | B8      |  114 |        6 |     0.0526316 |  0.0338847 | 0.101682  |      3074    |            10 |
|    59 | B2      | 1800 |      327 |     0.181667  |  0.0440652 | 0.276347  |      3202.75 |             7 |
|    59 | B4      | 1800 |      237 |     0.131667  |  0.0418114 | 0.179316  |      2792.75 |             7 |
|    59 | B6      | 1800 |      223 |     0.123889  |  0.0366408 | 0.160961  |      2648.25 |             8 |
|    59 | B8      |  919 |      114 |     0.124048  |  0.0434434 | 0.151319  |      3091    |             8 |
|    60 | B2      | 1800 |      223 |     0.123889  |  0.0430151 | 0.195257  |      3318.25 |             7 |
|    60 | B4      | 1800 |      242 |     0.134444  |  0.0454    | 0.17257   |      3117.5  |             7 |
|    60 | B6      | 1800 |      233 |     0.129444  |  0.0413235 | 0.179188  |      2976.5  |             7 |
|    60 | B8      |  927 |      132 |     0.142395  |  0.0462591 | 0.166931  |      3392.5  |             7 |
|    61 | B2      | 1800 |      241 |     0.133889  |  0.0432356 | 0.196863  |      3223.25 |             7 |
|    61 | B4      | 1800 |      236 |     0.131111  |  0.0539491 | 0.182505  |      2911    |             7 |
|    61 | B6      | 1800 |      211 |     0.117222  |  0.0404531 | 0.152538  |      2888    |             8 |
|    61 | B8      | 1059 |      122 |     0.115203  |  0.0451582 | 0.14062   |      3274    |             8 |
|    62 | B2      | 1800 |      244 |     0.135556  |  0.0403548 | 0.196367  |      3245.75 |             7 |
|    62 | B4      | 1800 |      259 |     0.143889  |  0.0441587 | 0.212955  |      2908    |             7 |
|    62 | B6      | 1800 |      231 |     0.128333  |  0.0371695 | 0.177172  |      2731    |             8 |
|    62 | B8      |  929 |      128 |     0.137783  |  0.0446207 | 0.181582  |      3204    |             8 |
|    63 | B2      | 1800 |      250 |     0.138889  |  0.0389674 | 0.197402  |      3341    |             7 |
|    63 | B4      | 1800 |      237 |     0.131667  |  0.042769  | 0.202102  |      2784    |             7 |
|    63 | B6      | 1153 |      138 |     0.119688  |  0.0349075 | 0.145616  |      2559    |             8 |
|    63 | B8      |  453 |       57 |     0.125828  |  0.0416328 | 0.150571  |      3083.5  |             8 |
|    65 | B2      | 1800 |      166 |     0.0922222 |  0.0366013 | 0.107624  |      3032.5  |             7 |
|    65 | B4      |  842 |       92 |     0.109264  |  0.0398698 | 0.137423  |      2818    |             8 |
|    65 | B6      |  323 |       31 |     0.0959752 |  0.0295409 | 0.119195  |      2596.5  |             8 |
|    65 | B8      |  105 |        8 |     0.0761905 |  0.0352762 | 0.0802402 |      2833.5  |             8 |

## Interpretation

The atom grid shows whether q_template behaves as a support covariate rather than a hard veto. A safe support covariate should have localized, explainable enrichment, nonzero train-heldout generalization, and no dependence on forbidden identifiers. A hard veto would require a robust downstream gain; this study does not claim that. It shows that high-q risk is partially learnable from amplitude, phase, baseline, dropout, topology, and waveform atoms under a run-heldout split.

## Systematics and Caveats

- The label is a q_template residual flag, not external PID, energy, or timing truth.
- The S01 q_template table was generated previously, but the selected-pulse count and normalized waveforms were rescanned from raw ROOT here before benchmarking.
- Bootstrap units are runs, not pulses; pulse-level statistical errors would be much narrower and misleading.
- Run appears in the explanatory grid, but numeric run ID is excluded from model features to avoid memorizing train runs.
- The q_template residual itself is excluded from all predictors; using q_template to predict high q_template would be a tautological leakage sentinel.

## Verdict

`result.json` names **atom_gated_cnn_new** as the winner. The q_template atom is suitable as a diagnostic support covariate for follow-up studies, but not as a standalone veto or physics observable in this study.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s01h_1781040960_832_1c8e6dee_qtemplate_atom_grid.py --config configs/s01h_1781040960_832_1c8e6dee_qtemplate_atom_grid.yaml
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `heldout_predictions.csv.gz`, `atom_enrichment_grid.csv`, `run_stave_q_leakage_grid.csv`, `benchmark_sample.csv.gz`, and `method_auc_ci.png`.

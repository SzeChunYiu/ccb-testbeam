# P10f: conditional-template q_template tail validation

- **Ticket ID:** `1781027860.942.36c33ff0`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT under `data/root/root`; no Monte Carlo.
- **Config:** `configs/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.json`

## Raw-ROOT reproduction first

The selected-pulse table and the P10a calibration-only empirical q-template reference were rebuilt from raw `HRDv` waveforms before any model comparison.

| quantity                                       |      expected |    reproduced |       delta |   tolerance | pass   |
|:-----------------------------------------------|--------------:|--------------:|------------:|------------:|:-------|
| S00/S01 selected B-stave pulses                | 640737        | 640737        | 0           |       0     | True   |
| analysis selected rows                         | 377362        | 377362        | 0           |       0     | True   |
| P10a calibration-only empirical q_template MSE |      0.044414 |      0.044414 | 2.71402e-11 |       5e-07 | True   |

## Methods

Split is by run. Sample-I analysis runs 44-57 are scored after training only on Sample-I calibration runs 31-42; Sample-II analysis runs 58-63 and 65 are scored after training only on calibration run 64. CIs bootstrap held-out runs.

Baseline traditional method: calibration-only median templates by stave and amplitude bin. Strong traditional method: calibration-only median templates further binned by train-quantile rise-width and tail-summary handles, with hierarchical fallback. ML methods: multi-output ExtraTrees conditional templates from same-pulse local handles. The aggressive ML arm includes tail-summary handles; the no-tail ablation removes `tail_mean_8_17`, `tail_area_10_17`, and `late_over_total`. Run id, event id, event order, other-stave observables, downstream timing labels, and held-out target rows are excluded.

`q_template_mse` uses all aligned samples. `q_tail_mse` is the validation target for this ticket and uses aligned samples with relative index >= `2`.

## Held-out run-bootstrap summary

| fold                                  | method                          |   n_runs |   n_rows |   q_template_mse | q_template_mse_ci95                            |   q_tail_mse | q_tail_mse_ci95                               |
|:--------------------------------------|:--------------------------------|---------:|---------:|-----------------:|:-----------------------------------------------|-------------:|:----------------------------------------------|
| sample_i_analysis_from_sample_i_calib | calibration_amp_median          |       14 |   252266 |       0.0473488  | [0.033032022141308966, 0.06261311071636015]    |   0.0554156  | [0.038831229984157514, 0.07289132467571174]   |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_conditional      |       14 |   252266 |       0.00268483 | [0.001898036651187874, 0.0034635990881111884]  |   0.00296853 | [0.002101335481620436, 0.003850932618869831]  |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_no_tail          |       14 |   252266 |       0.00284726 | [0.0020270079021392213, 0.003627660479304247]  |   0.00317435 | [0.002260767974367966, 0.004030528938472531]  |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_no_tail_shuffled |       14 |   252266 |       0.0626835  | [0.044615686507533, 0.08160876545372625]       |   0.0754848  | [0.054275102747031984, 0.0976481283020837]    |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_shuffled         |       14 |   252266 |       0.0635322  | [0.045286184703872384, 0.08289635240615895]    |   0.0764433  | [0.055126732621145105, 0.09922260678268942]   |
| sample_i_analysis_from_sample_i_calib | traditional_shape_handle_median |       14 |   252266 |       0.0235483  | [0.016952550308694386, 0.03050536093016061]    |   0.0281393  | [0.02043784267775386, 0.03620011172218669]    |
| sample_ii_analysis_from_run64_calib   | calibration_amp_median          |        7 |   125096 |       0.0383189  | [0.028232631965910967, 0.04489375276480483]    |   0.0430088  | [0.03219784711790909, 0.04996314934508866]    |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_conditional      |        7 |   125096 |       0.00312043 | [0.0024428564009729174, 0.0037125819862702395] |   0.00349625 | [0.0027859033784795, 0.004099562730373168]    |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_no_tail          |        7 |   125096 |       0.00325951 | [0.0025516901490276506, 0.0038759232635107096] |   0.00369719 | [0.0029399988718851336, 0.004354219626213057] |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_no_tail_shuffled |        7 |   125096 |       0.055172   | [0.04381591387746077, 0.06348431591095242]     |   0.0656556  | [0.05341488610627447, 0.07475322034911472]    |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_shuffled         |        7 |   125096 |       0.0543233  | [0.043202446265752384, 0.062100498839000394]   |   0.0646829  | [0.05258948793929841, 0.07324927050314782]    |
| sample_ii_analysis_from_run64_calib   | traditional_shape_handle_median |        7 |   125096 |       0.0238132  | [0.018251738493677717, 0.027684502472002867]   |   0.0275921  | [0.021467111893018927, 0.03175097113833573]   |

## Deltas vs calibration median

| fold                                  | comparison                                                   | metric         |      delta | delta_ci95                                     |
|:--------------------------------------|:-------------------------------------------------------------|:---------------|-----------:|:-----------------------------------------------|
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_conditional minus calibration_amp_median      | q_template_mse | -0.044664  | [-0.059316884232280945, -0.03078362488138345]  |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_conditional minus calibration_amp_median      | q_tail_mse     | -0.0524471 | [-0.06937982091151929, -0.03649522545898295]   |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_no_tail minus calibration_amp_median          | q_template_mse | -0.0445016 | [-0.05970895760509836, -0.031536981244099205]  |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_no_tail minus calibration_amp_median          | q_tail_mse     | -0.0522413 | [-0.06833326436035464, -0.03682390375458099]   |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_no_tail_shuffled minus calibration_amp_median | q_template_mse |  0.0153347 | [0.011441014808082864, 0.019339773384404763]   |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_no_tail_shuffled minus calibration_amp_median | q_tail_mse     |  0.0200692 | [0.0152947318398122, 0.025137341770193854]     |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_shuffled minus calibration_amp_median         | q_template_mse |  0.0161833 | [0.012117029425003766, 0.02025249543285298]    |
| sample_i_analysis_from_sample_i_calib | ml_extra_trees_shuffled minus calibration_amp_median         | q_tail_mse     |  0.0210276 | [0.015986561433899166, 0.026552163489070513]   |
| sample_i_analysis_from_sample_i_calib | traditional_shape_handle_median minus calibration_amp_median | q_template_mse | -0.0238005 | [-0.031693323952383716, -0.01624167957405303]  |
| sample_i_analysis_from_sample_i_calib | traditional_shape_handle_median minus calibration_amp_median | q_tail_mse     | -0.0272763 | [-0.03648213239506299, -0.018087722355057616]  |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_conditional minus calibration_amp_median      | q_template_mse | -0.0351985 | [-0.041459020559875624, -0.025981858553120293] |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_conditional minus calibration_amp_median      | q_tail_mse     | -0.0395125 | [-0.046213144042019275, -0.029646590417341506] |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_no_tail minus calibration_amp_median          | q_template_mse | -0.0350594 | [-0.04127530432127935, -0.025680782120030134]  |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_no_tail minus calibration_amp_median          | q_tail_mse     | -0.0393116 | [-0.04582133024815663, -0.029348138353844973]  |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_no_tail_shuffled minus calibration_amp_median | q_template_mse |  0.0168531 | [0.015067003030418432, 0.01851518187904313]    |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_no_tail_shuffled minus calibration_amp_median | q_tail_mse     |  0.0226468 | [0.02047005792073888, 0.024716945785493286]    |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_shuffled minus calibration_amp_median         | q_template_mse |  0.0160044 | [0.014651368471866905, 0.017305375658897237]   |
| sample_ii_analysis_from_run64_calib   | ml_extra_trees_shuffled minus calibration_amp_median         | q_tail_mse     |  0.0216741 | [0.019774915007178925, 0.02340919542342839]    |
| sample_ii_analysis_from_run64_calib   | traditional_shape_handle_median minus calibration_amp_median | q_template_mse | -0.0145057 | [-0.017796778032648904, -0.010274931134484145] |
| sample_ii_analysis_from_run64_calib   | traditional_shape_handle_median minus calibration_amp_median | q_tail_mse     | -0.0154167 | [-0.018786617632887102, -0.0106127732447316]   |

## Leakage checks

| fold                                  | train_eval_run_overlap   |   train_eval_key_overlap |   waveform_hash_overlap_count | uses_run_or_event_features   | uses_downstream_timing_labels   | ml_tail_too_good_triggered   | no_tail_ml_tail_too_good_triggered   |   nn_distance_min |   nn_distance_p01 |   nn_frac_dist_le_1e-06 |
|:--------------------------------------|:-------------------------|-------------------------:|------------------------------:|:-----------------------------|:--------------------------------|:-----------------------------|:-------------------------------------|------------------:|------------------:|------------------------:|
| sample_i_analysis_from_sample_i_calib | []                       |                        0 |                             0 | False                        | False                           | True                         | True                                 |        0.00776509 |         0.0125364 |                       0 |
| sample_ii_analysis_from_run64_calib   | []                       |                        0 |                             0 | False                        | False                           | True                         | True                                 |        0.00950977 |         0.0197339 |                       0 |

A too-good flag fires if real ML tail MSE is less than 25% of its shuffled-target control. Waveform hashes are SHA256 values of normalized 18-sample waveforms quantized at 1e-6.

## Finding

The no-tail ExtraTrees conditional q-tail scores beat the calibration-only amplitude-median baseline with CI-clean run-bootstrap deltas in 2 of 2 folds. The aggressive tail-handle ML arm fired the too-good trigger, consistent with target-proximal tail handles. The no-tail ablation also fired the too-good trigger, so the ML gain is not promoted.

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `heldout_scores_by_run.csv`, `method_summary.csv`, `method_deltas.csv`, `leakage_checks.csv`, and template diagnostics.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.py --config configs/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.json
```

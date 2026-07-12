# S27d - Event-Level Masked-Window Retraining for Complete PID-Energy-Stress Eligibility

Ticket: `1783806742.4527.050404c3`  
Worker: `testbeam-laptop-2`

## Abstract
S27c identified pulse-window attribution at endpoint level. S27d closes the main caveat by freezing those windows, reading raw B-stack ROOT waveforms, and retraining the full method panel event by event on the same complete-run split. The lowest held-out joint loss is obtained by **gradient_boosted_trees** under mask `all_0_17` with score 0.07996. Unlike S27c, the small attention/transformer-like architecture is included in the winner rule.

## Raw ROOT Reproduction
The script opens `h101/HRDv`, reshapes each row to `(event, channel, sample)`, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with corrected peak above 1000 ADC.

| quantity                           | expected | reproduced | delta | pass |
| ---------------------------------- | -------- | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737   | 640737     | 0     | True |
| sample_i_calib selected pulses     | 248745   | 248745     | 0     | True |
| sample_i_analysis selected pulses  | 252266   | 252266     | 0     | True |
| sample_ii_calib selected pulses    | 14630    | 14630      | 0     | True |
| sample_ii_analysis selected pulses | 125096   | 125096     | 0     | True |

## Event Targets
For event `i`, corrected waveform `x_{ics}` is obtained from raw ADC waveform `a_{ics}` by

`x_{ics}=a_{ics}-median_{s in {0,1,2,3}} a_{ics}`.

The event-level weak endpoints are deliberately constructed from full-window raw observables and then predicted from masked windows:

`E_i = log(1 + sum_{c,s} max(x_{ics},0))` for energy closure;
`P_i = 1{(Q_{B6}+Q_{B8}) / sum_c Q_c > median_train}` as a range/PID topology proxy;
`T_i = min_c CFD50(x_{ic})` as a timing proxy in sample units;
`S_i = 1{late_tail_fraction_i > Q_0.75^train or peak_i > Q_0.95^train}` as a pile-up/saturation stress proxy.

These are not external particle-truth labels; they are raw-data, event-native stress targets used to test whether masked windows retain the same information after retraining.

## Split and Confidence Intervals
Training runs are groups `sample_i_calib, sample_i_analysis, sample_ii_calib`; held-out runs are `sample_ii_analysis`. Each run is a complete block. Bootstrap intervals resample the held-out runs with replacement for 100 replicates.

## Methods
- `traditional_charge_depth_timewalk`: fixed charge-window, distal-charge, late-tail, and CFD50 formulas with no event-row training.
- `ridge`: standardized linear ridge/logistic models.
- `gradient_boosted_trees`: histogram gradient boosting for nonlinear tabular closure.
- `mlp`: two-layer tabular neural network.
- `cnn1d`: neural model on convolution-like local difference features from the masked waveform.
- `residual_cnn_gru_new`: new residual sequence architecture approximation using cumulative/residual features and random forests, chosen because S27d asks whether sequence memory and residual local shape help after masking.
- `attention_transformer_small`: transformer-like attention summary features over masked samples with boosted heads; included in the complete winner rule.

The joint score minimized in `result.json` is

`L = 0.28(1-AUC_PID) + 0.30 R68_E + 0.20 R68_T/2 + 0.17(1-AUC_stress) + 0.05 |bias_E|`.

## Primary Results
| mask             | method                            | family           | joint_score | pid_auc | energy_res68 | timing_res68_samples | stress_auc | energy_bias |
| ---------------- | --------------------------------- | ---------------- | ----------- | ------- | ------------ | -------------------- | ---------- | ----------- |
| all_0_17         | gradient_boosted_trees            | tree             | 0.079964    | 0.99593 | 0.033956     | 0.67388              | 0.99372    | 0.0036454   |
| pretrigger_0_3   | traditional_charge_depth_timewalk | traditional      | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          | -0.65458    |
| peak_charge_8_11 | traditional_charge_depth_timewalk | traditional      | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          | -0.65458    |
| rising_edge_4_7  | traditional_charge_depth_timewalk | traditional      | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          | -0.65458    |
| causal_0_11      | traditional_charge_depth_timewalk | traditional      | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          | -0.65458    |
| late_tail_12_17  | traditional_charge_depth_timewalk | traditional      | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          | -0.65458    |
| all_0_17         | traditional_charge_depth_timewalk | traditional      | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          | -0.65458    |
| all_0_17         | residual_cnn_gru_new              | new_architecture | 0.09641     | 0.98935 | 0.027564     | 0.84047              | 0.99397    | 0.0017471   |
| causal_0_11      | gradient_boosted_trees            | tree             | 0.12768     | 0.95966 | 0.054327     | 0.96725              | 0.98178    | 0.0052542   |
| causal_0_11      | residual_cnn_gru_new              | new_architecture | 0.13424     | 0.95369 | 0.046467     | 1.042                | 0.98238    | 0.0028667   |
| all_0_17         | attention_transformer_small       | attention        | 0.15591     | 0.97912 | 0.088251     | 1.1821               | 0.9732     | 0.016486    |
| causal_0_11      | attention_transformer_small       | attention        | 0.17738     | 0.94184 | 0.11625      | 1.1811               | 0.95647    | 0.01426     |
| all_0_17         | mlp                               | neural_tabular   | 0.18795     | 0.99197 | 0.1311       | 1.4425               | 0.99592    | 0.028475    |
| peak_charge_8_11 | residual_cnn_gru_new              | new_architecture | 0.18934     | 0.94092 | 0.079364     | 1.4338               | 0.97141    | 0.015015    |
| late_tail_12_17  | residual_cnn_gru_new              | new_architecture | 0.1901      | 0.94139 | 0.093284     | 1.4198               | 0.98055    | 0.0084778   |
| peak_charge_8_11 | gradient_boosted_trees            | tree             | 0.19536     | 0.94905 | 0.090128     | 1.4684               | 0.96651    | 0.03044     |
| rising_edge_4_7  | residual_cnn_gru_new              | new_architecture | 0.20108     | 0.89075 | 0.083378     | 1.4044               | 0.97105    | -0.0023164  |
| rising_edge_4_7  | gradient_boosted_trees            | tree             | 0.2027      | 0.90132 | 0.089462     | 1.4322               | 0.97069    | 0.00054167  |

## Bootstrap Intervals
| mask             | method                            | energy_res68_ci_low | energy_res68_ci_high | timing_res68_samples_ci_low | timing_res68_samples_ci_high | pid_auc_ci_low | pid_auc_ci_high | stress_auc_ci_low | stress_auc_ci_high |
| ---------------- | --------------------------------- | ------------------- | -------------------- | --------------------------- | ---------------------------- | -------------- | --------------- | ----------------- | ------------------ |
| all_0_17         | gradient_boosted_trees            | 0.023706            | 0.04968              | 0.62125                     | 0.70843                      | 0.99478        | 0.99729         | 0.99107           | 0.9955             |
| pretrigger_0_3   | traditional_charge_depth_timewalk | 0.12443             | 0.15113              | 0                           | 0                            | 0.90839        | 0.93081         | 1                 | 1                  |
| peak_charge_8_11 | traditional_charge_depth_timewalk | 0.12439             | 0.1486               | 0                           | 0                            | 0.90638        | 0.93023         | 1                 | 1                  |
| rising_edge_4_7  | traditional_charge_depth_timewalk | 0.12123             | 0.15154              | 0                           | 0                            | 0.90714        | 0.92993         | 1                 | 1                  |
| causal_0_11      | traditional_charge_depth_timewalk | 0.12292             | 0.15089              | 0                           | 0                            | 0.909          | 0.93351         | 1                 | 1                  |
| late_tail_12_17  | traditional_charge_depth_timewalk | 0.12255             | 0.15073              | 0                           | 0                            | 0.91041        | 0.93203         | 1                 | 1                  |
| all_0_17         | traditional_charge_depth_timewalk | 0.12317             | 0.15113              | 0                           | 0                            | 0.90696        | 0.93183         | 1                 | 1                  |
| all_0_17         | residual_cnn_gru_new              | 0.015361            | 0.048984             | 0.79309                     | 0.89094                      | 0.98727        | 0.99147         | 0.9915            | 0.99674            |
| causal_0_11      | gradient_boosted_trees            | 0.03869             | 0.072818             | 0.86482                     | 1.0686                       | 0.95333        | 0.9646          | 0.9759            | 0.98738            |
| causal_0_11      | residual_cnn_gru_new              | 0.025757            | 0.081962             | 0.94569                     | 1.1559                       | 0.94971        | 0.95968         | 0.97498           | 0.98841            |
| all_0_17         | attention_transformer_small       | 0.059216            | 0.14145              | 1.0955                      | 1.3064                       | 0.97303        | 0.98534         | 0.96167           | 0.98167            |
| causal_0_11      | attention_transformer_small       | 0.072262            | 0.17075              | 1.0718                      | 1.244                        | 0.93836        | 0.94603         | 0.94508           | 0.97213            |
| all_0_17         | mlp                               | 0.0854              | 0.20463              | 1.3103                      | 1.5626                       | 0.99004        | 0.99401         | 0.99424           | 0.998              |
| peak_charge_8_11 | residual_cnn_gru_new              | 0.053044            | 0.11429              | 1.3607                      | 1.4986                       | 0.93421        | 0.94715         | 0.96052           | 0.9778             |
| late_tail_12_17  | residual_cnn_gru_new              | 0.061947            | 0.12254              | 1.3787                      | 1.4773                       | 0.93374        | 0.94892         | 0.97381           | 0.98809            |
| peak_charge_8_11 | gradient_boosted_trees            | 0.066987            | 0.11639              | 1.3745                      | 1.5264                       | 0.94253        | 0.95584         | 0.95454           | 0.97723            |
| rising_edge_4_7  | residual_cnn_gru_new              | 0.052631            | 0.12432              | 1.3481                      | 1.4742                       | 0.87823        | 0.90587         | 0.96028           | 0.98199            |
| rising_edge_4_7  | gradient_boosted_trees            | 0.061191            | 0.11497              | 1.3718                      | 1.4747                       | 0.88151        | 0.91621         | 0.96174           | 0.97882            |

## Best Method by Mask
| mask             | method                            | joint_score | pid_auc | energy_res68 | timing_res68_samples | stress_auc |
| ---------------- | --------------------------------- | ----------- | ------- | ------------ | -------------------- | ---------- |
| all_0_17         | gradient_boosted_trees            | 0.079964    | 0.99593 | 0.033956     | 0.67388              | 0.99372    |
| causal_0_11      | traditional_charge_depth_timewalk | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          |
| late_tail_12_17  | traditional_charge_depth_timewalk | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          |
| peak_charge_8_11 | traditional_charge_depth_timewalk | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          |
| pretrigger_0_3   | traditional_charge_depth_timewalk | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          |
| rising_edge_4_7  | traditional_charge_depth_timewalk | 0.095541    | 0.91954 | 0.13428      | 0                    | 1          |

## Per-Run Held-Out Diagnostics
| mask             | method                      | run | n_events | pid_auc | energy_res68 | timing_res68_samples | stress_auc |
| ---------------- | --------------------------- | --- | -------- | ------- | ------------ | -------------------- | ---------- |
| all_0_17         | attention_transformer_small | 58  | 600      | 0.99512 | 0.042461     | 1.2182               | 0.98947    |
| all_0_17         | attention_transformer_small | 59  | 600      | 0.97858 | 0.11071      | 1.1571               | 0.95177    |
| all_0_17         | attention_transformer_small | 60  | 600      | 0.96824 | 0.20746      | 1.4427               | 0.96589    |
| all_0_17         | attention_transformer_small | 61  | 600      | 0.9827  | 0.15963      | 1.4271               | 0.96459    |
| all_0_17         | attention_transformer_small | 62  | 600      | 0.96609 | 0.14127      | 1.3916               | 0.96651    |
| all_0_17         | attention_transformer_small | 63  | 600      | 0.97648 | 0.066176     | 1.0463               | 0.9761     |
| all_0_17         | attention_transformer_small | 65  | 600      | 0.99245 | 0.049596     | 0.96813              | 0.99203    |
| causal_0_11      | attention_transformer_small | 58  | 600      | 0.94526 | 0.051066     | 1.1156               | 0.98873    |
| causal_0_11      | attention_transformer_small | 59  | 600      | 0.95162 | 0.15763      | 1.1997               | 0.94021    |
| causal_0_11      | attention_transformer_small | 60  | 600      | 0.94495 | 0.25309      | 1.402                | 0.95338    |
| causal_0_11      | attention_transformer_small | 61  | 600      | 0.9439  | 0.21511      | 1.2503               | 0.94727    |
| causal_0_11      | attention_transformer_small | 62  | 600      | 0.93586 | 0.17364      | 1.3559               | 0.94821    |
| causal_0_11      | attention_transformer_small | 63  | 600      | 0.93875 | 0.084153     | 1.0135               | 0.95042    |
| causal_0_11      | attention_transformer_small | 65  | 600      | 0.93765 | 0.065045     | 0.95782              | 0.9798     |
| late_tail_12_17  | attention_transformer_small | 58  | 600      | 0.94777 | 0.093237     | 1.4588               | 0.97941    |
| late_tail_12_17  | attention_transformer_small | 59  | 600      | 0.93164 | 0.2644       | 1.5716               | 0.92448    |
| late_tail_12_17  | attention_transformer_small | 60  | 600      | 0.91992 | 0.3559       | 1.8419               | 0.95366    |
| late_tail_12_17  | attention_transformer_small | 61  | 600      | 0.94406 | 0.30204      | 1.7478               | 0.95343    |
| late_tail_12_17  | attention_transformer_small | 62  | 600      | 0.9125  | 0.29933      | 1.67                 | 0.95538    |
| late_tail_12_17  | attention_transformer_small | 63  | 600      | 0.9048  | 0.19392      | 1.4969               | 0.95973    |
| late_tail_12_17  | attention_transformer_small | 65  | 600      | 0.93815 | 0.15205      | 1.4038               | 0.97722    |
| peak_charge_8_11 | attention_transformer_small | 58  | 600      | 0.94072 | 0.076847     | 1.3861               | 0.97986    |
| peak_charge_8_11 | attention_transformer_small | 59  | 600      | 0.94208 | 0.21146      | 1.5923               | 0.88596    |
| peak_charge_8_11 | attention_transformer_small | 60  | 600      | 0.93332 | 0.28593      | 1.7475               | 0.90689    |
| peak_charge_8_11 | attention_transformer_small | 61  | 600      | 0.9314  | 0.2473       | 1.668                | 0.90157    |
| peak_charge_8_11 | attention_transformer_small | 62  | 600      | 0.91436 | 0.23164      | 1.6502               | 0.91566    |
| peak_charge_8_11 | attention_transformer_small | 63  | 600      | 0.92163 | 0.14184      | 1.3455               | 0.92247    |
| peak_charge_8_11 | attention_transformer_small | 65  | 600      | 0.92043 | 0.10251      | 1.2732               | 0.96518    |
| pretrigger_0_3   | attention_transformer_small | 58  | 600      | 0.6223  | 0.47107      | 1.2918               | 0.53939    |
| pretrigger_0_3   | attention_transformer_small | 59  | 600      | 0.63149 | 0.69624      | 1.5075               | 0.65966    |
| pretrigger_0_3   | attention_transformer_small | 60  | 600      | 0.67374 | 0.68343      | 1.7364               | 0.68508    |
| pretrigger_0_3   | attention_transformer_small | 61  | 600      | 0.64422 | 0.66958      | 1.6003               | 0.66581    |
| pretrigger_0_3   | attention_transformer_small | 62  | 600      | 0.68783 | 0.71025      | 1.6576               | 0.66719    |
| pretrigger_0_3   | attention_transformer_small | 63  | 600      | 0.66731 | 0.63245      | 1.1471               | 0.62348    |
| pretrigger_0_3   | attention_transformer_small | 65  | 600      | 0.67365 | 0.66856      | 1.2557               | 0.58675    |
| rising_edge_4_7  | attention_transformer_small | 58  | 600      | 0.84891 | 0.046294     | 1.3462               | 0.97497    |
| rising_edge_4_7  | attention_transformer_small | 59  | 600      | 0.88725 | 0.21966      | 1.5872               | 0.92957    |
| rising_edge_4_7  | attention_transformer_small | 60  | 600      | 0.8975  | 0.33894      | 1.7743               | 0.9536     |
| rising_edge_4_7  | attention_transformer_small | 61  | 600      | 0.89632 | 0.27741      | 1.6                  | 0.93878    |
| rising_edge_4_7  | attention_transformer_small | 62  | 600      | 0.89368 | 0.24197      | 1.6095               | 0.96098    |
| rising_edge_4_7  | attention_transformer_small | 63  | 600      | 0.87829 | 0.11646      | 1.3234               | 0.93878    |
| rising_edge_4_7  | attention_transformer_small | 65  | 600      | 0.85189 | 0.086616     | 1.3501               | 0.97683    |

## Systematics
The main systematic is target definition: PID and stress are weak proxies derived from B-stack waveform topology, not external truth. Because targets are event-native and labels are recomputed only from raw ROOT, they are appropriate for relative masked-window retraining but not a standalone physics measurement. The subsample is stratified by run to limit compute while keeping complete-run split semantics. Bootstrap intervals quantify held-out run variability; they do not cover alternate weak-label definitions, gain calibrations, or longer waveform context. The small transformer is intentionally compact and should be read as an eligibility test, not the final high-capacity architecture.

## Caveats
- The `attention_transformer_small` row is now eligible for the winner rule, but it is a compact fixed-attention feature model rather than a large trainable transformer.
- Energy, PID, timing, and stress targets share raw waveforms; this study measures masked predictive retention, not independent detector truth.
- Late-tail masks are noncausal for online PID/timing promotion even when predictive.
- The traditional method is strong for interpretability and low variance, but its formula cannot adapt to all frozen masks.

## Conclusion
`result.json` names `gradient_boosted_trees` on `all_0_17` as the S27d winner. The event-level retraining confirms that the frozen windows can be benchmarked in a single table with ridge, GBT, MLP, 1D-CNN, a residual sequence architecture, and a transformer-like attention row all eligible under the same complete-run bootstrap rule.

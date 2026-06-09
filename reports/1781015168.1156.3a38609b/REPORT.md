# S16g: Sample-I/Sample-II pedestal-lowering timing transfer

- **Ticket:** 1781015168.1156.3a38609b
- **Worker:** testbeam-laptop-2
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16g_1781015168_1156_3a38609b.json`

## Question

Does a pedestal-lowering timing-residual model trained on Sample I transfer to Sample II, and vice versa, on B4/B6/B8 timing residuals?

## Raw reproduction first

Raw B-stack ROOT was read from `h101/HRDv` before any fitting. The S00/S02 count gate passes:

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The downstream timing table then uses events where B4, B6, and B8 are all selected above 1000 ADC. The table contains 15,870 downstream pulse rows from 5,290 events.

## Methods

The base timing is CFD20 on baseline samples 0-3. The S16 lowering diagnostic is the adaptive pedestal decrease, computed from the corrected waveform with jagged-sample masking. For each pulse the target is its base corrected time residual relative to the other two downstream staves after the fixed 2 cm time-of-flight correction.

The traditional model is a train-sample-only median residual table by stave, amplitude bin, and lowering bin, with stave/lowering and stave fallbacks. The ML model is a random forest over normalized waveform shape plus amplitude, peak, area/amp, pre-trigger spread, and lowering. Both are trained on one sample period and evaluated run-by-run on the other sample's analysis runs. Run id, event id, sample label, target residual, and timing columns are excluded from ML features.

## Transfer Results

Intervals are run-block bootstraps over held-out target runs.

| Direction | Method | Held-out runs | Pair residuals | Sigma68 ns | Full RMS ns | Tail frac abs>5 ns |
|---|---|---:|---:|---:|---:|---:|
| sample_i_to_sample_ii | traditional_lowering_strata | 7 | 11460 | 1.886 [1.782, 1.997] | 5.797 [4.374, 6.724] | 0.0171 [0.0124, 0.0208] |
| sample_i_to_sample_ii | ml_lowering_rf | 7 | 11460 | 2.130 [1.973, 2.339] | 5.844 [4.717, 6.715] | 0.0440 [0.0331, 0.0533] |
| sample_i_to_sample_ii | ml_shuffled_target_control | 7 | 11460 | 3.113 [2.986, 3.250] | 6.183 [4.946, 7.153] | 0.0609 [0.0501, 0.0772] |
| sample_i_to_sample_ii | cfd20 | 7 | 11460 | 3.150 [3.008, 3.281] | 6.204 [4.963, 7.401] | 0.0579 [0.0502, 0.0723] |
| sample_i_to_sample_ii | adaptive_lowered_cfd20 | 7 | 11460 | 3.220 [3.083, 3.350] | 7.058 [6.012, 8.397] | 0.1041 [0.0840, 0.1239] |
| sample_ii_to_sample_i | traditional_lowering_strata | 14 | 1950 | 1.964 [1.860, 2.070] | 5.915 [2.307, 9.365] | 0.0154 [0.0072, 0.0254] |
| sample_ii_to_sample_i | ml_lowering_rf | 14 | 1950 | 2.632 [2.464, 2.818] | 5.966 [3.566, 8.778] | 0.0903 [0.0670, 0.1132] |
| sample_ii_to_sample_i | cfd20 | 14 | 1950 | 3.149 [3.013, 3.254] | 6.285 [3.052, 9.472] | 0.0687 [0.0523, 0.0828] |
| sample_ii_to_sample_i | adaptive_lowered_cfd20 | 14 | 1950 | 3.154 [3.042, 3.284] | 7.176 [3.855, 11.331] | 0.0923 [0.0728, 0.1115] |
| sample_ii_to_sample_i | ml_shuffled_target_control | 14 | 1950 | 3.228 [3.100, 3.355] | 6.369 [3.244, 10.225] | 0.0836 [0.0651, 0.0990] |

Sample I -> Sample II: traditional lowering strata gives 1.886 ns sigma68 and ML gives 2.130 ns. Sample II -> Sample I: traditional gives 1.964 ns and ML gives 2.632 ns. The deterministic lowering-strata model is the strongest transfer result in both directions.

## Leakage Checks

| Check | Aggregate value | Passing folds | All pass |
|---|---:|---:|---|
| ml_not_implausibly_better_than_raw | 0.8155 | 13/21 | no |
| ml_train_rows | 9320 | 21/21 | yes |
| shuffled_target_not_better_than_ml | 0.8778 | 21/21 | yes |
| train_heldout_event_id_overlap | 0 | 21/21 | yes |
| train_heldout_run_overlap | 0 | 21/21 | yes |
| train_target_sample_overlap | 0 | 21/21 | yes |
| ml_feature_forbidden_column_overlap | 0 | 1/1 | yes |

The transfer split has no train/held-out run overlap and no train/held-out event overlap. The shuffled-target control is worse than ML in all folds, but the ML-vs-raw improvement exceeds the pre-set "too good" guard in 13/21 folds. Those fold details are saved in `leakage_fold_details.csv`, and the RF is therefore treated as a diagnostic transfer model rather than the headline correction.

## Conclusion

A simple traditional lowering-strata correction transfers across sample periods and substantially narrows B4/B6/B8 pair residuals versus raw CFD20. The direct adaptive-lowered CFD20 timing does not transfer, and ML does not beat the traditional correction. The conservative reading is that pedestal lowering is a useful detector diagnostic and coarse timing nuisance term, but the high-lowering tail should not be promoted as a portable ML timing correction without stronger run-family controls.

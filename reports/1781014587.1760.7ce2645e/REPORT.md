# S16e: forced/random pedestal no-proxy rerun

- **Ticket:** `1781014587.1760.7ce2645e`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-06-09
- **Input:** raw `data/root/root/hrd*_run_*.root`; checksums in `input_sha256.csv` and `manifest.json`.
- **Config:** `s16e_config.json`

## Question

S16d found no true forced/random-trigger pedestal entries in the local extracted ROOT mirror. This rerun checks the local raw/archive mirrors again, keeps that raw-ROOT reproduction gate, and benchmarks pedestal prediction on pre-trigger no-pulse samples without using the quiet-event amplitude proxy.

## Raw ROOT Reproduction First

| Quantity | Expected | Reproduced | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |
| forced/random/non-beam ROOT entries | 0 | 0 | yes |
| forced/random/pedestal archive or filename hits | 0 | 0 | yes |

I found no local external DAQ run log or forced/random pedestal ROOT candidate. The scan covers the extracted ROOT mirror, `/home/billy/ccb-data`, `/home/billy/Desktop/test_beam/data`, and zip member names in the local raw archives. Therefore no dedicated forced/random pedestal acquisition is available in this worker; the benchmark below uses pre-trigger samples from physics events and does not cut on event amplitude.

## Methods

The benchmark rows are sampled uniformly within run from all B-stack events and staves. For each row one of samples 0-3 is the held-out target and the other three pre-trigger samples are the inputs. Runs `[57, 65]` are held out completely; CIs bootstrap held-out runs and records within run.

Traditional methods are median-of-three, mean-of-three, and a robust detector correction that adds a training-run median offset per stave and target sample. The ML method is a histogram gradient boosting regressor trained only on non-held-out runs. ML features exclude run, event id, trigger, filename, selected-pulse amplitude, and the target ADC.

| Method | n | mean bias [ADC] | MAE [ADC] | width68 [ADC] |
|---|---:|---:|---:|---:|
| ml_hist_gradient_boosting | 24000 | 2.751 [-0.698, 5.443] | 23.954 [18.611, 29.791] | 12.270 [12.091, 12.638] |
| traditional_mean3 | 24000 | 0.114 [-3.116, 3.255] | 36.518 [27.428, 45.756] | 10.000 [9.667, 10.333] |
| traditional_stave_sample_offset_median3 | 24000 | -1.660 [-5.260, 1.246] | 37.814 [28.571, 48.269] | 11.000 [10.000, 11.000] |
| traditional_median3 | 24000 | -1.724 [-4.810, 0.981] | 37.816 [28.475, 47.516] | 11.000 [10.000, 11.000] |

Best held-out method by MAE is `ml_hist_gradient_boosting` with MAE `23.954` ADC and width68 `12.270` ADC. The best traditional method is `traditional_mean3` with MAE `36.518` ADC.

## Leakage Checks

| Check | value | pass? | note |
|---|---:|---|---|
| shuffled_training_targets_mae_minus_real_mae | 132.478 | yes | Shuffled targets must perform materially worse than real training. |
| run_split_mae_minus_row_split_mae | -2.624 | yes | A large row-split advantage would suggest run leakage or duplicate memorization. |
| heldout_feature_duplicate_fraction | 0.055 | yes | Exact feature duplicates across train and held-out runs are rare enough to reject memorization. |
| feature_exclusion |  | yes | ML features exclude run, event number, trigger, filenames, selected-pulse amplitude, and target ADC. |

The row-split advantage is small and shuffled targets are materially worse, so the ML result does not look like run or target leakage. Exact feature duplicates across held-out runs are also below the configured threshold.

## Conclusion

The S16d number is reproduced from raw ROOT: there are `0` true forced/random/non-beam pedestal entries and no local forced/random/pedestal archive candidates. Without an external forced/random run, the no-proxy pre-trigger benchmark shows that ordinary pre-trigger pedestal samples can be predicted to around `23.954` ADC MAE on held-out runs. This is a baseline electronics-pedestal benchmark, not a substitute for a dedicated forced/random-trigger pedestal run.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781014587.1760.7ce2645e/s16e_forced_random_pedestal_no_proxy.py --config reports/1781014587.1760.7ce2645e/s16e_config.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `archive_runlog_scan.csv`, `no_proxy_counts_by_run.csv`, `heldout_method_summary.csv`, `heldout_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and figures.

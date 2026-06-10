# S16e: external forced/random pedestal ingest audit

- **Ticket:** `1781017317.1094.3dce221c`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-09
- **Input:** raw `data/root/root/hrd*_run_*.root`; checksums in `input_sha256.csv` and `manifest.json`.
- **Config:** `configs/s16e_1781017317_1094_3dce221c_forced_random_no_proxy.json`

## Question

S16d found no true forced/random-trigger pedestal entries in the local extracted ROOT mirror. This ticket asks whether an external DAQ/run-log source or newly mirrored forced/random HRD ROOT is now visible; it keeps the raw-ROOT reproduction gate first, refuses the quiet-event amplitude fallback, and benchmarks only a no-proxy pre-trigger baseline because no direct forced/random sample is present.

## Raw ROOT Reproduction First

| Quantity | Expected | Reproduced | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |
| forced/random/non-beam ROOT entries | 0 | 0 | yes |
| forced/random/pedestal archive or filename hits | 0 | 0 | yes |

I found no local external DAQ run log or forced/random pedestal ROOT candidate. The scan covers the extracted ROOT mirror, `/home/billy/ccb-data`, `/home/billy/Desktop/test_beam/data`, and zip member names in the local raw archives. Therefore no dedicated forced/random pedestal acquisition is available in this worker. The benchmark below uses pre-trigger samples from physics events and does not cut on event amplitude; it is not a substitute for true forced/random pedestal truth.

## Methods

The benchmark rows are sampled uniformly within run from all B-stack events and staves. For each row one of samples 0-3 is the held-out target and the other three pre-trigger samples are the inputs. Runs `[57, 65]` are held out completely; CIs bootstrap held-out runs and records within run.

Traditional methods are median-of-three, mean-of-three, and a robust detector correction that adds a training-run median offset per stave and target sample. The ML method is a histogram gradient boosting regressor trained only on non-held-out runs. ML features exclude run, event id, trigger, filename, selected-pulse amplitude, and the target ADC.

| Method | n | mean bias [ADC] | MAE [ADC] | width68 [ADC] |
|---|---:|---:|---:|---:|
| ml_hist_gradient_boosting | 5000 | 3.967 [-0.209, 8.064] | 32.143 [24.262, 40.772] | 13.262 [12.954, 13.786] |
| traditional_mean3 | 5000 | 0.388 [-6.695, 7.512] | 35.891 [22.834, 48.206] | 10.333 [9.992, 11.000] |
| traditional_stave_sample_offset_median3 | 5000 | -1.783 [-10.063, 6.230] | 37.374 [27.612, 50.360] | 11.000 [10.000, 11.000] |
| traditional_median3 | 5000 | -1.909 [-9.288, 5.380] | 37.385 [25.699, 48.963] | 11.000 [10.000, 11.000] |

Best held-out method by MAE is `ml_hist_gradient_boosting` with MAE `32.143` ADC and width68 `13.262` ADC. The best traditional method is `traditional_mean3` with MAE `35.891` ADC.

## Leakage Checks

| Check | value | pass? | note |
|---|---:|---|---|
| shuffled_training_targets_mae_minus_real_mae | 138.563 | yes | Shuffled targets must perform materially worse than real training. |
| run_split_mae_minus_row_split_mae | -2.292 | yes | A large row-split advantage would suggest run leakage or duplicate memorization. |
| heldout_feature_duplicate_fraction | 0.011 | yes | Exact feature duplicates across train and held-out runs are rare enough to reject memorization. |
| feature_exclusion |  | yes | ML features exclude run, event number, trigger, filenames, selected-pulse amplitude, and target ADC. |

The row-split advantage is small and shuffled targets are materially worse, so the ML result does not look like run or target leakage. Exact feature duplicates across held-out runs are also below the configured threshold.

## Conclusion

The S16d number is reproduced from raw ROOT: there are `0` true forced/random/non-beam pedestal entries and no local forced/random/pedestal archive candidates. The requested direct S16d rerun against external forced/random truth is therefore not estimable from the current mirror. Without an external forced/random run, the no-proxy pre-trigger benchmark shows that ordinary pre-trigger pedestal samples can be predicted to around `32.143` ADC MAE on held-out runs. This is a baseline electronics-pedestal benchmark, not a substitute for a dedicated forced/random-trigger pedestal run.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16e_1781017317_1094_3dce221c_forced_random_no_proxy.py --config configs/s16e_1781017317_1094_3dce221c_forced_random_no_proxy.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `archive_runlog_scan.csv`, `no_proxy_counts_by_run.csv`, `heldout_method_summary.csv`, `heldout_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and figures.

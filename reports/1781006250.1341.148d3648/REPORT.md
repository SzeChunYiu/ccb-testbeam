# P10c: Leave-one-run-family conditional template stress test

- **Ticket ID:** 1781006250.1341.148d3648
- **Worker:** testbeam-laptop-3
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** 076f9e4f7ae6dba0efb7c7c7ef2cb28335ef0753

## Raw reproduction gate

Before any modeling, the script rebuilt the selected B-stave pulse table from raw `HRDv` waveforms using the S00/S01 gate: baseline-subtracted amplitude > 1000 ADC.

| quantity                        |   expected |   reproduced |   delta | pass   |
|:--------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| analysis selected rows          |     377362 |       377362 |       0 | True   |

## Methods

The split is by run family, not by row: Sample I held out means fitting only run 64 and evaluating runs 44-57; Sample II held out means fitting runs 31-42 and evaluating runs 58-63 and 65.

Traditional method: train-only S01 empirical median templates per B stave and amplitude bin, with stave-median fallback when a bin has fewer than 30 pulses.

ML method: a strongly regularized multi-output conditional ridge model maps standardized log amplitude, squared log amplitude, stave one-hot, and stave/log-amplitude interactions to the CFD20-aligned normalized waveform. It uses no run id, event id, timing label, or other-stave information.

Controls: a per-stave mean-template control and a shuffled-target conditional ridge control are evaluated on the same held-out runs.

## Held-out q-template MSE

Values are means of per-run MSEs; 95% CIs bootstrap held-out runs.

| fold              | train_group     | eval_group         |   empirical_mse | empirical_mse_ci                            |   mean_template_mse |   conditional_mse | conditional_mse_ci                         |   shuffled_conditional_mse |   delta_conditional_minus_empirical | delta_conditional_minus_empirical_ci         |
|:------------------|:----------------|:-------------------|----------------:|:--------------------------------------------|--------------------:|------------------:|:-------------------------------------------|---------------------------:|------------------------------------:|:---------------------------------------------|
| holdout_sample_i  | sample_ii_calib | sample_i_analysis  |       0.0477821 | [0.03336586633695607, 0.0626292818741241]   |           0.0805962 |         0.0607969 | [0.04471182910711141, 0.07768520825916267] |                  0.0782432 |                           0.0130148 | [0.010708263590122712, 0.015343943964221198] |
| holdout_sample_ii | sample_i_calib  | sample_ii_analysis |       0.0389922 | [0.029072690988680344, 0.04583195299639763] |           0.08965   |         0.0682174 | [0.05835029804636898, 0.07573445142748281] |                  0.0866629 |                           0.0292253 | [0.02631280186537388, 0.032329390318912264]  |

## Leakage audit

| fold              | train_eval_run_overlap   |   train_eval_key_overlap | uses_run_or_event_features   | conditional_beats_empirical_ci   | shuffled_beats_real_ci   |
|:------------------|:-------------------------|-------------------------:|:-----------------------------|:---------------------------------|:-------------------------|
| holdout_sample_i  | []                       |                        0 | False                        | False                            | False                    |
| holdout_sample_ii | []                       |                        0 | False                        | False                            | False                    |

The result is not a too-good ML win: in both family-held-out directions the conditional ridge MSE is worse than the empirical amplitude-bin template. The real conditional ridge improves on the shuffled-target control, but the shuffled control does not beat the real model and there is no run/key overlap, so the pattern supports P10a's q-space failure diagnosis rather than indicating leakage.

## Finding

The P10a q-space failure persists under leave-one-run-family-out calibration with stronger regularization.

No Monte Carlo was used. `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSV, leakage checks, and figures are in this report directory.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10c_run_family_conditional_template.py --config configs/p10c_run_family_conditional_template.yaml
```

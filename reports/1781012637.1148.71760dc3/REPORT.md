# P10e: Family-heldout conditional template negative-control registry

- **Ticket ID:** `1781012637.1148.71760dc3`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Monte Carlo:** none

## Raw reproduction first

The selected pulse table was rebuilt from raw `HRDv` waveforms before any model fit. The P10c/S01 counts reproduce exactly.

| quantity                        |   expected |   reproduced |   delta | pass   |
|:--------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| analysis selected rows          |     377362 |       377362 |       0 | True   |

## Registry benchmark

Split: train and evaluate on disjoint run families, then summarize by held-out run with run-bootstrap 95% CIs.

Traditional method: train-only S01 empirical median templates by B stave and amplitude bin.

ML method: conditional ridge template using only log amplitude, log-amplitude squared, stave one-hot, and stave/log-amplitude interactions. It excludes run id, event id, event order, target labels, and other-stave information.

Required negative controls: per-stave mean template, shuffled-target conditional ridge, train/eval run overlap, train/eval `(run,eventno,evt,stave)` key overlap, and run/event feature exclusion.

| fold              | train_group     | eval_group         |   empirical_mse | empirical_mse_ci                            |   mean_template_mse |   conditional_mse | conditional_mse_ci                         |   shuffled_conditional_mse |   delta_conditional_minus_empirical | delta_conditional_minus_empirical_ci         |
|:------------------|:----------------|:-------------------|----------------:|:--------------------------------------------|--------------------:|------------------:|:-------------------------------------------|---------------------------:|------------------------------------:|:---------------------------------------------|
| holdout_sample_i  | sample_ii_calib | sample_i_analysis  |       0.0477821 | [0.03336586633695607, 0.0626292818741241]   |           0.0805962 |         0.0607969 | [0.04471182910711141, 0.07768520825916267] |                  0.0782432 |                           0.0130148 | [0.010708263590122712, 0.015343943964221198] |
| holdout_sample_ii | sample_i_calib  | sample_ii_analysis |       0.0389922 | [0.029072690988680344, 0.04583195299639763] |           0.08965   |         0.0682174 | [0.05835029804636898, 0.07573445142748281] |                  0.0866629 |                           0.0292253 | [0.02631280186537388, 0.032329390318912264]  |

## Leakage and promotion gate

| fold              | required_controls_present   | missing_controls   | train_eval_run_overlap   |   train_eval_key_overlap | uses_run_or_event_features   | conditional_beats_empirical_ci   | shuffled_beats_real_ci   | too_good_claim_allowed   | registry_pass   |
|:------------------|:----------------------------|:-------------------|:-------------------------|-------------------------:|:-----------------------------|:---------------------------------|:-------------------------|:-------------------------|:----------------|
| holdout_sample_i  | True                        |                    |                          |                        0 | False                        | False                            | False                    | False                    | True            |
| holdout_sample_ii | True                        |                    |                          |                        0 | False                        | False                            | False                    | False                    | True            |

A future too-good q-space claim should not be promoted unless these controls are present and clean. In this run the conditional ridge is worse than the empirical amplitude-bin template in both held-out families, so no too-good ML claim is present.

## Finding

P10a/P10c q-space failure persists under the registry check.

Registry status: **pass**.

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSV, leakage/registry CSV, and figures are in this directory.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10e_conditional_template_registry.py --config configs/p10e_conditional_template_registry.yaml
```

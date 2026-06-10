# P10g: per-run conditional-template residual audit

- **Ticket ID:** `1781025208.1047.4bc52d2c`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Monte Carlo:** none

## Raw reproduction first

The selected pulse table was rebuilt from raw `HRDv` waveforms before any residual model was fit.

| quantity                        |   expected |   reproduced |   delta | pass   |
|:--------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| analysis selected rows          |     377362 |       377362 |       0 | True   |

## Methods

Split: P10e family-heldout by run. `holdout_sample_i` trains on run 64 and evaluates Sample-I analysis runs 44-57; `holdout_sample_ii` trains on Sample-I calibration runs 31-37 and 39-42 and evaluates Sample-II analysis runs 58-63 and 65.

Traditional method: train-only S01 empirical median templates by B stave and amplitude bin with stave-median fallback below 30 train pulses.

ML method: the P10e conditional ridge template using standardized log amplitude, squared log amplitude, stave one-hot, and stave/log-amplitude interactions. It excludes run id, event id, event order, target labels, and other-stave information.

Negative controls: per-stave mean template, shuffled-target conditional ridge, train/eval run-overlap check, train/eval `(run,eventno,evt,stave)` key-overlap check, and explicit run/event feature exclusion. A subgroup ML win is counted only if the conditional-minus-empirical run-bootstrap CI is below zero and the real conditional model also beats shuffled-target conditional with CI below zero.

## Global P10e reproduction

| fold              | subgroup_type   | subgroup   |   n_runs |   n_pulses |   empirical_mse |   conditional_mse |   shuffled_conditional_mse |   delta_conditional_minus_empirical | delta_conditional_minus_empirical_ci         |   delta_conditional_minus_shuffled | delta_conditional_minus_shuffled_ci            | ml_win_after_controls   | ci_note                                |
|:------------------|:----------------|:-----------|---------:|-----------:|----------------:|------------------:|---------------------------:|------------------------------------:|:---------------------------------------------|-----------------------------------:|:-----------------------------------------------|:------------------------|:---------------------------------------|
| holdout_sample_i  | global          | all        |       14 |     252266 |       0.0477821 |         0.0607969 |                  0.0791205 |                           0.0130148 | [0.010679917724669204, 0.015280949683401308] |                         -0.0183237 | [-0.019893688023460976, -0.01674388397220774]  | False                   | run-block bootstrap over held-out runs |
| holdout_sample_ii | global          | all        |        7 |     125096 |       0.0389922 |         0.0682957 |                  0.0865769 |                           0.0293035 | [0.026338185718751603, 0.03231978157956401]  |                         -0.0182813 | [-0.023590608272268592, -0.011469454974835746] | False                   | run-block bootstrap over held-out runs |

## Per-stave held-out run bootstrap

| fold              | subgroup_type   | subgroup   |   n_runs |   n_pulses |   empirical_mse |   conditional_mse |   shuffled_conditional_mse |   delta_conditional_minus_empirical | delta_conditional_minus_empirical_ci         |   delta_conditional_minus_shuffled | delta_conditional_minus_shuffled_ci            | ml_win_after_controls   | ci_note                                |
|:------------------|:----------------|:-----------|---------:|-----------:|----------------:|------------------:|---------------------------:|------------------------------------:|:---------------------------------------------|-----------------------------------:|:-----------------------------------------------|:------------------------|:---------------------------------------|
| holdout_sample_i  | stave           | B2         |       14 |     241422 |       0.0493722 |         0.0560144 |                  0.0753301 |                          0.00664221 | [0.005700868551813456, 0.007600555490767469] |                        -0.0193157  | [-0.021131570394549964, -0.017584894414714166] | False                   | run-block bootstrap over held-out runs |
| holdout_sample_i  | stave           | B4         |       14 |       6451 |       0.0286403 |         0.195074  |                  0.188252  |                          0.166434   | [0.1530438108927845, 0.17957978601704344]    |                         0.00682289 | [0.0021621975701750225, 0.012707549006588886]  | False                   | run-block bootstrap over held-out runs |
| holdout_sample_i  | stave           | B6         |       14 |       3094 |       0.0179017 |         0.127841  |                  0.134074  |                          0.109939   | [0.08994055322127584, 0.12555991891310822]   |                        -0.00623295 | [-0.008895267548481973, -0.00407071701234026]  | False                   | run-block bootstrap over held-out runs |
| holdout_sample_i  | stave           | B8         |       14 |       1299 |       0.026852  |         0.156769  |                  0.153927  |                          0.129918   | [0.10075982704988641, 0.15835404307103085]   |                         0.00284216 | [-0.0006599641692634393, 0.006343332600075974] | False                   | run-block bootstrap over held-out runs |
| holdout_sample_ii | stave           | B2         |        7 |      88213 |       0.044395  |         0.0656241 |                  0.0852235 |                          0.0212291  | [0.018651373803276756, 0.02386686124452903]  |                        -0.0195995  | [-0.02571042723594067, -0.012745936500957952]  | False                   | run-block bootstrap over held-out runs |
| holdout_sample_ii | stave           | B4         |        7 |      21229 |       0.0341788 |         0.102205  |                  0.121733  |                          0.0680266  | [0.038626231950993725, 0.10639243531558858]  |                        -0.019528   | [-0.02488521296193385, -0.01331890879401458]   | False                   | run-block bootstrap over held-out runs |
| holdout_sample_ii | stave           | B6         |        7 |      11148 |       0.0243444 |         0.0939103 |                  0.106788  |                          0.0695659  | [0.043591570421643785, 0.10172553088426868]  |                        -0.0128773  | [-0.018117856664571948, -0.006454895424211604] | False                   | run-block bootstrap over held-out runs |
| holdout_sample_ii | stave           | B8         |        7 |       4506 |       0.0253572 |         0.105293  |                  0.107432  |                          0.0799362  | [0.04885451770430407, 0.11448307628840511]   |                        -0.00213881 | [-0.008346034789056586, 0.004935392474985116]  | False                   | run-block bootstrap over held-out runs |

## Per-run point scan

The per-run scan found 0 held-out runs where the conditional ridge point estimate is below the empirical template. Single-run rows cannot support a run-block CI, so they are leakage-hunt targets rather than promoted wins.

| fold             | subgroup_type   | subgroup   |   n_runs |   n_pulses |   empirical_mse |   conditional_mse |   shuffled_conditional_mse |   delta_conditional_minus_empirical | delta_conditional_minus_empirical_ci         |   delta_conditional_minus_shuffled | delta_conditional_minus_shuffled_ci            | ml_win_after_controls   | ci_note                                             |
|:-----------------|:----------------|:-----------|---------:|-----------:|----------------:|------------------:|---------------------------:|------------------------------------:|:---------------------------------------------|-----------------------------------:|:-----------------------------------------------|:------------------------|:----------------------------------------------------|
| holdout_sample_i | run             | run_46     |        1 |        687 |       0.0323213 |         0.0380606 |                  0.0512308 |                          0.00573931 | [0.00573931319302079, 0.00573931319302079]   |                         -0.0131702 | [-0.013170155558792605, -0.013170155558792605] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_47     |        1 |       5276 |       0.0440101 |         0.0502342 |                  0.0646745 |                          0.00622409 | [0.006224088134809236, 0.006224088134809236] |                         -0.0144403 | [-0.014440315028021164, -0.014440315028021164] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_52     |        1 |       7152 |       0.0316929 |         0.0419024 |                  0.0593875 |                          0.0102095  | [0.010209537223681203, 0.010209537223681203] |                         -0.0174851 | [-0.017485117718198315, -0.017485117718198315] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_53     |        1 |      32200 |       0.0200396 |         0.0306492 |                  0.0482001 |                          0.0106096  | [0.01060955144996819, 0.01060955144996819]   |                         -0.0175509 | [-0.017550918840634186, -0.017550918840634186] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_54     |        1 |      30440 |       0.0160836 |         0.0269448 |                  0.0438887 |                          0.0108612  | [0.010861180336519866, 0.010861180336519866] |                         -0.016944  | [-0.016943954971089314, -0.016943954971089314] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_50     |        1 |      35217 |       0.0233562 |         0.0344753 |                  0.050711  |                          0.0111191  | [0.011119127086919374, 0.011119127086919374] |                         -0.0162356 | [-0.01623563701777169, -0.01623563701777169]   | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_56     |        1 |      40148 |       0.0217839 |         0.032981  |                  0.0489682 |                          0.0111971  | [0.011197069258892745, 0.011197069258892745] |                         -0.0159872 | [-0.015987192634892906, -0.015987192634892906] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_51     |        1 |      14740 |       0.0283199 |         0.0403486 |                  0.0574884 |                          0.0120287  | [0.01202867588907507, 0.01202867588907507]   |                         -0.0171399 | [-0.017139863277106537, -0.017139863277106537] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_55     |        1 |      17387 |       0.0304706 |         0.0428406 |                  0.0601154 |                          0.01237    | [0.012369966427313344, 0.012369966427313344] |                         -0.0172748 | [-0.01727478844858058, -0.01727478844858058]   | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_49     |        1 |      14815 |       0.0848661 |         0.10133   |                  0.123214  |                          0.0164643  | [0.016464268678119676, 0.016464268678119676] |                         -0.0218832 | [-0.02188319840528058, -0.02188319840528058]   | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_45     |        1 |      24333 |       0.0898854 |         0.107453  |                  0.130574  |                          0.0175678  | [0.017567775840046262, 0.017567775840046262] |                         -0.0231205 | [-0.023120455343776963, -0.023120455343776963] | False                   | single held-out run; CI collapses to point estimate |
| holdout_sample_i | run             | run_48     |        1 |      14000 |       0.0824445 |         0.100042  |                  0.121573  |                          0.0175976  | [0.017597568468115637, 0.017597568468115637] |                         -0.0215308 | [-0.021530761901269138, -0.021530761901269138] | False                   | single held-out run; CI collapses to point estimate |

## Leakage audit

| fold              | train_group     | eval_group         | train_eval_run_overlap   |   train_eval_key_overlap | uses_run_or_event_features   | required_controls_present   |   n_train_runs |   n_eval_runs |
|:------------------|:----------------|:-------------------|:-------------------------|-------------------------:|:-----------------------------|:----------------------------|---------------:|--------------:|
| holdout_sample_i  | sample_ii_calib | sample_i_analysis  |                          |                        0 | False                        | True                        |              1 |            14 |
| holdout_sample_ii | sample_i_calib  | sample_ii_analysis |                          |                        0 | False                        | True                        |             11 |             7 |

The run-stave point scan found 0 point-estimate cells with ML below empirical; the best point delta was 0.00142248. None is claimable by the required held-out run-bootstrap gate.

## Finding

Supported ML subgroup wins after controls: **0**.
No per-stave subgroup has a negative conditional-minus-empirical run-bootstrap CI, and no single-run or run-stave point advantage is promoted because it lacks a multi-run bootstrap CI. The P10e global q-space failure therefore does not hide a supported narrow per-run or per-stave ML win.

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `global_summary.csv`, `per_stave_summary.csv`, `per_run_scan.csv`, `run_stave_scan.csv`, `leakage_checks.csv`, and `conditional_ridge_cv.csv` are in this directory.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.py --config configs/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.yaml
```

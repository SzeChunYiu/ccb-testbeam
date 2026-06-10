# P04f Adaptive-Template Residual Basis Diagnosis

- **Ticket:** `1781024351.1905.535c46de`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.
- **Split:** P04d held-out runs `[57, 65]`; every template, PC basis, calibrator, and model is trained on other runs.
- **Target:** inverted odd duplicate-readout amplitude; features use even readout only.

## Raw Reproduction First

S00 selected B-stave pulses: `640,737` vs expected `640,737`.

P04d peak_calibrated reproduction: res68 `0.123782` on `26857` held-out rows (expected `0.123782`).

## Held-Out Benchmark

| method                      |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                    | run_block_res68_ci95                         |   within_10pct |
|:----------------------------|------:|-------------------:|-----------------:|:----------------------------------------------|:---------------------------------------------|---------------:|
| peak_calibrated             | 26857 |       -0.0666998   |       0.123782   | [0.12216506175529748, 0.12532780745228497]    | [0.10180915216194056, 0.1394391077099221]    |       0.581078 |
| residual_basis_huber        | 26857 |       -2.01091e-05 |       0.00610234 | [0.005993236821084948, 0.006228534393114597]  | [0.00578839450814469, 0.0063972729373755685] |       0.935101 |
| residual_basis_ridge        | 26857 |        0.00310614  |       0.0251153  | [0.024623343952219344, 0.025451186881547728]  | [0.02449778263182372, 0.025702022313618855]  |       0.918122 |
| residual_basis_extra_trees  | 26857 |       -9.32031e-05 |       0.00217811 | [0.002118515199624692, 0.0022384986921433233] | [0.00211118023980359, 0.0022672453461811707] |       0.984622 |
| shuffled_target_extra_trees | 26857 |        0.344058    |       0.802883   | [0.7837246904521793, 0.8271962977712389]      | [0.5381894746198456, 1.1185693725184849]     |       0.119001 |

## Per-Run Check

| method                     |   run |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                    |   within_10pct |
|:---------------------------|------:|------:|-------------------:|-----------------:|:----------------------------------------------|---------------:|
| peak_calibrated            |    57 | 13819 |       -0.0498185   |       0.101811   | [0.09982034739178387, 0.1040403017348675]     |       0.672842 |
| peak_calibrated            |    65 | 13038 |       -0.0862171   |       0.13944    | [0.13747273422427106, 0.14098265781339192]    |       0.483817 |
| residual_basis_huber       |    57 | 13819 |        0.000145354 |       0.00639739 | [0.00624697161601422, 0.006562319049269723]   |       0.922932 |
| residual_basis_huber       |    65 | 13038 |       -0.000195825 |       0.00578843 | [0.005635279865601702, 0.005969291443173658]  |       0.947998 |
| residual_basis_extra_trees |    57 | 13819 |       -0.000109547 |       0.00226729 | [0.0021713602623396814, 0.002385372116784891] |       0.980534 |
| residual_basis_extra_trees |    65 | 13038 |       -7.1048e-05  |       0.00211153 | [0.002037071056550887, 0.002181565550930743]  |       0.988955 |

## Residual Basis

The residual basis is train-only per stave and amplitude bin: median normalized even-waveform template, residual PCs, peak-anchor delta, and tail/baseline residual moments.

| stave   | amp_bin   |   train_rows_for_basis |   heldout_rows |   template_peak_sample |   pc1_var_frac |   pc2_var_frac |   pc3_var_frac |   train_residual_rms |
|:--------|:----------|-----------------------:|---------------:|-----------------------:|---------------:|---------------:|---------------:|---------------------:|
| B2      | 1000_1500 |                  12000 |           2767 |                      8 |       0.861286 |      0.0729931 |      0.0315217 |             1.18231  |
| B2      | 1500_2000 |                  12000 |           2235 |                      8 |       0.806603 |      0.100119  |      0.0411795 |             0.717069 |
| B2      | 2000_3000 |                  12000 |           4361 |                      7 |       0.612366 |      0.173468  |      0.0847744 |             0.369161 |
| B2      | 3000_4000 |                  12000 |           4930 |                      7 |       0.395737 |      0.299673  |      0.109255  |             0.223681 |
| B2      | 4000_5500 |                  12000 |           4926 |                      6 |       0.39598  |      0.281757  |      0.0983632 |             0.175886 |
| B2      | 5500_7000 |                  12000 |           3018 |                      6 |       0.474554 |      0.233272  |      0.10341   |             0.112294 |
| B2      | 7000_9000 |                  12000 |           1957 |                      6 |       0.460763 |      0.267616  |      0.122611  |             0.132018 |
| B2      | 9000_inf  |                  12000 |            334 |                      6 |       0.49474  |      0.216978  |      0.141633  |             0.168121 |
| B4      | 1000_1500 |                   3079 |            151 |                      6 |       0.689008 |      0.202963  |      0.0461822 |             0.80929  |
| B4      | 1500_2000 |                   3267 |            171 |                      7 |       0.601817 |      0.22644   |      0.08807   |             0.451374 |
| B4      | 2000_3000 |                  11814 |            501 |                      8 |       0.495794 |      0.33831   |      0.0696769 |             0.330321 |
| B4      | 3000_4000 |                  10475 |            440 |                      7 |       0.573113 |      0.262152  |      0.0612121 |             0.308835 |
| B4      | 4000_5500 |                   4878 |            200 |                      7 |       0.542945 |      0.236503  |      0.0833695 |             0.278562 |
| B4      | 5500_7000 |                    967 |             29 |                      7 |       0.511561 |      0.240172  |      0.106462  |             0.257391 |
| B4      | 7000_9000 |                    137 |              6 |                      6 |       0.503609 |      0.283408  |      0.0826058 |             0.230302 |
| B6      | 1000_1500 |                   1810 |             81 |                      7 |       0.699294 |      0.19888   |      0.0525245 |             0.719557 |

## Mode Audit

| mode                           |   corr_with_abs_error_improvement |   low20_median_improvement |   high20_median_improvement |
|:-------------------------------|----------------------------------:|---------------------------:|----------------------------:|
| per-stave amp-bin PC1          |                         0.184393  |                  0.149997  |                   0.08751   |
| per-stave amp-bin PC2          |                         0.0996347 |                  0.0938741 |                   0.0871167 |
| per-stave amp-bin PC3          |                        -0.160845  |                  0.0878435 |                   0.140279  |
| peak-sample anchoring error    |                        -0.337864  |                  0.0871877 |                   0.0717598 |
| tail residual mean             |                        -0.269883  |                  0.104302  |                   0.0949559 |
| baseline residual mean         |                         0.174612  |                  0.085165  |                   0.0705483 |
| tail/baseline covariance proxy |                        -0.150632  |                  0.0975908 |                   0.0971233 |

## Leakage Checks

| check                                 | value                                                                   | pass   |
|:--------------------------------------|:------------------------------------------------------------------------|:-------|
| train_heldout_run_overlap             | 0                                                                       | True   |
| train_heldout_event_stave_key_overlap | 0                                                                       | True   |
| exact_even_waveform_hash_overlap      | 0                                                                       | True   |
| features_exclude_run_event_odd_target | even waveform, even summaries, train-only residual basis, stave one-hot | True   |
| shuffled_target_extra_trees_res68     | 0.8028830995191673                                                      | True   |
| ml_to_shuffled_res68_ratio            | 0.0027128588172485317                                                   | True   |
| looks_too_good_triggered_extra_audit  | True                                                                    | True   |

The ML result is extremely narrow because the target is a duplicate readout of the same scintillator pulse, so it was leakage-hunted with run/key overlap, exact even-waveform hash overlap, and shuffled-target sentinels before interpretation.

## Finding

P04d peak_calibrated reproduces at res68=0.1238.  A train-only residual-basis Huber calibrator using per-stave amplitude-bin PCs, peak anchoring, and tail/baseline terms improves this to 0.0061 (ridge 0.0251), so the failed direct adaptive-template scale is mostly a calibratable residual-mode problem rather than a template-support problem.  The largest held-out mode association is peak-sample anchoring error (corr -0.338).  ExtraTrees reaches 0.0022; because that is duplicate-readout-level small, it is interpreted only after leakage checks: no run/key/hash overlap and shuffled-target res68=0.8029.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `counts_by_run.csv`, `p04f_benchmark.csv`, `p04f_by_run.csv`, `residual_basis_summary.csv`, `residual_mode_audit.csv`, and `leakage_checks.csv`.

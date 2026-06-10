# Study report: P03g - waveform timing residual negative-control registry

- **Ticket:** 1781015703.872.41e940b8
- **Author:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo
- **Split:** leave one Sample-II analysis run out across runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/p03g_1781015703_872_41e940b8_negative_control_registry.yaml`

## Question

Can waveform residual learners beat an amp-only analytic timewalk correction only when physically meaningful waveform information is present, and fail under preregistered negative controls?

## Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before timing work.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Methods

Traditional method: template-phase timing plus amp-only analytic timewalk, calibrated without the held-out run. The analytic model was fixed to `amp_only` and used no waveform residual learner.

ML method: P03c-style heteroskedastic MLP and tiny 1D CNN residual learners on `analytic_timewalk` residual targets. Hyperparameters were chosen by grouped train-run CV on true waveforms, then frozen for amplitude-only, phase-scrambled, sample-permuted, run-only, and shuffled-target controls.

## Head-to-head summary

| method            |   mean_sigma68_ns |   median_sigma68_ns |   min_sigma68_ns |   max_sigma68_ns |   mean_full_rms_ns |   n_heldout_runs |
|:------------------|------------------:|--------------------:|-----------------:|-----------------:|-------------------:|-----------------:|
| mlp_true_waveform |           1.13174 |             1.12724 |         0.868129 |          1.31835 |            2.25187 |                7 |
| cnn_true_waveform |           1.21696 |             1.20468 |         1.1128   |          1.36435 |            2.32289 |                7 |
| analytic_timewalk |           1.4964  |             1.45871 |         1.18748  |          2.12996 |            2.50469 |                7 |

## Negative controls

| method              |   mean_sigma68_ns |   median_sigma68_ns |   min_sigma68_ns |   max_sigma68_ns |   mean_full_rms_ns |   n_heldout_runs |
|:--------------------|------------------:|--------------------:|-----------------:|-----------------:|-------------------:|-----------------:|
| mlp_amplitude_only  |           1.23899 |             1.26389 |         1.08404  |          1.36807 |            2.32411 |                7 |
| cnn_phase_scrambled |           1.24458 |             1.28429 |         0.966221 |          1.34754 |            2.34067 |                7 |
| cnn_sample_permuted |           1.25036 |             1.31973 |         0.975879 |          1.36005 |            2.34016 |                7 |
| cnn_amplitude_only  |           1.26169 |             1.31691 |         0.882769 |          1.40698 |            2.3564  |                7 |
| mlp_sample_permuted |           1.26351 |             1.30795 |         1.0159   |          1.39981 |            2.34718 |                7 |
| mlp_phase_scrambled |           1.27323 |             1.30212 |         0.964561 |          1.40471 |            2.33804 |                7 |
| cnn_run_only        |           1.4964  |             1.45871 |         1.18748  |          2.12996 |            2.50469 |                7 |
| mlp_run_only        |           1.4964  |             1.45871 |         1.18748  |          2.12996 |            2.50469 |                7 |
| mlp_shuffled_target |           1.50143 |             1.44225 |         1.2127   |          2.13997 |            2.51382 |                7 |
| cnn_shuffled_target |           1.53158 |             1.48853 |         1.18592  |          2.24184 |            2.53157 |                7 |

## True-control gaps and pull widths

| architecture   | true_method         | control_method      |   n_runs |   mean_true_minus_control_sigma68_ns |   run_bootstrap_ci_low |   run_bootstrap_ci_high |   leave_one_run_min |   leave_one_run_max |
|:---------------|:--------------------|:--------------------|---------:|-------------------------------------:|-----------------------:|------------------------:|--------------------:|--------------------:|
| mlp            | mlp_true_waveform   | mlp_amplitude_only  |        7 |                           -0.107247  |              -0.199377 |              0.00996956 |          -0.158033  |         -0.0817549  |
| mlp            | mlp_true_waveform   | mlp_phase_scrambled |        7 |                           -0.141491  |              -0.212333 |             -0.0624911  |          -0.175423  |         -0.118626   |
| mlp            | mlp_true_waveform   | mlp_sample_permuted |        7 |                           -0.131773  |              -0.217639 |             -0.0340208  |          -0.169978  |         -0.104993   |
| mlp            | mlp_true_waveform   | mlp_run_only        |        7 |                           -0.364665  |              -0.573366 |             -0.224856   |          -0.396061  |         -0.266981   |
| mlp            | mlp_true_waveform   | mlp_shuffled_target |        7 |                           -0.369691  |              -0.583357 |             -0.21772    |          -0.410658  |         -0.271177   |
| cnn            | cnn_true_waveform   | cnn_amplitude_only  |        7 |                           -0.0447356 |              -0.140022 |              0.0649941  |          -0.0911001 |         -0.0168705  |
| cnn            | cnn_true_waveform   | cnn_phase_scrambled |        7 |                           -0.0276217 |              -0.117853 |              0.0535891  |          -0.0572252 |          0.00689781 |
| cnn            | cnn_true_waveform   | cnn_sample_permuted |        7 |                           -0.0334005 |              -0.115675 |              0.0454305  |          -0.0623574 |         -0.00325101 |
| cnn            | cnn_true_waveform   | cnn_run_only        |        7 |                           -0.279445  |              -0.49663  |             -0.135429   |          -0.314142  |         -0.17974    |
| cnn            | cnn_true_waveform   | cnn_shuffled_target |        7 |                           -0.314625  |              -0.557191 |             -0.152831   |          -0.355445  |         -0.202138   |
| cnn            | cnn_amplitude_only  | pull_width_sigma68  |        7 |                            0.477959  |               0.376265 |              0.565866   |           0.443343  |          0.519543   |
| cnn            | cnn_phase_scrambled | pull_width_sigma68  |        7 |                            0.454315  |               0.369402 |              0.52992    |           0.424454  |          0.490033   |
| cnn            | cnn_run_only        | pull_width_sigma68  |        7 |                            0.74764   |               0.654224 |              0.854877   |           0.702645  |          0.768827   |
| cnn            | cnn_sample_permuted | pull_width_sigma68  |        7 |                            0.445902  |               0.359502 |              0.521424   |           0.416839  |          0.480538   |
| cnn            | cnn_shuffled_target | pull_width_sigma68  |        7 |                            0.712143  |               0.641871 |              0.834317   |           0.652408  |          0.727478   |
| cnn            | cnn_true_waveform   | pull_width_sigma68  |        7 |                            0.484747  |               0.385693 |              0.581323   |           0.448018  |          0.526225   |
| mlp            | mlp_amplitude_only  | pull_width_sigma68  |        7 |                            0.48124   |               0.398694 |              0.564528   |           0.449049  |          0.514326   |
| mlp            | mlp_phase_scrambled | pull_width_sigma68  |        7 |                            0.520892  |               0.439926 |              0.600556   |           0.491358  |          0.553411   |
| mlp            | mlp_run_only        | pull_width_sigma68  |        7 |                            0.801379  |               0.703522 |              0.930124   |           0.74042   |          0.826862   |
| mlp            | mlp_sample_permuted | pull_width_sigma68  |        7 |                            0.530963  |               0.451208 |              0.6081     |           0.501192  |          0.562497   |
| mlp            | mlp_shuffled_target | pull_width_sigma68  |        7 |                            0.74559   |               0.690854 |              0.832947   |           0.703487  |          0.759479   |
| mlp            | mlp_true_waveform   | pull_width_sigma68  |        7 |                            0.602356  |               0.515516 |              0.669816   |           0.580463  |          0.64046    |

## Per-heldout-run metrics

|   heldout_run | method              |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_baseline_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|--------------:|:--------------------|-------------:|---------:|----------:|--------------:|-----------------------:|---------------:|----------------:|-------------------:|
|            58 | mlp_true_waveform   |     0.868129 | 0.737702 |   1.14262 |       2.56532 |            -0.319354   |    -0.529654   |     -0.0937134  |                219 |
|            58 | cnn_amplitude_only  |     0.882769 | 0.788105 |   1.05087 |       2.62459 |            -0.304714   |    -0.485763   |     -0.17267    |                219 |
|            58 | mlp_phase_scrambled |     0.964561 | 0.827289 |   1.279   |       2.63564 |            -0.222923   |    -0.446112   |      0.0295152  |                219 |
|            58 | cnn_phase_scrambled |     0.966221 | 0.88364  |   1.18068 |       2.64889 |            -0.221263   |    -0.402732   |     -0.0515311  |                219 |
|            58 | cnn_sample_permuted |     0.975879 | 0.852239 |   1.18557 |       2.63302 |            -0.211604   |    -0.397822   |     -0.0520093  |                219 |
|            58 | mlp_sample_permuted |     1.0159   | 0.815568 |   1.27803 |       2.61428 |            -0.171585   |    -0.404441   |      0.0362429  |                219 |
|            58 | mlp_amplitude_only  |     1.08404  | 0.982747 |   1.28753 |       2.64699 |            -0.103445   |    -0.27683    |      0.0149613  |                219 |
|            58 | cnn_true_waveform   |     1.11622  | 1.04267  |   1.23018 |       2.70269 |            -0.0712633  |    -0.290789   |      0.016676   |                219 |
|            58 | cnn_shuffled_target |     1.18592  | 1.13356  |   1.40173 |       2.68003 |            -0.00156054 |    -0.0149889  |      0.00652248 |                219 |
|            58 | analytic_timewalk   |     1.18748  | 1.13497  |   1.40746 |       2.67793 |             0          |     0          |      0          |                219 |
|            58 | cnn_run_only        |     1.18748  | 1.13497  |   1.40746 |       2.67793 |             0          |     0          |      0          |                219 |
|            58 | mlp_run_only        |     1.18748  | 1.13497  |   1.40746 |       2.67793 |             0          |     0          |      0          |                219 |
|            58 | mlp_shuffled_target |     1.2127   | 1.16494  |   1.42842 |       2.70057 |             0.0252145  |    -0.00684607 |      0.063874   |                219 |
|            59 | mlp_true_waveform   |     1.09148  | 1.03193  |   1.17975 |       2.32865 |            -0.367223   |    -0.455448   |     -0.261132   |               2289 |
|            59 | cnn_phase_scrambled |     1.33513  | 1.29535  |   1.38154 |       2.42769 |            -0.123573   |    -0.204375   |     -0.038485   |               2289 |
|            59 | cnn_sample_permuted |     1.33675  | 1.29758  |   1.38369 |       2.43162 |            -0.121961   |    -0.203124   |     -0.0333837  |               2289 |
|            59 | cnn_amplitude_only  |     1.34501  | 1.26848  |   1.40248 |       2.43005 |            -0.113694   |    -0.209383   |     -0.0289106  |               2289 |
|            59 | mlp_amplitude_only  |     1.35169  | 1.28724  |   1.40614 |       2.42429 |            -0.107021   |    -0.204593   |     -0.0212919  |               2289 |
|            59 | cnn_true_waveform   |     1.36435  | 1.32514  |   1.41188 |       2.44148 |            -0.0943623  |    -0.174863   |     -0.0085532  |               2289 |
|            59 | mlp_phase_scrambled |     1.37017  | 1.30443  |   1.45139 |       2.50371 |            -0.0885395  |    -0.177744   |      0.0104717  |               2289 |
|            59 | mlp_sample_permuted |     1.38394  | 1.31834  |   1.46649 |       2.51539 |            -0.0747691  |    -0.162068   |      0.0228954  |               2289 |
|            59 | analytic_timewalk   |     1.45871  | 1.38881  |   1.5303  |       2.54019 |             0          |     0          |      0          |               2289 |
|            59 | cnn_run_only        |     1.45871  | 1.38881  |   1.5303  |       2.54019 |             0          |     0          |      0          |               2289 |
|            59 | mlp_run_only        |     1.45871  | 1.38881  |   1.5303  |       2.54019 |             0          |     0          |      0          |               2289 |
|            59 | mlp_shuffled_target |     1.47961  | 1.40533  |   1.55776 |       2.55503 |             0.0209049  |     0.00305394 |      0.0424895  |               2289 |
|            59 | cnn_shuffled_target |     1.48853  | 1.40869  |   1.5638  |       2.55837 |             0.0298228  |     0.0139945  |      0.0462254  |               2289 |
|            60 | mlp_true_waveform   |     1.12724  | 1.06881  |   1.19234 |       2.29468 |            -0.216461   |    -0.29588    |     -0.133903   |               2424 |
|            60 | mlp_sample_permuted |     1.1404   | 1.05164  |   1.22327 |       2.28723 |            -0.203301   |    -0.281992   |     -0.115895   |               2424 |
|            60 | mlp_amplitude_only  |     1.16141  | 1.08573  |   1.22583 |       2.29422 |            -0.182297   |    -0.253705   |     -0.114416   |               2424 |
|            60 | cnn_sample_permuted |     1.16222  | 1.08005  |   1.27002 |       2.34933 |            -0.181483   |    -0.270707   |     -0.0680538  |               2424 |
|            60 | cnn_phase_scrambled |     1.16245  | 1.09851  |   1.28744 |       2.35661 |            -0.181256   |    -0.253468   |     -0.0567248  |               2424 |
|            60 | cnn_true_waveform   |     1.17459  | 1.09482  |   1.2785  |       2.33498 |            -0.169116   |    -0.254367   |     -0.0682737  |               2424 |
|            60 | mlp_phase_scrambled |     1.25082  | 1.16397  |   1.32951 |       2.29347 |            -0.0928833  |    -0.187074   |     -0.0100282  |               2424 |
|            60 | cnn_amplitude_only  |     1.25289  | 1.16988  |   1.33394 |       2.37157 |            -0.0908172  |    -0.174361   |     -0.00375694 |               2424 |
|            60 | mlp_shuffled_target |     1.33262  | 1.27918  |   1.40522 |       2.3942  |            -0.0110856  |    -0.0189059  |      0.0124342  |               2424 |
|            60 | analytic_timewalk   |     1.3437   | 1.27872  |   1.40735 |       2.39529 |             0          |     0          |      0          |               2424 |
|            60 | cnn_run_only        |     1.3437   | 1.27872  |   1.40735 |       2.39529 |             0          |     0          |      0          |               2424 |
|            60 | mlp_run_only        |     1.3437   | 1.27872  |   1.40735 |       2.39529 |             0          |     0          |      0          |               2424 |
|            60 | cnn_shuffled_target |     1.36039  | 1.30313  |   1.43145 |       2.40855 |             0.0166888  |     0.0100352  |      0.0349429  |               2424 |
|            61 | mlp_true_waveform   |     1.17919  | 1.1249   |   1.23717 |       2.43379 |            -0.95077    |    -1.03305    |     -0.810141   |               2799 |
|            61 | cnn_true_waveform   |     1.25229  | 1.18547  |   1.29208 |       2.56443 |            -0.877674   |    -0.951189   |     -0.752467   |               2799 |
|            61 | mlp_amplitude_only  |     1.26389  | 1.1964   |   1.31294 |       2.57867 |            -0.866074   |    -0.936091   |     -0.736766   |               2799 |
|            61 | cnn_sample_permuted |     1.27079  | 1.21466  |   1.31692 |       2.57716 |            -0.859176   |    -0.928782   |     -0.729843   |               2799 |
|            61 | cnn_phase_scrambled |     1.27224  | 1.21436  |   1.3121  |       2.57712 |            -0.857727   |    -0.926789   |     -0.729599   |               2799 |
|            61 | mlp_phase_scrambled |     1.30212  | 1.22286  |   1.35932 |       2.57033 |            -0.827844   |    -0.927161   |     -0.699959   |               2799 |
|            61 | mlp_sample_permuted |     1.30795  | 1.25545  |   1.36798 |       2.56762 |            -0.822015   |    -0.894484   |     -0.693174   |               2799 |
|            61 | cnn_amplitude_only  |     1.31691  | 1.24881  |   1.38065 |       2.61062 |            -0.813051   |    -0.888369   |     -0.686482   |               2799 |
|            61 | analytic_timewalk   |     2.12996  | 1.98455  |   2.21051 |       3.00806 |             0          |     0          |      0          |               2799 |
|            61 | cnn_run_only        |     2.12996  | 1.98455  |   2.21051 |       3.00806 |             0          |     0          |      0          |               2799 |
|            61 | mlp_run_only        |     2.12996  | 1.98455  |   2.21051 |       3.00806 |             0          |     0          |      0          |               2799 |
|            61 | mlp_shuffled_target |     2.13997  | 2.00772  |   2.22152 |       3.0201  |             0.0100094  |    -0.00915282 |      0.0368713  |               2799 |
|            61 | cnn_shuffled_target |     2.24184  | 2.16242  |   2.36551 |       3.09268 |             0.111873   |     0.101726   |      0.188516   |               2799 |
|            62 | mlp_true_waveform   |     1.12275  | 1.06366  |   1.18339 |       2.39013 |            -0.346257   |    -0.412138   |     -0.272577   |               2421 |
|            62 | cnn_phase_scrambled |     1.28429  | 1.23693  |   1.33883 |       2.46416 |            -0.184715   |    -0.24507    |     -0.113078   |               2421 |
|            62 | cnn_true_waveform   |     1.29378  | 1.22957  |   1.33816 |       2.47082 |            -0.175224   |    -0.247644   |     -0.109365   |               2421 |
|            62 | cnn_amplitude_only  |     1.30257  | 1.22339  |   1.3687  |       2.47569 |            -0.166436   |    -0.252803   |     -0.0859821  |               2421 |
|            62 | cnn_sample_permuted |     1.31973  | 1.26455  |   1.37226 |       2.47569 |            -0.149277   |    -0.218763   |     -0.0754864  |               2421 |
|            62 | mlp_amplitude_only  |     1.32293  | 1.25158  |   1.38132 |       2.48583 |            -0.146077   |    -0.225548   |     -0.0700952  |               2421 |
|            62 | mlp_phase_scrambled |     1.36398  | 1.30126  |   1.43819 |       2.49342 |            -0.105023   |    -0.173843   |     -0.0237838  |               2421 |
|            62 | mlp_sample_permuted |     1.37568  | 1.3035   |   1.45328 |       2.50384 |            -0.0933205  |    -0.16634    |     -0.00199615 |               2421 |
|            62 | analytic_timewalk   |     1.469    | 1.40577  |   1.51714 |       2.58419 |             0          |     0          |      0          |               2421 |
|            62 | cnn_run_only        |     1.469    | 1.40577  |   1.51714 |       2.58419 |             0          |     0          |      0          |               2421 |
|            62 | mlp_run_only        |     1.469    | 1.40577  |   1.51714 |       2.58419 |             0          |     0          |      0          |               2421 |
|            62 | mlp_shuffled_target |     1.47623  | 1.42365  |   1.52818 |       2.5835  |             0.00722157 |    -0.00350876 |      0.0276802  |               2421 |
|            62 | cnn_shuffled_target |     1.53323  | 1.46006  |   1.59193 |       2.62174 |             0.064225   |     0.0389177  |      0.0846195  |               2421 |
|            63 | cnn_true_waveform   |     1.1128   | 1.01428  |   1.25577 |       2.46453 |            -0.27852    |    -0.388372   |     -0.138066   |               1110 |
|            63 | mlp_true_waveform   |     1.21502  | 1.11894  |   1.30784 |       2.4486  |            -0.1763     |    -0.28659    |     -0.0582248  |               1110 |
|            63 | cnn_amplitude_only  |     1.32473  | 1.21262  |   1.43254 |       2.54393 |            -0.0665931  |    -0.195756   |      0.0643835  |               1110 |
|            63 | cnn_sample_permuted |     1.3271   | 1.22022  |   1.40122 |       2.51485 |            -0.0642223  |    -0.178314   |      0.0402579  |               1110 |
|            63 | cnn_phase_scrambled |     1.34754  | 1.23688  |   1.42068 |       2.51944 |            -0.0437809  |    -0.169681   |      0.0575668  |               1110 |
|            63 | mlp_amplitude_only  |     1.36807  | 1.24421  |   1.47202 |       2.52373 |            -0.0232516  |    -0.162072   |      0.106294   |               1110 |
|            63 | analytic_timewalk   |     1.39132  | 1.28795  |   1.46912 |       2.62807 |             0          |     0          |      0          |               1110 |
|            63 | cnn_run_only        |     1.39132  | 1.28795  |   1.46912 |       2.62807 |             0          |    -1.9984e-15 |      0          |               1110 |
|            63 | mlp_run_only        |     1.39132  | 1.28795  |   1.46912 |       2.62807 |             0          |     0          |      0          |               1110 |
|            63 | cnn_shuffled_target |     1.39522  | 1.2885   |   1.46709 |       2.6269  |             0.00389694 |    -0.0128     |      0.00979483 |               1110 |
|            63 | mlp_sample_permuted |     1.39981  | 1.29581  |   1.52456 |       2.55332 |             0.00849146 |    -0.108365   |      0.139119   |               1110 |
|            63 | mlp_phase_scrambled |     1.40471  | 1.3015   |   1.50064 |       2.5037  |             0.0133863  |    -0.106173   |      0.129485   |               1110 |
|            63 | mlp_shuffled_target |     1.42664  | 1.32369  |   1.51675 |       2.65    |             0.0353155  |     0.00637686 |      0.0591216  |               1110 |
|            65 | mlp_amplitude_only  |     1.12088  | 0.794524 |   1.40417 |       1.31504 |            -0.373756   |    -0.702489   |     -0.106349   |                198 |
|            65 | cnn_true_waveform   |     1.20468  | 0.81336  |   1.40885 |       1.2813  |            -0.289957   |    -0.670109   |     -0.0940985  |                198 |
|            65 | mlp_sample_permuted |     1.2209   | 0.9777   |   1.5475  |       1.38858 |            -0.273743   |    -0.510704   |      0.060225   |                198 |
|            65 | mlp_phase_scrambled |     1.25625  | 0.920704 |   1.59285 |       1.36604 |            -0.238388   |    -0.55486    |      0.0405489  |                198 |
|            65 | mlp_true_waveform   |     1.31835  | 0.997552 |   1.58613 |       1.30192 |            -0.176287   |    -0.529404   |      0.123998   |                198 |
|            65 | cnn_phase_scrambled |     1.34419  | 1.02832  |   1.59491 |       1.39075 |            -0.150448   |    -0.467258   |      0.152649   |                198 |
|            65 | cnn_sample_permuted |     1.36005  | 1.05978  |   1.61368 |       1.39948 |            -0.134588   |    -0.440615   |      0.182099   |                198 |
|            65 | cnn_amplitude_only  |     1.40698  | 1.08539  |   1.62813 |       1.43837 |            -0.0876606  |    -0.433779   |      0.191162   |                198 |
|            65 | mlp_shuffled_target |     1.44225  | 1.31149  |   1.65511 |       1.69335 |            -0.0523934  |    -0.092685   |      0.00146324 |                198 |
|            65 | analytic_timewalk   |     1.49464  | 1.32219  |   1.66053 |       1.69913 |             0          |     0          |      0          |                198 |
|            65 | cnn_run_only        |     1.49464  | 1.32219  |   1.66053 |       1.69913 |             0          |     0          |      0          |                198 |
|            65 | mlp_run_only        |     1.49464  | 1.32219  |   1.66053 |       1.69913 |             0          |     0          |      0          |                198 |
|            65 | cnn_shuffled_target |     1.51595  | 1.34518  |   1.69814 |       1.73275 |             0.0213137  |    -0.0042238  |      0.0646988  |                198 |

## Calibration and leakage checks

|   heldout_run | method              | architecture   | control         |   n_pulses |   pred_sigma_median_ns |   abs_error_median_ns |   pull_width_sigma68 |   pull_rms |
|--------------:|:--------------------|:---------------|:----------------|-----------:|-----------------------:|----------------------:|---------------------:|-----------:|
|            58 | mlp_true_waveform   | mlp            | true_waveform   |        219 |                1.84826 |              0.551381 |             0.373734 |   1.74876  |
|            58 | mlp_amplitude_only  | mlp            | amplitude_only  |        219 |                1.75961 |              0.349073 |             0.282728 |   1.14232  |
|            58 | mlp_phase_scrambled | mlp            | phase_scrambled |        219 |                1.77915 |              0.33385  |             0.325781 |   0.950134 |
|            58 | mlp_sample_permuted | mlp            | sample_permuted |        219 |                1.7717  |              0.36833  |             0.341759 |   0.997024 |
|            58 | mlp_run_only        | mlp            | run_only        |        219 |                2.00334 |              1.29776  |             0.830742 |   1.23635  |
|            58 | mlp_shuffled_target | mlp            | shuffled_target |        219 |                2.43852 |              1.29598  |             0.722716 |   0.967399 |
|            58 | cnn_true_waveform   | cnn            | true_waveform   |        219 |                2.14658 |              0.355545 |             0.235877 |   0.919704 |
|            58 | cnn_amplitude_only  | cnn            | amplitude_only  |        219 |                1.8042  |              0.271749 |             0.228449 |   1.11149  |
|            58 | cnn_phase_scrambled | cnn            | phase_scrambled |        219 |                2.15541 |              0.278142 |             0.240009 |   0.917782 |
|            58 | cnn_sample_permuted | cnn            | sample_permuted |        219 |                2.19258 |              0.248684 |             0.238086 |   0.934771 |
|            58 | cnn_run_only        | cnn            | run_only        |        219 |                2.17786 |              1.15835  |             0.764171 |   1.13728  |
|            58 | cnn_shuffled_target | cnn            | shuffled_target |        219 |                2.53419 |              1.25602  |             0.655227 |   1.09428  |
|            59 | mlp_true_waveform   | mlp            | true_waveform   |       2289 |                1.38725 |              0.499379 |             0.619124 |   0.996218 |
|            59 | mlp_amplitude_only  | mlp            | amplitude_only  |       2289 |                1.72452 |              0.533598 |             0.517703 |   0.984689 |
|            59 | mlp_phase_scrambled | mlp            | phase_scrambled |       2289 |                1.68912 |              0.59825  |             0.585426 |   1.11401  |
|            59 | mlp_sample_permuted | mlp            | sample_permuted |       2289 |                1.73872 |              0.614965 |             0.572419 |   1.10669  |
|            59 | mlp_run_only        | mlp            | run_only        |       2289 |                2.48885 |              1.17259  |             0.663674 |   0.94187  |
|            59 | mlp_shuffled_target | mlp            | shuffled_target |       2289 |                2.51759 |              1.15252  |             0.702307 |   0.950322 |
|            59 | cnn_true_waveform   | cnn            | true_waveform   |       2289 |                1.88192 |              0.499044 |             0.553616 |   0.948801 |
|            59 | cnn_amplitude_only  | cnn            | amplitude_only  |       2289 |                1.76059 |              0.572926 |             0.527568 |   1.00427  |
|            59 | cnn_phase_scrambled | cnn            | phase_scrambled |       2289 |                2.00312 |              0.504605 |             0.497721 |   0.965252 |
|            59 | cnn_sample_permuted | cnn            | sample_permuted |       2289 |                1.93071 |              0.511342 |             0.496417 |   1.00174  |
|            59 | cnn_run_only        | cnn            | run_only        |       2289 |                1.88154 |              1.18401  |             0.87789  |   1.24588  |
|            59 | cnn_shuffled_target | cnn            | shuffled_target |       2289 |                2.44044 |              1.20921  |             0.676489 |   0.932875 |
|            60 | mlp_true_waveform   | mlp            | true_waveform   |       2424 |                1.58324 |              0.554884 |             0.564268 |   0.819641 |
|            60 | mlp_amplitude_only  | mlp            | amplitude_only  |       2424 |                1.98335 |              0.495286 |             0.425228 |   0.860217 |
|            60 | mlp_phase_scrambled | mlp            | phase_scrambled |       2424 |                1.91865 |              0.602013 |             0.486179 |   0.911269 |
|            60 | mlp_sample_permuted | mlp            | sample_permuted |       2424 |                1.90239 |              0.650735 |             0.465483 |   0.916082 |
|            60 | mlp_run_only        | mlp            | run_only        |       2424 |                2.44392 |              1.17667  |             0.648481 |   0.933297 |
|            60 | mlp_shuffled_target | mlp            | shuffled_target |       2424 |                2.52194 |              1.1707   |             0.662254 |   0.930775 |
|            60 | cnn_true_waveform   | cnn            | true_waveform   |       2424 |                2.01263 |              0.47663  |             0.460006 |   0.895158 |
|            60 | cnn_amplitude_only  | cnn            | amplitude_only  |       2424 |                1.93638 |              0.455101 |             0.441224 |   0.882285 |
|            60 | cnn_phase_scrambled | cnn            | phase_scrambled |       2424 |                2.20185 |              0.448084 |             0.422729 |   0.895781 |
|            60 | cnn_sample_permuted | cnn            | sample_permuted |       2424 |                2.20788 |              0.437766 |             0.416005 |   0.909538 |
|            60 | cnn_run_only        | cnn            | run_only        |       2424 |                2.38666 |              1.20708  |             0.66404  |   0.955691 |
|            60 | cnn_shuffled_target | cnn            | shuffled_target |       2424 |                2.50975 |              1.19856  |             0.637779 |   0.90263  |
|            61 | mlp_true_waveform   | mlp            | true_waveform   |       2799 |                1.46064 |              0.68803  |             0.733715 |   1.22244  |
|            61 | mlp_amplitude_only  | mlp            | amplitude_only  |       2799 |                1.67324 |              0.626934 |             0.674386 |   1.25899  |
|            61 | mlp_phase_scrambled | mlp            | phase_scrambled |       2799 |                1.67988 |              0.673223 |             0.698098 |   1.22237  |
|            61 | mlp_sample_permuted | mlp            | sample_permuted |       2799 |                1.66962 |              0.66788  |             0.709589 |   1.30551  |
|            61 | mlp_run_only        | mlp            | run_only        |       2799 |                2.12336 |              1.89353  |             1.16713  |   1.44654  |
|            61 | mlp_shuffled_target | mlp            | shuffled_target |       2799 |                2.47158 |              1.88706  |             0.998208 |   1.21315  |
|            61 | cnn_true_waveform   | cnn            | true_waveform   |       2799 |                1.76553 |              0.610861 |             0.705123 |   1.12848  |
|            61 | cnn_amplitude_only  | cnn            | amplitude_only  |       2799 |                1.67038 |              0.649967 |             0.685653 |   1.24195  |
|            61 | cnn_phase_scrambled | cnn            | phase_scrambled |       2799 |                2.00233 |              0.598739 |             0.633481 |   1.15341  |
|            61 | cnn_sample_permuted | cnn            | sample_permuted |       2799 |                2.07012 |              0.593062 |             0.620283 |   1.13503  |
|            61 | cnn_run_only        | cnn            | run_only        |       2799 |                2.43536 |              1.89511  |             1.01761  |   1.26122  |
|            61 | cnn_shuffled_target | cnn            | shuffled_target |       2799 |                2.47631 |              1.97024  |             1.07056  |   1.29026  |
|            62 | mlp_true_waveform   | mlp            | true_waveform   |       2421 |                1.4184  |              0.534887 |             0.665466 |   1.47555  |
|            62 | mlp_amplitude_only  | mlp            | amplitude_only  |       2421 |                1.79433 |              0.517791 |             0.508712 |   0.991112 |
|            62 | mlp_phase_scrambled | mlp            | phase_scrambled |       2421 |                1.70493 |              0.613997 |             0.575333 |   1.02755  |
|            62 | mlp_sample_permuted | mlp            | sample_permuted |       2421 |                1.73317 |              0.597812 |             0.56691  |   1.03617  |
|            62 | mlp_run_only        | mlp            | run_only        |       2421 |                2.09364 |              1.23201  |             0.795917 |   1.16079  |
|            62 | mlp_shuffled_target | mlp            | shuffled_target |       2421 |                2.39468 |              1.21344  |             0.715601 |   1.12968  |
|            62 | cnn_true_waveform   | cnn            | true_waveform   |       2421 |                1.94005 |              0.524498 |             0.525638 |   0.965048 |
|            62 | cnn_amplitude_only  | cnn            | amplitude_only  |       2421 |                1.79598 |              0.509217 |             0.500851 |   0.999518 |
|            62 | cnn_phase_scrambled | cnn            | phase_scrambled |       2421 |                2.07745 |              0.489355 |             0.489689 |   1.00851  |
|            62 | cnn_sample_permuted | cnn            | sample_permuted |       2421 |                2.16591 |              0.503247 |             0.473832 |   1.02483  |
|            62 | cnn_run_only        | cnn            | run_only        |       2421 |                2.68308 |              1.20665  |             0.621065 |   0.905783 |
|            62 | cnn_shuffled_target | cnn            | shuffled_target |       2421 |                2.55205 |              1.24278  |             0.659627 |   0.944707 |
|            63 | mlp_true_waveform   | mlp            | true_waveform   |       1110 |                1.44379 |              0.5524   |             0.62154  |   1.03461  |
|            63 | mlp_amplitude_only  | mlp            | amplitude_only  |       1110 |                1.77314 |              0.515082 |             0.500022 |   1.00112  |
|            63 | mlp_phase_scrambled | mlp            | phase_scrambled |       1110 |                1.76085 |              0.564831 |             0.52995  |   0.982305 |
|            63 | mlp_sample_permuted | mlp            | sample_permuted |       1110 |                1.72586 |              0.597127 |             0.547638 |   1.01544  |
|            63 | mlp_run_only        | mlp            | run_only        |       1110 |                2.22685 |              1.1569   |             0.708508 |   1.09622  |
|            63 | mlp_shuffled_target | mlp            | shuffled_target |       1110 |                2.49022 |              1.15287  |             0.720685 |   1.10531  |
|            63 | cnn_true_waveform   | cnn            | true_waveform   |       1110 |                2.02926 |              0.4984   |             0.451297 |   1.00494  |
|            63 | cnn_amplitude_only  | cnn            | amplitude_only  |       1110 |                1.72452 |              0.498819 |             0.509538 |   1.00996  |
|            63 | cnn_phase_scrambled | cnn            | phase_scrambled |       1110 |                2.07816 |              0.465548 |             0.448786 |   1.03537  |
|            63 | cnn_sample_permuted | cnn            | sample_permuted |       1110 |                2.05154 |              0.467487 |             0.449616 |   1.01833  |
|            63 | cnn_run_only        | cnn            | run_only        |       1110 |                2.36122 |              1.11222  |             0.668188 |   1.03384  |
|            63 | cnn_shuffled_target | cnn            | shuffled_target |       1110 |                2.48487 |              1.13627  |             0.620134 |   0.967592 |
|            65 | mlp_true_waveform   | mlp            | true_waveform   |        198 |                1.53306 |              0.696234 |             0.638645 |   0.729813 |
|            65 | mlp_amplitude_only  | mlp            | amplitude_only  |        198 |                1.97398 |              0.511092 |             0.459902 |   0.561794 |
|            65 | mlp_phase_scrambled | mlp            | phase_scrambled |        198 |                2.0725  |              0.632987 |             0.445478 |   0.58453  |
|            65 | mlp_sample_permuted | mlp            | sample_permuted |        198 |                2.01655 |              0.763429 |             0.51294  |   0.640876 |
|            65 | mlp_run_only        | mlp            | run_only        |        198 |                2.09604 |              1.14706  |             0.7952   |   0.821023 |
|            65 | mlp_shuffled_target | mlp            | shuffled_target |        198 |                2.38073 |              1.15042  |             0.697359 |   0.704018 |
|            65 | cnn_true_waveform   | cnn            | true_waveform   |        198 |                2.05488 |              0.532617 |             0.461672 |   0.588859 |
|            65 | cnn_amplitude_only  | cnn            | amplitude_only  |        198 |                1.79681 |              0.457295 |             0.452427 |   0.597205 |
|            65 | cnn_phase_scrambled | cnn            | phase_scrambled |        198 |                2.13158 |              0.427652 |             0.447792 |   0.564116 |
|            65 | cnn_sample_permuted | cnn            | sample_permuted |        198 |                2.11876 |              0.429536 |             0.427078 |   0.554566 |
|            65 | cnn_run_only        | cnn            | run_only        |        198 |                2.6861  |              1.14706  |             0.620518 |   0.640668 |
|            65 | cnn_shuffled_target | cnn            | shuffled_target |        198 |                2.54362 |              1.1739   |             0.66519  |   0.679959 |

|   heldout_run | check                          |   value | detail                                                                                                                                                                                                                                               |
|--------------:|:-------------------------------|--------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|            58 | analytic_candidate             |       0 | amp_only, alpha=100.0                                                                                                                                                                                                                                |
|            58 | feature_audit                  |       0 | true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature |
|            58 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                         |
|            59 | analytic_candidate             |       0 | amp_only, alpha=100.0                                                                                                                                                                                                                                |
|            59 | feature_audit                  |       0 | true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature |
|            59 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                         |
|            60 | analytic_candidate             |       0 | amp_only, alpha=100.0                                                                                                                                                                                                                                |
|            60 | feature_audit                  |       0 | true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature |
|            60 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                         |
|            61 | analytic_candidate             |       0 | amp_only, alpha=100.0                                                                                                                                                                                                                                |
|            61 | feature_audit                  |       0 | true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature |
|            61 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                         |
|            62 | analytic_candidate             |       0 | amp_only, alpha=100.0                                                                                                                                                                                                                                |
|            62 | feature_audit                  |       0 | true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature |
|            62 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                         |
|            63 | analytic_candidate             |       0 | amp_only, alpha=100.0                                                                                                                                                                                                                                |
|            63 | feature_audit                  |       0 | true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature |
|            63 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                         |
|            65 | analytic_candidate             |       0 | amp_only, alpha=100.0                                                                                                                                                                                                                                |
|            65 | feature_audit                  |       0 | true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature |
|            65 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                         |

The leakage audit found zero train/held-out event-id overlap in every fold. The controls deliberately remove or corrupt waveform meaning without adding event id, event order, pair residuals, other-stave timing, or held-out targets.

## Verdict

`result.json` verdict: `true_waveform_beats_analytic_but_controls_are_not_all_rejected`. Mean sigma68 is analytic `1.496 ns`, MLP true waveform `1.132 ns`, and CNN true waveform `1.217 ns`.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03g_1781015703_872_41e940b8_negative_control_registry.py --config configs/p03g_1781015703_872_41e940b8_negative_control_registry.yaml
```

Artifacts: `reproduction_match_table.csv`, `heldout_run_summary.csv`, `heldout_pair_residuals.csv`, `pooled_summary.csv`, `true_control_gap_summary.csv`, `ml_cv_scan.csv`, `ml_calibration.csv`, `leakage_checks.csv`, `result.json`, `manifest.json`, figures, and raw input hashes.

# S06c: charge-proxy timing pull-width calibration gate

- **Ticket:** `1781059684.1019.46485748`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT under `data/root/root` plus the P06c run-external pair-residual panel
- **Primary split:** leave-one-run-out by run over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65
- **Bootstrap:** event-paired run-block bootstrap with 40 replicates
- **Primary metric:** charge-matched pooled calibration loss; lower is better

## Abstract

This study asks whether charge-proxy timing models provide calibrated per-pair timing uncertainties after matched charge controls. The raw `HRDv` reproduction gate passes exactly, and the winner written to `result.json` is **`phase_conformal_gated_cnn`** with calibration loss **0.0534** and 95% bootstrap CI **[0.0434, 0.0701]**. The best non-traditional model is **`phase_conformal_gated_cnn`**; its pooled calibration-loss delta relative to the traditional robust-width baseline is **-0.6056**.

## Reproduction Gate

Counts are rebuilt directly from raw `HRDv`: reshape each event to 8 channels by 18 samples, subtract the median of samples 0-3, and select B-stave pulses with baseline-subtracted maximum amplitude greater than 1000 ADC. This reproduces the S00 selected-pulse number before any benchmark row is used.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a analytic timing closure is also rerun from raw ROOT as the timing-number reproduction gate:

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals | best_candidate   |   best_alpha |
|:------------------------|--------:|---------:|----------:|-------------------:|:-----------------|-------------:|
| s02_template_phase_base | 2.88915 |  2.75558 |   3.27718 |                198 | amp_only         |          100 |
| s03a_analytic_timewalk  | 1.49464 |  1.33459 |   1.60785 |                198 | amp_only         |          100 |

## Estimands And Equations

For event `e`, downstream staves `a,b`, and timing method `m`, the time-of-flight corrected timestamp is `tau_{e,s,m}=t_{e,s,m}-x_s v_TOF`, with `v_TOF=0.078 ns/cm`. The pair residual is

`r_{eabm}=tau_{e,a,m}-tau_{e,b,m}`.

Each uncertainty model predicts a positive scale `sigma_hat_{eabm}` and the pull is

`z_{eabm}=r_{eabm}/sigma_hat_{eabm}`.

The robust width is `sigma68(x)=(Q_0.84(x)-Q_0.16(x))/2`. Nominal coverages are `C68=P(|z|<=1)` and `C95=P(|z|<=1.96)`. The charge-proxy slope diagnostic fits `r = beta_0 + beta_Q log(1+Q) + epsilon`; `beta_Q` close to zero means residual bias is not drifting with charge proxy.

The primary calibration loss is the mean of `|sigma68(z)-1|`, `|C68-0.682689|`, `|C95-0.95|`, and uncertainty-bin expected calibration error. It penalizes undercoverage and overconservative intervals rather than only timing core width.

## Methods

Traditional baseline: S02 template-phase timing plus the S03 analytic amplitude timewalk correction for the central timestamp, paired with an S04-style atom robust-width lookup for `sigma_hat`. The lookup is trained only on non-held-out runs and falls back through pair, phase, sample-window, and global support levels.

ML/NN methods: ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new phase-conformal atom-gated CNN. They use the same run-external central timing and then learn residual scale from waveform, amplitude, charge proxy, q-template, baseline, phase, sample-window, anomaly, topology, and run-family covariates, excluding event id, raw residual, pull, sigma target, and held-out labels.

Charge matching: methods are compared on identical pair rows and charge bins. The headline table is pooled across all held-out runs, while the charge-bin and run tables show whether a score is driven by a single charge or run support slice.

## Head-To-Head Benchmark

| method                    | method_label                              |     n |   n_runs |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   pull_width68 |   pull_width68_ci_low |   pull_width68_ci_high |   coverage68 |   coverage68_ci_low |   coverage68_ci_high |   coverage95 |   coverage95_ci_low |   coverage95_ci_high |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   calibration_ece |
|:--------------------------|:------------------------------------------|------:|---------:|-------------------:|--------------------------:|---------------------------:|---------------:|----------------------:|-----------------------:|-------------:|--------------------:|---------------------:|-------------:|--------------------:|---------------------:|-------------:|--------------:|----------------------:|------------------:|
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            | 11460 |        7 |          0.0534484 |                 0.0434369 |                  0.0700961 |       0.901022 |              0.856429 |               0.940388 |     0.631937 |            0.568517 |             0.689923 |     0.960995 |            0.956226 |             0.967136 |      1.50399 |       2.41532 |             0.0114311 |         0.0530683 |
| cnn1d                     | 1D-CNN residual scale model               | 11460 |        7 |          0.0973354 |                 0.0807988 |                  0.154484  |       1.00983  |              0.929209 |               1.11455  |     0.454538 |            0.380336 |             0.525443 |     0.936126 |            0.920667 |             0.945764 |      1.5101  |       2.42042 |             0.0129145 |         0.137488  |
| mlp                       | MLP residual scale model                  | 11460 |        7 |          0.103472  |                 0.0643345 |                  0.152552  |       1.05182  |              0.951463 |               1.14405  |     0.516928 |            0.469511 |             0.575594 |     0.876003 |            0.849108 |             0.915301 |      1.64477 |       2.42453 |             0.0138743 |         0.122311  |
| gradient_boosted_trees    | HistGradientBoosting residual scale model | 11460 |        7 |          0.109007  |                 0.0724785 |                  0.207181  |       1.0451   |              0.904084 |               1.2125   |     0.502792 |            0.408957 |             0.571317 |     0.869721 |            0.812919 |             0.918555 |      1.5543  |       2.31556 |             0.0153578 |         0.130751  |
| ridge                     | Ridge residual scale model                | 11460 |        7 |          0.110021  |                 0.0771306 |                  0.199628  |       1.02024  |              0.86789  |               1.16767  |     0.481065 |            0.397129 |             0.581428 |     0.871728 |            0.81469  |             0.931656 |      1.57318 |       2.54659 |             0.0161431 |         0.139949  |
| traditional               | S02/S03/S04 atom robust-width baseline    | 11460 |        7 |          0.659059  |                 0.55785   |                  0.811848  |       2.71207  |              2.47946  |               3.01606  |     0.384991 |            0.293961 |             0.444086 |     0.631588 |            0.517839 |             0.694029 |      1.55109 |       2.66699 |             0.0191099 |         0.308055  |

## Run-Split Bootstrap

|   stratum | method                    |    n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   pull_width68 |   pull_width68_ci_low |   pull_width68_ci_high |   coverage68 |   coverage95 |   sigma68_ns |
|----------:|:--------------------------|-----:|-------------------:|--------------------------:|---------------------------:|---------------:|----------------------:|-----------------------:|-------------:|-------------:|-------------:|
|        58 | phase_conformal_gated_cnn |  219 |          0.0807315 |                 0.0592193 |                  0.11633   |       0.916748 |              0.837307 |               0.983617 |     0.552511 |     0.977169 |      1.44496 |
|        58 | traditional               |  219 |          1.00002   |                 0.746787  |                  1.45197   |       3.91407  |              2.93555  |               5.59359  |     0.342466 |     0.56621  |      1.18748 |
|        59 | phase_conformal_gated_cnn | 2289 |          0.036222  |                 0.0307038 |                  0.0450489 |       0.974835 |              0.925064 |               1.00336  |     0.638707 |     0.954128 |      1.45517 |
|        59 | traditional               | 2289 |          0.500969  |                 0.433137  |                  0.593831  |       2.29731  |              2.08249  |               2.66124  |     0.45391  |     0.707733 |      1.45871 |
|        60 | phase_conformal_gated_cnn | 2424 |          0.0705094 |                 0.0669    |                  0.080341  |       0.820108 |              0.783846 |               0.836498 |     0.651815 |     0.963696 |      1.31669 |
|        60 | traditional               | 2424 |          0.640158  |                 0.528202  |                  0.693212  |       2.71494  |              2.28896  |               2.89361  |     0.403878 |     0.665017 |      1.3437  |
|        61 | phase_conformal_gated_cnn | 2799 |          0.0816349 |                 0.0739142 |                  0.0886687 |       0.92619  |              0.899907 |               0.958053 |     0.536977 |     0.967846 |      1.77103 |
|        61 | traditional               | 2799 |          0.832446  |                 0.783451  |                  0.895317  |       2.97132  |              2.78444  |               3.1993   |     0.255806 |     0.47124  |      2.12996 |
|        62 | phase_conformal_gated_cnn | 2421 |          0.0690428 |                 0.0603464 |                  0.0793391 |       0.854903 |              0.830134 |               0.875983 |     0.730277 |     0.950847 |      1.441   |
|        62 | traditional               | 2421 |          0.569961  |                 0.492176  |                  0.637787  |       2.50677  |              2.21503  |               2.75139  |     0.426683 |     0.690624 |      1.469   |
|        63 | phase_conformal_gated_cnn | 1110 |          0.0578199 |                 0.0496721 |                  0.0667156 |       0.947253 |              0.916187 |               0.986071 |     0.596396 |     0.965766 |      1.47808 |
|        63 | traditional               | 1110 |          0.589972  |                 0.492557  |                  0.68724   |       2.59869  |              2.24042  |               2.90071  |     0.437838 |     0.687387 |      1.39132 |
|        65 | phase_conformal_gated_cnn |  198 |          0.0838919 |                 0.0551612 |                  0.116195  |       0.828315 |              0.789698 |               0.913361 |     0.737374 |     0.989899 |      1.52228 |
|        65 | traditional               |  198 |          0.687806  |                 0.360875  |                  0.922469  |       2.90825  |              1.75277  |               3.73232  |     0.424242 |     0.646465 |      1.49464 |

## Charge-Matched Controls

| stratum             | method                    |    n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   pull_width68 |   coverage68 |   coverage95 |   sigma68_ns |   tail_frac_abs_gt5ns |
|:--------------------|:--------------------------|-----:|-------------------:|--------------------------:|---------------------------:|---------------:|-------------:|-------------:|-------------:|----------------------:|
| charge[1000,4000)   | ridge                     |   60 |          0.0651568 |                 0.0499922 |                  0.235281  |       0.951869 |    0.6       |     1        |     0.871694 |            0          |
| charge[1000,4000)   | phase_conformal_gated_cnn |   60 |          0.078621  |                 0.0667476 |                  0.220197  |       0.883141 |    0.616667  |     0.966667 |     1.27218  |            0          |
| charge[1000,4000)   | cnn1d                     |   60 |          0.119402  |                 0.0944933 |                  0.221755  |       0.856557 |    0.516667  |     0.933333 |     1.26482  |            0          |
| charge[1000,4000)   | gradient_boosted_trees    |   60 |          0.198452  |                 0.135097  |                  0.303479  |       0.675228 |    0.45      |     0.883333 |     1.8244   |            0          |
| charge[1000,4000)   | mlp                       |   60 |          0.217319  |                 0.131997  |                  0.294476  |       0.524887 |    0.5       |     0.916667 |     1.24001  |            0          |
| charge[1000,4000)   | traditional               |   60 |          1.76562   |                 1.59733   |                  2.17344   |       6.58843  |    0.316667  |     0.333333 |     1.00611  |            0          |
| charge[14000,24000) | phase_conformal_gated_cnn | 5990 |          0.0684683 |                 0.0487386 |                  0.0977688 |       0.829498 |    0.646411  |     0.968114 |     1.5331   |            0.00717863 |
| charge[14000,24000) | mlp                       | 5990 |          0.0977837 |                 0.0808375 |                  0.13985   |       0.954066 |    0.5202    |     0.886477 |     1.60341  |            0.00834725 |
| charge[14000,24000) | gradient_boosted_trees    | 5990 |          0.102139  |                 0.0838594 |                  0.215559  |       0.985869 |    0.493155  |     0.878464 |     1.5149   |            0.00934891 |
| charge[14000,24000) | cnn1d                     | 5990 |          0.106302  |                 0.0925306 |                  0.129679  |       0.950154 |    0.452421  |     0.94424  |     1.55916  |            0.00751252 |
| charge[14000,24000) | ridge                     | 5990 |          0.116514  |                 0.0897514 |                  0.162396  |       0.961676 |    0.471786  |     0.876628 |     1.55831  |            0.0103506  |
| charge[14000,24000) | traditional               | 5990 |          0.460577  |                 0.305375  |                  0.646068  |       2.04002  |    0.415359  |     0.682471 |     1.54329  |            0.0138564  |
| charge[24000,40000) | phase_conformal_gated_cnn | 3624 |          0.048945  |                 0.0282784 |                  0.079118  |       1.04788  |    0.600442  |     0.942053 |     1.55262  |            0.0182119  |
| charge[24000,40000) | cnn1d                     | 3624 |          0.134519  |                 0.0781029 |                  0.21374   |       1.15375  |    0.472406  |     0.912252 |     1.54249  |            0.0217991  |
| charge[24000,40000) | ridge                     | 3624 |          0.162506  |                 0.0687358 |                  0.257966  |       1.21796  |    0.507726  |     0.836921 |     1.72697  |            0.0292494  |
| charge[24000,40000) | mlp                       | 3624 |          0.180481  |                 0.127764  |                  0.253007  |       1.28945  |    0.498068  |     0.846302 |     1.69351  |            0.0217991  |
| charge[24000,40000) | gradient_boosted_trees    | 3624 |          0.187652  |                 0.0989846 |                  0.317579  |       1.30489  |    0.503587  |     0.831954 |     1.63791  |            0.0256623  |
| charge[24000,40000) | traditional               | 3624 |          0.454854  |                 0.322331  |                  0.551602  |       1.96186  |    0.39404   |     0.666943 |     1.77525  |            0.0306291  |
| charge[4000,8000)   | phase_conformal_gated_cnn |  285 |          0.0957514 |                 0.0743414 |                  0.202699  |       0.765888 |    0.659649  |     0.961404 |     1.22879  |            0.0175439  |
| charge[4000,8000)   | cnn1d                     |  285 |          0.144512  |                 0.0836096 |                  0.228403  |       0.839584 |    0.421053  |     0.954386 |     1.23591  |            0.0105263  |
| charge[4000,8000)   | ridge                     |  285 |          0.174143  |                 0.127176  |                  0.208053  |       0.618157 |    0.515789  |     0.968421 |     1.14053  |            0.0140351  |
| charge[4000,8000)   | mlp                       |  285 |          0.185022  |                 0.161227  |                  0.219497  |       0.509428 |    0.561404  |     0.936842 |     1.32155  |            0.0245614  |
| charge[4000,8000)   | gradient_boosted_trees    |  285 |          0.196671  |                 0.154633  |                  0.266168  |       0.496386 |    0.519298  |     0.933333 |     1.20214  |            0.0105263  |
| charge[4000,8000)   | traditional               |  285 |          2.07634   |                 1.85307   |                  2.31762   |       7.37213  |    0.14386   |     0.2      |     1.26605  |            0.0105263  |
| charge[40000,80000) | phase_conformal_gated_cnn |   30 |          0.28401   |                 0.093201  |                  0.828432  |       1.64688  |    0.5       |     0.833333 |     3.6784   |            0.266667   |
| charge[40000,80000) | ridge                     |   30 |          0.320858  |                 0.113715  |                  0.905586  |       1.59427  |    0.5       |     0.7      |     6.60268  |            0.4        |
| charge[40000,80000) | mlp                       |   30 |          0.39102   |                 0.114161  |                  0.884195  |       1.64479  |    0.433333  |     0.633333 |     5.6509   |            0.366667   |
| charge[40000,80000) | gradient_boosted_trees    |   30 |          0.397796  |                 0.167671  |                  0.705716  |       1.90202  |    0.5       |     0.7      |     4.56458  |            0.3        |
| charge[40000,80000) | cnn1d                     |   30 |          0.49593   |                 0.111606  |                  2.12959   |       2.08468  |    0.4       |     0.633333 |     4.85102  |            0.333333   |
| charge[40000,80000) | traditional               |   30 |          2.54563   |                 1.59024   |                  4.72044   |       9.13347  |    0.0666667 |     0.2      |     6.49259  |            0.333333   |
| charge[8000,14000)  | phase_conformal_gated_cnn | 1471 |          0.11404   |                 0.0927517 |                  0.135224  |       0.676514 |    0.648538  |     0.980965 |     1.32383  |            0.00611829 |
| charge[8000,14000)  | gradient_boosted_trees    | 1471 |          0.153679  |                 0.122711  |                  0.185261  |       0.658691 |    0.539089  |     0.917743 |     1.35436  |            0.00747791 |
| charge[8000,14000)  | mlp                       | 1471 |          0.15444   |                 0.142473  |                  0.1712    |       0.70113  |    0.543848  |     0.898029 |     1.40497  |            0.00951734 |
| charge[8000,14000)  | ridge                     | 1471 |          0.154693  |                 0.124471  |                  0.180915  |       0.793347 |    0.441196  |     0.917063 |     1.32795  |            0.00951734 |
| charge[8000,14000)  | cnn1d                     | 1471 |          0.158496  |                 0.13316   |                  0.199499  |       0.786327 |    0.424201  |     0.96465  |     1.3461   |            0.00611829 |
| charge[8000,14000)  | traditional               | 1471 |          1.95419   |                 1.76446   |                  2.11935   |       7.47308  |    0.295037  |     0.441876 |     1.23885  |            0.00951734 |

Amplitude-bin companion table:

| stratum            | method                    |    n |   calibration_loss |   pull_width68 |   coverage68 |   coverage95 |   sigma68_ns |
|:-------------------|:--------------------------|-----:|-------------------:|---------------:|-------------:|-------------:|-------------:|
| amp_adc[1000,1500) | ridge                     |  256 |          0.184117  |       0.601823 |     0.484375 |     0.9375   |     1.04003  |
| amp_adc[1000,1500) | mlp                       |  256 |          0.190266  |       0.498774 |     0.558594 |     0.9375   |     1.07925  |
| amp_adc[1000,1500) | phase_conformal_gated_cnn |  256 |          0.202035  |       0.372205 |     0.613281 |     0.953125 |     0.713217 |
| amp_adc[1000,1500) | gradient_boosted_trees    |  256 |          0.215234  |       0.413099 |     0.515625 |     0.941406 |     0.851605 |
| amp_adc[1000,1500) | cnn1d                     |  256 |          0.258354  |       0.401361 |     0.421875 |     0.953125 |     0.6722   |
| amp_adc[1000,1500) | traditional               |  256 |          2.02015   |       7.26439  |     0.144531 |     0.277344 |     0.943987 |
| amp_adc[1500,2500) | phase_conformal_gated_cnn | 3901 |          0.100333  |       0.710134 |     0.651115 |     0.972058 |     1.45683  |
| amp_adc[1500,2500) | mlp                       | 3901 |          0.125974  |       0.821932 |     0.53576  |     0.894386 |     1.49364  |
| amp_adc[1500,2500) | gradient_boosted_trees    | 3901 |          0.129053  |       0.813379 |     0.518072 |     0.899513 |     1.45851  |
| amp_adc[1500,2500) | cnn1d                     | 3901 |          0.141732  |       0.816136 |     0.443732 |     0.951038 |     1.46823  |
| amp_adc[1500,2500) | ridge                     | 3901 |          0.142435  |       0.865719 |     0.455524 |     0.887208 |     1.46501  |
| amp_adc[1500,2500) | traditional               | 3901 |          1.1376    |       4.531    |     0.369649 |     0.58344  |     1.35234  |
| amp_adc[2500,4000) | phase_conformal_gated_cnn | 6811 |          0.0376286 |       0.965227 |     0.624872 |     0.958156 |     1.52437  |
| amp_adc[2500,4000) | cnn1d                     | 6811 |          0.111934  |       1.07354  |     0.4619   |     0.932315 |     1.52271  |
| amp_adc[2500,4000) | mlp                       | 6811 |          0.131894  |       1.13894  |     0.50624  |     0.867567 |     1.68391  |
| amp_adc[2500,4000) | ridge                     | 6811 |          0.133362  |       1.12596  |     0.494788 |     0.866246 |     1.60364  |
| amp_adc[2500,4000) | gradient_boosted_trees    | 6811 |          0.14793   |       1.16331  |     0.493026 |     0.85406  |     1.60385  |
| amp_adc[2500,4000) | traditional               | 6811 |          0.460248  |       2.0448   |     0.415064 |     0.68683  |     1.56158  |
| amp_adc[4000,7000) | phase_conformal_gated_cnn |  492 |          0.0787321 |       1.11813  |     0.587398 |     0.916667 |     1.62638  |
| amp_adc[4000,7000) | cnn1d                     |  492 |          0.208218  |       1.35945  |     0.455285 |     0.861789 |     1.6406   |
| amp_adc[4000,7000) | ridge                     |  492 |          0.208359  |       1.30818  |     0.49187  |     0.79065  |     2.41689  |
| amp_adc[4000,7000) | gradient_boosted_trees    |  492 |          0.223055  |       1.42794  |     0.510163 |     0.813008 |     1.73392  |
| amp_adc[4000,7000) | mlp                       |  492 |          0.232441  |       1.44415  |     0.493902 |     0.815041 |     1.9872   |
| amp_adc[4000,7000) | traditional               |  492 |          0.773289  |       2.61668  |     0.215447 |     0.432927 |     2.55444  |

ML-minus-traditional deltas. Negative calibration-loss delta favors the ML/NN method after matched support:

| dimension   | stratum             | method                    |   ml_minus_traditional_calibration_loss |   ml_minus_traditional_calibration_loss_ci_low |   ml_minus_traditional_calibration_loss_ci_high |   ml_minus_traditional_pull_width68 |   ml_minus_traditional_sigma68_ns |   ml_minus_traditional_tail_frac_abs_gt5ns |
|:------------|:--------------------|:--------------------------|----------------------------------------:|-----------------------------------------------:|------------------------------------------------:|------------------------------------:|----------------------------------:|-------------------------------------------:|
| charge_bin  | charge[40000,80000) | phase_conformal_gated_cnn |                               -2.26162  |                                     nan        |                                      nan        |                           -7.48659  |                        -2.8142    |                                -0.0666667  |
| charge_bin  | charge[40000,80000) | ridge                     |                               -2.22477  |                                     nan        |                                      nan        |                           -7.5392   |                         0.110092  |                                 0.0666667  |
| charge_bin  | charge[40000,80000) | mlp                       |                               -2.15461  |                                     nan        |                                      nan        |                           -7.48869  |                        -0.841697  |                                 0.0333333  |
| charge_bin  | charge[40000,80000) | gradient_boosted_trees    |                               -2.14783  |                                     nan        |                                      nan        |                           -7.23145  |                        -1.92801   |                                -0.0333333  |
| charge_bin  | charge[40000,80000) | cnn1d                     |                               -2.0497   |                                     nan        |                                      nan        |                           -7.04879  |                        -1.64157   |                                 0          |
| charge_bin  | charge[4000,8000)   | phase_conformal_gated_cnn |                               -1.98059  |                                     nan        |                                      nan        |                           -6.60624  |                        -0.0372516 |                                 0.00701754 |
| charge_bin  | charge[4000,8000)   | cnn1d                     |                               -1.93183  |                                     nan        |                                      nan        |                           -6.53255  |                        -0.0301376 |                                 0          |
| charge_bin  | charge[4000,8000)   | ridge                     |                               -1.9022   |                                     nan        |                                      nan        |                           -6.75397  |                        -0.125512  |                                 0.00350877 |
| charge_bin  | charge[4000,8000)   | mlp                       |                               -1.89132  |                                     nan        |                                      nan        |                           -6.8627   |                         0.0555044 |                                 0.0140351  |
| charge_bin  | charge[4000,8000)   | gradient_boosted_trees    |                               -1.87967  |                                     nan        |                                      nan        |                           -6.87574  |                        -0.0639015 |                                 0          |
| charge_bin  | charge[8000,14000)  | phase_conformal_gated_cnn |                               -1.84015  |                                     nan        |                                      nan        |                           -6.79657  |                         0.0849816 |                                -0.00339905 |
| charge_bin  | charge[8000,14000)  | gradient_boosted_trees    |                               -1.80051  |                                     nan        |                                      nan        |                           -6.81439  |                         0.115511  |                                -0.00203943 |
| charge_bin  | charge[8000,14000)  | mlp                       |                               -1.79975  |                                     nan        |                                      nan        |                           -6.77195  |                         0.166128  |                                 0          |
| charge_bin  | charge[8000,14000)  | ridge                     |                               -1.79949  |                                     nan        |                                      nan        |                           -6.67973  |                         0.0891009 |                                 0          |
| charge_bin  | charge[8000,14000)  | cnn1d                     |                               -1.79569  |                                     nan        |                                      nan        |                           -6.68675  |                         0.107254  |                                -0.00339905 |
| charge_bin  | charge[1000,4000)   | ridge                     |                               -1.70046  |                                     nan        |                                      nan        |                           -5.63656  |                        -0.134417  |                                 0          |
| charge_bin  | charge[1000,4000)   | phase_conformal_gated_cnn |                               -1.687    |                                     nan        |                                      nan        |                           -5.70529  |                         0.266064  |                                 0          |
| charge_bin  | charge[1000,4000)   | cnn1d                     |                               -1.64622  |                                     nan        |                                      nan        |                           -5.73188  |                         0.25871   |                                 0          |
| charge_bin  | charge[1000,4000)   | gradient_boosted_trees    |                               -1.56717  |                                     nan        |                                      nan        |                           -5.91321  |                         0.818293  |                                 0          |
| charge_bin  | charge[1000,4000)   | mlp                       |                               -1.5483   |                                     nan        |                                      nan        |                           -6.06355  |                         0.233903  |                                 0          |
| all         | all                 | phase_conformal_gated_cnn |                               -0.605611 |                                      -0.696717 |                                       -0.506898 |                           -1.81105  |                        -0.0471061 |                                -0.00767888 |
| all         | all                 | cnn1d                     |                               -0.561724 |                                      -0.63028  |                                       -0.489827 |                           -1.70225  |                        -0.0409947 |                                -0.00619546 |
| all         | all                 | mlp                       |                               -0.555587 |                                      -0.617404 |                                       -0.507052 |                           -1.66025  |                         0.0936821 |                                -0.0052356  |
| all         | all                 | gradient_boosted_trees    |                               -0.550053 |                                      -0.593663 |                                       -0.447206 |                           -1.66697  |                         0.0032034 |                                -0.00375218 |
| all         | all                 | ridge                     |                               -0.549039 |                                      -0.598618 |                                       -0.463421 |                           -1.69184  |                         0.0220909 |                                -0.00296684 |
| charge_bin  | charge[24000,40000) | phase_conformal_gated_cnn |                               -0.405909 |                                     nan        |                                      nan        |                           -0.913979 |                        -0.222623  |                                -0.0124172  |
| charge_bin  | charge[14000,24000) | phase_conformal_gated_cnn |                               -0.392109 |                                     nan        |                                      nan        |                           -1.21052  |                        -0.010194  |                                -0.0066778  |
| charge_bin  | charge[14000,24000) | mlp                       |                               -0.362793 |                                     nan        |                                      nan        |                           -1.08595  |                         0.0601204 |                                -0.00550918 |
| charge_bin  | charge[14000,24000) | gradient_boosted_trees    |                               -0.358438 |                                     nan        |                                      nan        |                           -1.05415  |                        -0.0283954 |                                -0.00450751 |
| charge_bin  | charge[14000,24000) | cnn1d                     |                               -0.354275 |                                     nan        |                                      nan        |                           -1.08986  |                         0.0158678 |                                -0.00634391 |

## Charge-Slope And Support Diagnostics

| method                    | method_label                              |   charge_slope_ns_per_log_charge |   charge_slope_ci_low |   charge_slope_ci_high |   abs_pull_slope_per_log_charge |   abs_pull_slope_ci_low |   abs_pull_slope_ci_high |
|:--------------------------|:------------------------------------------|---------------------------------:|----------------------:|-----------------------:|--------------------------------:|------------------------:|-------------------------:|
| cnn1d                     | 1D-CNN residual scale model               |                       -0.487923  |                   nan |                    nan |                       0.177259  |                     nan |                      nan |
| gradient_boosted_trees    | HistGradientBoosting residual scale model |                       -0.749133  |                   nan |                    nan |                       0.110925  |                     nan |                      nan |
| mlp                       | MLP residual scale model                  |                       -0.705517  |                   nan |                    nan |                       0.139292  |                     nan |                      nan |
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            |                       -0.533873  |                   nan |                    nan |                       0.0690932 |                     nan |                      nan |
| ridge                     | Ridge residual scale model                |                       -0.0800395 |                   nan |                    nan |                       0.134933  |                     nan |                      nan |
| traditional               | S02/S03/S04 atom robust-width baseline    |                       -0.0811722 |                   nan |                    nan |                      -3.16984   |                     nan |                      nan |

Support ledger:

| dimension         | stratum                       |   n_pair_residuals |   n_events |   n_runs |   support_fraction |   median_charge_adc_samples |   median_amplitude_adc |
|:------------------|:------------------------------|-------------------:|-----------:|---------:|-------------------:|----------------------------:|-----------------------:|
| amplitude_bin     | amp_adc[2500,4000)            |               6811 |       3099 |        7 |         0.594328   |                    23669    |                2966.75 |
| amplitude_bin     | amp_adc[1500,2500)            |               3901 |       2372 |        7 |         0.340401   |                    15308.5  |                2177.5  |
| amplitude_bin     | amp_adc[4000,7000)            |                492 |        302 |        7 |         0.0429319  |                    34128.8  |                4223.5  |
| amplitude_bin     | amp_adc[1000,1500)            |                256 |        216 |        7 |         0.0223386  |                     7781.12 |                1382.12 |
| baseline_bin      | baseline_rms[0,8)             |               3889 |       2127 |        7 |         0.339354   |                    21015.5  |                2780    |
| baseline_bin      | baseline_rms[8,16)            |               3261 |       1578 |        7 |         0.284555   |                    20897    |                2764    |
| baseline_bin      | baseline_rms[64,inf)          |               3067 |       1082 |        7 |         0.267627   |                    18731    |                2496.25 |
| baseline_bin      | baseline_rms[16,32)           |                935 |        491 |        7 |         0.0815881  |                    20906.2  |                2803.25 |
| baseline_bin      | baseline_rms[32,64)           |                308 |        185 |        7 |         0.0268761  |                    21951.2  |                2781.75 |
| charge_bin        | charge[14000,24000)           |               5990 |       3189 |        7 |         0.522688   |                    19147.6  |                2559.25 |
| charge_bin        | charge[24000,40000)           |               3624 |       1871 |        7 |         0.31623    |                    28074.4  |                3354.88 |
| charge_bin        | charge[8000,14000)            |               1471 |       1032 |        7 |         0.12836    |                    11881.2  |                1841.75 |
| charge_bin        | charge[4000,8000)             |                285 |        175 |        7 |         0.0248691  |                     6698.5  |                1699.75 |
| charge_bin        | charge[1000,4000)             |                 60 |         31 |        7 |         0.0052356  |                     3152.75 |                1857.5  |
| charge_bin        | charge[40000,80000)           |                 30 |         23 |        6 |         0.0026178  |                    43392.5  |                4796.88 |
| p09_anomaly_class | unassigned_common             |              10516 |       3624 |        7 |         0.917627   |                    21031.1  |                2723    |
| p09_anomaly_class | novel_delayed_peak            |                571 |        212 |        7 |         0.0498255  |                    10563    |                2780.75 |
| p09_anomaly_class | novel_early_pretrigger        |                298 |        140 |        6 |         0.0260035  |                    11932.9  |                2010.38 |
| p09_anomaly_class | dropout                       |                 27 |         13 |        5 |         0.00235602 |                     8761.75 |                1515.75 |
| p09_anomaly_class | novel_broad_template_mismatch |                 26 |         13 |        5 |         0.00226876 |                    36376.1  |                3981.5  |
| p09_anomaly_class | pileup_or_long_tail           |                 16 |          9 |        4 |         0.00139616 |                    10845.8  |                3029.62 |
| p09_anomaly_class | novel_undershoot_recovery     |                  6 |          3 |        2 |         0.00052356 |                     6203.62 |                1281.12 |
| q_template_bin    | q_template[0.2,inf)           |               4551 |       1602 |        7 |         0.39712    |                    18090    |                2576    |
| q_template_bin    | q_template[0.08,0.12)         |               2057 |       1060 |        7 |         0.179494   |                    22361    |                2830    |
| q_template_bin    | q_template[0.05,0.08)         |               2021 |       1113 |        7 |         0.176353   |                    22622.5  |                2845.5  |
| q_template_bin    | q_template[0.12,0.2)          |               1534 |        713 |        7 |         0.133857   |                    21630.1  |                2755.5  |
| q_template_bin    | q_template[0.025,0.05)        |               1262 |        733 |        7 |         0.110122   |                    20291.5  |                2683    |
| q_template_bin    | q_template[0,0.025)           |                 35 |         34 |        5 |         0.0030541  |                    20171.5  |                2707.25 |
| run               | 61                            |               2799 |        933 |        1 |         0.244241   |                    21492    |                2774.25 |
| run               | 60                            |               2424 |        808 |        1 |         0.211518   |                    22624    |                2910.5  |
| run               | 62                            |               2421 |        807 |        1 |         0.211257   |                    20089.2  |                2674    |
| run               | 59                            |               2289 |        763 |        1 |         0.199738   |                    19232.5  |                2559.5  |
| run               | 63                            |               1110 |        370 |        1 |         0.0968586  |                    18485.4  |                2551.62 |
| run               | 58                            |                219 |         73 |        1 |         0.0191099  |                    18484.5  |                2679.75 |
| run               | 65                            |                198 |         66 |        1 |         0.0172775  |                    16706.8  |                2432.75 |

## Sentinels And Leakage Checks

The sentinels are inherited from the P06c uncertainty layer and are re-reported because this ticket interprets the same run-external scale models through a charge-proxy gate.

| sentinel        | method                    |     n |   bias_ns |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68 |   coverage68 |   coverage95 |   coverage68_error |   coverage95_error |   calibration_ece |   calibration_loss |
|:----------------|:--------------------------|------:|----------:|------------:|-------------:|--------------:|----------------------:|---------------:|-------------:|-------------:|-------------------:|-------------------:|------------------:|-------------------:|
| amplitude_only  | ridge_uncertainty_control | 11460 |   1.24417 |     1.49475 |      1.55109 |       2.66699 |             0.0191099 |        1.02596 |     0.465532 |     0.862216 |           0.217157 |          0.0877836 |          0.15247  |           0.120844 |
| topology_only   | ridge_uncertainty_control | 11460 |   1.24417 |     1.49475 |      1.55109 |       2.66699 |             0.0191099 |        1.03123 |     0.533159 |     0.837435 |           0.149531 |          0.112565  |          0.136935 |           0.107566 |
| run_family_only | ridge_uncertainty_control | 11460 |   1.24417 |     1.49475 |      1.55109 |       2.66699 |             0.0191099 |        1.02452 |     0.461344 |     0.857941 |           0.221346 |          0.0920593 |          0.156703 |           0.123656 |
| shuffled_target | ridge_uncertainty_control | 11460 |   1.24417 |     1.49475 |      1.55109 |       2.66699 |             0.0191099 |        1.0285  |     0.468412 |     0.860471 |           0.214278 |          0.0895288 |          0.151903 |           0.121053 |

| check                        | value                                                                        | pass   | note                                                                                                     |
|:-----------------------------|:-----------------------------------------------------------------------------|:-------|:---------------------------------------------------------------------------------------------------------|
| raw_root_reproduction_passed | True                                                                         | True   | raw HRDv selected-pulse count and S03a timing gate must pass before benchmark interpretation             |
| required_methods_present     | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional | True   | traditional plus ridge, gradient-boosted trees, MLP, 1D-CNN, and new phase-conformal gated CNN           |
| split_by_run                 | 58,59,60,61,62,63,65                                                         | True   | pair rows are leave-one-run-out over Sample-II analysis runs                                             |
| uncertainty_heldout_runs     | 58,59,60,61,62,63,65                                                         | True   | each uncertainty layer leaves out the evaluated run                                                      |
| uncertainty_meta_available   | 42                                                                           | True   | fold metadata records the run-external uncertainty fits                                                  |
| forbidden_feature_audit      | 0                                                                            | True   | source P06c uncertainty features exclude event id, raw residual, pull, sigma target, and held-out labels |

Uncertainty fold metadata sample:

| method                    |   heldout_run |    scale |   groups |   feature_count | feature_mode   |   shuffle_target |   gated |
|:--------------------------|--------------:|---------:|---------:|----------------:|:---------------|-----------------:|--------:|
| traditional               |            58 | 1        |      199 |             nan | nan            |              nan |     nan |
| traditional               |            59 | 1        |      195 |             nan | nan            |              nan |     nan |
| traditional               |            60 | 1        |      182 |             nan | nan            |              nan |     nan |
| traditional               |            61 | 1        |      184 |             nan | nan            |              nan |     nan |
| traditional               |            62 | 1        |      188 |             nan | nan            |              nan |     nan |
| traditional               |            63 | 1        |      195 |             nan | nan            |              nan |     nan |
| traditional               |            65 | 1        |      198 |             nan | nan            |              nan |     nan |
| ridge                     |            58 | 1.02357  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            59 | 1.00729  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            60 | 1.02254  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            61 | 1.04214  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            62 | 1.01614  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            63 | 1.01445  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            65 | 1.02122  |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            58 | 0.996605 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            59 | 1.00276  |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            60 | 0.993334 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            61 | 0.995773 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            62 | 0.982997 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            63 | 0.988978 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            65 | 1.00033  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            58 | 1.03944  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            59 | 1.02466  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            60 | 1.03088  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            61 | 1.05483  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            62 | 1.00387  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            63 | 1.03086  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            65 | 1.01737  |      nan |              70 | full           |                0 |     nan |
| cnn1d                     |            58 | 0.862025 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            59 | 0.948146 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            60 | 0.849148 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            61 | 0.896508 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            62 | 0.908328 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            63 | 0.849406 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            65 | 0.907594 |      nan |              70 | nan            |              nan |       0 |
| phase_conformal_gated_cnn |            58 | 0.939751 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            59 | 0.915355 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            60 | 1.0124   |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            61 | 0.936448 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            62 | 0.900205 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            63 | 0.952577 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            65 | 0.899983 |      nan |              70 | nan            |              nan |       1 |

## Systematics

- The bootstrap resamples runs and events, so it covers run-to-run instability and event-level pair correlation, but it does not cover alternate ROOT branch decoding, electronics calibrations, or unrecorded beam-condition changes.
- The charge proxy is waveform area after baseline subtraction, not an externally calibrated MeV energy. Conclusions are therefore about charge-conditioned timing uncertainty, not absolute calorimetric energy resolution.
- Pair residuals share staves within an event. The event-paired bootstrap reduces overcounting, but an external clock could still expose absolute-time errors that same-particle pair residuals cancel.
- The traditional baseline is intentionally strong and transparent. If an ML/NN method wins only by a small point-estimate margin with overlapping CIs, the practical conclusion should be model parity rather than adoption.
- Neural models are compact CPU-scale architectures inherited from P06c. Larger models might improve scale calibration, but would need the same run-external and charge-matched checks.

## Caveats And Interpretation

The winner is `phase_conformal_gated_cnn` by point-estimate calibration loss. This is not equivalent to the narrowest timing residual: S06 consumers need calibrated `sigma_hat`, so pull width and interval coverage are the adoption gate. The charge-bin tables show where charge support changes the conclusion; sparse high-charge and low-charge regions remain the least stable places to propagate uncertainty without abstention or inflation.

## Follow-Up

S06e: charge-bin conformal inflation stress test for pull-calibrated timing; expected information gain is whether sparse low- and high-charge bins can be made locally calibrated under fixed abstention budgets or whether the S06c ML win is only global.

## Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s06c_1781059684_1019_46485748_charge_proxy_timing_pull_width_calibration.py --config configs/s06c_1781059684_1019_46485748_charge_proxy_timing_pull_width_calibration.json
```

Primary artifacts: `result.json`, `manifest.json`, `REPORT.md`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `pooled_method_summary.csv`, `per_run_method_summary.csv`, `charge_bin_method_summary.csv`, `amplitude_bin_method_summary.csv`, `method_delta_vs_traditional.csv`, `charge_slope_summary.csv`, `support_summary.csv`, `sentinel_checks.csv`, `leakage_checks.csv`, `input_sha256.csv`, and figures.


# S06b: amplitude-energy timing support closure

- **Ticket:** `1781054026.2063.38d35ceb`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT files under `/home/billy/Desktop/test_beam/data/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65
- **Bootstrap:** event-paired run-block bootstrap with 300 replicates
- **Primary rule:** lowest pooled pairwise pull-calibration loss, with sigma68/full-RMS/tail/support tables reported as constraints
- **Benchmark provenance:** S06b performs an independent raw ROOT reproduction gate, then reuses the committed P06c run-external pair-residual benchmark rows recorded in `source_benchmark_rows.json` to avoid repeating identical LORO model training

## Abstract

S06b tests whether the apparent timing-resolution curve versus amplitude or charge-energy proxy is monotonic, or whether it is dominated by support changes from saturation, dropout/anomaly, q-template mismatch, and baseline action bands. The raw ROOT reproduction gate passes exactly. The winner by the pre-registered pooled calibration-loss rule is **phase_conformal_gated_cnn** with calibration loss **0.0534** and bootstrap 95% CI **[0.0414, 0.0705]**. The support closure tables show that amplitude/charge bins are not exchangeable physics slices: high-amplitude and high-charge regions carry sharply different action-band composition, so naive sigma(E) claims require the reported support conditioning.

## Raw ROOT Reproduction Gate

Counts are recomputed directly from `HRDv`: subtract the median of samples 0-3, require baseline-subtracted amplitude > 1000 ADC, and sum selected B-stave pulses across the configured raw ROOT files.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a analytic timing reference is rerun before the fold-local benchmark:

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals | best_candidate   |   best_alpha |
|:------------------------|--------:|---------:|----------:|-------------------:|:-----------------|-------------:|
| s02_template_phase_base | 2.88915 |  2.63915 |   3.27718 |                198 | amp_only         |          100 |
| s03a_analytic_timewalk  | 1.49464 |  1.33645 |   1.62215 |                198 | amp_only         |          100 |

## Estimands And Equations

For event `e`, stave `s`, and method `m`, the geometry-corrected timestamp is `tau_{e,s,m}=t_{e,s,m}-x_s v_TOF`, with `v_TOF=0.078 ns/cm` and 2 cm downstream spacing. Pair residuals are `r_{e,a,b,m}=tau_{e,a,m}-tau_{e,b,m}` for B4-B6, B4-B8, and B6-B8.

The robust timing width is `sigma68(r)=(Q84(r)-Q16(r))/2`; full RMS is computed about the mean. Each uncertainty model predicts `sigma_hat`, giving pull `z=r/sigma_hat`, pull width `sigma68(z)`, 68% coverage `P(|z|<=1)`, 95% coverage `P(|z|<=1.96)`, and calibration ECE from sigma-quantile coverage bins.

The primary calibration loss is `mean(|sigma68(z)-1|, |C68-0.682689|, |C95-0.95|, ECE)`. Monotonicity is evaluated on adjacent amplitude or charge bins: a violation occurs when a higher proxy bin has larger `sigma68(r)` than the previous bin; a significant violation additionally requires non-overlapping bootstrap CIs.

## Methods

Traditional method: fold-local S02 template-phase timing, S03a amplitude-only analytic timewalk correction, and an S04-style robust-width lookup over pair, peak sample, leading-edge phase, sample-window mask, and coarser fallbacks. This is the strongest non-ML comparator because it uses the known timing reconstruction physics and action-bin robust widths without seeing held-out runs.

ML/NN methods: ridge, HistGradientBoosting, MLP, 1D-CNN, and the new phase-conformal atom-gated CNN. All models are trained run-externally and use waveform shape plus amplitude, charge proxy, q-template, baseline, phase, topology, anomaly/action, and run-family covariates. The new architecture encodes the two pair waveforms with 1D convolutions, gates channels using atom/tabular support features, and applies a run-external conformal phase-bin scale adjustment.

The pair-residual benchmark rows are the committed P06c rows for the same Sample-II LORO split and methods. S06b does not treat that as a reproduction proxy: it first reruns the raw ROOT count and S03a timing closure, then computes new amplitude/charge support, monotonicity, action-band, per-run, and ML-minus-traditional summaries in this ticket-owned report directory.

## Head-To-Head Winner Table

| method                    | method_label                              |     n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   pull_width68 |   coverage68 |   coverage95 |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|:--------------------------|:------------------------------------------|------:|-------------------:|--------------------------:|---------------------------:|---------------:|-------------:|-------------:|-------------:|--------------:|----------------------:|
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            | 11460 |          0.0534484 |                 0.0414198 |                  0.0704633 |       0.901022 |     0.631937 |     0.960995 |      1.50399 |       2.41532 |             0.0114311 |
| cnn1d                     | 1D-CNN residual scale model               | 11460 |          0.0973354 |                 0.079418  |                  0.159563  |       1.00983  |     0.454538 |     0.936126 |      1.5101  |       2.42042 |             0.0129145 |
| mlp                       | MLP residual scale model                  | 11460 |          0.103472  |                 0.0667066 |                  0.170197  |       1.05182  |     0.516928 |     0.876003 |      1.64477 |       2.42453 |             0.0138743 |
| gradient_boosted_trees    | HistGradientBoosting residual scale model | 11460 |          0.109007  |                 0.0740727 |                  0.218837  |       1.0451   |     0.502792 |     0.869721 |      1.5543  |       2.31556 |             0.0153578 |
| ridge                     | Ridge residual scale model                | 11460 |          0.110021  |                 0.0776086 |                  0.216983  |       1.02024  |     0.481065 |     0.871728 |      1.57318 |       2.54659 |             0.0161431 |
| traditional               | S02/S03/S04 atom robust-width baseline    | 11460 |          0.659059  |                 0.549944  |                  0.775257  |       2.71207  |     0.384991 |     0.631588 |      1.55109 |       2.66699 |             0.0191099 |

Per-run held-out scores with bootstrap CIs:

|   run | method                    |    n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   pull_width68 |   coverage68 |   coverage95 |   any_action_band_fraction |
|------:|:--------------------------|-----:|-------------------:|--------------------------:|---------------------------:|-------------:|--------------------:|---------------------:|---------------:|-------------:|-------------:|---------------------------:|
|    58 | phase_conformal_gated_cnn |  219 |          0.0807315 |                 0.0602546 |                  0.107904  |      1.44496 |             1.35789 |              1.58067 |       0.916748 |     0.552511 |     0.977169 |                   0.826484 |
|    58 | gradient_boosted_trees    |  219 |          0.110666  |                 0.0893471 |                  0.155009  |      1.4617  |             1.32083 |              1.65737 |       0.938791 |     0.479452 |     0.899543 |                   0.826484 |
|    58 | cnn1d                     |  219 |          0.130305  |                 0.104732  |                  0.202964  |      1.40396 |             1.32176 |              1.57127 |       1.04228  |     0.374429 |     0.949772 |                   0.826484 |
|    58 | mlp                       |  219 |          0.141722  |                 0.111514  |                  0.197579  |      1.63394 |             1.48246 |              1.80638 |       0.937856 |     0.415525 |     0.881279 |                   0.826484 |
|    58 | ridge                     |  219 |          0.145133  |                 0.125538  |                  0.190398  |      1.34328 |             1.23697 |              1.50827 |       0.942984 |     0.392694 |     0.90411  |                   0.826484 |
|    58 | traditional               |  219 |          1.00002   |                 0.736553  |                  1.4398    |      1.18748 |             1.13221 |              1.38647 |       3.91407  |     0.342466 |     0.56621  |                   0.826484 |
|    59 | phase_conformal_gated_cnn | 2289 |          0.036222  |                 0.0300818 |                  0.0439326 |      1.45517 |             1.41566 |              1.50307 |       0.974835 |     0.638707 |     0.954128 |                   0.706859 |
|    59 | mlp                       | 2289 |          0.0920123 |                 0.0773608 |                  0.113499  |      1.52757 |             1.48553 |              1.57926 |       1.0226   |     0.525557 |     0.87855  |                   0.706859 |
|    59 | gradient_boosted_trees    | 2289 |          0.0989203 |                 0.0874986 |                  0.119799  |      1.44995 |             1.39618 |              1.49745 |       1.01611  |     0.496723 |     0.882918 |                   0.706859 |
|    59 | cnn1d                     | 2289 |          0.113159  |                 0.0980019 |                  0.131765  |      1.46085 |             1.41383 |              1.51165 |       1.03012  |     0.42464  |     0.93709  |                   0.706859 |
|    59 | ridge                     | 2289 |          0.148263  |                 0.126433  |                  0.170428  |      1.50618 |             1.44465 |              1.56298 |       1.13091  |     0.451289 |     0.873307 |                   0.706859 |
|    59 | traditional               | 2289 |          0.500969  |                 0.418874  |                  0.605013  |      1.45871 |             1.39212 |              1.54074 |       2.29731  |     0.45391  |     0.707733 |                   0.706859 |
|    60 | phase_conformal_gated_cnn | 2424 |          0.0705094 |                 0.0651583 |                  0.0800182 |      1.31669 |             1.28861 |              1.35147 |       0.820108 |     0.651815 |     0.963696 |                   0.681931 |
|    60 | gradient_boosted_trees    | 2424 |          0.0725238 |                 0.0630073 |                  0.0842037 |      1.38599 |             1.33289 |              1.43798 |       0.962982 |     0.556931 |     0.908003 |                   0.681931 |
|    60 | cnn1d                     | 2424 |          0.0815077 |                 0.0707981 |                  0.0903071 |      1.37389 |             1.33306 |              1.42727 |       0.910421 |     0.55033  |     0.940594 |                   0.681931 |
|    60 | mlp                       | 2424 |          0.0937052 |                 0.0749505 |                  0.115347  |      1.55167 |             1.48983 |              1.59933 |       1.03635  |     0.52764  |     0.882013 |                   0.681931 |
|    60 | ridge                     | 2424 |          0.0949629 |                 0.0850998 |                  0.108436  |      1.40425 |             1.35449 |              1.45952 |       0.925804 |     0.526815 |     0.905528 |                   0.681931 |
|    60 | traditional               | 2424 |          0.640158  |                 0.532314  |                  0.716009  |      1.3437  |             1.28027 |              1.40727 |       2.71494  |     0.403878 |     0.665017 |                   0.681931 |
|    61 | phase_conformal_gated_cnn | 2799 |          0.0816349 |                 0.074942  |                  0.091108  |      1.77103 |             1.72897 |              1.82807 |       0.92619  |     0.536977 |     0.967846 |                   0.733119 |
|    61 | cnn1d                     | 2799 |          0.205483  |                 0.186604  |                  0.224083  |      1.86024 |             1.79761 |              1.9438  |       1.20927  |     0.322615 |     0.909968 |                   0.733119 |
|    61 | mlp                       | 2799 |          0.217984  |                 0.193059  |                  0.240272  |      1.87564 |             1.80745 |              1.94971 |       1.24766  |     0.405502 |     0.811004 |                   0.733119 |
|    61 | ridge                     | 2799 |          0.271707  |                 0.249507  |                  0.298376  |      2.06807 |             1.99215 |              2.14016 |       1.25462  |     0.322972 |     0.754912 |                   0.733119 |
|    61 | gradient_boosted_trees    | 2799 |          0.300019  |                 0.279042  |                  0.322566  |      1.92756 |             1.85216 |              2.01401 |       1.38341  |     0.337263 |     0.750982 |                   0.733119 |
|    61 | traditional               | 2799 |          0.832446  |                 0.773418  |                  0.889757  |      2.12996 |             1.98182 |              2.21105 |       2.97132  |     0.255806 |     0.47124  |                   0.733119 |
|    62 | mlp                       | 2421 |          0.0611271 |                 0.0524967 |                  0.0731523 |      1.60852 |             1.53992 |              1.65947 |       0.966936 |     0.594796 |     0.914911 |                   0.716233 |
|    62 | phase_conformal_gated_cnn | 2421 |          0.0690428 |                 0.0598295 |                  0.0808341 |      1.441   |             1.39335 |              1.48033 |       0.854903 |     0.730277 |     0.950847 |                   0.716233 |
|    62 | cnn1d                     | 2421 |          0.0746625 |                 0.0667905 |                  0.0832184 |      1.44731 |             1.40896 |              1.49318 |       0.935287 |     0.541512 |     0.951673 |                   0.716233 |
|    62 | gradient_boosted_trees    | 2421 |          0.076191  |                 0.0664046 |                  0.085026  |      1.47062 |             1.41176 |              1.52016 |       0.880185 |     0.596861 |     0.923172 |                   0.716233 |
|    62 | ridge                     | 2421 |          0.0792349 |                 0.0696967 |                  0.0925335 |      1.50027 |             1.44816 |              1.55781 |       0.856238 |     0.594382 |     0.934325 |                   0.716233 |
|    62 | traditional               | 2421 |          0.569961  |                 0.482844  |                  0.644703  |      1.469   |             1.40501 |              1.5232  |       2.50677  |     0.426683 |     0.690624 |                   0.716233 |
|    63 | phase_conformal_gated_cnn | 1110 |          0.0578199 |                 0.0483615 |                  0.0703267 |      1.47808 |             1.43504 |              1.53173 |       0.947253 |     0.596396 |     0.965766 |                   0.725225 |
|    63 | ridge                     | 1110 |          0.0667334 |                 0.0509592 |                  0.0830774 |      1.43923 |             1.33303 |              1.52291 |       0.884932 |     0.606306 |     0.938739 |                   0.725225 |
|    63 | gradient_boosted_trees    | 1110 |          0.0753427 |                 0.0576445 |                  0.0870255 |      1.42938 |             1.36681 |              1.50985 |       0.873159 |     0.6      |     0.926126 |                   0.725225 |
|    63 | mlp                       | 1110 |          0.0766701 |                 0.0636103 |                  0.0999583 |      1.51483 |             1.43921 |              1.60598 |       0.8696   |     0.598198 |     0.930631 |                   0.725225 |
|    63 | cnn1d                     | 1110 |          0.109283  |                 0.0993398 |                  0.129327  |      1.34042 |             1.29172 |              1.39284 |       0.890408 |     0.476577 |     0.94955  |                   0.725225 |
|    63 | traditional               | 1110 |          0.589972  |                 0.43935   |                  0.70144   |      1.39132 |             1.29529 |              1.47371 |       2.59869  |     0.437838 |     0.687387 |                   0.725225 |
|    65 | phase_conformal_gated_cnn |  198 |          0.0838919 |                 0.0552714 |                  0.12015   |      1.52228 |             1.37735 |              1.65945 |       0.828315 |     0.737374 |     0.989899 |                   0.737374 |
|    65 | mlp                       |  198 |          0.0895641 |                 0.0539706 |                  0.149031  |      1.60649 |             1.35683 |              1.77652 |       0.904628 |     0.565657 |     0.90404  |                   0.737374 |
|    65 | ridge                     |  198 |          0.103187  |                 0.0723379 |                  0.155795  |      1.44215 |             1.29683 |              1.6662  |       0.910023 |     0.510101 |     0.914141 |                   0.737374 |
|    65 | gradient_boosted_trees    |  198 |          0.122553  |                 0.0678541 |                  0.163608  |      1.45325 |             1.22026 |              1.6934  |       0.716396 |     0.580808 |     0.924242 |                   0.737374 |
|    65 | cnn1d                     |  198 |          0.12984   |                 0.106708  |                  0.183587  |      1.45474 |             1.34643 |              1.62772 |       1.05138  |     0.393939 |     0.959596 |                   0.737374 |
|    65 | traditional               |  198 |          0.687806  |                 0.423698  |                  0.910555  |      1.49464 |             1.31969 |              1.67457 |       2.90825  |     0.424242 |     0.646465 |                   0.737374 |

## Amplitude And Energy-Proxy Closure

Amplitude-bin benchmark:

| stratum            | method                    |    n |   n_runs |   support_fraction |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   calibration_loss |   any_action_band_fraction |
|:-------------------|:--------------------------|-----:|---------:|-------------------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|-------------------:|---------------------------:|
| amp_adc[1000,1500) | ridge                     |  256 |        7 |          0.0223386 |     1.04003  |            0.700025 |              1.36438 |       2.8117  |            0.0078125  |          0.184117  |                   0.976562 |
| amp_adc[1000,1500) | mlp                       |  256 |        7 |          0.0223386 |     1.07925  |            0.851703 |              1.39175 |       2.82192 |            0.0234375  |          0.190266  |                   0.976562 |
| amp_adc[1000,1500) | phase_conformal_gated_cnn |  256 |        7 |          0.0223386 |     0.713217 |            0.417429 |              1.11398 |       3.03328 |            0.015625   |          0.202035  |                   0.976562 |
| amp_adc[1000,1500) | gradient_boosted_trees    |  256 |        7 |          0.0223386 |     0.851605 |            0.737313 |              1.27075 |       2.93945 |            0.0078125  |          0.215234  |                   0.976562 |
| amp_adc[1000,1500) | cnn1d                     |  256 |        7 |          0.0223386 |     0.6722   |            0.494148 |              1.1443  |       2.95533 |            0.0078125  |          0.258354  |                   0.976562 |
| amp_adc[1000,1500) | traditional               |  256 |        7 |          0.0223386 |     0.943987 |            0.447368 |              1.33365 |       2.95576 |            0.0078125  |          2.02015   |                   0.976562 |
| amp_adc[1500,2500) | phase_conformal_gated_cnn | 3901 |        7 |          0.340401  |     1.45683  |            1.32235  |              1.58486 |       2.11929 |            0.00666496 |          0.100333  |                   0.758267 |
| amp_adc[1500,2500) | mlp                       | 3901 |        7 |          0.340401  |     1.49364  |            1.37795  |              1.61099 |       2.12202 |            0.0069213  |          0.125974  |                   0.758267 |
| amp_adc[1500,2500) | gradient_boosted_trees    | 3901 |        7 |          0.340401  |     1.45851  |            1.3207   |              1.63233 |       2.02969 |            0.00717765 |          0.129053  |                   0.758267 |
| amp_adc[1500,2500) | cnn1d                     | 3901 |        7 |          0.340401  |     1.46823  |            1.33738  |              1.63103 |       2.0417  |            0.00717765 |          0.141732  |                   0.758267 |
| amp_adc[1500,2500) | ridge                     | 3901 |        7 |          0.340401  |     1.46501  |            1.321    |              1.75808 |       2.11855 |            0.00974109 |          0.142435  |                   0.758267 |
| amp_adc[1500,2500) | traditional               | 3901 |        7 |          0.340401  |     1.35234  |            1.17755  |              1.69792 |       2.19758 |            0.0135863  |          1.1376    |                   0.758267 |
| amp_adc[2500,4000) | phase_conformal_gated_cnn | 6811 |        7 |          0.594328  |     1.52437  |            1.37388  |              1.72082 |       2.36099 |            0.00969021 |          0.0376286 |                   0.679636 |
| amp_adc[2500,4000) | cnn1d                     | 6811 |        7 |          0.594328  |     1.52271  |            1.38164  |              1.71096 |       2.41712 |            0.0113052  |          0.111934  |                   0.679636 |
| amp_adc[2500,4000) | mlp                       | 6811 |        7 |          0.594328  |     1.68391  |            1.5514   |              1.83178 |       2.39921 |            0.0129203  |          0.131894  |                   0.679636 |
| amp_adc[2500,4000) | ridge                     | 6811 |        7 |          0.594328  |     1.60364  |            1.44948  |              1.87092 |       2.51294 |            0.0140948  |          0.133362  |                   0.679636 |
| amp_adc[2500,4000) | gradient_boosted_trees    | 6811 |        7 |          0.594328  |     1.60385  |            1.4333   |              1.8447  |       2.32266 |            0.0155631  |          0.14793   |                   0.679636 |
| amp_adc[2500,4000) | traditional               | 6811 |        7 |          0.594328  |     1.56158  |            1.3175   |              1.94838 |       2.63796 |            0.0171781  |          0.460248  |                   0.679636 |
| amp_adc[4000,7000) | phase_conformal_gated_cnn |  492 |        7 |          0.0429319 |     1.62638  |            1.39698  |              2.14855 |       4.09012 |            0.0630081  |          0.0787321 |                   0.715447 |
| amp_adc[4000,7000) | cnn1d                     |  492 |        7 |          0.0429319 |     1.6406   |            1.4554   |              2.13876 |       4.08565 |            0.0752033  |          0.208218  |                   0.715447 |
| amp_adc[4000,7000) | ridge                     |  492 |        7 |          0.0429319 |     2.41689  |            1.88762  |              3.22372 |       4.73682 |            0.115854   |          0.208359  |                   0.715447 |
| amp_adc[4000,7000) | gradient_boosted_trees    |  492 |        7 |          0.0429319 |     1.73392  |            1.43692  |              2.25013 |       3.36983 |            0.0731707  |          0.223055  |                   0.715447 |
| amp_adc[4000,7000) | mlp                       |  492 |        7 |          0.0429319 |     1.9872   |            1.69178  |              2.27796 |       3.99275 |            0.0752033  |          0.232441  |                   0.715447 |
| amp_adc[4000,7000) | traditional               |  492 |        7 |          0.0429319 |     2.55444  |            2.20671  |              3.26431 |       4.91732 |            0.0934959  |          0.773289  |                   0.715447 |

Charge-energy-proxy benchmark:

| stratum             | method                    |    n |   n_runs |   support_fraction |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   calibration_loss |   any_action_band_fraction |
|:--------------------|:--------------------------|-----:|---------:|-------------------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|-------------------:|---------------------------:|
| charge[1000,4000)   | ridge                     |   60 |        7 |          0.0052356 |     0.871694 |            0.552612 |              1.10725 |      0.848247 |            0          |          0.0651568 |                   1        |
| charge[1000,4000)   | phase_conformal_gated_cnn |   60 |        7 |          0.0052356 |     1.27218  |            1.15603  |              1.46241 |      1.23228  |            0          |          0.078621  |                   1        |
| charge[1000,4000)   | cnn1d                     |   60 |        7 |          0.0052356 |     1.26482  |            1.09553  |              1.46134 |      1.15892  |            0          |          0.119402  |                   1        |
| charge[1000,4000)   | gradient_boosted_trees    |   60 |        7 |          0.0052356 |     1.8244   |            1.32987  |              2.63662 |      1.82338  |            0          |          0.198452  |                   1        |
| charge[1000,4000)   | mlp                       |   60 |        7 |          0.0052356 |     1.24001  |            0.991789 |              1.60389 |      1.21105  |            0          |          0.217319  |                   1        |
| charge[1000,4000)   | traditional               |   60 |        7 |          0.0052356 |     1.00611  |            0.902313 |              1.11356 |      0.894033 |            0          |          1.76562   |                   1        |
| charge[14000,24000) | phase_conformal_gated_cnn | 5990 |        7 |          0.522688  |     1.5331   |            1.39281  |              1.7114  |      2.17902  |            0.00717863 |          0.0684683 |                   0.665776 |
| charge[14000,24000) | mlp                       | 5990 |        7 |          0.522688  |     1.60341  |            1.47871  |              1.74662 |      2.18926  |            0.00834725 |          0.0977837 |                   0.665776 |
| charge[14000,24000) | gradient_boosted_trees    | 5990 |        7 |          0.522688  |     1.5149   |            1.359    |              1.72741 |      2.17496  |            0.00934891 |          0.102139  |                   0.665776 |
| charge[14000,24000) | cnn1d                     | 5990 |        7 |          0.522688  |     1.55916  |            1.417    |              1.77705 |      2.25278  |            0.00751252 |          0.106302  |                   0.665776 |
| charge[14000,24000) | ridge                     | 5990 |        7 |          0.522688  |     1.55831  |            1.37406  |              1.89267 |      2.32502  |            0.0103506  |          0.116514  |                   0.665776 |
| charge[14000,24000) | traditional               | 5990 |        7 |          0.522688  |     1.54329  |            1.28006  |              1.93834 |      2.43508  |            0.0138564  |          0.460577  |                   0.665776 |
| charge[24000,40000) | phase_conformal_gated_cnn | 3624 |        7 |          0.31623   |     1.55262  |            1.37656  |              1.77308 |      2.53164  |            0.0182119  |          0.048945  |                   0.700607 |
| charge[24000,40000) | cnn1d                     | 3624 |        7 |          0.31623   |     1.54249  |            1.3739   |              1.74412 |      2.55738  |            0.0217991  |          0.134519  |                   0.700607 |
| charge[24000,40000) | ridge                     | 3624 |        7 |          0.31623   |     1.72697  |            1.50308  |              2.00869 |      2.82979  |            0.0292494  |          0.162506  |                   0.700607 |
| charge[24000,40000) | mlp                       | 3624 |        7 |          0.31623   |     1.69351  |            1.53504  |              1.87604 |      2.49565  |            0.0217991  |          0.180481  |                   0.700607 |
| charge[24000,40000) | gradient_boosted_trees    | 3624 |        7 |          0.31623   |     1.63791  |            1.45739  |              1.91917 |      2.36697  |            0.0256623  |          0.187652  |                   0.700607 |
| charge[24000,40000) | traditional               | 3624 |        7 |          0.31623   |     1.77525  |            1.49624  |              2.0862  |      3.00724  |            0.0306291  |          0.454854  |                   0.700607 |
| charge[4000,8000)   | phase_conformal_gated_cnn |  285 |        7 |          0.0248691 |     1.22879  |            0.866753 |              1.3286  |      3.3949   |            0.0175439  |          0.0957514 |                   1        |
| charge[4000,8000)   | cnn1d                     |  285 |        7 |          0.0248691 |     1.23591  |            0.854786 |              1.30087 |      3.37808  |            0.0105263  |          0.144512  |                   1        |
| charge[4000,8000)   | ridge                     |  285 |        7 |          0.0248691 |     1.14053  |            0.973187 |              1.29848 |      3.17168  |            0.0140351  |          0.174143  |                   1        |
| charge[4000,8000)   | mlp                       |  285 |        7 |          0.0248691 |     1.32155  |            1.04368  |              1.56777 |      3.34565  |            0.0245614  |          0.185022  |                   1        |
| charge[4000,8000)   | gradient_boosted_trees    |  285 |        7 |          0.0248691 |     1.20214  |            0.937395 |              1.49065 |      3.34549  |            0.0105263  |          0.196671  |                   1        |
| charge[4000,8000)   | traditional               |  285 |        7 |          0.0248691 |     1.26605  |            1.17593  |              1.33992 |      3.24068  |            0.0105263  |          2.07634   |                   1        |
| charge[40000,80000) | phase_conformal_gated_cnn |   30 |        6 |          0.0026178 |     3.6784   |            1.34299  |             13.752   |      8.96832  |            0.266667   |          0.28401   |                   1        |
| charge[40000,80000) | ridge                     |   30 |        6 |          0.0026178 |     6.60268  |            1.54826  |             14.2136  |      9.98612  |            0.4        |          0.320858  |                   1        |
| charge[40000,80000) | mlp                       |   30 |        6 |          0.0026178 |     5.6509   |            1.92534  |             13.3672  |      9.98866  |            0.366667   |          0.39102   |                   1        |
| charge[40000,80000) | gradient_boosted_trees    |   30 |        6 |          0.0026178 |     4.56458  |            2.3493   |             10.3417  |      7.59124  |            0.3        |          0.397796  |                   1        |
| charge[40000,80000) | cnn1d                     |   30 |        6 |          0.0026178 |     4.85102  |            1.25327  |             13.8409  |      8.90263  |            0.333333   |          0.49593   |                   1        |
| charge[40000,80000) | traditional               |   30 |        6 |          0.0026178 |     6.49259  |            1.88234  |             14.5902  |     10.0094   |            0.333333   |          2.54563   |                   1        |
| charge[8000,14000)  | phase_conformal_gated_cnn | 1471 |        7 |          0.12836   |     1.32383  |            1.23017  |              1.44173 |      2.41455  |            0.00611829 |          0.11404   |                   0.874915 |
| charge[8000,14000)  | gradient_boosted_trees    | 1471 |        7 |          0.12836   |     1.35436  |            1.21403  |              1.46721 |      2.11265  |            0.00747791 |          0.153679  |                   0.874915 |
| charge[8000,14000)  | mlp                       | 1471 |        7 |          0.12836   |     1.40497  |            1.27672  |              1.50301 |      2.43898  |            0.00951734 |          0.15444   |                   0.874915 |
| charge[8000,14000)  | ridge                     | 1471 |        7 |          0.12836   |     1.32795  |            1.2346   |              1.45163 |      2.14038  |            0.00951734 |          0.154693  |                   0.874915 |
| charge[8000,14000)  | cnn1d                     | 1471 |        7 |          0.12836   |     1.3461   |            1.26468  |              1.41495 |      2.1259   |            0.00611829 |          0.158496  |                   0.874915 |
| charge[8000,14000)  | traditional               | 1471 |        7 |          0.12836   |     1.23885  |            1.14974  |              1.3234  |      2.15083  |            0.00951734 |          1.95419   |                   0.874915 |

Monotonicity audit:

| dimension     | method                    |   n_bins |   n_adjacent_transitions |   monotonicity_violation_count |   monotonicity_violation_rate |   significant_violation_count |   max_adjacent_sigma68_increase_ns |   sigma68_vs_bin_mid_corr |
|:--------------|:--------------------------|---------:|-------------------------:|-------------------------------:|------------------------------:|------------------------------:|-----------------------------------:|--------------------------:|
| amplitude_bin | cnn1d                     |        4 |                        3 |                              3 |                           1   |                             1 |                           0.796034 |                  0.745673 |
| amplitude_bin | gradient_boosted_trees    |        4 |                        3 |                              3 |                           1   |                             1 |                           0.606907 |                  0.820969 |
| amplitude_bin | mlp                       |        4 |                        3 |                              3 |                           1   |                             0 |                           0.414387 |                  0.946339 |
| amplitude_bin | phase_conformal_gated_cnn |        4 |                        3 |                              3 |                           1   |                             1 |                           0.743609 |                  0.748494 |
| amplitude_bin | ridge                     |        4 |                        3 |                              3 |                           1   |                             1 |                           0.813245 |                  0.982833 |
| amplitude_bin | traditional               |        4 |                        3 |                              3 |                           1   |                             1 |                           0.992859 |                  0.98833  |
| charge_bin    | cnn1d                     |        6 |                        5 |                              3 |                           0.6 |                             1 |                           3.30853  |                  0.909695 |
| charge_bin    | gradient_boosted_trees    |        6 |                        5 |                              4 |                           0.8 |                             1 |                           2.92667  |                  0.871073 |
| charge_bin    | mlp                       |        6 |                        5 |                              5 |                           1   |                             1 |                           3.95739  |                  0.914682 |
| charge_bin    | phase_conformal_gated_cnn |        6 |                        5 |                              4 |                           0.8 |                             0 |                           2.12577  |                  0.926707 |
| charge_bin    | ridge                     |        6 |                        5 |                              5 |                           1   |                             0 |                           4.87572  |                  0.927896 |
| charge_bin    | traditional               |        6 |                        5 |                              4 |                           0.8 |                             1 |                           4.71735  |                  0.92471  |

Support/action-band composition by amplitude and charge bins, using the nonduplicated traditional pair rows:

| dimension     | stratum             |   n_pair_residuals |   n_runs |   support_fraction |   saturation_fraction |   dropout_fraction |   anomaly_noncommon_fraction |   wide_baseline_fraction |   high_q_template_fraction |   any_action_band_fraction |
|:--------------|:--------------------|-------------------:|---------:|-------------------:|----------------------:|-------------------:|-----------------------------:|-------------------------:|---------------------------:|---------------------------:|
| amplitude_bin | amp_adc[1000,1500)  |                256 |        7 |          0.0223386 |            0          |        0.046875    |                    0.253906  |                 0.660156 |                   0.976562 |                   0.976562 |
| amplitude_bin | amp_adc[1500,2500)  |               3901 |        7 |          0.340401  |            0          |        0.00384517  |                    0.0992053 |                 0.374263 |                   0.754166 |                   0.758267 |
| amplitude_bin | amp_adc[2500,4000)  |               6811 |        7 |          0.594328  |            0          |        0           |                    0.0638673 |                 0.239759 |                   0.675084 |                   0.679636 |
| amplitude_bin | amp_adc[4000,7000)  |                492 |        7 |          0.0429319 |            0.0325203  |        0           |                    0.115854  |                 0.229675 |                   0.715447 |                   0.715447 |
| charge_bin    | charge[1000,4000)   |                 60 |        7 |          0.0052356 |            0          |        0.0166667   |                    1         |                 0.05     |                   1        |                   1        |
| charge_bin    | charge[4000,8000)   |                285 |        7 |          0.0248691 |            0          |        0.0350877   |                    0.708772  |                 0.498246 |                   1        |                   1        |
| charge_bin    | charge[8000,14000)  |               1471 |        7 |          0.12836   |            0          |        0.00883753  |                    0.242012  |                 0.479266 |                   0.872196 |                   0.874915 |
| charge_bin    | charge[14000,24000) |               5990 |        7 |          0.522688  |            0          |        0.000500835 |                    0.0392321 |                 0.2601   |                   0.660601 |                   0.665776 |
| charge_bin    | charge[24000,40000) |               3624 |        7 |          0.31623   |            0.00331126 |        0           |                    0.0229029 |                 0.261589 |                   0.697296 |                   0.700607 |
| charge_bin    | charge[40000,80000) |                 30 |        6 |          0.0026178 |            0.133333   |        0           |                    0.266667  |                 0.633333 |                   1        |                   1        |

## ML-Minus-Traditional Deltas

Negative deltas indicate an ML/NN method improves on the traditional row in the matched amplitude or charge bin.

| dimension     | stratum             | method                    |   traditional_calibration_loss |   calibration_loss |   ml_minus_traditional_calibration_loss |   traditional_sigma68_ns |   sigma68_ns |   ml_minus_traditional_sigma68_ns |   traditional_tail_frac_abs_gt5ns |   tail_frac_abs_gt5ns |   ml_minus_traditional_tail_frac_abs_gt5ns |
|:--------------|:--------------------|:--------------------------|-------------------------------:|-------------------:|----------------------------------------:|-------------------------:|-------------:|----------------------------------:|----------------------------------:|----------------------:|-------------------------------------------:|
| charge_bin    | charge[40000,80000) | phase_conformal_gated_cnn |                        2.54563 |          0.28401   |                               -2.26162  |                 6.49259  |     3.6784   |                        -2.8142    |                        0.333333   |            0.266667   |                                -0.0666667  |
| charge_bin    | charge[40000,80000) | ridge                     |                        2.54563 |          0.320858  |                               -2.22477  |                 6.49259  |     6.60268  |                         0.110092  |                        0.333333   |            0.4        |                                 0.0666667  |
| charge_bin    | charge[40000,80000) | mlp                       |                        2.54563 |          0.39102   |                               -2.15461  |                 6.49259  |     5.6509   |                        -0.841697  |                        0.333333   |            0.366667   |                                 0.0333333  |
| charge_bin    | charge[40000,80000) | gradient_boosted_trees    |                        2.54563 |          0.397796  |                               -2.14783  |                 6.49259  |     4.56458  |                        -1.92801   |                        0.333333   |            0.3        |                                -0.0333333  |
| charge_bin    | charge[40000,80000) | cnn1d                     |                        2.54563 |          0.49593   |                               -2.0497   |                 6.49259  |     4.85102  |                        -1.64157   |                        0.333333   |            0.333333   |                                 0          |
| charge_bin    | charge[4000,8000)   | phase_conformal_gated_cnn |                        2.07634 |          0.0957514 |                               -1.98059  |                 1.26605  |     1.22879  |                        -0.0372516 |                        0.0105263  |            0.0175439  |                                 0.00701754 |
| charge_bin    | charge[4000,8000)   | cnn1d                     |                        2.07634 |          0.144512  |                               -1.93183  |                 1.26605  |     1.23591  |                        -0.0301376 |                        0.0105263  |            0.0105263  |                                 0          |
| charge_bin    | charge[4000,8000)   | ridge                     |                        2.07634 |          0.174143  |                               -1.9022   |                 1.26605  |     1.14053  |                        -0.125512  |                        0.0105263  |            0.0140351  |                                 0.00350877 |
| charge_bin    | charge[4000,8000)   | mlp                       |                        2.07634 |          0.185022  |                               -1.89132  |                 1.26605  |     1.32155  |                         0.0555044 |                        0.0105263  |            0.0245614  |                                 0.0140351  |
| charge_bin    | charge[4000,8000)   | gradient_boosted_trees    |                        2.07634 |          0.196671  |                               -1.87967  |                 1.26605  |     1.20214  |                        -0.0639015 |                        0.0105263  |            0.0105263  |                                 0          |
| charge_bin    | charge[8000,14000)  | phase_conformal_gated_cnn |                        1.95419 |          0.11404   |                               -1.84015  |                 1.23885  |     1.32383  |                         0.0849816 |                        0.00951734 |            0.00611829 |                                -0.00339905 |
| amplitude_bin | amp_adc[1000,1500)  | ridge                     |                        2.02015 |          0.184117  |                               -1.83604  |                 0.943987 |     1.04003  |                         0.0960441 |                        0.0078125  |            0.0078125  |                                 0          |
| amplitude_bin | amp_adc[1000,1500)  | mlp                       |                        2.02015 |          0.190266  |                               -1.82989  |                 0.943987 |     1.07925  |                         0.135264  |                        0.0078125  |            0.0234375  |                                 0.015625   |
| amplitude_bin | amp_adc[1000,1500)  | phase_conformal_gated_cnn |                        2.02015 |          0.202035  |                               -1.81812  |                 0.943987 |     0.713217 |                        -0.23077   |                        0.0078125  |            0.015625   |                                 0.0078125  |
| amplitude_bin | amp_adc[1000,1500)  | gradient_boosted_trees    |                        2.02015 |          0.215234  |                               -1.80492  |                 0.943987 |     0.851605 |                        -0.0923818 |                        0.0078125  |            0.0078125  |                                 0          |
| charge_bin    | charge[8000,14000)  | gradient_boosted_trees    |                        1.95419 |          0.153679  |                               -1.80051  |                 1.23885  |     1.35436  |                         0.115511  |                        0.00951734 |            0.00747791 |                                -0.00203943 |
| charge_bin    | charge[8000,14000)  | mlp                       |                        1.95419 |          0.15444   |                               -1.79975  |                 1.23885  |     1.40497  |                         0.166128  |                        0.00951734 |            0.00951734 |                                 0          |
| charge_bin    | charge[8000,14000)  | ridge                     |                        1.95419 |          0.154693  |                               -1.79949  |                 1.23885  |     1.32795  |                         0.0891009 |                        0.00951734 |            0.00951734 |                                 0          |
| charge_bin    | charge[8000,14000)  | cnn1d                     |                        1.95419 |          0.158496  |                               -1.79569  |                 1.23885  |     1.3461   |                         0.107254  |                        0.00951734 |            0.00611829 |                                -0.00339905 |
| amplitude_bin | amp_adc[1000,1500)  | cnn1d                     |                        2.02015 |          0.258354  |                               -1.7618   |                 0.943987 |     0.6722   |                        -0.271787  |                        0.0078125  |            0.0078125  |                                 0          |
| charge_bin    | charge[1000,4000)   | ridge                     |                        1.76562 |          0.0651568 |                               -1.70046  |                 1.00611  |     0.871694 |                        -0.134417  |                        0          |            0          |                                 0          |
| charge_bin    | charge[1000,4000)   | phase_conformal_gated_cnn |                        1.76562 |          0.078621  |                               -1.687    |                 1.00611  |     1.27218  |                         0.266064  |                        0          |            0          |                                 0          |
| charge_bin    | charge[1000,4000)   | cnn1d                     |                        1.76562 |          0.119402  |                               -1.64622  |                 1.00611  |     1.26482  |                         0.25871   |                        0          |            0          |                                 0          |
| charge_bin    | charge[1000,4000)   | gradient_boosted_trees    |                        1.76562 |          0.198452  |                               -1.56717  |                 1.00611  |     1.8244   |                         0.818293  |                        0          |            0          |                                 0          |
| charge_bin    | charge[1000,4000)   | mlp                       |                        1.76562 |          0.217319  |                               -1.5483   |                 1.00611  |     1.24001  |                         0.233903  |                        0          |            0          |                                 0          |
| amplitude_bin | amp_adc[1500,2500)  | phase_conformal_gated_cnn |                        1.1376  |          0.100333  |                               -1.03727  |                 1.35234  |     1.45683  |                         0.104489  |                        0.0135863  |            0.00666496 |                                -0.0069213  |
| amplitude_bin | amp_adc[1500,2500)  | mlp                       |                        1.1376  |          0.125974  |                               -1.01163  |                 1.35234  |     1.49364  |                         0.1413    |                        0.0135863  |            0.0069213  |                                -0.00666496 |
| amplitude_bin | amp_adc[1500,2500)  | gradient_boosted_trees    |                        1.1376  |          0.129053  |                               -1.00855  |                 1.35234  |     1.45851  |                         0.106174  |                        0.0135863  |            0.00717765 |                                -0.00640861 |
| amplitude_bin | amp_adc[1500,2500)  | cnn1d                     |                        1.1376  |          0.141732  |                               -0.995869 |                 1.35234  |     1.46823  |                         0.115896  |                        0.0135863  |            0.00717765 |                                -0.00640861 |
| amplitude_bin | amp_adc[1500,2500)  | ridge                     |                        1.1376  |          0.142435  |                               -0.995166 |                 1.35234  |     1.46501  |                         0.112671  |                        0.0135863  |            0.00974109 |                                -0.00384517 |

## Action-Band Systematics

The table below ranks saturation, q-template, baseline, and anomaly/dropout action strata by calibration loss. Sparse strata are retained with counts so they are not mistaken for broad support.

| dimension         | stratum                       | method                    |     n |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68 |   coverage68 |   coverage95 |   calibration_loss |
|:------------------|:------------------------------|:--------------------------|------:|-------------:|--------------:|----------------------:|---------------:|-------------:|-------------:|-------------------:|
| p09_anomaly_class | dropout                       | traditional               |    27 |     2.00566  |      8.12679  |             0.148148  |      10.9118   |     0        |    0.0740741 |           3.06243  |
| p09_anomaly_class | pileup_or_long_tail           | traditional               |    16 |     1.32411  |      1.731    |             0.0625    |       7.02574  |     0.1875   |    0.3125    |           2.38614  |
| p09_anomaly_class | novel_delayed_peak            | traditional               |   571 |     1.18095  |      5.11019  |             0.0770578 |       8.40638  |     0.217163 |    0.285464  |           2.27537  |
| p09_anomaly_class | novel_broad_template_mismatch | traditional               |    26 |     9.6144   |     13.7844   |             0.5       |       7.28326  |     0.115385 |    0.230769  |           2.05327  |
| baseline_bin      | baseline_rms[64,inf)          | traditional               |  3067 |     1.16796  |      3.48029  |             0.018911  |       7.64153  |     0.216498 |    0.372351  |           2.05182  |
| q_template_bin    | q_template[0.2,inf)           | traditional               |  4551 |     1.19371  |      3.12565  |             0.0186772 |       7.31942  |     0.254669 |    0.421885  |           1.9384   |
| saturation_flag   | True                          | traditional               |    16 |     4.71691  |     10.2914   |             0.3125    |       4.07616  |     0.0625   |    0.1875    |           1.48628  |
| p09_anomaly_class | novel_early_pretrigger        | traditional               |   298 |     1.31998  |      3.97116  |             0.0268456 |       3.75262  |     0.285235 |    0.402685  |           1.04244  |
| saturation_flag   | True                          | phase_conformal_gated_cnn |    16 |     5.37965  |     10.2355   |             0.25      |       2.91599  |     0.5      |    0.6875    |           0.787061 |
| saturation_flag   | False                         | traditional               | 11444 |     1.54935  |      2.63078  |             0.0187871 |       2.71209  |     0.385442 |    0.632209  |           0.658661 |
| p09_anomaly_class | novel_broad_template_mismatch | cnn1d                     |    26 |     9.2971   |     13.961    |             0.423077  |       2.37562  |     0.423077 |    0.653846  |           0.555203 |
| p09_anomaly_class | unassigned_common             | traditional               | 10516 |     1.59707  |      2.28274  |             0.0139787 |       2.19934  |     0.399106 |    0.660137  |           0.514878 |
| p09_anomaly_class | novel_broad_template_mismatch | mlp                       |    26 |    11.3005   |     14.9021   |             0.5       |       1.80933  |     0.423077 |    0.5       |           0.474077 |
| saturation_flag   | True                          | gradient_boosted_trees    |    16 |     3.364    |      8.68853  |             0.1875    |       1.51775  |     0.375    |    0.5625    |           0.404313 |
| baseline_bin      | baseline_rms[32,64)           | traditional               |   308 |     1.6669   |      3.97645  |             0.0324675 |       1.82939  |     0.477273 |    0.681818  |           0.384946 |
| p09_anomaly_class | novel_broad_template_mismatch | gradient_boosted_trees    |    26 |     7.56755  |     11.3531   |             0.423077  |       1.65658  |     0.384615 |    0.730769  |           0.366178 |
| baseline_bin      | baseline_rms[16,32)           | traditional               |   935 |     1.82582  |      2.17891  |             0.0203209 |       1.70214  |     0.455615 |    0.709091  |           0.35103  |
| p09_anomaly_class | novel_broad_template_mismatch | phase_conformal_gated_cnn |    26 |    10.5555   |     14.7851   |             0.423077  |       1.63164  |     0.461538 |    0.692308  |           0.349052 |
| q_template_bin    | q_template[0,0.025)           | traditional               |    35 |     0.759192 |      0.837733 |             0         |       0.513872 |     0.228571 |    0.828571  |           0.339862 |
| baseline_bin      | baseline_rms[8,16)            | traditional               |  3261 |     1.86653  |      2.19007  |             0.0187059 |       1.59865  |     0.443729 |    0.725544  |           0.323444 |
| q_template_bin    | q_template[0.12,0.2)          | traditional               |  1534 |     2.08051  |      3.14492  |             0.0423729 |       1.56272  |     0.423729 |    0.724902  |           0.322203 |
| p09_anomaly_class | novel_broad_template_mismatch | ridge                     |    26 |     9.27598  |     13.6269   |             0.423077  |       1.72059  |     0.615385 |    0.692308  |           0.313302 |
| p09_anomaly_class | pileup_or_long_tail           | cnn1d                     |    16 |     2.20575  |      2.18831  |             0.1875    |       1.33515  |     0.25     |    0.8125    |           0.30178  |
| saturation_flag   | True                          | ridge                     |    16 |     5.79958  |     10.6591   |             0.4375    |       1.26939  |     0.3125   |    0.6875    |           0.300694 |
| baseline_bin      | baseline_rms[0,8)             | traditional               |  3889 |     1.83999  |      2.23252  |             0.0164567 |       1.51101  |     0.44433  |    0.734636  |           0.297898 |
| q_template_bin    | q_template[0,0.025)           | cnn1d                     |    35 |     0.894468 |      0.88011  |             0         |       0.449435 |     0.371429 |    0.885714  |           0.285971 |
| q_template_bin    | q_template[0,0.025)           | gradient_boosted_trees    |    35 |     0.851618 |      0.834003 |             0         |       0.426591 |     0.371429 |    0.971429  |           0.274333 |
| q_template_bin    | q_template[0,0.025)           | ridge                     |    35 |     0.759603 |      0.811787 |             0         |       0.38137  |     0.457143 |    0.971429  |           0.267781 |
| p09_anomaly_class | dropout                       | gradient_boosted_trees    |    27 |     1.10359  |      7.93979  |             0.111111  |       0.431468 |     0.481481 |    0.851852  |           0.259021 |
| saturation_flag   | True                          | mlp                       |    16 |     3.627    |     10.68     |             0.3125    |       0.873669 |     0.375    |    0.625     |           0.253007 |
| p09_anomaly_class | pileup_or_long_tail           | phase_conformal_gated_cnn |    16 |     1.72663  |      1.88066  |             0.0625    |       1.21397  |     0.4375   |    0.6875    |           0.240554 |
| q_template_bin    | q_template[0.08,0.12)         | traditional               |  2057 |     2.06175  |      2.1857   |             0.0184735 |       1.40083  |     0.495382 |    0.781235  |           0.233735 |
| q_template_bin    | q_template[0,0.025)           | phase_conformal_gated_cnn |    35 |     0.803664 |      0.778655 |             0         |       0.252561 |     0.714286 |    0.971429  |           0.229656 |
| q_template_bin    | q_template[0.05,0.08)         | traditional               |  2021 |     1.99836  |      2.02056  |             0.0158337 |       1.36931  |     0.489857 |    0.786244  |           0.226049 |
| q_template_bin    | q_template[0,0.025)           | mlp                       |    35 |     0.708519 |      0.822339 |             0         |       0.453083 |     0.571429 |    1         |           0.205925 |
| p09_anomaly_class | dropout                       | cnn1d                     |    27 |     1.91338  |      8.01816  |             0.111111  |       0.499071 |     0.592593 |    0.888889  |           0.201718 |

Sentinel controls:

| sentinel        | method                    |     n |   calibration_loss |   pull_width68 |   coverage68 |   coverage95 |   calibration_ece |   sigma68_ns |
|:----------------|:--------------------------|------:|-------------------:|---------------:|-------------:|-------------:|------------------:|-------------:|
| amplitude_only  | ridge_uncertainty_control | 11460 |           0.120844 |        1.02596 |     0.465532 |     0.862216 |          0.15247  |      1.55109 |
| topology_only   | ridge_uncertainty_control | 11460 |           0.107566 |        1.03123 |     0.533159 |     0.837435 |          0.136935 |      1.55109 |
| run_family_only | ridge_uncertainty_control | 11460 |           0.123656 |        1.02452 |     0.461344 |     0.857941 |          0.156703 |      1.55109 |
| shuffled_target | ridge_uncertainty_control | 11460 |           0.121053 |        1.0285  |     0.468412 |     0.860471 |          0.151903 |      1.55109 |

Leakage and bookkeeping checks:

| check                                | value                                                                        | pass   | note                                                                                         |
|:-------------------------------------|:-----------------------------------------------------------------------------|:-------|:---------------------------------------------------------------------------------------------|
| raw_root_reproduction_gate           | 1                                                                            | True   | reproduction_match_table.csv exact before modeling                                           |
| required_methods_present             | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional | True   | traditional, ridge, GBT, MLP, 1D-CNN, and new phase-conformal gated CNN                      |
| uncertainty_train_eval_event_overlap | 0                                                                            | True   | uncertainty layer leaves out the evaluated run                                               |
| forbidden_feature_audit              | 0                                                                            | True   | uncertainty features exclude event id, raw residual, pull, sigma target, and held-out labels |
| s06b_required_action_columns         | saturation_flag,q_template_bin,baseline_bin,p09_anomaly_class                | True   | support closure includes saturation, q-template, baseline, and anomaly/dropout atoms         |
| s06b_required_methods_present        | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional | True   | traditional, ridge, GBT, MLP, 1D-CNN, and novel phase-conformal gated CNN                    |

## Systematics And Caveats

- Run-block bootstrap captures held-out-run and event correlation but not alternate hardware calibrations or independent beamline composition labels.
- Charge proxy is waveform area after baseline subtraction, not an externally calibrated calorimetric energy; S06b therefore phrases conclusions as amplitude/energy-proxy closure.
- Pair residuals remove the common event clock but still correlate the two staves in each pair. Absolute single-stave timing should inherit these intervals conservatively.
- Action bands are inferred from reduced waveform atoms. Dropout/anomaly labels are morphology flags, not hand-scanned truth labels for every row.
- The winner optimizes calibrated uncertainty, not merely narrow central sigma68. A narrower model with poor coverage would fail the downstream PID/energy-consumer requirement.

## Interpretation

The S06b answer is that a single monotonic sigma(E) curve is not defensible without support conditioning. The winner `phase_conformal_gated_cnn` gives the best calibrated held-out intervals, while the amplitude/charge tables and action-band fractions identify where apparent resolution changes are entangled with saturation, q-template, baseline, and dropout/anomaly support. Downstream consumers should use the support-conditional intervals or abstention/inflation bands rather than a one-dimensional amplitude or charge correction.

## Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s06b_1781054026_2063_38d35ceb_amplitude_energy_support_closure.py --config configs/s06b_1781054026_2063_38d35ceb_amplitude_energy_support_closure.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `pooled_method_summary.csv`, `per_run_bootstrap_summary.csv`, `amplitude_charge_support_summary.csv`, `action_band_composition.csv`, `monotonicity_audit.csv`, `amplitude_charge_delta_vs_traditional.csv`, `action_band_summary.csv`, `sentinel_checks.csv`, `leakage_checks.csv`, `input_sha256.csv`, and the two figures.


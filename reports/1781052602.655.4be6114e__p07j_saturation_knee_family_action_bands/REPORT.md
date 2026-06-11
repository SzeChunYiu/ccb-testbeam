# P07j: saturation knee family action bands

**Ticket:** `1781052602.655.4be6114e`  
**Worker:** `testbeam-laptop-3`  
**Date:** 2026-06-11  
**Depends on:** P07f natural B2 duplicate knees; P07g/P07i retained-window and acceptance-gate definitions; P07c/P07d timing and q_template side-effect definitions.  
**Raw ROOT directory:** `/home/billy/ccb-data/extracted/root/root`  
**Config:** `configs/p07j_1781052602_655_4be6114e_saturation_knee_family_action_bands.json`  
**Git commit:** `0a5d421e7c6a2707ebcab737b8555b11d1e6ffba`

## 0. Question

Can the conflicting natural B2 saturation-knee families be converted into transparent pass, correct, abstain, and veto action bands before corrections feed charge, timing, PID, or energy consumers, and does a run-held-out ML/NN policy improve on the traditional duplicate-readout policy?

The pre-registered metric set from the ticket was action support fraction, charge res68/bias, timing-tail delta, q_template shift, harm rate versus no correction, calibration ECE, and ML-minus-traditional deltas with run-block bootstrap confidence intervals.

## 1. Reproduction

Raw B-stack ROOT files were read directly. `HRDv` was reshaped to `(event, channel, sample)`, samples 0-3 defined the baseline, and B2/odd duplicate quantities were recomputed before any modelling.

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulse records    |      640737    |    640737    |       0 |       0     | True   |
| P07e high-amplitude B2 duplicate rows |      183132    |    183132    |       0 |       0     | True   |
| P07f duplicate-proxy knee rows        |      565387    |    565387    |       0 |       0     | True   |
| P07f low-family median knee ADC       |        2752.02 |      2752.02 |       0 |       1e-06 | True   |
| P07f high-family median knee ADC      |        7239.7  |      7239.7  |       0 |       1e-06 | True   |

The P07f duplicate-knee family anchors also reproduce exactly because the same raw duplicate rows and constrained piecewise fit are rerun here.

| family    |   runs |   median_knee_adc |   min_knee_adc |   max_knee_adc |   median_chi2_ndf_proxy |
|:----------|-------:|------------------:|---------------:|---------------:|------------------------:|
| high-knee |     12 |           7239.7  |        6827.13 |        7487.02 |             1.13424e-05 |
| low-knee  |     18 |           2752.02 |        2497.35 |        3035.64 |             8.50923e-06 |
| unstable  |      3 |            nan    |         nan    |         nan    |           nan           |

## 2. Traditional Method

For each run, binned medians of the odd/B2 duplicate-charge ratio `y` versus B2 amplitude `x` were fit with

`y(x) = beta0 + beta1 x + beta2 max(0, x - xk)`,

subject to positive pre-slope and bounded post/pre slope ratio. The fitted `xk` defines the run-family knee. High-knee runs are those with `xk >= 5000 ADC`. The transparent policy then assigns four actions. **Pass** means a stable high-knee event with negligible duplicate residual and no side-effect risk. **Correct** means `x in [xk - 550, xk + 850]`, positive duplicate residual in the preregistered correction band, and no charge/q_template/CFD side-effect violation under the retained-window correction. **Veto** means low-family or unstable high-amplitude support, excessive residual, or a predicted side-effect violation. **Abstain** covers events outside these transparent supports. The table above gives the distribution and the proxy chi2/ndf from the weighted binned residuals.

The candidate correction is deliberately small: if accepted, `Ahat = A(1 + min(0.22 max(r,0), 0.04))`, where `r` is the duplicate low-line residual. This makes the gate test about support and side effects, not about inventing an unconstrained amplitude correction.

## 3. ML/NN Methods

The supervised target is the duplicate-closure **correct** action derived on training runs only: high-knee family support, positive bounded duplicate residual, and no violation of charge, q_template, or CFD side-effect gates under the small candidate correction. Features exclude run id, event ids, odd-channel samples, odd amplitude/charge/peak, and all duplicate residuals. They include only the even B2 waveform and waveform-derived scalars such as log amplitude, charge/amplitude, peak sample, plateau count, top-two gap, early/mid/late charge fractions, and normalized samples.

Folds are leave-one-run-out. Ridge is implemented as L2 logistic regression; GBT is histogram gradient boosting; MLP is a two-layer ReLU classifier; the 1D-CNN receives the normalized 18-sample sequence. The new architecture is a residual gated CNN: residual temporal convolutions preserve edge/tail locality, and a small gate conditioned on peak coordinate plus late-sample mean suppresses channels inconsistent with saturation support.

Probability thresholds are chosen inside each training fold by maximizing F1 over a fixed preregistered grid with a precision penalty below 0.50. Calibration diagnostics are in `calibration_by_run.csv`; the shuffled-target leakage sentinel is in `leakage_sentinels.csv`.

Calibration summary across held-out runs:

| method                    |   folds |   mean_ece |   median_ece |   mean_brier |   mean_average_precision |
|:--------------------------|--------:|-----------:|-------------:|-------------:|-------------------------:|
| ML_gradient_boosted_trees |      30 |  0.156596  |    0.126698  |    0.118465  |                 0.648663 |
| ML_mlp                    |      30 |  0.0513363 |    0.0372278 |    0.0231886 |                 0.670935 |
| ML_ridge_logistic         |      30 |  0.245864  |    0.208338  |    0.172553  |                 0.446184 |
| NN_1d_cnn                 |      30 |  0.872511  |    0.875396  |    0.770277  |                 0.067819 |
| NN_residual_gated_cnn_new |      30 |  0.780626  |    0.810498  |    0.650427  |                 0.29439  |

## 4. Head-to-Head Benchmark

All rows below are evaluated on the same held-out candidate events. CIs are run-block bootstraps over held-out runs. `action_support_fraction` is the non-abstain fraction; for ML/NN policies this is the correction fraction because those models do not emit pass/veto labels. `charge_res68` is the 68th percentile of the absolute duplicate-closure residual after the accepted correction; non-accepted rows are no-correction rows for timing and q_template deltas.

| method                                |      n |   action_support_fraction |   pass_fraction |   correct_fraction |   abstain_fraction |   veto_fraction |   accepted_fraction |   accepted_fraction_ci_low |   accepted_fraction_ci_high |   charge_res68 |   charge_res68_ci_low |   charge_res68_ci_high |   charge_bias |   charge_bias_ci_low |   charge_bias_ci_high |   timing_tail_delta |   q_template_median_shift |   harm_rate_vs_no_correction |   precision |   recall |        f1 |   utility |
|:--------------------------------------|-------:|--------------------------:|----------------:|-------------------:|-------------------:|----------------:|--------------------:|---------------------------:|----------------------------:|---------------:|----------------------:|-----------------------:|--------------:|---------------------:|----------------------:|--------------------:|--------------------------:|-----------------------------:|------------:|---------:|----------:|----------:|
| NN_1d_cnn                             | 177508 |                 0.999718  |        0        |          0.999718  |        0.000281677 |        0        |           0.999718  |                  0.999426  |                   0.999982  |      0.0194345 |             0.0158377 |              0.024752  |    0.00276657 |           0.00211074 |            0.00376229 |        -1.69006e-05 |              -0.000787909 |                  0.0570284   |   0.0152876 | 0.813611 | 0.0299665 |  0.852606 |
| NN_residual_gated_cnn_new             | 177508 |                 0.77205   |        0        |          0.77205   |        0.22795     |        0        |           0.77205   |                  0.659363  |                   0.885227  |      0.0125814 |             0.0106112 |              0.0153127 |    0.00395299 |           0.00268127 |            0.00564684 |        -5.63355e-06 |              -0.000365767 |                  0.0169063   |   0.0238456 | 0.80109  | 0.0455683 |  0.757785 |
| traditional_run_family_duplicate_gate | 177508 |                 0.782725  |        0.552482 |          0.0153007 |        0.217275    |        0.214942 |           0.0153007 |                  0.0114367 |                   0.018025  |      0.0154068 |             0.0149086 |              0.015992  |    0.0138432  |           0.0133879  |            0.0142832  |         0           |               0           |                  0           |   0.814515  | 0.814515 | 0.814515  |  0.666913 |
| ML_gradient_boosted_trees             | 177508 |                 0.0679744 |        0        |          0.0679744 |        0.932026    |        0        |           0.0679744 |                  0.0531083 |                   0.0884927 |      0.0139209 |             0.012706  |              0.0153588 |    0.0124445  |           0.0111706  |            0.0138258  |        -5.63355e-06 |               0           |                  0.000146472 |   0.322866  | 0.694407 | 0.407271  |  0.393352 |
| ML_mlp                                | 177508 |                 0.0342182 |        0        |          0.0342182 |        0.965782    |        0        |           0.0342182 |                  0.024976  |                   0.0501347 |      0.0155739 |             0.0142186 |              0.0171967 |    0.0140536  |           0.0129488  |            0.0153216  |         0           |               0           |                  5.63355e-05 |   0.498784  | 0.485447 | 0.432581  |  0.380114 |
| ML_ridge_logistic                     | 177508 |                 0.0927113 |        0        |          0.0927113 |        0.907289    |        0        |           0.0927113 |                  0.0728715 |                   0.124095  |      0.0130982 |             0.0117065 |              0.0149194 |    0.0107509  |           0.00953223 |            0.0123145  |        -5.63355e-06 |               0           |                  0.00252383  |   0.212766  | 0.657904 | 0.300631  |  0.325645 |

ML/NN minus traditional deltas on the same run-bootstrap point estimates:

| method                    |   action_support_fraction_minus_traditional |   accepted_fraction_minus_traditional |   charge_res68_minus_traditional |   charge_bias_minus_traditional |   timing_tail_delta_minus_traditional |   q_template_median_shift_minus_traditional |   harm_rate_vs_no_correction_minus_traditional |   f1_minus_traditional |
|:--------------------------|--------------------------------------------:|--------------------------------------:|---------------------------------:|--------------------------------:|--------------------------------------:|--------------------------------------------:|-----------------------------------------------:|-----------------------:|
| NN_1d_cnn                 |                                   0.216993  |                             0.984418  |                      0.00402766  |                    -0.0110766   |                          -1.69006e-05 |                                -0.000787909 |                                    0.0570284   |              -0.784549 |
| NN_residual_gated_cnn_new |                                  -0.0106756 |                             0.756749  |                     -0.00282538  |                    -0.00989021  |                          -5.63355e-06 |                                -0.000365767 |                                    0.0169063   |              -0.768947 |
| ML_gradient_boosted_trees |                                  -0.714751  |                             0.0526737 |                     -0.00148596  |                    -0.00139868  |                          -5.63355e-06 |                                 0           |                                    0.000146472 |              -0.407244 |
| ML_mlp                    |                                  -0.748507  |                             0.0189175 |                      0.000167095 |                     0.000210449 |                           0           |                                 0           |                                    5.63355e-05 |              -0.381935 |
| ML_ridge_logistic         |                                  -0.690014  |                             0.0774106 |                     -0.00230868  |                    -0.00309225  |                          -5.63355e-06 |                                 0           |                                    0.00252383  |              -0.513884 |

Winner by side-effect-gated utility is **NN_1d_cnn**. The transparent traditional action-band policy has support fraction 0.7827, correction fraction 0.0153, veto fraction 0.2149, and harm rate 0.0000; the winner has support fraction 0.9997, correction fraction 0.9997, and harm rate 0.0570.

## 5. Falsification

Pre-registration came from the claimed ticket before analysis: define pass/correct/abstain/veto bands from duplicate-readout run-family knee support, split by run, report action support, charge res68/bias, timing-tail delta, q_template median shift, harm rate, and calibration diagnostics with bootstrap CIs; train ML without run/event IDs or duplicate targets.

The explicit falsification test is side-effect failure: a method is not eligible to win if `|median q_template shift| > 0.035`, `|timing tail delta| > 0.015`, or harm rate exceeds 0.08. Six primary methods were compared, so model-selection claims use the side-effect gate plus utility ranking rather than a single uncorrected p-value. The shuffled-target GBT sentinel provides the leakage null; it should not recover material accepted fraction or average precision on held-out runs.

Leakage sentinel summary:

|                                  |   count |   unique | top                 |   freq |        mean |           std |          min |         25% |         50% |         75% |         max |
|:---------------------------------|--------:|---------:|:--------------------|-------:|------------:|--------------:|-------------:|------------:|------------:|------------:|------------:|
| heldout_run                      |      30 |      nan | nan                 |    nan |  48.9       |  10.7715      |  31          |  39.25      |  50.5       |  57.75      |  65         |
| control                          |      30 |        1 | shuffled_target_gbt |     30 | nan         | nan           | nan          | nan         | nan         | nan         | nan         |
| test_accept_fraction             |      30 |      nan | nan                 |    nan |   0.023265  |   0.0222941   |   0.00405627 |   0.010119  |   0.0160488 |   0.0235738 |   0.0881612 |
| test_average_precision_vs_oracle |      12 |      nan | nan                 |    nan |   0.0282893 |   0.0155846   |   0.0100495  |   0.0168194 |   0.0261575 |   0.0318072 |   0.0597354 |
| threshold                        |      30 |      nan | nan                 |    nan |   0.05      |   2.11725e-17 |   0.05       |   0.05      |   0.05      |   0.05      |   0.05      |

## 6. Threats To Validity

- Benchmark/selection: the traditional method is strong because it is allowed to use the odd duplicate channel and per-run knee fits; ML/NN methods are deliberately harder because they must infer the correction action from even-waveform shape only.
- Data leakage: all supervised models are trained on non-held-out runs. Run id, event ids, and odd duplicate variables are absent from primary features.
- Metric misuse: action support alone is not treated as success. The utility penalizes harm and charge-closure residuals, and the full per-run distributions are written to `benchmark_by_run.csv`.
- Post-hoc selection: candidate thresholds, side-effect gates, model list, and probability grid are fixed in the config before execution. The new residual-gated CNN is included because 18-sample waveforms make local temporal residual structure a sensible inductive bias.

## 7. Provenance Manifest

`manifest.json` records input ROOT checksums, command, Python/platform metadata, seeds, config, and output hashes.

## 8. Findings And Next Steps

The configured side-effect-gated utility ranks NN_1d_cnn first, with action support 0.9997 and correction fraction 0.9997; accepted/corrected fraction 0.9997 [0.9994, 1.0000], charge res68 0.0194 [0.0158, 0.0248], timing-tail delta -0.0000, q_template median shift -0.0008, and harm rate 0.0570. That ranking is not accepted as an automatic production recommendation because label purity and side-effect risk matter: precision is 0.0153. The transparent duplicate-run-family action policy is the conservative deployment recommendation because it has much lower harm (0.0000) and directly enforces odd-readout knee support, although its correction fraction is smaller (0.0153). Waveform-only ML therefore does not justify replacing the duplicate-readout gate for production natural B2 deployment.

Hypothesis: run-family knee support is primarily a readout-family condition rather than a waveform-shape condition; even-channel waveform classifiers can emulate some high-knee support but should not replace duplicate-readout gates unless an independent natural-boundary validation shows equal charge and timing safety.

Proposed follow-up ticket:

P07k action-band propagation to downstream timing and energy consumers -- Apply the P07j traditional action bands to downstream timing, PID, q_template, and energy summaries with the odd duplicate channel hidden after band formation; this has high information gain because it directly tests whether the low-harm correction band remains safe for production consumers outside the observables used to construct it.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p07j_1781052602_655_4be6114e_saturation_knee_family_action_bands.py --config configs/p07j_1781052602_655_4be6114e_saturation_knee_family_action_bands.json
```

Artifacts: `result.json`, `manifest.json`, `raw_reproduction.csv`, `run_family_knees.csv`, `action_band_counts_by_run.csv`, `candidate_counts_by_run.csv`, `benchmark_by_run.csv`, `benchmark_summary.csv`, `ml_minus_traditional.csv`, `calibration_by_run.csv`, `leakage_sentinels.csv`, `predictions.csv.gz`, and benchmark figures.

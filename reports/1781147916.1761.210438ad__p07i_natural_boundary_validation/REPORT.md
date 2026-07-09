# P07i: Natural-Boundary Validation of the P07h Winning Model

**Ticket:** `1781147916.1761.210438ad`  
**Worker:** `testbeam-laptop-1`  
**Date:** 2026-07-10  
**Depends on:** P07f natural B2 duplicate knees; P07c/P07d timing and q-template side-effect definitions.  
**Raw ROOT directory:** `/home/billy/ccb-data/extracted/root/root`  
**Config:** `configs/p07i_1781147916_1761_210438ad_natural_boundary_validation.json`  
**Git commit:** `42160812d1c467ac0a9c2e2e00d95ac55238125b`

## 0. Question

Can the P07h artificial-saturation winner be validated on natural B2 `A >= 7000` pulses under duplicate-readout run-family knee support without worsening charge closure, CFD timing, or q_template tails, and does a run-held-out ML/NN gate improve on the transparent traditional gate?

The pre-registered metric set from the ticket was accepted fraction, charge res68, timing-tail delta, q_template median shift, and harm rate versus no correction, with run-block bootstrap confidence intervals.

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

subject to positive pre-slope and bounded post/pre slope ratio. The fitted `xk` defines the run-family knee. High-knee runs are those with `xk >= 5000 ADC`; low-knee or unstable runs abstain above the natural saturation threshold. In high-knee runs the transparent gate accepts only `x in [xk - 550, xk + 850]` and only when the odd-closure residual lies in the preregistered positive residual band. The table above gives the distribution and the proxy chi2/ndf from the weighted binned residuals.

The candidate correction is deliberately small: if accepted, `Ahat = A(1 + min(0.22 max(r,0), 0.04))`, where `r` is the duplicate low-line residual. This makes the gate test about support and side effects, not about inventing an unconstrained amplitude correction.

## 3. ML/NN Methods

The supervised target is the duplicate-closure oracle derived on training runs only: high-knee family support, positive bounded duplicate residual, and no violation of charge, q_template, or CFD side-effect gates under the small candidate correction. Features exclude run id, event ids, odd-channel samples, odd amplitude/charge/peak, and all duplicate residuals. They include only the even B2 waveform and waveform-derived scalars such as log amplitude, charge/amplitude, peak sample, plateau count, top-two gap, early/mid/late charge fractions, and normalized samples.

Folds are leave-one-run-out. Ridge is implemented as L2 logistic regression; GBT is histogram gradient boosting; MLP is a two-layer ReLU classifier; the 1D-CNN receives the normalized 18-sample sequence. The new architecture is a residual gated CNN: residual temporal convolutions preserve edge/tail locality, and a small gate conditioned on peak coordinate plus late-sample mean suppresses channels inconsistent with saturation support.

Probability thresholds are chosen inside each training fold by maximizing F1 over a fixed preregistered grid with a precision penalty below 0.50. Calibration diagnostics are in `calibration_by_run.csv`; the shuffled-target leakage sentinel is in `leakage_sentinels.csv`.

## 4. Head-to-Head Benchmark

All rows below are evaluated on the same held-out candidate events. CIs are run-block bootstraps over held-out runs. `charge_res68` is the 68th percentile of the absolute duplicate-closure residual after the accepted correction; non-accepted rows are no-correction rows for timing and q_template deltas.

| method                                |      n |   accepted_fraction |   accepted_fraction_ci_low |   accepted_fraction_ci_high |   charge_res68 |   charge_res68_ci_low |   charge_res68_ci_high |   timing_tail_delta |   q_template_median_shift |   harm_rate_vs_no_correction |   precision |   recall |        f1 |   utility |
|:--------------------------------------|-------:|--------------------:|---------------------------:|----------------------------:|---------------:|----------------------:|-----------------------:|--------------------:|--------------------------:|-----------------------------:|------------:|---------:|----------:|----------:|
| NN_1d_cnn                             | 177508 |           0.999482  |                  0.997941  |                   1         |      0.0193888 |             0.0159425 |              0.023965  |        -1.69006e-05 |              -0.00078515  |                  0.0568256   |   0.015301  | 0.814515 | 0.0299929 |  0.852999 |
| NN_residual_gated_cnn_new             | 177508 |           0.873865  |                  0.767157  |                   0.950106  |      0.0134698 |             0.0115357 |              0.0162688 |        -5.63355e-06 |              -0.000424238 |                  0.0247876   |   0.018716  | 0.805254 | 0.036429  |  0.828645 |
| traditional_run_family_duplicate_gate | 177508 |           0.431372  |                  0.325524  |                   0.518403  |      0.0132771 |             0.0110626 |              0.0154765 |        -5.63355e-06 |               0           |                  0.00762783  |   0.0309927 | 0.814515 | 0.0593663 |  0.455982 |
| ML_gradient_boosted_trees             | 177508 |           0.0678054 |                  0.0526683 |                   0.0905883 |      0.0139205 |             0.0125312 |              0.0153198 |        -5.63355e-06 |               0           |                  0.000129572 |   0.327141  | 0.69767  | 0.410277  |  0.395638 |
| ML_mlp                                | 177508 |           0.0340773 |                  0.0244157 |                   0.0491906 |      0.0155811 |             0.0141873 |              0.0170194 |         0           |               0           |                  6.76026e-05 |   0.497783  | 0.49249  | 0.442022  |  0.387492 |
| ML_ridge_logistic                     | 177508 |           0.0923789 |                  0.070719  |                   0.121771  |      0.0131003 |             0.0116043 |              0.0147397 |        -5.63355e-06 |               0           |                  0.0025182   |   0.214298  | 0.658365 | 0.302362  |  0.326714 |

Winner by side-effect-gated utility is **NN_1d_cnn**. The transparent traditional baseline has accepted fraction 0.4314 and harm rate 0.0076; the winner has accepted fraction 0.9995 and harm rate 0.0568.

## 5. Falsification

Pre-registration came from the claimed ticket before analysis: accept only inside duplicate-readout run-family knee support, split by run, report accepted fraction, charge res68, timing-tail delta, q_template median shift, and harm rate with bootstrap CIs; train ML without run/event IDs or duplicate targets.

The explicit falsification test is side-effect failure: a method is not eligible to win if `|median q_template shift| > 0.035`, `|timing tail delta| > 0.015`, or harm rate exceeds 0.08. Six primary methods were compared, so model-selection claims use the side-effect gate plus utility ranking rather than a single uncorrected p-value. The shuffled-target GBT sentinel provides the leakage null; it should not recover material accepted fraction or average precision on held-out runs.

Leakage sentinel summary:

|                                  |   count |   unique | top                 |   freq |        mean |           std |          min |          25% |         50% |         75% |         max |
|:---------------------------------|--------:|---------:|:--------------------|-------:|------------:|--------------:|-------------:|-------------:|------------:|------------:|------------:|
| heldout_run                      |      30 |      nan | nan                 |    nan |  48.9       |  10.7715      |  31          |  39.25       |  50.5       |  57.75      |  65         |
| control                          |      30 |        1 | shuffled_target_gbt |     30 | nan         | nan           | nan          | nan          | nan         | nan         | nan         |
| test_accept_fraction             |      30 |      nan | nan                 |    nan |   0.0195716 |   0.0145952   |   0.00372928 |   0.00989028 |   0.0180833 |   0.0242377 |   0.0765432 |
| test_average_precision_vs_oracle |      12 |      nan | nan                 |    nan |   0.0250174 |   0.0156045   |   0.0123     |   0.0150622  |   0.0175081 |   0.0278628 |   0.0557151 |
| threshold                        |      30 |      nan | nan                 |    nan |   0.05      |   2.11725e-17 |   0.05       |   0.05       |   0.05      |   0.05      |   0.05      |

## 6. Threats To Validity

- Benchmark/selection: the traditional method is strong because it is allowed to use the odd duplicate channel and per-run knee fits; ML/NN methods are deliberately harder because they must infer acceptance from even-waveform shape only.
- Data leakage: all supervised models are trained on non-held-out runs. Run id, event ids, and odd duplicate variables are absent from primary features.
- Metric misuse: accepted fraction alone is not treated as success. The utility penalizes harm and charge-closure residuals, and the full per-run distributions are written to `benchmark_by_run.csv`.
- Post-hoc selection: candidate thresholds, side-effect gates, model list, and probability grid are fixed in the config before execution. The new residual-gated CNN is included because 18-sample waveforms make local temporal residual structure a sensible inductive bias.

## 7. Provenance Manifest

`manifest.json` records input ROOT checksums, command, Python/platform metadata, seeds, config, and output hashes.

## 8. Findings And Next Steps

The configured side-effect-gated utility ranks NN_1d_cnn first, with accepted fraction 0.9995 [0.9979, 1.0000], charge res68 0.0194 [0.0159, 0.0240], timing-tail delta -0.0000, q_template median shift -0.0008, and harm rate 0.0568. That win is driven by near-total coverage, not label purity: precision is only 0.0153. The transparent duplicate-run-family gate is the conservative deployment recommendation because it has much lower harm (0.0076) and directly enforces odd-readout knee support, although its accepted fraction is smaller (0.4314). Waveform-only ML therefore does not justify replacing the duplicate-readout gate for production natural B2 deployment.

Hypothesis: run-family knee support is primarily a readout-family condition rather than a waveform-shape condition; even-channel waveform classifiers can emulate some high-knee support but should not replace duplicate-readout gates unless an independent natural-boundary validation shows equal charge and timing safety.

Proposed follow-up ticket:

P07j duplicate-gated natural B2 correction on independent q/timing consumers -- Apply the P07i traditional run-family duplicate gate to downstream timing, PID, and q_template consumers with the odd duplicate channel hidden after gate formation; this tests whether the safe acceptance support remains safe outside the gate-construction observables and has high information gain because it can falsify production adoption directly.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p07i_1781051216_479_669827f2_run_family_acceptance_gate.py --config configs/p07i_1781147916_1761_210438ad_natural_boundary_validation.json
```

Artifacts: `result.json`, `manifest.json`, `raw_reproduction.csv`, `run_family_knees.csv`, `candidate_counts_by_run.csv`, `benchmark_by_run.csv`, `benchmark_summary.csv`, `calibration_by_run.csv`, `leakage_sentinels.csv`, `predictions.csv.gz`, and benchmark figures.

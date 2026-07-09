# P07j: duplicate-gated natural B2 correction on independent consumers

**Ticket:** `1781151055.1851.734c09d2`  
**Worker:** `testbeam-laptop-2`  
**Date (UTC):** 2026-07-09  
**Depends on:** P07f natural B2 duplicate knees; P07i traditional run-family duplicate gate; P07c/P07d timing and q_template side-effect definitions.  
**Raw ROOT directory:** `/home/billy/ccb-data/extracted/root/root`  
**Config:** `configs/p07j_1781151055_1851_734c09d2_duplicate_gated_independent_consumers.json`  
**Git commit:** `c50a2f0486a5f8709d7a4ce28dbc1a8eaabda523`

## 0. Question

Does the P07i/P07j traditional run-family duplicate gate remain safe when it is formed with the odd duplicate readout, the odd channel is then hidden, and the candidate natural-B2 correction is propagated to independent timing and q_template consumers? Does any run-held-out ML/NN policy improve on the transparent duplicate-readout policy under identical side-effect gates?

The pre-registered metric set from the ticket was action support fraction, charge res68/bias, timing-tail delta, q_template shift, harm rate versus no correction, calibration ECE, and ML-minus-traditional deltas with run-block bootstrap confidence intervals. The odd duplicate channel is used only to form/evaluate the gate and closure oracle; downstream-consumer features are even-channel waveform observables only.

## 1. Reproduction

Raw B-stack ROOT files were read directly. `HRDv` was reshaped to `(event, channel, sample)`, samples 0-3 defined the baseline, and B2/odd duplicate quantities were recomputed before any modelling.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| S00 selected B-stave pulse records | 640737.0 | 640737.0 | 0.0 | 0.0 | True |
| P07e high-amplitude B2 duplicate rows | 183132.0 | 183132.0 | 0.0 | 0.0 | True |
| P07f duplicate-proxy knee rows | 565387.0 | 565387.0 | 0.0 | 0.0 | True |
| P07f low-family median knee ADC | 2752.018164556962 | 2752.018164556962 | 0.0 | 1e-06 | True |
| P07f high-family median knee ADC | 7239.696392405063 | 7239.696392405063 | 0.0 | 1e-06 | True |

The P07f duplicate-knee family anchors also reproduce exactly because the same raw duplicate rows and constrained piecewise fit are rerun here.

| family | runs | median_knee_adc | min_knee_adc | max_knee_adc | median_chi2_ndf_proxy |
| --- | --- | --- | --- | --- | --- |
| high-knee | 12 | 7239.696392405063 | 6827.131075949366 | 7487.016202531646 | 1.1342429364372467e-05 |
| low-knee | 18 | 2752.018164556962 | 2497.346835443038 | 3035.6403797468347 | 8.509234352944188e-06 |
| unstable | 3 |  |  |  |  |

## 2. Traditional Method

For each run, binned medians of the odd/B2 duplicate-charge ratio `y` versus B2 amplitude `x` were fit with

`y(x) = beta0 + beta1 x + beta2 max(0, x - xk)`,

subject to positive pre-slope and bounded post/pre slope ratio. The fitted `xk` defines the run-family knee. High-knee runs are those with `xk >= 5000 ADC`. The transparent policy then assigns four actions. **Pass** means a stable high-knee event with negligible duplicate residual and no side-effect risk. **Correct** means `x in [xk - 550, xk + 850]`, positive duplicate residual in the preregistered correction band, and no charge/q_template/CFD side-effect violation under the retained-window correction. **Veto** means low-family or unstable high-amplitude support, excessive residual, or a predicted side-effect violation. **Abstain** covers events outside these transparent supports. The table above gives the distribution and the proxy chi2/ndf from the weighted binned residuals.

The candidate correction is deliberately small: if accepted, `Ahat = A(1 + min(0.22 max(r,0), 0.04))`, where `r` is the duplicate low-line residual. This makes the gate test about support and side effects, not about inventing an unconstrained amplitude correction.

## 3. ML/NN Methods

The supervised target is the duplicate-closure **correct** action derived on training runs only: high-knee family support, positive bounded duplicate residual, and no violation of charge, q_template, or CFD side-effect gates under the small candidate correction. The odd duplicate channel is hidden after this gate/target construction. Features exclude run id, event ids, odd-channel samples, odd amplitude/charge/peak, and all duplicate residuals. They include only the even B2 waveform and waveform-derived scalars such as log amplitude, charge/amplitude, peak sample, plateau count, top-two gap, early/mid/late charge fractions, and normalized samples.

Folds are leave-one-run-out. Ridge is implemented as L2 logistic regression; GBT is histogram gradient boosting; MLP is a two-layer ReLU classifier; the 1D-CNN receives the normalized 18-sample sequence. The new architecture is a residual gated CNN: residual temporal convolutions preserve edge/tail locality, and a small gate conditioned on peak coordinate plus late-sample mean suppresses channels inconsistent with saturation support.

Probability thresholds are chosen inside each training fold by maximizing F1 over a fixed preregistered grid with a precision penalty below 0.50. Calibration diagnostics are in `calibration_by_run.csv`; the shuffled-target leakage sentinel is in `leakage_sentinels.csv`.

Calibration summary across held-out runs:

| method | folds | mean_ece | median_ece | mean_brier | mean_average_precision |
| --- | --- | --- | --- | --- | --- |
| ML_gradient_boosted_trees | 30 | 0.15653083001499754 | 0.12475404128324785 | 0.11758752025559085 | 0.6559306294868975 |
| ML_mlp | 30 | 0.05088648148583281 | 0.039147903793873395 | 0.02300714488533062 | 0.6683013711345575 |
| ML_ridge_logistic | 30 | 0.24570561055990686 | 0.2084366265141622 | 0.17234959290296162 | 0.4463767941354348 |
| NN_1d_cnn | 30 | 0.8716873737137542 | 0.8742219845436101 | 0.7687662545317236 | 0.06554295374137581 |
| NN_residual_gated_cnn_new | 30 | 0.8213801262462924 | 0.8263457505486491 | 0.7025180504777907 | 0.17904497041222367 |

## 4. Head-to-Head Benchmark

All rows below are evaluated on the same held-out candidate events. CIs are run-block bootstraps over held-out runs. `action_support_fraction` is the non-abstain fraction; for ML/NN policies this is the correction fraction because those models do not emit pass/veto labels. `charge_res68` is the 68th percentile of the absolute duplicate-closure residual after the accepted correction; non-accepted rows are no-correction rows for timing and q_template deltas.

| method | n | action_support_fraction | pass_fraction | correct_fraction | abstain_fraction | veto_fraction | accepted_fraction | accepted_fraction_ci_low | accepted_fraction_ci_high | charge_res68 | charge_res68_ci_low | charge_res68_ci_high | charge_bias | charge_bias_ci_low | charge_bias_ci_high | timing_tail_delta | q_template_median_shift | harm_rate_vs_no_correction | precision | recall | f1 | utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NN_1d_cnn | 177508 | 0.9996000180273564 | 0.0 | 0.9996000180273564 | 0.0003999819726434 | 0.0 | 0.9996000180273564 | 0.9984027183727526 | 1.0 | 0.0194109907682769 | 0.0159629355379882 | 0.0239656705365332 | 0.0027626834338396 | 0.0022045394916864 | 0.0038208670746603 | -1.690064673141502e-05 | -0.0007859817558606 | 0.0569326452892264 | 0.0153008681975643 | 0.8145154021227212 | 0.0299926232079458 | 0.852796180726034 |
| NN_residual_gated_cnn_new | 177508 | 0.8947258715100165 | 0.0 | 0.8947258715100165 | 0.1052741284899835 | 0.0 | 0.8947258715100165 | 0.786935082106597 | 0.9533988472840188 | 0.0139795492364325 | 0.0121413283807228 | 0.0160407472554832 | 0.0026259201393636 | 0.0017615423873741 | 0.0039044409097002 | -5.633548910471606e-06 | -0.0004307176359376 | 0.023936949320594 | 0.0180065489229478 | 0.8053751111916215 | 0.0350698408653341 | 0.8509708962405018 |
| traditional_run_family_duplicate_gate | 177508 | 0.7827252856209298 | 0.5524821416499538 | 0.0153007188408409 | 0.2172747143790702 | 0.2149424251301349 | 0.0153007188408409 | 0.0118707252671734 | 0.0182484619648054 | 0.0154068299365387 | 0.014839848616347 | 0.0160067506184386 | 0.0138431990401373 | 0.0133627950015557 | 0.0143194842929593 | 0.0 | 0.0 | 0.0 | 0.8145154021227212 | 0.8145154021227212 | 0.8145154021227212 | 0.666913040539018 |
| ML_gradient_boosted_trees | 177508 | 0.0678053946864366 | 0.0 | 0.0678053946864366 | 0.9321946053135634 | 0.0 | 0.0678053946864366 | 0.0526683320838605 | 0.0905882937842592 | 0.0139205023812757 | 0.01253120259229 | 0.015319837399611 | 0.0124669514048141 | 0.011159281866744 | 0.0139126129428696 | -5.633548910471606e-06 | 0.0 | 0.0001295716249408 | 0.3271408349645353 | 0.6976700573984708 | 0.4102766400949677 | 0.3956379918875883 |
| ML_mlp | 177508 | 0.0342238096311152 | 0.0 | 0.0342238096311152 | 0.9657761903688848 | 0.0 | 0.0342238096311152 | 0.0244367999168345 | 0.0496351191064751 | 0.0156157779194859 | 0.0142041778525524 | 0.0171038643498895 | 0.014154332991127 | 0.0129022469185557 | 0.0154698517499055 | 0.0 | 0.0 | 5.6335489104716406e-05 | 0.5018881048959415 | 0.4879946949052361 | 0.4403099253284463 | 0.3863027434265581 |
| ML_ridge_logistic | 177508 | 0.0923845685828244 | 0.0 | 0.0923845685828244 | 0.9076154314171756 | 0.0 | 0.0923845685828244 | 0.0707250203604819 | 0.1218051611800808 | 0.0130990407195016 | 0.0116018869904318 | 0.0147366516290608 | 0.0107574719254859 | 0.009491419942867 | 0.0121438889362961 | -5.633548910471606e-06 | 0.0 | 0.0025181963629808 | 0.2142899346116351 | 0.6583651457042344 | 0.302343677936148 | 0.3267049218428004 |

ML/NN minus traditional deltas on the same run-bootstrap point estimates:

| method | action_support_fraction_minus_traditional | accepted_fraction_minus_traditional | charge_res68_minus_traditional | charge_bias_minus_traditional | timing_tail_delta_minus_traditional | q_template_median_shift_minus_traditional | harm_rate_vs_no_correction_minus_traditional | f1_minus_traditional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NN_1d_cnn | 0.21687473240642663 | 0.9842992991865155 | 0.0040041608317382005 | -0.0110805156062977 | -1.690064673141502e-05 | -0.0007859817558606 | 0.0569326452892264 | -0.7845227789147754 |
| NN_residual_gated_cnn_new | 0.11200058588908668 | 0.8794251526691755 | -0.0014272807001062 | -0.0112172789007737 | -5.633548910471606e-06 | -0.0004307176359376 | 0.023936949320594 | -0.7794455612573872 |
| ML_gradient_boosted_trees | -0.7149198909344932 | 0.05250467584559569 | -0.0014863275552629996 | -0.0013762476353232009 | -5.633548910471606e-06 | 0.0 | 0.0001295716249408 | -0.4042387620277535 |
| ML_mlp | -0.7485014759898146 | 0.0189230907902743 | 0.00020894798294720032 | 0.0003111339509897001 | 0.0 | 0.0 | 5.6335489104716406e-05 | -0.3742054767942749 |
| ML_ridge_logistic | -0.6903407170381054 | 0.0770838497419835 | -0.0023077892170370994 | -0.0030857271146513994 | -5.633548910471606e-06 | 0.0 | 0.0025181963629808 | -0.5121717241865732 |

Winner by side-effect-gated utility is **NN_1d_cnn**. The transparent traditional action-band policy has support fraction 0.7827, correction fraction 0.0153, veto fraction 0.2149, and harm rate 0.0000; the winner has support fraction 0.9996, correction fraction 0.9996, and harm rate 0.0569.

## 5. Falsification

Pre-registration came from the claimed ticket before analysis: apply the P07i/P07j duplicate-readout run-family gate, hide the odd channel after gate formation, split by run, report action support, charge res68/bias, timing-tail delta, q_template median shift, harm rate, and calibration diagnostics with bootstrap CIs; train ML without run/event IDs or duplicate targets.

The explicit falsification test is side-effect failure: a method is not eligible to win if `|median q_template shift| > 0.035`, `|timing tail delta| > 0.015`, or harm rate exceeds 0.08. Six primary methods were compared, so model-selection claims use the side-effect gate plus utility ranking rather than a single uncorrected p-value. The shuffled-target GBT sentinel provides the leakage null; it should not recover material accepted fraction or average precision on held-out runs.

Leakage sentinel summary:

| index | count | unique | top | freq | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| heldout_run | 30.0 |  |  |  | 48.9 | 10.771450131297758 | 31.0 | 39.25 | 50.5 | 57.75 | 65.0 |
| control | 30 | 1 | shuffled_target_gbt | 30 |  |  |  |  |  |  |  |
| test_accept_fraction | 30.0 |  |  |  | 0.019571560141294478 | 0.014595249701930489 | 0.0037292817679558 | 0.009890284379036125 | 0.01808332695324715 | 0.02423771880293615 | 0.0765432098765432 |
| test_average_precision_vs_oracle | 12.0 |  |  |  | 0.025017437559618817 | 0.015604501788986407 | 0.0122999918404622 | 0.0150622328453812 | 0.0175081175902845 | 0.0278628146600826 | 0.0557151287575076 |
| threshold | 30.0 |  |  |  | 0.05000000000000002 | 1.4115032135209254e-17 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 |

## 6. Threats To Validity And Caveats

- Benchmark/selection: the traditional method is strong because it is allowed to use the odd duplicate channel and per-run knee fits; ML/NN methods are deliberately harder because they must infer the correction action from even-waveform shape only.
- Data leakage: all supervised models are trained on non-held-out runs. Run id, event ids, and odd duplicate variables are absent from primary features.
- Metric misuse: action support alone is not treated as success. The utility penalizes harm and charge-closure residuals, and the full per-run distributions are written to `benchmark_by_run.csv`.
- Post-hoc selection: candidate thresholds, side-effect gates, model list, and probability grid are fixed in the config before execution. The new residual-gated CNN is included because 18-sample waveforms make local temporal residual structure a sensible inductive bias.

## 7. Provenance Manifest

`manifest.json` records input ROOT checksums, command, Python/platform metadata, seeds, config, and output hashes.

## 8. Findings And Next Steps

The configured side-effect-gated utility ranks NN_1d_cnn first, with action support 0.9996 and correction fraction 0.9996; accepted/corrected fraction 0.9996 [0.9984, 1.0000], charge res68 0.0194 [0.0160, 0.0240], timing-tail delta -0.0000, q_template median shift -0.0008, and harm rate 0.0569. That ranking is not accepted as an automatic production recommendation because label purity and side-effect risk matter: precision is 0.0153. The transparent duplicate-run-family action policy is the conservative deployment recommendation because it has much lower harm (0.0000) and directly enforces odd-readout knee support, although its correction fraction is smaller (0.0153). Waveform-only ML therefore does not justify replacing the duplicate-readout gate for production natural B2 deployment.

Hypothesis: run-family knee support is primarily a readout-family condition rather than a waveform-shape condition; even-channel waveform classifiers can emulate some high-knee support but should not replace duplicate-readout gates unless an independent natural-boundary validation shows equal charge, timing, and q_template safety.

Proposed follow-up ticket:

P07l blinded downstream-energy closure for duplicate-gated B2 corrections -- Freeze the P07j/P07k duplicate-gated correction from this independent-consumer benchmark and apply it to a fully blinded energy/PID summary table with no odd-channel or duplicate-residual columns available after gate formation. Expected information gain: separates waveform/timing/q_template side-effect safety from final physics-energy stability before production adoption.

## 9. Reproducibility

```bash
/usr/bin/python3 scripts/p07j_1781151055_1851_734c09d2_duplicate_gated_independent_consumers.py --config configs/p07j_1781151055_1851_734c09d2_duplicate_gated_independent_consumers.json
```

Artifacts: `result.json`, `manifest.json`, `raw_reproduction.csv`, `run_family_knees.csv`, `action_band_counts_by_run.csv`, `candidate_counts_by_run.csv`, `benchmark_by_run.csv`, `benchmark_summary.csv`, `ml_minus_traditional.csv`, `calibration_by_run.csv`, `leakage_sentinels.csv`, `predictions.csv.gz`, and benchmark figures.


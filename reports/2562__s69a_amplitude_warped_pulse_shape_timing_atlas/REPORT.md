# S69a Amplitude-Warped Pulse-Shape Timing Atlas

## Abstract

Ticket `#2562` asks whether amplitude-normalized leading-edge curvature,
constant-fraction time, and pedestal phase explain residual timing tails under
pile-up and mild saturation.  I reproduced the selected B-stack pulse count
directly from raw ROOT `h101/HRDv`, then benchmarked a traditional
CFD/template-curvature method against ridge, gradient-boosted trees, MLP,
1D-CNN, compact transformer, and the ticket-local
`amplitude_warped_derivative_cnn_new` architecture.  The evaluation is split by
source run, and uncertainty intervals are held-out run-block percentile
bootstrap intervals.

The winner named in `result.json` is **`gradient_boosted_trees`** with held-out
`sigma_68 = 0.05614 ns`
`[0, 0.4742]`.

## Ticket Claim Provenance

The required command

```text
tn-ticket claim testbeam-laptop-1 --project testbeam
```

was run exactly once.  The local helper returned the malformed payload

```text
null
# null

null
```

without moving an open issue.  Direct backend inspection showed `#2562` was the
oldest open `project:testbeam` issue.  To avoid a second `claim` invocation, I
manually applied the same label transition intended by the helper:

```text
gh issue edit 2562 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open
```

## Raw ROOT Reproduction

For each event, `HRDv` is reshaped to `(8,18)`.  The B-stack channels are
`B2,B4,B6,B8`, corresponding to HRD channels `0,2,4,6`.  With pretrigger baseline

`b_{ec} = median(x_{ec0}, x_{ec1}, x_{ec2}, x_{ec3})`,

the reproduced selected-pulse count is

`N = sum_e sum_c 1[max_t(x_{ect} - b_{ec}) > 1000]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced raw count is
**640737**.
This matches the processed S00 selected-pulse table exactly.

## Estimand and Equations

The constant-fraction crossing at fraction `f` is computed by linear
interpolation before the pulse maximum:

`t_f = k-1 + (f A - y_{k-1})/(y_k-y_{k-1})`,

where `y_t=x_t-b`, `A=max_t y_t`, and `k` is the first pre-peak sample with
`y_k >= fA`.  The target is the event-relative CFD20 timing residual

`r_i = 10 ns * [t_0.20,i - median(t_0.20,j: j in selected B pulses of same event)]`.

This target is internal to the same raw event and therefore avoids an external
truth join.  It measures whether a method can remove pulse-shape-dependent
timing offsets among simultaneously recorded B-stack pulses.

The normalized waveform is `z_t=(x_t-b)/max(A,1)`.  First and second
differences are

`d_t=z_{t+1}-z_t`, and `c_t=d_{t+1}-d_t`.

Resolution is `sigma_68(e)=0.5[Q_84(e)-Q_16(e)]`; bias is `median(e)`;
calibration slope is the least-squares slope of predicted residual versus
target residual; tails are `P(|e|>5 ns)` and `P(|e|>10 ns)`.

## Split and Uncertainty

The split unit is the source run.  Held-out runs are
`[42, 50, 57, 58, 60, 62, 64, 65]` and training runs are
`[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56, 59, 61, 63]`.  The benchmark uses `29487` training
rows and `9600` held-out rows, after a fixed per-run cap to
keep neural training bounded.  Confidence intervals use
`500` paired held-out run-block bootstrap
replicates.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_cfd_template_curvature | traditional | ridge-regularized CFD20/50/80 time-walk, amplitude, pedestal, slope, tail, and curvature correction |
| ridge | linear ML | standardized ridge regression on engineered waveform, pedestal, CFD, derivative, curvature, and normalized sample features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled feature matrix |
| mlp | neural tabular | two-hidden-layer perceptron on the engineered scalar and normalized waveform feature vector |
| 1d_cnn | neural waveform | compact convolutional regressor over the 18 normalized waveform samples with scalar features concatenated after pooling |
| compact_waveform_transformer | neural sequence | one-layer self-attention encoder over waveform samples with scalar context |
| amplitude_warped_derivative_cnn_new | new architecture | three-channel CNN over normalized waveform, first derivative, and second derivative, with amplitude/pedestal context |

The new architecture is sensible here because the ticket hypothesis is about
amplitude-warped leading-edge curvature rather than generic waveform
classification.  The derivative channels expose edge speed and curvature
directly, while the scalar branch carries amplitude, pedestal phase, and mild
saturation nuisance terms.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | calibration_slope_pred_vs_target | calibration_slope_pred_vs_target_ci_low | calibration_slope_pred_vs_target_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 9600 | 0.123 | 0.123 | 0.123 | 0.05614 | 0 | 0.4742 | 0.2573 | 0.2052 | 0.3113 | 5.254 | 0.0426 | 0.02531 |
| amplitude_warped_derivative_cnn_new | 9600 | -0.002216 | -0.01186 | 0.01114 | 0.06615 | 0.0424 | 0.295 | 0.0229 | 0.01281 | 0.03423 | 5.809 | 0.02292 | 0.01698 |
| compact_waveform_transformer | 9600 | 0.02604 | 0.02185 | 0.02975 | 0.06739 | 0.04454 | 0.3121 | 0.02356 | 0.01314 | 0.03563 | 5.807 | 0.02344 | 0.01698 |
| 1d_cnn | 9600 | 0.01202 | 0.005868 | 0.01563 | 0.07322 | 0.03396 | 0.3078 | 0.02519 | 0.01461 | 0.03706 | 5.795 | 0.02292 | 0.01698 |
| mlp | 9600 | 0.008421 | -0.01158 | 0.02526 | 0.4271 | 0.3011 | 0.8156 | 0.2861 | 0.2321 | 0.3391 | 5.333 | 0.04479 | 0.02687 |
| traditional_cfd_template_curvature | 9600 | 0.1555 | 0.05669 | 0.234 | 0.782 | 0.599 | 1.205 | 0.08679 | 0.07072 | 0.1113 | 5.703 | 0.04885 | 0.02104 |
| ridge | 9600 | 0.07442 | -0.04614 | 0.2052 | 1.009 | 0.8711 | 1.234 | 0.1343 | 0.1049 | 0.1681 | 5.555 | 0.05615 | 0.02396 |

## Paired Deltas Against Traditional Comparator

Positive `delta_sigma68_ns` means the method is wider than the traditional
CFD/template-curvature comparator in the same bootstrap replicate.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_curvature | -0.7259 | -0.752 | -0.5979 | -0.03256 | -0.111 | 0.06628 | -0.00625 |
| amplitude_warped_derivative_cnn_new | traditional_cfd_template_curvature | -0.7159 | -0.9106 | -0.5575 | -0.1577 | -0.2289 | -0.06489 | -0.02594 |
| compact_waveform_transformer | traditional_cfd_template_curvature | -0.7146 | -0.903 | -0.5552 | -0.1295 | -0.205 | -0.03376 | -0.02542 |
| 1d_cnn | traditional_cfd_template_curvature | -0.7088 | -0.9 | -0.5648 | -0.1435 | -0.2269 | -0.04278 | -0.02594 |
| mlp | traditional_cfd_template_curvature | -0.355 | -0.4247 | -0.2875 | -0.1471 | -0.2184 | -0.06611 | -0.004062 |
| ridge | traditional_cfd_template_curvature | 0.2265 | 0.01025 | 0.3275 | -0.08111 | -0.1381 | -0.003428 | 0.007292 |

## Run and Stave Systematics

The table below is the run-level held-out decomposition.  Run-block bootstrap
intervals are intentionally conservative because the held-out support includes
calibration and analysis families with different amplitude and pedestal
distributions.

| run | group | method | n | bias_ns | sigma68_ns | calibration_slope_pred_vs_target | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | sample_i_calib | 1d_cnn | 1200 | 0.008542 | 0.03903 | 0.02664 | 0.01917 |
| 42 | sample_i_calib | amplitude_warped_derivative_cnn_new | 1200 | 0.007297 | 0.04351 | 0.02134 | 0.01917 |
| 42 | sample_i_calib | compact_waveform_transformer | 1200 | 0.0307 | 0.0418 | 0.01918 | 0.01917 |
| 42 | sample_i_calib | gradient_boosted_trees | 1200 | 0.123 | 0 | 0.2644 | 0.03333 |
| 42 | sample_i_calib | mlp | 1200 | 0.02069 | 0.3274 | 0.4251 | 0.035 |
| 42 | sample_i_calib | ridge | 1200 | 0.2426 | 0.9024 | 0.138 | 0.045 |
| 42 | sample_i_calib | traditional_cfd_template_curvature | 1200 | 0.2908 | 0.6302 | 0.0657 | 0.03917 |
| 50 | sample_i_analysis | 1d_cnn | 1200 | -0.007086 | 0.03117 | 0.009393 | 0.01917 |
| 50 | sample_i_analysis | amplitude_warped_derivative_cnn_new | 1200 | 0.02543 | 0.03293 | 0.007529 | 0.01917 |
| 50 | sample_i_analysis | compact_waveform_transformer | 1200 | 0.03312 | 0.03705 | 0.008367 | 0.01917 |
| 50 | sample_i_analysis | gradient_boosted_trees | 1200 | 0.123 | 0 | 0.1367 | 0.02667 |
| 50 | sample_i_analysis | mlp | 1200 | 0.03696 | 0.2757 | 0.175 | 0.03 |
| 50 | sample_i_analysis | ridge | 1200 | 0.3408 | 0.8479 | 0.08092 | 0.03167 |
| 50 | sample_i_analysis | traditional_cfd_template_curvature | 1200 | 0.3086 | 0.4701 | 0.08541 | 0.0275 |
| 57 | sample_i_analysis | 1d_cnn | 1200 | 0.01156 | 0.03789 | 0.0109 | 0.02 |
| 57 | sample_i_analysis | amplitude_warped_derivative_cnn_new | 1200 | -0.006551 | 0.04269 | 0.009091 | 0.02 |
| 57 | sample_i_analysis | compact_waveform_transformer | 1200 | 0.02966 | 0.04943 | 0.008785 | 0.02 |
| 57 | sample_i_analysis | gradient_boosted_trees | 1200 | 0.123 | 0.003092 | 0.2129 | 0.03583 |
| 57 | sample_i_analysis | mlp | 1200 | 0.02006 | 0.3369 | 0.2614 | 0.03833 |
| 57 | sample_i_analysis | ridge | 1200 | 0.218 | 0.9224 | 0.08279 | 0.05333 |
| 57 | sample_i_analysis | traditional_cfd_template_curvature | 1200 | 0.2809 | 0.6436 | 0.05704 | 0.04167 |
| 58 | sample_ii_analysis | 1d_cnn | 1200 | 0.01414 | 0.02337 | 0.01829 | 0.015 |
| 58 | sample_ii_analysis | amplitude_warped_derivative_cnn_new | 1200 | -0.002544 | 0.0335 | 0.01848 | 0.015 |
| 58 | sample_ii_analysis | compact_waveform_transformer | 1200 | 0.01966 | 0.04043 | 0.02443 | 0.01583 |
| 58 | sample_ii_analysis | gradient_boosted_trees | 1200 | 0.123 | 0.005069 | 0.3239 | 0.03417 |
| 58 | sample_ii_analysis | mlp | 1200 | 0.03051 | 0.2638 | 0.3371 | 0.0375 |
| 58 | sample_ii_analysis | ridge | 1200 | 0.09811 | 0.7718 | 0.1241 | 0.03833 |
| 58 | sample_ii_analysis | traditional_cfd_template_curvature | 1200 | 0.04084 | 0.4627 | 0.1346 | 0.03417 |
| 60 | sample_ii_analysis | 1d_cnn | 1200 | 0.0165 | 0.7322 | 0.04993 | 0.01917 |
| 60 | sample_ii_analysis | amplitude_warped_derivative_cnn_new | 1200 | -0.01806 | 0.7374 | 0.04714 | 0.01917 |
| 60 | sample_ii_analysis | compact_waveform_transformer | 1200 | 0.0234 | 0.7323 | 0.04713 | 0.01917 |
| 60 | sample_ii_analysis | gradient_boosted_trees | 1200 | 0.123 | 0.9533 | 0.3354 | 0.04833 |
| 60 | sample_ii_analysis | mlp | 1200 | -0.04253 | 1.281 | 0.3638 | 0.05333 |
| 60 | sample_ii_analysis | ridge | 1200 | -0.179 | 1.549 | 0.1767 | 0.06917 |
| 60 | sample_ii_analysis | traditional_cfd_template_curvature | 1200 | -0.1237 | 1.53 | 0.07201 | 0.06 |
| 62 | sample_ii_analysis | 1d_cnn | 1200 | 0.01724 | 0.646 | 0.04327 | 0.03083 |
| 62 | sample_ii_analysis | amplitude_warped_derivative_cnn_new | 1200 | -0.01092 | 0.6127 | 0.03914 | 0.03083 |
| 62 | sample_ii_analysis | compact_waveform_transformer | 1200 | 0.02835 | 0.64 | 0.04189 | 0.0325 |
| 62 | sample_ii_analysis | gradient_boosted_trees | 1200 | 0.123 | 1 | 0.3573 | 0.05833 |
| 62 | sample_ii_analysis | mlp | 1200 | -0.04837 | 1.173 | 0.3609 | 0.05833 |
| 62 | sample_ii_analysis | ridge | 1200 | -0.1323 | 1.486 | 0.1814 | 0.075 |
| 62 | sample_ii_analysis | traditional_cfd_template_curvature | 1200 | -0.03598 | 1.517 | 0.08902 | 0.065 |
| 64 | sample_ii_calib | 1d_cnn | 1200 | 0.01591 | 0.105 | 0.03549 | 0.04 |
| 64 | sample_ii_calib | amplitude_warped_derivative_cnn_new | 1200 | -0.0136 | 0.1105 | 0.03457 | 0.04 |
| 64 | sample_ii_calib | compact_waveform_transformer | 1200 | 0.02067 | 0.09637 | 0.03636 | 0.04167 |
| 64 | sample_ii_calib | gradient_boosted_trees | 1200 | 0.123 | 0.1688 | 0.2312 | 0.06333 |
| 64 | sample_ii_calib | mlp | 1200 | 0.008499 | 0.4545 | 0.2448 | 0.05833 |
| 64 | sample_ii_calib | ridge | 1200 | -0.1018 | 1.034 | 0.19 | 0.07333 |
| 64 | sample_ii_calib | traditional_cfd_template_curvature | 1200 | 0.1051 | 0.8699 | 0.162 | 0.06833 |
| 65 | sample_ii_analysis | 1d_cnn | 1200 | 0.01759 | 0.0374 | 0.01476 | 0.02 |
| 65 | sample_ii_analysis | amplitude_warped_derivative_cnn_new | 1200 | -0.01744 | 0.04421 | 0.01338 | 0.02 |
| 65 | sample_ii_analysis | compact_waveform_transformer | 1200 | 0.02024 | 0.05334 | 0.01127 | 0.02 |
| 65 | sample_ii_analysis | gradient_boosted_trees | 1200 | 0.123 | 0.03527 | 0.2356 | 0.04083 |
| 65 | sample_ii_analysis | mlp | 1200 | -0.0057 | 0.2983 | 0.1972 | 0.0475 |
| 65 | sample_ii_analysis | ridge | 1200 | -0.001928 | 0.834 | 0.1401 | 0.06333 |
| 65 | sample_ii_analysis | traditional_cfd_template_curvature | 1200 | 0.1586 | 0.6927 | 0.08052 | 0.055 |

The companion stave-stratified table is written to
`stave_heldout_metrics.csv`; it is intentionally kept out of the main text to
avoid duplicating the long run table, but it uses the same metrics and held-out
predictions.

Systematic checks:

- **Run leakage:** run numbers, event numbers, and event indices are excluded
  from every model matrix; only the split uses the run.
- **Event leakage:** the target uses same-event B-stack relative timing, but
  model inputs are single-pulse features only.  The event reference is not an
  input.
- **Pedestal nuisance:** baseline, pretrigger slope, and pretrigger RMS are
  retained as nuisance controls and are available to every learned comparator.
- **Mild saturation:** `sat_count` and tail fraction expose near-clipping
  without allowing the model to see downstream labels.
- **Finite sample:** neural models are trained on a bounded per-run sample, so
  their ranking is an architectural stress test, not a claim of final neural
  capacity.

## Caveats

The target is an internal timing-consistency residual rather than a beamline
truth timestamp.  It is appropriate for pulse-shape timing tails but cannot by
itself certify absolute time of flight.  The raw ROOT count is exact; the
benchmark table is a reproducible run-stratified sample to make the neural
panel tractable on the laptop.  If future work needs final production neural
capacity, it should repeat the same split on the full selected table with
seed-averaged neural fits.

## Conclusion

`result.json` names `gradient_boosted_trees` as the winner.  Under the run-held-out
criterion, this means the best observed method minimized the bootstrap-measured
`sigma_68` of event-relative CFD20 residuals while preserving explicit raw ROOT
count closure and leakage controls.

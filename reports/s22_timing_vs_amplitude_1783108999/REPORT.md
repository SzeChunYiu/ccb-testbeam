# S22 — Per-stave timing resolution vs amplitude

- Generated: 2026-07-03 20:03:38 UTC
- Git commit: `b85f11bc75f4d95e48a7037aad5c7939135262c3`
- Runs: Sample I [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57] / Sample II [58, 59, 60, 61, 62, 63, 65] (disjoint sets)
- Selection: baseline-subtracted amplitude A > 1000 ADC (standard anchor)
- Pickoff: CFD20, rising-edge constrained (last below->above crossing at or before the peak,
  linear interpolation; mv4/s05c fix pattern)
- Residuals: per-pair (right - left - TOF), centered by the per-(pair, run) median before pooling
  (review: uncentered pooling mixes cable-delay offsets into sigma). sigma68 = (q84-q16)/2.
- Binning: min(A_left, A_right); edges 1000, 1250, 1550, 1900, 2300, 2800, 3400, 4200, 5200, 6500, 8000, inf ADC; bins quoted only with n >= 50.
- Errors: event-level bootstrap within run (95% CI); run-to-run spread quoted separately.
  No pooled iid bootstrap over the three linearly dependent pair residuals is performed.
- Timewalk: analytic AMP-ONLY correction (features 1000/A, sqrt(1000/A), log1p(A/1000) per stave;
  s03a amp_only basis, MV4b 1/A-leading form), fit as a pair-difference model on per-(pair,run)-
  centered residuals, TWO-STAGE (downstream betas from downstream pairs only; B2's beta fit
  afterwards with downstream betas frozen, so B2 saturation cannot leak into the headline
  downstream corrections), evaluated LEAVE-ONE-RUN-OUT within each sample (every corrected
  number is out-of-sample at run level).
- Per-stave: sigma_pair/sqrt(2) under the ASSUMPTION of independent equal-variance stave errors;
  triangle decomposition cross-check where all three downstream pairs populate a bin.

## Key numbers

### sample_II

| pair | stage | amp_lo | amp_hi | n | amp_median | sigma68_ns | ci_low_ns | ci_high_ns | run_spread_std_ns | n_runs_used |
|---|---|---|---|---|---|---|---|---|---|---|
| B2-B4 | raw_cfd20 | 1000.000 | 1250.000 | 762 | 1117.250 | 1.847 | 1.561 | 2.338 | 15.652 | 7 |
| B2-B4 | raw_cfd20 | 1250.000 | 1550.000 | 1031 | 1413.000 | 1.613 | 1.425 | 1.877 | 7.385 | 7 |
| B2-B4 | raw_cfd20 | 1550.000 | 1900.000 | 1513 | 1733.000 | 1.537 | 1.407 | 1.658 | 4.976 | 7 |
| B2-B4 | raw_cfd20 | 1900.000 | 2300.000 | 2389 | 2116.500 | 1.456 | 1.373 | 1.544 | 5.087 | 7 |
| B2-B4 | raw_cfd20 | 2300.000 | 2800.000 | 4430 | 2576.000 | 1.421 | 1.368 | 1.470 | 4.161 | 7 |
| B2-B4 | raw_cfd20 | 2800.000 | 3400.000 | 6102 | 3087.500 | 1.312 | 1.266 | 1.348 | 7.663 | 7 |
| B2-B4 | raw_cfd20 | 3400.000 | 4200.000 | 3545 | 3671.000 | 1.142 | 1.086 | 1.190 | 2.869 | 7 |
| B2-B4 | raw_cfd20 | 4200.000 | 5200.000 | 666 | 4446.500 | 5.193 | 3.727 | 7.019 | 8.322 | 7 |
| B2-B4 | raw_cfd20 | 5200.000 | 6500.000 | 95 | 5535.000 | 10.791 | 4.646 | 18.300 | nan | 1 |
| B2-B4 | timewalk_corrected | 1000.000 | 1250.000 | 762 | 1117.250 | 3.021 | 2.612 | 3.388 | 15.125 | 7 |
| B2-B4 | timewalk_corrected | 1250.000 | 1550.000 | 1031 | 1413.000 | 2.921 | 2.684 | 3.308 | 8.521 | 7 |
| B2-B4 | timewalk_corrected | 1550.000 | 1900.000 | 1513 | 1733.000 | 2.622 | 2.441 | 2.835 | 4.528 | 7 |
| B2-B4 | timewalk_corrected | 1900.000 | 2300.000 | 2389 | 2116.500 | 2.172 | 2.014 | 2.252 | 5.224 | 7 |
| B2-B4 | timewalk_corrected | 2300.000 | 2800.000 | 4430 | 2576.000 | 1.594 | 1.539 | 1.646 | 3.040 | 7 |
| B2-B4 | timewalk_corrected | 2800.000 | 3400.000 | 6102 | 3087.500 | 1.364 | 1.323 | 1.400 | 7.167 | 7 |
| B2-B4 | timewalk_corrected | 3400.000 | 4200.000 | 3545 | 3671.000 | 1.516 | 1.433 | 1.560 | 2.503 | 7 |
| B2-B4 | timewalk_corrected | 4200.000 | 5200.000 | 666 | 4446.500 | 4.741 | 3.412 | 6.398 | 8.412 | 7 |
| B2-B4 | timewalk_corrected | 5200.000 | 6500.000 | 95 | 5535.000 | 11.038 | 5.325 | 17.423 | nan | 1 |
| B2-B6 | raw_cfd20 | 1000.000 | 1250.000 | 504 | 1123.750 | 3.505 | 3.253 | 4.453 | 2.072 | 5 |
| B2-B6 | raw_cfd20 | 1250.000 | 1550.000 | 679 | 1412.500 | 2.943 | 2.778 | 3.482 | 2.295 | 6 |
| B2-B6 | raw_cfd20 | 1550.000 | 1900.000 | 997 | 1734.000 | 2.622 | 2.456 | 2.832 | 2.715 | 6 |
| B2-B6 | raw_cfd20 | 1900.000 | 2300.000 | 1546 | 2116.500 | 2.201 | 2.100 | 2.334 | 1.524 | 7 |
| B2-B6 | raw_cfd20 | 2300.000 | 2800.000 | 2676 | 2564.250 | 1.954 | 1.853 | 2.040 | 2.848 | 7 |
| B2-B6 | raw_cfd20 | 2800.000 | 3400.000 | 3066 | 3059.000 | 1.697 | 1.634 | 1.751 | 7.706 | 7 |
| B2-B6 | raw_cfd20 | 3400.000 | 4200.000 | 776 | 3581.500 | 3.259 | 2.286 | 6.396 | 11.889 | 6 |
| B2-B6 | raw_cfd20 | 4200.000 | 5200.000 | 101 | 4539.000 | 20.736 | 12.633 | 24.949 | nan | 1 |
| B2-B6 | timewalk_corrected | 1000.000 | 1250.000 | 504 | 1123.750 | 3.310 | 2.894 | 4.410 | 2.465 | 5 |
| B2-B6 | timewalk_corrected | 1250.000 | 1550.000 | 679 | 1412.500 | 2.760 | 2.436 | 2.967 | 1.942 | 6 |
| B2-B6 | timewalk_corrected | 1550.000 | 1900.000 | 997 | 1734.000 | 2.396 | 2.249 | 2.672 | 1.803 | 6 |
| B2-B6 | timewalk_corrected | 1900.000 | 2300.000 | 1546 | 2116.500 | 2.167 | 2.038 | 2.282 | 1.923 | 7 |
| B2-B6 | timewalk_corrected | 2300.000 | 2800.000 | 2676 | 2564.250 | 1.751 | 1.683 | 1.841 | 1.435 | 7 |
| B2-B6 | timewalk_corrected | 2800.000 | 3400.000 | 3066 | 3059.000 | 1.541 | 1.489 | 1.603 | 7.179 | 7 |
| B2-B6 | timewalk_corrected | 3400.000 | 4200.000 | 776 | 3581.500 | 2.620 | 2.188 | 4.511 | 12.461 | 6 |
| B2-B6 | timewalk_corrected | 4200.000 | 5200.000 | 101 | 4539.000 | 21.317 | 14.589 | 26.577 | nan | 1 |
| B2-B8 | raw_cfd20 | 1000.000 | 1250.000 | 166 | 1121.500 | 7.242 | 4.092 | 19.551 | 5.259 | 4 |
| B2-B8 | raw_cfd20 | 1250.000 | 1550.000 | 237 | 1408.500 | 3.333 | 2.528 | 3.762 | 5.732 | 5 |
| B2-B8 | raw_cfd20 | 1550.000 | 1900.000 | 387 | 1739.000 | 2.622 | 2.284 | 2.849 | 0.403 | 5 |
| B2-B8 | raw_cfd20 | 1900.000 | 2300.000 | 619 | 2135.500 | 2.187 | 1.938 | 2.291 | 0.214 | 5 |
| B2-B8 | raw_cfd20 | 2300.000 | 2800.000 | 1185 | 2568.500 | 1.966 | 1.869 | 2.077 | 0.528 | 6 |
| B2-B8 | raw_cfd20 | 2800.000 | 3400.000 | 1155 | 3031.500 | 1.972 | 1.833 | 2.084 | 6.095 | 7 |
| B2-B8 | raw_cfd20 | 3400.000 | 4200.000 | 222 | 3614.000 | 16.906 | 13.002 | 19.941 | 7.119 | 5 |
| B2-B8 | raw_cfd20 | 4200.000 | 5200.000 | 56 | 4571.000 | 19.854 | 13.029 | 30.629 | nan | 0 |
| B2-B8 | timewalk_corrected | 1000.000 | 1250.000 | 166 | 1121.500 | 7.369 | 3.984 | 18.612 | 5.949 | 4 |
| B2-B8 | timewalk_corrected | 1250.000 | 1550.000 | 237 | 1408.500 | 2.665 | 2.106 | 3.130 | 4.885 | 5 |
| B2-B8 | timewalk_corrected | 1550.000 | 1900.000 | 387 | 1739.000 | 2.262 | 1.962 | 2.498 | 0.683 | 5 |
| B2-B8 | timewalk_corrected | 1900.000 | 2300.000 | 619 | 2135.500 | 1.859 | 1.709 | 2.044 | 0.365 | 5 |
| B2-B8 | timewalk_corrected | 2300.000 | 2800.000 | 1185 | 2568.500 | 1.694 | 1.576 | 1.768 | 0.631 | 6 |
| B2-B8 | timewalk_corrected | 2800.000 | 3400.000 | 1155 | 3031.500 | 1.781 | 1.644 | 1.877 | 6.010 | 7 |
| B2-B8 | timewalk_corrected | 3400.000 | 4200.000 | 222 | 3614.000 | 17.381 | 12.883 | 20.537 | 7.821 | 5 |
| B2-B8 | timewalk_corrected | 4200.000 | 5200.000 | 56 | 4571.000 | 20.158 | 13.431 | 28.871 | nan | 0 |
| B4-B6 | raw_cfd20 | 1000.000 | 1250.000 | 496 | 1125.500 | 2.877 | 2.548 | 3.106 | 0.126 | 5 |
| B4-B6 | raw_cfd20 | 1250.000 | 1550.000 | 764 | 1420.750 | 2.481 | 2.208 | 2.492 | 0.324 | 6 |
| B4-B6 | raw_cfd20 | 1550.000 | 1900.000 | 1087 | 1741.500 | 2.256 | 2.100 | 2.334 | 0.245 | 6 |
| B4-B6 | raw_cfd20 | 1900.000 | 2300.000 | 1737 | 2111.500 | 1.823 | 1.721 | 1.886 | 0.090 | 7 |
| B4-B6 | raw_cfd20 | 2300.000 | 2800.000 | 2982 | 2565.500 | 1.586 | 1.536 | 1.628 | 0.075 | 7 |
| B4-B6 | raw_cfd20 | 2800.000 | 3400.000 | 2685 | 3033.000 | 1.413 | 1.372 | 1.453 | 0.178 | 7 |
| B4-B6 | raw_cfd20 | 3400.000 | 4200.000 | 374 | 3556.000 | 1.536 | 1.371 | 1.680 | 0.087 | 4 |
| B4-B6 | timewalk_corrected | 1000.000 | 1250.000 | 496 | 1125.500 | 1.940 | 1.787 | 2.160 | 0.440 | 5 |
| B4-B6 | timewalk_corrected | 1250.000 | 1550.000 | 764 | 1420.750 | 2.111 | 1.926 | 2.165 | 0.178 | 6 |
| B4-B6 | timewalk_corrected | 1550.000 | 1900.000 | 1087 | 1741.500 | 2.007 | 1.868 | 2.078 | 0.167 | 6 |
| B4-B6 | timewalk_corrected | 1900.000 | 2300.000 | 1737 | 2111.500 | 1.712 | 1.637 | 1.776 | 0.160 | 7 |
| B4-B6 | timewalk_corrected | 2300.000 | 2800.000 | 2982 | 2565.500 | 1.415 | 1.368 | 1.474 | 0.069 | 7 |
| B4-B6 | timewalk_corrected | 2800.000 | 3400.000 | 2685 | 3033.000 | 1.288 | 1.248 | 1.326 | 0.127 | 7 |
| B4-B6 | timewalk_corrected | 3400.000 | 4200.000 | 374 | 3556.000 | 1.486 | 1.371 | 1.632 | 0.204 | 4 |
| B4-B8 | raw_cfd20 | 1000.000 | 1250.000 | 187 | 1127.500 | 3.246 | 2.418 | 3.403 | 0.201 | 5 |
| B4-B8 | raw_cfd20 | 1250.000 | 1550.000 | 326 | 1419.500 | 2.614 | 2.274 | 2.733 | 0.317 | 5 |
| B4-B8 | raw_cfd20 | 1550.000 | 1900.000 | 573 | 1752.500 | 2.119 | 1.871 | 2.226 | 0.147 | 5 |
| B4-B8 | raw_cfd20 | 1900.000 | 2300.000 | 911 | 2114.500 | 1.837 | 1.721 | 1.965 | 0.200 | 6 |
| B4-B8 | raw_cfd20 | 2300.000 | 2800.000 | 1305 | 2549.000 | 1.700 | 1.583 | 1.763 | 0.108 | 6 |
| B4-B8 | raw_cfd20 | 2800.000 | 3400.000 | 521 | 2952.500 | 1.587 | 1.416 | 1.714 | 0.115 | 5 |
| B4-B8 | timewalk_corrected | 1000.000 | 1250.000 | 187 | 1127.500 | 2.741 | 1.758 | 3.130 | 0.404 | 5 |
| B4-B8 | timewalk_corrected | 1250.000 | 1550.000 | 326 | 1419.500 | 2.476 | 2.224 | 2.739 | 0.186 | 5 |
| B4-B8 | timewalk_corrected | 1550.000 | 1900.000 | 573 | 1752.500 | 1.935 | 1.689 | 1.972 | 0.214 | 5 |
| B4-B8 | timewalk_corrected | 1900.000 | 2300.000 | 911 | 2114.500 | 1.580 | 1.494 | 1.691 | 0.212 | 6 |
| B4-B8 | timewalk_corrected | 2300.000 | 2800.000 | 1305 | 2549.000 | 1.417 | 1.370 | 1.515 | 0.083 | 6 |
| B4-B8 | timewalk_corrected | 2800.000 | 3400.000 | 521 | 2952.500 | 1.543 | 1.309 | 1.595 | 0.141 | 5 |
| B6-B8 | raw_cfd20 | 1000.000 | 1250.000 | 190 | 1140.500 | 1.260 | 1.030 | 1.515 | 0.302 | 5 |
| B6-B8 | raw_cfd20 | 1250.000 | 1550.000 | 322 | 1415.000 | 1.240 | 1.102 | 1.391 | 0.177 | 5 |
| B6-B8 | raw_cfd20 | 1550.000 | 1900.000 | 552 | 1744.750 | 1.326 | 1.204 | 1.449 | 0.166 | 5 |
| B6-B8 | raw_cfd20 | 1900.000 | 2300.000 | 907 | 2114.500 | 1.346 | 1.281 | 1.451 | 0.077 | 7 |
| B6-B8 | raw_cfd20 | 2300.000 | 2800.000 | 1308 | 2564.500 | 1.271 | 1.224 | 1.340 | 0.200 | 6 |
| B6-B8 | raw_cfd20 | 2800.000 | 3400.000 | 727 | 2988.500 | 1.176 | 1.047 | 1.239 | 0.095 | 5 |
| B6-B8 | raw_cfd20 | 3400.000 | 4200.000 | 71 | 3532.500 | 1.237 | 0.887 | 2.575 | 0.055 | 2 |
| B6-B8 | timewalk_corrected | 1000.000 | 1250.000 | 190 | 1140.500 | 1.456 | 1.190 | 1.619 | 0.252 | 5 |
| B6-B8 | timewalk_corrected | 1250.000 | 1550.000 | 322 | 1415.000 | 1.330 | 1.130 | 1.435 | 0.032 | 5 |
| B6-B8 | timewalk_corrected | 1550.000 | 1900.000 | 552 | 1744.750 | 1.145 | 1.024 | 1.186 | 0.086 | 5 |
| B6-B8 | timewalk_corrected | 1900.000 | 2300.000 | 907 | 2114.500 | 1.063 | 0.980 | 1.127 | 0.058 | 7 |
| B6-B8 | timewalk_corrected | 2300.000 | 2800.000 | 1308 | 2564.500 | 0.936 | 0.885 | 0.981 | 0.090 | 6 |
| B6-B8 | timewalk_corrected | 2800.000 | 3400.000 | 727 | 2988.500 | 0.902 | 0.838 | 0.969 | 0.069 | 5 |
| B6-B8 | timewalk_corrected | 3400.000 | 4200.000 | 71 | 3532.500 | 1.213 | 0.754 | 2.889 | 0.081 | 2 |

### sample_I

| pair | stage | amp_lo | amp_hi | n | amp_median | sigma68_ns | ci_low_ns | ci_high_ns | run_spread_std_ns | n_runs_used |
|---|---|---|---|---|---|---|---|---|---|---|
| B2-B4 | raw_cfd20 | 1000.000 | 1250.000 | 361 | 1122.000 | 38.146 | 25.396 | 52.428 | 23.437 | 8 |
| B2-B4 | raw_cfd20 | 1250.000 | 1550.000 | 348 | 1394.000 | 44.999 | 30.709 | 51.899 | 20.147 | 9 |
| B2-B4 | raw_cfd20 | 1550.000 | 1900.000 | 415 | 1734.500 | 39.064 | 25.469 | 43.183 | 19.027 | 10 |
| B2-B4 | raw_cfd20 | 1900.000 | 2300.000 | 580 | 2112.000 | 38.532 | 31.386 | 43.438 | 13.956 | 10 |
| B2-B4 | raw_cfd20 | 2300.000 | 2800.000 | 945 | 2577.500 | 35.057 | 29.370 | 38.660 | 15.757 | 11 |
| B2-B4 | raw_cfd20 | 2800.000 | 3400.000 | 1537 | 3082.000 | 37.186 | 31.665 | 38.941 | 14.609 | 11 |
| B2-B4 | raw_cfd20 | 3400.000 | 4200.000 | 1098 | 3703.000 | 34.129 | 27.852 | 36.996 | 15.681 | 11 |
| B2-B4 | raw_cfd20 | 4200.000 | 5200.000 | 394 | 4554.000 | 44.323 | 35.080 | 45.618 | 13.839 | 10 |
| B2-B4 | raw_cfd20 | 5200.000 | 6500.000 | 134 | 5614.000 | 40.414 | 23.922 | 38.680 | 17.468 | 3 |
| B2-B4 | timewalk_corrected | 1000.000 | 1250.000 | 361 | 1122.000 | 44.457 | 33.165 | 56.025 | 19.399 | 8 |
| B2-B4 | timewalk_corrected | 1250.000 | 1550.000 | 348 | 1394.000 | 46.639 | 34.047 | 55.146 | 18.932 | 9 |
| B2-B4 | timewalk_corrected | 1550.000 | 1900.000 | 415 | 1734.500 | 40.822 | 30.867 | 43.305 | 15.419 | 10 |
| B2-B4 | timewalk_corrected | 1900.000 | 2300.000 | 580 | 2112.000 | 38.553 | 31.736 | 43.025 | 11.750 | 10 |
| B2-B4 | timewalk_corrected | 2300.000 | 2800.000 | 945 | 2577.500 | 33.475 | 29.192 | 36.798 | 14.881 | 11 |
| B2-B4 | timewalk_corrected | 2800.000 | 3400.000 | 1537 | 3082.000 | 34.656 | 30.888 | 37.122 | 13.230 | 11 |
| B2-B4 | timewalk_corrected | 3400.000 | 4200.000 | 1098 | 3703.000 | 34.451 | 28.820 | 36.554 | 13.880 | 11 |
| B2-B4 | timewalk_corrected | 4200.000 | 5200.000 | 394 | 4554.000 | 45.726 | 36.680 | 47.090 | 12.544 | 10 |
| B2-B4 | timewalk_corrected | 5200.000 | 6500.000 | 134 | 5614.000 | 40.916 | 23.995 | 41.766 | 18.560 | 3 |
| B2-B6 | raw_cfd20 | 1000.000 | 1250.000 | 150 | 1142.750 | 45.872 | 25.642 | 51.657 | 20.016 | 2 |
| B2-B6 | raw_cfd20 | 1250.000 | 1550.000 | 182 | 1397.500 | 41.781 | 27.313 | 51.740 | 23.524 | 3 |
| B2-B6 | raw_cfd20 | 1550.000 | 1900.000 | 222 | 1717.000 | 36.511 | 26.809 | 42.887 | 12.512 | 7 |
| B2-B6 | raw_cfd20 | 1900.000 | 2300.000 | 292 | 2120.000 | 35.287 | 26.975 | 39.895 | 16.156 | 8 |
| B2-B6 | raw_cfd20 | 2300.000 | 2800.000 | 457 | 2558.500 | 29.880 | 19.960 | 33.752 | 17.507 | 11 |
| B2-B6 | raw_cfd20 | 2800.000 | 3400.000 | 571 | 3075.500 | 36.500 | 27.024 | 37.997 | 14.997 | 10 |
| B2-B6 | raw_cfd20 | 3400.000 | 4200.000 | 303 | 3663.500 | 41.306 | 36.121 | 46.777 | 13.395 | 7 |
| B2-B6 | raw_cfd20 | 4200.000 | 5200.000 | 81 | 4470.500 | 42.867 | 19.623 | 39.453 | nan | 0 |
| B2-B6 | timewalk_corrected | 1000.000 | 1250.000 | 150 | 1142.750 | 44.491 | 26.945 | 49.807 | 14.356 | 2 |
| B2-B6 | timewalk_corrected | 1250.000 | 1550.000 | 182 | 1397.500 | 44.923 | 28.295 | 54.065 | 21.796 | 3 |
| B2-B6 | timewalk_corrected | 1550.000 | 1900.000 | 222 | 1717.000 | 34.404 | 28.480 | 43.835 | 12.047 | 7 |
| B2-B6 | timewalk_corrected | 1900.000 | 2300.000 | 292 | 2120.000 | 33.892 | 27.197 | 39.147 | 14.425 | 8 |
| B2-B6 | timewalk_corrected | 2300.000 | 2800.000 | 457 | 2558.500 | 26.112 | 20.174 | 30.272 | 14.398 | 11 |
| B2-B6 | timewalk_corrected | 2800.000 | 3400.000 | 571 | 3075.500 | 33.876 | 27.009 | 38.159 | 13.384 | 10 |
| B2-B6 | timewalk_corrected | 3400.000 | 4200.000 | 303 | 3663.500 | 40.980 | 36.243 | 46.226 | 12.966 | 7 |
| B2-B6 | timewalk_corrected | 4200.000 | 5200.000 | 81 | 4470.500 | 45.871 | 18.928 | 41.467 | nan | 0 |
| B2-B8 | raw_cfd20 | 1000.000 | 1250.000 | 94 | 1103.000 | 56.214 | 29.697 | 54.740 | nan | 0 |
| B2-B8 | raw_cfd20 | 1250.000 | 1550.000 | 77 | 1408.000 | 48.851 | 20.773 | 42.202 | nan | 0 |
| B2-B8 | raw_cfd20 | 1550.000 | 1900.000 | 82 | 1752.250 | 39.863 | 8.981 | 40.184 | nan | 0 |
| B2-B8 | raw_cfd20 | 1900.000 | 2300.000 | 99 | 2107.500 | 37.448 | 9.506 | 38.486 | nan | 0 |
| B2-B8 | raw_cfd20 | 2300.000 | 2800.000 | 173 | 2583.000 | 26.242 | 13.128 | 29.521 | 0.341 | 2 |
| B2-B8 | raw_cfd20 | 2800.000 | 3400.000 | 199 | 3054.000 | 39.914 | 21.819 | 44.024 | 7.431 | 4 |
| B2-B8 | raw_cfd20 | 3400.000 | 4200.000 | 118 | 3752.250 | 46.789 | 32.213 | 48.867 | nan | 0 |
| B2-B8 | timewalk_corrected | 1000.000 | 1250.000 | 94 | 1103.000 | 54.337 | 32.677 | 51.815 | nan | 0 |
| B2-B8 | timewalk_corrected | 1250.000 | 1550.000 | 77 | 1408.000 | 43.323 | 19.123 | 38.705 | nan | 0 |
| B2-B8 | timewalk_corrected | 1550.000 | 1900.000 | 82 | 1752.250 | 41.195 | 7.889 | 42.758 | nan | 0 |
| B2-B8 | timewalk_corrected | 1900.000 | 2300.000 | 99 | 2107.500 | 29.153 | 9.287 | 36.382 | nan | 0 |
| B2-B8 | timewalk_corrected | 2300.000 | 2800.000 | 173 | 2583.000 | 18.002 | 12.114 | 32.362 | 7.455 | 2 |
| B2-B8 | timewalk_corrected | 2800.000 | 3400.000 | 199 | 3054.000 | 39.429 | 25.175 | 41.718 | 6.773 | 4 |
| B2-B8 | timewalk_corrected | 3400.000 | 4200.000 | 118 | 3752.250 | 50.289 | 31.201 | 51.002 | nan | 0 |
| B4-B6 | raw_cfd20 | 1000.000 | 1250.000 | 100 | 1138.750 | 2.786 | 1.902 | 2.964 | nan | 0 |
| B4-B6 | raw_cfd20 | 1250.000 | 1550.000 | 152 | 1404.750 | 2.644 | 1.953 | 2.741 | nan | 1 |
| B4-B6 | raw_cfd20 | 1550.000 | 1900.000 | 229 | 1732.500 | 2.123 | 1.746 | 2.182 | 0.287 | 7 |
| B4-B6 | raw_cfd20 | 1900.000 | 2300.000 | 340 | 2120.750 | 1.801 | 1.499 | 1.950 | 0.398 | 10 |
| B4-B6 | raw_cfd20 | 2300.000 | 2800.000 | 563 | 2590.000 | 1.537 | 1.358 | 1.583 | 0.160 | 10 |
| B4-B6 | raw_cfd20 | 2800.000 | 3400.000 | 574 | 3027.500 | 1.253 | 1.152 | 1.395 | 0.132 | 10 |
| B4-B6 | raw_cfd20 | 3400.000 | 4200.000 | 84 | 3581.000 | 1.532 | 0.883 | 1.755 | nan | 0 |
| B4-B6 | timewalk_corrected | 1000.000 | 1250.000 | 100 | 1138.750 | 1.658 | 1.100 | 1.954 | nan | 0 |
| B4-B6 | timewalk_corrected | 1250.000 | 1550.000 | 152 | 1404.750 | 2.062 | 1.469 | 2.346 | nan | 1 |
| B4-B6 | timewalk_corrected | 1550.000 | 1900.000 | 229 | 1732.500 | 2.077 | 1.666 | 2.111 | 0.281 | 7 |
| B4-B6 | timewalk_corrected | 1900.000 | 2300.000 | 340 | 2120.750 | 1.812 | 1.480 | 1.880 | 0.257 | 10 |
| B4-B6 | timewalk_corrected | 2300.000 | 2800.000 | 563 | 2590.000 | 1.369 | 1.212 | 1.408 | 0.098 | 10 |
| B4-B6 | timewalk_corrected | 2800.000 | 3400.000 | 574 | 3027.500 | 1.195 | 1.065 | 1.264 | 0.135 | 10 |
| B4-B6 | timewalk_corrected | 3400.000 | 4200.000 | 84 | 3581.000 | 1.624 | 1.064 | 1.831 | nan | 0 |
| B4-B8 | raw_cfd20 | 1550.000 | 1900.000 | 101 | 1746.500 | 1.809 | 1.152 | 1.846 | nan | 0 |
| B4-B8 | raw_cfd20 | 1900.000 | 2300.000 | 166 | 2112.500 | 1.777 | 1.452 | 1.934 | 0.546 | 2 |
| B4-B8 | raw_cfd20 | 2300.000 | 2800.000 | 214 | 2566.250 | 1.792 | 1.556 | 2.025 | 0.416 | 5 |
| B4-B8 | raw_cfd20 | 2800.000 | 3400.000 | 96 | 2934.000 | 1.550 | 1.006 | 1.684 | nan | 0 |
| B4-B8 | timewalk_corrected | 1550.000 | 1900.000 | 101 | 1746.500 | 1.627 | 1.077 | 1.769 | nan | 0 |
| B4-B8 | timewalk_corrected | 1900.000 | 2300.000 | 166 | 2112.500 | 1.694 | 1.303 | 1.785 | 0.492 | 2 |
| B4-B8 | timewalk_corrected | 2300.000 | 2800.000 | 214 | 2566.250 | 1.451 | 1.188 | 1.514 | 0.345 | 5 |
| B4-B8 | timewalk_corrected | 2800.000 | 3400.000 | 96 | 2934.000 | 1.331 | 0.802 | 1.446 | nan | 0 |
| B6-B8 | raw_cfd20 | 1250.000 | 1550.000 | 58 | 1412.250 | 1.389 | 0.710 | 1.534 | nan | 0 |
| B6-B8 | raw_cfd20 | 1550.000 | 1900.000 | 115 | 1740.500 | 1.379 | 0.966 | 1.540 | nan | 0 |
| B6-B8 | raw_cfd20 | 1900.000 | 2300.000 | 160 | 2108.500 | 1.297 | 1.008 | 1.494 | 0.331 | 3 |
| B6-B8 | raw_cfd20 | 2300.000 | 2800.000 | 214 | 2557.000 | 1.420 | 1.145 | 1.544 | 0.358 | 5 |
| B6-B8 | raw_cfd20 | 2800.000 | 3400.000 | 111 | 2965.000 | 1.314 | 0.810 | 1.350 | nan | 0 |
| B6-B8 | timewalk_corrected | 1250.000 | 1550.000 | 58 | 1412.250 | 1.375 | 0.805 | 1.606 | nan | 0 |
| B6-B8 | timewalk_corrected | 1550.000 | 1900.000 | 115 | 1740.500 | 1.189 | 0.845 | 1.327 | nan | 0 |
| B6-B8 | timewalk_corrected | 1900.000 | 2300.000 | 160 | 2108.500 | 0.954 | 0.774 | 1.140 | 0.249 | 3 |
| B6-B8 | timewalk_corrected | 2300.000 | 2800.000 | 214 | 2557.000 | 1.078 | 0.841 | 1.177 | 0.211 | 5 |
| B6-B8 | timewalk_corrected | 2800.000 | 3400.000 | 111 | 2965.000 | 1.007 | 0.676 | 1.066 | nan | 0 |

## Scaling-law fits (sigma(A) = sqrt(c^2 + k^2 (1000/A)^p), p=2 vs p=1)

```json
{
  "sample_I|B4-B6|raw_cfd20": {
    "inv_A": {
      "floor_c_ns": 0.7019129868026615,
      "coeff_k_ns": 3.4307700762561004,
      "chi2": 1.6090414930841583,
      "ndf": 5,
      "chi2_ndf": 0.3218082986168317,
      "n_points": 7
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.0,
      "coeff_k_ns": 2.5202822821241564,
      "chi2": 6.246583756363449,
      "ndf": 5,
      "chi2_ndf": 1.24931675127269,
      "n_points": 7
    }
  },
  "sample_I|B4-B6|timewalk_corrected": {
    "inv_A": {
      "floor_c_ns": 0.9726679531546977,
      "coeff_k_ns": 2.552469402053734,
      "chi2": 9.181449082073856,
      "ndf": 5,
      "chi2_ndf": 1.8362898164147712,
      "n_points": 7
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.0,
      "coeff_k_ns": 2.273034625124401,
      "chi2": 8.060558077117014,
      "ndf": 5,
      "chi2_ndf": 1.6121116154234028,
      "n_points": 7
    }
  },
  "sample_I|B4-B8|raw_cfd20": {
    "inv_A": {
      "floor_c_ns": 1.5925008414338848,
      "coeff_k_ns": 1.6344388750772354,
      "chi2": 0.28556371879155956,
      "ndf": 2,
      "chi2_ndf": 0.14278185939577978,
      "n_points": 4
    },
    "inv_sqrtA": {
      "floor_c_ns": 1.383983401348832,
      "coeff_k_ns": 1.6195109845649427,
      "chi2": 0.2639129865259469,
      "ndf": 2,
      "chi2_ndf": 0.13195649326297346,
      "n_points": 4
    }
  },
  "sample_I|B4-B8|timewalk_corrected": {
    "inv_A": {
      "floor_c_ns": 1.1534873369446559,
      "coeff_k_ns": 2.292497827030397,
      "chi2": 0.3720582940530406,
      "ndf": 2,
      "chi2_ndf": 0.1860291470265203,
      "n_points": 4
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.42884840410888453,
      "coeff_k_ns": 2.2340466426774954,
      "chi2": 0.3016703652212163,
      "ndf": 2,
      "chi2_ndf": 0.15083518261060816,
      "n_points": 4
    }
  },
  "sample_I|B6-B8|raw_cfd20": {
    "inv_A": {
      "floor_c_ns": 1.3547006431753723,
      "coeff_k_ns": 0.3210494775195989,
      "chi2": 0.19285105255938614,
      "ndf": 3,
      "chi2_ndf": 0.06428368418646205,
      "n_points": 5
    },
    "inv_sqrtA": {
      "floor_c_ns": 1.3474819896593402,
      "coeff_k_ns": 0.3021161637931507,
      "chi2": 0.19325901677897517,
      "ndf": 3,
      "chi2_ndf": 0.06441967225965839,
      "n_points": 5
    }
  },
  "sample_I|B6-B8|timewalk_corrected": {
    "inv_A": {
      "floor_c_ns": 0.8901179371879383,
      "coeff_k_ns": 1.2810245849259838,
      "chi2": 0.6671739964353388,
      "ndf": 3,
      "chi2_ndf": 0.22239133214511295,
      "n_points": 5
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.6897248937372507,
      "coeff_k_ns": 1.215400937319714,
      "chi2": 0.7654131280362076,
      "ndf": 3,
      "chi2_ndf": 0.25513770934540253,
      "n_points": 5
    }
  },
  "sample_II|B4-B6|raw_cfd20": {
    "inv_A": {
      "floor_c_ns": 0.9313111639886256,
      "coeff_k_ns": 3.3088519286344686,
      "chi2": 4.342949779750144,
      "ndf": 5,
      "chi2_ndf": 0.8685899559500289,
      "n_points": 7
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.0,
      "coeff_k_ns": 2.601361917240557,
      "chi2": 18.568965151859857,
      "ndf": 5,
      "chi2_ndf": 3.7137930303719715,
      "n_points": 7
    }
  },
  "sample_II|B4-B6|timewalk_corrected": {
    "inv_A": {
      "floor_c_ns": 1.0495656859258444,
      "coeff_k_ns": 2.528814441186519,
      "chi2": 20.52633362009228,
      "ndf": 5,
      "chi2_ndf": 4.105266724018456,
      "n_points": 7
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.02862451870706849,
      "coeff_k_ns": 2.3531152581276826,
      "chi2": 16.863162814389707,
      "ndf": 5,
      "chi2_ndf": 3.3726325628779414,
      "n_points": 7
    }
  },
  "sample_II|B4-B8|raw_cfd20": {
    "inv_A": {
      "floor_c_ns": 1.0930319832329058,
      "coeff_k_ns": 3.2691404481932134,
      "chi2": 0.5098910802217396,
      "ndf": 4,
      "chi2_ndf": 0.1274727700554349,
      "n_points": 6
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.0,
      "coeff_k_ns": 2.780969449446763,
      "chi2": 3.763927384711186,
      "ndf": 4,
      "chi2_ndf": 0.9409818461777965,
      "n_points": 6
    }
  },
  "sample_II|B4-B8|timewalk_corrected": {
    "inv_A": {
      "floor_c_ns": 0.884198888343668,
      "coeff_k_ns": 2.954637614825784,
      "chi2": 3.74642507376429,
      "ndf": 4,
      "chi2_ndf": 0.9366062684410725,
      "n_points": 6
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.0,
      "coeff_k_ns": 2.401352686065973,
      "chi2": 7.437894121396672,
      "ndf": 4,
      "chi2_ndf": 1.859473530349168,
      "n_points": 6
    }
  },
  "sample_II|B6-B8|raw_cfd20": {
    "inv_A": {
      "floor_c_ns": 1.2542027155531064,
      "coeff_k_ns": 0.47690008635595105,
      "chi2": 1.9018108704676018,
      "ndf": 5,
      "chi2_ndf": 0.38036217409352036,
      "n_points": 7
    },
    "inv_sqrtA": {
      "floor_c_ns": 1.2040041835782698,
      "coeff_k_ns": 0.620051124947647,
      "chi2": 1.78077672131894,
      "ndf": 5,
      "chi2_ndf": 0.35615534426378803,
      "n_points": 7
    }
  },
  "sample_II|B6-B8|timewalk_corrected": {
    "inv_A": {
      "floor_c_ns": 0.7422283648511944,
      "coeff_k_ns": 1.518795433843684,
      "chi2": 0.4852253735831432,
      "ndf": 5,
      "chi2_ndf": 0.09704507471662864,
      "n_points": 7
    },
    "inv_sqrtA": {
      "floor_c_ns": 0.0,
      "coeff_k_ns": 1.5272462116739485,
      "chi2": 0.5156278434714233,
      "ndf": 5,
      "chi2_ndf": 0.10312556869428466,
      "n_points": 7
    }
  }
}
```

## Triangle per-stave decomposition (cross-check)

| sample | stage | amp_bin | amp_median | stave | sigma68_ns | negative_variance_clipped |
|---|---|---|---|---|---|---|
| sample_I | raw_cfd20 | 2 | 1740.500 | B4 | 1.714 | False |
| sample_I | raw_cfd20 | 2 | 1740.500 | B6 | 1.252 | False |
| sample_I | raw_cfd20 | 2 | 1740.500 | B8 | 0.578 | False |
| sample_I | raw_cfd20 | 3 | 2112.500 | B4 | 1.536 | False |
| sample_I | raw_cfd20 | 3 | 2112.500 | B6 | 0.940 | False |
| sample_I | raw_cfd20 | 3 | 2112.500 | B8 | 0.894 | False |
| sample_I | raw_cfd20 | 4 | 2566.250 | B4 | 1.334 | False |
| sample_I | raw_cfd20 | 4 | 2566.250 | B6 | 0.763 | False |
| sample_I | raw_cfd20 | 4 | 2566.250 | B8 | 1.197 | False |
| sample_I | raw_cfd20 | 5 | 2965.000 | B4 | 1.059 | False |
| sample_I | raw_cfd20 | 5 | 2965.000 | B6 | 0.670 | False |
| sample_I | raw_cfd20 | 5 | 2965.000 | B8 | 1.131 | False |
| sample_I | timewalk_corrected | 2 | 1740.500 | B4 | 1.665 | False |
| sample_I | timewalk_corrected | 2 | 1740.500 | B6 | 1.241 | False |
| sample_I | timewalk_corrected | 2 | 1740.500 | B8 | 0.000 | True |
| sample_I | timewalk_corrected | 3 | 2112.500 | B4 | 1.619 | False |
| sample_I | timewalk_corrected | 3 | 2112.500 | B6 | 0.813 | False |
| sample_I | timewalk_corrected | 3 | 2112.500 | B8 | 0.498 | False |
| sample_I | timewalk_corrected | 4 | 2566.250 | B4 | 1.187 | False |
| sample_I | timewalk_corrected | 4 | 2566.250 | B6 | 0.682 | False |
| sample_I | timewalk_corrected | 4 | 2566.250 | B8 | 0.835 | False |
| sample_I | timewalk_corrected | 5 | 2965.000 | B4 | 1.045 | False |
| sample_I | timewalk_corrected | 5 | 2965.000 | B6 | 0.579 | False |
| sample_I | timewalk_corrected | 5 | 2965.000 | B8 | 0.825 | False |
| sample_II | raw_cfd20 | 0 | 1127.500 | B4 | 2.935 | False |
| sample_II | raw_cfd20 | 0 | 1127.500 | B6 | 0.000 | True |
| sample_II | raw_cfd20 | 0 | 1127.500 | B8 | 1.387 | False |
| sample_II | raw_cfd20 | 1 | 1419.500 | B4 | 2.393 | False |
| sample_II | raw_cfd20 | 1 | 1419.500 | B6 | 0.657 | False |
| sample_II | raw_cfd20 | 1 | 1419.500 | B8 | 1.052 | False |
| sample_II | raw_cfd20 | 2 | 1744.750 | B4 | 1.978 | False |
| sample_II | raw_cfd20 | 2 | 1744.750 | B6 | 1.086 | False |
| sample_II | raw_cfd20 | 2 | 1744.750 | B8 | 0.761 | False |
| sample_II | raw_cfd20 | 3 | 2114.500 | B4 | 1.563 | False |
| sample_II | raw_cfd20 | 3 | 2114.500 | B6 | 0.939 | False |
| sample_II | raw_cfd20 | 3 | 2114.500 | B8 | 0.965 | False |
| sample_II | raw_cfd20 | 4 | 2564.500 | B4 | 1.376 | False |
| sample_II | raw_cfd20 | 4 | 2564.500 | B6 | 0.788 | False |
| sample_II | raw_cfd20 | 4 | 2564.500 | B8 | 0.997 | False |
| sample_II | raw_cfd20 | 5 | 2988.500 | B4 | 1.251 | False |
| sample_II | raw_cfd20 | 5 | 2988.500 | B6 | 0.657 | False |
| sample_II | raw_cfd20 | 5 | 2988.500 | B8 | 0.976 | False |
| sample_II | timewalk_corrected | 0 | 1127.500 | B4 | 2.140 | False |
| sample_II | timewalk_corrected | 0 | 1127.500 | B6 | 0.000 | True |
| sample_II | timewalk_corrected | 0 | 1127.500 | B8 | 1.713 | False |
| sample_II | timewalk_corrected | 1 | 1419.500 | B4 | 2.100 | False |
| sample_II | timewalk_corrected | 1 | 1419.500 | B6 | 0.215 | False |
| sample_II | timewalk_corrected | 1 | 1419.500 | B8 | 1.312 | False |
| sample_II | timewalk_corrected | 2 | 1744.750 | B4 | 1.797 | False |
| sample_II | timewalk_corrected | 2 | 1744.750 | B6 | 0.893 | False |
| sample_II | timewalk_corrected | 2 | 1744.750 | B8 | 0.717 | False |
| sample_II | timewalk_corrected | 3 | 2114.500 | B4 | 1.466 | False |
| sample_II | timewalk_corrected | 3 | 2114.500 | B6 | 0.884 | False |
| sample_II | timewalk_corrected | 3 | 2114.500 | B8 | 0.590 | False |
| sample_II | timewalk_corrected | 4 | 2564.500 | B4 | 1.252 | False |
| sample_II | timewalk_corrected | 4 | 2564.500 | B6 | 0.660 | False |
| sample_II | timewalk_corrected | 4 | 2564.500 | B8 | 0.664 | False |
| sample_II | timewalk_corrected | 5 | 2988.500 | B4 | 1.270 | False |
| sample_II | timewalk_corrected | 5 | 2988.500 | B6 | 0.212 | False |
| sample_II | timewalk_corrected | 5 | 2988.500 | B8 | 0.877 | False |

## Caveats (honest)

- The sqrt(2) per-stave conversion assumes independent, equal-variance stave errors; any
  common-mode jitter (clock, trigger, correlated pickup) makes it an underestimate of the
  true single-stave resolution and the triangle decomposition can return negative variances
  (flagged where clipped).
- B2-containing pairs are saturation-contaminated: 30-40% of selected B2 pulses sit above
  ~7000 ADC where the amplitude (and hence both the CFD threshold and the timewalk feature)
  is compressed. B2 curves are flagged and excluded from headline per-stave claims.
- Binning by min pair amplitude attributes the resolution to the smaller pulse; the partner
  amplitude is unconstrained above it (2D profiling would sharpen the attribution and is a
  natural follow-up).
- Sample I downstream statistics are intrinsically low (B2-stopper topology): several bins do
  not reach n >= 50 and are left empty rather than quoted.
- The timewalk fit target is the pair difference itself; with per-(pair,run) centering this
  is free of the other-stave-mean attenuation bias flagged in the review for s03a, but it
  still attributes shared amplitude-correlated effects to the individual staves.
- The 10 ns sampling period is coarse relative to the sub-ns corrected resolution: sigma68
  values inherit interpolation/quantisation structure, and bins are not fully independent of
  the CFD phase.
- This study reuses the same runs as earlier S02/S03 timing work (no fresh confirmation
  partition); treat small raw-vs-corrected differences with the program-level multiplicity
  caution from the external review.

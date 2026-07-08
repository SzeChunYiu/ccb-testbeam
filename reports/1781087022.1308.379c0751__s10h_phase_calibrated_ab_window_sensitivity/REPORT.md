# S10h: phase-calibrated A/B coincidence-window sensitivity

**Ticket:** `1781087022.1308.379c0751`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This study asks whether the weak A-stack validation can be explained by uncalibrated inter-stack timing. The available event-synchronous raw closure pair in `hrdb` is the even B-stave readout and its inverted odd duplicate readout, used here as an A/B-like timing pair. I first reproduce the registered raw B-stave selected-pulse count from ROOT, estimate run- and stave-specific phase offsets from clean single-pulse events, and then benchmark coincidence classification over multiple calibrated timing windows. The named winner in `result.json` is **1d_cnn**, with mean held-out average precision **1.0000** over the tested windows.

## Raw ROOT reproduction

For every configured `hrdb_run_NNNN.root`, the script reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3 per channel, keeps the physical even B-stave channels B2/B4/B6/B8, and counts pulses with maximum baseline-subtracted amplitude above 1000 ADC. The reproduced total is **640,737** against the registered **640,737**, delta **0**.

## Phase calibration

Clean single-pulse candidates satisfy `1500 <= A_even <= 12000` ADC, an odd/even amplitude ratio above 0.15, and even and odd CFD20 peak regions in samples 4--12. For event `i`, run `r`, and stave `s`, the raw offset is

`d_i = 10 ns * (t_odd,i - t_even,i)`.

The phase estimate is the robust median

`phi_{r,s} = median_{i in clean(r,s)} d_i`,

and coincidence scoring uses the calibrated residual `Delta_i = d_i - phi_{r,s}`. Phase-offset summary:

| run | stave | clean pairs | phase offset ns | sigma68 ns |
|---:|---|---:|---:|---:|
| 58 | B2 | 180 | -9.995 | 0.016 |
| 58 | B4 | 180 | -9.990 | 0.185 |
| 58 | B6 | 172 | -9.993 | 0.112 |
| 58 | B8 | 65 | -10.000 | 0.111 |
| 59 | B2 | 180 | -9.985 | 1.363 |
| 59 | B4 | 180 | -9.988 | 0.324 |
| 59 | B6 | 180 | -9.992 | 0.756 |
| 59 | B8 | 180 | -9.997 | 0.122 |
| 60 | B2 | 180 | -9.991 | 0.127 |
| 60 | B4 | 180 | -9.982 | 0.570 |
| 60 | B6 | 180 | -9.996 | 0.382 |
| 60 | B8 | 180 | -9.996 | 0.373 |
| 61 | B2 | 180 | -9.997 | 0.115 |
| 61 | B4 | 180 | -9.993 | 0.410 |
| 61 | B6 | 180 | -9.985 | 0.243 |
| 61 | B8 | 180 | -9.995 | 0.166 |
| 62 | B2 | 180 | -9.992 | 0.209 |
| 62 | B4 | 180 | -9.993 | 0.435 |
| 62 | B6 | 180 | -9.994 | 0.423 |
| 62 | B8 | 180 | -9.993 | 0.344 |
| 63 | B2 | 180 | -9.992 | 0.084 |
| 63 | B4 | 180 | -9.994 | 0.355 |
| 63 | B6 | 180 | -9.993 | 0.401 |
| 63 | B8 | 180 | -9.999 | 0.148 |
| 65 | B2 | 180 | -9.992 | 0.030 |
| 65 | B4 | 180 | -9.987 | 0.309 |
| 65 | B6 | 180 | -9.989 | 0.454 |
| 65 | B8 | 67 | -9.997 | 0.062 |

## Benchmark design

The benchmark is split by run: runs `58, 59, 60, 61, 62` train all learned models and runs `63, 65` are held out. For each run and timing window, balanced positive/negative examples are synthesized from raw clean event pairs by injecting a calibrated residual inside or outside the requested window. This isolates window sensitivity while preserving raw waveform shape, amplitude, stave, and run support.

The operational label is `y_i(w)=1{|Delta_i| <= w}` for windows `w in {5,10,15,20,30} ns`. Run-bootstrap CIs draw held-out runs with replacement and recompute pooled ROC AUC and average precision; therefore the intervals represent run-to-run support uncertainty rather than independent-row binomial uncertainty.

The strong traditional baseline is not a strawman. It combines the calibrated phase margin with waveform agreement and charge-balance penalties:

`S_trad = 1 - |Delta|/w - 0.15 |log(A_odd/A_even)| - 0.25 RMS(x_odd - x_even)`.

Ridge, gradient-boosted trees, and the MLP receive even/odd/difference/product waveform samples plus engineered timing, charge, tail, peak, and stave features. The 1D-CNN receives two waveform channels plus the calibrated residual, charge ratio, and window. The new architecture is a late-fusion phase CNN: even and odd waveforms pass through separate convolutional stems, are fused through a learned phase-aware gate, and then classified with scalar phase and charge context. This is sensible here because A/B coincidence is a paired-sensor problem, not a single-waveform morphology problem.

## Results

| method | window ns | AP | 95% CI | ROC AUC | 95% CI | rows | positives |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1d_cnn | 5 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 181 |
| traditional_phase_template | 5 | 0.9998 | [0.9998, 0.9998] | 0.9998 | [0.9998, 0.9998] | 380 | 181 |
| late_fusion_phase_cnn_new | 5 | 0.9995 | [0.9994, 0.9998] | 0.9996 | [0.9994, 0.9998] | 380 | 181 |
| mlp | 5 | 0.9970 | [0.9955, 0.9989] | 0.9972 | [0.9958, 0.9990] | 380 | 181 |
| ridge | 5 | 0.9967 | [0.9943, 0.9989] | 0.9974 | [0.9955, 0.9990] | 380 | 181 |
| gradient_boosted_trees | 5 | 0.9945 | [0.9889, 1.0000] | 0.9975 | [0.9950, 1.0000] | 380 | 181 |
| 1d_cnn | 10 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| late_fusion_phase_cnn_new | 10 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| mlp | 10 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| ridge | 10 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| traditional_phase_template | 10 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| gradient_boosted_trees | 10 | 0.9948 | [0.9896, 1.0000] | 0.9974 | [0.9947, 1.0000] | 380 | 190 |
| 1d_cnn | 15 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| gradient_boosted_trees | 15 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| late_fusion_phase_cnn_new | 15 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| ridge | 15 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| traditional_phase_template | 15 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| mlp | 15 | 0.9999 | [0.9999, 1.0000] | 0.9999 | [0.9999, 1.0000] | 380 | 190 |
| 1d_cnn | 20 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| gradient_boosted_trees | 20 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| late_fusion_phase_cnn_new | 20 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| mlp | 20 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| ridge | 20 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| traditional_phase_template | 20 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| 1d_cnn | 30 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| late_fusion_phase_cnn_new | 30 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| mlp | 30 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| ridge | 30 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| traditional_phase_template | 30 | 1.0000 | [1.0000, 1.0000] | 1.0000 | [1.0000, 1.0000] | 380 | 190 |
| gradient_boosted_trees | 30 | 0.9974 | [0.9947, 1.0000] | 0.9973 | [0.9947, 1.0000] | 380 | 190 |

Mean held-out average precision across windows:

| method | mean AP | mean ROC AUC |
|---|---:|---:|
| 1d_cnn | 1.0000 | 1.0000 |
| gradient_boosted_trees | 0.9973 | 0.9984 |
| late_fusion_phase_cnn_new | 0.9999 | 0.9999 |
| mlp | 0.9994 | 0.9994 |
| ridge | 0.9993 | 0.9995 |
| traditional_phase_template | 1.0000 | 1.0000 |

Per-run metrics are stored in `heldout_per_run_metrics.csv`. The compact summary below reports the AP range across held-out runs and windows:

| method | min AP | max AP | finite cells |
|---|---:|---:|---:|
| 1d_cnn | 1.0000 | 1.0000 | 10 |
| gradient_boosted_trees | 0.9889 | 1.0000 | 10 |
| late_fusion_phase_cnn_new | 0.9994 | 1.0000 | 10 |
| mlp | 0.9955 | 1.0000 | 10 |
| ridge | 0.9943 | 1.0000 | 10 |
| traditional_phase_template | 0.9998 | 1.0000 | 10 |

## Systematics and Caveats

- The odd duplicate readout is an A/B-like closure target, not a physically independent A-stack detector. The report therefore tests whether phase calibration can rescue a paired-readout coincidence window, not the full independent A-stack acceptance.
- Labels are window-threshold labels derived after injecting calibrated residuals into raw clean pairs. This gives controlled truth for method comparison but does not establish the real overlapping-pulse prevalence.
- The traditional baseline directly observes the calibrated residual used in the label. That is intentional: the question is whether phase-calibrated timing is already sufficient before adding waveform ML. Learned methods also see the same timing scalar, so the comparison is fair for this operational task.
- Run-bootstrap intervals use only two held-out runs, so they are sensitivity diagnostics, not final production uncertainties.
- Phase offsets are medians over selected clean pairs. Residual run substructure, amplitude-dependent time walk, and independent A-stack geometry are not propagated beyond the observed clean-pair width.

## Verdict

`result.json` names **1d_cnn** as the winner by mean held-out average precision over timing windows. The main physics conclusion is that phase calibration makes the window task nearly deterministic in this duplicate-readout closure setting; the strongest traditional phase-margin method is therefore a serious baseline, and any future independent A-stack claim must beat this calibrated reference on true `hrda`/`hrdb` paired data.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s10h_1781087022_1308_379c0751_phase_calibrated_ab_window_sensitivity.py --config configs/s10h_1781087022_1308_379c0751_phase_calibrated_ab_window_sensitivity.json
```

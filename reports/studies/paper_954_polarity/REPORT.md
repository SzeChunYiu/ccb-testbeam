# Issue #954 — Measured channel-polarity study (8×16 raw product)

**Verdict: the locked v1 polarity map is FALSIFIED for channels 2–7.** The
measured map is `configs/channel_polarity_v2.json`
(status `MEASURED_202608_RUNS31_65_UNANIMOUS_BOTH_ESTIMATORS`).

## Measurement

- Inputs: all 33 runs (31–65, 1,096,728 events) of the pre-threshold 8×16 raw
  product, every file SHA-256-verified against
  `reports/studies/paper_1318_depth_profile/manifest_8x16.json`.
- Two independent estimators per run: the locked module
  `scripts/channel_polarity.py::infer_channel_polarity` (now with an
  isolated-dropout mask) and an independent MAD-vote estimator
  (σ = 1.4826·MAD of raw pretrigger samples, kσ = 8 exclusive votes).
- Every channel: **unanimous across all 33 runs in both estimators.**

| ch | v1 | measured | run-31 votes (pos:neg) | frac_pos_pref |
|----|----|----|----|----|
| 0 | +1 | **+1** ✓ | 27274:2200 | 0.891 |
| 1 | −1 | **−1** ✓ | 335:17426 | 0.027 |
| 2 | +1 | **−1** ✗ | 3388:16850 | 0.208 |
| 3 | −1 | **+1** ✗ | 36378:222 | 0.992 |
| 4 | +1 | **−1** ✗ | 116:34563 | 0.004 |
| 5 | −1 | **+1** ✗ | 35481:82 | 0.997 |
| 6 | +1 | **−1** ✗ | 101:34870 | 0.003 |
| 7 | −1 | **+1** ✗ | 33827:15 | 0.999 |

The measured pattern is pair-alternating `(+,−)(−,+)(−,+)(−,+)`: only the
(ch0, ch1) pair matches v1's even-positive convention. Negative controls
(synthetic truth recovery, sign-flip recovery, low-SNR fail-closed, dropout
robustness for both estimators) all pass; the low-SNR control fails closed
(AMBIGUOUS/UNMEASURED, sign 0, never authorising).

## Consequence for the v1-built 8×16 event product

Under v1, `estimate_amplitude` reads the **noise side** of channels 2–7. Run-31
median amplitudes:

| ch | v1 convention (max−base) | measured convention | true pulses |
|----|----|----|----|
| 0 | 4709.0 | 9.0 | positive (v1 correct) |
| 2 | 434.2 | 1129.0 | negative |
| 4 | **14.5** | **2422.5** | negative |
| 6 | **13.0** | **2554.5** | negative |

B6/B8 amplitudes in the committed event table are pure noise-side maxima
(~13–15 ADC), not pulse heights.

## Falsification check on the #1318 depth profile

`depth_profile_falsification.json` (producer:
`scripts/real_data/issue_954_profile_falsification.py`) recomputes the #1318
observable from raw under v1 and the measured map. The v1 arm reproduces the
committed `depth_profile_result_thresh_0.json` exactly (0.8740 / 0.7267 B2
shares), validating the pipeline. Under the measured map at threshold 0:

| arm | Sample I (B2,B4,B6,B8) | Sample II | B8/B2 I → II |
|----|----|----|----|
| v1 (published) | 0.874, 0.107, 0.011, 0.008 | 0.727, 0.128, 0.085, 0.061 | 0.009 → 0.084 |
| measured, even ch | 0.353, 0.156, 0.240, 0.252 | 0.153, 0.273, 0.278, 0.296 | 0.713 → 1.935 |
| measured, odd ch | 0.352, 0.204, 0.220, 0.225 | 0.216, 0.242, 0.266, 0.276 | 0.638 → 1.278 |

- The published **87.4 % entrance concentration is a polarity artifact** and is
  withdrawn; CL-1318-001 is marked FLAWED pending regeneration.
- The qualitative claim **survives**: Sample II carries a larger downstream
  share than Sample I under every polarity arm, threshold (0–1000 ADC) and
  channel choice (even/odd).
- Even-vs-odd channel choice shifts the quantitative profile (e.g. II B2 share
  0.153 vs 0.216): the regeneration must carry the duplicate-readout channel
  choice as a nuisance envelope (same discipline as the #1319 MC parity
  envelope), not silently pick one.
- CL-1320-001 (8.748 ns B4–B6 residual) consumed the same v1 product; it is
  likewise FLAWED pending regeneration with v2 waveforms.

## Follow-ups

1. Rebuild the 8×16 event product with `configs/channel_polarity_v2.json`
   (builder now accepts the measured status, fail-closed otherwise).
2. Regenerate #1318 depth profile + figures + paper numbers from the v2
   product, with the even/odd duplicate channel choice as a nuisance envelope.
3. Reassess #1320 timing residual on v2 waveforms.
4. Paper text (abstract/conclusions) cites 87.4 %/72.7 %/7.6× — replace after
   regeneration; ledger rows updated in this PR.

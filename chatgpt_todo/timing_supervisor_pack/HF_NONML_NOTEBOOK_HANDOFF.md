# Hugging Face non-ML timing notebook handoff

## Purpose

Use the public Hugging Face dataset `billyyiu747/ccb-testbeam` as the external data source for the student-facing non-ML timing notebook instead of depending on the LUNARC filesystem path.

## Frozen primary sample

- Sample: `sample_ii_analysis`
- Analysis runs: `58,59,60,61,62,63,65`
- Calibration run `64`: explicitly excluded
- Primary staves: B4/B6; B8 retained for common-population three-stave checks
- Channel map: B2/B4/B6/B8 = 0/2/4/6 (0-based)

## Primary Hugging Face input

Dataset: `billyyiu747/ccb-testbeam`

Prefer the dataset-card `parquet/` lane because it is described as the ucesb raw ADC representation with `HRDv_ch001 ... HRDv_ch128`. Do not use `sorted/` precomputed waveform features as the primary timing input.

The notebook must resolve and record the exact Hugging Face repository revision SHA at runtime, list the exact source files, hash every downloaded source file, and require complete coverage of all seven analysis runs before timing.

If the Parquet lane cannot prove all seven requested runs, fail closed rather than silently using `parquet/sample/events_sample.parquet` as a partial physics sample. The `ccb_data_hrd.zip` archive may be used only as an explicit fallback, with archive/member provenance recorded.

## Reconstruction contract

- Expected raw event schema: 128 ADC values -> channel-major `(8,16)`
- Sample period: 10 ns
- Baseline: median samples 0-3
- Public-source membership: direct baseline-subtracted amplitude > 1000 ADC
- Primary pickoff: strict linearly interpolated CFD20
- Strict sample-0 policy: threshold already crossed at sample 0 => left-censored / NaN; do not fabricate t=0
- Compatibility lane may reproduce the historical `data_side_real_beam.py` sample-0-to-zero convention, but it is not the primary estimator
- Primary B4-B6 geometry hypothesis: 4.0 cm with 0.078 ns/cm constant TOF; explicitly show width translation invariance

## Five-event comparison contract

Choose five complete valid B4-B6 CFD20 events using stable SHA256 ordering of `seed:run:eventno`, seed `20260907`. Export:

- exact event IDs
- all 16 B4 and B6 raw ADC values
- baseline and corrected ADC
- amplitude and peak sample
- CFD threshold
- interpolation bracket
- interpolation phase
- crossing slope
- CFD timestamp
- raw B6-B4 residual
- TOF-shifted residual

Five events are implementation-comparison examples only. All timing-width diagnostics use the complete selected Sample-II event population.

## Statistical/physics gates

- Report sigma68, standard deviation, RMS/tails and event count together
- Show full and log-y residual distributions
- Scan CFD fractions
- Report run stability
- Three-stave variance algebra must use pair variances on one common B4/B6/B8 event population; never substitute `sigma68^2`
- Never clip negative inferred variances
- Pair width is not automatically intrinsic single-stave resolution
- Current 8x16 public beam product remains timing-format limited; no detector-resolution authorization from a narrow/conditional pair result alone

## Provenance requirement

Repository addendum `chatgpt_todo/PAPER_COMPLETION_AUDIT_HF_DATA_ADDENDUM_20260814.md` requires byte-level verification before calling the Hugging Face mirror authorising. Record Hub revision, file SHA-256, run coverage and schema in the notebook output manifest, and compare with LUNARC digests when an authorising digest set is available.

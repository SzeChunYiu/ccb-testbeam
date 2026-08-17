# Remaining external actions after repository-side audit repairs

This file intentionally lists only work that cannot be completed honestly from repository text/code alone. Everything else remains the audit programme's responsibility under #1594.

## 1. Canonical raw beam archive + hardware semantics (#1603)

The repository already has archive/per-run reference hashes in `reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv`. Do not create replacement expected values.

External actions:

- populate/confirm `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam-data/` from the authoritative **144-word / 8×18** raw product;
- verify every copied archive/per-run file against the committed SHA-256/byte manifest;
- establish which recorded local 144-word copy is authoritative by byte identity (`/home/billy/Desktop/test_beam/data/` vs `/home/billy/ccb-data/data/extracted/root/root/`);
- provide authoritative channel/stave mapping and channel swaps/dead-channel records;
- provide independent pulse-polarity / ADC-coding / sampling-clock documentation or a source-bound raw-waveform measurement;
- provide hardware trigger logic by run period, firmware changes and run-quality exclusions.

The separate LUNARC path `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/` is recorded as a **truncated 128-word staging product** and is non-authorising for waveform physics.

## 2. Detector/electronics bench calibration (#1604)

Supply any available bench/run records for:

- ADC/pulser gain and linearity;
- pedestal/forced-trigger data;
- timing/reference-clock calibration;
- SiPM bias and temperature during the beam period;
- SiPM gain/PDE/crosstalk/afterpulse measurements if available;
- WLS fibre type/lot/geometry and any attenuation/timing measurements;
- electronics saturation/full-scale and recovery behavior.

If a measurement does not exist, say so. The dependent precision claim must remain `BLOCKED` and the quantity becomes a nuisance parameter; it must not be reconstructed from an old headline.

## 3. Mechanical/material survey (#1608)

Supply drawings/survey/BOM information for material upstream of and between active staves:

- windows;
- target and holders;
- trigger counters;
- support structures;
- air gaps;
- coatings/wrapping;
- fibre/optical interfaces;
- electronics/support material in the acceptance.

This is needed before quantitative stopping-depth/acceptance transfer can be trusted.

## 4. New simulation production / runtime receipt (#1608/#1606)

The p+d reference/model selection is **no longer a user task**. The repository now has a source-bound 190 MeV p+d differential-cross-section table from K. Ermisch et al., *Phys. Rev. C* 71, 064004 (2005), with byte-bound metadata and production-macro checks.

External execution still needed:

- run the finalized material/source nuisance configurations on the real Geant4 environment;
- propagate cross-section statistical/systematic and support/extrapolation variations;
- preserve an immutable runtime receipt binding executable, Geant4/runtime dependencies, macro/config, source table bytes, geometry/material model, seed and outputs;
- regenerate stopping/DeltaE-E/PID-sensitive MC after the validated changes.

## 5. Independent final validation sample (#1605/#1606/#1609)

For promoted model-selection/ML claims, reserve a run block / beam period / external dataset that was never used for feature discovery, cut tuning, architecture choice or hyperparameter selection. If no untouched sample remains, confirm that explicitly; the affected claims stay exploratory/gated until new independent data exist.

## 6. Beam-current / rate reference if available (#1607)

Provide independent beam-current or trigger-rate logs if they exist. These are needed for direct rate/pile-up validation rather than inferring a detector rate limit only from waveform-window arithmetic.

## What does NOT need user intervention

Repository-side claim governance, equation/reference audits, software defects, stale/superseded documentation, scientific-figure standards, statistical/ML audit tooling, dependency/supersession mapping, rerun code and fail-closed CI are audit-program work. Do not manually choose which old headline to preserve; corrected evidence determines the surviving values.

GitHub handoff: #1617. Keep this file and #1617 synchronized when external evidence closes a blocker.

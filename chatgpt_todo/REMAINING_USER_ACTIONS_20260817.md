# Remaining external actions after repository-side audit repairs

This file intentionally lists only work that cannot be completed honestly from repository text/code alone. Everything else belongs to the automated/analysis repair programme in #1594.

## 1. Raw beam data identity and hardware semantics (#1603)

Provide or make accessible the authoritative raw ROOT dataset and associated run/hardware records needed to establish:

- exact file inventory and SHA-256 hashes;
- authoritative run list and archive lineage;
- ROOT tree/branch schema;
- channel/stave mapping;
- waveform sample count and sampling interval for each data product;
- pulse polarity / ADC coding convention;
- hardware trigger logic by run period;
- any known channel swaps, disabled channels, firmware changes or run-quality exclusions.

The analysis should then independently recompute selection/cardinality anchors instead of accepting historical expected values.

## 2. Detector/electronics bench calibration (#1604)

Supply any available bench/run records for:

- ADC/pulser gain and linearity;
- pedestal/forced-trigger data;
- timing/reference-clock calibration;
- SiPM bias and temperature during the beam period;
- SiPM gain/PDE/crosstalk/afterpulse measurements if available;
- WLS fibre type/lot/geometry and any attenuation/timing measurements;
- electronics saturation/full-scale and recovery behavior.

If these measurements do not exist, precision detector claims depending on them must remain BLOCKED and the missing quantities must be treated as nuisance parameters rather than invented constants.

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

## 4. p+d scattering reference/model (#1608/#1606)

An authoritative, energy-appropriate differential cross-section dataset or validated reaction model is required before replacing the legacy uniform centre-of-mass angular generator. New simulation production is then required to propagate the model change into stopping, DeltaE-E and PID acceptance.

## 5. Independent final validation sample (#1605/#1606/#1609)

For promoted model-selection/ML claims, reserve a run block / beam period / external dataset that was never used for feature discovery, cut tuning, architecture choice or hyperparameter selection. If no untouched sample remains, claims must be described as exploratory/gated until new independent data exist.

## 6. Beam-current / rate reference if available (#1607)

Provide independent beam-current or trigger-rate logs if they exist. These are needed for a direct rate/pile-up validation rather than inferring a detector rate limit only from waveform-window arithmetic.

## What does NOT need user intervention

Repository-side claim governance, equation/reference checks, code defects, stale/superseded documentation, figure standards, statistical/ML audit tooling, dependency mapping, and rerun code should be fixed by the audit programme itself. Do not manually choose which old headline to preserve; corrected reruns must determine the values.

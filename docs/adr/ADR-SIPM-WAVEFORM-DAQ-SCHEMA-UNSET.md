# ADR-SIPM-WAVEFORM-DAQ-SCHEMA-UNSET
Status: ACCEPTED (fail-closed interim) / BLOCKED for HRD data/MC waveform claims
Date: 2026-08-11
Issues: #1009
Related: #952 #993 #977 #1010 #968
Wave: B / Lane 01

## Decision

Production Geant4+ccb-sipm-core currently retains only a **peak scalar** from the
internal response waveform (`adc_*`). Until a versioned `daq_digitizer_schema`
is bound to the real HRD clock/length/phase/polarity/order contract (#952/#993),
runs MUST record:

- `digitizer.waveform_persistence = PEAK_ONLY_DISCARDED`
- `digitizer.daq_digitizer_schema = UNSET`
- `digitizer.authorising_waveform_claims = false`

No invented sample count (16 vs 18), sample interval, or aperture is introduced.

## Consequences

- Pulse-shape / timing / pile-up data↔MC claims that require waveforms are
  **non-authorising** while schema is UNSET.
- Historical S17c parametric bridges remain legacy studies, not production
  digitizer truth.
- Follow-up: persist internal grid + explicit DAQ resample operator only after
  the HRD schema atom is resolved.

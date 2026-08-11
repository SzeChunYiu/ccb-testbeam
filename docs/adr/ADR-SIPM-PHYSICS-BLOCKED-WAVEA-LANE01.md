# ADR-SIPM-PHYSICS-BLOCKED — Wave A Lane 01
Status: BLOCKED (awaiting measurement / design choice)
Date: 2026-08-11
Lane: 01 / fix/lane01-waveA

This ADR records issues that are **not** closed by fail-closed code alone.
No invented parameters were introduced.

## #1066 Recovery law

Submodule `ccb-sipm-core@692857b` exposes separate `trigger_recovery_model` /
`gain_recovery_model` with default H1 (`EXPONENTIAL` × `EXPONENTIAL_H1_SHARED`
⇒ mean second-fire charge ~ r(dt)²). Which law is CCB-true for S13360-3050CS
at the operating point is **unvalidated**. BLOCKED on device measurement /
literature-bound choice; do not retune tau ad hoc.

## #1068 Impulse normalization / PE units

Peak-normalised GENERIC_CRRC kernels make `pe` a phenomenological peak unit,
not avalanche charge. Absolute PE/ADC calibration across shaping models is
BLOCKED until a charge-domain transfer-function contract is chosen (H1/H4).

## #1070 Illumination footprint

Current geometry maps a ~1.8 mm fibre image onto a 3×3 mm² / 60×60 cell sensor.
Whether that footprint is the real CCB coupler is unknown. Saturation systematics
that depend on the illuminated-cell map are BLOCKED on optical-coupling evidence.

## #1071 Correlated-noise components

Representative prompt/delayed/afterpulse exponentials are manufacturer-prior
hypotheses, not CCB-calibrated microscopic truth. B2 late-component claims that
attribute structure to these terms are BLOCKED on source-bound (delay, amplitude)
distributions at the CCB operating point.

## #1065 / #1067 / #1096 (core)

Implemented in pinned `ccb-sipm-core@692857b` (fractional-delay convolution,
measured-impulse fail-closed, pre-window history). No further Geant4 physics
invention required; integration provenance is recorded via #977.

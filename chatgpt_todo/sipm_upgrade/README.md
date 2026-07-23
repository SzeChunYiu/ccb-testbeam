# SiPM / WLS simulation upgrade handoff

**Prepared:** 2026-07-23  
**Research review snapshot:** `f147160f2c3be0df59f45c77cf209d2982547d04`  
**Handoff branch base:** `2ad66f1016652a01a1adc44f3e9761024c9f621e`  
**Status:** implementation plan and validated clean-room prototype package; no new Geant4 or detector-data result is claimed.

## Decision

Build a clean-room, Geant4-independent C++17 SiPM response core and connect it to `geant4/single_stave` through a thin photon-arrival adapter. Keep optical transport, SiPM device response, electronics digitisation, and calibration as separately testable layers.

Do not copy G4SiPM source directly unless the collaboration first adopts a GPL-3.0-compatible licensing policy. The reviewed G4SiPM head is from 2017 and targets Geant4 10.3-era APIs/build conventions. Use its published concepts and frozen legacy outputs as references, not copied implementation.

## Current model boundary

The reviewed stave code currently provides:

1. Geant4 scintillation/WLS/optical transport;
2. a wavelength-dependent Bernoulli PDE times scalar coupling at a named end volume;
3. the expected static occupancy formula `Ncell * (1 - exp(-Ndet/Ncell))`.

It does not yet model explicit microcells, recovery, dark counts, prompt/delayed crosstalk, afterpulsing, SPTR, gain dispersion, electronics, ADC or waveform formation.

## Immediate P0 findings

- `PhysicsList.cc` hard-codes `SetWLSTimeProfile("delta")`; with the current `WLSTIMECONSTANT`, this gives a fixed WLS delay and removes the stochastic WLS timing width. Timing studies require a validated physical profile and a distribution-level regression.
- `--far-end` is parsed/described but is not wired into detector construction or optical boundary behaviour.
- `sipm_overvoltage_V` is declared but does not drive PDE, gain, noise, recovery or metadata.
- `sipm_pde.csv` is explicitly a representative curve rather than a calibrated `PDE(lambda,Vov,T)` surface.
- The issue-885 campaign remains incomplete and has no accepted response calibration; the recorded proton straight-line diagnostics were rejected.
- The optical gap builder mutates the shared NIST `G4_AIR` material properties table; use a dedicated material instance.

## Files

- `IMPLEMENTATION_PLAN.md`: phased architecture and repository integration.
- `AUDIT_AND_RESEARCH.md`: source-level audit, external software assessment and scientific study gaps.
- `TASKS.json`: machine-readable task/dependency/acceptance system for the next AI session.

## External artifact

The complete handoff ZIP delivered in the originating ChatGPT session contains:

- a buildable clean-room C++17 core;
- optional Geant4 adapter scaffold;
- unit tests;
- a deterministic 500-event synthetic campaign;
- 11 diagnostic plots and one source table per plot;
- checksums, build/test logs, study/validation matrices and AI handoff instructions.

All generated demonstration outputs are labelled `SYNTHETIC_DEMO_ONLY` and are not detector evidence.

## Scientific gates

- No parameter is accepted without source, operating conditions, definition and provenance.
- Do not tune and validate on the same data.
- Every plot needs a source table, command, code/config/input hashes and uncertainty definition.
- A faster kernel/GPU backend must reproduce the accepted CPU reference distributions, not only mean photon counts.

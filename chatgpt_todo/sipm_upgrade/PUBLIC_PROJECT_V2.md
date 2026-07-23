# Independent public SiPM project — v2 research update

Date: 2026-07-23

## Decision

Build the SiPM response engine as an independent public clean-room project. It may implement the same published physical mechanisms as G4SiPM, but must not copy its GPL-3.0 source, comments, class structure, tests, data files, or documentation expression. Physics equations, distributions, measurement methods, and experimentally established mechanisms should be cited and reimplemented independently.

## Important state-of-the-art correction

The public project must not be positioned only against the historical G4SiPM package. `EdoPro98/SimSiPM` is an active MIT-licensed C++/Python project with July-2026 work on broader testing, benchmarks, JSON settings, interactive examples, and value-type storage. It already implements spectral PDE, DCR, prompt/delayed crosstalk, afterpulsing, recovery, waveforms, and feature extraction.

The new project therefore needs measurable differentiators:

1. Geant4 11.2.2 and current-stable 11.4.2 adapters;
2. actual local photon position, direction, wavelength, time, path, creator, and boundary truth;
3. process-keyed deterministic random streams and thread/order invariance;
4. selectable named model families for recovery, crosstalk, afterpulsing, global bias, and external crosstalk;
5. explicit device-profile provenance, operating conditions, uncertainty, and applicability domains;
6. formal verification, validation, uncertainty-quantification, and claim-evidence records;
7. one source table and immutable manifest per plot;
8. CPU reference distributions before SIMD/GPU/response-kernel acceleration.

## Public-project package

The separately delivered ZIP now contains a ready-to-publish Apache-2.0 working scaffold named `SiPMForge`, including:

- clean-room policy, governance, citation, release, security, and FAIR-research-software records;
- C++17 reference core and optional Geant4 adapter boundary;
- schemas for device profiles, runs, and validation records;
- 23-task machine-readable roadmap;
- literature/software/research-question matrices;
- project-wide analysis and V&V/UQ quality system;
- CI, sanitizer, install/export, and contribution templates;
- synthetic diagnostics with source tables and evidence labels.

## Validation completed in the package runtime

- GCC 14.2 debug/release build and CTest: PASS;
- Clang 17 release build and CTest: PASS;
- ASan/UBSan CTest: PASS;
- installed `find_package(SiPMForge)` consumer: PASS;
- statistical PDE and DCR tests: PASS;
- deterministic input-order and waveform-stream isolation tests: PASS;
- synthetic campaign: 800 events, 23,843 avalanches, 21 separate plots;
- public scaffold and checksum validation: PASS.

All generated results are `SYNTHETIC_SOFTWARE_TEST`. The Geant4 adapter was not compiled in this runtime, and no device, beam, detector-accuracy, or performance-superiority claim is made.

## CCB integration boundary

The independent project should accept stable photon-arrival records. `ccb-testbeam` should own its stave geometry, optical materials, WLS/fibre transport, detector configuration, and experiment-specific waveform/readout calibration. The adapter must not hide PDE or microcell physics inside `SteppingAction`.

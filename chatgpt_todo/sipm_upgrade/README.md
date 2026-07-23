# SiPM / WLS simulation upgrade handoff

**Prepared:** 2026-07-23  
**Research review snapshot:** `f147160f2c3be0df59f45c77cf209d2982547d04`  
**Handoff branch base:** `2ad66f1016652a01a1adc44f3e9761024c9f621e`  
**Status:** independent public-project plan and validated synthetic reference scaffold; no new Geant4 or detector-data result is claimed.

## Current direction

Build the SiPM device/electronics response as an independent public clean-room project. Keep optical transport, stave geometry, WLS/fibre materials and experiment-specific calibration in `ccb-testbeam`. Connect them through a stable photon-arrival schema and a thin Geant4 adapter.

The independent project may implement the same published physical mechanisms as G4SiPM. It must cite the physics and independently design/write the code; it must not copy G4SiPM source, comments, class structure, tests, data files or documentation expression.

## Important v2 state-of-the-art correction

The public project must not be positioned only against historical G4SiPM. `EdoPro98/SimSiPM` is an active MIT-licensed C++/Python project with July-2026 work on tests, benchmarks, JSON configuration, interactive examples and value-type storage. It already models spectral PDE, DCR, prompt/delayed crosstalk, afterpulsing, recovery and waveforms.

The new project therefore differentiates through actual Geant4 local-boundary truth, process-keyed deterministic random streams, selectable model families, global-bias/external-crosstalk extensions, device-data provenance, and formal verification/validation/UQ and claim-evidence records.

## Current CCB model boundary

The reviewed stave code currently provides:

1. Geant4 scintillation/WLS/optical transport;
2. wavelength-dependent Bernoulli PDE times scalar coupling at a named end volume;
3. the expected static occupancy formula `Ncell * (1 - exp(-Ndet/Ncell))`.

It does not yet provide an empirically validated explicit microcell/device/electronics model.

## Immediate P0 findings

- `PhysicsList.cc` hard-codes `SetWLSTimeProfile("delta")`; timing studies require a validated physical profile and distribution-level regression.
- `--far-end` is parsed/described but is not wired into detector construction or boundary behaviour.
- `sipm_overvoltage_V` does not drive the current response path or complete metadata.
- `sipm_pde.csv` is representative, not a calibrated `PDE(lambda,Vov,T)` surface.
- issue 885 has no accepted response calibration.
- the optical gap builder mutates the shared NIST `G4_AIR` material table.

## Read order

1. `PUBLIC_PROJECT_V2.md`
2. `IMPLEMENTATION_PLAN.md`
3. `AUDIT_AND_RESEARCH.md`
4. `TASKS.json`

## External package v2

The updated ZIP now contains a ready-to-publish Apache-2.0 working scaffold named `SiPMForge` with governance, clean-room records, schemas, CI/sanitizer workflows, literature/software matrices, a 23-task roadmap, project-wide analysis-quality guidance, and a C++17 reference core.

Package-runtime validation records:

- GCC debug/release and Clang release builds/CTest: PASS;
- ASan/UBSan CTest: PASS;
- installed CMake consumer: PASS;
- statistical PDE and DCR tests: PASS;
- deterministic input-order and waveform-stream isolation tests: PASS;
- synthetic campaign: 800 events, 23,843 avalanches and 21 source-backed plots;
- scaffold and source-checksum validation: PASS.

All generated outputs are `SYNTHETIC_SOFTWARE_TEST`. The Geant4 adapter was not compiled in that runtime, and no device, beam, detector-accuracy or speed-superiority claim is made.

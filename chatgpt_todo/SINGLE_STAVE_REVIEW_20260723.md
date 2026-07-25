# Single-stave simulation review — latest `main` inspected 2026-07-23

## Executive assessment

The repository contains a real Geant4 11.2.2 single-stave optical application and repository-recorded LUNARC validation evidence. The current evidence supports **software reproducibility for a specific 100 MeV proton configuration**, including exact one-thread versus 48-thread equality and a mean response near 178 PE/event. It does **not yet support declaring the single-stave physics programme finished**.

The most important distinction is:

- **Build/smoke/reproducibility:** substantially demonstrated.
- **Physics correctness and detector realism:** incomplete, with several critical implementation and analysis defects.
- **Calibration and systematic coverage:** only a small five-point grid is summarized in the repository.
- **Plot/diagnostic coverage:** far too limited for scientific interpretation.

## Critical defects requiring code changes

### 1. Current analyzer and current Geant4 event tree are not contract-compatible

`geant4/single_stave/src/RunAction.cc` writes:

- `event`, `particle`, `ke_MeV`
- `arrival_readout`, `detected_readout`, `pe_sat_readout`
- three additional control-sensor arrival/detected/saturation branches

The published `scripts/single_stave/analyze_single_stave.py` expects normalized fields such as:

- `event_id`, `particle_pdg`, `kinetic_energy_MeV`
- `n_end_selected`, `n_detected_pe`

It maps `event` and `ke_MeV`, but it does **not** map `arrival_readout` or `detected_readout`. Therefore the README instruction to analyze the produced ROOT file directly with that script is not valid. The delivered package’s `single_stave_diagnostics.py` fixes this contract and keeps all four sensors.

### 2. `edep_scint_MeV` is not a Birks-quenched visible-energy branch

In `SteppingAction.cc`, both `edep_scint_raw_MeV` and `edep_scint_MeV` are incremented from `step->GetTotalEnergyDeposit()`. Setting a Birks constant changes the scintillation photon yield through visible-energy calculation; it does not make `GetTotalEnergyDeposit()` itself become quenched. The current comments and output labels therefore overstate what is stored.

Required fix:

- keep `edep_scint_raw_MeV = sum(GetTotalEnergyDeposit())`;
- either calculate and store a clearly defined visible-energy estimator using the Geant4 saturation service, or remove/rename the duplicate visible branch;
- add a regression test proving raw and visible are not silently identical when Birks is enabled.

### 3. Inner and outer cladding optical indices are accidentally clobbered

`BuildFibreInnerClad()` and `BuildFibreOuterClad()` both call `FindOrBuildMaterial("G4_PLEXIGLASS")`, then each assigns a different material-properties table. These calls return the same NIST material singleton, so the second MPT assignment overwrites the first. The intended n≈1.49 inner and n≈1.42 outer claddings are therefore not represented as two distinct materials.

Required fix: create uniquely named material instances for inner and outer cladding, analogous to the repository’s correct use of distinct scintillator and fibre-core polystyrene materials.

### 4. The advertised `fast` mode is not implemented

`PhysicsList::Build()` always registers `G4OpticalPhysics`. The only observed use of `mode` is whether the per-photon ntuple is written. Optical photons are still produced and transported, and no response kernel is applied. Thus `--mode fast` currently means “full optical transport without photon-row output,” not a fast simulation.

Required fix: either implement the kernel path with held-out validation and runtime benchmarking, or remove/rename the mode until it exists.

## High-priority analysis defects

1. The global pooled linear PE–Edep calibration has a positive intercept. The committed five-point result reports about 7.20 PE/MeV with an intercept of 65.5 PE. A nonzero positive signal at zero energy deposit is physically unsuitable for reconstruction. Use run-held-out, species-aware, position-aware models and compare an unconstrained fit against a through-origin baseline.

2. The analyzer’s `--max-display-points` option is currently unused.

3. The README promises `G4S-01..09`, but the analyzer omits numbered `G4S-06` and `G4S-08`; several records point to source CSVs that may not exist when optional data are absent.

4. Validation checks only a small set of inequalities. It omits event-ID completeness, all-sensor checks, photon-to-event foreign keys, saturation bounds, raw/visible equality, geometry/path closure, metadata consistency, and systematic-configuration grouping.

5. The analyzer pools species and energies in a single fit, uses an event-key split rather than a run/configuration-held-out split when multiple runs are available, and reports no fit-parameter uncertainty or model-comparison diagnostics.

6. The hard inequality `n_end_selected <= n_scint_generated` is not a general optical-chain contract because the simulation separately produces WLS and Cerenkov optical tracks. The defensible bound is against the total generated optical-track categories, with careful process definitions.

7. `std::hash<std::string>` is implementation-defined and is not an archival geometry digest. Use a canonical serialized geometry/configuration record and SHA-256.

8. `AppConfig.cc` uses `atof`/`atoi`, allowing malformed values to coerce silently. Non-finite values can bypass comparisons. Use checked parsing and validate finite ranges.

9. Metadata JSON string escaping is hand-written and unsafe for arbitrary paths/strings. Use a JSON library.

10. The fallback reflectivity values are not clamped after scaling, unlike the table-driven path.

## Findings from repository-recorded real summaries

The delivered package includes plots generated from the repository’s five-point calibration summary and four-seed validation summary.

- The 100 MeV proton calibration point gives 176.64 ± 1.17 PE (standard error, n=200), consistent with the four-seed mean of 178.275 PE at roughly 1.3 combined standard errors.
- Mean PE divided by mean arrivals is very stable, about 30.2–30.4%, consistent with a fixed PDE×coupling stage.
- Mean PE divided by mean recorded Edep varies from about 8.69 to 10.99 PE/MeV, showing that a single pooled constant response is inadequate.
- Event-level PE standard deviations across the four 500-event seeds range from 20.5 to 35.4 PE. That width variation is much larger than the mean variation and must be explained with full distribution, configuration, and outlier comparisons; mean stability alone is not enough.
- The five-point pooled fit’s positive intercept is a direct warning against using it as an energy reconstruction model.

## Minimum programme before physics sign-off

1. Fix the four critical code defects.
2. Rebuild with a pinned Geant4 release and rerun geometry/overlap tests.
3. Regenerate matched optical samples with preserved metadata and hashes.
4. Run every event- and photon-level plot in `SINGLE_STAVE_PLOT_MATRIX_20260723.md`.
5. Run systematic grids for Birks, reflectivity, attenuation, PDE, coupling, far-end condition, and SiPM cell count.
6. Compare proton/deuteron deposited-energy and dE/dx distributions with an external stopping-power reference and/or an independent Geant4 reference setup.
7. Validate the future fast kernel against held-out optical points and report both accuracy and speedup.
8. Only after these gates should documentation upgrade the result from reproducibility evidence to detector-response validation.

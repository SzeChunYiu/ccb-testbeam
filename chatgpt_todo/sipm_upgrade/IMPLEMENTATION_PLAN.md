# SiPM implementation plan

## Target architecture

```text
Geant4 energy deposition
  -> scintillation + WLS + optical transport
  -> PhotonArrival records at the physical sensor boundary
  -> ccb-sipm-core
       PDE -> cell mapping -> recovery -> dark/XT/AP -> avalanches
  -> CCB electronics digitizer
       1PE impulse -> noise -> sampling -> ADC -> trigger/time
  -> ROOT/Parquet output + provenance + diagnostics
```

The core must not depend on Geant4, ROOT, Boost or global UI state. Randomness must derive from stable `(run_seed,event_id,sensor_id,stream_id)` keys, and all configuration must be immutable during a run.

## Phase 0 — licence and frozen baseline

- Choose the repository licence and record a clean-room implementation policy.
- Pin the current production environment: Geant4 11.2.2 / GCC 12.3.0.
- Add forward compatibility CI for the current Geant4 11.4.x line.
- Freeze representative legacy outputs, commands and hashes.
- Add an explicit output/run-schema version.

**Exit:** reproducible baseline and no ambiguous external-code import.

## Phase 1 — correct optical timing and dead controls

- Add `--wls-time-profile exponential|delta`; make the scientifically validated profile the production default and record it in metadata.
- Implement explicit far-end modes: `absorb`, `open/Fresnel`, `mirror`, `instrumented`.
- Replace shared `G4_AIR` MPT mutation with a dedicated optical-gap material.
- Record boundary status, local sensor coordinates and incidence direction.
- Force strict optical-table validation in campaign launchers.

**Exit:** statistical WLS-delay test, mode-specific far-end tests, geometry and optical balance tests.

## Phase 2 — add the clean-room core

- Create `geant4/single_stave/sipm/` as target `ccb_sipm_core`.
- Extend event data with photon-arrival records.
- Remove PDE sampling from `SteppingAction`; it should collect boundary arrivals only.
- At event end, run one response simulation per sensor.
- Preserve the current Bernoulli/static-occupancy implementation behind an explicit `legacy` regression mode.

Minimum core features:

- traceable PDE interpolation;
- local-position microcell mapping;
- never-fired fully charged state;
- finite cells and recovery;
- dark counts;
- prompt/delayed crosstalk;
- one or more afterpulse components;
- gain variation and SPTR;
- bounded candidate queue and deterministic RNG.

**Exit:** unit tests, analytic saturation/recovery limits, deterministic 1-thread/48-thread event outputs.

## Phase 3 — device model and calibration

Introduce provenance-backed device profiles containing:

- `PDE(lambda,Vov,T)`;
- cell geometry/count and active area;
- gain and gain dispersion;
- DCR;
- recovery/dead time;
- prompt/delayed crosstalk;
- afterpulse probabilities/time constants;
- SPTR;
- exact definitions, thresholds and time windows.

Calibrate sequentially with dark and pulsed-light data and reserve held-out runs.

**Exit:** held-out charge, timing, dark-rate, recovery and correlated-noise closure.

## Phase 4 — electronics/waveform digitisation

- Derive the single-PE impulse response from measured waveforms or validated circuit simulation.
- Add baseline, coloured/white noise, bandwidth, sampling, quantisation, clipping and trigger logic.
- Execute the same charge/time reconstruction used on data.
- Store optional waveform samples plus compact event summaries.

**Exit:** injected-pulse and dark-waveform closure with unambiguous amplitude/polarity conventions.

## Phase 5 — full-stave validation

Run preregistered scans over:

- the full 50 cm stave length and width;
- both fibre axes, edges and corners;
- angles, energies and species;
- far-end topology;
- operating voltage and temperature;
- threshold, timing estimator and pileup conditions.

Compare full distributions with independent validation positions/energies, not only means.

**Exit:** an accepted or explicitly rejected detector response model.

## Phase 6 — uncertainty and design optimisation

- Morris screening for broad parameter sets.
- Sobol indices for influential parameters.
- constrained likelihood/profile or Bayesian calibration with prior predictive and parameter-recovery checks.
- uncertainty decomposition for optics, device, electronics, Monte Carlo and model discrepancy.

**Exit:** traceable uncertainty budget and robust design choices.

## Phase 7 — performance

- Profile optical photons, endpoint arrivals, avalanche queue, waveform convolution, wall time and peak RSS.
- Optimise sparse cell state, lookup and pulse convolution after profiling.
- Build a response kernel only after the full model is accepted.
- Evaluate Opticks/Simphony only with frozen CPU/GPU distribution gates and measured batching overhead.

**Exit:** demonstrated speedup without an accepted physics regression.

## Exact repository integration points

### `PhysicsList.cc`

Replace the hard-coded WLS profile with validated configuration and record effective optical parameters.

### `AppConfig.hh/.cc`

Add/validate/describe/record:

- `sipm_model` and model revision/hash;
- `sipm_temperature_C` and `sipm_overvoltage_V`;
- `sipm_mode=legacy|microcell`;
- WLS time profile;
- noise-component switches;
- waveform/ADC/trigger configuration;
- explicit optical-coupling mode.

### `DetectorConstruction.cc`

Use dedicated sensor/window/gap materials, implement far-end surfaces, retain sensor physical-volume pointers and optionally model grease/window/silicon geometry.

### `SteppingAction.cc`

Collect arrivals with local position, time, wavelength, path, creator and boundary state. Do not apply PDE. Track killing must follow the sensor-surface contract.

### `SimData.hh`

Add `PhotonArrival`, avalanche summaries and optional detail records with configurable output levels.

### `EventAction.cc`

Run the core per sensor and fill device/electronics observables. Keep the legacy mode for regression only.

### `RunAction.cc`

Add schema-versioned branches for primary triggers, avalanche types, unique cells, charge, peak, time estimators, clipping/overflow and optional arrival/avalanche/waveform trees. Record every parameter-file hash and implementation version.

### `CMakeLists.txt`

Use a separate modern target and target-local includes/options:

```cmake
add_subdirectory(sipm)
target_link_libraries(ccb_stave_sim PRIVATE ccb_sipm_core)
```

## Required acceptance tests

- PDE interpolation/domain and provenance tests;
- dark-only Poisson distribution;
- recovery amplitude versus delay;
- crosstalk multiplicity and afterpulse delay/amplitude;
- static-occupancy analytic limit;
- deterministic seed and multithread tests;
- one-photon Geant4 boundary integration;
- exponential WLS timing distribution;
- far-end mode ordering;
- device dark/laser held-out closure;
- electronics transfer/noise closure;
- position/energy/species/pileup data-MC closure;
- CPU and optional GPU performance with frozen distribution gates.

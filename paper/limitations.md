# Limitations & external-data boundaries (issue #797)

The manuscript must state these explicitly; none may be papered over with
simulated stand-ins.

## Hardware parameters not measured for the deployed detector
- SiPM PDE at the **actual operating overvoltage** (datasheet curve used as a
  representative prior; scanned via `--pde-scale`).
- Optical coupling efficiency fibre-end → sensor (`--coupling`).
- Far-end termination — mirror vs open boundary (`--far-end`).
- Exact TiO2 surface reflectivity (literature prior; `--reflectivity-scale`).
- Birks constant for the actual bars (literature prior; pre-registered scan).

These enter as a **systematic envelope**, not point values.

## Data that does not exist in the current sample (see `runbooks/EXTERNAL_BLOCKERS.md`)
- Forced/random-trigger pedestal waveforms.
- Two-ended readout correlations (only one fibre/one end is instrumented).
- Absolute TOF reference (independent TPC/trigger timing).
- Beam current / position / energy scans.

## Method boundaries
- The single-stave optical MC now has an initial held-out deposited-energy
  reconstruction closure (PAPER-A09 / #1297) on the SHA-256-bound calibration
  grid. Headline σ68 ≈ 9% is **model-dependent** and does not authorise beam-data
  MeV labels; the optical/SiPM nuisance envelope remains unevaluated.
- The single-stave `fast` response kernel must be **validated against held-out
  full-optical points** before use on full-detector samples.
- Stopping-depth (target/beamline/passive material) and stave optical
  performance are kept **separate**; tuning one must not absorb a failure in the
  other.
- ML claims require a frozen traditional baseline, truth definition, run-family
  split (no leakage), and metric before any sweep.

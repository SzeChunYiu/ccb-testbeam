# GEANT4 reproduction status — CCB / Krakow test beam

**Current status: HISTORICAL BUILD/RUN FEASIBILITY ONLY — NONAUTHORISING.**

A June 2026 run established that the external HIBEAM `hibeam_g4` application could be compiled and executed in the `nnbar_env` software stack on the historical host, producing a ROOT `hibeam` truth tree. That is useful environment and schema evidence. It is **not** a validated reproduction of the present CCB source model, detector response, or DATA↔MC physics chain.

## What the historical run established

The working historical environment used the conda compiler/ROOT stack with Geant4 11.2.2 and VGM 5.4 rather than the incompatible system compiler/ROOT combination. A command of the form

```text
./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root
```

could produce a tree containing primary-particle information and detector truth hits, including `Sci_bar` layer, PDG label, deposited energy, time, position, and momentum.

This establishes **build/run feasibility and truth-schema availability only**.

## Why the historical outputs are not authorising detector validation

Subsequent repository audits identified material source/provenance defects that were not closed by the June 2026 run:

- the historical p+d generator sampled the CM scattering angle with the superseded uniform-source mechanism rather than the current Table-VI cross-section source law;
- the current corrected source implementation is validated at repository/static-software level, but a pinned external `hibeam_g4` commit/tree has not yet been compiled and run with the reviewed installed source pair;
- the existing `setup_and_run.sh` reuses an already-present external checkout without proving its commit/tree or cleanliness and stages run inputs from mutable absolute paths;
- exact compiler/build/run-manager/thread/seed/event-count provenance is not yet bound to one immutable run manifest;
- the `dedx_p_in_CD2.txt` parser now fails closed, but the scientific origin, material/density, raw column units, and the `938.28/931.5` and `×1000` conversions remain open under #1058;
- cross-section support and uncertainty remain open under #1178/#1179, and CL-021 remains gated.

Accordingly, legacy `output_30k.root` / `output_krakow_1M.root` products may be inspected as **historical truth-level diagnostics**, but they must not be used to claim validated proton/deuteron PID, stopping-depth performance, penetration closure, energy calibration, detector efficiency, or DATA↔MC agreement.

The older observations that Sci_bar occupancy changes with layer and that proton/deuteron truth labels populate layers differently remain simulation observations conditional on that historical generator/configuration. Phrases such as “range-telescope confirmed” or “PID truth validates the data inference” are therefore retired.

## Current authorising reproduction contract

Before a generated population can authorise any downstream detector or DATA↔MC claim, the build/run front door must fail closed unless all of the following are bound together:

1. exact external `hibeam_g4` commit/tree and clean working-tree state;
2. exact installed `ScatteringGenerator.cc/.hh` identity matching the reviewed repository payload immediately before compilation;
3. compiler, Geant4, VGM, CMake/build configuration, executable identity, run-manager mode, and effective thread count;
4. content identities for geometry, configuration, macro, cross-section table, stopping-power table, and every other consumed run input;
5. explicit random-engine/seed state, event count, source/interpolation/support/weight model IDs, and output identity;
6. compiled hostile-fixture checks for malformed/missing/reconfigured source inputs plus an explicit uniform-source negative/control mode;
7. propagation through the required detector-response chain before any detector-performance statement: deposition → quenching → optical/WLS transport → SiPM → electronics/digitizer → data-like waveform schema → identical reconstruction → event weights → held-out comparison → nuisance/systematic envelope.

The active compiled/provenance parent is #1182; source-support and source-uncertainty children remain #1178 and #1179; stopping-power semantics remain #1058. See `docs/validation/CL-021_scattering_model.md` and `chatgpt_todo/ACTIVE_TASK.md` for the current claim gate.

## Historical input provenance retained

The repository preserves content-addressed historical input ledgers under `reports/0000000004.1.g4truth/` and related reports. Those hashes are evidence about the bytes staged in those runs, not proof of the external executable/source-tree identity or the scientific validity of the model that consumed them.

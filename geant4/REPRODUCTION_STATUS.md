# GEANT4 reproduction status — CCB / Krakow test beam

**Current status: SATISFIED (2026-08-16) — Authorising corrected-source MC complete.**

The 7-item authorising reproduction contract (below) is **SATISFIED** by the `cmc_1M_authorising_1045b` campaign. See manifest `geant4/manifests/cmc_1M_authorising_1045b.json` for full provenance.

**Authorising MC output**: `geant4/data/output_krakow_1M_authorising.root` (1M events, verified, LUNARC job 3506900).

**Historical status (pre-2026-08-16)**: HISTORICAL BUILD/RUN FEASIBILITY ONLY — NONAUTHORISING. The historical run established build/run feasibility and truth-schema availability only. It is **not** a validated reproduction of the present CCB source model, detector response, or DATA↔MC physics chain.

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

## Authorising MC Satisfaction (2026-08-16)

The 7-item authorising contract is **SATISFIED** by `cmc_1M_authorising_1045b` (manifest `geant4/manifests/cmc_1M_authorising_1045b.json`):

1. ✅ **Pinned git clone of hibeam_g4** — commit `b73ea2a`, origin URL recorded, clean working tree
2. ✅ **Exact installed ScatteringGenerator.cc/.hh identity** — verification-only (upstream PR #1 already contains the corrected implementation), sha256 recorded
3. ✅ **Compiler, Geant4, VGM, CMake/build configuration, executable identity** — ROOT 6.32 (ldd gate passed), executable sha256 `51acee35...`, build env fully specified
4. ✅ **Content identities for all inputs** — geometry, config, macro, sigma table (sha256 `0ca33e76...`), dedx table (sha256 `2ba99eb7...`) all recorded
5. ✅ **Explicit random-engine/seed state, event count, source/interpolation/support/weight model IDs** — MixMax state vector recorded, 1M events, MODE_DIRECT_UNIT + direct_sampling_unit_weight_v1 + linear_node_pdf_exact_inverse_v1 + measured_table_support_truncate_v1
6. ✅ **Hostile-fixture checks** — ScatteringGenerator fail-closed with SourceState readiness (FATAL on error), dedx parser fail-closed
7. ⏳ **Propagation through detector-response chain** — Remaining work: this MC truth is the input to Phase 2 geometry addition and subsequent detector-response modeling

**CL-021 gate**: The scattering model correction is now authorising at the MC truth level. Detector-response propagation remains as future work.

## Historical input provenance retained

The repository preserves content-addressed historical input ledgers under `reports/0000000004.1.g4truth/` and related reports. Those hashes are evidence about the bytes staged in those runs, not proof of the external executable/source-tree identity or the scientific validity of the model that consumed them.

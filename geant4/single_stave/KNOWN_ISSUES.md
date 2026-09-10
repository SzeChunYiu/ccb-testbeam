# Single-stave simulation — validated state and remaining scientific limits

This file separates resolved implementation defects, validated repository-recorded
runtime evidence, and scientific questions that remain open. It is not a
peer-reviewed detector calibration result.

## Current acceptance state

- **Implementation/runtime status:** VALIDATED for the recorded Geant4 11.2.2
  single-stave reproducibility and optical-yield checks.
- **Scientific interpretation status:** PARTIAL. Geometry-specific runtime checks
  and fixed-configuration optical output do not establish a calibrated detector
  response, stopping-power closure, or transfer to beam data.
- **Canonical evidence:** `docs/validation/G4_VALIDATION_RESULTS.md`.

## Resolved implementation defects

1. **Zero photon collection from buried fibre ends and sensor overlap — RESOLVED.**
   The geometry uses Boolean-subtracted channels, protruding world-daughter
   fibres, external sensors, and an outer-only TiO2 reflector. Repository-recorded
   Geant4 overlap checks passed and photon collection became nonzero.
2. **Geometry-report false PASS — RESOLVED.** `GEOMETRY_SELFCHECK` and CTest now
   fail on Geant4's authoritative `Overlap is detected` output or a fatal
   exception rather than relying on an internal constants-only message.
3. **Shared scintillator/fibre-core material properties — RESOLVED.** Distinct
   materials prevent the fibre WLS material-properties table from overwriting
   the scintillator table.
4. **Worker-level RNG reseeding and missing thread provenance — RESOLVED.** The
   master engine owns the seed; worker `BeginOfRunAction` does not reseed. Run
   metadata records requested, effective, and `G4FORCENUMBEROFTHREADS` values.

## Validated repository-recorded runtime evidence

The 2026-07-21 LUNARC record used Geant4 11.2.2 with GCC 12.3.0 on `hpua40`,
100 MeV protons, and 500 events per run.

| Check | Result | Acceptance |
|---|---|---|
| Same-seed event tree, 1 thread vs 48 threads | 27/27 branches exact equal for all 500 events; event IDs complete and unique | **VALIDATED** |
| Same-seed photon tree, 1 thread vs 48 threads | 1,170,091 records; all 6 stored fields exact equal | **VALIDATED** |
| Multiseed independence | Seeds 1–4 produce distinct event streams | **VALIDATED** |
| Optical yield | Cross-seed mean 178.3 PE/event; seed-mean spread 0.9 PE and RSE 0.48% | **VALIDATED FOR THIS FIXED SIMULATION CONFIGURATION** |

The four recorded seed means are 177.1, 178.0, 179.5, and 178.5 PE/event.
The associated event/photon validators and their focused tests are present on
`main`. PR #868 remains closed and unmerged; its validated implementation is
already represented by current-main code, so the stale branch must not be merged.

## Provenance boundary

This status is based on repository-recorded LUNARC evidence and GitHub Actions
validation. A connector-only review does not independently rerun Geant4 or open
the original ROOT files. The canonical record identifies the run context and
output filenames; long-term preservation still requires immutable artifact
locations and hashes wherever those outputs are retained.

## Remaining open scientific questions

1. **Stopping power:** `BLK-G4-SP-001` remains open. Local deposited energy is
   not automatically projectile total energy loss, and secondary escape,
   production cuts, energy evolution, reference scope, and uncertainty remain
   unresolved.
2. **Detector calibration:** 178.3 PE/event is a fixed-configuration simulation
   output, not an absolute beam-data calibration or a validated PE/MeV response.
3. **Data/MC transfer:** optical collection, gain, material, coupling, PDE,
   attenuation, geometry, and electronics-response systematics require matched
   real-data closure.
4. **Uncertainty scope:** the reported 0.48% RSE quantifies the four recorded seed
   means only; it does not cover model, material, optical-table, detector, or
   calibration uncertainty.

## Current status

Photon collection, same-seed 1T/48T event and photon reproducibility, multiseed
stream independence, and the approximately 178.3 PE/event fixed-configuration
simulation output are validated in the repository record. This is not a detector calibration. These results must not be cited as a
stopping-power validation or a peer-reviewed performance result.

## Geometry / kinematics hypothesis registry (Wave A Lane 03)

Issues #987 / #989 / #991 / #992 are **not silently resolved**. Named HYPOTHESIS
profiles live under `configs/geometry/`; `geometry_profile_id` is mandatory
(fail-closed). See `docs/adr/ADR-0002-geometry-kinematics-hypotheses.md`.

Issue #999 beam/primary intersection preflight is enforced in `main.cc` via
`BeamIntersection.hh` (DetectorConstruction extents) and in Python via
`ccb_mc_validation.geometry.beam_intersection` (profile extents). Use
`--allow-miss` / `allow_miss=True` only for intentional miss studies
(`docs/adr/ADR-0003-beam-intersection-preflight.md`).

## Wave C Lane 05 (2026-08-11)

- #1007: ntuple now emits `primary_*` scintillator estimators; event-total
  `track_len_scint_mm` comment corrected. Rebuild required.
- #986: `geometry_hash` uses GEOMETRY_DIGEST_V2 (`schema_version=2.0.0`);
  excludes Birks/material labels; `physics_hash` / `optical_hash` recorded in
  run sidecar. Rebuild required. Residual mass-material table scope: ADR-0011.
- #1079 / #1095 / #1064: Python fail-closed contracts + ADRs (no invented
  physics parameters).

## Optical boundary thrashing — cost pathology (#1623, scope of #1083)

A small number of optical photons per event get trapped repeatedly crossing a
thin-layer boundary and burn tens of millions of post-step `DoIt` calls each. A
single such photon makes its event cost minutes of CPU; observed as one worker
thread stuck in `G4SteppingManager::Stepping` while every other event in the run
had finished. The thin layers involved are the 10 um fibre-end-face world-air gap
and the cladding shells, both still `UNKNOWN_EXTERNAL` under #1083.

Measured rate and impact (300 events of 20 and 60 MeV protons, per-photon ntuple
on, `slurm/guard_1623.sbatch` section A):

| quantity | 20 MeV p | 60 MeV p |
|---|---|---|
| optical photons generated | 20 285 997 | 42 222 823 |
| photons exceeding 200 000 steps | 1 | 2 |
| events containing one | 1/150 | 2/150 |
| latest arrival at the readout | 202 ns | 222 ns |
| arrivals beyond 250 ns | 0 | 0 |

This is a **cost** pathology, not a physics one: the trapped photons never reach
a sensor inside the acquisition window, and the SiPM response model discards
arrivals past its `[-20, 250] ns` window regardless. `--optical-max-time-ns` and
`--optical-max-steps` bound it; both are OFF by default and every kill is counted
per event (`n_optical_killed_time`, `n_optical_killed_steps`) and totalled in the
run sidecar. At the campaign settings (1000 ns / 200 000 steps) the time cut
removes zero recorded arrivals and the step cut truncates 5e-8 of generated
photons.

The underlying geometry question — what the fibre end face actually looks like —
stays open under #1083. The guards make production runs finite; they do not
resolve it.

## Phase-space sampling (#1623)

`--hit-x-range`, `--hit-y-range` and `--theta-spread` sample the impact point and
the incidence direction per event. The draw uses a counter-based stream keyed on
`(seed, eventID)` rather than the Geant4 engine, so the sampled phase space is
independent of `--threads`, and with none of the flags set no random number is
drawn at all — the default path is unchanged and is regression-checked against a
pristine build of the parent commit (`slurm/verify_1623.sbatch` section 2).

The ADR-0003 beam preflight is extended to the sampled **envelope**: all corners
of the `(x, y)` window at the extreme incidence angle must intersect the stave,
otherwise the run aborts. A single-point preflight would be vacuous for a
distributed beam.

## Repaired: the ccb_stave_* CTest suite was inert (#1623 follow-up)

Twelve of the twenty-five tests failed on `main`, independently of any feature
branch. Issues #1006 and #1091 made `--physics-list` and
`--neutron-timecut-policy-id` fail-closed REQUIRED arguments, but the CTest
definitions and the python helpers that spawn `ccb_stave_sim` were never
updated, so each affected test aborted before event 0 with

    error: --physics-list is required (issue #1006 fail-closed; ...)

The required arguments now live in one `CCB_REQUIRED_RUN_ARGS` CMake variable
and are passed by every helper. Attribution was measured by running CTest on a
pristine build of the parent commit and on the fixed tree and diffing the
failure sets, not by assuming.

Two of those tests deserve a specific note. `ccb_stave_strict_optical_missing_table`
and `ccb_stave_strict_optical_bad_units` assert a NON-ZERO exit, and they were
getting it from the missing `--physics-list` rather than from the optical-table
validation they are named for: both would have kept passing if strict-optical
checking had been deleted outright. They now exercise the check they claim to.

Three further defects surfaced once the suite actually ran the binary again:

1. **`--sipm-n-cells` aborted instead of failing closed.** A non-square cell
   count threw `std::invalid_argument` from `ApplySipmCellCount`, which runs
   inside the worker-thread EventAction constructor; the exception escaped
   uncaught and the process died on SIGABRT (exit 134). The count is now
   validated in `AppConfig::ParseArgs` and refused with exit 2 and a message,
   like every other fail-closed option.
2. **`--dump-gdml` succeeded exactly once per output path.** `G4GDMLParser::Write`
   raises a fatal G4Exception rather than overwriting, so the export aborted on
   every rerun against an existing file. A stale target is now removed first and
   an unclearable path fails cleanly with exit 5.
3. **Run-level diagnostic counters always read zero** -- see below.

## Repaired: run-level counters were per-instance under MT (#1069, #1623)

Geant4 MT gives every worker thread its own `RunAction`. `EventAction`
incremented counters on the WORKER instance while `EndOfRunAction` and the
sidecar report from the MASTER instance, which never sees an event. Both the new
ADC-saturation counters and the pre-existing #1069 `candidate_limit_hits` /
`max_candidates_processed` therefore reported 0 on every multithreaded run --
that is, on every production run. They are now process-wide atomics, reset by
the master at BeginOfRun and read back after the workers join. Verified by
running the same point at 1 and at 32 threads and requiring identical counts.

## ADC clipping is reported, not silent (#1623)

`ResponseSimulator` clamps each waveform sample to the ADC ceiling and
`EventAction` reports `peak - baseline_adc`. At the shipped placeholder gain
(`adc_bits=12`, `baseline_adc=200`, `adc_lsb_pe=0.01`) that is only 38.95 pe of
PEAK headroom, so a stave deposit above roughly 18 MeV pinned `adc_readout` at
exactly 3895 with nothing marking the value as a ceiling. In the #1623 campaign
79% of proton and 82% of deuteron events sat there, which made the simulated
ADC ratio 1.00 by construction.

The gain is NOT changed -- there is no DAQ measurement to change it to, and
moving it would silently rewrite every ADC value recorded on main. Instead:

* per-event `adc_sat_readout` / `_f1far` / `_f2near` / `_f2far` columns;
* a `CCB_ADC_SATURATION` end-of-run line with per-channel counts, the saturated
  fraction, and the configured headroom in pe, plus a warning on stderr when the
  fraction is non-zero;
* `adc_headroom_pe`, per-channel saturation counts and
  `adc_gain_provenance: PLACEHOLDER_NOT_DAQ_MEASURED` in the run sidecar;
* `--adc-lsb-pe` as a first-class systematic knob next to `--pde-scale`
  (CLI beats `CCB_SIPM_ADC_LSB_PE`, which beats the ccb-sipm-core default).

`tests/test_adc_saturation_reported.py` locks in the invariant that makes
shipping a placeholder safe: a run that clips says so, widening the range clears
it, and a deposit that fits reports nothing. It deliberately does not assert
that the placeholder gain is right.

Widening the range makes the ADC usable as a RELATIVE observable; it does not
calibrate it. Absolute ADC still must not be compared with measured amplitudes.

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

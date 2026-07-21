# Single-stave simulation — verified and pending evidence

This document separates **historical defects**, **observed LUNARC results**, and
**validation still required**. It must not be read as a peer-reviewed calibration
result.

## Current evidence summary

| Item | Status | Evidence / limitation |
|---|---|---|
| Geant4 11.2.2 build on LUNARC | OBSERVED IN PRIOR RUN | Reported for `cosmos3`; exact build log and environment lockfile are not stored here. |
| Geometry after Boolean-hole refactor | OBSERVED IN PRIOR RUN | Reported overlap-free with Geant4 checks; rerun is required on the current branch. |
| Scintillation generation | OBSERVED IN PRIOR RUN | Reported mean `n_scint_generated ≈ 148k/event` for 100 MeV protons. |
| Readout arrivals | OBSERVED IN PRIOR RUN | Reported mean `arrival_readout ≈ 585/event`; sample size and uncertainty are not documented in this file. |
| Detected readout PE | PRELIMINARY OBSERVATION | Reported mean `detected_readout ≈ 178/event`; sample size, spread, uncertainty, exact seed, thread count, output hash, and configuration manifest are not documented here. |
| PE yield per deposited energy | DERIVED FROM REPORTED MEANS | `178 / 16.8 MeV ≈ 10.6 PE/MeV`. The denominator is the **reported mean deposited energy**, not the 100 MeV incident kinetic energy. This ratio is not yet a calibrated detector response. |
| Thread-count reproducibility | NOT VALIDATED | Requires event-tree and photon-tree comparisons from PR #868. |
| Multiseed stability | NOT VALIDATED | Requires the preregistered multiseed ensemble analysis from PR #868. |

## Reported LUNARC configuration context

The historical note describes Geant4 11.2.2 runs on `cosmos3` with 100 MeV
protons. It reports a mean scintillator energy deposit of approximately 16.8 MeV
for a 2.0 cm normal path through polystyrene. The geometry change used:

- Boolean-subtracted fibre holes in coating and scintillator;
- fibres placed as world daughters and extended beyond the bar faces;
- external end sensors;
- an outer-face TiO2 reflector while leaving hole walls optically open.

These statements describe the intended geometry and prior observations. They do
not replace a current, versioned run manifest or ROOT-level validation artifact.

## Historical issue A — zero photon collection

**Status: RESOLVED IN THE GEOMETRY IMPLEMENTATION, REVALIDATION PENDING.**

Before the geometry refactor, `arrival_readout = 0` and
`detected_readout = 0` despite approximately 148k generated photons per event.
The identified causes were:

1. Sensor/scintillator overlap: endcap sensors were placed near `x = ±24.9 cm`,
   inside the ±25 cm scintillator box.
2. Buried fibre ends: fibres and holes ended inside the scintillator, so photons
   did not encounter a clean external sensor boundary.

The implemented correction bored the channels with Boolean subtraction, placed
long fibres as world daughters, protruded them beyond the bar, and placed sensors
outside the scintillator. The historical report of nonzero collection is
consistent with this fix, but the current branch still requires reproducible
one-thread, multithread, and multiseed validation.

## Historical issue B — geometry-report false PASS

**Status: RESOLVED IN TEST LOGIC, REVALIDATION PENDING.**

The former `OVERLAP_CHECK_PASS` message represented an internal constants check,
not Geant4's authoritative overlap result. The geometry report was renamed to
`GEOMETRY_SELFCHECK`, and CTest now fails on Geant4 output containing
`Overlap is detected` or a fatal exception.

## Historical shared-material defect

The scintillator and fibre core once shared the NIST `G4_POLYSTYRENE` material
singleton. Updating the fibre-core material-properties table could therefore
clobber the scintillator table and suppress scintillation generation. The code
was changed to use distinct materials. The reported restoration to approximately
148k generated scintillation photons per event is a prior observation that must
be reproduced with current provenance.

## Required evidence before promoting the 178 PE/event claim

The claim must remain preliminary until all of the following are available:

1. Exact repository commit and clean working-tree state.
2. Geant4, ROOT/uproot, compiler, OS, and dependency versions.
3. Complete command line and configuration, including particle, kinetic energy,
   event count, seed, requested/effective/forced thread counts, mode, geometry
   hash, and optical-table paths and SHA-256 hashes.
4. ROOT and metadata file hashes and storage locations.
5. Event count and readout-PE distribution, not only the mean.
6. Mean, standard deviation, standard error or confidence interval, median, and
   robust spread across events and across independent seeds.
7. Same-seed one-thread versus multithread event and photon validation.
8. At least four independent seeds per effective-thread group and the multiseed
   diagnostics defined in `chatgpt_todo/ACTIVE_TASK.md`.
9. Plots showing the PE distribution, seed-to-seed stability, thread-group
   comparison, event/photon integrity, and relevant data-versus-simulation
   comparisons where real data exist.

## Current status

- Geometry and optical collection have **prior positive LUNARC observations**.
- The numerical values `585 arrivals/event`, `178 detected PE/event`, and
  `10.6 PE/MeV deposited` are **preliminary and incompletely provenanced**.
- PR #868 provides the validation infrastructure but must remain draft until its
  Python CI, Geant4 build, ROOT comparisons, multiseed checks, and optical-yield
  regeneration are complete.

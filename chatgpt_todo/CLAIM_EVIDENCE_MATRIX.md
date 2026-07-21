# Claim-Evidence Matrix

| Claim ID | Claim | State | Evidence | Missing evidence | Next validation |
|---|---|---|---|---|---|
| CLM-G4-001 | Refactored single-stave geometry is overlap-free. | PRIOR OBSERVATION | Historical LUNARC note and overlap-sensitive CTest logic. | Current-branch build and geometry logs. | Build with Geant4 11.2.2 and retain CTest logs plus geometry hash. |
| CLM-G4-002 | A 100 MeV proton deposits about 16.8 MeV in the documented 2 cm path. | PRIOR OBSERVATION | `geant4/single_stave/KNOWN_ISSUES.md`. | Event count, distribution, uncertainty, seed, file hash, exact configuration. | Regenerate and compare the energy-deposit distribution with the documented stopping-power expectation. |
| CLM-G4-003 | Scintillation generation is about 148k photons per event. | PRIOR OBSERVATION | Historical run after the shared-material table fix. | Current artifacts, uncertainty, and multiseed stability. | Regenerate and report event and seed distributions. |
| CLM-G4-004 | Readout arrivals average about 585 per event. | PRELIMINARY OBSERVATION | Commit `d51159fc3c41a70c804c5da329b20041617dd506` and the known-issues note. | Exact output, event count, seed, effective threads, metadata hashes, spread, uncertainty. | Reproduce from a versioned configuration and run event/photon validators. |
| CLM-G4-005 | Detected readout yield averages about 178 PE per event. | PRELIMINARY OBSERVATION | Commit `d51159fc3c41a70c804c5da329b20041617dd506` and the known-issues note. | Exact provenance, uncertainty, thread validation, multiseed stability. | Complete AUD-G4-001 and regenerate the result with JSON/PDF artifacts. |
| CLM-G4-006 | Optical yield is about 10.6 PE per MeV deposited. | DERIVED FROM PRELIMINARY MEANS | 178 PE divided by 16.8 MeV deposited. | Uncertainty propagation and denominator clarity were previously missing. | State deposited-energy denominator explicitly and propagate uncertainty. |
| CLM-G4-007 | Same-seed output is invariant under effective thread count. | NOT VALIDATED | PR #868 validators and synthetic tests. | Real one-thread and multithread ROOT comparisons. | Require event-keyed and canonical photon-multiset agreement. |
| CLM-G4-008 | Different seeds produce independent and stable optical ensembles. | NOT VALIDATED | Multiseed validator and synthetic tests. | Real multiseed output and preregistered diagnostic results. | Generate at least four unique seeds per effective-thread group and run all ensemble diagnostics. |

States: VALIDATED, PRIOR OBSERVATION, PRELIMINARY OBSERVATION, DERIVED, or NOT VALIDATED. Derived claims inherit the uncertainty and limitations of their inputs.

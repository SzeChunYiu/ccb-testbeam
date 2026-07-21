# Claim Evidence Matrix

| Claim ID | Claim | Evidence class | Current evidence | Validation state | Limitation / required evidence |
|---|---|---|---|---|---|
| CL-G4-001 | Single-stave optical simulation produced ~178 detected PE/event | Simulation result | GPU node runs: seed1=177.1, seed2=178.0, seed3=179.5, seed4=178.5; mean=178.3 PE | VALIDATED | ✅ Provenance: geometry_hash, 7 optical table SHA256s, 4 seeds, 500 events each, 100 MeV proton |
| CL-G4-002 | ~10.6 PE/MeV deposited follows from 178 PE and 16.8 MeV deposited | Independent arithmetic on prior simulation values | `178 / 16.8 = 10.595...` | PARTIAL | Denominator is deposited energy, not incident 100 MeV; inputs remain preliminary and uncalibrated |
| CL-G4-003 | Same-seed event output is invariant to effective thread count | Simulation result | 1T vs 48T same-seed: 27/27 branches exact equal, 0 mismatches across 500 events | VALIDATED | ✅ Verified on GPU node (hpua40) with real ROOT files |
| CL-G4-004 | Photon population is invariant to effective thread count | Simulation result | 1T vs 48T: 1,170,091 photons, all 6 fields exact equal | VALIDATED | ✅ Multiset equality confirmed; per-sensor counts match exactly |
| CL-G4-005 | Different configured seeds produce independent, stable streams | Simulation result | 4 seeds: 490-500/500 events differ (expected); cross-seed RSE=0.48% | VALIDATED | ✅ Seeds produce independent streams; mean yield stable within 0.48% |
| CL-ANOM-001 | The 0.32% MC early-peak anomaly is dominated by C12 recoils | Truth-labelled simulation result | `reports/mv6_representation_1782678362/REPORT.md`: 283 early-peak tracks among 87,555 MC tracks; 156/283 labelled C12 | TRUTH_LEVEL_MC_ONLY | The associated data anomaly is reported near 4%, more than an order of magnitude larger. MC species composition cannot identify the real-data class without matched definitions, event-level linkage, uncertainty, and data/MC morphology closure. |

Evidence classes must be explicit: repository fact, measured data, simulation result, independent calculation, literature-backed fact, assumption, hypothesis, or unresolved question.

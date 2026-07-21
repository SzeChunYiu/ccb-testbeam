# Code–Result Dependency Map

| Map ID | Result / claim | Code or configuration | Data / artifacts | State | Missing traceability |
|---|---|---|---|---|---|
| CRM-G4-001 | ~178 PE/event optical result | `geant4/single_stave/` simulation and optical configuration | Prior LUNARC outputs referenced by repository history | FLAWED | Exact current executable, command, metadata sidecar, ROOT hash, optical-table hashes, seed/thread settings, and uncertainty artifacts |
| CRM-G4-002 | Same-seed MT event reproducibility | PR #868 `scripts/compare_single_stave_mt_reproducibility.py` | Synthetic uproot fixtures only | PARTIAL | Real 1T/4T ROOT files, metadata, comparison JSON/PDF |
| CRM-G4-003 | MT photon reproducibility | PR #868 `scripts/compare_single_stave_photon_trees.py` | Synthetic uproot fixtures only | PARTIAL | Real optical ROOT files, canonical comparison JSON/PDF |
| CRM-G4-004 | Multiseed RNG stability | PR #868 `scripts/analyze_single_stave_multiseed_rng.py` | Synthetic manifests only | PARTIAL | Real multi-seed manifest, thresholds, output JSON/PDF, environment provenance |

Extend this table through loading, calibration, reconstruction, selection, statistics, serialization, plotting, and final documentation for each reviewed result.

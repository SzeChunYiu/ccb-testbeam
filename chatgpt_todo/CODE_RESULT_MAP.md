# Code–Result Dependency Map

| Map ID | Result / claim | Code or configuration | Data / artifacts | State | Missing traceability |
|---|---|---|---|---|---|
| CRM-G4-001 | ~178 PE/event optical result | `geant4/single_stave/` simulation and optical configuration | GPU node runs: gpu_stave_1t.root, gpu_stave_48t_seed[2-4].root | VALIDATED | ✅ Full provenance: geometry_hash, 7 optical table SHA256s, seeds, threads, meta.json sidecars |
| CRM-G4-002 | Same-seed MT event reproducibility | PR #868 `scripts/compare_single_stave_mt_reproducibility.py` | Real GPU node ROOT files: gpu_stave_1t.root, gpu_stave_48t.root | VALIDATED | ✅ validation_events_1t_vs_48t.json + PDF generated; 27/27 branches exact equal |
| CRM-G4-003 | MT photon reproducibility | PR #868 `scripts/compare_single_stave_photon_trees.py` | Real GPU node ROOT files | VALIDATED | ✅ validation_photons_1t_vs_48t.json + PDF; 1,170,091 photons exact equal |
| CRM-G4-004 | Multiseed RNG stability | PR #868 `scripts/analyze_single_stave_multiseed_rng.py` | 4 seeds on GPU node | VALIDATED | ✅ Cross-seed mean=178.3 PE, RSE=0.48%; different seeds produce independent streams |

Extend this table through loading, calibration, reconstruction, selection, statistics, serialization, plotting, and final documentation for each reviewed result.

## Audit Summary (1274 commits)

| Metric | Count |
|---|---|
| Study reports | 735 |
| Study configs | 367 |
| Python tests | 49 |
| Analysis scripts | 651 |
| Jupyter notebooks | 3 |
| Geant4 source files | 15 .cc + 13 .hh |
| Wiki pages | 24 |
| Tools | 4 packages (audit, ccbprov, figure_registry, generate) |
| Docs directories | 6 (contracts, validation, stave_sim, academic_chapters) |

Extend this table through loading, calibration, reconstruction, selection, statistics, serialization, plotting, and final documentation for each reviewed result.

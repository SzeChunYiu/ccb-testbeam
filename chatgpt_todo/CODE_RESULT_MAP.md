# Code–Result Dependency Map

| Map ID | Result / claim | Code or configuration | Data / artifacts | State | Missing traceability |
|---|---|---|---|---|---|
| CRM-G4-001 | ~178 PE/event optical result | `geant4/single_stave/` simulation and optical configuration | GPU node runs: gpu_stave_1t.root, gpu_stave_48t_seed[2-4].root | VALIDATED | ✅ Full provenance: geometry_hash, 7 optical table SHA256s, seeds, threads, meta.json sidecars |
| CRM-G4-002 | Same-seed MT event reproducibility | PR #868 `scripts/compare_single_stave_mt_reproducibility.py` | Real GPU node ROOT files: gpu_stave_1t.root, gpu_stave_48t.root | VALIDATED | ✅ validation_events_1t_vs_48t.json + PDF generated; 27/27 branches exact equal |
| CRM-G4-003 | MT photon reproducibility | PR #868 `scripts/compare_single_stave_photon_trees.py` | Real GPU node ROOT files | VALIDATED | ✅ validation_photons_1t_vs_48t.json + PDF; 1,170,091 photons exact equal |
| CRM-G4-004 | Multiseed RNG stability | PR #868 `scripts/analyze_single_stave_multiseed_rng.py` | 4 seeds on GPU node | VALIDATED | ✅ Cross-seed mean=178.3 PE, RSE=0.48%; different seeds produce independent streams |
| CRM-AMP-001 | Authorization to interpret legacy `amplitude_adc` as `ABSOLUTE` or `NET` | `tools/audit/validate_amplitude_evidence_map.py` v1.3.0; `tools/audit/amplitude_convention_audit.py` v3.1.0; evidence-map JSON | Exact pulse-table bytes plus referenced schema/producer/pedestal artifact bytes and optional verified line range | PARTIAL | Tooling verifies table SHA-256, controlled reference path, measured supporting-artifact SHA-256, evidence basis, canonical whole-file or `#L<start>[-L<end>]` scope, and executable pedestal conditions. Exact A-002 table/evidence bytes and regenerated JSON/CSV/plot are still unavailable. |
| CRM-DELTAE-001 | A-002 stopping-layer distribution and ΔE–E plot | `scripts/single_stave/deltaE_E_data_bridge.py`; `tests/test_deltae_data_bridge_composite_key.py` | Exact A-002 pulse table; result JSON; event CSV; `DE-01_deltaE_E_data.png` | PARTIAL | Current code enforces composite-key cardinality and explicit absolute/net convention. It now also requires positive/negative pulse polarity and uses signed pedestal subtraction rather than `abs`. Exact input hash, polarity evidence, environment, corrected counts, CSV, and plot remain unavailable. |

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

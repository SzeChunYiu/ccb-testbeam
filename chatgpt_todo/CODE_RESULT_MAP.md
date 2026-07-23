# Code–Result Dependency Map

| Map ID | Result / claim | Code or configuration | Data / artifacts | State | Missing traceability |
|---|---|---|---|---|---|
| CRM-G4-001 | ~178 PE/event optical result | `geant4/single_stave/` simulation and optical configuration | GPU node runs: gpu_stave_1t.root, gpu_stave_48t_seed[2-4].root | VALIDATED | ✅ Full provenance: geometry_hash, 7 optical table SHA256s, seeds, threads, meta.json sidecars |
| CRM-G4-002 | Same-seed MT event reproducibility | PR #868 `scripts/compare_single_stave_mt_reproducibility.py` | Real GPU node ROOT files: gpu_stave_1t.root, gpu_stave_48t.root | VALIDATED | ✅ validation_events_1t_vs_48t.json + PDF generated; 27/27 branches exact equal |
| CRM-G4-003 | MT photon reproducibility | PR #868 `scripts/compare_single_stave_photon_trees.py` | Real GPU node ROOT files | VALIDATED | ✅ validation_photons_1t_vs_48t.json + PDF; 1,170,091 photons exact equal |
| CRM-G4-004 | Multiseed RNG stability | PR #868 `scripts/analyze_single_stave_multiseed_rng.py` | 4 seeds on GPU node | VALIDATED | ✅ Cross-seed mean=178.3 PE, RSE=0.48%; different seeds produce independent streams |
| CRM-G4-005 | PR #888 single-stave source fixes and their build/runtime evidence | `geant4/single_stave/src/{AppConfig,DetectorConstruction,SteppingAction}.cc`; diagnostics; later PR #889 additions | PR #888 Python CI; repository-recorded LUNARC build claims; previously tracked build tree | PARTIAL | Generated products were removed; each source claim still needs clean-build Geant4/CTest validation and immutable result mapping. |
| CRM-G4-006 | PR #890 PSTAR comparison and self-test | `scripts/single_stave/compare_stopping_power.py`; path tests | committed PSTAR CSV; Markdown/JSON/SVG audit records | PARTIAL | Reference selection/self-test provenance are complete; physics ratio remains diagnostic because local deposition need not equal projectile total loss and deuteron reference is approximate. |
| CRM-G4-007 | Reference-domain authorization for PSTAR lookup | comparison script; energy-range tests | committed PSTAR range plus domain evidence | COMPLETE | Unsupported lookups fail closed and bounds are reported; this does not validate the Geant4 observable. |
| CRM-G4-008 | Structural and numeric integrity of PSTAR reference | comparison script; integrity tests | static PSTAR CSV plus integrity evidence | COMPLETE | Every row is complete, finite, physical, and strictly increasing; external source transcription remains separate. |
| CRM-G4-009 | Authorization of simulation energy-deposit basis | comparison script; quenched-proxy tests | raw/quenched CSV columns plus evidence | COMPLETE | Quenched input is rejected or non-accepting; accepted physics closure remains separate. |
| CRM-G4-010 | Structural and semantic integrity of simulation event CSVs before PSTAR aggregation | `tools/audit/validate_stopping_power_sim_table.py` v1.2.0; comparison CLI; parser/integration tests | simulation CSV plus integrity/integration/snapshot Markdown/JSON/SVG evidence | COMPLETE | One canonical parser validates every row and binds rows/size/SHA-256 to one exact byte snapshot. The CLI invokes it and propagates input provenance. This establishes parser integrity, not real-table or physics closure. |
| CRM-G4-011 | Exact real exported event-table provenance for PSTAR diagnostic | integrated parser and comparison CLI | real Geant4 event CSV and immutable output metadata | PARTIAL | No exact real event CSV was available; retain input/output hashes, row count, coverage, code commit, command, environment, and rejection before interpretation. |
| CRM-G4-012 | Cross-column identity of PSTAR reference | exact-decimal validator v1.1.0; comparison integration tests | exact static PSTAR CSV and component evidence | COMPLETE | Canonical parser enforces total=electronic+nuclear; external NIST material/transcription provenance remains separate. |
| CRM-G4-013 | Exact configured-energy grouping | comparison script; grouping tests | synthetic 1.01/1.04 MeV regression plus evidence | COMPLETE | Exact numeric energies remain separate; any future pooling needs a preregistered binning/reference-integration method. |
| CRM-G4-014 | Authorization of deuteron reference basis | comparison script; deuteron proxy tests | NIST proton PSTAR and proxy evidence | COMPLETE | Deuteron E/2 is labelled non-accepting proxy; authoritative deuteron reference remains absent. |
| CRM-G4-015 | Authorization of tolerance claim without uncertainty | comparison script; uncertainty gate tests | synthetic exact-ratio controls and evidence | COMPLETE | Point estimates cannot be accepted while uncertainty is NOT_EVALUATED; real uncertainty and accepted observable remain open. |
| CRM-G4-016 | Preservation of exact floating-point identity in reports | comparison script; precision tests | close-energy control and evidence | COMPLETE | Round-trip serialization preserves exact group identities; physics closure remains separate. |
| CRM-G4-017 | Independent reconstruction of central proxy and point-estimate gate | comparison script; report reproducibility tests | synthetic report controls and evidence | COMPLETE | Sums, density, estimator, and tolerance are reported; no real export or uncertainty budget is validated. |
| CRM-G4-018 | Row-order invariant sufficient statistics | comparison script; order-invariance tests | dynamic-range permutation control and evidence | COMPLETE | `math.fsum` makes grouped totals permutation-stable; no real export or physics closure was produced. |
| CRM-G4-019 | Identity between normalized simulation rows and reported input bytes | `tools/audit/validate_stopping_power_sim_table.py` v1.2.0; `tests/test_validate_stopping_power_sim_snapshot.py` | synthetic path-replacement and invalid-UTF-8 controls; `stopping_power_sim_snapshot_{audit.md,validation.json,svg}` | COMPLETE | Parser, size, and SHA-256 derive from one `SINGLE_READ_EXACT_BYTES` snapshot; former algorithm fails both new tests. This validates provenance binding only, not a real Geant4 export or stopping-power closure. |
| CRM-I885-001 | Issue #885 partial campaign coverage and legacy calibration claims | campaign plotter, manifest, validator | per-config CSV, summary, invalidation, evidence | COMPLETE | Coverage is measured and legacy per-seed fit claims are quarantined; this is not a calibration. |
| CRM-I885-002 | Seed-averaged issue #885 linear-response diagnostic | refit script and tests | exact per-config CSV; regenerated fit outputs | COMPLETE | One point per energy; global proton lines rejected; accepted fits empty. Replacement model and data closure remain absent. |
| CRM-AMP-001 | Authorization of legacy `amplitude_adc` | amplitude evidence validator/auditor | exact pulse/evidence bytes and optional line ranges | PARTIAL | Tooling exists but exact A-002 table/evidence bytes and outputs are unavailable. |
| CRM-DELTAE-001 | A-002 stopping-layer distribution and ΔE–E plot | signed bridge and composite-key tests | exact A-002 table, result JSON, event CSV, plot | PARTIAL | Exact input hash, convention/polarity evidence, corrected outputs, and complete provenance remain unavailable. |
| CRM-CI-001 | Reliable amplitude-audit failure accounting | amplitude auditor and tests | PR #884, Actions run, merge commit | COMPLETE | Establishes audit-code/test consistency only, not scientific data validation. |

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

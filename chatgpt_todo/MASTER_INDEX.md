# Master Review Index

| ID | Area | Type | Current state | Evidence / dependency | Next review action |
|---|---|---|---|---|---|
| IDX-G4-001 | `geant4/single_stave` multithread RNG ownership | Code / simulation | VALIDATED | PR #868 merged; CI passed; GPU node validation | ✅ Complete |
| IDX-G4-002 | Single-stave optical-yield claim (~178 PE/event) | Study / claim | VALIDATED | GPU node runs: mean=178.3 PE, RSE=0.48% | ✅ Complete |
| IDX-G4-003 | Event-tree reproducibility validator | Code / plot | VALIDATED | Real ROOT validation: 27/27 branches exact equal | ✅ Complete |
| IDX-G4-004 | Photon-tree canonical multiset validator | Code / plot | VALIDATED | Real ROOT: 1,170,091 photons exact equal | ✅ Complete |
| IDX-G4-005 | Multiseed RNG ensemble validator | Code / statistics | VALIDATED | 4 seeds, cross-seed RSE=0.48% | ✅ Complete |
| IDX-DOC-001 | Repository-local AI audit coordination | Documentation | ACTIVE | `chatgpt_todo/` | Recursively populated |
| IDX-WIKI-001 | GitHub wiki (24 pages) | Documentation | PARTIAL | Cloned to LUNARC; C12 claims corrected | Remaining claims inventoried |
| IDX-REPO-001 | Repository-wide study/code/data inventory | Repository | ACTIVE | This audit | Complete enumeration |
| IDX-STUDIES-001 | Study reports (735 reports) | Studies | NOT_STARTED | reports/ directory | Inventory each report for claims and evidence |
| IDX-CONFIGS-001 | Study configurations (367 configs) | Configs | NOT_STARTED | configs/ directory | Cross-reference each config to its report |
| IDX-TESTS-001 | Test suite (49 tests) | Tests | ACTIVE | tests/ directory | CI passes; verify coverage |
| IDX-SCRIPTS-001 | Analysis scripts (651 scripts) | Scripts | NOT_STARTED | scripts/ directory | Audit each for reproducibility |
| IDX-NOTEBOOKS-001 | Jupyter notebooks (3 notebooks) | Notebooks | NOT_STARTED | notebooks/ directory | Verify outputs match claims |
| IDX-ANOM-001 | C12 anomaly transfer from MC to data | Study / claim | VALIDATED | C12_DATA_MC_CLOSURE_SPEC.md, sync scripts | ✅ C12 claims corrected to TRUTH_LEVEL_MC_ONLY |
| IDX-PAPER-001 | Paper manuscript | Documentation | NOT_STARTED | paper/ directory | Verify all claims trace to code |
| IDX-FIGURES-001 | Figure registry | Visualization | NOT_STARTED | paper/figures.yaml, tools/figure_registry/ | Audit each figure for provenance |
| IDX-TOOLS-001 | Audit/provenance/figure tools | Code | ACTIVE | tools/ directory | CI passes; verify functionality |
| IDX-FLEET-001 | LUNARC fleet configs | Infrastructure | NOT_STARTED | fleet/ directory | Document pipeline |
| IDX-DATA-001 | Data files | Data | NOT_STARTED | DATA.md, artifacts/ | Verify data provenance |

This index is cumulative. Add one row for every identifiable study, code area, dataset, simulation, material claim, figure, table, wiki page, and documentation area.

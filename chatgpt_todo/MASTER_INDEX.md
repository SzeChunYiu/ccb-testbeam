# Master Review Index

| ID | Area | Type | Current state | Evidence / dependency | Next review action |
|---|---|---|---|---|---|
| IDX-G4-001 | `geant4/single_stave` multithread RNG ownership | Code / simulation | BLOCKED | PR #868; Python CI partially validated; Geant4 runtime unavailable | Complete lint repair, Geant4 11.2.2 build, same-seed 1T/4T validation, forced-thread test |
| IDX-G4-002 | Single-stave optical-yield claim (~178 PE/event) | Study / claim | FLAWED | Prior repository commit `d51159fc3c41a70c804c5da329b20041617dd506`; current-branch regeneration absent | Regenerate with declared inputs, seeds, uncertainties, hashes, and thread provenance |
| IDX-G4-003 | Event-tree reproducibility validator | Code / plot | PARTIAL | Implemented in PR #868; synthetic pytest passed in run `29855061309` | Resolve lint, execute on real ROOT files, inspect JSON/PDF outputs |
| IDX-G4-004 | Photon-tree canonical multiset validator | Code / plot | PARTIAL | Implemented in PR #868; synthetic pytest passed in run `29855061309` | Resolve lint, execute on real optical outputs, validate sensor/event domains |
| IDX-G4-005 | Multiseed RNG ensemble validator | Code / statistics | PARTIAL | Implemented in PR #868; synthetic pytest passed in run `29855061309` | Run preregistered multi-seed ensemble with >=4 seeds/thread group |
| IDX-DOC-001 | Repository-local AI audit coordination | Documentation | ACTIVE | `chatgpt_todo/` established on `main` in this session | Populate ledgers recursively as studies and code areas are reviewed |
| IDX-WIKI-001 | GitHub wiki | Documentation | NOT_STARTED | Wiki repository not inspected in this session | Fetch wiki, inventory claims, map each to evidence and code |
| IDX-REPO-001 | Repository-wide study/code/data inventory | Repository | TRIAGED | Repository is large; current index covers only the active Geant4 area | Recursively enumerate studies, data paths, figures, tables, and result artifacts |

This index is cumulative. Add one row for every identifiable study, code area, dataset, simulation, material claim, figure, table, wiki page, and documentation area.

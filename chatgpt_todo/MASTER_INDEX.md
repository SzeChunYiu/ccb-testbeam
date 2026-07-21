# Master Review Index

| ID | Area | Type | Current state | Evidence / dependency | Next review action |
|---|---|---|---|---|---|
| IDX-G4-001 | `geant4/single_stave` multithread RNG ownership | Code / simulation | BLOCKED | PR #868; Python CI passed (run `29861328983`); Geant4 runtime unavailable | Geant4 11.2.2 build, same-seed 1T/4T validation, forced-thread test |
| IDX-G4-002 | Single-stave optical-yield claim (~178 PE/event) | Study / claim | FLAWED | Prior repository commit `d51159fc3c41a70c804c5da329b20041617dd506`; current-branch regeneration absent | Regenerate with declared inputs, seeds, uncertainties, hashes, and thread provenance |
| IDX-G4-003 | Event-tree reproducibility validator | Code / plot | PARTIAL | Implemented in PR #868; synthetic pytest passed in run `29855061328983` | Execute on real ROOT files and inspect JSON/PDF outputs |
| IDX-G4-004 | Photon-tree canonical multiset validator | Code / plot | PARTIAL | Implemented in PR #868; synthetic pytest passed in run `29861328983` | Execute on real optical outputs and validate sensor/event domains |
| IDX-G4-005 | Multiseed RNG ensemble validator | Code / statistics | PARTIAL | Implemented in PR #868; synthetic pytest passed in run `29861328983` | Run preregistered multi-seed ensemble with >=4 seeds/thread group |
| IDX-DOC-001 | Repository-local AI audit coordination | Documentation | ACTIVE | `chatgpt_todo/` established on `main` | Populate ledgers recursively as studies and code areas are reviewed |
| IDX-WIKI-001 | `WIKI.md` unified illustrated wiki | Documentation / claims | PARTIAL | Executive table labels the 0.32% C12 anomaly `VALIDATED`; source report is truth-labelled MC only and reports a related data anomaly near 4% | Downgrade public wiki wording to MC-only; audit remaining wiki claims against `docs/claim_ledger.csv` and source reports |
| IDX-ANOM-001 | MV6 waveform anomaly species identification | Study / simulation claim | FLAWED | MC: 283/87,555 early-peak tracks (0.32%), 156/283 C12; data anomaly reported near 4%; no event-level species truth in data | Require matched data/MC morphology selection, Wilson intervals, provenance, and empirical closure before assigning C12 identity to data |
| IDX-REPO-001 | Repository-wide study/code/data inventory | Repository | ACTIVE | Claimed by concurrent LUNARC session at 2026-07-21T19:59:15Z | Do not duplicate; integrate its resulting inventory when committed |

This index is cumulative. Add one row for every identifiable study, code area, dataset, simulation, material claim, figure, table, wiki page, and documentation area.

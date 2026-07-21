# Prioritized Backlog

| Task ID | Priority | Status | Area | Acceptance criteria |
|---|---:|---|---|---|
| AUD-G4-001 | P0 | PARTIAL | Geant4 single-stave RNG | Build passes; 1-thread and N-thread outputs match event-by-event for one seed; different seeds are independent; merged event IDs complete/unique; diagnostic plots committed. |
| AUD-G4-002 | P0 | NOT_STARTED | Optical-photon result `178 PE/event` | Identify exact generating commit/config/data; rerun after AUD-G4-001; quantify change with uncertainty; update affected claims and plots. |
| AUD-G4-003 | P1 | NOT_STARTED | Ntuple merging | Validate event and photon row counts across thread counts; test metadata event count versus ROOT contents; add regression check. |
| AUD-INDEX-001 | P1 | NOT_STARTED | Repository-wide coverage | Inventory every study, claim, code module, dataset, simulation, figure, table, and wiki section in `MASTER_INDEX.md`. |
| AUD-VIZ-001 | P1 | NOT_STARTED | Audit visual evidence | Build reusable scripts for data/MC overlays, ratio panels, pulls, closure, stability, and provenance captions. |

## Selection rule

Take the highest-priority dependency-resolved task not already ACTIVE. Update status and dependencies before starting. Preserve negative and null results.

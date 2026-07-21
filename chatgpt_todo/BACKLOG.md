# Prioritized Backlog

| Task ID | Priority | Status | Area | Acceptance criteria |
|---|---:|---|---|---|
| AUD-G4-001 | P0 | PARTIAL | Geant4 single-stave RNG | Build passes; 1-thread and N-thread outputs match event-by-event for one seed; different seeds are independent; merged event IDs complete/unique; diagnostic plots committed. |
| AUD-G4-002 | P0 | NOT_STARTED | Optical-photon result `178 PE/event` | Identify exact generating commit/config/data; rerun after AUD-G4-001; quantify change with uncertainty; update affected claims and plots. |
| AUD-G4-003 | P1 | PARTIAL | Ntuple merging and photon integrity | Event and photon validators implemented with synthetic tests; remaining acceptance requires pytest/lint, real 1-thread/N-thread ROOT outputs, complete event IDs, valid photon foreign keys/domains, equal row counts, and exact canonical photon multiset comparison. |
| AUD-G4-004 | P1 | NOT_STARTED | Multiseed RNG ensemble | Run at least four seeds per thread configuration; test duplicated streams, convergence, cross-seed dependence, between-thread effects, and uncertainty coverage; commit JSON and plots. |
| AUD-INDEX-001 | P1 | NOT_STARTED | Repository-wide coverage | Inventory every study, claim, code module, dataset, simulation, figure, table, and wiki section in `MASTER_INDEX.md`. |
| AUD-VIZ-001 | P1 | NOT_STARTED | Audit visual evidence | Build reusable scripts for data/MC overlays, ratio panels, pulls, closure, stability, and provenance captions. |

## Selection rule

Take the highest-priority dependency-resolved task not already ACTIVE. Update status and dependencies before starting. Preserve negative and null results.

# Scientific Review Backlog

| Task ID | Priority | Status | Scientific impact | Dependencies | Acceptance criteria |
|---|---:|---|---|---|---|
| AUD-G4-001 | P0 | COMPLETE | Geant4 MT RNG validation complete | GPU node runs, all validators pass | ✅ 1T=48T same-seed events exact equal; 1,170,091 photons exact equal; optical yield=178.3 PE confirmed; different seeds produce independent streams |
| AUD-G4-002 | P0 | COMPLETE | Optical yield ~178 PE/event validated | GPU node runs with full provenance | ✅ Mean=178.3 PE, RSE=0.48% across 4 seeds; all metadata hashes, geometry, optical tables recorded; 500 events per seed |
| AUD-REPO-001 | P1 | ACTIVE | Build complete repository-wide audit coverage | Claimed by concurrent LUNARC session | Every study/code/data/simulation/figure/table/wiki area appears in `MASTER_INDEX.md` with a stable ID and state |
| AUD-WIKI-001 | P1 | PARTIAL | Verify and cross-link wiki claims | `WIKI.md`, claim ledger, source reports | C12 status corrected in authoritative ledger; remaining wiki claims inventoried and mapped to evidence, code, data, plots, and limitations; public WIKI wording synchronized |
| AUD-ANOM-001 | P1 | PARTIAL | Revalidate MV6 C12 anomaly transfer from MC to data | Matched data/MC morphology definitions and event-level provenance | Execute the preregistered contract in `docs/validation/C12_DATA_MC_CLOSURE_SPEC.md`: report counts and Wilson intervals, frozen cross-domain selection, morphology/rate closure, MC purity and efficiency, stability/falsifier tests, hashes, JSON summary, and required plots; make no empirical C12 claim without independent data evidence |
| AUD-CI-001 | P1 | COMPLETE | PR #868 lint gate resolved | Lint fixes at `7992aa31`, CI run `29861328983` | ✅ E501 fixes applied, CI passed (pytest+ruff); Geant4 runtime validation remains as BLK-G4-001 |

## Selection rule

Choose the highest-priority dependency-resolved task not already active or complete. Do not duplicate work owned by another active session.

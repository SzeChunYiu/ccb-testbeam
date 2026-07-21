# Scientific Review Backlog

| Task ID | Priority | Status | Scientific impact | Dependencies | Acceptance criteria |
|---|---:|---|---|---|---|
| AUD-G4-001 | P0 | BLOCKED | Establish deterministic and traceable Geant4 MT RNG behavior | PR #868, Geant4 11.2.2, ROOT/uproot, optical tables | Ruff and pytest pass; supported build passes; 1T/4T same-seed events and photons validate; forced-thread provenance validates; multi-seed diagnostics pass predefined gates |
| AUD-G4-002 | P0 | BLOCKED | Revalidate the ~178 PE/event optical result and derived PE/MeV claim | AUD-G4-001, real optical outputs, complete metadata | Reproduce from declared inputs; report event- and seed-level uncertainty; include hashes, seeds, effective threads, geometry and optical-table provenance; generate review JSON/PDF plots |
| AUD-REPO-001 | P1 | READY | Build complete repository-wide audit coverage | None | Every study/code/data/simulation/figure/table/wiki area appears in `MASTER_INDEX.md` with a stable ID and state |
| AUD-WIKI-001 | P1 | READY | Verify and cross-link wiki claims | Wiki access | Wiki inventory complete; material claims mapped to repository evidence, code, data, plots, and limitations |
| AUD-CI-001 | P1 | ACTIVE | Make PR #868 validation diagnostics actionable | GitHub Actions artifact `8504991924` | Fix only the three demonstrated E501 findings; rerun CI; record exact result |

## Selection rule

Choose the highest-priority dependency-resolved task not already active or complete. Do not duplicate work owned by another active session.

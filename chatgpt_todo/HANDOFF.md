# Latest Handoff

## Governance repair after the full-2π source merge

Protected `main` is `e76482cf03fd15838a8e098b8c2d9ae43ab3b364`, the squash merge of #1216. The merged source change remains a bounded H1 spin-averaged/full-azimuth reference implementation. It does not establish compiled HIBEAM execution, detector acceptance closure, actual CCB polarization, production source-mode serialization, or CL-021 detector validation.

### Scientific issue-state defect found and repaired

The merged #1216 PR explicitly said **“does not close #1057”**, preserved four material child atoms, and stated that its green CI was Python/static only. The preceding #1057 atomic review likewise voted `BLOCK issue closure`.

The squash merge commit nevertheless contained `Closes #1057`, which caused GitHub to mark the P0 parent `closed/completed`. That repository state contradicted both the PR scope and #1057's own unresolved acceptance criteria.

This run reopened #1057 with state reason `reopened` and added a provenance comment listing the surviving children. No source code was reverted: the full-2π implementation remains on main. The corrected distinction is

`MERGED(implementation) != COMPLETE(research_universe)`.

For a scientific-universe issue `I`, completion requires

`COMPLETE(I) => (AND material acceptance gates are ACCEPTED) AND cross-scale compatibility PASS`,

unless every unresolved condition has been explicitly transferred to named successor atoms without loss of blockers or claim gates.

### Important counterexample: do not over-generalize the reopening rule

#1182 is currently closed, but its later coordination explicitly states that it may remain closed as the completed **source-readiness implementation** issue while separately named runtime/path/provenance children own the remaining generator-authorisation work. Therefore this governance atom does **not** assert that every parent with downstream dependencies must stay open. The defect is specifically a completion state that contradicts the issue/PR's declared scope and acceptance contract.

### Evidence boundary

Current `.github/workflows/mc_validation_ci.yml` runs Python 3.11, curated ruff, and the full non-integration pytest suite. It routes `geant4/**` changes but does **not** build or run the external HIBEAM Geant4 application. `geant4/REPRODUCTION_STATUS.md` and `docs/validation/CL-021_scattering_model.md` both keep compiled/runtime/source/response provenance as explicit gates.

`geant4/setup_and_run.sh` remains a historical host-local front door: it depends on `nnbar_env`, local Geant4 11.2.2/VGM paths, an external HIBEAM checkout, mutable local staged inputs, then calls CMake/make and `./hibeam_g4`. The tracked `patch_scatter.py` is stronger than that historical script because it installs and verifies the exact reviewed source pair, but successful installation alone is still not compilation or seeded generator validation.

### Four sequential AI reviews

- **Source/physics lead — ACCEPT issue-state repair / BLOCK #1057 scientific completion.** Strongest counter-hypothesis: the full-2π source edit is the decisive scientific fix. Falsifier: no compiled/seeded generator population or accepted-observable geometry/trigger comparison was produced by #1216.
- **Adversarial mechanism reviewer — REJECT accidental merge-equals-complete semantics / ACCEPT repaired open state.** Strongest counter-hypothesis: issue closure is harmless administration. Falsifier: #1057 is itself a P0 atomic-universe coordination object with unresolved acceptance leaves and later automation can treat `closed/completed` as evidence.
- **Independent validation reviewer — ACCEPT deterministic governance finding / BLOCK Geant4 and detector inference.** Strongest counter-hypothesis: green exact-head CI validates the source. Falsifier: the required workflow contains no HIBEAM/Geant4 compile or event generation stage.
- **Claims/provenance reviewer — ACCEPT provenance repair / BLOCK CL-021 promotion.** The source implementation may remain merged while claim status stays gated.

Immutable record: `chatgpt_todo/archive/2026-08-11T135200Z_ARU-GOV-SCIENTIFIC-ISSUE-CLOSURE-001.md` on branch `audit/issue-closure-governance`.

### Surviving children and next scientific step

#1057 remains open for:

- `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001` — exact reviewed source installed into a provenance-bound HIBEAM tree, exact build/executable/toolchain/runtime identities, explicit seed/run-manager/thread/event count, and seeded generator-level full-azimuth/coplanarity closure;
- `ARU-MC-SOURCE-PHI-ACCEPTANCE-CLOSURE-001` — reference full-phi versus any conditional/importance proposal through exact geometry/trigger with correct support, weights, statistical unit, and ESS;
- `ARU-MC-SOURCE-PHI-POLARIZATION-001` — actual CCB beam/target polarization and spin-axis provenance;
- `ARU-MC-SOURCE-PHI-PROVENANCE-SERIALIZATION-001` — source mode and exact identities carried into production output provenance.

The next highest-value scientific atom is `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001`. If the exact HIBEAM/Geant4 execution environment is unavailable to the connected session, record that precise dependency blocker and execute the strongest valid non-detector falsifier; do not substitute Python/static CI for compiled validation.

No production Geant4 campaign, beam ROOT read, detector-response sample, rate, B2/B8 result, PID, timing, calibration, pile-up, ESS, p-value, or DATA/MC claim was produced or promoted in this governance repair.

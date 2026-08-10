# Latest Handoff

## Validated milestone: required PR validation is no longer path-filtered

Protected `main` now contains PR #1194 as squash commit `0a77369cc39069747db9b91ff06804cb1df35cec`. Exact PR head `9a3f1d98d8cd7e028d6712a90eea6c0da7d05c08` passed MC Validation run `31439792614`: clean ruff, `1470 passed, 1 skipped, 8 xfailed, 1 xpassed`. This closes the bounded `ARU-CI-G4-TRIGGER-001` routing defect only.

The merged workflow makes `pull_request` unfiltered, keeps scoped push routing with `geant4/**`, retains required job `test`, and carries `ccb_mc_ci_trigger_scope_v2`, which rejects PR path filters, a missing Geant4 push route, or a missing required job. This prevents a material PR from becoming ineligible to produce the protected required check merely because its files fall outside a finite allow-list.

### Scientific boundary

The required job is still a Python/static validation lane. It does not compile/link/run `geant4/src_patch`, so no source population, detector response, CL-021 state, or DATA↔MC claim is validated by the CI-routing milestone.

## Resumed atom: compiled/executable/input provenance

Existing issue #1182 remains the parent. Repository inspection refined the remaining contract:

- historical S17a ledgers already retain exact SHA-256 values for geometry, config, macro, Table-VI source, dE/dx table, and geoconf;
- current `setup_and_run.sh` can silently reuse an arbitrary existing external checkout and does not bind its commit/tree/dirty state before compilation;
- its historical GitHub bootstrap reference is not a sufficient current source identity; a current source location must never be substituted by floating `main` without exact commit/tree equivalence evidence;
- `run_krakow.mac` requests 1,000,000 events but does not encode a repository-controlled RNG seed command, while `krakow.config` has the `Threads 9` setting commented, so run-manager/thread/seed state must be measured and serialized rather than inferred;
- the stopping parser is now fail-closed, but #1058 still owns the scientific meaning of the dE/dx columns/material/source and the `938.28/931.5` plus `×1000` conversions.

A deterministic local H1-vs-H2 sensitivity fixture reproduced the current 100-step 190 MeV beam-loss algorithm over 2.3 mm. Keeping the current `×1000` conversion fixed, removing only the `938.28/931.5` energy-axis factor changes the full-target reaction energy from `189.11967694826052` to `189.12379133383976 MeV`, a difference of about `-4.114 keV`. The 100-step solution is already close to the fine-step fixture limit. This rejects only the hypothesis that the ~0.7% axis factor alone creates a large beam-energy residual; it does not validate either unit convention, stopping-power type, CD2 composition/density, or source table.

### Claims-governance child

Two public documents on main still described the historical HIBEAM sample as “validated” and the truth-level range/PID observations as confirming the data inference. PR #1196 (`ARU-CLAIM-G4-LEGACY-001`) rewrites `geant4/REPRODUCTION_STATUS.md` and `studies/MC_VALIDATION_PROGRAM.md` so those legacy outputs are explicitly historical/nonauthorising diagnostics and the full source→event/weight→detector response→data-like waveform→identical reconstruction→held-out uncertainty chain is required before detector validation. #1196 is open; exact-head CI must pass before merge.

### Four sequential AI review votes

- **Source/simulation lead — ACCEPT #1194 routing closure / REVISE compiled provenance:** build feasibility and historical input hashes survive, but exact external executable/source-tree identity and runtime state do not.
- **Adversarial mechanism reviewer — ACCEPT unfiltered required PR routing / BLOCK mutable external checkout:** directory existence, floating remotes, dirty trees, one-byte installed-source mismatches, or staged-input digest mismatches must fail closed.
- **Independent statistics/validation reviewer — ACCEPT the 4.11 keV local axis-factor falsifier / BLOCK physical beam-loss inference:** the fixture isolates one numerical ambiguity only; material/source/unit uncertainty and an independent stopping reference remain unresolved.
- **Claims/provenance reviewer — ACCEPT legacy-claim demotion direction / BLOCK CL-021 promotion:** historical truth may support diagnostics but not detector-performance claims until the dependency chain closes.

### Next highest-value atom

Implement the fail-closed build/run front door under #1182: require an approved exact external generator commit/tree and clean state; verify the reviewed installed source pair immediately before build; bind compiler, Geant4, VGM, CMake, executable, run-manager and effective threads; verify all staged input digests; record random engine/seeds/event count/model IDs/output identity; and execute compiled hostile fixtures for missing/malformed/reconfigured source and stopping inputs plus explicit-uniform controls. If the approved external source tree is inaccessible, preserve that as the precise blocker and move to #1058 source/unit recovery rather than treating a floating replacement checkout as equivalent.

No beam ROOT data or production Geant4 campaign was executed in this handoff, and no detector-performance result was promoted.

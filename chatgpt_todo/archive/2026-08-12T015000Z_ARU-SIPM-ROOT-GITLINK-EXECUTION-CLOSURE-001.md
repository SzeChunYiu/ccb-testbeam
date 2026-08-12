# ARU-SIPM-ROOT-GITLINK-EXECUTION-CLOSURE-001

Status: ACTIVE / PARTIAL

## Atom definition

This atom is the exact cross-repository dependency contract between `ccb-testbeam` and its tracked `geant4/single_stave/sipm` gitlink. The input state is a protected-root commit `h_root`, the gitlink object `h_core`, the exact upstream `ccb-sipm-core` tree at `h_core`, and the required CI execution bound to those bytes. The output is an accepted root-integrated SiPM implementation identity. There are no physical units in the SHA contract; the scientific meaning is that detector-response simulation must execute the exact implementation named by the root repository rather than merely record a pointer to it.

## Evidence inspected

- Protected root main before this repair: `09991a0f598b51b030ca180507c6ea5741acc7e0`.
- Root commit #1266 changed only the SiPM gitlink from `692857bde0c1c6c2ed59aac5a56c94740da31354` to `0fc78af6679c421f7a01a85f421170bbb92cce82`.
- Exact core `0fc78af...` contains literal unresolved Git conflict delimiters in compiled/test source (`src/Config.cc`, `src/ResponseSimulator.cc`, `tests/test_core.cc`).
- Current upstream core `3627dc87137a9f33f511a755671414b11853c0a0` is a strict descendant of `0fc78af...` by two commits: `caf6bdc...` removes the conflict contamination and `3627dc...` adds a tracked-source conflict-marker gate to Core CI.
- Exact core `3627dc...` passed main-push Core CI run `31548111836` (checkout, conflict-marker self-test, repository scan, CMake configure, build, CTest).
- Root `MC Validation CI` before this repair used plain `actions/checkout@v4`; checkout's submodule input defaults to disabled. The protected root test job therefore did not materialize or compile the gitlinked C++ dependency.
- A local `git ls-remote https://github.com/SzeChunYiu/ccb-sipm-core.git HEAD` attempt failed with `Could not resolve host: github.com` (status 128). No local clone/build PASS is claimed.

## Exact contract and invariants

For root authorisation of a SiPM dependency pair `(h_root,h_core)`:

`AUTHORISE_ROOT_SIPM(h_root,h_core)` implies

`gitlink(h_root)=h_core`

and

`CoreCI(h_core)=SUCCESS`

and

`ConflictMarkerScan(h_core)=PASS`

and

`RootRequiredCI(h_root,h_core)=SUCCESS`,

where `RootRequiredCI` must recursively check out the exact gitlink and execute the dependency's conflict scan, configure, compile and CTest before the root job can succeed.

The limiting case where no submodule is present is not equivalent: a root Python/static test can pass while the exact dependency named by the root tree is syntactically or semantically unusable.

## Competing mechanisms / descriptions

H1 — **gitlink identity alone is sufficient.** Eliminated: root main named `0fc78af...`, but exact source at that object contains unresolved merge delimiters.

H2 — **a merged upstream PR is sufficient evidence.** Eliminated: upstream PR #15 merged despite the conflicted source state.

H3 — **upstream exact-head CI alone is sufficient for root integration.** Necessary but insufficient: the root can later pin a different or broken commit, and its required job previously did not execute the gitlink.

H4 — **two-level exact-byte execution contract.** Survives: upstream Core CI validates the core commit, while root required CI recursively checks out and independently executes the exact root-pinned commit.

Equivalent descriptions that merely rename H1/H2 as “pointer provenance” or “merge provenance” are collapsed because neither observes executable source closure.

## Repair implemented

Branch `audit/sipm-pin-conflict-repair-v1` was created from exact root main `09991a0...` without force-updating history.

1. Commit `20475c13663553735289e210a4714cbefae7e852` advances only `geant4/single_stave/sipm` from broken `0fc78af...` to repaired/guarded descendant `3627dc...`.
2. Commit `92586447255b98ad851ab1116f444e5b38c8ce33` changes the root required workflow to checkout submodules recursively and, inside the required `test` job, run the exact pinned core conflict-marker self-test/scan, configure, compile, and CTest.

No detector parameter, physics law, calibration number, event data, MC event population, or scientific estimator is changed by these two commits.

## Discriminating experiments / controls

Executed evidence already available:

- **Hostile source control:** exact `0fc78af.../src/Config.cc` contains raw conflict delimiters in compiled code. This falsifies H1/H2.
- **Descendant comparison:** `0fc78af... -> 3627dc...` is strict ancestry; the only source/test changes remove conflict contamination, plus the CI guard. This falsifies a repair-by-unrelated-rewrite explanation.
- **Exact upstream execution:** Core CI `31548111836` succeeds on `3627dc...` with conflict scan + configure + build + CTest.
- **Negative environment control:** local DNS resolution failure is recorded; it is not converted into a local PASS.

Still required before merge: exact-final-head protected root MC Validation must execute the newly added recursive checkout and C++ validation step successfully. If duplicate push and pull-request required contexts exist, all exact-head contexts must succeed.

## Four sequential AI review passes

### A. Detector-response integration lead

Background: C++ detector simulation integration, submodule provenance, waveform-response software.

Evidence inspected: root #1266 diff/gitlink, exact broken core source, repaired descendant source, upstream Core CI, root workflow.

Strongest counter-hypothesis: `0fc78af...` is still acceptable because it contains the desired measured-impulse fail-closed changes.

Attempted falsifier: inspect exact compiled source at the gitlink. Literal unresolved merge delimiters falsify executability/source closure.

Residual uncertainty: root exact-head CI with the new recursive checkout has not yet run.

Vote: **ACCEPT repin + root exact-pin execution design / BLOCK merge until protected exact-head root CI succeeds**.

### B. Adversarial mechanism / software-provenance reviewer

Background: fault injection, CI threat models, cross-repository dependency integrity.

Evidence inspected: checkout semantics, root workflow, upstream conflict incident, ancestry comparison.

Strongest counter-hypothesis: green protected root tests prove the dependency is good.

Attempted falsifier: inspect root workflow. The pre-repair required job never enabled submodule checkout, so a green result cannot observe dependency compilation.

Residual uncertainty: future workflow edits could silently remove this cross-repository execution gate.

Vote: **REJECT pointer-only/root-Python-only validation / ACCEPT required recursive checkout + dependency execution**.

### C. Independent statistics / validation reviewer

Background: reproducible validation, negative controls, exact-head CI governance.

Evidence inspected: upstream Core CI run `31548111836`, strict ancestry, exact source defect, local DNS failure.

Strongest counter-hypothesis: upstream green CI is enough to merge the root pin immediately.

Attempted falsifier: distinguish upstream object validation from root integration. Root still must prove that its exact tree materializes and executes that object in the protected job.

Residual uncertainty: protected root exact-final-head result pending; no stochastic detector sample participates.

Vote: **ACCEPT upstream software oracle / BLOCK root integration until exact-head required CI succeeds / BLOCK detector inference**.

### D. Claims / provenance reviewer

Background: calibration authority, claim ledgers, code→artifact→claim traceability.

Evidence inspected: #1067 acceptance criteria and comments, campaign ledger, #1266 merge state, core provenance history.

Strongest counter-hypothesis: #1067 can remain scientifically complete because the fail-closed code exists somewhere upstream.

Attempted falsifier: root main currently pins the conflicted implementation, while #1067 still has unresolved source-byte/calibration/resampling/historical-output leaves. Repository state therefore contradicts a COMPLETE label.

Residual uncertainty: none of this identifies a real measured electronics transfer function.

Vote: **REOPEN/REVISE #1067 to PARTIAL/BLOCKED; BLOCK measured-electronics and detector-performance claim promotion**.

## Cross-scale propagation

Micro/software: exact C++ source must be conflict-free and executable.

Meso/integration: root gitlink must name that exact source and protected CI must execute it.

Event/study: any persisted waveform or detector-response result must later bind the exact core identity and runtime kernel/configuration into the output provenance; this atom alone does not establish that artifact-level binding.

Claim: no measured-electronics, timing, pile-up, PID, efficiency, or detector-performance claim is promoted by source/build closure.

## Child atoms / dependencies

- `ARU-ELEC-IMPULSE-RUN-METADATA-SERIALIZATION-001`: bind exact core identity plus SiPM runtime metadata/effective-kernel identity into production output sidecars.
- `ARU-ELEC-IMPULSE-CALIBRATION-CLOSURE-001`: units, polarity, baseline, time zero, normalisation and resampling closure against a real calibration object.
- `ARU-ELEC-IMPULSE-SOURCE-BYTE-BINDING-001`: exact external calibration bytes must bind to parsed numerical samples.
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`: audit outputs previously advertised as measured or generated under ambiguous lineage.
- Upstream `ARU-CORE-MAIN-PROTECTION-001` (#17): live branch/ruleset enforcement remains separate from the repository-owned conflict scan already merged in core #18.

## Claim / data boundary

No beam bytes, production Geant4 population, measured single-PE/electronics waveform, DATA↔MC comparison, timing/PID metric, efficiency, rate, ESS, p-value, or detector-performance result was generated or promoted. This is software/integration/provenance evidence only.

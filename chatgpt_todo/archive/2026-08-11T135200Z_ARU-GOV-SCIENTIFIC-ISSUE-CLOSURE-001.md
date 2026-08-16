# ARU-GOV-SCIENTIFIC-ISSUE-CLOSURE-001 — scientific issue completion must follow evidence gates

**Status:** PARTIAL / GOVERNANCE_DEFECT_REPAIRED_FOR_1057 / PREVENTIVE_CONTRACT_DOCUMENTED

## Selected atom

Repository issue state is itself a scientific-provenance observable when an issue represents an atomic research universe. A merged implementation must not silently become equivalent to whole-universe completion when material child atoms, acceptance criteria, or claim gates remain unresolved.

This atom was selected from protected `main@e76482cf03fd15838a8e098b8c2d9ae43ab3b364` after inspecting recent commits, PR #1216, issue #1057, CL-021, Geant4 reproduction documentation, the current CI workflow, and `chatgpt_todo` coordination.

## Exact input/output contract

Inputs:
- issue body and acceptance criteria for atomic universe `I`;
- all material child atoms `C_i` explicitly retained by the issue/PR/handoff;
- merged PR scope and stated limitations;
- claim/provenance gates coupled to `I`;
- exact repository commit and issue state transition.

Output:
- `OPEN/PARTIAL` while any material completion condition is unresolved;
- `CLOSED/COMPLETED` only when the issue's declared scientific acceptance contract is satisfied or the issue is explicitly superseded by a complete, cross-linked successor with no loss of blockers.

Scientific meaning: `closed/completed` must mean the represented research universe has met its completion contract, not merely that one bounded implementation landed.

## Invariant

For material child gates `G_k` and cross-scale compatibility predicate `X`,

`COMPLETE(I) => (AND_k G_k == ACCEPTED) AND X == PASS`.

Conversely,

`exists k: G_k in {NOT_STARTED, TRIAGED, ACTIVE, PARTIAL, FLAWED, BLOCKED} => COMPLETE(I) = false`

unless the issue has been explicitly superseded and every unresolved child is transferred to a named successor without claim promotion.

Repository merge and scientific completion are distinct state variables:

`MERGED(implementation) != COMPLETE(research_universe)`.

## Live contradiction found

PR #1216 explicitly stated that it **does not close #1057** and listed four unresolved children: compiled/seeded Geant4 source closure, accepted-observable closure, polarization provenance, and production source-model serialization. The preceding #1057 review also voted `BLOCK issue closure`.

The squash merge nevertheless produced commit `e76482cf03fd15838a8e098b8c2d9ae43ab3b364` whose message contained `Closes #1057`, and GitHub marked #1057 `closed/completed` automatically. That issue state contradicted the merged PR's own scientific scope and the issue's unchecked acceptance criteria.

This run reopened #1057 with state reason `reopened` and added a provenance comment enumerating the unresolved leaves. The merged source implementation remains on `main`; only the incorrect parent-completion state was repaired.

## Competing mechanisms

### H1 — merge implies scientific completion
Rejected. PR #1216 itself says its Python/static CI does not compile or run the modified Geant4 source, and #1057 requires downstream geometry/trigger/support closure.

### H2 — issue closure is merely administrative and can coexist with unresolved scientific leaves
Rejected for atomic-universe issues because repository state is used as coordination evidence. Closing a P0 parent while its own acceptance leaves remain open creates a false completion signal for later AI/human review.

### H3 — close the implementation issue and transfer every remaining leaf to explicit successors
Potentially valid only when the parent is explicitly scoped as an implementation-only issue and every material unresolved condition is transferred without loss. This is how #1182 is currently documented: a later comment explicitly states that the source-readiness implementation issue may remain closed while separate runtime/path children own the remaining provenance gates. That explicit transfer is not equivalent to the accidental #1057 auto-close.

### H4 — keep #1057 open after the bounded implementation merge
Survives. It preserves the issue's original acceptance semantics and is the current repaired state.

## Discriminating evidence / negative controls

1. **PR-scope control:** #1216 body says `does not close #1057` and names unresolved children.
2. **Issue-body control:** #1057 acceptance criteria include full-vs-proposal accepted-observable closure, support coverage, and rate/normalization governance; these are not satisfied by the static source edit.
3. **CI-scope control:** current MC Validation CI runs Python 3.11 ruff + pytest and does not build the HIBEAM Geant4 application.
4. **Claim control:** `docs/validation/CL-021_scattering_model.md` remains `OPEN — hypothesis FALSIFIED; source model remains GATED` and explicitly requires compiled seeded source closure and detector-chain propagation.
5. **Counterexample control (#1182):** unlike #1057, #1182 has an explicit later comment stating it can remain closed as the completed source-readiness implementation issue while separately named children own remaining runtime/path provenance. This prevents over-generalizing the rule to “every issue with any downstream dependency must stay open.”

## Four sequential AI review passes

### (a) Source/physics lead — ACCEPT state repair / BLOCK source-physics completion
Evidence inspected: #1057 body/comment, #1216 body/merge, CL-021, Geant4 reproduction status. Strongest counter-hypothesis: the full-2pi source code merge is the scientifically decisive fix. Falsifier: no compiled/seeded event population or geometry/trigger accepted-observable comparison exists in the merged validation. Residual uncertainty: actual HIBEAM runtime availability and beam polarization. Vote: **ACCEPT reopening / BLOCK #1057 completion**.

### (b) Adversarial mechanism reviewer — REJECT merge-equals-complete semantics
Evidence inspected: automatic close trigger in the squash commit versus explicit non-closing PR text. Strongest counter-hypothesis: downstream children are discoverable elsewhere, so parent closure is harmless. Falsifier: #1057 itself is P0 and its own acceptance checklist remains unresolved; later automation can reasonably treat closed/completed as a completion signal. Residual uncertainty: no repository-level automated guard currently prevents future accidental close keywords. Vote: **REJECT accidental completion state / ACCEPT repaired open state**.

### (c) Independent statistics/validation reviewer — ACCEPT governance falsifier / BLOCK physics inference
Evidence inspected: current workflow and #1216 validation record. Strongest counter-hypothesis: exact-head green CI is sufficient validation. Falsifier: workflow contains no Geant4 build/run stage and no generated event sample. Residual uncertainty: compiled closure requires an environment containing the pinned HIBEAM/Geant4 toolchain. Vote: **ACCEPT deterministic governance finding / BLOCK generator and detector inference**.

### (d) Claims/provenance reviewer — ACCEPT provenance repair / BLOCK CL-021 promotion
Evidence inspected: CL-021 and reproduction-status gates. Strongest counter-hypothesis: issue state is independent of public claim state. Falsifier: project coordination and claim governance explicitly use issue/atom status to track unresolved dependencies. Residual uncertainty: downstream claim surfaces must continue to reference the reopened parent correctly. Vote: **ACCEPT issue-state correction / BLOCK public physics promotion**.

## Child atoms spawned

- `ARU-GOV-MERGE-CLOSE-KEYWORD-001`: define a practical fail-closed review rule for auto-close keywords on scientific-universe PRs whose bodies declare unresolved children. Do not add a network-dependent CI gate without a reproducible GitHub-event contract.
- Existing scientific leaves under #1057 remain: `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001`, `ARU-MC-SOURCE-PHI-ACCEPTANCE-CLOSURE-001`, `ARU-MC-SOURCE-PHI-POLARIZATION-001`, `ARU-MC-SOURCE-PHI-PROVENANCE-SERIALIZATION-001`.

## Claim/wiki implications

No detector claim is promoted. The full-2pi implementation on main is a bounded source-model change. #1057 remains P0/open and CL-021 remains gated. Any public statement implying the full source/acceptance problem is solved must remain blocked until the surviving children and cross-scale compatibility checks pass.

## Repository actions in this run

- reopened #1057 from `closed/completed` to `open/reopened`;
- added an issue comment documenting the accidental auto-close and unresolved child atoms;
- opened this coordination branch from exact current main for a durable repository handoff.

No production Geant4 campaign, beam ROOT inspection, detector simulation, rate, B2/B8, PID, timing, calibration, pile-up, ESS, p-value, or DATA/MC result was produced in this atom.

## Next highest-value atom

`ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001`: compile the exact reviewed `ScatteringGenerator.cc/.hh` in a provenance-bound HIBEAM tree and execute a seeded generator-level closure. The current repository CI is Python/static only, while `geant4/setup_and_run.sh` depends on host-local `nnbar_env`, Geant4/VGM paths, an external checkout, and mutable staged inputs. If that execution environment is unavailable, record the precise blocker rather than treating static CI as compiled validation, then move to the next independent scientific leaf.

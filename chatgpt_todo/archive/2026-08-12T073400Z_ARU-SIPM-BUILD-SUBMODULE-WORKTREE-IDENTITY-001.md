# ARU-SIPM-BUILD-SUBMODULE-WORKTREE-IDENTITY-001

Status: **ACTIVE / PRE-CI**  
Parent: #977  
Exposed by: merged PR #1285  
Implementation branch: `audit/sipm-submodule-worktree-identity-v1`  
Exact branch base: `main@4376a3f88c8e059a5c1a92c020856c98d31f538b`  
Exact pinned core gitlink at base: `3627dc87137a9f33f511a755671414b11853c0a0`

## Atomic contract

Inputs:

- exact superproject repository/worktree;
- superproject HEAD `H_root`;
- gitlink entry at `geant4/single_stave/sipm`, `H_link`;
- materialized nested path `W_core`;
- nested Git HEAD `H_core`;
- nested tracked/untracked worktree state.

Output: an authorising source block for a build receipt only if all of the following hold:

1. `gitlink(H_root, core_path) = H_link` and the entry is mode `160000 commit`;
2. `W_core` is an independent Git worktree whose reported top-level directory equals the configured core path;
3. `H_core = H_link` exactly as canonical nonzero 40-hex Git object identity;
4. the nested tracked/untracked status is clean when authorising cleanliness is required;
5. the existing superproject cleanliness contract also passes.

A detached nested HEAD is valid because branch attachment is not the measurand. Ignored files are not included in `git status --untracked-files=all`; their possible build influence remains an explicit child.

## Scientific/provenance meaning

The build receipt is intended to identify the actual source state from which `ccb_stave_sim` was compiled. The superproject gitlink identifies intended nested source, but it is not itself evidence that those nested bytes were materialized in the build worktree. This atom is execution/source provenance only; it has no detector observable, physical unit, event population, or calibrated response measurand.

## Competing mechanisms

### H1 — outer clean status plus exact gitlink proves nested source

Rejected. A deterministic Git fixture showed that the superproject can remain clean when the gitlink path is merely an empty directory or contains ordinary non-Git descendant content.

### H2 — directory existence proves nested source

Rejected. A non-Git lookalike directory under the gitlink path also left outer status clean.

### H3 — require `<core>/.git` to be a directory

Rejected as an implementation-specific parameterization. Real submodules and linked worktrees may use a `.git` file. The scientific contract is semantic Git-worktree identity, not filesystem layout.

### H4 — semantic nested repository check

Survives: resolve `git -C <core> rev-parse --show-toplevel`, require it to equal the configured core path, require nested `HEAD == H_link`, and inspect nested status directly. Top-level equality is required because Git invoked from an empty descendant directory can discover the parent superproject.

### H5 — content-hash every nested file independently of Git

Potentially stronger for non-Git/ignored/generated-source threats, but not required to close this bounded child and not observationally equivalent to the existing Git source-intent model. Spawned as a separate ignored/generated-source influence child.

## Equations / invariants / limiting cases

Authorising source-worktree identity:

`PASS_source => H_core = H_link = gitlink(H_root, core_path)`

and

`PASS_source => top_level(W_core) = canonical(core_path)`

and, when authorising cleanliness is requested,

`PASS_source => status_root = CLEAN AND status_core = CLEAN`.

Limiting cases:

- clean independent nested worktree at exact gitlink: PASS;
- detached nested HEAD at exact gitlink: PASS;
- empty gitlink directory: FAIL;
- non-Git lookalike directory: FAIL;
- nested Git HEAD different from gitlink: FAIL;
- nested tracked or ordinary untracked change: FAIL under authorising cleanliness;
- ignored nested file: not decided by this atom; explicitly residual.

## Executed discriminating experiment

Environment: Linux container, Git `2.47.3`; no RNG.

Procedure:

1. initialize temporary superproject and commit `README`;
2. initialize nested Git repository at `geant4/single_stave/sipm`, commit one core file;
3. install nested commit as superproject mode-160000 gitlink with `git update-index --cacheinfo` and commit;
4. verify outer `git status --porcelain=v1 --untracked-files=all` is exactly empty;
5. remove nested Git repository and recreate only the empty directory;
6. rerun outer status;
7. add ordinary non-Git content under that directory and rerun outer status;
8. separately create a different nested Git HEAD and inspect outer/nested status.

Observed exact qualitative results:

- correct nested worktree: outer status `''`;
- empty gitlink directory: outer status `''`;
- non-Git descendant content at gitlink path: outer status `''`;
- wrong nested Git HEAD: outer status ` M geant4/single_stave/sipm`;
- dirty nested tracked source: outer status ` M geant4/single_stave/sipm`, nested status ` M CORE`.

A second fixture showed ordinary nested untracked content is surfaced as outer submodule modification, while a nested ignored file can leave both ordinary nested status and outer status clean; `git status --ignored` exposes the ignored file. This motivates, but does not resolve, the ignored-source child.

This is deterministic Git/provenance evidence, not detector simulation or beam evidence.

## Implementation

Branch base: `4376a3f88c8e059a5c1a92c020856c98d31f538b`.

Production commit `ed9902718e0cba3ae195a630ab0b96721e9249fd`:

- upgrades authorising receipt schema from `ccb-single-stave-build-receipt/1` to `/2`;
- adds `_core_worktree_identity()`;
- requires semantic independent nested Git top-level equality;
- requires nested `HEAD == superproject gitlink`;
- requires nested tracked/untracked cleanliness for authorising receipt creation;
- serializes `ccb_sipm_core_worktree_head` and `ccb_sipm_core_worktree_clean_at_receipt`;
- makes v1 receipts non-authorising under the strengthened contract;
- records `IGNORED_CCB_SIPM_CORE_FILES_NOT_ATTESTED` as an explicit limitation.

Focused-test commit `af6932d5a1340f110fff43fb521b1aa291b5b29d` adds `tests/test_sipm_submodule_worktree_identity.py` with six deterministic controls:

1. exact nested worktree PASS and serialized state;
2. empty gitlink directory FAIL while outer status is provably clean;
3. non-Git lookalike content FAIL while outer status is provably clean;
4. nested HEAD mismatch FAIL;
5. dirty nested tracked source FAIL at the nested contract;
6. legacy schema-v1 receipt FAIL.

## Four sequential AI review passes

### A. Build/provenance lead

Evidence inspected: merged #1285 contract/limitations, current `sipm_build_receipt.py`, exact base gitlink, deterministic Git fixtures.

Strongest counter-hypothesis: exact gitlink plus clean superproject status is already a complete source identity.

Attempted falsifier: delete the nested repository while preserving the gitlink and inspect outer status.

Result: outer status remains clean. Counter-hypothesis rejected.

Residual uncertainty: ignored/generated nested files and observation-time races.

Vote: **ACCEPT bounded contract and repair / BLOCK #977 COMPLETE pending CI and residual children**.

### B. Adversarial mechanism reviewer

Evidence inspected: empty directory, non-Git lookalike, wrong nested HEAD, dirty nested source, Git parent-discovery behavior.

Strongest counter-hypothesis: checking that the path exists or that `git rev-parse` succeeds is enough.

Attempted falsifier: invoke Git from a non-Git descendant path under the superproject; Git can discover the parent repository. Therefore top-level equality is required.

Residual uncertainty: symlink/path alias edge cases and ignored source influence.

Vote: **REJECT outer-clean/path-exists formulations / ACCEPT semantic top-level+HEAD model**.

### C. Independent statistics/validation reviewer

Evidence inspected: deterministic no-RNG fixture design and focused regression matrix.

Strongest counter-hypothesis: the observed empty-directory behavior is a one-off numerical/statistical effect.

Falsifier: no stochastic estimator exists; the state transition is deterministic Git semantics. Protected exact-head repository CI is still required to validate implementation integration.

Residual uncertainty: cross-version Git behavior will be exercised by CI but not yet observed for this head.

Vote: **ACCEPT deterministic falsifier / REVISE pending exact-head CI / BLOCK detector inference**.

### D. Claims/provenance reviewer

Evidence inspected: #977 parent acceptance criteria, #1280/#1282/#1284/#1285 provenance chain, current claim boundary.

Strongest counter-hypothesis: source-worktree closure completes the detector-response provenance parent.

Attempted falsifier: parent still lacks operating-point closure (#1072), measured-electronics authorization/historical audit (#1067), ignored/generated-source decision, full compiler/link/runtime-loader attestation and broader detector-response evidence.

Residual uncertainty: historical authorising outputs under receipt schema v1 need audit/quarantine semantics.

Vote: **ACCEPT bounded source-worktree repair / KEEP #977 OPEN/PARTIAL and public detector claims gated**.

## Cross-scale propagation

Micro/source layer: distinguishes intended gitlink from actual materialized nested source worktree.

Build layer: receipt schema v2 can bind compile-time root/core labels and executable bytes to an exact nested source worktree rather than only a gitlink.

Campaign layer: when combined with merged campaign source intent and build-receipt checks, stale/missing/mis-materialized core worktrees fail before an authorising receipt can be created.

Study/claim layer: no detector result is promoted. Receipt schema v1 is no longer sufficient for newly authorising source-worktree identity; historical outputs need separate governance.

## Child atoms spawned / retained

- `ARU-SIPM-BUILD-IGNORED-SOURCE-INFLUENCE-001` — determine whether ignored/generated files under ccb-sipm-core can affect compilation and, if so, bind or reject them;
- existing mutate-and-restore / time-of-check race child;
- exact compiler/link invocation attestation;
- runtime dynamic-library image identity;
- shared launcher/verifier byte binding;
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`;
- #1072 requested/effective operating-point closure;
- #1067 measured-electronics source/calibration authorization.

## Validation boundary / next gate

No local repository clone was available because the execution container could not resolve `github.com`; the independent Git fixtures above executed locally, but the exact repository branch has not yet passed protected CI. Open a draft PR and require exact-final-head MC Validation before merge. Do not treat a red/pending head as authorising.

No beam bytes, production Geant4 population, measured SiPM/electronics calibration, timing/PID metric, rate, efficiency, ESS, p-value, or detector-performance quantity was generated or promoted.

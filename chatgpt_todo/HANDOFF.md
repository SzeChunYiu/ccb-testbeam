# Latest Handoff

## Selected atom: exact external source overlay provenance before Geant4 compilation

Protected `main` entered this session at `774eda1b1180098c7e00757db312ede41491094b`, after PR #1197 recorded the validated CI-routing milestone and resumed #1182. The static readiness/source-parity repair is already on main through #1183; #1178, #1179, #1058 and CL-021 remain open/gated.

### Atomic contract and contradiction resolved

The reviewed deployment helper `geant4/src_patch/patch_scatter.py` intentionally installs the repository-reviewed `ScatteringGenerator.hh/.cc` bytes into an external `hibeam_g4` checkout. Unless the pinned upstream commit already contains identical bytes, a correct installation necessarily makes those tracked external paths differ from `HEAD`. Therefore the shorthand contract “exact upstream commit/tree + clean Git state + reviewed installed pair” is over-constrained: generic cleanliness and a legitimate overlay can be mutually exclusive.

The source identity is instead decomposed into two layers:

1. **Pinned baseline:** external `HEAD` and `HEAD^{tree}` must equal exact approved values supplied by the run specification.
2. **Allowed overlay:** the Git index remains clean; no untracked paths are present; every visible work-tree delta is an unstaged modification of only `include/ScatteringGenerator.hh` or `src/ScatteringGenerator.cc`; both external paths are regular non-symlink files byte-identical to `geant4/src_patch/ScatteringGenerator.hh/.cc`. A zero-delta baseline is allowed only when upstream already contains the reviewed bytes.

This collapses two observationally equivalent correct states—upstream-already-equal and pinned-baseline-plus-reviewed-overlay—while excluding arbitrary dirty trees.

### Implementation and discriminating tests

Branch `audit/geant4-build-frontdoor-provenance` adds schema `ccb_geant4_external_overlay_v1` in `tools/audit/validate_geant4_external_overlay.py` and focused tests in `tests/test_geant4_external_overlay.py`; both are added to the curated ruff lane.

The deterministic fixture matrix creates temporary Git repositories and tests:

- exact two-file unstaged reviewed overlay — expected PASS;
- clean upstream already byte-identical to the reviewed pair — expected PASS;
- interrupted deployment where only one file is replaced — BLOCK on pair mismatch;
- extra tracked mutation outside the overlay — BLOCK;
- untracked source path — BLOCK;
- staged/index mutation of an overlay file — BLOCK;
- exact clean baseline with wrong source bytes — BLOCK;
- wrong expected `HEAD` commit or tree — BLOCK.

The validator snapshots Git status before and after byte verification and rejects a status transition during inspection. Required source paths are rejected if they are symlinks or non-regular files. This closes the static logical gap only; it does not make mutable path verification equivalent to an immutable compiled-source snapshot.

### Competing mechanisms and eliminations

- **H1: require completely clean external Git state at build time.** Rejected as a universal rule because the approved overlay itself can be the only expected delta.
- **H2: ignore dirty state once the reviewed pair matches.** Rejected because unrelated tracked/untracked modifications could alter the executable while the pair still matches.
- **H3: pin upstream commit/tree and permit exactly the reviewed pair as the only unstaged delta.** Survives and is implemented.
- **H4: permit staged overlay changes as equivalent.** Rejected for this front door because index state becomes an additional mutable provenance layer with no scientific need.
- **H5: trust the overlay installer’s successful return without pre-build re-verification.** Rejected because the installer explicitly documents that its two-path replacement is not crash-atomic.

### Four sequential AI review passes

- **Source/build lead — ACCEPT static overlay decomposition / BLOCK compiled authorisation.** Evidence: current installer contract, mutable historical setup script, exact baseline/overlay model. Strongest counter-hypothesis: generic `git clean` is sufficient. Falsifier: a correct reviewed overlay on a differing upstream commit is necessarily dirty. Residual: approved upstream commit/tree and actual compiled source snapshot are still absent.
- **Adversarial mechanism reviewer — ACCEPT exact allow-list / BLOCK mutable post-check build.** Evidence: interrupted-install, staged, untracked and extra-dirty fixtures. Strongest counter-hypothesis: matching the two source files alone is enough. Falsifier: unrelated source mutations remain possible and are rejected. Residual: mutation after the validator returns but before/during compilation.
- **Independent validation reviewer — ACCEPT deterministic Git/byte-state falsifiers / BLOCK physics inference.** No stochastic or detector model enters this atom. Residual: compiler/toolchain/runtime state and hostile compiled fixtures.
- **Claims/provenance reviewer — ACCEPT local provenance contract / BLOCK CL-021 promotion.** Passing schema `ccb_geant4_external_overlay_v1` can authorise only the source-identity precondition. It does not validate a generated angular population, event weight, detector response, or DATA↔MC result.

### Repository actions

Stale PR #1195 was independently compared with current main and closed without merge because it reintroduced two already-rejected mechanisms: the event-zero source-loading gate and finite `pull_request.paths` routing. The validated readiness fix remains the main implementation; no scientific result was discarded.

### Remaining child atoms

Even if the overlay PR passes CI, #1182 remains open. The next build/run front-door children are: content-bound staged-input identity at consumption rather than historical pathnames alone; a build source/input snapshot or equivalent re-verification that survives post-check mutation; compiler/Geant4/VGM/CMake/executable identity; run-manager/thread mode; random engine/seeds/event count/model IDs; compiled missing/malformed/reconfigured source and stopping fixtures; explicit `CSFile=null` control; repeated readiness; output hash/manifest binding; and downstream detector-response closure.

No beam ROOT data or production Geant4 campaign was executed, and no B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.

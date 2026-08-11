# ARU-MC-G4-OVERLAY-PROVENANCE-001

Status: `ACTIVE / STATIC_IMPLEMENTATION_ON_PR / EXACT_HEAD_CI_REQUIRED / COMPILED_RUNTIME_BLOCKED`

Parent: #1182 / `ARU-MC-CS-COMPILED-PROVENANCE-001`  
Related: #1178, #1179, #1058, CL-021

## Exact atom

Determine the only external `hibeam_g4` Git/work-tree states that are authorised to enter compilation after applying the repository-reviewed CCB `ScatteringGenerator` overlay.

### Inputs

- external Git work tree root;
- approved exact `HEAD` commit ID;
- approved exact `HEAD^{tree}` ID;
- reviewed repository payloads:
  - `geant4/src_patch/ScatteringGenerator.hh` -> external `include/ScatteringGenerator.hh`;
  - `geant4/src_patch/ScatteringGenerator.cc` -> external `src/ScatteringGenerator.cc`.

### Output

Schema `ccb_geant4_external_overlay_v1`, `PASS` only when the exact pinned baseline and exact reviewed overlay compose without any other visible Git mutation.

Units: none. This is a provenance/state atom, not a detector measurand.

Scientific meaning: passing this atom establishes only that the source bytes presented to the next build step are the reviewed CCB overlay applied to the declared upstream baseline. It does not establish compiled executable identity or physics validity.

## Competing descriptions

1. `HEAD/tree exact AND git status completely clean`.
2. `reviewed pair matches; ignore all other dirtiness`.
3. `HEAD/tree exact AND only the reviewed pair may appear as unstaged work-tree deltas`.
4. `HEAD/tree exact AND staged reviewed pair is equivalent to unstaged overlay`.
5. `successful patch_scatter.py return is enough; no pre-build re-check`.

Descriptions 1 and 3 become equivalent only when the pinned upstream pair already equals the reviewed payload. Otherwise 1 is over-constrained. Description 2 is under-constrained. Description 4 introduces an unnecessary index-state dependency. Description 5 ignores the installer’s explicit non-transactional two-path boundary.

## Invariants

Let `C` be approved external `HEAD`, `T=tree(C)`, `A` the set of allowed overlay paths, `D` visible Git deltas, and `B(p)` file bytes.

Required:

- `HEAD == C`;
- `HEAD^{tree} == T`;
- no index/staged mutation;
- no untracked path;
- `D subseteq {unstaged modification of p : p in A}`;
- for every `p in A`, `B_external(p) == B_reviewed(p)`;
- all required paths are regular non-symlink files;
- Git status is unchanged across the byte-verification interval.

Passing with `D = empty` is allowed only because the byte equality condition independently proves that upstream already contains the reviewed pair.

## Eliminated mechanisms

- Generic clean-tree requirement as a universal post-overlay gate: incompatible with a legitimate overlay when upstream differs.
- Pair-only byte check: unrelated tracked/untracked changes can still alter a build.
- Staged-overlay equivalence: index contents become another mutable, nonessential provenance layer.
- Installer-return-only authority: an interrupted two-path deployment can leave one reviewed and one stale file.

## Surviving mechanism

Exact pinned baseline plus an allow-listed, unstaged, byte-exact reviewed two-file overlay and no other visible Git mutation.

Nuisance/dependency variables: approved upstream commit/tree, filesystem mutation after validation, ignored/generated files, external build system behavior, compiler/toolchain/runtime state, and staged run-input identities.

## Discriminating experiments implemented

Temporary Git fixtures, no RNG:

1. two-file reviewed unstaged overlay -> PASS;
2. clean baseline already equal -> PASS;
3. one-file interrupted overlay -> BLOCK;
4. extra tracked mutation -> BLOCK;
5. untracked path -> BLOCK;
6. staged overlay -> BLOCK;
7. clean baseline with wrong source bytes -> BLOCK;
8. wrong expected commit -> BLOCK;
9. wrong expected tree -> BLOCK.

Exact files:

- `tools/audit/validate_geant4_external_overlay.py`
- `tests/test_geant4_external_overlay.py`
- `.github/workflows/mc_validation_ci.yml` curated lint list

## Cross-atom propagation

This local gate composes upstream source identity as:

`approved hibeam_g4 baseline -> reviewed CCB overlay -> pre-build source identity`.

It does **not** yet compose to:

`compiled executable -> runtime source/input state -> generator distribution -> event weights -> detector response -> DATA-like reconstruction -> held-out comparison -> claim`.

Therefore #1182 remains open even if this PR is validated.

## Four sequential AI reviews

### Domain/source-build lead — ACCEPT local state model / BLOCK runtime
Evidence: `patch_scatter.py`, `setup_and_run.sh`, #1182 current main state.  
Strongest counter-hypothesis: a clean checkout is the only reproducible checkout.  
Attempted falsifier: install a correct reviewed overlay on a differing pinned baseline; the checkout becomes intentionally dirty.  
Residual uncertainty: approved upstream production pin and compiled snapshot.  
Vote: **ACCEPT / REVISE parent**.

### Adversarial mechanism reviewer — ACCEPT allow-list / BLOCK post-check mutation
Evidence: partial deployment and extra-dirty mechanisms.  
Strongest counter-hypothesis: source pair equality alone is enough.  
Attempted falsifiers: extra tracked file, untracked path, staged path, one-file overlay.  
Residual uncertainty: mutation after validator return and ignored/generated build artifacts.  
Vote: **ACCEPT local / BLOCK build authorisation**.

### Independent statistics/validation reviewer — ACCEPT deterministic closure / BLOCK inference
Evidence: exact Git/object/byte predicates; no stochastic estimator.  
Strongest counter-hypothesis: green Python CI validates the source physics.  
Attempted falsifier: none of the tests executes the generator or samples an angle.  
Residual uncertainty: compiled hostile fixtures, seed/thread/runtime state.  
Vote: **ACCEPT software falsifiers / BLOCK physics inference**.

### Claims/provenance reviewer — ACCEPT pre-build provenance gate / BLOCK CL-021
Evidence: current claim dependency graph and historical MC overclaim audit.  
Strongest counter-hypothesis: reviewed C++ bytes alone validate CL-021.  
Attempted falsifier: compiled executable/source/input/output identities remain unbound.  
Residual uncertainty: all downstream chain atoms.  
Vote: **ACCEPT local provenance / BLOCK claim promotion**.

## Repository actions

- Branch: `audit/geant4-build-frontdoor-provenance` from protected `main@774eda1b1180098c7e00757db312ede41491094b`.
- Stale PR #1195 closed without merge after independent diff review: it reintroduced the event-zero initialization gate and finite required-PR path filtering already rejected on main.
- Exact-head CI for this atom is required before merge; no validation claim is made until it completes successfully.

## Child atoms spawned

1. Exact staged-input bytes at consumption/build/run boundary, not historical pathnames alone.
2. Build-source/input snapshot or equivalent mutation-resistant re-verification.
3. Compiler/Geant4/VGM/CMake/executable identity.
4. Run-manager/thread/random-engine/seed/event-count identity.
5. Compiled hostile source/stopping fixtures and explicit uniform control.
6. Output identity plus complete run manifest.

No beam or production Geant4 data were generated or promoted in this atom.

# Latest Handoff

## Selected atom: bind the validated Geant4 source/input state to the built executable

Protected `main` advanced from `774eda1b1180098c7e00757db312ede41491094b` to `17349d0a72a267723b805615480e76519ed7b8a8` after PR #1198 passed exact-head MC Validation and was squash-merged. The merged `ccb_geant4_external_overlay_v1` gate proves only a pre-build external baseline/reviewed-overlay state. #1182 remains open; CL-021 and detector inference remain gated.

### New atomic contract

`ARU-MC-G4-BUILD-BINDING-001` asks whether the source and staged-input bytes observed before compilation can be bound to a resulting executable without pretending that a mutable path is an immutable build snapshot.

The implemented two-phase contract is:

- `begin`: re-use the exact #1198 external-overlay validator and record each declared staged input from one opened regular non-symlink stream as `(label, resolved path, bytes, sha256)`; store the explicit build-contract JSON and a canonical receipt digest.
- `finalize`: verify the begin receipt digest, re-run the external source validator, require the source projection to match the begin state exactly, re-hash all staged inputs and require exact identity, then record the resulting regular non-symlink executable by SHA-256/byte count. The final canonical receipt binds to the begin receipt digest.

This detects persistent source/input changes between the two build boundaries and creates an exact executable identity. It does **not** prove that no transient mutate-and-restore occurred between observations, nor does declared toolchain metadata constitute independent compiler/Geant4/VGM attestation.

### Competing mechanisms

- **Pre-build source validation only:** insufficient; a later staged input or source mutation can affect compilation/run.
- **Executable hash only:** insufficient; it identifies bytes without attributing them to approved source/input state.
- **Pre/post source+input identity plus executable hash:** survives as the strongest bounded observable contract available without an immutable build sandbox.
- **Treat two observations as immutable consumption identity:** rejected; transient mutate-and-restore is observationally invisible.
- **Path/stat-only provenance:** rejected; the implementation hashes byte count and SHA-256 from the same opened file stream and rejects symlinks/non-regular files.

### Implementation and falsifiers

Branch `audit/geant4-build-binding-receipt` adds `tools/audit/geant4_build_binding_receipt.py`, `tests/test_geant4_build_binding_receipt.py`, curated ruff coverage, and archive `2026-08-10T235000Z_ARU-MC-G4-BUILD-BINDING-001.md`.

The deterministic fixtures encode unchanged source/input/executable success; source mutation failure; staged macro mutation failure; symlink input/executable failure; begin-receipt tampering failure; duplicate semantic labels/physical paths failure; empty build-contract failure; and canonical receipt digest presence. Exact-head CI is required before this implementation is called validated.

### Four sequential AI review passes

- **Build/source provenance lead — REVISE.** Accept the two-boundary primitive; block compiled-physics authorisation. Residual: toolchain identity is declared, not independently measured.
- **Adversarial mechanism reviewer — ACCEPT bounded detector / BLOCK immutable-build claims.** The strongest counterexample is transient source/input mutation restored before `finalize`.
- **Independent validation reviewer — ACCEPT deterministic integrity oracle / BLOCK inference.** No generated angles, weights, seeds, event counts or detector observables enter this atom.
- **Claims/provenance reviewer — BLOCK CL-021 promotion.** Executable identity alone lacks independently attested dependencies, runtime provenance and physics closure.

### Next child atoms

After exact-head CI, keep #1182 open and move to an immutable source/input snapshot or build sandbox, independently measured compiler/CMake/Geant4/VGM and linked-library identity, runtime run-manager/thread/random-engine/seeds/event count/model IDs, output file/tree/schema/hash identity, and compiled hostile source/stopping controls. A parent claim cannot be promoted until these material children and downstream detector-response compatibility pass.

No beam ROOT bytes or production Geant4 campaign were executed in this environment, and no angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.

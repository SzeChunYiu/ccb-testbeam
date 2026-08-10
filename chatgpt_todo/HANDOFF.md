# Latest Handoff

## Session

- **Task ID:** `ARU-S00-PUBLICATION-CONTENT-IDENTITY-001`
- **Stamp:** `2026-08-10T074800Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial main:** `5cb0b9426dc2f9e1b58a33fcb36c2e0c3eaa8f0a`
- **Validated merge this session:** PR #1145 -> `ef4f3cbabe010285558a425fc3e92d525b1803a2` after exact-head MC Validation CI run 919 = `success`.
- **Issue:** #1147
- **Parent:** #1110
- **Branch / PR:** `fix/s00-publication-content-identity` / #1148
- **Status:** `CONTENT_IDENTITY_IMPLEMENTED_PENDING_EXACT_HEAD_CI`

## Selected atom

The child atom introduced by the immutable-generation fix is byte identity:

```text
logical artifact path
-> physical in-generation regular file
-> SHA-256(bytes)
-> content-bound CURRENT.json pointer
-> verified resolver
```

The required provenance invariant is:

```text
same pointer bytes + same generation_id + changed artifact bytes
=> resolver failure, never silent authority
```

A second invariant rejects path aliases:

```text
resolved artifact must remain physically inside the named generation
AND no artifact path component may be a symbolic link
```

## Evidence / mechanism collapse

The v1 primitive merged in #1145 was transactionally stronger than the legacy mutable-directory replacement, but its authority tuple was still only `(generation_id, relative_path, model_identity)`. Ordinary generation files remained writable, and `resolve_artifact()` checked only `is_file()`. Therefore in-place mutation could change the scientific object without changing the pointer. Separately, lexical `..`/absolute-path checks did not exclude a relative symlink because `Path.is_file()` follows symlinks.

Rejected alternatives:

- path-only "immutable" policy: no byte identity;
- chmod-only read-only generations: permissions are mutable and are not provenance proof;
- content-addressed generation ID alone: partial, but still requires complete artifact hashing and validation.

Survivor: per-artifact SHA-256 binding in the pointer plus physical-containment / symlink rejection and resolver-time hash verification.

## Work completed

1. Opened #1147 as the non-duplicative child atom under #1110.
2. Advanced pointer schema to `ccb.s00.publication-pointer.v2` before any production pointer integration.
3. Added `artifact_sha256` to `S00PublicationPointer` and its JSON payload.
4. Added strict lowercase 64-hex SHA-256 parsing and exact key parity between `artifacts` and `artifact_sha256`.
5. Added physical containment validation using resolved paths and explicit rejection of symlink components.
6. Hash and fsync every authoritative artifact while still in staging.
7. Revalidate containment and SHA-256 after the staging->generation move and before pointer commit.
8. Make `resolve_artifact()` recompute SHA-256 and fail closed on content mismatch.
9. Added hostile tests for post-publication manifest/table mutation, external symlink artifact, symlinked parent directory, post-publication symlink substitution, missing digest map, malformed digests, digest-key mismatch, and a staging-directory symlink alias.
10. Updated `ACTIVE_TASK.md`, this handoff, and the immutable ARU archive.

## Audit-the-audit corrections

Two child defects were found while reviewing the first #1148 implementation rather than waiting for CI to expose them:

1. The first physical-path helper changed legacy controlled-error wording for a missing authoritative file. Existing tests separately require `required artifact` during publication and `authoritative artifact missing` during resolution. The controlled error now contains both semantic markers, preserving fail-closed behavior and existing test contracts.
2. Artifact-component checks alone did not reject the staging directory itself being a symbolic link. `publish_generation()` now rejects a symlink staging root before the same-filesystem parent check, and a dedicated hostile regression verifies that no pointer or generation is created and the external target remains untouched.

Any workflow run for a pre-correction head is stale and must not authorize merge. Only exact-head CI after these corrections is acceptable.

## Four sequential review passes

- **Filesystem/reconstruction lead — ACCEPT design / pending exact-head CI.** The authority pointer now identifies bytes rather than only a pathname.
- **Adversarial mechanism reviewer — ACCEPT after artifact + staging symlink and post-move controls / residual direct-bypass risk.** A direct legacy consumer can still bypass verified resolution; that remains #1110 integration work.
- **Statistics/validation reviewer — ACCEPT deterministic contract / pending CI.** Hash equality and path containment are exact software/provenance assertions; no beam-statistical inference is involved.
- **Claims/provenance reviewer — BLOCK claim promotion.** CL-001 and downstream users must not be promoted until producer integration emits v2 pointers and consumers use content-verifying resolution.

## Authoritative sources checked

Python documentation states that `Path.resolve()` makes paths absolute while resolving symbolic links, which supports the physical-containment falsifier. Python's `hashlib` documentation provides SHA-256/file-digest primitives; SHA-256 is used here as byte identity, not as a probabilistic detector-performance claim.

## Next work

1. Require exact-head CI on PR #1148; do not merge on stale checks.
2. Then return to #1110 producer integration: report + selected pulse table in one generation, one pointer commit after all P0 gates.
3. Migrate canonical validators/consumers to `resolve_artifact()` so digest verification cannot be bypassed by mutable legacy paths.
4. Decide legacy-path compatibility semantics and prove they are aliases, never independent authorities.
5. Add crash/concurrent-reader tests around the real producer transition.
6. Keep physical validity of first-four pedestal samples in #1109 separate from this provenance atom.

## Scientific boundary

No raw beam ROOT data were opened, no S00 counts regenerated, no Geant4 simulation run, and no timing/PID/penetration/energy/pile-up/detector-performance quantity changed.
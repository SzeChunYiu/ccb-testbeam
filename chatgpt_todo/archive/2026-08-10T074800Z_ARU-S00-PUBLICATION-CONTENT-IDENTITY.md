# ARU-S00-PUBLICATION-CONTENT-IDENTITY-001

## Atom

`immutable generation path identity -> artifact byte identity -> content-bound authority pointer -> verified downstream resolution`

Parent: #1110. Child issue opened this session: #1147.

## Input/output contract

Input is a completed S00 staging generation plus a logical artifact map. Output is either no authority change or one `CURRENT.json` pointer that identifies a complete generation and the SHA-256 of every authoritative logical artifact.

For artifact `a`:

```text
H(a) = SHA256(bytes(a))
```

Authoritative resolution is valid only if:

```text
realpath(generation / relative_path(a)) is within generation
AND no path component is a symlink
AND SHA256(current bytes(a)) == pointer.artifact_sha256[a]
```

## Mechanism universe

1. **Path-only immutability policy.** Existing #1145 v1 behavior. Rejected because ordinary files remain writable and path identity is not content identity.
2. **Read-only permissions.** Rejected as provenance proof because permissions can be changed and privileged writers can mutate files.
3. **Content-addressed generation identifier only.** Partial but insufficient unless every logical artifact is included in the content computation and all consumers verify it.
4. **Content-bound pointer.** Survivor: bind per-artifact SHA-256 in the pointer, reject symlink/path escapes, and verify digest during resolution.

## Confirmed source-level falsifiers

### Content mutation

The v1 `resolve_artifact()` checked `artifact.is_file()` and returned the path. Therefore:

```text
publish -> modify generation/manifest.json in place -> resolve
```

could return a different byte sequence under the same pointer/generation identity.

### Symlink alias

The v1 lexical path validator rejected absolute paths and `..`, but `Path.is_file()` follows symbolic links. A staging file such as `manifest.json -> /outside/file` could therefore satisfy the required-file test despite not being physically contained in the generation.

## Equivalence collapse

All defenses that merely make accidental modification *less likely* (naming conventions, chmod, retained old generations) are collapsed into one non-authoritative class: they do not establish content identity. The discriminant is whether the authority object cryptographically binds the bytes and whether the consumer re-verifies that binding.

## Implementation

Branch: `fix/s00-publication-content-identity`.

Changes:

- pointer schema advanced to `ccb.s00.publication-pointer.v2` before production integration;
- `artifact_sha256` added to pointer dataclass and JSON;
- strict 64-character lowercase hex digest validation;
- exact logical-name key parity between artifact paths and digests;
- SHA-256 computation and file fsync in staging;
- explicit symlink-component rejection;
- resolved-path containment check;
- post-move containment and digest revalidation before authority commit;
- resolver-time SHA-256 verification;
- hostile regression tests for mutation, symlink escape/substitution, malformed hashes and missing/mismatched hash maps.

## Discriminating tests

- regular file publish/resolve: must pass;
- mutate manifest after publication: resolver must fail hash mismatch;
- mutate selected table after publication: resolver must fail hash mismatch;
- external symlink in staging: publication must fail before authority change;
- symlinked parent directory: publication must fail;
- replace authoritative file with symlink after publication: resolver must fail;
- missing `artifact_sha256`: pointer parse must fail;
- malformed SHA-256 (wrong length/nonhex/uppercase/null): parse must fail;
- artifact/hash key mismatch: parse must fail;
- prior #1145 rollback and pointer-commit fault tests must remain green.

## Four role-separated reviews

### Filesystem / reconstruction lead

Evidence: merged v1 source, pointer schema, resolver semantics, current generation policy.
Strongest counter-hypothesis: path identity plus retained generations is already enough.
Falsifier: in-place edit after publication leaves pointer unchanged but changes bytes.
Vote: **ACCEPT content-bound design / pending exact-head CI**.

### Adversarial mechanism reviewer

Evidence: lexical path validator plus `is_file()` behavior.
Strongest counter-hypothesis: producers are trusted, so symlink aliases do not matter.
Falsifier: provenance must fail closed against accidental or hostile path aliases regardless of producer intent; a symlink can leave the generation namespace while retaining a relative lexical path.
Vote: **ACCEPT after symlink + post-move revalidation / residual direct-bypass risk**.

### Statistics / validation reviewer

Evidence: deterministic byte and path identities.
Strongest counter-hypothesis: hash collision probability requires statistical treatment.
Disposition: SHA-256 is used as exact software provenance identity; no detector-performance confidence statement is inferred. The relevant tests are deterministic equality/failure tests.
Vote: **ACCEPT deterministic design / pending CI**.

### Claims / provenance reviewer

Evidence: CL-001 and downstream artifacts still use legacy paths; producer is not yet on pointer authority.
Strongest counter-hypothesis: hardening the primitive is sufficient to promote claims.
Falsifier: a legacy-path consumer can bypass the resolver and therefore bypass digest verification.
Vote: **BLOCK claim promotion / BLOCK #1110 closure**.

## External authoritative documentation

- Python `pathlib.Path.resolve()` documentation: resolves symbolic links and produces an absolute path, supporting the physical-containment check.
- Python `hashlib` documentation: SHA-256/file hashing is available for deterministic byte identity.

## Scientific boundary

No raw ROOT event sample, MC sample, detector response, S00 count, timing, PID, penetration, energy, or pile-up result is produced or changed by this atom. It governs provenance of future authorized artifacts.

## Next child dependency

Return to #1110 only after this content-bound primitive passes exact-head CI. The real producer must place both the report set and selected pulse table in one generation and publish one v2 pointer after all P0 gates. Downstream validators must resolve through the content-verifying API; legacy paths cannot remain independent authorities.

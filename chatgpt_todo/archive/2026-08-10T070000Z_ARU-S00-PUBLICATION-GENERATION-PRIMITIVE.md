# ARU-S00-PUBLICATION-GENERATION-PRIMITIVE-001

## Session

- Stamp: `2026-08-10T070000Z`
- Initial remote `main`: `5cb0b9426dc2f9e1b58a33fcb36c2e0c3eaa8f0a`
- Parent issue: #1110
- Branch: `fix/s00-publication-generation-primitive`
- Scope: publication commit primitive only; the canonical S00 producer/consumers are not wired to it in this branch.

## Atomic contract

A validated S00 generation must become authoritative without destructively editing the previously authoritative generation. Let `G_k` be an immutable artifact generation and `P` the small authority pointer. The authority state is

```text
A(t) = decode(P(t)).generation_id
```

and the fail-closed invariant is

```text
failure before pointer commit => bytes(P_after) == bytes(P_before)
```

A successful transition is

```text
staging -> immutable G_(k+1) -> fsync -> atomic P_k -> P_(k+1) -> fsync
```

Old generations are not removed on the authorisation path. A crash after the generation move but before the pointer replacement can leave an orphan generation, but it cannot make that orphan authoritative.

## Mechanism universe and equivalence collapse

- **H1 destructive mutable-directory replacement:** current `atomic_publish()` removes the target before renaming the new tree. Rejected for concurrent-reader and crash semantics.
- **H2 current same-name staging/temp rename:** the producer staging name and `atomic_publish()` temp name are the same path. Rejected: the helper can delete its own candidate before rename (#1110 post-merge falsifier).
- **H3 independently replace report directory and configured pulse-table file:** locally atomic per object but not one transaction. Rejected as a global authority mechanism because a process can die between the two commits.
- **H4 immutable generation plus one atomic authority pointer:** survivor implemented as the reusable primitive in this branch.
- **H5 database/transactional object store:** potentially valid but unnecessary for the present filesystem workflow; equivalent authority semantics can be obtained with immutable generations plus one pointer.

## Implementation

New `src/ccb_mc_validation/s00_publication.py` provides:

- strict generation IDs and generation-relative artifact paths;
- staging creation under the generation root so the data rename stays on one filesystem;
- validation of every required artifact before publication;
- model-identity JSON serialization before the immutable generation move;
- immutable final generation IDs (existing generations are never overwritten);
- advisory `flock` serialization for competing publishers;
- `fsync` of file and directory metadata around commit points;
- atomic `CURRENT.json` replacement with `os.replace`;
- typed pointer parsing and logical artifact resolution.

The module intentionally does not delete orphan generations in the commit failure path. Garbage collection is a separate non-authorising maintenance atom.

## Discriminating tests

New tests cover:

1. first publication creates one immutable generation and a resolvable pointer;
2. second publication retains the old generation while authority moves to the new one;
3. injected failure at pointer replacement leaves the old pointer byte-identical and the old generation readable;
4. missing required artifacts fail before generation movement;
5. an existing generation ID cannot be overwritten;
6. path traversal/absolute generation IDs and artifact paths are rejected;
7. staging must be a direct child of the generation root;
8. malformed pointer schemas fail closed;
9. a pointer whose authoritative artifact is missing fails closed;
10. non-JSON-serializable model identity fails before generation movement.

## Four sequential expert passes

### Filesystem/reconstruction lead — ACCEPT primitive / BLOCK integration
The immutable-generation + pointer transaction removes the self-delete and destructive target replacement from the authority model. The producer still uses its legacy `atomic_publish()` until explicitly wired.

### Adversarial/concurrency reviewer — ACCEPT with residual integration risks
Strongest counterexample was a crash after immutable generation move but before pointer replacement. The surviving orphan is non-authoritative because authority is only `CURRENT.json`. A separate integration test must still prove real downstream readers never bypass the pointer.

### Validation/statistics reviewer — ACCEPT deterministic test design / pending exact-head CI
No beam statistics are required to test filesystem authority semantics. The key negative control is byte identity of the previous pointer under injected commit failure.

### Claims/provenance reviewer — BLOCK #1110 closure
The primitive is not sufficient while `scripts/01_build_pulse_table_from_root.py`, CL-001 validation, and downstream S00 consumers still resolve mutable legacy paths directly. The authority root must be integrated and source-bound before #1110 can close.

## Residual child atoms

1. Wire the canonical producer to generate one immutable package containing report artifacts and selected pulse table, then commit a single pointer only after all P0 gates pass.
2. Define the exact pointer/generation root paths in configuration without reusing mutable report-directory identity.
3. Migrate authoritative downstream consumers to `resolve_artifact()` or an equivalent model-bound resolver.
4. Define legacy `data/processed/s00_selected_b_pulses.csv.gz` and report-directory behavior explicitly as compatibility aliases or retire them; they cannot remain independent authorities.
5. Add real-producer injected-crash and concurrent-reader tests.
6. Add orphan-generation garbage collection only after proving it cannot delete current or referenced generations.

## Scientific boundary

No raw ROOT file was opened, no S00 count was regenerated, no Geant4 simulation was run, and no detector-performance or physics claim changed. This branch provides a filesystem/provenance primitive only.

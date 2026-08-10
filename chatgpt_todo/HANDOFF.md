# Latest Handoff

## Session

- **Task ID:** `ARU-RAW-DIGEST-SAME-STREAM-001`
- **Stamp:** `2026-08-10T094900Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial/current main:** `4fda4b5013a712a329646127140d8a52d322af92`
- **Parent issue:** #993
- **Child issue:** #1155
- **Reviewed PR:** #1154 (`e7ab22893ffad0266acb7c4243ebb748a1334ec7`)
- **Branch:** `audit/raw-digest-same-stream-review`
- **Status:** `INDEPENDENT_REVIEW_COMPLETE / CHILD_ATOM_OPEN / NO_SCIENTIFIC_PROMOTION`

## Selected atom

```text
raw ROOT pathname
-> opened byte stream
-> SHA-256 digest + byte count + source identity
-> provenance row
```

The exact local invariant is:

```text
sha256 = H(B)
bytes  = |B|
```

for the same opened byte stream `B`. Source identity metadata must be derived from the same descriptor/snapshot rather than from a later pathname lookup.

## Verified repository state

Current `main` is `4fda4b5013a712a329646127140d8a52d322af92`. Recent main changes include #1146, #1153, #1132 and #1108.

PR #1154 correctly repairs an exact provenance contradiction: the historical producer computed every available raw-file digest but persisted only `digests[:3]` while reporting the full digest count. The PR removes that truncation, records missing runs and completeness, adds synthetic tests, and corrects data-side report prose so CL-001 remains GATED and 8x16<->8x18 lineage remains unresolved.

Both `test` check-runs on PR #1154 exact head `e7ab228...` are now green. However, the successful pull-request merge-ref was built against then-current main `f8da281e...`. Current main later advanced to `4fda4b50...`. `compare(main@4fda4b50, head@e7ab2289)` reports `diverged`, with the head 6 commits ahead and 3 behind and merge base `9c68115e...`. Therefore those earlier checks are not reused as current-base merge authority.

## Remaining row-level provenance defect

The current PR helper still performs separate observations:

```text
path.exists()
sha256_file(path)
path.stat().st_size
```

If the pathname is replaced or modified between the hash read and the later stat, a row can bind `sha256(A)` to `bytes(B)`. Reordering those separate calls does not solve the mechanism class.

Issue #1155 was opened with a one-open same-stream design. The preferred implementation is a small helper that opens once, hashes bounded blocks while counting those exact bytes, captures descriptor metadata with `fstat`, and fails closed under an explicit source-stability policy. A content-addressed/immutable source snapshot is an acceptable stronger world if the data host supports it.

## Required hostile controls

- replace the pathname after digest read but before metadata collection: old design can create a mixed-version row; repaired design must not;
- mutate source contents in-place during read: reject instability or explicitly bind the exact read stream under a documented immutable-source contract;
- stable-file positive control with exact digest and byte count;
- same descriptor supplies digest, byte count and source identity;
- explicit symlink/alias policy;
- preserve PR #1154's stable ordering, complete-list semantics and missing-run reporting.

Synthetic files are sufficient for this software/provenance atom. No beam-data hash should be fabricated in CI.

## Four sequential expert passes

- **DAQ/provenance lead — REVISE.** #1154 fixes manifest completeness but not row-level same-stream identity.
- **Adversarial filesystem reviewer — BLOCK current row authority.** Path replacement or mutation can separate digest and size semantics.
- **Independent validation reviewer — ACCEPT deterministic child design / require executable mutation tests.** Beam statistics are irrelevant to this atom.
- **Claims/provenance reviewer — ACCEPT child / BLOCK scientific promotion.** #993 remains open and CL-001 remains GATED.

## Repository actions

- submitted a COMMENT review on PR #1154, anchored to exact head `e7ab228...`, recording `RP-RAW-DIGEST-001` and the stale-current-base CI gate;
- opened #1155 with the exact atom definition, competing mechanism worlds, equivalence collapse, implementation surface, hostile tests and acceptance contract;
- preserved the full derivation in `chatgpt_todo/archive/2026-08-10T094900Z_ARU-RAW-DIGEST-SAME-STREAM-REVIEW.md`;
- did not push code onto the active PR #1154 branch, avoiding concurrent implementation conflict.

## Scientific boundary

No raw ROOT file was available to this runtime. No digest manifest was regenerated. No S00 count, timing, PID, penetration, energy, pile-up, calibration, Geant4 or detector-performance quantity changed. This run produced provenance-review evidence and an implementation-ready child atom only.

## Next actions

1. Refresh PR #1154 onto current main and require fresh current-base exact-head CI.
2. Implement #1155 as a one-open same-stream raw digest helper with mutation/path-replacement controls, either on a coordinated follow-up branch or after #1154 is safely integrated.
3. Keep #993 open until stage-by-stage event/channel/sample lineage between 8x16 and 8x18 products is demonstrated.

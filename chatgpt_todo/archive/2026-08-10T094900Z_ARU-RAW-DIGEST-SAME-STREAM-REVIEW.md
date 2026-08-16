# ARU — Raw-input digest same-stream provenance review

## Selected atom

`raw ROOT pathname -> opened byte stream -> SHA-256 digest + byte count + source identity -> provenance row`

Parent scientific/provenance issue: #993. Independent review target: PR #1154. Child atom opened: #1155.

## Repository state inspected

- Initial/current `main`: `4fda4b5013a712a329646127140d8a52d322af92`.
- Recent main changes include merged #1146 (per-event HRD width gate), #1132 (Birks public-claim binding), #1153 (gitlink/submodule integrity), and #1108 (optical interface semantics).
- PR #1154 head: `e7ab22893ffad0266acb7c4243ebb748a1334ec7`.
- PR #1154 changes the data-side provenance producer so all available raw-file digests are serialized rather than `digests[:3]`, records missing runs/completeness, adds synthetic tests, and demotes overstrong report prose.
- Both exact-head check-runs on `e7ab228...` have completed successfully, but the PR merge-ref run was against then-current main `f8da281e...`; current main has since advanced. `compare(main@4fda4b50, head@e7ab2289)` is diverged: head is 6 commits ahead and 3 behind, merge base `9c68115e...`.
- #993 remains open and requires byte/sample lineage between the 8x16 raw product and 8x18 historical timing product.
- CL-001 remains GATED; no count or detector-performance promotion is authorised by this atom.

## Exact defect retained after #1154's truncation repair

The PR's `collect_raw_input_digests()` performs three logically separate pathname observations:

1. `path.exists()`;
2. `sha256_file(path)`;
3. `path.stat().st_size`.

For provenance authority this permits a mixed-version row if the source path is replaced or modified between the digest read and the later stat. The row can therefore encode `sha256(A)` together with `bytes(B)`.

The required local invariant is instead defined on one opened byte stream `B`:

`sha256 = H(B)`

and

`bytes = |B|`.

Source identity metadata should be captured from that same descriptor/snapshot rather than from a later pathname lookup.

A stronger fail-closed mutable-source contract compares `fstat` identity before and after the stream read and rejects source instability unless the data host supplies an explicitly immutable/content-addressed source snapshot.

## Competing mechanism worlds

1. **Immutable source** — the data host guarantees that raw ROOT files cannot change during provenance generation. One-open digest/count plus recorded immutability assumption is sufficient.
2. **Path replacement** — the pathname can be atomically replaced after hashing and before metadata collection. Current design can serialize a mixed row.
3. **In-place mutation** — one inode changes while hashing. A digest still identifies the exact bytes read by the hasher, but those bytes need not represent any stable on-disk generation unless source-stability checks or snapshotting are used.
4. **Symlink/alias** — the user-visible path and underlying object identity differ. The producer needs an explicit policy; implicit `Path` following is not a provenance contract.

Reordering separate `hash(path)` and `stat(path)` calls does not create an independent solution; all such parameterizations share the same pathname-TOCTOU class.

## Falsifiers and implementation contract

Required synthetic hostile controls:

- replace the pathname after the digest read but before byte-count collection; demonstrate the old design can produce `H(A)` with `|B|` and the repaired design cannot;
- mutate the source in place during hashing and require either explicit rejection or a documented exact-read-stream/immutable-source policy;
- positive stable-file control with known digest and byte count;
- same opened descriptor supplies digest, counted bytes, and source identity;
- symlink policy is explicit and tested;
- stable run ordering, complete-list semantics, and missing-run reporting introduced by #1154 remain unchanged.

Preferred implementation surface: `digest_raw_input(path) -> RawInputDigest`, opening the source once, reading in bounded blocks while updating both SHA-256 and an explicit byte counter, capturing descriptor metadata with `fstat`, and failing closed under the chosen source-stability policy. `collect_raw_input_digests()` should call that helper rather than hashing and stat-ing a pathname separately.

No absent beam-data hashes should be fabricated. Synthetic mutation controls are sufficient for this software/provenance child; real digest regeneration remains a data-host task under #993.

## Four sequential expert passes

### DAQ / provenance lead — REVISE

Evidence inspected: #993 acceptance contract, #1154 patch, exact-head CI state, current main divergence. The complete-list repair is correct but the row itself is not yet same-stream bound.

Strongest counter-hypothesis: raw files are operationally immutable on the data host, making the race impossible in practice. Required rebuttal: make that immutable-source contract explicit and test/record it, or implement one-open source-stability checks.

Vote: **REVISE**.

### Adversarial filesystem reviewer — BLOCK mixed-version row authority

Attempted falsifier: pathname replacement between hash and stat. The present call sequence has no mechanism that forces those observations to describe the same underlying generation.

Vote: **BLOCK** any claim that the row is internally atomic provenance until #1155 is satisfied.

### Independent validation reviewer — ACCEPT deterministic testability

The defect is software/provenance semantics, not beam statistics. Mutation/path-replacement fixtures can distinguish the mechanisms without raw beam files.

Vote: **ACCEPT child design / require executable mutation tests**.

### Claims / provenance reviewer — ACCEPT governance boundary

The report demotion in #1154 is directionally correct and #993 remains open. This child must not be interpreted as 8x16<->8x18 lineage evidence or CL-001 promotion.

Vote: **ACCEPT #1155 / BLOCK scientific promotion**.

## Repository actions

- submitted an independent COMMENT review on PR #1154 at exact head `e7ab228...`, recording concern `RP-RAW-DIGEST-001`, the stale-current-base gate, and four-role disposition;
- opened issue #1155 with the one-open same-stream contract, mechanism alternatives, hostile controls, implementation surface, and scientific boundary;
- no code was pushed onto PR #1154's active implementation branch to avoid conflicting with concurrent work.

## Scientific boundary

No raw ROOT file was available to this runtime. No raw digest artifact was regenerated. No S00 count, timing, PID, penetration, energy, pile-up, calibration, Geant4, or detector-performance quantity changed. The result of this run is an independently reviewed provenance child and an implementation-ready falsification contract.

## Next highest-value work

1. Let #1154 refresh onto current main and obtain fresh current-base CI after addressing or explicitly deferring #1155.
2. Implement #1155 as a one-open same-stream raw digest helper with mutation/path-replacement negative controls.
3. Return to #993's harder physical/data-lineage atom only after the digest producer can truthfully bind each raw source row.

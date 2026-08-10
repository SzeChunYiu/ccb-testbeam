# ARU-RAW-CONSUMER-SAME-BYTES-001

Status: ACTIVE / PARTIAL  
Parent issues: #1149, #993  
Upstream closed leaf: #1155  
Main at selection: `439d611efe9908ae91379b7024e98ead36e4d30b`

## Atom and exact contract

Input is one raw-input provenance row produced by the merged `same-open-stream-v1`
contract plus the pathname that is about to be consumed by a scientific analysis.
The output is either a seekable binary stream whose opened object is verified against
that row or a controlled authorization failure before the caller may authorize output.

The manifest producer establishes

```text
sha256(row) = H(B_manifest)
bytes(row) = |B_manifest|
```

for one opened stream. A later pathname reopen does not establish

```text
B_consumer = B_manifest.
```

The selected local contract requires, for one opened descriptor `D`,

```text
regular(D)
identity(D) = identity(row)
H(bytes read from D) = sha256(row)
|bytes read from D| = bytes(row)
identity(D, after verify) = identity(D, before verify)
identity(D, after consumer) = identity(D, after verify)
```

where identity is `(st_dev, st_ino, st_nlink, st_size, st_mtime_ns, st_ctime_ns)`.
The consumer receives a duplicate descriptor, not a newly resolved pathname.

Units: byte count is bytes; digest is SHA-256 over raw bytes; filesystem identity fields
are OS metadata and are not detector observables. Scientific meaning is provenance only.
No waveform, timing, energy, PID, pile-up, or detector-performance measurand is changed.

## Competing mechanisms / descriptions

- H1: independent pathname reopen after a coherent manifest row. Rejected as
  authorizing: the path can be replaced between manifest and consumption.
- H2: compare pathname metadata only before reopening. Rejected: metadata is not the
  manifest content digest and path resolution can still change.
- H3: verify the opened descriptor against the manifest, rewind it, and give a duplicate
  of that same opened object to the consumer while retaining a guard descriptor. Selected
  bounded implementation for raw ROOT integration.
- H4: copy every raw file into a content-addressed verified snapshot before analysis.
  Stronger immutable-byte semantics, but adds a complete read+write copy for each large
  raw ROOT file and requires a real-host cost benchmark.
- H5: mechanically enforced immutable data-host/object-store source. Viable if the host
  provides a source-bound immutability contract; not established in repository evidence.

H3 and H4 are not equivalent under a privileged hostile writer. H3 detects ordinary
in-place/path/link-state mutation through descriptor metadata and keeps the consumer on the
verified inode. H4 additionally fixes a private byte copy. This implementation does not
claim protection against a privileged writer capable of mutating bytes while forging or
restoring inode metadata.

## Invariants / limiting cases

1. Same stable file: authorization succeeds; arbitrary seek/read stays on the verified
   opened object.
2. Same-content replacement with a new inode: digest equality alone is insufficient for
   this transaction; descriptor identity mismatch fails closed.
3. Different-content replacement before open: fails before consumer yield.
4. Replacement after verified open: consumer remains attached to the old inode, but
   link/ctime state changes and the transaction fails closed on exit.
5. In-place append/write during consumption: size/mtime/ctime change and the transaction
   fails closed on exit.
6. Final symlink: rejected via `O_NOFOLLOW`.
7. A malformed manifest row cannot be coerced through bool-as-int or noncanonical digest
   spellings.

## Experiments / negative controls implemented

`tests/test_raw_input_authorization.py` includes:

- stable exact-byte read/seek positive control;
- explicit legacy independent-path replacement demonstration;
- same-content new-inode replacement;
- different-content replacement;
- replacement while the authorized stream is held;
- in-place mutation while held;
- hard-link alias creation while held;
- digest mismatch;
- path/schema/type hostile inputs;
- symlink and invalid-block-size controls.

No raw beam ROOT file is available in this runtime, so the real 33-file manifest and the
full read-overhead benchmark were not executed.

## Four sequential review passes

### A. DAQ / raw-data provenance lead — ACCEPT primitive / BLOCK lineage closure

Evidence inspected: `data_side_real_beam.py` manifest producer and `timing()` consumer,
#993, #1149, merged #1155. Strongest counter-hypothesis: content digest alone should make
a later path acceptable. Attempted falsifier: same-content path replacement preserves
SHA-256 but changes the opened source identity. Residual uncertainty: real data-host
filesystem/source-immutability policy is not documented. Vote: **ACCEPT local primitive;
BLOCK #993 and #952 closure**.

### B. Adversarial filesystem / software reviewer — REVISE then ACCEPT bounded threat model

Evidence inspected: separate `uproot.open(path)` consumer, descriptor semantics, hostile
path/link/mutation fixtures. Strongest counter-hypothesis: holding an fd completely solves
concurrency. Falsifier: in-place mutation can affect an open inode; therefore a post-consumer
guard check is required and even that does not defeat a privileged metadata-forging writer.
Residual uncertainty: distributed filesystem caching and privileged-writer threat model on
the real host. Vote: **ACCEPT bounded ordinary-filesystem contract; REJECT claims of
cryptographic snapshot immutability**.

### C. Independent validation / statistics reviewer — ACCEPT deterministic design pending CI

Evidence inspected: invariant matrix and test design. Strongest counter-hypothesis: these
controls are tautological because no ROOT parser is involved. Falsifier: tests mutate actual
filesystem state and exercise OS descriptor/link semantics; a later integration test must
also prove Uproot is given a file-like descriptor rather than a path. Residual uncertainty:
exact-head repository CI and production-size I/O cost. Vote: **ACCEPT primitive tests
pending CI; BLOCK real-artifact closure**.

### D. Claims / provenance reviewer — ACCEPT local provenance repair / BLOCK promotion

Evidence inspected: #993 acceptance criteria, #1149 consumer requirement, CL-001 gating
state. Strongest counter-hypothesis: a coherent raw source automatically validates the
16-vs-18 waveform lineage. Falsifier: hash/content identity does not define the transform,
event/channel/sample mapping, polarity, or event key. Residual uncertainty is all downstream
scientific lineage. Vote: **ACCEPT bounded provenance primitive; BLOCK claim promotion**.

## Cross-scale propagation

```text
raw pathname
-> manifest row (#1155)
-> verified opened consumer object (this atom)
-> Uproot event/word extraction
-> 8x16/8x18 schema and exact word closure (#952/#993/#953)
-> selector/polarity/event identity
-> timing / DeltaE-E / PID / claims
```

A local provenance pass is necessary but not sufficient for every downstream node.

## Child atoms / handoff

1. Integrate `verified_raw_input_stream()` into `timing()` so Uproot receives the verified
   file-like object for the complete iteration lifetime; remove independent `path.exists()`
   and `uproot.open(path)` authorization.
2. Make a missing or unmatched manifest row a controlled failure rather than silently
   skipping a run used by the timing population.
3. Add a mocked Uproot integration test proving no pathname reopen occurs.
4. Benchmark the extra full-file verification read on the real data host and compare with a
   snapshot/object-store alternative if I/O cost is material.
5. Regenerate the complete raw manifest on the real host, then continue #993/#953 exact
   event/channel/sample and word-level lineage. Do not infer 8x16<->8x18 equivalence from
   hashes alone.

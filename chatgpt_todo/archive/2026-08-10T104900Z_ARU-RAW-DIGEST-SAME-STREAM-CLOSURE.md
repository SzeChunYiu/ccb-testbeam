# ARU — raw-input same-stream provenance closure

## Scope and state

- **Task ID:** `ARU-RAW-DIGEST-SAME-STREAM-CLOSURE`
- **Primary issue:** #1155
- **Parent:** #993
- **Related:** #952, #953, CL-001
- **Initial remote main:** `7fb2a06596a87cb2dd294ec9d0b149e3575293e5`
- **Branch:** `fix/raw-input-same-stream-provenance`
- **Evidence type:** deterministic software/provenance validation; no new beam or MC result.

## Atomic contract

Atom:

`raw ROOT pathname -> one opened regular-file byte stream B -> SHA-256 + exact byte count + descriptor identity/stability -> provenance row -> 16x18 lineage evidence`

For one row, the authorising internal identity is

```text
sha256 = H(B)
bytes  = |B|
```

for the exact same stream `B`. Descriptor metadata are obtained from that same open object rather than a later pathname lookup.

The stability gate is

```text
(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)_before
==
(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)_after
```

and `bytes_read == st_size_after`.

The pathname remains a locator. Content identity is the digest; replacing the pathname after the descriptor is opened must not create a row combining the digest of one object with the size of another.

## Competing mechanisms and equivalence collapse

- **H1 stable regular-file source:** one descriptor can bind digest, count and source identity. Survives.
- **H2 pathname replacement between separate hash/stat calls:** current pre-fix design can serialize `H(A)` with `|B|`. Eliminated by one-open stream semantics.
- **H3 in-place mutation during hashing:** same descriptor can still observe an unstable object; require before/after `fstat` stability and exact byte-count closure. Survives only as a controlled failure state.
- **H4 final-component symlink/alias:** implicit path following makes source identity ambiguous. Final-component symlinks are rejected with `O_NOFOLLOW`.
- **H5 reorder `stat(path)` and `hash(path)`:** collapsed with H2; reordering separate pathname observations does not repair the race.
- **H6 immutable/content-addressed source snapshot:** stronger external model. Not required for row-level same-stream closure, but remains a valid future child if the data-host threat model requires protection beyond ordinary file mutation detection.

## Implementation

`scripts/studies/data_side_real_beam.py` now defines `digest_raw_input()` and `RawInputProvenanceError`.

The helper:

1. requires positive block size;
2. requires `os.O_NOFOLLOW` and opens exactly once with `os.open(..., O_RDONLY|O_NOFOLLOW)`;
3. accepts only regular files;
4. hashes bounded `os.read()` blocks while counting those exact same bytes;
5. captures `fstat()` before and after the read;
6. fails closed when device/inode/size/mtime/ctime changes or the counted bytes differ from final descriptor size;
7. records digest, bytes, device, inode, link count, mtime and ctime;
8. causes symlink/nonregular/unstable inputs to fail rather than be serialized as ordinary provenance.

`collect_raw_input_digests()` no longer performs `exists -> hash(path) -> stat(path)`; only `FileNotFoundError` is converted into the explicit missing-run state. Other identity failures propagate.

The provenance payload records schema `same-open-stream-v1` and the stability contract. The complete-list and explicit-missing-run behavior from #1154 is preserved.

## Deterministic falsifiers added

`tests/test_data_side_rmax_quarantine.py` now contains:

- stable known-byte positive controls with exact SHA-256 and byte count;
- a legacy split-observation counterexample: hash A, replace contents with differently sized B, then stat, proving `H(A)`/`|B|` can coexist under the old pattern;
- pathname replacement after the repaired descriptor is open: the result remains bound to A's exact bytes and size rather than mixing with replacement B;
- in-place append during hashing: repaired helper must raise `RawInputProvenanceError`;
- final-component symlink rejection;
- nonregular input and invalid-block-size rejection;
- preservation of missing-run ordering and non-truncated manifest behavior;
- persisted digest-schema identity.

No test result is claimed until GitHub Actions executes the exact PR head.

## Four sequential expert reviews

### A. DAQ / provenance lead — ACCEPT local contract; BLOCK #993 closure

**Background:** raw DAQ product identity, file-level provenance, waveform-lineage contracts.

**Evidence inspected:** #1155, merged #1154 producer, current data-side source/tests, #993 parent contract.

**Strongest counter-hypothesis:** one-open file hashing is unnecessary if the LUNARC raw directory is immutable. Even if operational immutability is true, it is not encoded by the existing producer and does not justify split pathname observations.

**Attempted falsifier:** explicit A->B replacement between legacy hash and size observations.

**Residual uncertainty:** real data-host immutability policy and exact 33-file source state are unavailable here.

**Vote:** `ACCEPT` row-integrity repair; `BLOCK` 8x16<->8x18 lineage promotion.

### B. Adversarial filesystem reviewer — ACCEPT after hostile controls

**Background:** POSIX descriptor/path semantics, TOCTOU, symlink and mutation attacks.

**Evidence inspected:** old separate path operations, new one-descriptor implementation, mutation fixtures.

**Strongest counter-hypothesis:** a pathname replacement after open could still contaminate the row. The one-open test instead binds the original inode/stream; the replacement only changes the locator's later referent.

**Attempted falsifiers:** path replacement during read, in-place append during read, final symlink, directory input.

**Residual uncertainty:** a privileged/adversarial writer capable of pathological same-size in-place changes and metadata manipulation is outside the ordinary data-host contract; a content-addressed immutable snapshot would be the stronger model if required.

**Vote:** `ACCEPT` bounded same-stream contract; do not call it a hostile-root filesystem guarantee.

### C. Independent validation / statistics reviewer — ACCEPT deterministic design pending CI

**Background:** reproducible validation, exact invariants, negative controls.

**Evidence inspected:** existing #1154 completeness tests and new known-answer/mutation controls.

**Strongest counter-hypothesis:** tests merely restate implementation. The legacy mixed-version counterexample and independent pathname/mutation interventions exercise different state transitions rather than only nominal outputs.

**Attempted falsifier:** alter source state at controlled read boundaries and require either exact old-stream binding or fail-closed instability.

**Residual uncertainty:** no real ROOT file is available in this runtime, so the regenerated 33-file provenance artifact is not validated here.

**Vote:** `ACCEPT` software test design pending exact-head CI; `BLOCK` empirical artifact closure.

### D. Claims / provenance reviewer — ACCEPT bounded repair; BLOCK claim promotion

**Background:** source-to-claim traceability and fail-closed claim governance.

**Evidence inspected:** #1155 acceptance, #993 lineage requirement, CL-001's existing GATED status.

**Strongest counter-hypothesis:** stronger digest rows could be interpreted as proving the 16/18 product relationship. Rejected: a file digest identifies bytes but does not establish transformations between products.

**Attempted falsifier:** trace the repair upward; it changes only source-row coherence, not event/channel/sample mapping.

**Residual uncertainty:** the canonical real provenance artifact still needs regeneration on the data host.

**Vote:** `ACCEPT` provenance repair; `BLOCK` CL-001 or detector-performance promotion.

## Cross-scale propagation

```text
raw file bytes
-> same-stream digest row
-> complete raw-input manifest
-> exact raw/sorted stage lineage (#953)
-> 8x16 / 8x18 mapping (#993)
-> selector population
-> timing / topology / PID / claims
```

The local repair prevents a mixed-version row from contaminating the provenance chain. It does not make any downstream transformation valid by itself.

## Child atoms / unresolved dependencies

1. Regenerate the complete real raw-input manifest on the data host from the original 33 canonical files; retain command, host/filesystem context, producer commit and artifact hash.
2. Continue #993 with stage-by-stage event/channel/sample closure between the 8x16 and historical 8x18 products.
3. Continue #953 exact raw->sorted key/word closure and #952 waveform-width census.
4. If repository policy requires adversarial-writer protection rather than ordinary stable-source detection, define a content-addressed immutable source-snapshot atom instead of silently expanding this helper's threat model.

## Scientific boundary

No raw ROOT file was opened in this runtime, no provenance artifact was regenerated from beam bytes, no Geant4 simulation was run, and no S00 count, timing, PID, penetration, energy, pile-up, calibration or detector-performance result changed. CL-001 remains GATED and #993 remains open.

# ARU — raw-input same-stream provenance closure

## Scope and state

- **Task ID:** `ARU-RAW-DIGEST-SAME-STREAM-CLOSURE`
- **Primary issue:** #1155
- **Parent:** #993
- **Related:** #952, #953, #1149, CL-001
- **Initial remote main:** `7fb2a06596a87cb2dd294ec9d0b149e3575293e5`
- **Branch:** `fix/raw-input-same-stream-provenance`
- **PR:** #1157
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

The pathname remains a locator, not content identity. Any mutation that changes the descriptor stability tuple during hashing is rejected rather than serialized as an ordinary row.

## Competing mechanisms and equivalence collapse

- **H1 stable regular-file source:** one descriptor can bind digest, count and source identity. Survives.
- **H2 pathname replacement between separate hash/stat calls:** pre-fix design can serialize `H(A)` with `|B|`. Eliminated by one-open stream semantics plus stability gate.
- **H3 in-place mutation during hashing:** same descriptor can observe an unstable object; before/after `fstat` and exact byte-count closure reject the tested append mutation. Survives only as a controlled failure state.
- **H4 final-component symlink/alias:** implicit final-component following makes source identity ambiguous. Final-component symlinks are rejected with `O_NOFOLLOW`.
- **H5 reorder `stat(path)` and `hash(path)`:** collapsed with H2; reordering separate pathname observations does not repair the race.
- **H6 immutable/content-addressed source snapshot:** stronger external model. Not required for row-level same-stream closure, but remains the preferred extension if the data-host threat model requires stronger immutable-consumption guarantees.

## Implementation

`scripts/studies/data_side_real_beam.py` defines `digest_raw_input()` and `RawInputProvenanceError`.

The helper:

1. requires positive block size;
2. requires `os.O_NOFOLLOW` and opens exactly once with `os.open(..., O_RDONLY|O_NOFOLLOW)`;
3. accepts only regular files;
4. hashes bounded `os.read()` blocks while counting those exact same bytes;
5. captures `fstat()` before and after the read;
6. fails closed when device/inode/size/mtime/ctime changes or counted bytes differ from final descriptor size;
7. records digest, bytes, device, inode, link count, mtime and ctime;
8. causes symlink/nonregular/unstable inputs to fail rather than be serialized as ordinary provenance.

`collect_raw_input_digests()` no longer performs `exists -> hash(path) -> stat(path)`; only `FileNotFoundError` is converted into the explicit missing-run state. Other identity failures propagate.

The provenance payload records schema `same-open-stream-v1` and the stability contract. The complete-list and explicit-missing-run behavior from #1154 is preserved.

## Deterministic falsifiers and CI discovery

`tests/test_data_side_rmax_quarantine.py` contains:

- stable known-byte positive controls with exact SHA-256 and byte count;
- a legacy split-observation counterexample: hash A, mutate to differently sized B, then stat, proving `H(A)`/`|B|` can coexist under the old pattern;
- pathname replacement after the repaired descriptor is open;
- in-place append during hashing;
- final-component symlink rejection;
- nonregular input and invalid-block-size rejection;
- preservation of missing-run ordering and non-truncated manifest behavior;
- persisted digest-schema identity.

### First exact-head CI falsifier

PR #1157 head `fa188b57a94762f10d6ad786c3bd00cdd5f20dc8`, workflow run `31381447250`, job `93432302892`:

- checkout: PASS;
- dependency install: PASS;
- ruff: `All checks passed!`;
- pytest log: `1 failed, 1294 passed, 1 skipped, 8 xfailed, 1 xpassed`;
- enforcement step: FAIL.

The sole failure was the adversarial path-replacement test. The first test design predicted that replacing the pathname after open would still yield a coherent row for the original descriptor. The implementation instead raised `RawInputProvenanceError` because replacement changes the open inode's metadata-change time on the CI filesystem, so the before/after stability tuple differed.

This is a stronger fail-closed result, not a reason to weaken the implementation. The test was revised to require controlled rejection of path replacement. The failed expectation and correction are intentionally preserved here.

## Four sequential expert reviews

### A. DAQ / provenance lead — ACCEPT local contract; BLOCK #993 closure

**Background:** raw DAQ product identity, file-level provenance, waveform-lineage contracts.

**Evidence inspected:** #1155, merged #1154 producer, current data-side source/tests, #993 parent contract, first #1157 CI artifact.

**Strongest counter-hypothesis:** one-open hashing is unnecessary if the data host guarantees source immutability. Even if operational immutability is true, it is not encoded by the old producer and does not justify split pathname observations.

**Attempted falsifier:** explicit A->B state change between legacy hash and size observations.

**Residual uncertainty:** real data-host immutability policy and exact 33-file source state are unavailable here.

**Vote:** `ACCEPT` row-integrity repair; `BLOCK` 8x16<->8x18 lineage promotion.

### B. Adversarial filesystem reviewer — ACCEPT after revision

**Background:** POSIX descriptor/path semantics, TOCTOU, symlink and mutation attacks.

**Evidence inspected:** old separate path operations, one-descriptor implementation, hostile fixtures, CI failure trace.

**Strongest counter-hypothesis:** pathname replacement after open might silently leave a valid row whose locator now refers to other bytes. The CI falsifier showed the current metadata stability gate rejects that tested replacement instead.

**Attempted falsifiers:** path replacement during read, in-place append during read, final symlink, directory input.

**Residual uncertainty:** a privileged/adversarial writer capable of pathological same-size in-place changes while defeating ordinary metadata-change evidence remains outside this bounded contract; a content-addressed immutable snapshot is stronger if that threat model is required.

**Vote:** `ACCEPT` fail-closed same-stream contract after revising the test expectation.

### C. Independent validation / statistics reviewer — ACCEPT design; exact-head rerun required

**Background:** reproducible validation, exact invariants, negative controls.

**Evidence inspected:** #1154 completeness tests, new known-answer/mutation controls, exact CI artifact.

**Strongest counter-hypothesis:** tests merely restate implementation. The first CI run disproved one reviewer expectation, demonstrating that the hostile fixtures can reveal state behavior not assumed by the test author.

**Attempted falsifier:** alter source state at controlled read boundaries and require either exact stable-stream closure or a controlled provenance failure.

**Residual uncertainty:** corrected exact-head CI is still required; no real ROOT file is available in this runtime, so the regenerated 33-file provenance artifact is not validated here.

**Vote:** `REVISE -> ACCEPT design`, pending corrected exact-head CI; `BLOCK` empirical artifact closure.

### D. Claims / provenance reviewer — ACCEPT bounded repair; BLOCK claim promotion

**Background:** source-to-claim traceability and fail-closed claim governance.

**Evidence inspected:** #1155 acceptance, #993 lineage requirement, CL-001's existing GATED status, data-side report provenance caveat.

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

## Recursive child / compatibility atom

The main study calls `data_provenance()` and later reopens raw run paths in `timing()` through `uproot.open`. A coherent manifest row therefore does not, by itself, establish that later scientific consumers read the same bytes that were hashed. This is the same verified-read/consumption universe already open as #1149 for S00 artifacts, so no duplicate issue was created. #1149 was cross-linked to #1155/#993 with the raw-side falsifier and solution classes: verified stream/snapshot consumption or a mechanically enforced and recorded immutable-source contract.

## Unresolved dependencies

1. Obtain corrected exact-head/current-base CI for PR #1157.
2. Regenerate the complete real raw-input manifest on the data host from the original 33 canonical files; retain command, host/filesystem context, producer commit and artifact hash.
3. Continue #993 with stage-by-stage event/channel/sample closure between the 8x16 and historical 8x18 products.
4. Continue #953 exact raw->sorted key/word closure and #952 waveform-width census.
5. Reuse #1149 for same-bytes consumer migration rather than treating pathname reopen as authorising provenance.

## Scientific boundary

No raw ROOT file was opened in this runtime, no provenance artifact was regenerated from beam bytes, no Geant4 simulation was run, and no S00 count, timing, PID, penetration, energy, pile-up, calibration or detector-performance result changed. CL-001 remains GATED and #993 remains open.

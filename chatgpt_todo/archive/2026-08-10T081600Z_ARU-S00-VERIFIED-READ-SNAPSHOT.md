# ARU-S00-VERIFIED-READ-SNAPSHOT-001

## Atom

`content-bound CURRENT.json -> generation artifact -> verification -> downstream bytes consumed`

Parent: #1149. Upstream: #1147 -> #1110.

## Exact contract

A path resolver proves only a time-indexed statement:

```text
H(file at t_verify) = H(pointer)
```

An authorising read requires:

```text
H(bytes actually consumed) = H(pointer)
```

without assuming that a mutable pathname is unchanged between verification and consumption.

## Competing mechanisms / designs

1. Documentation-only single-writer assumption — rejected for authorising reads because no mechanical guarantee exists.
2. chmod/read-only generation — defense in depth only; permissions do not identify consumed bytes.
3. reject `st_nlink != 1` — blocks one alias mechanism but leaves pathname replacement and in-place mutation races.
4. verified source descriptor — collapses pathname replacement but in-place writes to the open inode can still change a later read.
5. complete all-bytes in-memory read — exact but may require selected-table-sized memory.
6. **streaming verified private snapshot — selected survivor.** Copy once in bounded blocks to a private `mkstemp` file, hash the exact copied blocks, yield only after digest equality, then consume the private snapshot.
7. filesystem snapshot/content-addressed object store — stronger infrastructure option, unnecessary for the current repository-scale contract.

The survivor has O(n) source read + O(n) temporary write I/O and bounded memory. It intentionally prefers exact consumed-byte identity over a zero-copy mutable-path API. Production-scale timing on the real selected-pulse table remains to be measured before claiming the overhead is negligible.

## Implementation

Added `src/ccb_mc_validation/s00_verified_read.py` with:

- one-time `CURRENT.json` read, so a reader binds one complete old-or-new authority snapshot;
- physical generation-path validation using the publication primitive;
- `os.open(..., O_NOFOLLOW)` when available plus `fstat` regular-file validation;
- secure `tempfile.mkstemp` snapshot creation;
- streaming SHA-256 over the exact bytes copied into the snapshot;
- yield only when copied-byte digest equals the pointer digest;
- compound suffix preservation such as `.csv.gz` for downstream readers;
- provenance metadata: pointer snapshot, device, inode, link count and source size;
- read-only snapshot mode while yielded and deterministic cleanup afterward.

The API deliberately records `source_nlink` instead of rejecting hard links. A hard-link alias is safe under the selected contract because mutation before/during copying must still reproduce the authorised digest, while mutation after snapshot creation cannot affect the private snapshot.

## Deterministic falsifiers / negative controls

`tests/test_s00_verified_read.py` covers:

- exact authorised bytes + digest + cleanup;
- source tamper before snapshot -> fail closed;
- source tamper after snapshot -> private bytes unchanged;
- hard-link alias mutation after snapshot -> private bytes unchanged;
- hard-link alias mutation before snapshot -> fail closed;
- pointer swap after snapshot -> reader retains one complete old generation while `CURRENT.json` advances;
- unknown logical artifact -> no snapshot creation;
- invalid block size;
- missing scratch directory.

`tests/test_s00_verified_read_negative_control.py` preserves the hostile control proving the original gap: `resolve_artifact()` verifies a path, then a hard-link mutation changes the bytes returned by a later path read. This is intentionally not treated as a failure of the v2 pointer; it demonstrates why authorising consumers need a same-bytes read primitive.

## Four sequential expert reviews

### Filesystem/reconstruction lead — ACCEPT design / pending exact-head CI
Background: POSIX publication transactions and reconstruction artifact lineage.

Evidence inspected: merged v2 publication primitive, #1149 contract, Python tempfile/os documentation, source and tests on this branch.

Strongest counter-hypothesis: same-descriptor verification is sufficient. Rejected for strict same-bytes semantics because later reads from a mutable inode can differ after verification.

Residual uncertainty: real selected-table I/O overhead has not been measured.

### Adversarial mechanism reviewer — ACCEPT local contract / BLOCK direct-path authorisation
Background: filesystem race, alias and provenance failure analysis.

Attempted falsifiers: post-verify path mutation, external hard-link mutation, pointer swap, tamper before snapshot. The private snapshot survives the first three and fails closed on pre-copy tamper.

Residual risk: privileged mutation of the private temporary file/process is outside the declared threat model.

### Statistics/validation reviewer — ACCEPT deterministic design / pending CI
Background: reproducibility, validation design and failure injection.

No beam statistics are relevant. Acceptance is exact byte equality and state-machine behavior. The negative control is retained so the test suite proves the distinction between path verification and consumed-byte verification.

Residual requirement: benchmark real production size before universal migration if I/O overhead materially affects workflow.

### Claims/provenance reviewer — REVISE parent #1110, do not promote CL-001
Background: claim ledger and provenance authority.

The new API can be an authorising read boundary only after consumers are migrated to it. Existing direct legacy-path reads and `resolve_artifact()->reopen Path` remain non-authorising for strict concurrent-reader claims. No detector result or CL-001 state changes in this atom.

## Primary/authoritative external sources

- Python `tempfile` documentation: `mkstemp()` creates temporary files securely and avoids the insecure name-only `mktemp()` pattern: https://docs.python.org/3/library/tempfile.html
- Python `os` documentation: `os.open`, `O_NOFOLLOW` where supported, file-descriptor `stat`/`fstat` metadata and related operating-system interfaces: https://docs.python.org/3/library/os.html

These sources support software semantics only; they do not support any detector-physics claim.

## Cross-scale compatibility

```text
CURRENT.json pointer
-> content-bound generation bytes (#1147)
-> verified private snapshot (#1149)
-> parser/statistical consumer
-> study artifact
-> claim ledger
```

The new child does not solve producer integration. #1110 still requires the canonical producer to publish report + selected table in one immutable generation and downstream authoritative consumers to use the verified-read boundary.

## Scientific boundary

No raw ROOT data were opened, no S00 counts regenerated, no Geant4 job run, and no timing/PID/penetration/energy/pile-up/detector-performance quantity changed.

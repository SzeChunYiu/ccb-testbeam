# ARU-RAW-UPROOT-SAME-STREAM-001

Status: ACTIVE / PARTIAL
Parent issues: #1149, #993
Upstream primitive: PR #1159, squash merge `4fe1efaf931083de0a3c61bd25a447f5cb21e7a2`

## Atom contract

Input: one raw ROOT pathname plus its complete same-stream provenance row `{run,file,sha256,bytes,source_dev,source_ino,source_nlink,source_mtime_ns,source_ctime_ns}`.
Output: an Uproot file object whose complete lifetime is nested inside the verified descriptor context.
Scientific meaning: a timing/raw-waveform consumer may only authorize results from bytes whose SHA-256 and descriptor identity match the manifest row. A later independent pathname reopen is not authorizing.

Invariant: `H(B_consumed) = H(B_manifest) = row.sha256`, with one descriptor identity `(dev,ino,nlink,size,mtime_ns,ctime_ns)` stable through verification and consumer-context exit.

## Competing mechanisms collapsed

1. Manifest hash followed by `uproot.open(path)`: rejected; pathname can be replaced between verification and use.
2. Re-stat/re-hash pathname immediately before Uproot: equivalent TOCTOU class; rejected as an independent solution.
3. Full copied snapshot: survives as strongest isolation but costs an extra full write and storage.
4. Verified open descriptor/stream held through Uproot lifetime: surviving bounded solution under ordinary filesystem metadata semantics.
5. Immutable data-host contract: survives only if mechanically enforced and recorded; currently not established.

## Implementation and falsifiers

Added `raw_uproot_authorization.py` with strict unique run indexing and `open_verified_uproot()`. Uproot receives only the verified seekable stream, never a string/Path. Added tiny ROOT fixture tests for successful branch reads, file-like-not-path argument, pre-open replacement rejection, replacement during Uproot lifetime, duplicate/missing manifest rows, and malformed run identifiers. No beam file or detector simulation is used; fixtures test software semantics only.

The canonical `scripts/studies/data_side_real_beam.py::timing()` still performs `uproot.open(path)` and is therefore not yet migrated. This branch proves the adapter/lifetime contract first; the producer integration remains a child atom.

## Four role-separated reviews

### A. DAQ / reconstruction lead — ACCEPT adapter, REVISE integration
Evidence inspected: merged raw descriptor primitive; current `data_side_real_beam.py` digest production and timing loop; Uproot adapter tests.
Strongest counter-hypothesis: the file-like adapter changes ROOT interpretation or cannot support random-access reads.
Attempted falsifier: real Uproot `recreate` fixture, branch lookup, array read through the authorized stream.
Residual uncertainty: real multi-GB beam-file performance and remote filesystem behavior are unmeasured.
Vote: ACCEPT local adapter / REVISE canonical consumer.

### B. Adversarial mechanism reviewer — ACCEPT bounded threat model
Evidence inspected: replacement and hard-link/in-place mutation controls in #1159 plus new Uproot lifetime controls.
Strongest counter-hypothesis: Uproot silently reopens the source pathname after receiving the stream.
Attempted falsifier: spy asserts Uproot receives a seekable file object and no pathname; pathname replacement while the Uproot object is alive must end in a provenance failure.
Residual uncertainty: privileged writers able to mutate bytes and forge/restore inode metadata are out of scope.
Vote: ACCEPT adapter / BLOCK pathname fallback.

### C. Independent statistics / validation reviewer — ACCEPT deterministic validation
Evidence inspected: exact identity equations and finite fixture tests.
Strongest counter-hypothesis: passing tests could be mistaken for timing-resolution validation.
Attempted falsifier: test outputs contain no detector-performance estimator and no beam values.
Residual uncertainty: production-size verification overhead requires data-host benchmark.
Vote: ACCEPT software contract / BLOCK physics inference.

### D. Claims / provenance reviewer — BLOCK claim promotion
Evidence inspected: CL-001 remains GATED; #993/#952/#953 remain unresolved; current timing script still uses pathname reopen.
Strongest counter-hypothesis: same-bytes raw consumption alone closes raw→sorted or 8x16↔8x18 lineage.
Attempted falsifier: dependency trace shows event identity, width lineage, mapping/polarity, and real manifest regeneration remain independent atoms.
Residual uncertainty: authoritative downstream consumers beyond this timing path have not all been enumerated.
Vote: BLOCK #993/CL-001 promotion.

## Children / handoff

1. Migrate `data_side_real_beam.py::timing(canon)` to require the complete provenance rows and use `open_verified_uproot()` for the full iteration lifetime; missing/duplicate required run rows must fail before scientific output.
2. Benchmark the extra verification read on the real data host (size/hash, filesystem/device, cold/warm cache, block size, wall time, throughput, temporary-space use).
3. Continue #993/#953 exact event/channel/sample lineage only after the raw consumer bytes are mechanically bound.
4. Do not duplicate #952 for waveform-width failures; that issue owns 8x16/8x18 width semantics.

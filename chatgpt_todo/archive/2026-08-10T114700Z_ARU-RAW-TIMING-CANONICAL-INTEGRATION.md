# ARU-RAW-TIMING-CANONICAL-INTEGRATION

Status: ACTIVE / PARTIAL pending exact-head CI
Parent issues: #1149, #993
Related blockers: #952, #953
Upstream primitive on main: PR #1159, squash merge `4fe1efaf931083de0a3c61bd25a447f5cb21e7a2`
Integration PR: #1160

## Exact contract

Input: canonical selected-pulse table, complete raw-input provenance rows, and one raw ROOT source per timing-required run.
Output: the existing sampling-limited B4/B6 timing artifact plus explicit raw authorization mode/run IDs.
Units: waveform amplitudes remain ADC; CFD/sample/ToF quantities remain ns. This change does not alter the timing estimator.
Measurand: unchanged; only the byte-source authorization of the waveform consumer is modified.
Provenance invariant: `H(B_consumed) = H(B_manifest) = row.sha256`, with `(dev,ino,nlink,size,mtime_ns,ctime_ns)` stable through verification and the complete Uproot iteration lifetime.

## Mechanisms and eliminations

- `manifest hash -> later uproot.open(path)`: eliminated by pathname replacement TOCTOU.
- `stat/hash path immediately before open`: same observational/mechanistic class; not an independent solution.
- silent `if not path.exists(): continue`: eliminated because a missing timing-required run changes the statistical population without an authorizing failure.
- verified open descriptor/stream held across Uproot: surviving bounded solution.
- private content snapshot: surviving stronger isolation option, deferred until data-host cost/threat evidence warrants the extra copy.

## Implementation

`raw_uproot_authorization.py` provides typed unique run indexing, required-run completeness and `open_verified_uproot()`.

Canonical `scripts/studies/data_side_real_beam.py::timing()` now:

- accepts the provenance record returned by `data_provenance()`;
- converts timing run keys to Python integers before matching manifest rows;
- requires exactly one row for every run in the B4/B6 timing subset;
- removes the old path-existence skip and direct pathname Uproot open;
- nests each entire `tree.iterate()` transaction inside the verified Uproot context;
- records `raw_input_authorization=manifest-bound-same-open-stream-v1` and the sorted authorized run list.

No waveform-width behavior is changed: the existing `waveform.size != 8 * NSAMP` branch remains under #952.

## Falsifiers / controls

1. Tiny ROOT file produced with Uproot is read through the adapter and returns exact expected EVENTNO/HRDv values.
2. Spy asserts Uproot receives a seekable file object, not a string or Path.
3. Same pathname replaced before open is rejected by descriptor identity.
4. Pathname replaced while Uproot is alive causes a fail-closed post-consumer identity error.
5. Missing required manifest row fails before any raw open.
6. Duplicate/malformed run rows fail closed.
7. Canonical timing fixture succeeds only with a matching manifest row and writes its timing figure.
8. Canonical timing fixture rejects a replaced raw source before authorizing timing output.

Fixtures are software-semantic controls only, not detector validation.

## Sequential expert review

### A. DAQ / reconstruction lead
Evidence: merged descriptor primitive, canonical provenance producer, timing loop before/after, real Uproot fixture.
Counter-hypothesis: file-like Uproot access changes raw decoding or cannot support the random-access pattern.
Falsifier: actual Uproot branch/array/iterate operations on a ROOT fixture through the verified stream.
Residual uncertainty: real multi-GB data-host performance; physical validity of first-four pedestal; 8x16/8x18 lineage.
Vote: ACCEPT canonical byte-authorization integration pending exact-head CI; BLOCK broader reconstruction closure.

### B. Adversarial mechanism reviewer
Evidence: pre-open and during-consumption replacement controls; missing-row control; unchanged width skip.
Counter-hypothesis: a later pathname fallback or silent missing run can still change the consumed population.
Falsifier: no pathname passed to Uproot; manifest completeness is checked before run opens; replacement during lifetime fails at exit.
Residual uncertainty: privileged writers able to forge/restore metadata; distributed-filesystem semantics not measured here.
Vote: ACCEPT bounded ordinary-filesystem contract; BLOCK future pathname fallback.

### C. Independent statistics / validation reviewer
Evidence: deterministic identity tests; unchanged timing estimator and event selection.
Counter-hypothesis: provenance repair changes a timing result or constitutes timing validation.
Falsifier: no real beam bytes are available/executed; tests assert software state transitions only.
Residual uncertainty: population-level consequences can only be checked after regeneration on the data host.
Vote: ACCEPT software validation pending CI; BLOCK detector/timing inference.

### D. Claims / provenance reviewer
Evidence: CL-001 remains GATED; #993/#952/#953 remain open; canonical reports predate this contract.
Counter-hypothesis: binding timing bytes is sufficient for raw->sorted or public-claim closure.
Falsifier: dependency trace still lacks exact 16<->18 transformation, event/channel/sample word closure, mapping/polarity closure, and regenerated real artifacts.
Residual uncertainty: other raw consumers still need inventory and migration where authorizing.
Vote: BLOCK #993 closure and CL-001 promotion.

## Remaining children

- Exact-head CI on the final #1160 state.
- Real data-host benchmark of the extra verification pass, including source bytes/hash, device/filesystem, cache state, block size, wall time and throughput.
- Regenerate complete real provenance and timing artifacts under the new contract.
- Inventory other authorizing raw consumers for independent pathname reopen.
- Resume #993/#953 exact event/channel/sample and word-level lineage; keep width semantics under #952.

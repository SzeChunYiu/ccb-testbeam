# ARU-ELEC-IMPULSE-DIGEST-CANONICALIZATION-001

Status: `VALIDATED` at bounded software/provenance-primitive level. Parent `#1067` remains `PARTIAL` / open.

## Atom and parent dependencies

This atom is a child of `ARU-ELEC-IMPULSE-PROVENANCE-STATE-001` and `#1067`. It starts from protected `ccb-testbeam main@cf3106f9111755f9b51e0388e2bd9feb769242b2`, whose SiPM gitlink is exact `ccb-sipm-core@f0258f5020ba9c8b6b44b284bfcafaeb27528a2c` (`CUSTOM_UNVALIDATED` quarantine already integrated).

The atom intentionally separates three provenance objects:

1. exact external calibration/source bytes;
2. parsed in-memory `(time_ns, amplitude)` numerical sample payload;
3. actual resampled/normalized effective runtime kernel consumed by waveform synthesis.

A digest of object 2 does not identify object 1. A digest of object 3 does not establish that either 1 or 2 was measured on a detector. No positive `MEASURED` authorization is introduced here.

## Exact input/output contract

For finite IEC-559 / IEEE-754 binary64 samples, define

`S_sample = "CCB_SIPM_IMPULSE_SAMPLES_V1\0" || LE64(N) || concat_i(LE64(bits(t_i)) || LE64(bits(a_i)))`

and

`H_sample = SHA256(S_sample)`.

For an effective kernel with finite positive sample spacing `dt_ns`, define

`S_kernel = "CCB_SIPM_EFFECTIVE_KERNEL_V1\0" || LE64(bits(dt_ns)) || LE64(M) || concat_j(LE64(bits(h_j)))`

and

`H_kernel = SHA256(S_kernel)`.

Returned identities are `sha256:<64 lowercase hexadecimal characters>`. Signed zero is deliberately collapsed (`-0.0 == +0.0`) before serialization because it is one numerical state for this observable. Non-finite values are rejected rather than inventing a NaN-payload equivalence class. Kernel spacing and exact length are part of the effective identity; therefore history-support extension changes `H_kernel` even when the source samples do not change.

SHA-256 follows NIST FIPS 180-4, DOI `10.6028/NIST.FIPS.180-4`.

## Competing mechanisms and eliminations

- **H1: caller text serialization is the numerical identity.** Eliminated: formatting, precision and locale are not the scientific numerical state.
- **H2: native-memory bytes are the identity.** Eliminated: host endianness/representation would leak into provenance.
- **H3: schema-tagged, count-bound, little-endian binary64 canonicalization.** Survives and is implemented.
- **H4: hash the external source bytes and call that the parsed-sample identity.** Eliminated as a category error; source bytes and parsed numerical values are distinct atoms.
- **H5: caller-provided hash-shaped text authorizes measured provenance.** Eliminated by the existing `CUSTOM_UNVALIDATED` quarantine; this atom computes identities from content rather than trusting labels.

Architecture/compiler differences that genuinely alter the effective floating-point kernel are not silently collapsed; if runtime values differ, their kernel digests differ. That is a provenance signal, not a defect in this atom.

## Deterministic discriminating tests

Core PR `#11` adds `tests/test_impulse_digest.cc` with no RNG and no detector data. Controls include:

- SHA-256 empty known answer `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- SHA-256 `abc` known answer `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`;
- canonical sample `{t=[0,1,2], a=[0,1,0]}` -> `sha256:dbceaf26fdae5b951099d8a76aef391bdc94c53336bbbd0cf63e49fc00a5b094`;
- effective kernel `dt=1 ns`, `{0,1,0}` -> `sha256:aa049b621977903cb9c4cb0423dd1bf6844f59a667c593a906b725531b79e29a`;
- the same prefix plus one trailing zero -> `sha256:d943f8002a50b1f2c83de80aa50495e7511e541563033d2801e6351edb5c08f6`;
- `-0/+0` equivalence;
- one-amplitude tamper sensitivity;
- kernel-length/history-extension sensitivity;
- `dt` sensitivity;
- mismatched vector lengths, non-finite values and non-positive `dt` fail closed.

A standalone authoring sanity check reproduced the expected constants, but the published branch differs in include path/formatting from that local source. Therefore no exact-committed local build PASS is claimed.

## Exact GitHub execution and repository actions

Core branch `audit/impulse-digest-canonicalization` was based exactly on `ccb-sipm-core main@f0258f5020ba9c8b6b44b284bfcafaeb27528a2c`.

Core PR `#11` exact head `9968b1ac771783668e76f7ef24fa4b626bb33a7b` passed Core CI run `31527846708`, job `93899990266`, including checkout, configure, build and CTest. It was marked ready only after that exact-head success, then squash-merged with expected-head guard as exact core main `8ecf6037de9f14cc073f5ed99299a8e78a5fadb3`. A subsequent main-push Core CI run `31528356724` on that exact merge commit completed `SUCCESS`.

This testbeam integration branch was created from exact protected `main@cf3106f9111755f9b51e0388e2bd9feb769242b2`. Its first commit `d89b267afc77d4e87cb6ca8dc4edc0a0e96c91a8` changes only the gitlink `geant4/single_stave/sipm` from `f0258f5020ba9c8b6b44b284bfcafaeb27528a2c` to descendant core `8ecf6037de9f14cc073f5ed99299a8e78a5fadb3` before coordination/archive updates.

## Four sequential AI review passes

### A. Electronics/calibration lead

Background: SiPM single-photoelectron/electronics response calibration and waveform metrology.

Evidence inspected: #1067 acceptance contract, provenance quarantine on `f0258f...`, canonical schema, known-answer/tamper controls, exact-head and merged-main Core CI.

Strongest counter-hypothesis: the parsed numerical samples can stand in for the exact external calibration object.

Attempted falsifier: external files with distinct bytes/formatting can parse to identical numerical pairs. Therefore `H_sample` cannot identify exact external bytes.

Residual uncertainty: no external source parser/byte binding, no bench calibration object, and no same-object runtime-kernel binding.

Vote: **ACCEPT canonical numerical identities / REVISE measured-calibration provenance**.

### B. Adversarial mechanism reviewer

Background: binary serialization, cross-platform representation and provenance fault injection.

Evidence inspected: text/native-memory alternatives, explicit schema/endianness/count contract, signed-zero and tamper controls.

Strongest counter-hypothesis: native-memory or caller text serialization is sufficiently reproducible.

Attempted falsifier: text precision/locale and host byte order produce representation ambiguity unrelated to the intended numerical observable. `-0/+0` also exposes duplicate representations for one intended zero state.

Residual uncertainty: different floating arithmetic may produce different effective kernels; this should remain visible until a separate tolerance/equivalence atom proves otherwise. Same-object runtime binding is still open.

Vote: **ACCEPT canonicalization / BLOCK source-byte equivalence and positive `MEASURED` authorization**.

### C. Independent statistics/validation reviewer

Background: reproducible numerical validation, deterministic known-answer tests and negative controls.

Evidence inspected: standard SHA-256 known answers, independently precomputed payload/kernel constants, tamper controls, exact-head and merged-main Core CI.

Strongest counter-hypothesis: the tests merely restate the implementation.

Attempted falsifier: standard external SHA-256 vectors plus independently computed expected digests constrain both the cryptographic primitive and canonical byte construction; spacing/length/tamper tests discriminate omitted contract fields.

Residual uncertainty: the digest function is not yet bound to the exact runtime kernel consumed by the simulator; no measured detector sample participates.

Vote: **ACCEPT deterministic software oracle / BLOCK detector inference**.

### D. Claims/provenance reviewer

Background: claim ledgers, calibration traceability and source-to-result governance.

Evidence inspected: #1067 unresolved gates, `CUSTOM_UNVALIDATED` semantics, new digest primitive and surviving dependencies.

Strongest counter-hypothesis: canonical source/effective digest primitives alone satisfy #1067.

Attempted falsifier: exact external source-byte binding, same-object runtime-kernel binding, calibration/resampling validation, positive authorization state and historical-output audit are all independently absent.

Residual uncertainty: historical outputs that claimed `MEASURED` without full gates remain unaudited.

Vote: **ACCEPT this child primitive / BLOCK #1067 COMPLETE and public measured-electronics claims**.

## Cross-scale propagation and compatibility

Micro/software level: canonical numerical identities are now content-derived and deterministic.

Meso/electronics level: no calibration meaning is inferred; the existing `CUSTOM_UNVALIDATED` quarantine remains the authority state.

Event/waveform level: effective-kernel hash is not yet computed from the exact same kernel object consumed by convolution, so result provenance is not closed.

Study/claim level: no beam bytes, production Geant4/MC, measured CCB single-PE waveform, DCR calibration, baseline, timing, pile-up, PID, efficiency, rate, ESS, p-value or detector-performance result was regenerated or promoted.

No claim-ledger or wiki row is promoted by this atom. #1067 must remain open/PARTIAL.

## Spawned/surviving child atoms

1. `ARU-ELEC-IMPULSE-DIGEST-RUNTIME-BINDING-001`: compute `H_kernel` from the same history-complete kernel object actually consumed by waveform synthesis and serialize that exact identity; reject reconstructed-copy closure.
2. `ARU-ELEC-IMPULSE-SOURCE-BYTE-BINDING-001`: SHA-256 exact external calibration bytes and bind parser input/output to `H_sample`.
3. `ARU-ELEC-IMPULSE-CALIBRATION-CLOSURE-001`: validate units, polarity, baseline, time zero, normalization and resampling observables against a real calibration object.
4. Positive typed `CUSTOM_UNVALIDATED -> MEASURED` authorization after all required gates pass.
5. Historical-output audit for prior unbound `MEASURED` metadata.

## Next highest-value atom

`ARU-ELEC-IMPULSE-DIGEST-RUNTIME-BINDING-001`: make the exact history-complete kernel consumed by convolution the single object from which the effective digest is computed, with a hostile reconstructed/corrupted-copy control. This is dependency-ready now that the canonical digest primitive exists.

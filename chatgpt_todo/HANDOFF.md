# Latest Handoff

## Canonical impulse numerical identities implemented and integrated for review

The selected atom is `ARU-ELEC-IMPULSE-DIGEST-CANONICALIZATION-001`, a bounded child of open/PARTIAL #1067. Protected testbeam base inspected at selection was `main@cf3106f9111755f9b51e0388e2bd9feb769242b2`; its exact SiPM gitlink was `ccb-sipm-core@f0258f5020ba9c8b6b44b284bfcafaeb27528a2c`, which already contains the `CUSTOM_UNVALIDATED` provenance-state quarantine.

The scientific/provenance problem is that three identities must not be conflated: exact external calibration bytes; parsed numerical `(time_ns, amplitude)` samples; and the actual resampled/normalized history-complete runtime kernel. This atom defines content-derived canonical identities for the latter two only. It does not identify external source bytes and does not authorize `MEASURED`.

For finite IEC-559/IEEE-754 binary64 samples:

`H_sample = SHA256("CCB_SIPM_IMPULSE_SAMPLES_V1\0" || LE64(N) || concat_i(LE64(bits(t_i)) || LE64(bits(a_i))))`.

For the effective kernel:

`H_kernel = SHA256("CCB_SIPM_EFFECTIVE_KERNEL_V1\0" || LE64(bits(dt_ns)) || LE64(M) || concat_j(LE64(bits(h_j))))`.

Signed zero is explicitly collapsed so `-0.0` and `+0.0` represent one numerical state. Non-finite values are rejected. Kernel spacing and exact length participate in identity, so extending pre-window/history response support necessarily changes `H_kernel`. SHA-256 follows NIST FIPS 180-4, DOI `10.6028/NIST.FIPS.180-4`.

Competing mechanisms were separated rather than averaged: caller text serialization is rejected because format/precision/locale are representation choices; native-memory hashing is rejected because host representation leaks into provenance; external source-file hashing is retained as a separate child rather than mislabeled as the parsed-sample identity. Canonical schema-tagged little-endian binary64 serialization survives. Architecture/compiler differences that genuinely alter the effective numerical kernel remain visible as different digests until a separate equivalence/tolerance atom proves otherwise.

## Exact implementation and tests

Core branch `audit/impulse-digest-canonicalization` started from exact `ccb-sipm-core main@f0258f5020ba9c8b6b44b284bfcafaeb27528a2c`. Core PR #11 added `include/ccb/sipm/Digest.hh`, `src/Digest.cc`, `tests/test_impulse_digest.cc`, `docs/impulse_digest_v1.md`, and Core CTest wiring.

The deterministic tests include standard SHA-256 known answers for empty input and `abc`; independently computed canonical sample/kernel known answers; `-0/+0` equivalence; amplitude tamper sensitivity; history/kernel-length sensitivity; sample-spacing sensitivity; and fail-closed mismatched-length/nonfinite/nonpositive-`dt` controls. No RNG, beam data, detector calibration or production MC participates.

PR #11 exact head `9968b1ac771783668e76f7ef24fa4b626bb33a7b` passed Core CI run `31527846708`, job `93899990266`, with checkout/configure/build/CTest. It was marked ready only after this exact-head success and squash-merged with expected-head guard as exact core main `8ecf6037de9f14cc073f5ed99299a8e78a5fadb3`. Independent main-push Core CI run `31528356724` on that exact merged commit also completed SUCCESS.

A local standalone authoring sanity check reproduced the known answers, but the published source differs in include path/formatting; therefore no exact-committed local-build PASS is claimed. GitHub CI is the execution evidence.

## Testbeam integration

Branch `audit/impulse-digest-canonicalization-integration` was created from exact protected `main@cf3106f9111755f9b51e0388e2bd9feb769242b2`. Its first commit `d89b267afc77d4e87cb6ca8dc4edc0a0e96c91a8` changes only `geant4/single_stave/sipm` from `f0258f5020ba9c8b6b44b284bfcafaeb27528a2c` to descendant `8ecf6037de9f14cc073f5ed99299a8e78a5fadb3`; subsequent commits add the immutable atom archive and coordination updates. Do not merge this integration unless the exact final head passes required protected MC Validation and protected main has not moved incompatibly.

Immutable record: `chatgpt_todo/archive/2026-08-11T191700Z_ARU-ELEC-IMPULSE-DIGEST-CANONICALIZATION-001.md`.

## Four sequential AI reviews

**Electronics/calibration lead — ACCEPT canonical numerical identities / REVISE measured-calibration provenance.** Evidence: #1067, existing quarantine, canonical contract, tamper controls and exact Core CI. Strongest counter-hypothesis: parsed samples identify the calibration object. Falsifier: different external byte representations can parse to identical numerical pairs. Residual: source-byte/parser binding, bench calibration, runtime-kernel binding.

**Adversarial mechanism reviewer — ACCEPT canonicalization / BLOCK source-byte equivalence and positive MEASURED authorization.** Evidence: text/native-memory alternatives, schema/endianness/count contract, signed-zero and tamper controls. Strongest counter-hypothesis: ordinary text/native bytes are reproducible enough. Falsifier: precision/locale/endianness ambiguities and duplicate signed-zero representations. Residual: platform-dependent floating results and same-object runtime binding.

**Independent statistics/validation reviewer — ACCEPT deterministic software oracle / BLOCK detector inference.** Evidence: standard SHA-256 known answers, independent expected payload/kernel constants, tamper controls, exact-head plus merged-main Core CI. Strongest counter-hypothesis: tests restate the implementation. Falsifier: standard vectors constrain the hash primitive independently and contract-field perturbations must alter the digest. Residual: exact consumed runtime kernel is not yet bound; no detector sample participates.

**Claims/provenance reviewer — ACCEPT child primitive / BLOCK #1067 COMPLETE and public measured-electronics claims.** Evidence: #1067 acceptance criteria and surviving dependencies. Strongest counter-hypothesis: canonical digest functions complete measured-response provenance. Falsifier: external source-byte binding, same-object runtime-kernel binding, calibration/resampling closure, positive authorization and historical-output audit remain absent.

## Cross-scale boundary and next atom

At micro/software level the numerical digest primitive is deterministic and validated. At mesoscopic electronics level calibration authority is unchanged: sampled impulses remain `CUSTOM_UNVALIDATED` absent further gates. At event/waveform level the effective digest is not yet bound to the exact kernel object actually consumed by convolution. At study/claim level nothing is promoted.

The next highest-value atom is `ARU-ELEC-IMPULSE-DIGEST-RUNTIME-BINDING-001`: restructure the runtime path so the exact history-complete kernel object consumed by waveform synthesis is the same object passed to `CanonicalEffectiveKernelHash` and serialized into run metadata. Include a hostile test in which an independently reconstructed/corrupted copy would produce a different digest and must not satisfy closure. Then continue `ARU-ELEC-IMPULSE-SOURCE-BYTE-BINDING-001`, calibration closure, typed positive authorization and historical-output audit.

#1067 remains open/PARTIAL. #1096 history-horizon convergence and #1065 sub-grid timing remain distinct. No beam bytes, production Geant4/MC sample, measured CCB single-PE calibration, baseline, timing, pile-up, PID, event weights, ESS, p-value, rate, efficiency or detector-performance result was regenerated or promoted.

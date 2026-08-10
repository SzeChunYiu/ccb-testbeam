# Latest Handoff

## Merged milestone: configured scattering-source readiness (#1182)

Protected `main` now contains PR #1183 as squash commit `d62075693df5e0f58b64078097ddc4ebea86d90f`. Exact PR head `0f5fe23bfd3ea2e4aa2ff019b108433571bdcf3e` passed MC Validation run `31436595715`: clean ruff, `1466 passed, 1 skipped, 8 xfailed, 1 xpassed`. This validates the bounded repository/static software contract only; the workflow does not compile `geant4/src_patch`.

### Contract now on main

Tracked `ScatteringGenerator.cc/.hh` implement per-instance readiness independent of global event ID:

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`.

For configured source mode, `GeneratePrimaryVertex()` calls `EnsureSourceReady()` before event RNG, so event generation requires the same generator instance to be `CONFIGURED_READY`. Uniform `theta_cm` is restricted to explicit `CSFile=null`; missing/invalid configured source or stopping data and inconsistent configured CDF state are fatal rather than a success exit or hidden uniform fallback. Stopping and cross-section rows are parsed into local validated vectors and published transactionally, and post-readiness file identity changes fail closed.

The central source law remains `linear_node_pdf_exact_inverse_v1`, `measured_table_support_truncate_v1`, `unit_direct_sampling_v1`; Table-VI SHA-256 is `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`.

### External deployment parity

The historical text-rewrite `patch_scatter.py` was a distinct stale representation that still embedded the superseded fail-open source path. It has been replaced by an exact-byte installer: the external root is mandatory via `--src-root`; each destination file is atomically replaced from the tracked reviewed `.hh/.cc` bytes; successful return then requires the complete pair to reread byte-identically. A temp-tree regression proves successful-return pair parity, while missing target layout is a negative control.

Two-path filesystem replacement is not crash-atomic. An interruption between header/source replacement can leave a partial external deployment, so a material child remains: the future build front door must re-verify both source identities immediately before compilation. Static source parity is therefore not executable provenance.

### CI falsifiers retained

Earlier runs were not hidden. Run `31433066785` failed two regression expectations after 1462 passing tests: one fixture confused enum declaration with scoped readiness usage and one test froze incidental prose instead of inverse mechanics. After correction, run `31436259144` exposed one further negative-control mismatch: a bare non-class-qualified `GeneratePrimaryVertex()` fixture was correctly not recognized as the production per-instance call contract. That fixture was weakened explicitly rather than weakening the production audit. Final run `31436595715` then passed all authorising repository checks.

### Four sequential review votes

- **Source/runtime lead — ACCEPT static mechanism / BLOCK runtime authorisation:** the event-ID dependency and configured-source fail-open paths are removed in tracked source, but exact external executable/build/run-manager/thread provenance and real stopping-table compatibility remain unbound.
- **Adversarial mechanism reviewer — ACCEPT successful-return deployment parity / BLOCK compiled fault matrix:** stale text-patch drift is removed, but compile/link behavior, Geant4 fatal semantics, worker command propagation, interrupted-deployment pre-build verification and hostile runtime fixtures remain open.
- **Independent statistics/validation reviewer — ACCEPT deterministic software closure / BLOCK physics inference:** state-machine and byte-parity tests validate software semantics only, not a generated angular population, detector response or DATA/MC agreement.
- **Claims/provenance reviewer — BLOCK CL-021 promotion:** `geant4/setup_and_run.sh` still clones hibeam_g4 without a pinned commit, immutable production `dedx_p_in_CD2.txt` identity is absent, and no production manifest binds source/stopping/build/thread/seeds/event count.

### Next highest-value atom

`ARU-MC-CS-COMPILED-PROVENANCE-001`: establish one fail-closed build/run front door that binds exact hibeam_g4 commit/tree, installed source/header hashes, Geant4/compiler/build identity, run-manager/thread mode, immutable stopping/source inputs, model IDs, seeds and event count; re-verify installed source pair before compilation; then compile and execute missing/empty/one-row/malformed/nonfinite/nonmonotonic/zero-density source/stopping fixtures, explicit `CSFile=null`, repeated readiness, seeded sequential controls and multi-worker controls where supported.

#1182, #1178, #1179 and CL-021 remain open/gated. No production Geant4, beam ROOT, B2/B8, detector response, PID, penetration, timing, energy, pile-up, ESS, p-value, rate or detector-performance quantity was regenerated or promoted.

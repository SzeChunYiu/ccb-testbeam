# Active Task

- **Task ID:** `ARU-S00-VERIFIED-READ-SNAPSHOT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T081600Z`
- **Initial remote main SHA:** `ef4f3cbabe010285558a425fc3e92d525b1803a2`
- **Validated merge before atom selection:** PR #1148 exact head `820e157b0b5ec9bd0d05cb60a889a547e2228c13` had MC Validation CI run 933 = `success`; squash-merged to main as `96be3588241753601a4a96e6451527e5b3ebfe6b`.
- **Issue:** `#1149`
- **Parent issue:** `#1147`; upstream transaction parent `#1110`.
- **Branch:** `fix/s00-verified-read-snapshot`
- **Selected atom:** `content-bound pointer -> mutable generation pathname -> verification -> exact bytes consumed by an authorising downstream reader`.
- **Confirmed gap:** `resolve_artifact()` verifies bytes and then returns a pathname. A later read can observe different bytes after in-place or hard-link mutation.
- **Surviving design:** stream the source once into a private secure temporary snapshot while hashing the exact copied blocks; yield the snapshot only when its digest equals the digest in the one-time pointer snapshot.
- **Implemented:** `s00_verified_read.py`, exact-byte snapshot metadata/cleanup, hard-link and pointer-swap controls, and a hostile test preserving the old resolver TOCTOU counterexample.
- **Expert votes:** filesystem/reconstruction `ACCEPT design / pending CI`; adversarial `ACCEPT local snapshot contract / BLOCK direct-path authorisation`; statistics/validation `ACCEPT deterministic tests / pending CI`; claims/provenance `REVISE #1110 / no CL-001 promotion`.
- **Scientific boundary:** no beam ROOT data, Geant4, S00 count regeneration, timing/PID/penetration result, or detector-performance quantity changed.
- **Status:** `ACTIVE / IMPLEMENTED_PENDING_EXACT_HEAD_CI_AND_CONSUMER_MIGRATION`

# Active Task

- **Task ID:** `ARU-S00-PUBLICATION-CONTENT-IDENTITY-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T074800Z`
- **Initial remote main SHA:** `5cb0b9426dc2f9e1b58a33fcb36c2e0c3eaa8f0a`
- **Validated merge before atom selection:** PR #1145 exact-head `065c0b1a08b0893e84221be11483d8a6817ff92e` had MC Validation CI run 919 = `success`; squash-merged to main as `ef4f3cbabe010285558a425fc3e92d525b1803a2`.
- **Issue:** `#1147`
- **Parent issue:** `#1110`
- **Branch:** `fix/s00-publication-content-identity`
- **Selected atom:** `immutable generation path identity -> artifact byte identity -> authority pointer -> verified downstream resolution`.
- **Confirmed gap:** the v1 pointer committed only `(generation_id, relative_path, model_identity)`. Files remained writable and `resolve_artifact()` checked only `is_file()`, so post-publication byte mutation could silently change scientific content under the same authority. Lexically safe relative paths could also name symlinks because `is_file()` follows them.
- **Surviving design:** pointer schema v2 binds one SHA-256 digest per logical artifact; publication rejects symlink components / physical escapes, hashes and fsyncs authoritative files before the generation move, revalidates containment + digest after the move, and the resolver re-hashes before returning authority.
- **Implemented:** content-bound pointer payload; strict digest parser/key parity; SHA-256 generation; symlink/realpath containment guard; post-move digest revalidation; resolver hash verification; hostile content-mutation/symlink/malformed-pointer tests.
- **Expert votes:** filesystem/reconstruction `ACCEPT design / pending exact-head CI`; adversarial `ACCEPT after symlink + post-move controls / residual direct-bypass risk`; validation `ACCEPT deterministic contract / pending CI`; claims/provenance `BLOCK downstream promotion until #1110 producer/consumers use verified resolution`.
- **Scientific boundary:** no raw beam ROOT data, Geant4 job, S00 count regeneration, timing/PID/penetration result, or detector-performance quantity changed.
- **Status:** `ACTIVE / IMPLEMENTED_PENDING_PR_CI`
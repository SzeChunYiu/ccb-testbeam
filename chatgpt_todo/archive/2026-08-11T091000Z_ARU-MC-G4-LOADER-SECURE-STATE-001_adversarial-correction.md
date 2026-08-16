# ARU-MC-G4-LOADER-SECURE-STATE-001 — adversarial correction

Status: PARTIAL. This continuation supersedes the earlier interpretation of `AT_SECURE=0` in `2026-08-11T085000Z_ARU-MC-G4-LOADER-SECURE-STATE-001.md` while preserving that record as audit history.

## Concern `PROV-G4-LOADER-SECURE-002` — post-start environment cannot prove libc non-secure state

The first implementation treated kernel `AT_SECURE=0` plus an observed runtime `GLIBC_TUNABLES` value as sufficient to call loader-control environment values eligible inputs, with a special block when the observed tunable contained `glibc.rtld.enable_secure=1`.

Adversarial review falsified that interpretation using GNU libc's own implementation/test history: `glibc.rtld.enable_secure=1` can set libc secure mode even when kernel `AT_SECURE` is zero, and secure processing skips/removes environment variables including `GLIBC_TUNABLES`. Therefore absence of that tunable in a post-start `/proc/<pid>/environ`-derived receipt cannot prove it was absent at `execve` time. The observable is one-sided.

Correct invariant:

- `AT_SECURE=1` -> `SECURE_CONFIRMED_BY_KERNEL_AT_SECURE`; loader-control environment values must not be used as search authority.
- `AT_SECURE=0` -> `UNRESOLVED_KERNEL_AT_SECURE_ZERO`; loader-control environment values also must not be used as search authority until pre-exec launch environment + exact libc/loader semantics are independently bound.

Thus the atom now measures the kernel secure-execution input exactly but does **not** claim a complete effective glibc secure-mode Boolean for the zero case.

## Corrected implementation and tests

Tool correction commit: `8dbec7cdc8332d77c232e45a544943052a3fcf36`.

Test correction commit: `5a726711382e4164d52f7897f6a01bc05f469469`.

Exact GitHub-blob-bound local rerun, Python 3.13/Linux/no RNG:

`PYTHONPATH=/tmp/ccb_loader_exact python -m pytest -q /tmp/ccb_loader_exact/tests/test_geant4_loader_secure_state_attestation.py` -> `10 passed in 0.04s`.

- corrected tool: 11540 bytes; SHA-256 `b6821361ab5a7e13f71906accecbad3a7e7f9fc130432af262413413e69e7748`; Git blob SHA-1 `3102596db172b9f6f901d6768b7ad16042e7254c`.
- corrected tests: 7343 bytes; SHA-256 `af65d252ce7a5d57d71651144f60a9098b7c3ce672353a87f75c11b628465257`; Git blob SHA-1 `da51b78d275c4192636e5e4de6c7fece9fedb8b8`.

The revised control `test_post_start_tunable_observation_cannot_upgrade_at_secure_zero` explicitly demonstrates that even a post-start receipt showing `glibc.rtld.enable_secure=1` does not upgrade the kernel-zero case into a fully reconstructed loader decision; the result remains unresolved pending pre-exec provenance.

## Four sequential review update

- Runtime/physics integration lead — **REVISE** earlier zero-case interpretation; **ACCEPT** one-sided kernel-state measurement.
- Adversarial systems reviewer — **ACCEPT correction / BLOCK effective non-secure claim**. Strongest falsifier is glibc secure processing removing/skipping its own launch tunable from the environment seen by the program.
- Independent validation reviewer — **ACCEPT corrected deterministic oracle / BLOCK runtime generalisation**. Ten exact committed-code fixtures pass; no real HIBEAM process exercised.
- Claims/provenance reviewer — **BLOCK CL-021 promotion** unchanged.

## Spawned child

`ARU-MC-G4-LOADER-PREEXEC-ENV-001`: bind the exact environment and loader invocation at the `execve` boundary (or an equivalently immutable wrapper receipt) before the dynamic loader can sanitize it, together with exact loader/libc identity. Parent `ARU-MC-G4-LOADER-SEARCH-001` is not complete until this and the cache/config, cwd, token/hwcaps, preload/audit and later-load children are closed.

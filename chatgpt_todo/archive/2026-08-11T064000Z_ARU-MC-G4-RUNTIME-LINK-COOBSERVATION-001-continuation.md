# ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001 — mechanism falsifier continuation

## Executed Linux pathname-retargeting falsifier

Environment: Python 3.13.5; Linux 6.18.35 x86_64; glibc 2.41; no RNG.

A temporary file `mapped.so` containing `old-object-bytes` was opened with `O_RDONLY|O_CLOEXEC`. While that descriptor remained open, `os.replace(replacement.so, mapped.so)` retargeted the pathname to a different inode containing `new-object-bytes`. The old descriptor was then read with `pread`.

Observed JSON from the executed control:

```json
{"fd_bytes":"old-object-bytes","fd_identity_stable":true,"fd_key_after":[254,0,2769436],"fd_key_before":[254,0,2769436],"fd_sha256":"ff613fded8e7cb71e426a1329672eaa56b94827832d2b8da735c2ff0fd894670","path_bytes":"new-object-bytes","path_key_after_replace":[254,0,2769437],"path_retargeted":true,"path_sha256":"337abdd174a6b65b0dad5ee70be1c349e09a54a06f3780e0c0450a4feea74430"}
```

This directly falsifies the local equivalence hypothesis "later path open/read necessarily observes the same object as the already-open descriptor". It supports the bounded same-open-descriptor mechanism used by PR #1208. This is an OS/provenance falsifier only; it is not a Geant4 or detector result.

## Residual adversarial concern

The descriptor snapshot is stable by before/after `fstat` during the byte read, and hash plus ELF parsing consume the same immutable `bytes` snapshot. A mutation after that snapshot is outside this atom's instantaneous content claim; event-interval stability remains owned by `ARU-MC-G4-LATE-DLOPEN-001` / runtime-stability children. No claim is made that all mapped-object contents are observed simultaneously.

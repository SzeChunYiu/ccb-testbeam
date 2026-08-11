# S00 verified-read contract — issue #1149

**Authorising API:** `ccb_mc_validation.s00_verified_read.verified_artifact_snapshot`  
**Non-authorising pathname helper:** `ccb_mc_validation.s00_publication.resolve_artifact`

## Contract

`resolve_artifact()` proves `H(file at t_v) = H(pointer)` and returns a `Path`.
It does **not** prove that bytes later read from that pathname equal the verified
bytes (`t_c > t_v` TOCTOU / hard-link alias).

Authorising consumers MUST:

1. call `verified_artifact_snapshot(...)`, and
2. read only the yielded private snapshot bytes (hash-bound at copy time).

Threat model: concurrent/cooperating filesystem mutation and pathname
replacement. Not a defence against privileged writers altering the reader's
private temporary file or process memory.

Negative control: `tests/test_s00_verified_read_negative_control.py`.

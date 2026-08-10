# Active Task

- **Task ID:** `ARU-S00-VERIFIED-READ-SNAPSHOT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T081600Z`
- **Initial remote main SHA:** `ef4f3cbabe010285558a425fc3e92d525b1803a2`
- **Validated prerequisite merge:** PR #1148 exact head `820e157b0b5ec9bd0d05cb60a889a547e2228c13` had MC Validation CI run 933 = `success`; squash-merged as `96be3588241753601a4a96e6451527e5b3ebfe6b`.
- **Validated atom merge:** PR #1150 exact head `4675627807efff576cd9aa51b977b4480b64976b` had MC Validation CI run 943 = `success` (`1257 passed, 1 skipped, 8 xfailed, 1 xpassed`); squash-merged as `83256325f5cf9021912578963fdc19f6b9257df2`.
- **Issue:** `#1149` remains open.
- **Parent issue:** `#1147`; upstream transaction parent `#1110`.
- **Selected atom:** `content-bound pointer -> mutable generation pathname -> verification -> exact bytes consumed by an authorising downstream reader`.
- **Confirmed gap:** `resolve_artifact()` verifies bytes and then returns a pathname. A later read can observe different bytes after in-place or hard-link mutation.
- **Merged survivor:** `verified_artifact_snapshot()` streams the source into a private secure temporary snapshot while hashing the exact copied blocks and yields only after equality with the one-time pointer snapshot.
- **Validated controls:** pre-copy tamper fails closed; post-copy source/hard-link mutation cannot change the snapshot; pointer swap retains one complete old generation; the old `resolve_artifact()->later Path read` TOCTOU remains as an explicit negative control.
- **Expert votes after CI:** filesystem/reconstruction `ACCEPT local primitive`; adversarial `ACCEPT snapshot / BLOCK direct-path authorisation`; statistics/validation `ACCEPT deterministic closure`; claims/provenance `REVISE #1110 / no CL-001 promotion`.
- **Remaining #1149 acceptance:** benchmark the real selected-table copy/read overhead and migrate authoritative consumers to the verified snapshot API. Direct legacy paths and `resolve_artifact()->reopen Path` remain non-authorising for strict concurrent-reader provenance.
- **Coordination:** active PR #1146 changes `01_build_pulse_table_from_root.py`; reconcile that producer work before #1110 publication integration rather than creating an overlapping producer branch.
- **Scientific boundary:** no beam ROOT data, Geant4, S00 count regeneration, timing/PID/penetration result, or detector-performance quantity changed.
- **Status:** `PARTIAL / SAME_BYTES_PRIMITIVE_VALIDATED_ON_MAIN / CONSUMER_MIGRATION_AND_REAL_SCALE_BENCHMARK_OPEN`

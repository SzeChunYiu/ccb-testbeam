# Active Task

- **Task ID:** `ARU-CI-BASE-FRESHNESS-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Branch-point protected main:** `57407692c7d3af5de82585c5597b666cd74ad742` (PR #1187 merged after exact-head MC Validation run `31426849092`).
- **Selected atom:** whether a green PR-head CI result can authorise protected-main integration when the head does not contain the current `main` commit.
- **Exact discriminator:** PR #1186 head `4a2d1909b681517eee72389bf5f8d3604e4b8f54` had successful exact-head `test` checks but was `behind`; compare against then-current `main@a1bcb6a...` gave `status=diverged`, `ahead_by=11`, `behind_by=1`, merge base `f5f96951...`, and the normal protected squash merge was rejected with HTTP 405. Current-base control PR #1187 had the same CI workflow, `mergeable_state=clean`, and merged normally as `57407692...`.
- **Leading mechanism:** strict current-base ancestry is the operative merge gate; a generic Check-Runs/classic-status mismatch is weakened by the #1187 control. Exact hidden protection settings remain unobservable to the connector (403), so the configured rule itself is not claimed as directly inspected.
- **Implementation:** issue #1188 plus `tools/audit/validate_pr_base_freshness.py`, which emits `pr_base_freshness_v1` JSON and exits 0 only when the exact base is an ancestor of the head with `behind_by=0`; stale/diverged is exit 2, inspection failure exit 3.
- **Local deterministic validation:** synthetic Git-graph tests exercise stale/diverged, refreshed/current-base, CLI JSON/exit codes, and missing-ref fail-closed behavior; `pytest -q tests/test_pr_base_freshness.py` -> `3 passed in 12.97s`. No RNG. Local ruff execution was unavailable because the installed executable returned a permission error; repository exact-head CI is required.
- **Parallel scientific state:** interpolation-order sensitivity from #1187 is now on main but remains deterministic source-model sensitivity only. PR #1186 source-UQ work is not on main; #1179, #1178, #1182 and CL-021 remain open/gated.
- **Next experiment:** refresh #1186 onto current main by a normal non-force workflow, verify `behind_by=0`, require fresh `test` CI, then retry the normal protected merge. Apply the same ancestry audit to stale readiness PR #1183.
- **Status:** `ACTIVE / A_B_DISCRIMINATOR_EXECUTED / LOCAL_GIT_GUARD_IMPLEMENTED / EXACT_HEAD_REPOSITORY_CI_PENDING / #1186_REFRESH_PENDING / NO_PHYSICS_CLAIM_CHANGE`

# Latest Handoff

## Selected atom: current-base ancestry as merge-authorisation evidence (#1188)

Protected main advanced during this session from `a1bcb6a68630845c31c0b8ebcd5b45de0cea1dd6` to `57407692c7d3af5de82585c5597b666cd74ad742` when PR #1187 passed exact-head MC Validation run `31426849092` and was squash-merged normally. The merged work quantifies interpolation-order sensitivity only; #1178/#1179/#1182 and CL-021 remain open/gated.

### Discriminator

PR #1186 head `4a2d1909b681517eee72389bf5f8d3604e4b8f54` had successful exact-head `test` checks from MC Validation run `31426279702`, yet GitHub reported `mergeable_state=behind`. Against then-current main `a1bcb6a...`, the compare graph was `diverged`, `ahead_by=11`, `behind_by=1`, merge base `f5f96951c3f56986769a16cd53ab8e23dee3e287`. A normal squash merge with the exact expected head was rejected with HTTP 405, `Required status check "test" is expected.` No bypass or force update was attempted.

Control PR #1187 used the same required workflow, reported `mergeable_state=clean`, completed its `test` job successfully, and the same normal protected merge path succeeded. This sharply weakens the earlier generic Check-Runs/classic-status mismatch hypothesis and makes stale-base ancestry the leading mechanism for #1186's rejection. Exact branch-protection configuration remains inaccessible to the connector (403), so the hidden configuration is still a residual uncertainty.

### Implemented guard

Issue #1188 owns `ARU-CI-BASE-FRESHNESS-001`. On branch `audit/ci-base-freshness-contract`, `tools/audit/validate_pr_base_freshness.py` checks the local Git graph only. Given exact protected base and PR head refs, it resolves both commits, records their merge base and left/right commit counts, checks base ancestry, emits versioned JSON, and exits:

- 0 for exact current-base ancestry (`behind_by=0`),
- 2 for stale/diverged ancestry,
- 3 if the graph itself cannot be inspected.

It intentionally does not conflate ancestry with required-check status; both gates must pass.

A synthetic Git-repository falsifier was executed locally with no RNG. A feature branched before one new main commit yielded `behind_by=1`, `ahead_by=1` and nonauthorising status; a feature created from the new main yielded `behind_by=0`, `ahead_by=1` and authorising status; an unknown ref failed closed. `pytest -q tests/test_pr_base_freshness.py` returned `3 passed in 12.97s`. Local ruff could not be executed because the available executable returned an OS permission error, so exact-head repository CI remains mandatory before merge.

### Four sequential review votes

- **Scientific-software lead — ACCEPT mechanism / REVISE workflow:** current-base control falsifies a generic check-API explanation; exact hidden protection config remains unknown.
- **Adversarial reviewer — BLOCK stale-head authorisation:** rerunning checks on unchanged stale ancestry does not test the current integration state.
- **Independent validation reviewer — ACCEPT A/B discriminator / REQUIRE real refresh rerun:** causal closure requires #1186 refreshed to current main, fresh CI, and a successful normal protected merge.
- **Claims/provenance reviewer — BLOCK any statement that #1186 is on main:** its branch result is reviewable but absent from protected main.

### Immediate handoff

1. Wait for / inspect exact-head repository CI on the new #1188 guard PR; do not merge it before green CI.
2. Refresh #1186 onto the latest main through a normal **non-force** workflow, record new head and merge base, verify `behind_by=0`, and require fresh MC Validation CI before retrying merge.
3. Audit PR #1183 similarly; its recorded base `f5f96951...` is stale relative to current main and it owns the audit precursor to #1182's P0 source-readiness fix.
4. Do not let this repository-provenance repair promote any source, detector, ESS, p-value, PID, timing, penetration, energy or pile-up claim.

No beam ROOT bytes were opened and no production Geant4 campaign was run in this atom.

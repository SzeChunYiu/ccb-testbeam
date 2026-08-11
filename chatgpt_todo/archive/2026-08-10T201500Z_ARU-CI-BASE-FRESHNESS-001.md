# ARU-CI-BASE-FRESHNESS-001 — current-base ancestry as merge-authorisation evidence

Date: 2026-08-10
Parent: repository action / protected-main provenance
Canonical issue: #1188

## Atomic contract

A green PR-head validation result is not sufficient evidence for protected-main integration when the PR head does not contain the current main commit. Define current main `M`, PR head `H`, and `B=merge_base(M,H)`. For head-only CI to be treated as merge-authorising, require `B=M`, equivalently `behind_by=0`, unless a separately protected merge-result commit containing both current main and the PR changes has itself been validated.

The provenance tuple for an authorising merge is `{main_sha_before, pr_head_sha, merge_base_sha, behind_by, required_check_run_ids, merge_result_sha}`.

## Mechanism universe

1. Strict current-base ancestry: stale heads can be green but are not acceptable integration states.
2. Check-Runs/classic-status mismatch: protection might fail to recognize successful checks.
3. Transient status propagation: protection might temporarily lag a completed run.
4. Merge conflict: content conflict could block despite successful tests.
5. Force/bypass repair: rejected by repository policy and scientific provenance.

Rerunning CI on an unchanged stale head is observationally equivalent for ancestry and is not a separate repair mechanism.

## Executed discriminator

### Stale world — PR #1186

Head `4a2d1909b681517eee72389bf5f8d3604e4b8f54` had successful MC Validation CI run `31426279702` and successful exact-head `test` Check Runs. GitHub nevertheless reported `mergeable_state=behind`. Comparing then-current `main@a1bcb6a68630845c31c0b8ebcd5b45de0cea1dd6` to the head gave `status=diverged`, `ahead_by=11`, `behind_by=1`, with merge base `f5f96951c3f56986769a16cd53ab8e23dee3e287`. A normal squash merge with the exact expected head was rejected with HTTP 405, `Required status check "test" is expected.` No bypass or force update was attempted.

### Current-base control — PR #1187

Head `34b6404355156e45f2f95924069ed5381359de6f` used the same MC Validation CI workflow. Run `31426849092` completed successfully through checkout, package installation, lint, unit tests, diagnostic upload, and final enforcement. GitHub reported `mergeable_state=clean`. The same normal protected squash-merge path succeeded and created `main@57407692c7d3af5de82585c5597b666cd74ad742`.

The A/B result strongly favors stale-base ancestry as the operative mechanism for #1186 and weakens a generic check-API mismatch. Exact branch-protection configuration remains unavailable to the connector (403), so the hidden protection rule is not claimed as directly observed.

## Executable repair guard

`tools/audit/validate_pr_base_freshness.py` is a local Git-graph validator. It resolves both refs, computes the merge base and `git rev-list --left-right --count BASE...HEAD`, checks `git merge-base --is-ancestor BASE HEAD`, emits JSON, and returns:

- `0`: exact current base is an ancestor (`CURRENT_BASE`);
- `2`: stale/diverged base (`STALE_OR_DIVERGED_BASE`);
- `3`: graph inspection itself failed (`INSPECTION_FAILED`).

It deliberately does not inspect required check APIs; ancestry and CI/check authorization remain separate gates.

Focused local falsifiers were executed in a synthetic Git repository with no RNG: a feature branched before a new main commit returned `behind_by=1`, `ahead_by=1`, nonauthorising; a feature branched from the new main returned `behind_by=0`, `ahead_by=1`, authorising; an unresolved ref failed closed. Command: `pytest -q tests/test_pr_base_freshness.py` -> `3 passed in 12.97s` in the available Python 3.13 environment. Ruff could not be run locally because the available `ruff` executable returned an OS permission error; repository CI is therefore required before merge.

## Cross-atom propagation

This atom changes no detector model and no scientific estimator. It changes the meaning of evidence used before repository publication: stale-head green CI cannot be propagated upward as proof that a study/code/claim change is validated on current main. PR #1186 remains source-UQ research only until refreshed and retested; #1179 and CL-021 remain gated independently. PR #1183 is also stale relative to current main and must be refreshed before its readiness audit can authorize any follow-on #1182 implementation.

## Four sequential review passes

### Domain / scientific-software lead — ACCEPT mechanism, REVISE workflow
Evidence: exact compare graph, successful and failed protected merge attempts. Strongest counter-hypothesis: generic Check-Runs API mismatch. Attempted falsifier: #1187 used the same workflow/check mechanism and merged while current-base clean. Residual uncertainty: hidden protection configuration.

### Adversarial mechanism reviewer — BLOCK stale-head authorisation
Evidence: #1186 exact head green but one commit behind and rejected. Strongest counter-hypothesis: transient propagation delay. Attempted falsifier: repeated normal merge after checks completed still failed, while ancestry remained stale. Residual: races where main advances after a refresh.

### Independent validation reviewer — ACCEPT A/B discriminator, REQUIRE refreshed rerun
Evidence: stale+green+rejected versus current+green+merged. Strongest counter-hypothesis: content-specific protection behavior. Attempted falsifier: identical required workflow/job name and merge method. Residual: causal closure requires refreshing #1186 and observing a new successful protected merge.

### Claims/provenance reviewer — BLOCK any statement that #1186 is on main
Evidence: remote main SHA and rejected merge. Strongest counter-hypothesis: green CI alone constitutes publication. Attempted falsifier: the branch changes are absent from remote main. Residual: refreshed merge and post-merge handoff correction.

## Child atoms

- CI-FRESHNESS-CHILD-01: safely refresh #1186 without force, rerun required CI, and re-attempt protected merge.
- CI-FRESHNESS-CHILD-02: audit #1183 and other open scientific PRs for stale ancestry.
- CI-FRESHNESS-CHILD-03: decide whether the Git-graph validator should become a formal workflow/session gate without introducing a self-invalidating base-update race.

Status: PARTIAL. The discriminator and local guard are implemented; repository exact-head CI and the real stale-branch refresh experiment remain outstanding.

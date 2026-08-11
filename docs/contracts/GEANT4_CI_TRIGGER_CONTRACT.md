# Geant4 CI Trigger Contract

**Contract ID:** `ARU-CI-G4-TRIGGER-001`  
**Concern ID:** `CI-G4-ROUTE-001`  
**Status:** deterministic routing precondition; not compiled-Geant4 validation.

## Contract

Protected `main` requires job `test`. GitHub's authoritative Actions documentation states that `paths` filters gate `push`/`pull_request` workflow creation and that a workflow skipped by path filtering leaves an associated required check pending, blocking merge. Therefore the stronger repository invariant is not merely “remember every material directory in a PR allow-list”; the **required pull-request workflow must be unfiltered by path**.

Required routing invariant:

```text
pull_request exists
and pull_request has neither paths nor paths-ignore
and geant4/** ∈ on.push.paths
and test ∈ jobs
```

Authoritative documentation: GitHub Actions, “Workflow syntax for GitHub Actions”, section `on.<push|pull_request|pull_request_target>.<paths|paths-ignore>`, and “Troubleshooting required status checks”.

This is a software/provenance precondition only. The current `test` job installs the Python package, runs curated ruff checks and `pytest tests/ -q --ignore=tests/integration`; it does **not** compile `geant4/src_patch`, link the external `hibeam_g4` executable, execute Geant4, or validate detector/source physics.

## Repository discriminator

PR #1192 is a concrete negative-control witness. Its exact head `bef24345e815152e22523a44b708c4359ad2958f` changes only three files under `geant4/src_patch/`, yet no `MC Validation CI` workflow run is associated with that head. The pre-repair workflow path filters omit `geant4/**`, while protected `main` requires the `test` status. This is one manifestation of the more general contradiction between a required check and a path-filtered pull-request workflow.

PR #1192 is independently unsafe to merge: its patch restores event-ID-zero source initialization already removed by validated main. It was closed as superseded; useful provenance ideas must be reimplemented from current main without restoring that mechanism.

## Acceptance criteria

1. `pull_request` exists with no `paths` or `paths-ignore` filter, so every PR can produce the required `test` result.
2. `geant4/**` remains in `push.paths`, preserving validation routing for direct Geant4-path pushes as well.
3. The workflow still defines job `test`.
4. A repository validator fails closed on a PR path filter, missing Geant4 push route, or missing `test` job.
5. Exact-head repository CI passes after the workflow change.

## Scientific boundary and child atoms

Passing this contract means only that pull requests cannot evade or deadlock the repository's existing static/Python validation lane because of path selection. Authorising generator runs still require `ARU-MC-CS-COMPILED-PROVENANCE-001`: pinned external `hibeam_g4` source/tree, exact installed source identities, compiler/Geant4/build/run-manager/thread provenance, immutable stopping/source inputs, seeds/event counts, compiled hostile fixtures, and a content-bound run manifest. #1182, #1178, #1179 and CL-021 remain open/gated until those independent conditions pass.

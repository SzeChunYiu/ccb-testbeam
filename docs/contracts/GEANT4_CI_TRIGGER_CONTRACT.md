# Geant4 CI Trigger Contract

**Contract ID:** `ARU-CI-G4-TRIGGER-001`  
**Status:** deterministic routing precondition; not compiled-Geant4 validation.

## Contract

For the protected `MC Validation CI` workflow, any pull request or push that changes a path under `geant4/**` must be routed to the workflow containing the required branch-protection job `test`.

Required routing invariant:

```text
for event in {push, pull_request}:
    geant4/** ∈ on[event].paths
and
    test ∈ jobs
```

This is a software/provenance precondition only. The current `test` job installs the Python package, runs curated ruff checks and `pytest tests/ -q --ignore=tests/integration`; it does **not** compile `geant4/src_patch`, link the external `hibeam_g4` executable, execute Geant4, or validate detector/source physics.

## Repository discriminator

PR #1192 is a concrete negative-control witness. Its exact head `bef24345e815152e22523a44b708c4359ad2958f` changes only three files under `geant4/src_patch/`, yet no `MC Validation CI` workflow run is associated with that head. The pre-repair workflow path filters omit `geant4/**`, while protected `main` requires the `test` status. Thus a material Geant4-only change can receive neither the expected static validation nor a satisfiable required-check path.

## Acceptance criteria

1. `geant4/**` is present in both `push.paths` and `pull_request.paths`.
2. The workflow still defines job `test`.
3. A repository validator fails closed if either route or the required job is removed.
4. Negative controls cover a missing pull-request route and a renamed/missing required job.
5. Exact-head repository CI passes after the workflow change.

## Scientific boundary and child atoms

Passing this contract means only that Geant4-path changes enter the repository's existing static/Python validation lane. Authorising generator runs still require `ARU-MC-CS-COMPILED-PROVENANCE-001`: pinned external `hibeam_g4` source/tree, exact installed source identities, compiler/Geant4/build/run-manager/thread provenance, immutable stopping/source inputs, seeds/event counts, compiled hostile fixtures, and a content-bound run manifest. #1182, #1178, #1179 and CL-021 remain open/gated until those independent conditions pass.

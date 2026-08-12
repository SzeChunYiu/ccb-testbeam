# ADR-WAVE-D-LANE01: Authorising S00 reads use snapshots only

**Status:** accepted
**Date:** 2026-08-12
**Lane:** Wave D Lane 01
**Issues:** #1149

## Context

PR #1150 introduced `verified_artifact_snapshot`, which copies-and-hashes into a
private file. The remaining contract gap is social/API: callers can still open
the mutable generation pathname after a successful hash verification.

## Decision

1. Expose `authorising_artifact_snapshot` as the authorising API surface.
2. Provide `forbid_generation_path_for_authorising_read` so audits/tests can fail
   closed when a generation pathname is presented as an authorising read.
3. Do not claim privileged-attacker resistance beyond the existing snapshot
   threat model.

## Consequences

Authorising consumers must read snapshot bytes. Generation pathnames remain
valid for publication/staging internals only.

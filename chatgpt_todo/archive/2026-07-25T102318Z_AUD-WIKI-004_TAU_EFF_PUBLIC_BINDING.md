# Immutable handoff — AUD-WIKI-004

## Identity

- UTC stamp: `2026-07-25T102318Z`
- Initial remote `main`: `dcd30497d7e83a35d686b8835aefdb2537fbcf02`
- Task: root-WIKI exact S10b live10 public-binding audit
- Destination: direct commits to `main`; no force-push or history rewrite

## Repository state reviewed

Reviewed current main history, root WIKI, exact-width `CL-011`, Chapter 5's
concurrent correction, existing WIKI validators, open pull requests, closed PR
#868, and the current-head combined status. PR #868 is closed, unmerged, and
non-mergeable. The initial head has no attached status checks.

## Finding

The WIKI canonical table and pile-up section remain inconsistent with the
canonical S10b contract. They round the value, promote the result to
`VALIDATED`, omit the exact run-bootstrap interval and estimand limitations,
and in the canonical table invent stat/syst components and use the wrong truth
type.

## Better method

Added a strict UTF-8, single-read, exact-width, location-bound validator. Exact
tokens placed elsewhere cannot satisfy stale public claim locations. It checks
central value, interval, counts, status, truth type, missing uncertainty
components, source interpretation, blocker, unique section anchors, atomic JSON
publication, and destructive aliasing.

## Validation

```text
python -m py_compile \
  tools/audit/validate_wiki_tau_eff_public_binding.py \
  tests/test_validate_wiki_tau_eff_public_binding.py \
  tools/audit/render_wiki_tau_eff_public_binding_evidence.py
PYTHONPATH=. pytest -q tests/test_validate_wiki_tau_eff_public_binding.py
7 passed in 1.63s
```

Current exact excerpts: `FLAWED`, 24 findings. Corrected fixture: `VALIDATED`,
zero findings. JSON and SVG parsed. Python line-length maximum: 95.

## Files

- `tools/audit/validate_wiki_tau_eff_public_binding.py`
- `tests/test_validate_wiki_tau_eff_public_binding.py`
- `tools/audit/render_wiki_tau_eff_public_binding_evidence.py`
- `docs/validation/wiki_tau_eff_public_binding_audit.md`
- `docs/validation/wiki_tau_eff_public_binding_validation.json`
- `docs/validation/wiki_tau_eff_public_binding.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- this archive
- `chatgpt_todo/HANDOFF.md`

## Acceptance

`PARTIAL`: the validated gate and evidence are delivered. Root WIKI remediation
remains open. No detector or pile-up performance result is produced.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector exposes whole-file
replacement rather than byte-safe append/patch semantics for these shared
records, and a partial reconstruction could erase concurrent or append-only
provenance. This archive and latest handoff retain the append-equivalent record.

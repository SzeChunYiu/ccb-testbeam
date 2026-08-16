# Immutable session record — AUD-MC-002

## Identity

- UTC stamp: `2026-07-25T030239Z`
- Initial remote main: `a4b996ccbdfeea120e6deaead863f19d468d1091`
- Owner: scheduled scientific-review session
- Unit: issue #880 fail-closed weight handling and directional bias semantics

## Start-of-run inspection

Authenticated GitHub reads inspected repository metadata and permissions, current `main`,
recent commits, open pull requests, head status checks, issue #880 and its comment, merged PR
#897, `chatgpt_todo/ACTIVE_TASK.md`, `BACKLOG.md`, `HANDOFF.md`, the strict MC weight policy,
the issue #880 producer, and the retained result JSON.

No status checks were attached to the initial head. Open PRs were not modified. PR #868 was
not reopened or merged.

## Confirmed findings

- `load_mc` silently converts nonfinite event weights to unit weight.
- `wmean`, `wmedian`, `wfrac`, and `wcorr` can silently become unweighted estimators.
- `first_B_layer_mean_rel_bias_pct` is weighted-minus-unweighted divided by unweighted,
  although prose says it measures how far the legacy unweighted result was off.
- `deuteron_fraction_abs_bias_pp` is weighted minus unweighted, while the legacy-minus-
  weighted direction has the opposite sign.
- The retained JSON omits exact ROOT SHA-256, producer commit, generation command, and
  weight-validation policy/version.

## Independent calculations

From the tracked JSON values:

- weighted first-B mean change relative to unweighted: `-68.02243203341332%`;
- legacy first-B mean overstatement relative to weighted: `+212.7192164972955%`;
- weighted-minus-unweighted deuteron shift: `-40.585086858616876 pp`;
- legacy-minus-weighted deuteron shift: `+40.585086858616876 pp`;
- legacy deuteron overstatement relative to weighted: `+244.39966043037631%`.

These are deterministic transformations of retained summary numbers, not a ROOT rerun.

## Files delivered

- `tools/audit/audit_issue880_weight_semantics.py`
- `tests/test_audit_issue880_weight_semantics.py`
- `tools/audit/render_issue880_weight_semantics_evidence.py`
- `docs/validation/issue880_weight_semantics_audit.md`
- `docs/validation/issue880_weight_semantics_validation.json`
- `docs/validation/issue880_weight_semantics.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- this immutable archive
- latest `chatgpt_todo/HANDOFF.md`

## Validation

```text
python -m py_compile \
  tools/audit/audit_issue880_weight_semantics.py \
  tests/test_audit_issue880_weight_semantics.py \
  tools/audit/render_issue880_weight_semantics_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_issue880_weight_semantics.py

6 passed in 0.04s
```

JSON parsing passed, SVG XML parsing passed, and changed Python lines are at most 99
characters. Tests cover current-like fail-open behavior, direction-explicit acceptance,
arithmetic mutation, invalid UTF-8, atomic output, and alias protection.

## Acceptance and blockers

The audit implementation and evidence are validated. The retained issue #880 physics summary
remains `FLAWED` pending a producer correction and exact ROOT rerun. Required inputs are the
exact one-million-event ROOT bytes and an accepted first-primary event-weight contract.
Weighted uncertainty and data/MC closure remain unresolved.

`SESSION_LOG.md`, `BACKLOG.md`, and aggregate matrices were not replaced because the
connector exposes whole-file replacement rather than byte-safe append/patch semantics for
shared records. Replacing a partial or concurrently changing reconstruction could erase
unrelated provenance. This archive and the latest handoff preserve the append-equivalent
record.

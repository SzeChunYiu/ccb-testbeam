# Conflict record: `scripts/supervisor_deltaE_E.py`

Resolved per `audit/SOURCE_OF_TRUTH_POLICY.md`.

| Field | Value |
|---|---|
| Conflicting claims | Handoff `audit/KNOWN_CODE_DEFECTS.md` and `AI_SESSION_MASTER_PROMPT.md` both instruct repairing `scripts/supervisor_deltaE_E.py`. The file does **not exist** at the audited commit. |
| File / reference | `scripts/supervisor_deltaE_E.py` (referenced); repo tree at `d3b2beb` |
| Date / commit | Audited `d3b2beb217c7157693da45e3e8824489c7a8f036` (2026-07-20) |
| Evidence rank | (1) repo tree at the exact commit > (9) narrative instruction in the handoff prose |
| Selected value | The named file is **absent** at the audited commit; it existed historically (`git log --all` shows it under issue #618, e.g. commit `ca30589f`), so the handoff reference is **stale/superseded**. |
| Rationale | The tree at the audited commit is higher-ranked evidence than a prose instruction. `grep` shows the ΔE–E logic — and the `eventno`-only join defect the handoff describes — now lives distributed across fleet-generated `scripts/p*` / `scripts/s*` analysis files, not in a single `supervisor_deltaE_E.py`. |
| Test that would overturn | `git show d3b2beb:scripts/supervisor_deltaE_E.py` succeeding (file present at the audited commit), or `origin/main` moving to a commit that reintroduces the file. |

## Consequence (queued, not dropped)

The underlying defects the handoff attributes to this file are real and present
elsewhere. They are captured as closure task **CCB-DELTAE-FIX** (`READY`):

- event key must be `(file_id, run, event)`, not `eventno` alone
  (collision-prone across runs/files);
- Sample I / Sample II must be made explicit with inclusive/exclusive variants;
- `--stop-thresholds` / `--data-thresholds` must actually define the stored
  stopping distributions;
- stopping layer must not be "max layer with any deposit" (noise-sensitive);
- deterministic subsample seed; hexbin/2D density + conditional quantiles;
- emit event-level tables so plots reproduce independently.

Affected files (non-exhaustive, from `grep -l eventno scripts/*.py`):
`scripts/p07e_leading_edge_sample_ablation.py`,
`scripts/s05a_astack_external_control.py`,
`scripts/s16f_*_event_display_audit.py`, and others in the ΔE–E / Sample split
family. The fix requires the run/event/file keys present in the real data on
LUNARC, so it is validation-blocked, not code-blocked.

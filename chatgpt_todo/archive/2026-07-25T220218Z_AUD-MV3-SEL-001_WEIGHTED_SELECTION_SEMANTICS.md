# Immutable handoff — AUD-MV3-SEL-001

## Session identity

- **Session stamp:** 2026-07-25T220218Z
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `701116061eb3346a3ae2b31e2946ca450d6120e2`
- **Primary area:** merged MV3 selection-matched stopping-depth follow-up / `CL-021`
- **Policy:**
  `MV3_SELECTION_CLAIM_REQUIRES_WEIGHTED_SIGNED_CHARGE_AND_SAME_TARGET_VALIDATION`

## Repository state inspected

- PR #932 was merged as `701116061eb3346a3ae2b31e2946ca450d6120e2`.
- No open PR was returned at session start.
- PR #868 remained closed, unmerged, and non-mergeable; it was untouched.
- No status checks were attached to the initial commit.
- Exact reviewed Git blobs are recorded in
  `docs/validation/mv3_selection_claim_validation.json`.

## Confirmed defects

1. `scripts/studies/mv3_selection_matched.py` reads `PrimaryWeight`, silently
   substitutes `1.0` for missing/nonfinite weight, and never uses the resulting `w_evt` in
   profile counts, correlations, entry-energy summaries, or the advertised result.
2. The report says PrimaryWeight must not be used even though the repository's source-specific
   contract states it carries the generated-source cross-section factor and that unweighted
   truth distributions are not physical production distributions.
3. The producer uses `pdg_charge(int(p)) >= 1` instead of canonical `is_charged()`, excluding
   all negatively charged particles from trigger and deposition selections.
4. The advertised `16.602672795596263x` improvement changes both the MC selection and data
   target. Holding Sample-I data fixed gives `16.114635239581606x`.
5. The matched profile still has Pearson chi2/ndf `5590.089500522007`, B2 residual
   `7.735323559398211` percentage points, and total-variation distance
   `0.07735323559398212`; “gap gone” / “shape matches” is not authorized.
6. The summary omits input hashes, commit/command, weight sufficient statistics and ESS,
   uncertainty/covariance, and required gain/threshold/coincidence/weighting sensitivities.
7. The new verdict conflicts with canonical `CL-021`, which remains `FLAWED` under
   `BLK-MV3-LEGACY-001`.

## Work delivered

- `tools/audit/audit_mv3_selection_claim.py`
- `tests/test_audit_mv3_selection_claim.py`
- `tools/audit/render_mv3_selection_claim_evidence.py`
- `docs/validation/mv3_selection_claim_validation.json`
- `docs/validation/mv3_selection_claim.svg`
- `docs/validation/mv3_selection_claim_audit.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`

The exact current-like contract returns `FLAWED` with 16 findings. A corrected contract fixture
returns `VALIDATED` with zero findings.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv3_selection_claim.py \
  tests/test_audit_mv3_selection_claim.py \
  tools/audit/render_mv3_selection_claim_evidence.py

pytest -q tests/test_audit_mv3_selection_claim.py
7 passed in 0.07s
```

JSON parsing and SVG XML parsing passed. Changed Python lines are at most 99 characters.
Tests cover current-like failure, corrected acceptance, count/fraction mutation, duplicate
`CL-021`, invalid UTF-8, destructive output aliasing, and atomic JSON publication.

The runtime could not resolve `github.com` for a complete checkout. Exact GitHub blobs were
inspected through the authenticated connector; the executable audit was validated on a
byte-local fixture reproducing those observed contracts. No exact-repository local CLI run is
claimed.

## Direct-main commits before archive

- `b7ff8d887146cb1222eac318dc0afc0f4b943e61` — task claim
- `257e3eee09142f65de4e70aca0a9b1bfac76f668` — fail-closed audit gate
- `68390a96c4370b020fbeb44ba57076635ca85c30` — focused regressions
- `332031fc0f98f3694933ca8a01b7df60056df41b` — evidence renderer
- `1d561ba6b41a10d8eec37f175c32250f97f0b67e` — validation JSON
- `c94f4135a8ec6b25e79170198fdbc348297494c4` — visual evidence
- `f7d89238557ce91eb55c56f857af3522c658c544` — audit report
- `bb0ae8fa92e78fe4e1c80895c122287296264d17` — completed active task

GitHub contents writes advanced `main` directly and returned commit SHAs rather than
conventional terminal `git push` output. Remote history was re-read and confirmed this exact
sequence after the implementation/evidence writes.

## Acceptance and scientific boundary

- **Focused audit gate:** VALIDATED
- **Production selection-matched claim:** FLAWED pending weighted signed-charge rerun
- **Canonical CL-021:** remains FLAWED
- **Cumulative task:** PARTIAL

No ROOT file was reprocessed. No weighted stopping profile, detector/model correction,
calibration, PID result, or detector-performance result was produced. The committed historical
PNGs remain diagnostic only and must be regenerated together after producer remediation.

## Required next unit

1. fail closed on invalid/ambiguous/non-event-aligned weights and apply one PrimaryWeight per
   MC event;
2. use canonical signed-charge selection;
3. retain weighted primary and unweighted sensitivity results, `sum_w`, `sum_w2`, ESS, weight
   tails, and weighted profile covariance;
4. hold the data target fixed in every selection ablation;
5. preregister and run gain, threshold, coincidence-window, aggregation, and weighting scans;
6. regenerate all JSON/plots/reports from immutable inputs with full hashes and command;
7. synchronize the ledger and all public wording only after the exact-repository audit returns
   zero findings.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate matrices were
reviewed but not replaced. The connector offers whole-file replacement while complete shared
bytes are returned only in pages; reconstructing and replacing a partial or stale copy could
erase unrelated append-only or concurrent provenance. This immutable archive plus the latest
`HANDOFF.md` retain the complete append-equivalent record, but the mandatory aggregate
synchronization step remains unresolved.

# Latest Handoff — AUD-PID-001 Chapter 8 MV1 source synchronization

## Delivery identity

- **Session stamp:** `2026-07-25T131727Z`
- **Initial remote `main`:** `8cb0516e80f641d9f00d01d968ed0389ca48cac3`
- **Task-claim commit:** `bcdd9bb82d118ccfa8562956a61563ca6d82873b`
- **Validated core commit:** `2f653429c2b7ead1d35752a23f3bb908506dd23d`
- **Destination:** direct fast-forward commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport
- **Acceptance:** focused Chapter 8 documentation and fail-closed source binding
  COMPLETE; scientific `CL-017`/`CL-018` claims remain `GATED`
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T131727Z_AUD-PID-001_CHAPTER8_SOURCE_SYNC.md`

## What was corrected

The former Chapter 8 contradicted the tracked producer and summary. It labelled
traditional-cut purity as AUC, described truth-MC row-index output as beam-data
leave-one-run-out, promoted an HGB point estimate as an irreducible performance
ceiling, published untracked stopping-depth/combined-rule/systematic claims, and
interpreted MV2 quantities without a bound momentum-unit conversion.

The replacement chapter now reports only the tracked fixed outputs:

- `400369` charged B-arm tracks;
- `150130` protons and `146842` deuterons;
- `296972` proton/deuteron tracks;
- traditional threshold `13.287866011130776 MeV`, purity
  `0.8909863556160177`, efficiency `0.900961577750235`;
- logistic AUC `0.9628868703282414`, purity `0.9488978818667125`;
- HGB AUC `0.9859658513538254`, purity `0.9644090769970706`.

It binds the result to exact-width `CL-017` and `CL-018`, records
`truth_type=mc_truth_only`, `status=GATED`, blocker `BLK-MV1-001`, and states
that no beam-data PID performance metric is established.

## Source traceability

- former chapter blob: `5ad66ea8e7bfb22ca0cf4c1baf1e0b2cb759e527`
- claim-ledger blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`
- producer blob: `4f3632e59ede59bcf27e053265908ddca77b4386`
- summary blob: `9e49af48025b9699d957e932d06901dd47a45321`
- source commit: `3539ae3aad222284bd7be100802a2651c0e064de`

## Files delivered in the core commit

- `docs/academic_chapters/08_particle_id.md`
- `tools/audit/validate_chapter8_mv1_claims.py`
- `tests/test_validate_chapter8_mv1_claims.py`
- `tools/audit/render_chapter8_mv1_claims_evidence.py`
- `docs/validation/chapter8_mv1_claims_audit.md`
- `docs/validation/chapter8_mv1_claims_validation.json`
- `docs/validation/chapter8_mv1_claims.svg`

## Validation

```text
python -m py_compile \
  tools/audit/validate_chapter8_mv1_claims.py \
  tests/test_validate_chapter8_mv1_claims.py \
  tools/audit/render_chapter8_mv1_claims_evidence.py

PYTHONPATH=. pytest -q tests/test_validate_chapter8_mv1_claims.py

7 passed in 0.04s
```

The accepted fixture returned `VALIDATED` with zero issues. The stale chapter
fixture returned `FLAWED` with eight issues. Mutated ledger status, summary AUC,
and row-parity source contract failed. Invalid UTF-8 and output/input aliasing
returned controlled status 2. JSON and SVG parsing passed; changed Python lines
were at most 100 characters.

## Scientific boundary

No ROOT input was opened, no classifier was retrained, no beam-data label was
constructed, and no new uncertainty, range-energy closure, calibration,
stopping-depth result, or detector-performance claim was produced. A larger HGB
point AUC alone does not authorize the model.

## Required next work

1. Recover or regenerate immutable ROOT provenance and execution environment.
2. Retain event/run identifiers and use event/run-group-disjoint validation.
3. Freeze seeds and model versions; run repeated-split and event/run bootstrap.
4. Compare transparent physics baselines, calibrated flexible models, and
   failure slices with uncertainty and multiplicity controls.
5. Validate data/MC feature transfer before publishing beam-data PID metrics.
6. Establish exact MV2 momentum branch units before range-energy interpretation.

PR #868 remains closed, unmerged, non-mergeable, and untouched. Repository-wide
pytest, ruff, ROOT processing, classifier rerun, and GitHub Actions were not run;
no broad CI or scientific-performance success is claimed.

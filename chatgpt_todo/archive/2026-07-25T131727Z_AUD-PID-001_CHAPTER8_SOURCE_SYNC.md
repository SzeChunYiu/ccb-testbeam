# AUD-PID-001 — Chapter 8 MV1 source synchronization

## Session identity

- UTC stamp: `2026-07-25T131727Z`
- initial remote `main`: `8cb0516e80f641d9f00d01d968ed0389ca48cac3`
- task-claim commit: `bcdd9bb82d118ccfa8562956a61563ca6d82873b`
- validated core commit: `2f653429c2b7ead1d35752a23f3bb908506dd23d`
- destination: direct fast-forward commits to `main`; no force-push, branch,
  history rewrite, or PR transport
- PR #868: closed, unmerged, non-mergeable, and untouched

## Reviewed evidence

- former Chapter 8 blob: `5ad66ea8e7bfb22ca0cf4c1baf1e0b2cb759e527`
- claim-ledger blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`
- MV1/MV2 producer blob: `4f3632e59ede59bcf27e053265908ddca77b4386`
- MV1/MV2 summary blob: `9e49af48025b9699d957e932d06901dd47a45321`
- source commit recorded by `CL-017`/`CL-018`:
  `3539ae3aad222284bd7be100802a2651c0e064de`
- canonical rows: exact 43-column `CL-017` and `CL-018`, both
  `truth_type=mc_truth_only`, `status=GATED`, `n_mc=296972`, blocker
  `BLK-MV1-001`

## Confirmed source values

- charged B-arm tracks: `400369`
- proton tracks: `150130`
- deuteron tracks: `146842`
- proton/deuteron classification tracks: `296972`
- traditional threshold: `13.287866011130776 MeV`
- traditional purity: `0.8909863556160177`
- traditional efficiency: `0.900961577750235`
- logistic-regression AUC: `0.9628868703282414`
- logistic-regression purity at nominal 90% efficiency:
  `0.9488978818667125`
- HGB AUC: `0.9859658513538254`
- HGB purity at nominal 90% efficiency: `0.9644090769970706`

## Confirmed defects and corrections

1. The former chapter labelled rounded cut purity `0.891` as AUC. The producer
   computes no traditional-cut ROC AUC.
2. Truth-labelled Monte Carlo logistic output was described as weak-label
   beam-data leave-one-run-out validation. The producer uses exact PDG truth and
   an even/odd row-index split.
3. HGB point estimates were promoted as a truth ceiling, maximum achievable
   separation, and irreducible detector limit. The producer retains no event ID,
   so correlated tracks can cross the split; it records no CI, repeated split,
   systematic study, or explicit HGB seed.
4. Sample-I/Sample-II stopping-depth tables, a combined decision-tree operating
   point, and a plus/minus 4% PID systematic were not present in the tracked
   summary and were removed.
5. MV2 `mean_ekin_MeV` values are of order `1e-4 MeV`; the producer does not bind
   a momentum-branch unit conversion. Range-energy interpretation is blocked.
6. The former theoretical narrative mixed inconsistent thickness, transfer, and
   range statements. The replacement retains only source-relevant qualitative
   motivation and requires authoritative unit-checked closure before new theory
   numbers are published.

## Files delivered

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

Additional checks:

- accepted fixture: `VALIDATED`, zero issues;
- stale chapter fixture: `FLAWED`, eight issues;
- ledger-status mutation: rejected;
- summary-AUC mutation: rejected;
- missing row-parity source contract: rejected;
- invalid UTF-8: controlled status 2;
- destructive output alias: controlled status 2;
- validation JSON parse: PASS;
- SVG XML parse: PASS;
- maximum changed Python line lengths: 100, 99, and 98 characters.

## Scientific boundary and next work

This is documentation and source-contract validation, not a classifier rerun or
beam-data measurement. No ROOT file was opened, no model was retrained, and no
new AUC, purity, efficiency, calibration, uncertainty, stopping-depth closure,
or detector-performance result was generated.

Before production use, rerun from content-addressed ROOT bytes with event and run
identifiers, event/run-group-disjoint validation, explicit software versions and
seeds, event/run-aware uncertainty, calibration and failure-slice diagnostics,
and matched data/MC transfer closure. Resolve MV2 momentum units separately.

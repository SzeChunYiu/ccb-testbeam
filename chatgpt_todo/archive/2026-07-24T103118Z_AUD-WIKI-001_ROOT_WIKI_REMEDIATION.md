# AUD-WIKI-001 — complete root-WIKI canonical-claim remediation

## Session identity

- UTC stamp: `2026-07-24T103118Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `c254e767bbc225d98f9c839d50251c511ca69a98`
- Owner: scheduled scientific-review session
- Destination: direct sequential commits to `main`
- Acceptance: root-front-door remediation `VALIDATED`; repository-wide WIKI audit remains `PARTIAL`

## Start-of-run review

Authenticated GitHub reads inspected repository permissions, latest main history, PR #868, `WIKI.md`, `docs/claim_ledger.csv`, the WIKI validator and tests, latest `chatgpt_todo/` task/handoff records, and current status/workflow attachments. PR #868 remained closed, unmerged, and non-mergeable and was not modified.

A direct clone was retried and failed because the runtime could not resolve `github.com`. Repository reads and direct-main writes used the authenticated GitHub connector. No status checks or workflow runs were attached to the implementation/test head.

## Problem corrected

The exact pre-change root WIKI blob `04781e1107075e1e57c08e6dd4e1f48d9a131763` contradicted exact-width canonical claim rows:

1. `CL-010` is `BLOCKED` with no accepted numerical Rmax, but the WIKI published `3.044–3.05 MHz` as `VALIDATED`.
2. `CL-012` is `SUPERSEDED`, but the WIKI presented approximately 3.05 MHz as the new canonical value and repeated the unresolved 0.38-based derivation.
3. `CL-015` is `GATED` because the P04p coverage interval crosses the eligibility threshold, but the WIKI called duplicate readout an ML win or confirmed-win domain.
4. `CL-016` is `GATED`; external held-out P07e closure is worse than raw and producer bytes are unbound, but the WIKI called saturation recovery an ML win or promising domain.
5. The MV5 validation matrix still classified numerical Rmax as `VALIDATED`.

## Correction delivered

The complete `WIKI.md` was rewritten without removing unrelated sections. The corrected WIKI:

- withholds numerical Rmax pending `S-STAT-003` and marks it `BLOCKED`;
- retains `3.0448717948717947 MHz` only as explicitly superseded history;
- preserves `tau_eff = 124.79 ns` as `VALIDATED` with the canonical data-plus-MC truth type;
- separates duplicate-readout and saturation-recovery claims;
- marks both production decisions `GATED` with distinct limitations;
- states exactly that no production duplicate-readout model or saturation correction is authorized;
- removes unsupported combined/domain-level ML-win wording;
- changes MV5 numerical Rmax to `BLOCKED`;
- propagates `S-STAT-003`, `BLK-P04P-001`, and `BLK-P07E-001` into open issues.

Added:

- `tests/test_wiki_claim_front_door_current.py`;
- `docs/validation/wiki_front_door_remediation_audit.md`;
- `docs/validation/wiki_front_door_remediation_validation.json`;
- `docs/validation/wiki_front_door_remediation.svg`.

Updated:

- `WIKI.md`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this immutable archive record;
- latest handoff after this archive.

## Exact provenance

- Corrected WIKI bytes: `21368`
- Corrected WIKI SHA-256: `baaa9dbd3585870c7d9c0807493e9afce81f9767f3be68d581502d62496c59d4`
- Corrected WIKI Git blob: `9d8110893adeae482b2439c4187b53f94174a55e`
- Claim-ledger bytes: `12077`
- Claim-ledger SHA-256: `c0e283e6d43a1013a9565f2697c4f99f7b47d639245b9926a8ddc83786602e19`
- Claim-ledger Git blob: `853d955f449268ec614ac61f33f243d30cf473e0`
- Required records: `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, `CL-016`
- Required width: exactly `43` columns per record
- Validator: `validate_wiki_claim_front_door.py` v1.2.0
- Policy: `WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`

## Validation

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_wiki_claim_front_door_current.py

python -m pytest tests/test_wiki_claim_front_door_current.py -q

2 passed in 0.02s
```

The direct validator result was `VALIDATED` with zero issues and six required widths of 43. A prior run of the same regression returned `2 passed in 0.05s`; both results are retained truthfully.

The stale-Rmax mutation test returned `FLAWED` and contained:

- `WITHHELD_RMAX_VALUE_PUBLISHED`;
- `STATUS_LEDGER_MISMATCH`;
- `VALUE_PRESENT_WHEN_LEDGER_WITHHOLDS`.

JSON parsing and SVG XML parsing passed. A focused reconstructed-tree execution of the repository broken-link checker covered all 16 internal file targets referenced by the corrected WIKI and returned `All internal links valid`. The corrected WIKI introduces no new internal file target. A complete repository-wide scan was not run because a checkout was unavailable.

## Direct-main commits before archive

1. `eb690f38d6032257876678c3d5d046b764230b39` — `fix(docs): align root WIKI with canonical gated claims`
2. `c2b4ff39a31deb33f807208c18be0341c16f7c4b` — `test(audit): validate exact current root WIKI claims`
3. `e724845987bdf2f6f8072821aab1b147fab0a59a` — `docs(validation): record root WIKI remediation audit`
4. `dd90701b22499619976a23b727a88e5186f727ab` — `docs(validation): add root WIKI remediation record`
5. `055e0019a5057307629b575e20ff09ccb34be4da` — `docs(validation): visualize root WIKI remediation`
6. `e426af16ab8bb8592a38bec5f6fdb304dee51acc` — `docs(audit): track validated root WIKI remediation`

Each write returned a successful direct-main commit result. No branch, pull request, force-push, or history rewrite was used.

## Scientific boundary

No detector data, simulation, fit, Rmax calculation, uncertainty interval, model training, calibration, or detector-performance result was generated. This unit does not resolve `S-STAT-003`, select a P04p production model, authorize P07e saturation recovery, repair the remaining malformed ledger rows, or establish that every other WIKI statement is evidence-complete.

Full repository pytest, ruff, full broken-link checking, ROOT processing, model reruns, and GitHub Actions were not run.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file replacement rather than a byte-safe append operation and a complete current snapshot was not safely available. Replacing an append-only provenance file from partial reads would risk deleting prior history. This immutable archive and the latest handoff retain the complete run without fabricating an append.

## Next action

Continue `AUD-WIKI-001` by mapping and reviewing remaining material root-WIKI claims, while separately repairing the 19 malformed claim-ledger rows. Do not restore a numerical Rmax or authorize P04p/P07e production use until their named blockers are resolved.

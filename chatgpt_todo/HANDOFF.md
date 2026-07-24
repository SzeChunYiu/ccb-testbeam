# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T103118Z`
- **Task:** `AUD-WIKI-001`
- **Unit:** complete root-WIKI canonical-claim remediation
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote `main`:** `c254e767bbc225d98f9c839d50251c511ca69a98`
- **Validated remote-main delivery head before this handoff:** `03c4e4bf5bfa91bda275c89db83d5c8d25217805`
- **Destination:** direct sequential commits to `main`; no task branch, pull request, force-push, or history rewrite
- **Acceptance:** complete root-front-door remediation, focused integration regression, exact WIKI provenance, Markdown/JSON/SVG evidence, and immutable archive are `VALIDATED`; repository-wide WIKI coverage remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected repository permissions, latest main history, current commit status/workflow attachments, PR #868, `WIKI.md`, `docs/claim_ledger.csv`, the WIKI validator and tests, and mandatory `chatgpt_todo/` coordination records. The run based its writes on the latest observed remote head `c254e767bbc225d98f9c839d50251c511ca69a98`.

PR #868 remains closed, unmerged, and non-mergeable and was not modified. No status checks or workflow runs were attached to the implementation/test head, so no GitHub Actions success is inferred.

A direct clone was retried and failed because the runtime could not resolve `github.com`. Repository reads and direct-main writes therefore used the authenticated GitHub connector.

## Public claim conflicts corrected

The pre-change root WIKI blob `04781e1107075e1e57c08e6dd4e1f48d9a131763` contradicted exact-width canonical ledger records:

1. `CL-010` is `BLOCKED`, has no accepted numerical Rmax, and is blocked by `S-STAT-003`; the WIKI published `3.044–3.05 MHz` as `VALIDATED`.
2. `CL-012` is `SUPERSEDED`; the WIKI presented approximately 3.05 MHz as a new canonical value and repeated the unresolved 0.38-based derivation.
3. `CL-015` is `GATED` because the P04p coverage interval crosses the model-eligibility threshold; the WIKI called duplicate readout an ML win or confirmed-win domain.
4. `CL-016` is `GATED`; external P07e held-out duplicate closure is worse than raw and producer bytes are unbound; the WIKI called saturation recovery an ML win or promising domain.
5. The MV5 matrix labelled numerical Rmax `VALIDATED` despite the canonical blocker.

## Correction delivered

The complete root `WIKI.md` was rewritten while preserving unrelated sections. It now:

- withholds numerical Rmax pending `S-STAT-003` and marks it `BLOCKED`;
- retains `3.0448717948717947 MHz` only as explicitly `SUPERSEDED` history;
- preserves `tau_eff = 124.79 ns` as `VALIDATED` with the canonical data-plus-MC truth type;
- separates the P04p duplicate-readout and P07e saturation-recovery statements;
- marks both production decisions `GATED` with their distinct evidence limitations;
- states: `No production duplicate-readout or saturation correction is authorized.`;
- removes combined/domain-level ML-win language;
- marks MV5 numerical Rmax `BLOCKED`;
- propagates `S-STAT-003`, `BLK-P04P-001`, and `BLK-P07E-001` into open issues.

Added:

- `tests/test_wiki_claim_front_door_current.py`;
- `docs/validation/wiki_front_door_remediation_audit.md`;
- `docs/validation/wiki_front_door_remediation_validation.json`;
- `docs/validation/wiki_front_door_remediation.svg`;
- `chatgpt_todo/archive/2026-07-24T103118Z_AUD-WIKI-001_ROOT_WIKI_REMEDIATION.md`.

Updated:

- `WIKI.md`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

## Exact provenance and quantitative result

- Corrected WIKI bytes: `21368`
- Corrected WIKI SHA-256: `baaa9dbd3585870c7d9c0807493e9afce81f9767f3be68d581502d62496c59d4`
- Corrected WIKI Git blob: `9d8110893adeae482b2439c4187b53f94174a55e`
- Claim-ledger bytes: `12077`
- Claim-ledger SHA-256: `c0e283e6d43a1013a9565f2697c4f99f7b47d639245b9926a8ddc83786602e19`
- Claim-ledger Git blob: `853d955f449268ec614ac61f33f243d30cf473e0`
- Required canonical records: `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, `CL-016`
- Required width: exactly `43` columns for each record
- Validator: `validate_wiki_claim_front_door.py` v1.2.0
- Policy: `WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`
- Corrected-state validator result: `VALIDATED`, zero issues

No scientific number was newly calculated. The numerical evidence in this run is documentation/provenance validation only.

## Validation performed

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_wiki_claim_front_door_current.py

python -m pytest tests/test_wiki_claim_front_door_current.py -q

2 passed in 0.02s
```

A prior identical integration run returned `2 passed in 0.05s`; both results are retained without selecting a preferred runtime.

Direct validator output:

```text
status: VALIDATED
issues: 0
wiki bytes: 21368
wiki sha256: baaa9dbd3585870c7d9c0807493e9afce81f9767f3be68d581502d62496c59d4
required claim widths: 43, 43, 43, 43, 43, 43
```

The stale-Rmax mutation regression returned `FLAWED` and included:

- `WITHHELD_RMAX_VALUE_PUBLISHED`;
- `STATUS_LEDGER_MISMATCH`;
- `VALUE_PRESENT_WHEN_LEDGER_WITHHOLDS`.

Additional checks:

- local corrected WIKI Git blob matched the connector-returned committed blob exactly;
- committed integration-test Git blob matched the locally validated file;
- validation JSON parsed;
- SVG parsed as XML;
- a focused reconstructed-tree run of the repository broken-link checker covered all 16 internal file targets referenced by the WIKI and returned `All internal links valid`;
- the corrected WIKI introduces no new internal file target.

A full repository-wide link scan was not run because the checkout was unavailable. Full repository pytest, ruff, ROOT processing, model reruns, and GitHub Actions were also not run.

## Direct-to-main commit and push sequence

Each authenticated connector write returned a successful direct-main commit result:

1. `eb690f38d6032257876678c3d5d046b764230b39` — `fix(docs): align root WIKI with canonical gated claims`
2. `c2b4ff39a31deb33f807208c18be0341c16f7c4b` — `test(audit): validate exact current root WIKI claims`
3. `e724845987bdf2f6f8072821aab1b147fab0a59a` — `docs(validation): record root WIKI remediation audit`
4. `dd90701b22499619976a23b727a88e5186f727ab` — `docs(validation): add root WIKI remediation record`
5. `055e0019a5057307629b575e20ff09ccb34be4da` — `docs(validation): visualize root WIKI remediation`
6. `e426af16ab8bb8592a38bec5f6fdb304dee51acc` — `docs(audit): track validated root WIKI remediation`
7. `03c4e4bf5bfa91bda275c89db83d5c8d25217805` — `docs(audit): archive validated root WIKI remediation`

The connector does not return textual `git push` stdout; each successful contents-API write advanced remote `main` and returned the listed commit SHA. A post-handoff history read must confirm the handoff commit as remote head.

## Scientific boundary and unresolved risk

This documentation-governance unit does **not**:

- determine an accepted Rmax or resolve `S-STAT-003`;
- select a P04p production model or resolve `BLK-P04P-001`;
- authorize P07e saturation recovery or resolve `BLK-P07E-001`;
- repair the remaining 19 malformed claim-ledger rows;
- establish evidence completeness for every other WIKI statement;
- regenerate detector data, simulation, fits, uncertainties, calibration, or detector-performance results.

`AUD-WIKI-001` remains `PARTIAL` at repository-wide scope. The complete root-front-door remediation unit is `VALIDATED` and complete.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file replacement rather than a byte-safe append operation and a complete current byte snapshot was not safely available. Replacing the append-only file from partial reads could destroy prior provenance. The complete session record is retained in the immutable archive and this handoff.

## Next validated unit

Continue `AUD-WIKI-001` by mapping and reviewing remaining material WIKI claims. In parallel, repair the 19 malformed `docs/claim_ledger.csv` rows under `AUD-CLAIM-001`. Do not restore numerical Rmax or authorize P04p/P07e production use until the named blockers are resolved.

# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-24T041806Z`
- Completed task: `AUD-WIKI-002`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `c9ff3196a1c5a4441119e6b19b592db1a8b5763b`
- WIKI remediation implementation/evidence head: `ef5a2167934f414e7cf064c210ddd22bb401ce20`
- Immutable WIKI archive commit: `0024b78178827eae25a97c9ca17f02fad2610802`
- Remote `main` immediately before this handoff: `02102fae6897170c3b37aa1485c67ba0819e1101`
- Destination: direct commits to `main`; no task branch, force-push, or history rewrite
- Acceptance: `AUD-WIKI-002 = COMPLETE`
- Concurrent state preserved: `AUD-LEDGER-001` is active and has added a fail-closed schema validator/evidence after this run registered the remaining ledger defect. Its work was not overwritten or claimed as this session's work.

## Start-of-run review

Reviewed current `main`, recent history and concurrent activity, repository permissions,
PR #868, WIKI and claim-ledger content, the prior front-door validator/tests,
internal-link checking, and all mandatory `chatgpt_todo/` records.

PR #868 remains closed, unmerged, and non-mergeable. It was not modified.

A direct checkout was attempted and failed with:

```text
Could not resolve host: github.com
```

Authenticated GitHub connector reads and direct-main writes were used. Successful
write responses and subsequent remote reads are the push evidence; no local `git
push` transcript exists.

## Confirmed defects

### Public WIKI

1. `MV4 raw timing pull`, `MC raw timing pull`, and `MV4 raw` used `PASS`, although
   `PASS` is absent from the published legend and canonical `CL-007` is `VALIDATED`.
2. The canonical effective-live-time row used `data_only`; canonical `CL-011` is
   `data_mc_self_consistent`.
3. The WIKI stated `Every number has uncertainty.` while the canonical ledger still
   contains explicit `CI_MISSING_BLOCKING` entries.

### Exact claim-ledger schema

Exact-file validation exposed a deeper issue:

- canonical header width: `43` columns;
- original data rows: `26`;
- original exact-width rows: `0`;
- original row widths: `35` to `40` columns.

`CL-007` and `CL-011` placed their intended late values five fields early. Standard
CSV parsing therefore did not expose their intended truth type/status/source fields.

### Validator behavior

Validator v1.0.0 attempted a truth-type check on every matching effective-live-time
row, including a three-column summary row that has no truth-type column. This caused
a false missing-truth issue after correcting the canonical row.

## Remediation delivered

### `WIKI.md`

Exactly five statements changed:

- the blanket uncertainty-completeness sentence now points to the canonical ledger
  and explicitly states that `CI_MISSING_BLOCKING` entries remain incomplete;
- effective-live-time truth type is now `data + MC self-consistent`;
- all three raw-MV4 labels are now `VALIDATED`.

No scientific number, uncertainty value, formula, event selection, plot, or
interpretation was recalculated.

### `docs/claim_ledger.csv`

Only the two bound rows were reconstructed to the 43-column schema, preserving all
non-empty values:

- `CL-007`: `truth_type=digitized_mc`, `status=VALIDATED`;
- `CL-011`: `truth_type=data_mc_self_consistent`, `status=VALIDATED`.

The remaining 24 malformed rows were not guessed or silently padded. They remain
blocked under `AUD-LEDGER-001` / `BLK-LEDGER-001`.

### Validator and tests

`tools/audit/validate_wiki_claim_front_door.py` is now v1.1.0:

- status checks still apply to every bound summary/canonical row;
- truth type is checked only on matching rows with six or more table fields;
- at least one truth-type-bearing row is required for a truth binding.

The focused fixture now includes a duplicate three-column effective-live-time summary
row to prevent recurrence.

## Exact provenance

### Original files

- `WIKI.md`
  - Git blob: `c27a1e555145cb248e253f17a6f6d1cfe64542a8`
  - bytes: `19159`
  - SHA-256:
    `62385f61aa5742b9a522efe1bd8a2ab576638a0cfc1cfdf28ad59f53c78f5181`
- original claim ledger Git blob:
  `6f4d4023814b42a566826912bcef7df9903c41e7`

### Corrected files

- `WIKI.md`
  - Git blob: `04781e1107075e1e57c08e6dd4e1f48d9a131763`
  - bytes: `19279`
  - SHA-256:
    `c739c0791a47ae6f9dadddd790b223e1cf728d0db0945500d6d7f851df885620`
- `docs/claim_ledger.csv`
  - Git blob: `0c7ea56d00ed44bd976e4ba8e05a84cb4c6eb63e`
  - bytes: `8971`
  - SHA-256:
    `3ef63ee3836ce67c8b9f4538f754737cdcf53bc67d9a746210a0ea9e81e41d2d`
- validator
  - Git blob: `99d2f579c98563969df26dbf1f946d8454c8ba00`
  - SHA-256:
    `3d82e6e57f97b9396392dc83423edee559f077c71acf5d03712a2656ded80912`
- test
  - Git blob: `068333d2db2873044f0599e9ab3c884dfb870ea5`
  - SHA-256:
    `ca43f22839ed80d80365ff6d5b3f26d186130f0c6374eaea2a98de6c8707c9d3`

## Validation

Executed on exact local reconstructions:

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_validate_wiki_claim_front_door.py

python -m pytest tests/test_validate_wiki_claim_front_door.py -q

5 passed in 0.03s

python tools/audit/validate_wiki_claim_front_door.py \
  WIKI.md docs/claim_ledger.csv \
  --output docs/validation/wiki_claim_front_door_remediation_validation.json
```

Exact corrected-file result:

- process status: `0`;
- status: `VALIDATED`;
- issues: `0`;
- bindings checked: `4`;
- legend statuses: `8`.

Focused link validation:

```text
python scripts/broken_link_checker.py

✓ All internal links valid.
```

The link check used the exact corrected WIKI and a local mirror of all 16 unique
internal targets whose existence was verified on GitHub. It was not a full scan of
every repository Markdown file.

JSON parsing and SVG XML parsing also passed.

Not run:

- full repository pytest;
- ruff;
- ROOT/data processing;
- simulation;
- GitHub Actions.

No broad CI success is claimed. No status checks were attached to the WIKI archive
commit.

## Evidence added

- `docs/validation/wiki_claim_front_door_remediation_audit.md`
- `docs/validation/wiki_claim_front_door_remediation_validation.json`
- `docs/validation/wiki_claim_front_door_remediation.svg`
- `chatgpt_todo/archive/2026-07-24T041806Z_AUD-WIKI-002_FRONT_DOOR_REMEDIATION.md`

The SVG explicitly labels itself synthetic documentation/provenance evidence, not
detector data, and shows the remaining 24-row ledger limitation.

## Direct-to-main WIKI commit sequence

- `e2f7da44d437459db9cb56de2e1944102039f2d0` — `docs(wiki): align front-door claims with ledger`
- `0534463eaab3b6d794135d6782b976fd73d461b4` — `fix(docs): align bound claim-ledger rows`
- `210a33c4ff39ef1ee87a246a9a364f1d9d8f8a5b` — `fix(audit): handle WIKI summary rows in truth checks`
- `787c5e7e45401aea11e17fcd7abc0f176863b25b` — `test(audit): cover duplicate WIKI summary rows`
- `acb1789f4694840c12e1c6b4819110f485a24266` — remediation audit
- `a3f4f39679221c5e65578e1669f6cbb86fec3984` — validation JSON
- `eee766e554ac8520b3c69212effd853063a34afe` — visual evidence
- `ddcad3a63b007861f50dd7b33c35301251a1a845` — active-task completion
- `6a0268b46cc7c848096019ea466b73901df1605b` — backlog completion and ledger-task registration
- `f303c938804f1a28942298e714a261c940d365d5` — master-index update
- `5916896ed187dc383fd749f5963fa3ca80b2e014` — claim-evidence update
- `e1039b75af5c5d6dff3863b4fef737e85d864d78` — ledger blocker registration
- `9cd287117092b720e72cb01143f5004b056e5772` — code-result mapping
- `3f7a9d23b43d5e421c82949c59aa2b9f9fb6fd3e` — visualization mapping
- `ef5a2167934f414e7cf064c210ddd22bb401ce20` — study-ledger update
- `0024b78178827eae25a97c9ca17f02fad2610802` — immutable archive

Every listed commit is present in the remote `main` history. Concurrent
`AUD-LEDGER-001` commits based on the advanced main were preserved.

## Coordination state

- `AUD-WIKI-002`: `COMPLETE`
- `IDX-WIKI-002`: `COMPLETE`
- `CL-WIKI-001`: `COMPLETE`
- `CRM-WIKI-001`: `COMPLETE`
- `VIS-WIKI-001`: `COMPLETE`
- `ST-WIKI-001`: `COMPLETE`
- `AUD-LEDGER-001`: active follow-on
- `BLK-LEDGER-001`: open

`ACTIVE_TASK.md` now belongs to the concurrent `AUD-LEDGER-001` session and was not
overwritten during final reconciliation.

`SESSION_LOG.md` remains unchanged in this WIKI session because it is append-only,
the connector exposes whole-file replacement rather than an append primitive, and a
concurrent session began updating the same coordination system. Replacing 282 lines
while `main` was advancing would create an avoidable lost-update/provenance risk.
The complete WIKI session record is preserved in the immutable archive and this
handoff. This is an explicit coordination limitation, not a claim that the mandatory
append occurred.

## Scientific boundary and next work

This session did not recalculate timing pulls, effective live-time, pile-up rate,
confidence intervals, data, simulation, calibration, or detector performance.

The WIKI front-door unit is complete. Repository-wide WIKI verification remains open
under `AUD-WIKI-001`.

The follow-on claim-ledger task must reconstruct 24 remaining width-mismatched rows
from source-backed semantics and require 26/26 exact 43-column rows before late fields
are interpreted. No missing values or field placement may be guessed.

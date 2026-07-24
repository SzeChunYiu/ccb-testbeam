# AUD-WIKI-002 — WIKI Front-Door Remediation

## Session identity

- UTC session stamp: `2026-07-24T041806Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `c9ff3196a1c5a4441119e6b19b592db1a8b5763b`
- Direct destination: `main`
- Task acceptance: `COMPLETE`
- Concurrent follow-on preserved: `AUD-LEDGER-001` became active after this run registered the remaining claim-ledger schema defect; its commits were not reverted or overwritten.

## Start-of-run review

The run inspected current `main`, recent history, repository metadata and permissions,
PR #868, WIKI/claim files, the prior WIKI audit validator and tests, internal-link
checking, and all mandatory `chatgpt_todo/` records. PR #868 remained closed,
unmerged, and non-mergeable and was not modified.

A direct checkout remained unavailable because the runtime could not resolve
`github.com`. Authenticated GitHub connector reads and direct-main writes were used.
No force-push, history rewrite, branch transport, unrelated rollback, or destructive
data edit occurred.

## Exact files reviewed

- `WIKI.md`
  - original Git blob: `c27a1e555145cb248e253f17a6f6d1cfe64542a8`
  - original bytes: `19159`
  - original SHA-256:
    `62385f61aa5742b9a522efe1bd8a2ab576638a0cfc1cfdf28ad59f53c78f5181`
- `docs/claim_ledger.csv`
  - original Git blob: `6f4d4023814b42a566826912bcef7df9903c41e7`
- `tools/audit/validate_wiki_claim_front_door.py`
  - original Git blob: `53346a2fea2f91e21e8846cbaefde67db1020eca`
- `tests/test_validate_wiki_claim_front_door.py`
  - original Git blob: `d48efee195fcfbdd04650bf63dce64c806a06ef0`
- `scripts/broken_link_checker.py`
- the 16 unique internal targets linked from `WIKI.md`, each verified to exist on GitHub.

## Confirmed defects

1. Three public raw-MV4 timing rows used `PASS`, a status absent from the WIKI
   legend and inconsistent with canonical claim `CL-007 = VALIDATED`.
2. The canonical effective-live-time row used `data_only`, inconsistent with
   canonical `CL-011 = data_mc_self_consistent`.
3. The front matter stated `Every number has uncertainty.` despite explicit
   `CI_MISSING_BLOCKING` ledger entries.
4. Exact-file execution exposed a deeper schema defect: the claim-ledger header has
   43 columns, while all 26 original data rows had only 35--40. `CL-007` and
   `CL-011` placed their intended late fields five columns early.
5. Validator v1.0.0 tried to read a truth type from every matching tau row,
   including the three-column summary row that has no truth-type field.

## Remediation delivered

### WIKI

Exactly five public statements were changed:

- the blanket uncertainty statement now points to the canonical ledger and says
  `CI_MISSING_BLOCKING` entries remain incomplete;
- the effective-live-time truth type is `data + MC self-consistent`;
- all three raw-MV4 status labels are `VALIDATED`.

No numerical value, uncertainty value, formula, selection, or plot was changed.

### Claim ledger

`CL-007` and `CL-011` were reconstructed to exactly 43 fields while preserving their
non-empty values. Their intended mappings now parse as:

- `CL-007`: `truth_type=digitized_mc`, `status=VALIDATED`;
- `CL-011`: `truth_type=data_mc_self_consistent`, `status=VALIDATED`.

The remaining 24 rows were not guessed or silently padded. They remain blocked under
`AUD-LEDGER-001` / `BLK-LEDGER-001`.

### Validator and regression

`validate_wiki_claim_front_door.py` is now v1.1.0. A truth-type binding is checked
only on matching rows with a truth-type-bearing table shape, and at least one such
row is required. Short summary rows remain status-checked but no longer generate a
false missing-truth finding.

## Validation

Commands executed on exact local reconstructions:

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
- validator status: `VALIDATED`;
- issue count: `0`;
- bindings checked: `4`;
- legend statuses: `8`.

Focused internal-link check:

```text
python scripts/broken_link_checker.py

✓ All internal links valid.
```

The check used the exact corrected WIKI and a local mirror of all 16 unique internal
targets whose existence was verified on GitHub. It is not claimed as a repository-
wide scan of every Markdown file.

JSON parsing, SVG XML parsing, and focused changed-file checks also passed.

## Corrected-file provenance

- `WIKI.md`
  - bytes: `19279`
  - SHA-256:
    `c739c0791a47ae6f9dadddd790b223e1cf728d0db0945500d6d7f851df885620`
  - Git blob: `04781e1107075e1e57c08e6dd4e1f48d9a131763`
- `docs/claim_ledger.csv`
  - bytes: `8971`
  - SHA-256:
    `3ef63ee3836ce67c8b9f4538f754737cdcf53bc67d9a746210a0ea9e81e41d2d`
  - Git blob: `0c7ea56d00ed44bd976e4ba8e05a84cb4c6eb63e`
- validator
  - SHA-256:
    `3d82e6e57f97b9396392dc83423edee559f077c71acf5d03712a2656ded80912`
  - Git blob: `99d2f579c98563969df26dbf1f946d8454c8ba00`
- focused test
  - SHA-256:
    `ca43f22839ed80d80365ff6d5b3f26d186130f0c6374eaea2a98de6c8707c9d3`
  - Git blob: `068333d2db2873044f0599e9ab3c884dfb870ea5`

## Direct-main commit sequence for this task

- `e2f7da44d437459db9cb56de2e1944102039f2d0` — WIKI correction
- `0534463eaab3b6d794135d6782b976fd73d461b4` — bound ledger-row alignment
- `210a33c4ff39ef1ee87a246a9a364f1d9d8f8a5b` — validator summary-row fix
- `787c5e7e45401aea11e17fcd7abc0f176863b25b` — focused regression
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

A concurrent follow-on session then advanced `main` with the fail-closed
`AUD-LEDGER-001` schema validator and evidence. Those commits are preserved and are
not represented as work completed by this WIKI session.

## Scientific boundary

This session did not recalculate the MV4 pull, effective live-time, pile-up rate,
confidence intervals, beam-data result, simulation result, calibration, or detector
performance. Full repository pytest, ruff, ROOT processing, simulation, and GitHub
Actions were not run, and no broad CI success is claimed.

## Acceptance and next work

`AUD-WIKI-002` is `COMPLETE`. The public front door and its four bound rows now pass
the exact-file validator.

The repository-wide WIKI audit remains open under `AUD-WIKI-001`. Claim-ledger
schema remediation remains open under `AUD-LEDGER-001` / `BLK-LEDGER-001`; 24 rows
must be reconstructed from source-backed semantics before their positional late
fields can be interpreted.

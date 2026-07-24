# WIKI Front-Door Claim Remediation Audit

## Scope

This record documents the bounded remediation of `AUD-WIKI-002`. It aligns the
public `WIKI.md` front door with the canonical status and truth-type fields used
by claim-ledger records `CL-007` and `CL-011`, and it removes an unsupported
blanket statement about uncertainty completeness.

This is a documentation/provenance correction. It does not recalculate timing,
effective live-time, pile-up rate, confidence intervals, detector response, or
any data/Monte Carlo result.

## Exact inputs reviewed

- Base remote `main`: `c9ff3196a1c5a4441119e6b19b592db1a8b5763b`
- Original `WIKI.md` Git blob: `c27a1e555145cb248e253f17a6f6d1cfe64542a8`
- Original `WIKI.md` bytes: `19159`
- Original `WIKI.md` SHA-256:
  `62385f61aa5742b9a522efe1bd8a2ab576638a0cfc1cfdf28ad59f53c78f5181`
- Original `docs/claim_ledger.csv` Git blob:
  `6f4d4023814b42a566826912bcef7df9903c41e7`
- Original front-door validator Git blob:
  `53346a2fea2f91e21e8846cbaefde67db1020eca`
- Original focused test Git blob:
  `d48efee195fcfbdd04650bf63dce64c806a06ef0`

## Confirmed defects

1. `MV4 raw timing pull`, `MC raw timing pull`, and `MV4 raw` were labelled
   `PASS`, although `PASS` is absent from the WIKI confidence-status legend and
   canonical claim `CL-007` is `VALIDATED`.
2. The canonical WIKI row for effective live-time used truth type `data_only`,
   while canonical claim `CL-011` is `data_mc_self_consistent`.
3. The front matter stated `Every number has uncertainty.` while the ledger
   contains explicit `CI_MISSING_BLOCKING` values.
4. Exact-file execution exposed a schema-width defect in the claim ledger:
   the header has 43 columns but all 26 original data rows had only 35--40
   columns. In particular, `CL-007` and `CL-011` placed their intended
   `truth_type` and `status` values five columns early.
5. Validator v1.0.0 attempted a truth-type check on every matching tau row,
   including the three-column summary row that has no truth-type column. This
   produced a false `MISSING_WIKI_TRUTH_TYPE` finding after the canonical row
   was corrected.

## Remediation

### Public WIKI

Exactly five public statements were changed:

- the blanket uncertainty-completeness claim now points to the canonical ledger
  and explicitly states that `CI_MISSING_BLOCKING` entries remain incomplete;
- the canonical tau truth type is `data + MC self-consistent`;
- all three raw MV4 status labels are `VALIDATED`.

No numerical value, uncertainty value, formula, selection, or plot was changed.

### Bound claim-ledger rows

Five empty fields were inserted into each of `CL-007` and `CL-011`, restoring
those rows to the 43-column schema without changing their non-empty values.
Their intended fields now parse as:

- `CL-007`: `truth_type=digitized_mc`, `status=VALIDATED`;
- `CL-011`: `truth_type=data_mc_self_consistent`, `status=VALIDATED`.

The other 24 ledger rows remain width-mismatched and are not silently claimed
as repaired. They require a separate row-by-row schema/provenance audit.

### Validator

`validate_wiki_claim_front_door.py` is now v1.1.0. For bindings that require a
truth type, it checks only matching rows with a truth-type-bearing table shape
(six or more columns) and requires at least one such row. Three-column summary
rows continue to be checked for status but no longer generate a false missing
truth-type finding.

## Validation

Commands executed on exact local reconstructions of the proposed files:

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

- validator status: `VALIDATED`;
- process status: `0`;
- issue count: `0`;
- bindings checked: `4`;
- legend statuses found: `8`.

Focused internal-link validation was also executed against the exact corrected
WIKI and a local mirror of all 16 unique internal targets whose existence was
verified on GitHub:

```text
python scripts/broken_link_checker.py

✓ All internal links valid.
```

This is a focused WIKI target check, not a repository-wide scan of every
Markdown file.

## Corrected file provenance

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
- `tools/audit/validate_wiki_claim_front_door.py`
  - SHA-256:
    `3d82e6e57f97b9396392dc83423edee559f077c71acf5d03712a2656ded80912`
  - Git blob: `99d2f579c98563969df26dbf1f946d8454c8ba00`
- `tests/test_validate_wiki_claim_front_door.py`
  - SHA-256:
    `ca43f22839ed80d80365ff6d5b3f26d186130f0c6374eaea2a98de6c8707c9d3`
  - Git blob: `068333d2db2873044f0599e9ab3c884dfb870ea5`

## Acceptance and limitations

`AUD-WIKI-002` is complete when these exact changes are present on remote
`main` and the validator returns `VALIDATED` on the committed files.

A separate claim-ledger schema task remains open because 24 of 26 data rows
still do not match the 43-column header. No interpretation of shifted fields in
those rows is authorized until each row is reconstructed from its source and
validated.

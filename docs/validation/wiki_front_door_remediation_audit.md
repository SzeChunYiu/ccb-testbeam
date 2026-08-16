# Root WIKI canonical-claim remediation audit

## Scope

This validation unit closes the confirmed root-front-door wording conflicts for the canonical Rmax, P04p duplicate-readout, and P07e saturation-recovery claims. It does not claim a resolved Rmax, a production ML model, a detector recalibration, or a new data/simulation result.

## Inputs and provenance

- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `c254e767bbc225d98f9c839d50251c511ca69a98`
- Pre-change `WIKI.md` Git blob: `04781e1107075e1e57c08e6dd4e1f48d9a131763`
- Corrected `WIKI.md` Git blob: `9d8110893adeae482b2439c4187b53f94174a55e`
- Corrected WIKI size: `21368` bytes
- Corrected WIKI SHA-256: `baaa9dbd3585870c7d9c0807493e9afce81f9767f3be68d581502d62496c59d4`
- Claim-ledger Git blob: `853d955f449268ec614ac61f33f243d30cf473e0`
- Claim-ledger size: `12077` bytes
- Claim-ledger SHA-256: `c0e283e6d43a1013a9565f2697c4f99f7b47d639245b9926a8ddc83786602e19`
- Validator: `tools/audit/validate_wiki_claim_front_door.py` v1.2.0
- Policy: `WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`

## Canonical records enforced

The gate requires exactly 43 columns for `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, and `CL-016` before interpreting their late fields.

The corrected public WIKI now:

1. withholds numerical Rmax pending `S-STAT-003` and marks the current claim `BLOCKED`;
2. retains `3.0448717948717947 MHz` only as explicitly superseded correction history;
3. preserves `tau_eff = 124.79 ns` as `VALIDATED` with the canonical data-plus-MC truth type;
4. separates P04p duplicate-readout model selection from P07e saturation recovery;
5. records both production decisions as `GATED` with their distinct limitations;
6. states that no production duplicate-readout model or saturation correction is authorized;
7. removes the unsupported combined/domain-level ML-win wording;
8. changes MV5 Rmax in the MC matrix from `VALIDATED` to `BLOCKED`.

## Executable validation

Commands run on an exact locally reconstructed validator, the byte-identical corrected WIKI candidate, and exact-width current canonical rows extracted from the current claim-ledger blob:

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_wiki_claim_front_door_current.py

python -m pytest tests/test_wiki_claim_front_door_current.py -q

2 passed in 0.05s
```

The direct validator result was:

```text
status: VALIDATED
issues: 0
required claim widths: 43, 43, 43, 43, 43, 43
```

The stale-Rmax mutation regression returned `FLAWED` and included `WITHHELD_RMAX_VALUE_PUBLISHED`, `STATUS_LEDGER_MISMATCH`, and `VALUE_PRESENT_WHEN_LEDGER_WITHHOLDS`.

A focused broken-link run used the repository checker against the corrected WIKI and the 16 existing internal targets referenced by it. It returned `All internal links valid`. The corrected WIKI introduces no new internal file target. A complete repository-wide link scan was not run because a checkout was unavailable.

## Acceptance

The root-front-door remediation is `VALIDATED`. `AUD-WIKI-001` remains `PARTIAL` at repository scope because the remaining material WIKI claims have not all been individually mapped and reviewed.

## Limitations

- Direct cloning failed because this runtime could not resolve `github.com`; authenticated GitHub reads and direct-main writes were used.
- Full repository pytest, ruff, complete broken-link checking, ROOT processing, model reruns, and GitHub Actions were not run.
- No status checks or workflow runs were attached to the implementation/test head.
- This documentation correction does not resolve `S-STAT-003`, `BLK-P04P-001`, or `BLK-P07E-001`.

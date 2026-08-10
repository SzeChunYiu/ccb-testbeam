# ARU-CLAIM-BIRKS-GATE-HARDENING — adversarial child-atom handoff

- Parent atom: `ARU-CLAIM-BIRKS-HEADLINE-001` / issue #1131
- Branch: `audit/issue-1131-birks-public-claim-gate`
- PR: #1132
- Base main reviewed: `cb812b445b778b162ec8cbecde02029c45fc6bfa`

## Child atom discovered by adversarial review

The first local implementation of the public-claim gate searched for the literal
`0.0156 cm/MeV`. That implementation could have been bypassed by changing the public
value to another number such as `0.0157 cm/MeV` while leaving it unbound. This was a
validator-design defect, not a repository physics result.

## Remediation

Version 1.1.0 now:

- detects any numeric Birks value expressed in `cm/MeV` or `mm/MeV`;
- converts both to canonical `cm/MeV` before comparison;
- accepts the equivalent representations `0.0156 cm/MeV` and `0.156 mm/MeV`;
- compares public values with the canonical ledger value;
- compares the declared Cluster-E source-table value with the ledger value;
- preserves all original fail-closed status, source, blocker, schema and UTF-8 checks.

## Validation

```text
python -m py_compile \
  tools/audit/validate_birks_public_claim.py \
  tests/test_validate_birks_public_claim.py

pytest -q tests/test_validate_birks_public_claim.py
14 passed in 0.06s
```

The added hostile controls include a `0.0156 -> 0.0157 cm/MeV` mutation that must still
fail when no ledger/source binding exists, public-value mismatch, source-value
mismatch, and exact `cm/MeV` ↔ `mm/MeV` equivalence. No changed Python line exceeds
100 characters. `ruff` was not available in the local runtime; exact-head repository
CI remains authoritative for the full suite.

## Review state

- Domain/quenching: ACCEPT the hardened provenance gate; physical kB promotion remains
  BLOCKED by #1007/#1008/#1079/#1089/#1095.
- Adversarial mechanism: ACCEPT after the fixed-value bypass was removed.
- Statistics/validation: ACCEPT the deterministic negative controls; no detector or MC
  inference is authorized by them.
- Claims/provenance: ACCEPT; public withholding remains the safest immediate branch
  until a deliberate GATED canonical binding is introduced.

This file is append-equivalent provenance for the child atom; it does not replace the
older `2026-08-10T005000Z` handoff.

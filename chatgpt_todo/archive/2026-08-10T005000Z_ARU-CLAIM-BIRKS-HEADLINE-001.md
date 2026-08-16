# ARU-CLAIM-BIRKS-HEADLINE-001 handoff

- Session: `2026-08-10T005000Z`
- Base `main`: `cb812b445b778b162ec8cbecde02029c45fc6bfa`
- Issue: #1131
- Branch: `audit/issue-1131-birks-public-claim-gate`
- PR: #1132
- Scope: public claim governance only; no Birks physics value is validated here.

## Confirmed defect

`README.md`, `WIKI.md`, and `docs/PUBLICATION_NARRATIVE.md` publish
`Birks kB = 0.0156 cm/MeV` while declaring the canonical claim ledger and/or
`reports/studies/clusterE/claims_table.csv` authoritative. The current Cluster-E table
contains no Birks row, and #1131 records that the 43-column claim ledger has no Birks
claim row. Cluster-C itself reports 0.0156 for one `dE/dx` construction and 0.0127 for
another, so the legacy number is already estimator-world dependent.

## Delivered in PR #1132

- `tools/audit/validate_birks_public_claim.py` v1.0.0
- `tests/test_validate_birks_public_claim.py`
- `docs/validation/birks_public_claim_gate.md`

The gate fails closed on an unbound public number, missing declared source-table row,
public status stronger than the ledger, missing caveat for a non-authorizing value,
missing blockers/provenance, duplicate Birks rows, malformed schema, and invalid
UTF-8. It accepts either complete public withholding or one truthful GATED canonical
binding with a matching Cluster-E row.

## Validation executed

```text
python -m py_compile \
  tools/audit/validate_birks_public_claim.py \
  tests/test_validate_birks_public_claim.py

pytest -q tests/test_validate_birks_public_claim.py
10 passed in 0.04s
```

Both changed Python files have no line over 100 characters. `ruff` was unavailable in
the local runtime. `git clone https://github.com/SzeChunYiu/ccb-testbeam.git` failed
because the runtime could not resolve `github.com`; therefore no complete-current
checkout execution is claimed. GitHub MC Validation CI was running at handoff.

## Review votes

- Scintillator/quenching lead: ACCEPT provenance gate; BLOCK physics promotion.
- Adversarial mechanism reviewer: ACCEPT with removal/source/status negative controls.
- Statistics/validation reviewer: ACCEPT deterministic software tests; BLOCK any
  interpretation as detector/MC validation.
- Claims/provenance reviewer: ACCEPT; prefer withholding unless a deliberately GATED
  row is introduced.

## Literature

Pöschl et al., *Nuclear Instruments and Methods A* 988 (2021) 164865,
DOI `10.1016/j.nima.2020.164865`, fit and compare multiple ionization-quenching models
for plastic scintillators and treat the parameters as empirical. This supports keeping
model identity explicit but is not required to prove the repository-local provenance
defect.

## Next atomic unit

After PR #1132 is green and reviewed, remediate the controlled front doors and run the
new validator on a complete current checkout. Safest immediate branch: withhold/demote
the numerical headline while preserving the Cluster-C legacy study. A GATED ledger
binding is permissible only if it carries exact source/model identity, CI state, and
blockers #1007/#1008/#1079/#1089/#1095. Physical promotion of kB remains downstream of
those atoms.

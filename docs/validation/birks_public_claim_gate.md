# ARU-CLAIM-BIRKS-HEADLINE-001 — public Birks claim binding gate

## Scope

This audit unit addresses issue #1131 only: whether a public numerical Birks `kB`
statement is bound to the repository's declared canonical claim system. It does
**not** validate the physical value of `kB`, the scintillator material, the Geant4
production-cut/step world, or the per-track `dE/dx` estimator.

Base inspected: `main@cb812b445b778b162ec8cbecde02029c45fc6bfa`.

## Exact repository evidence

- `README.md` blob `678d7898e1171405cb0aca83a4342603ba388b91` says the row-by-row authority is
  `docs/claim_ledger.csv`, says its headline section mirrors the Cluster-E claims
  table, and publishes `Birks kB ... 0.0156 cm/MeV ... PASS`.
- `WIKI.md` says MC-closure values are reproduced verbatim from
  `reports/studies/clusterE/claims_table.csv` with no hand-entered values, but
  publishes `0.0156 cm/MeV` in both the MC-closure and canonical-results tables.
- `docs/PUBLICATION_NARRATIVE.md` blob `d42539871eaff8b5ec94e59f2f9489974b824af9`
  says every number is reproduced from the dashboard and Cluster-E claims table,
  then publishes `0.0156 cm/MeV` in the headline table and prose.
- `reports/studies/clusterE/claims_table.csv` blob
  `31bfd9b8133439e830d3e89bbb25046468eaecba` contains four rows and no Birks row.
- The canonical claim ledger has no Birks-kB row; issue #1131 records the exact
  CL-001..CL-026 inspection and the missing binding.
- `reports/studies/clusterC/SUMMARY.md` blob
  `acb15c520713a8478940d08732ddac370c2369f1` records two different fitted numbers:
  `0.0156 cm/MeV` for its per-track construction and `0.0127` for the total-Edep
  proxy, explicitly demonstrating estimator dependence inside the legacy study.

Therefore the current public provenance graph is inconsistent even before asking
whether `0.0156` is physically transferable.

## Atomic research universe

### Contract

Input objects are the controlled public documents, the 43-column canonical claim
ledger, and the Cluster-E public claim table. The output is a binary authorization
state for any public numerical Birks headline.

The invariant is:

`public numeric claim -> exactly one ledger row -> exactly one declared source-table row`

with compatible numerical value after unit normalization, units, status and
provenance.

A non-authorizing canonical state additionally requires explicit blockers and a
visible status caveat wherever the number is published.

### Competing explanations

- H1: the public value is generated from the canonical ledger/source table.
- H2: the value is a legitimate Cluster-C study result but was manually copied into
  front doors without canonical claim binding.
- H3: a Birks ledger/source row exists but is hidden by schema or parsing problems.
- H4: the public number should be withheld until physics-model identity is closed.

H1 is falsified by the exact current Cluster-E table and missing ledger row. H3 is
falsified by the exact-width ledger audit already recorded in #1131. H2 and H4 remain
compatible with the evidence; the gate deliberately allows either a correctly GATED
binding or complete public withholding.

## Four sequential review passes

1. **Scintillator/quenching lead — ACCEPT gate, BLOCK physics promotion.** The gate
   correctly separates claim provenance from the unresolved material/model question.
2. **Adversarial mechanism reviewer — ACCEPT after hardening.** The first local draft
   detected only the literal `0.0156 cm/MeV`. That was itself a bypass: changing the
   public value to `0.0157` could evade the gate. Version 1.1.0 now detects any numeric
   Birks value in `cm/MeV` or `mm/MeV`, normalizes units, and compares public, ledger,
   and source-table values. A mutation regression proves the bypass is closed.
3. **Statistics/validation reviewer — ACCEPT software fixture validation; BLOCK real
   scientific validation.** The software tests are deterministic. No MC or beam-data
   inference is made by this unit.
4. **Claims/provenance reviewer — ACCEPT.** Withholding is permitted without creating
   a synthetic ledger row; publishing the value requires a unique exact-width binding,
   source identity, CI state and blockers.

## Literature check

The claim-governance decision is also consistent with primary quenching literature.
Pöschl et al., *NIM A* 988 (2021) 164865,
DOI `10.1016/j.nima.2020.164865`, measure proton quenching in plastic scintillators,
fit multiple quenching models, and emphasize that model parameters are empirical.
That supports treating a fitted `kB` as model/measurement-world dependent rather than
as a context-free constant. This literature fact motivates #1008 but is not needed to
prove the repository-local provenance defect.

## Implementation

Added `tools/audit/validate_birks_public_claim.py` v1.1.0. It:

- reads README, WIKI, publication narrative, ledger and Cluster-E table once as exact
  UTF-8 byte snapshots and records SHA-256 provenance;
- requires the canonical 43-column ledger schema and unique claim IDs;
- detects any numeric Birks `kB` occurrence written in `cm/MeV` or `mm/MeV`;
- normalizes `mm/MeV` to `cm/MeV` before value comparison, so `0.156 mm/MeV` and
  `0.0156 cm/MeV` are correctly treated as equivalent descriptions;
- rejects a numeric public claim with no unique Birks ledger row;
- rejects public or source-table values that disagree with the canonical ledger value;
- rejects front-door assertions that the Cluster-E table is the source when it has no
  Birks row;
- rejects public `PASS` when the canonical row is non-authorizing;
- requires an explicit status caveat for a non-authorizing published value;
- requires a GATED/BLOCKED/etc. ledger row to carry explicit blockers;
- accepts the alternative remediation in which all controlled public numerical Birks
  values are withheld.

## Validation executed in this session

A GitHub network checkout was attempted and failed because this runtime could not
resolve `github.com`. The new files were therefore reconstructed and tested locally
before authenticated connector writes.

```text
python -m py_compile \
  tools/audit/validate_birks_public_claim.py \
  tests/test_validate_birks_public_claim.py

pytest -q tests/test_validate_birks_public_claim.py
..............                                                           [100%]
14 passed in 0.06s
```

The 14 tests cover the current-like unbound state; a `0.0156 -> 0.0157` mutation that
must not bypass the gate; a corrected GATED state; exact `cm/MeV` ↔ `mm/MeV`
equivalence; public-value mismatch; source-value mismatch; stronger public status;
missing status caveat; missing Cluster-E source row; missing blockers; complete
withholding; duplicate Birks ledger rows; invalid UTF-8; and machine-readable CLI
failure output. Both changed Python files were checked for lines over 100 characters;
none remain. `ruff` was unavailable in the local runtime and is left to repository CI.

## Scientific boundary and next action

This gate does not choose between `0.0156`, `0.0127`, another first-order Birks value,
or another quenching model. The immediate next step after merging the gate is to run
it on a complete current checkout and make the public state pass by either:

1. withholding/demoting the numerical headline everywhere in the controlled front
   doors; or
2. adding one truthful GATED simulation-fit ledger/source row carrying blockers
   `#1007;#1008;#1079;#1089;#1095`, then changing every public status/caveat to match.

Only later physics atoms may promote the value beyond that non-authorizing state.

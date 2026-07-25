# Cluster E canonical claim-binding and provenance audit

- **Task:** `AUD-REP-001`
- **Policy:** `CLUSTERE_HEADLINES_MUST_BIND_CANONICAL_LEDGER_AND_FULL_PROVENANCE`
- **Initial remote main:** `8ceda40d2f71d53a93bb02568c8e90509c973e0c`
- **Audit status:** **FLAWED** — 13 fail-closed findings
- **Evidence class:** software/documentation provenance audit

## Scientific question

Does the new Cluster E synthesis layer faithfully bind its public headline values,
statuses, and provenance to the canonical claim ledger and the distinct Cluster D
rerun/toy outputs it also summarizes?

## Exact repository facts

The canonical ledger records:

| Claim | Canonical value | Canonical state |
|---|---:|---|
| `CL-013` | `92 ADC/MeV`, with a `28 ADC/MeV` heuristic systematic envelope | `GATED`; not a confidence interval |
| `CL-021` | Pearson `chi2/ndf = 68269.40598948313` | `FLAWED`; legacy fixed diagnostic |
| `CL-022` | early-peak morphology `283/87555 = 0.003232254011764034` | `TRUTH_LEVEL_MC_ONLY` |

Cluster D also contains distinct later outputs:

- MV0 rerun gain `110 ADC/MeV`, KS `0.10773131550396098`;
- MV3 rerun `chi2/ndf = 86135.4707883642`;
- MV6 toy sample `25/38` early-peak tracks labelled C12.

These later outputs are useful diagnostics, but their own Cluster D summary states that
they do not silently supersede the canonical rows.

## Confirmed defects

1. `reports/PROJECT_DASHBOARD.md`, Cluster E `SUMMARY.md`, and
   `claims_table.csv` present `110 ADC/MeV` as the `CL-013` proxy instead of the
   canonical `92 ADC/MeV` value and `28 ADC/MeV` envelope.
2. The dashboard and summary cite approximately `8.6e4` as `CL-021`, conflating the
   later Cluster D MV3 rerun with the canonical exact legacy value
   `68269.40598948313`. The claims CSV also changes the canonical state from
   `FLAWED` to `TENSION`.
3. The Cluster E public claim row substitutes the Cluster D toy `25/38` C12 count
   for canonical `CL-022`, whose measurand is the total early-peak morphology rate
   `283/87555`; it also changes the canonical status from
   `TRUTH_LEVEL_MC_ONLY` to `BLOCKED`.
4. `provenance.json` records `base_commit = "(worktree HEAD)"` rather than a commit
   SHA, stores only 12 hexadecimal characters per digest while labelling them
   SHA-256, and omits used headline sources including the Opticks summary and
   Cluster D MV3 output.
5. The generator hardcodes the conflicting values and the truncated-digest policy,
   so rerunning it reproduces the contradiction instead of deriving canonical
   fields from the ledger.

The dashboard's statement that it is consistent with the ledger is therefore not
currently true.

## Better method

The synthesis must treat the ledger as a typed data source, not a prose citation:

- parse exactly 43 columns and reject duplicate/malformed claim rows;
- derive each canonical headline value, status, truth type, and uncertainty meaning
  from named ledger fields;
- show Cluster D reruns/toy studies in separate rows explicitly labelled as distinct
  diagnostics that do not supersede the canonical rows;
- record a full 40-hex base commit and full 64-hex SHA-256 for every input actually
  used, including Markdown sources;
- regenerate Markdown, CSV, JSON, and visual outputs in one transaction and run a
  location-bound validator before publication.

## Delivered validation gate

Added `tools/audit/validate_clusterE_canonical_binding.py`. It:

- snapshots every input once as strict UTF-8 and records bytes/SHA-256;
- enforces the 43-column ledger contract and unique claim IDs;
- validates exact `CL-013`, `CL-021`, and `CL-022` fields;
- distinguishes canonical `CL-021` from the Cluster D MV3 rerun;
- checks the dashboard, summary, and claims CSV at their actual claim locations;
- requires a full base commit and full SHA-256 for all required provenance inputs;
- rejects invalid UTF-8, malformed inputs, and destructive output aliasing;
- publishes machine-readable JSON atomically.

Focused tests:

```text
python -m py_compile \
  tools/audit/validate_clusterE_canonical_binding.py \
  tests/test_validate_clusterE_canonical_binding.py \
  tools/audit/render_clusterE_canonical_binding_evidence.py

pytest -q tests/test_validate_clusterE_canonical_binding.py
6 passed in 0.05s
```

Tests cover a current-like failing contract, a corrected zero-finding contract,
truncated provenance digests, malformed ledger width, invalid UTF-8, and atomic JSON
publication. The generated validation JSON parsed successfully and the SVG parsed as
XML. Changed Python lines are no longer than 100 characters.

## Acceptance boundary

This unit validates the contradiction and provides a fail-closed remediation gate.
It deliberately does not rewrite or regenerate the Cluster E dashboard bundle in the
same audit unit. `AUD-REP-001` remains **PARTIAL** until the generator and all derived
Markdown/CSV/JSON/PNG artifacts are corrected together and the validator returns
`VALIDATED` on exact repository bytes.

No detector performance, data/MC transfer, precision calibration, C12 identity, or
accepted stopping-profile closure is established by this audit.

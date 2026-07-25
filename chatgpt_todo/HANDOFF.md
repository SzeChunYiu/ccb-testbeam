# Latest Handoff — AUD-REP-001 Cluster E canonical binding audit

## Delivery identity

- **Session stamp:** `2026-07-25T190251Z`
- **Task ID:** `AUD-REP-001`
- **Initial remote `main`:** `8ceda40d2f71d53a93bb02568c8e90509c973e0c`
- **Validated implementation/evidence/archive head:**
  `2300d39f92d01cb73e545f6f68c6ad6c7641ed86`
- **Destination:** direct GitHub contents-API commits to remote `main`; no
  force-push, history rewrite, task branch, or PR transport.
- **Push-output boundary:** the connector returned successful commit SHAs rather
  than conventional textual `git push` stdout.

## Reviewed repository state

Fetched current `main`, recent history, combined status, open pull requests,
mandatory coordination records, `docs/claim_ledger.csv`, Cluster D summary and
MV0/MV3 outputs, Cluster E generator, project dashboard, Cluster E summary,
claims table, metrics, provenance, and the Opticks summary.

No status checks were attached to initial head
`8ceda40d2f71d53a93bb02568c8e90509c973e0c`. The execution container could not
resolve `github.com`, so a complete clone was unavailable. Exact source blobs were
fetched through the authenticated connector; focused Python files were reconstructed
and executed locally.

## Scientific question

Does Cluster E's new executive synthesis faithfully bind public values, evidence
classes, statuses, and provenance to the canonical ledger while keeping later
Cluster D reruns and toy studies separate?

## Canonical facts and distinct diagnostics

Canonical ledger:

- `CL-013 = 92 ADC/MeV`, with a `28 ADC/MeV` heuristic systematic envelope,
  `data_mc_calibration_proxy`, `GATED`;
- `CL-021 = 68269.40598948313` Pearson chi2/ndf,
  `legacy_data_mc_profile_diagnostic`, `FLAWED`;
- `CL-022 = 283/87555 = 0.003232254011764034`, `mc_truth_only`,
  `TRUTH_LEVEL_MC_ONLY`.

Distinct Cluster D outputs:

- MV0 rerun `110 ADC/MeV`, KS `0.10773131550396098`;
- MV3 rerun chi2/ndf `86135.4707883642`;
- MV6 toy early-peak C12 subset `25/38`.

Cluster D documentation says these outputs do not silently supersede the canonical
cross-domain claim rows.

## Confirmed defects

The exact current Cluster E bundle is `FLAWED` with 13 findings:

1. dashboard, summary, and claims CSV substitute the Cluster D `110 ADC/MeV`
   rerun for canonical `CL-013=92 ADC/MeV` with the `28 ADC/MeV` envelope;
2. dashboard and summary conflate the Cluster D MV3 rerun with canonical `CL-021`;
   the CSV also changes the exact canonical value/status to rounded `6.8e4` and
   `TENSION` instead of `FLAWED`;
3. dashboard, summary, and CSV substitute the MV6 toy `25/38` C12 subset for
   canonical `CL-022=283/87555` and alter its status;
4. provenance uses literal `(worktree HEAD)`, only 12 digest characters, and omits
   used Opticks and MV3 sources;
5. the generator hardcodes these conflicts, so reruns reproduce them.

The dashboard's statement that it is consistent with the ledger is therefore not
currently true.

## Delivered gate and evidence

Added:

- `tools/audit/validate_clusterE_canonical_binding.py`
- `tests/test_validate_clusterE_canonical_binding.py`
- `tools/audit/render_clusterE_canonical_binding_evidence.py`
- `docs/validation/clusterE_canonical_binding_validation.json`
- `docs/validation/clusterE_canonical_binding.svg`
- `docs/validation/clusterE_canonical_binding_audit.md`
- `chatgpt_todo/archive/2026-07-25T190251Z_AUD-REP-001_CLUSTERE_CANONICAL_BINDING.md`

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`

The validator snapshots strict UTF-8 bytes once, enforces the exact 43-column
ledger contract and unique IDs, validates the three canonical rows, checks the
actual dashboard/summary/CSV claim locations, separates canonical CL-021 from the
MV3 rerun, requires a full base commit and full input SHA-256 mappings, rejects
malformed input and destructive aliases, and publishes JSON atomically.

## Validation

```text
python -m py_compile \
  tools/audit/validate_clusterE_canonical_binding.py \
  tests/test_validate_clusterE_canonical_binding.py \
  tools/audit/render_clusterE_canonical_binding_evidence.py

pytest -q tests/test_validate_clusterE_canonical_binding.py
6 passed in 0.05s
```

The corrected fixture returned `VALIDATED` with zero findings. Current-like
substitution, truncated digest, malformed row width, invalid UTF-8, and atomic JSON
publication were covered. JSON and SVG parsing passed; changed Python lines are no
longer than 100 characters.

Exact current-repository end-to-end execution and PNG regeneration were not run
because a complete checkout was unavailable. The machine-readable record explicitly
separates exact GitHub-blob inspection from executable synthetic controls.

## Direct-main sequence through archive

- `d7098e6e33bedf0eda4b09f7f57b48c63e4cc12e` — fail-closed audit gate
- `13cae5e72a15c5124c886edbe21b4eced33d0352` — focused tests
- `18e1b8cb3b2f441e1bdab922262f102860e59b37` — evidence renderer
- `0a32012361d4f8aa4d533e2c5f82a2b0816ccb1b` — machine-readable evidence
- `9a4181c4517b98862e09b4af8190aa21d4c9366a` — visual evidence
- `72384a4f764a87c3aacafe87f13198129624e457` — audit report
- `ea51ebd80daee410074f9cf4eb37e0599aafa4fc` — active task
- `2300d39f92d01cb73e545f6f68c6ad6c7641ed86` — immutable archive

## Acceptance and next action

The focused audit gate/evidence is `VALIDATED`; cumulative `AUD-REP-001` is
`PARTIAL`. Correct the generator to derive canonical fields, display later rerun/toy
outputs as separate diagnostics, emit full hashes, transactionally regenerate every
Markdown/CSV/JSON/PNG artifact, and require the exact repository validator plus link
and focused test gates to return zero findings.

No detector performance, data/MC transfer, precision calibration, C12 identity, or
accepted stopping-profile closure was established.

Repository-wide pytest/ruff, Cluster E PNG regeneration, complete link inventory,
and GitHub Actions were not run. `SESSION_LOG.md`, `MASTER_INDEX.md`, `BACKLOG.md`,
`BLOCKERS.md`, and aggregate matrices were not replaced because complete current
bytes were returned only through paged/truncated views; partial replacement could
erase unrelated append-only provenance. The immutable archive and this handoff retain
the complete append-equivalent record.

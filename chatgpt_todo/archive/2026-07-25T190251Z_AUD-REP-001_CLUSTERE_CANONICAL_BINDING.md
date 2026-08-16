# Immutable session record — AUD-REP-001 Cluster E canonical binding

## Identity

- **Session stamp:** `2026-07-25T190251Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `8ceda40d2f71d53a93bb02568c8e90509c973e0c`
- **Task:** audit Cluster E dashboard/claim/provenance binding
- **Policy:** `CLUSTERE_HEADLINES_MUST_BIND_CANONICAL_LEDGER_AND_FULL_PROVENANCE`
- **Focused acceptance:** validated audit gate and evidence
- **Cumulative status:** `PARTIAL`; current Cluster E bundle is `FLAWED`

## Repository state reviewed

Fetched the exact repository, current `main`, recent commits, open pull requests,
combined status, repository-local coordination records, canonical claim ledger,
Cluster D summary and MV0/MV3 outputs, Cluster E generator, dashboard, summary,
claims CSV, metrics, provenance, and Opticks summary.

No combined status checks were attached to initial head
`8ceda40d2f71d53a93bb02568c8e90509c973e0c`. A direct clone was unavailable
because the execution container could not resolve `github.com`; exact source blobs
were fetched through the authenticated connector and focused Python files were
reconstructed and executed locally.

## Canonical values and distinct later diagnostics

Canonical `docs/claim_ledger.csv` fields:

- `CL-013`: `92 ADC/MeV`, heuristic systematic envelope `28 ADC/MeV`,
  `data_mc_calibration_proxy`, `GATED`;
- `CL-021`: exact Pearson `chi2/ndf = 68269.40598948313`,
  `legacy_data_mc_profile_diagnostic`, `FLAWED`;
- `CL-022`: `283/87555 = 0.003232254011764034`, `mc_truth_only`,
  `TRUTH_LEVEL_MC_ONLY`.

Distinct Cluster D outputs:

- MV0 rerun gain `110 ADC/MeV`, KS `0.10773131550396098`;
- MV3 rerun `chi2/ndf = 86135.4707883642`;
- MV6 toy early-peak C12 subset `25/38`.

Cluster D documentation states these outputs do not silently supersede the
canonical cross-domain claim rows.

## Confirmed defects

The current Cluster E bundle returned 13 fail-closed findings:

1. dashboard, summary, and claims CSV bind `CL-013` to `110` rather than canonical
   `92 ADC/MeV` with the `28 ADC/MeV` heuristic envelope;
2. dashboard/summary conflate the Cluster D MV3 rerun with canonical `CL-021`,
   while the claims CSV changes the exact value/state to rounded `6.8e4`/`TENSION`;
3. dashboard/summary/CSV substitute the MV6 toy `25/38` C12 subset for the
   canonical `CL-022` total morphology rate `283/87555`, and change the status;
4. `provenance.json` uses literal `(worktree HEAD)`, only 12 hexadecimal digest
   characters, and omits actually used Opticks and MV3 inputs;
5. the generator hardcodes these conflicts, so regeneration reproduces them.

The dashboard statement that it is consistent with the ledger is therefore false
for these bound claims.

## Delivered files

Added:

- `tools/audit/validate_clusterE_canonical_binding.py`
- `tests/test_validate_clusterE_canonical_binding.py`
- `tools/audit/render_clusterE_canonical_binding_evidence.py`
- `docs/validation/clusterE_canonical_binding_validation.json`
- `docs/validation/clusterE_canonical_binding.svg`
- `docs/validation/clusterE_canonical_binding_audit.md`

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md` (delivery commit recorded separately)

## Validation

```text
python -m py_compile \
  tools/audit/validate_clusterE_canonical_binding.py \
  tests/test_validate_clusterE_canonical_binding.py \
  tools/audit/render_clusterE_canonical_binding_evidence.py

pytest -q tests/test_validate_clusterE_canonical_binding.py
6 passed in 0.05s
```

Coverage includes current-like fail-closed behavior, a corrected zero-finding
contract, truncated digests, malformed ledger width, invalid UTF-8, and atomic JSON
publication. JSON parsing, SVG XML parsing, and 100-character Python line limits
passed.

The exact full repository command was not run because a complete checkout was not
available. The machine-readable record therefore distinguishes exact GitHub-blob
review from synthetic executable controls.

## Better method and next action

1. Parse the ledger as a strict 43-field typed source.
2. Derive canonical headline value/status/truth/uncertainty fields; do not hardcode
   canonical claims.
3. Keep later Cluster D rerun/toy diagnostics in separate explicitly labelled rows.
4. Record a full 40-hex base commit and full 64-hex digest for every input used.
5. Regenerate Markdown, CSV, JSON, provenance, and all PNGs together.
6. Run the new validator, existing claim/WIKI validators, broken-link inventory,
   focused pytest, and available CI before accepting the regenerated bundle.

## Direct-main sequence before handoff

- `d7098e6e33bedf0eda4b09f7f57b48c63e4cc12e` — audit gate
- `13cae5e72a15c5124c886edbe21b4eced33d0352` — focused tests
- `18e1b8cb3b2f441e1bdab922262f102860e59b37` — evidence renderer
- `0a32012361d4f8aa4d533e2c5f82a2b0816ccb1b` — machine-readable record
- `9a4181c4517b98862e09b4af8190aa21d4c9366a` — visual evidence
- `72384a4f764a87c3aacafe87f13198129624e457` — audit report
- `ea51ebd80daee410074f9cf4eb37e0599aafa4fc` — active-task update

## Scientific boundary

This is software/documentation provenance validation only. No detector performance,
data/MC transfer, accepted calibration, C12 identity, or stopping-profile closure was
produced or authorized.

Repository-wide pytest/ruff, Cluster E PNG regeneration, full broken-link inventory,
and GitHub Actions were not run. `MASTER_INDEX.md`, `BACKLOG.md`, `BLOCKERS.md`, and
aggregate matrices were not replaced because their complete current bytes were
returned only through paged/truncated views; partial replacement could erase
unrelated provenance.

# Latest Handoff — AUD-REP-001 Cluster E canonical binding audit

## Delivery identity

- **Session stamp:** `2026-07-25T190251Z`
- **Task ID:** `AUD-REP-001`
- **Initial remote `main`:** `8ceda40d2f71d53a93bb02568c8e90509c973e0c`
- **Concurrent main reconciliation:** publication-facing commit
  `ed28eb8ed9e3f15016c1a4bf0021293e813ee01c` landed before the first audit
  write. It did not change the audited Cluster E dashboard blob
  `49f35e9593e5896bea28ffaaf13f46b7863ed3b9`; the exact current dashboard was
  re-read after delivery and still contains the confirmed conflicts.
- **Validated implementation/evidence/archive head:**
  `2300d39f92d01cb73e545f6f68c6ad6c7641ed86`
- **Validated delivery handoff / after-SHA:**
  `1dc7d81d9cb26bb047e6839089fef93e8b51daed`
- **First remote confirmation commit:**
  `604b2785b40182b055021a62acf03a17c074b8c7`
- **Destination:** direct GitHub contents-API commits to remote `main`; no
  force-push, history rewrite, task branch, or PR transport.
- **Push-output boundary:** successful commit SHAs were returned rather than
  conventional textual `git push` stdout.

## Reviewed state

Fetched current `main`, recent history, status checks, open PRs, mandatory
coordination records, `docs/claim_ledger.csv`, Cluster D summary and MV0/MV3
outputs, Cluster E generator, dashboard, summary, claims table, metrics,
provenance, and the Opticks summary. No status checks were attached to initial
head. A complete clone was unavailable because the execution container could not
resolve `github.com`; exact GitHub blobs were reviewed and focused reconstructed
Python files were executed locally.

## Canonical facts versus distinct Cluster D diagnostics

Canonical ledger:

- `CL-013 = 92 ADC/MeV`, with a `28 ADC/MeV` heuristic systematic envelope,
  `data_mc_calibration_proxy`, `GATED`;
- `CL-021 = 68269.40598948313` Pearson chi2/ndf,
  `legacy_data_mc_profile_diagnostic`, `FLAWED`;
- `CL-022 = 283/87555 = 0.003232254011764034`, `mc_truth_only`,
  `TRUTH_LEVEL_MC_ONLY`.

Distinct Cluster D outputs are MV0 `110 ADC/MeV` (KS
`0.10773131550396098`), MV3 chi2/ndf `86135.4707883642`, and the MV6 toy C12
subset `25/38`. Cluster D documentation says these do not silently supersede
canonical cross-domain claims.

## Confirmed defects

The exact current Cluster E bundle is `FLAWED` with 13 findings:

1. dashboard, summary, and claims CSV substitute `110 ADC/MeV` for canonical
   `CL-013=92 ADC/MeV` and its `28 ADC/MeV` envelope;
2. dashboard/summary conflate the MV3 rerun with `CL-021`; the CSV changes the
   exact canonical value/status to rounded `6.8e4` and `TENSION`;
3. dashboard/summary/CSV substitute the toy `25/38` C12 subset for canonical
   `CL-022=283/87555` and alter its status;
4. provenance uses `(worktree HEAD)`, 12-character digests, and omits used
   Opticks and MV3 sources;
5. the generator hardcodes the conflicts, so regeneration reproduces them.

The dashboard's statement that it is consistent with the ledger is not currently
true. The concurrent publication-facing update propagates the dashboard/claims
CSV framing but does not repair their source contradiction.

## Delivered files

Added:

- `tools/audit/validate_clusterE_canonical_binding.py`
- `tests/test_validate_clusterE_canonical_binding.py`
- `tools/audit/render_clusterE_canonical_binding_evidence.py`
- `docs/validation/clusterE_canonical_binding_validation.json`
- `docs/validation/clusterE_canonical_binding.svg`
- `docs/validation/clusterE_canonical_binding_audit.md`
- `chatgpt_todo/archive/2026-07-25T190251Z_AUD-REP-001_CLUSTERE_CANONICAL_BINDING.md`

Updated `chatgpt_todo/ACTIVE_TASK.md` and `HANDOFF.md`.

The validator enforces single-read strict UTF-8 snapshots, exact 43-column ledger
rows and unique IDs, location-bound claim checks, separation of canonical CL-021
from the MV3 rerun, full base-commit and input-digest provenance, controlled
invalid-input handling, destructive-alias rejection, and atomic JSON publication.

## Validation

```text
python -m py_compile \
  tools/audit/validate_clusterE_canonical_binding.py \
  tests/test_validate_clusterE_canonical_binding.py \
  tools/audit/render_clusterE_canonical_binding_evidence.py

pytest -q tests/test_validate_clusterE_canonical_binding.py
6 passed in 0.05s
```

The corrected fixture returned zero findings. Current-like substitution,
truncated digests, malformed row width, invalid UTF-8, and atomic publication
were covered. JSON and SVG parsing passed; changed Python lines are at most 100
characters. Exact full-checkout execution and PNG regeneration were not run.

## Direct-main sequence

- `d7098e6e33bedf0eda4b09f7f57b48c63e4cc12e` — audit gate
- `13cae5e72a15c5124c886edbe21b4eced33d0352` — tests
- `18e1b8cb3b2f441e1bdab922262f102860e59b37` — renderer
- `0a32012361d4f8aa4d533e2c5f82a2b0816ccb1b` — JSON evidence
- `9a4181c4517b98862e09b4af8190aa21d4c9366a` — SVG evidence
- `72384a4f764a87c3aacafe87f13198129624e457` — audit report
- `ea51ebd80daee410074f9cf4eb37e0599aafa4fc` — active task
- `2300d39f92d01cb73e545f6f68c6ad6c7641ed86` — archive
- `1dc7d81d9cb26bb047e6839089fef93e8b51daed` — delivery handoff
- `604b2785b40182b055021a62acf03a17c074b8c7` — first confirmation

## Acceptance boundary and next action

Focused audit/evidence is `VALIDATED`; cumulative `AUD-REP-001` is `PARTIAL`.
Derive canonical fields in the generator, show rerun/toy outputs separately,
emit full hashes, regenerate all Markdown/CSV/JSON/PNG artifacts together, and
require the exact validator, link checks, focused tests, and available CI to pass.

No detector performance, data/MC transfer, precision calibration, C12 identity,
or accepted stopping-profile closure was established. Repository-wide
pytest/ruff, PNG regeneration, full link inventory, and GitHub Actions were not
run.

`SESSION_LOG.md`, `MASTER_INDEX.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate
matrices were not replaced because complete current bytes were only available
through paged/truncated views; partial replacement could erase append-only or
concurrent provenance. The immutable archive and this handoff preserve the full
append-equivalent run record.

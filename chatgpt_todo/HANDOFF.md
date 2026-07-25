# Latest Handoff — AUD-CLD-002 Cluster D canonical PSTAR binding

## Delivery identity

- **Session stamp:** `2026-07-25T173220Z`
- **Task ID:** `AUD-CLD-002`
- **Initial remote `main`:** `64c3841ccb522589e6866d835889e797ea342e24`
- **Validated implementation/evidence/archive head:**
  `bff941c6047ec589ded038d7afcb554b3abcb63c`
- **Validated delivery handoff / after-SHA:**
  `2a81915477741651fa08a5b7e754383a790e196a`
- **Remote-main confirmation:** this update is based on fetched handoff blob
  `5d2101a66749a5aafc31d51c84a8f6b732155391`, proving remote `main` already
  contained delivery commit `2a81915477741651fa08a5b7e754383a790e196a`.
- **Destination:** direct GitHub contents-API commits to remote `main`; no
  force-push, history rewrite, task branch, or PR transport.
- **Push-output boundary:** the connector returned successful commit SHAs rather
  than conventional textual `git push` stdout.
- **PR #868:** closed, unmerged, non-mergeable, and untouched.

## Reviewed repository state

Fetched current `main`, recent history, open PRs, PR #868, Cluster D summary and
reproducer, campaign plot helpers, the historical VIS-MC diagnostics, canonical
PSTAR CSV/parser, and repository-local coordination records. The preceding
Cluster D handoff named this focused migration as the next action.

## Confirmed defect

`_common.py` carried a second 20-row PSTAR-like table while the repository already
contained a 141-row canonical table and exact-decimal validator. The historical
VIS-MC-002 caption incorrectly said the canonical CSV was absent. The embedded
total stopping-power values were high relative to the canonical column by:

| Energy | Embedded | Canonical | Relative difference |
|---:|---:|---:|---:|
| 10 MeV | 50.5 | 45.0 | +12.2222% |
| 50 MeV | 19.8 | 12.21 | +62.1622% |
| 100 MeV | 12.9 | 7.14 | +80.6723% |
| 150 MeV | 9.74 | 5.331 | +82.7049% |

The historical panel also displayed an unsupported chi-square despite lacking an
accepted measurand, complete uncertainty model, covariance, and detector/model
systematics. These are reference differences, not detector measurements.

## Validated remediation

- Removed the embedded PSTAR table from the campaign helper.
- Reused `read_validated_pstar_table()` v1.1.0 and `total_MeV_cm2_g`.
- Bound conversion to density 1.060 g/cm3, log interpolation, and fail-closed
  reference-domain checks.
- Added a dedicated renderer with exact-energy grouping,
  `RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED`, `math.fsum` sufficient statistics,
  canonical reference provenance, external run paths, plot bytes/SHA-256,
  `uncertainty_method=NOT_EVALUATED`, and `acceptance_statistic=NONE`.
- Added the canonical renderer to the Cluster D reproducer.
- Marked `VIS-MC-002_transport_vs_pstar.png` `SUPERSEDED`; documented the
  canonical PNG/JSON and diagnostic-only scientific boundary.
- Added a fail-closed validator, focused tests, JSON, SVG, and audit report.

## Exact canonical reference

- Path: `data/reference/stopping_power/pstar_polystyrene.csv`
- Git blob: `7e953dd346caedcee6da54180fb636b890a64040`
- Bytes: 7,413
- SHA-256:
  `bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd`
- Rows: 141
- Identity: `total = electronic + nuclear`

## Validation

```text
python -m py_compile \
  scripts/single_stave/campaign_plots/_common.py \
  scripts/single_stave/campaign_plots/vis_mc_002_transport.py \
  tools/audit/validate_clusterd_pstar_binding.py \
  tests/test_clusterd_pstar_binding.py \
  tools/audit/render_clusterd_pstar_binding_evidence.py

PYTHONPATH=. pytest -q tests/test_clusterd_pstar_binding.py
5 passed in 2.08s
```

The exact 141-row reference and binding audit returned `VALIDATED` with zero
findings. Reintroduced embedded data, below-domain lookup, invalid UTF-8, and an
output/input alias failed closed. JSON and SVG parsing passed. Maximum changed
Python line length was 97 characters.

## Files and evidence

Updated:

- `scripts/single_stave/campaign_plots/_common.py`
- `reports/studies/clusterD/run_campaign_aggregation.sh`
- `reports/studies/clusterD/SUMMARY.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`

Added:

- `scripts/single_stave/campaign_plots/vis_mc_002_transport.py`
- `tools/audit/validate_clusterd_pstar_binding.py`
- `tests/test_clusterd_pstar_binding.py`
- `tools/audit/render_clusterd_pstar_binding_evidence.py`
- `docs/validation/clusterd_pstar_binding_validation.json`
- `docs/validation/clusterd_pstar_binding.svg`
- `docs/validation/clusterd_pstar_binding_audit.md`
- `chatgpt_todo/archive/2026-07-25T173220Z_AUD-CLD-002_PSTAR_BINDING.md`

## Direct-main sequence through delivery

- `dddd200a924ad6339a3bfc4626c88746efb2ba22` — task claim
- `20452fd4ad0bafac3e38783b05061de063798120` — campaign helper
- `00b34a197cc9664c0133b265979380387ff7f035` — dedicated renderer
- `624c0b666f3f19a3e85ab95b152db50463f464f1` — reproducer
- `096e6120e9223faf5a845a59d5f9312f9f8c3ddb` — summary quarantine
- `5715d134d3ae1452cfc8be02bc55b80dd543a0c5` — validator
- `ef70ec5ef33ca578162335bcb6e1288c2d75428e` — tests
- `46522c6d3c09e444309a0afed88ef3d5ae141850` — evidence renderer
- `87b565f76df34b96d10e4304ab86f117d6ceb305` — validation JSON
- `41790203b465fe9ad2fd79f575966828784db868` — SVG evidence
- `093688598dd837053db90d4f53891ad599d28d44` — audit report
- `2aca9f1c21149c649e75fb1b76e873f662617672` — immutable archive
- `bff941c6047ec589ded038d7afcb554b3abcb63c` — active completion
- `2a81915477741651fa08a5b7e754383a790e196a` — delivery handoff

## Scientific boundary and blockers

Focused software/reference migration is `VALIDATED`; cumulative work is
`PARTIAL`. No external i885 ROOT bytes were available, so the canonical campaign
PNG/JSON was not generated. Local deposited energy per scored track length is not
projectile total energy loss. No uncertainty budget, stopping-power closure,
deuteron result, calibration, or detector-performance claim is made.
`BLK-G4-SP-001` remains open.

A complete local clone was unavailable because the runtime could not resolve
`github.com`. Repository-wide pytest, ruff, Geant4 build/CTest, ROOT processing,
broad link checking, and GitHub Actions were not run; no broad CI success is
claimed.

## Mandatory coordination limitation

`ACTIVE_TASK.md`, this handoff, and the immutable archive were updated. Shared
aggregate files requiring byte-safe append or patch semantics (`SESSION_LOG.md`,
`MASTER_INDEX.md`, `BACKLOG.md`, `BLOCKERS.md`, `STUDY_REVIEW_LEDGER.md`,
`CLAIM_EVIDENCE_MATRIX.md`, `CODE_RESULT_MAP.md`, and `VISUALIZATION_MATRIX.md`)
were read but not replaced. Connector responses were paged/truncated and the
write API exposes whole-file replacement; replacing a partial reconstruction
could destroy unrelated or append-only provenance. This is an explicitly unmet
mandatory synchronization step.

## Next action

Run the dedicated renderer on immutable, content-addressed i885 ROOT inputs in a
complete current-main checkout. Record input hashes, environment, command,
counts, sufficient statistics, and generated PNG/JSON hashes, then review the
plot. Continue `AUD-G4-005` / `BLK-G4-SP-001` with an accepted projectile-loss
observable and preregistered uncertainty model.

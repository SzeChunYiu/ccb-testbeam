# AUD-CLD-002 — Cluster D VIS-MC-002 canonical PSTAR binding

- **Session:** 2026-07-25T173220Z
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `64c3841ccb522589e6866d835889e797ea342e24`
- **Focused status:** VALIDATED
- **Cumulative status:** PARTIAL
- **Policy:** `CLUSTERD_VIS_MC_002_MUST_USE_CANONICAL_VALIDATED_PSTAR_REFERENCE`

## Reviewed

Current main history and concurrency; open PRs and PR #868; Cluster D summary,
reproducer, campaign helper and VIS-MC diagnostics; canonical PSTAR CSV and
exact-decimal parser; `chatgpt_todo/` protocol, active task, handoff, backlog,
master index, blockers, and session log.

## Confirmed defect

The campaign helper carried a second coarse PSTAR table and the historical plot
claimed the canonical CSV was absent. Relative to the canonical total column,
the embedded values were high by 12.2222% at 10 MeV, 62.1622% at 50 MeV,
80.6723% at 100 MeV, and 82.7049% at 150 MeV. The historical plot also exposed
an unsupported chi-square while the plotted quantity remained a local deposited-
energy/track-length proxy with no complete uncertainty model.

## Validated changes

- `_common.py` now imports the canonical exact-decimal parser, removes the
  embedded table, uses `total_MeV_cm2_g`, the committed 1.060 g/cm3 density, log
  interpolation, and fail-closed reference-domain checks.
- `vis_mc_002_transport.py` records exact reference provenance, external input
  paths, exact-energy counts, deposited-energy and track-length sums,
  `RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED`, `MATH_FSUM_PER_EXACT_CONFIGURED_ENERGY`,
  plot bytes/SHA-256, no uncertainty evaluation, and no acceptance statistic.
- The Cluster D reproducer invokes the canonical renderer.
- The summary marks `VIS-MC-002_transport_vs_pstar.png` `SUPERSEDED` and names
  the canonical PNG/JSON outputs while retaining the diagnostic-only boundary.
- Added a fail-closed validator, focused tests, machine-readable evidence, SVG
  evidence, and a detailed audit report.

## Exact canonical reference

- Path: `data/reference/stopping_power/pstar_polystyrene.csv`
- Git blob: `7e953dd346caedcee6da54180fb636b890a64040`
- Bytes: 7,413
- SHA-256: `bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd`
- Rows: 141
- Identity: `total = electronic + nuclear`
- Parser version: 1.1.0

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

The exact 141-row reference and corrected binding returned `VALIDATED` with zero
findings. Reintroduced embedded data, below-domain lookup, invalid UTF-8, and an
output/input alias failed closed. JSON and SVG parsing passed. Maximum changed
Python line length was 97 characters.

## Direct-main commits before archive

- `dddd200a924ad6339a3bfc4626c88746efb2ba22` — claim task
- `20452fd4ad0bafac3e38783b05061de063798120` — canonical campaign helper
- `00b34a197cc9664c0133b265979380387ff7f035` — dedicated renderer
- `624c0b666f3f19a3e85ab95b152db50463f464f1` — reproduction path
- `096e6120e9223faf5a845a59d5f9312f9f8c3ddb` — summary quarantine
- `5715d134d3ae1452cfc8be02bc55b80dd543a0c5` — fail-closed audit
- `ef70ec5ef33ca578162335bcb6e1288c2d75428e` — focused tests
- `46522c6d3c09e444309a0afed88ef3d5ae141850` — evidence renderer
- `87b565f76df34b96d10e4304ab86f117d6ceb305` — validation JSON
- `41790203b465fe9ad2fd79f575966828784db868` — SVG evidence
- `093688598dd837053db90d4f53891ad599d28d44` — audit report

GitHub contents writes returned direct-main commit SHAs; conventional textual
`git push` output was not exposed.

## Scientific and execution boundary

No external i885 ROOT bytes were available. The canonical campaign PNG/JSON was
not regenerated. No projectile-energy-loss closure, uncertainty budget,
calibration, deuteron validation, or detector-performance result is claimed.
`BLK-G4-SP-001` remains open. A complete local clone was unavailable because the
runtime could not resolve `github.com`; repository-wide pytest, ruff, Geant4,
ROOT processing, broad link checking, and GitHub Actions were not run.

## Coordination limitation

`ACTIVE_TASK.md`, this immutable archive, and the latest handoff are updated.
Shared aggregate files requiring byte-safe append or patch semantics
(`SESSION_LOG.md`, `MASTER_INDEX.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate
matrices) were read but not replaced: connector responses were paged/truncated,
and whole-file replacement from a partial reconstruction could destroy unrelated
or append-only provenance. This is an unmet mandatory synchronization step, not
a claim that those records are current.

## Next action

Run the canonical renderer on content-addressed i885 ROOT files in a complete
current-main checkout. Retain run/input hashes, environment, command, generated
PNG/JSON hashes, counts, sufficient statistics, and diagnostic review. Then
continue `AUD-G4-005`/`BLK-G4-SP-001` with an accepted projectile-loss observable
and preregistered uncertainty model.

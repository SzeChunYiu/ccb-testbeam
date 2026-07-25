# Immutable handoff — AUD-CLD-001 Cluster D claim governance

## Identity

- Session: `2026-07-25T170507Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `5367ec7bbf5f37989cd29eedd0700bd77542049b`
- Source merge: PR #919 / `5367ec7bbf5f37989cd29eedd0700bd77542049b`
- Policy: `CLUSTERD_PUBLIC_STATUS_MUST_NOT_OVERRIDE_CANONICAL_CLAIM_GATES`
- Focused status: `VALIDATED`
- Cumulative status: `PARTIAL`

## Reviewed areas

- recent remote-main history and merged PR #919;
- open PR inventory and PR #868 disposition;
- `reports/studies/clusterD/SUMMARY.md`;
- Cluster D MV0, MV5, and MV6 reports and machine-readable results;
- Cluster D campaign plot helper and embedded PSTAR table;
- canonical `docs/claim_ledger.csv` rows CL-010 through CL-014 and CL-022;
- current `chatgpt_todo/ACTIVE_TASK.md`, `HANDOFF.md`, and session history;
- current combined-status metadata for the source merge.

PR #868 was closed, unmerged, non-mergeable, and untouched. No status checks were
attached to the source merge when inspected.

## Confirmed defects and corrections

### MV0

Merged wording said `PASS (PRODUCTION)` at 110 ADC/MeV. Exact source JSON records
KS `0.10773131550396098` and chi-square/ndf `2928.1720074390482`; per-stave KS
ranges from `0.19709479433376512` to `0.6026529124293721`. The source report itself
called the global result marginal and used external absolute-path inputs without a
content-addressed manifest.

Correction: `GATED (MARGINAL DATA/MC PROXY)`, with `BLK-MV0-001` retained. The new
scan does not supersede canonical CL-013/CL-014 or authorize a production gain.

### MV2

Merged wording said truth tables closed the data-side absolute-energy question.
Correction: `TRUTH_LEVEL_MC_ONLY / TABLE GENERATED`; beam-data energy calibration,
selection transfer, detector response, and uncertainty remain open.

### MV5

Merged wording treated `3.04 MHz` as an accepted Rmax. Exact source JSON records
`3.0448717948717947 MHz = (1/124.8 ns) × 0.38` and
`rmax_from_failure_ceiling_mhz = null`.

Correction: blocked/toy diagnostic. Canonical CL-010 withholds Rmax under
`S-STAT-003`; CL-012 classifies the duty-factor product as superseded.

### MV6

Merged wording transferred truth-MC composition to a concrete beam-data species
identity. Exact source JSON records 38 early-peak tracks, 25 C12-labelled, and GMM
cluster-3 C12 purity `0.464339908952959` with 1,280 normal versus 38 early-peak
tracks.

Correction: `TRUTH_LEVEL_MC_ONLY / TOY_DIAGNOSTIC`. The 25/38 composition is not a
beam-data purity, efficiency, or identity measurement; `AUD-ANOM-001` remains open.

### VIS-MC

Merged heading said the figures proved the simulation works. Several figures are
configuration checks or MC-internal closure by construction. VIS-MC-002 uses an
embedded coarse PSTAR table rather than the canonical committed CSV bytes/parser.

Correction: internal diagnostics with explicit acceptance boundaries.

## Files changed

Updated:

- `reports/studies/clusterD/SUMMARY.md`
- `reports/studies/clusterD/mv_runs/mv0/REPORT.md`
- `reports/studies/clusterD/mv_runs/mv5/REPORT.md`
- `reports/studies/clusterD/mv_runs/mv6/REPORT.md`
- `chatgpt_todo/ACTIVE_TASK.md`

Added:

- `tools/audit/validate_clusterd_claim_governance.py`
- `tests/test_validate_clusterd_claim_governance.py`
- `tools/audit/render_clusterd_claim_governance_evidence.py`
- `docs/validation/clusterd_claim_governance_validation.json`
- `docs/validation/clusterd_claim_governance.svg`
- `docs/validation/clusterd_claim_governance_audit.md`
- this immutable archive

## Validation

```text
python -m py_compile \
  tools/audit/validate_clusterd_claim_governance.py \
  tests/test_validate_clusterd_claim_governance.py

pytest -q tests/test_validate_clusterd_claim_governance.py

6 passed in 1.63s
```

The execution used an isolated repo-shaped fixture reconstructed from exact
corrected Markdown bytes and exact tracked values consumed by the validator.
Corrected status: `VALIDATED`, zero findings. Negative controls reintroduced the
merged overclaims, made the recovery-ceiling Rmax non-null, supplied invalid UTF-8,
and attempted destructive output aliasing; all failed closed. Atomic JSON output
and SVG XML parsing passed.

Exact corrected Markdown blobs match the fixture. The exact committed renderer
blob matches the locally compiled renderer. A full current-checkout integration
execution was not run because the container could not resolve `github.com`.

## Direct-main sequence before final handoff

- `f05971e9e889b3ef232fa84067da196eb39281ef` — Cluster D summary correction
- `f914bda5ffaa44a745022dab2fbf7ec6de65bee6` — MV0 correction
- `cb0f77baead16bf6b251e1d76a5a0d93e8836e28` — MV5 correction
- `76399bc6b92e227a86f174b04e6d3fdb92dc7c51` — MV6 correction
- `8011274a9ca26449e9d8e0936fb4a982b0d75b98` — validator
- `64ef6819010abc7857429bf16e4b64b0a9809702` — tests
- `18f6aabc2daf5f1e6c24e42eec3a199bfdc55f3b` — renderer
- `0c57fbaec26ffcaf545f9b4738a58714b66a0cf9` — validation JSON
- `73ac046414b9aac9910f64b763ee8b4d1c6d6b14` — SVG
- `090257c842f48fadb9ff9c28d3364431879c0328` — audit report
- `7c7fbb41dd30ede1bc543a404fb3d64e03583a0c` — active task

The connector returned a successful commit SHA for each direct-main contents write.
It does not expose conventional textual `git push` output.

## Checks not run

- full-checkout current-repository integration test;
- repository-wide pytest and ruff;
- ROOT/Geant4 or Cluster D script reruns;
- GitHub Actions acceptance;
- repository-wide broken-link inventory;
- independent reproduction of external ROOT, CSV, or NPZ inputs.

## Scientific boundary

No production calibration, absolute-energy closure, Rmax, PID transfer, anomaly
identity, Geant4/PSTAR closure, or detector-performance result was produced. This
run corrected public evidence classification and added a fail-closed governance
gate.

## Next work

1. content-address Cluster D external inputs and rerun the exact gate in a complete
   checkout;
2. resolve `BLK-MV0-001` with accepted observable/selection/uncertainty contracts;
3. resolve `S-STAT-003` with a preregistered Rmax definition;
4. execute matched data/MC anomaly closure under `AUD-ANOM-001`;
5. migrate VIS-MC-002 to the canonical PSTAR parser and committed reference bytes.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector exposes whole-file
replacement rather than byte-safe append/patch semantics, and the complete current
append-only content was returned only in truncated responses. Replacing a partial
reconstruction could erase unrelated provenance. This archive and the latest
`HANDOFF.md` are the append-equivalent record; mandatory aggregate synchronization
remains explicitly incomplete.

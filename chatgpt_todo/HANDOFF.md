# Latest Handoff — AUD-CLD-001 Cluster D claim governance

## Delivery identity

- **Session stamp:** `2026-07-25T170507Z`
- **Initial remote `main`:** `5367ec7bbf5f37989cd29eedd0700bd77542049b`
- **Validated implementation/evidence/archive head:**
  `6baa52245af439fc87f6b0ae3194a6ed26382d82`
- **Validated delivery handoff / after-SHA:**
  `fd3212db157efae56986ffa626257b73facdfb87`
- **Destination:** direct contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport
- **Push result:** every contents write returned a successful commit SHA; this
  confirmation write was based on the fetched delivery handoff blob, proving that
  remote `main` already contained `fd3212db157efae56986ffa626257b73facdfb87`
- **Focused remediation acceptance:** `VALIDATED`
- **Cumulative task status:** `PARTIAL`
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T170507Z_AUD-CLD-001_CLUSTERD_CLAIM_GOVERNANCE.md`

## Start-of-run state

The run fetched current `main` and found newly merged PR #919 at
`5367ec7bbf5f37989cd29eedd0700bd77542049b`. It reviewed the merge, recent
history, open PRs, PR #868, combined-status metadata, the Cluster D summary and
study outputs, campaign plot code, canonical claim ledger, and repository-local
handoff system.

PR #868 remains closed, unmerged, non-mergeable, and untouched. The source merge
had no attached status checks when inspected.

## Confirmed scientific-governance defects

### MV0 production claim

The merged summary called 110 ADC/MeV `PASS (PRODUCTION)`. Exact Cluster D output
records KS `0.10773131550396098`, chi-square/ndf `2928.1720074390482`, and per-
stave KS values from `0.19709479433376512` to `0.6026529124293721`. The report
itself called the global result marginal, compared data peak height with integrated
MC EDep×gain, and referenced external inputs without a content-addressed manifest.

The result is now labelled `GATED (MARGINAL DATA/MC PROXY)` and does not supersede
canonical CL-013/CL-014 or resolve `BLK-MV0-001`.

### MV2 absolute-energy closure claim

Truth-labelled MC range/energy tables were described as closing the data-side
absolute-energy question. They do not validate ADC-to-energy transfer, detector
response, trigger/selection transfer, or uncertainty. The summary now states
`TRUTH_LEVEL_MC_ONLY / TABLE GENERATED` and retains the open data-side problem.

### MV5 Rmax claim

The merged report said a toy study pinned Rmax near 3.04–3.05 MHz. Its JSON records
`3.0448717948717947 MHz = (1/124.8 ns)×0.38` and
`rmax_from_failure_ceiling_mhz = null`. Canonical CL-010 withholds Rmax under
`S-STAT-003`; CL-012 marks the duty-factor product superseded.

The report and summary now classify MV5 as blocked/toy diagnostic and do not
publish an accepted capacity.

### MV6 data-species identity claim

The merged report transferred truth-MC composition to a concrete beam-data
identity. Exact output contains 38 early-peak toy tracks, 25 C12-labelled, while
GMM cluster 3 is only `0.464339908952959` C12-labelled overall and contains 1,280
normal versus 38 early-peak tracks.

The report and summary now classify the result `TRUTH_LEVEL_MC_ONLY /
TOY_DIAGNOSTIC`. The 25/38 count is not a beam-data purity, efficiency, or species
measurement; `AUD-ANOM-001` remains open.

### VIS-MC proof language and PSTAR provenance

The heading “proving the sim works” overstated configuration checks and
MC-internal closure. VIS-MC-002 uses an embedded coarse PSTAR table rather than the
canonical committed CSV/parser. The summary now labels all figures internal
diagnostics and states their acceptance boundaries.

## Files changed

Updated:

- `reports/studies/clusterD/SUMMARY.md`
- `reports/studies/clusterD/mv_runs/mv0/REPORT.md`
- `reports/studies/clusterD/mv_runs/mv5/REPORT.md`
- `reports/studies/clusterD/mv_runs/mv6/REPORT.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this `HANDOFF.md`

Added:

- `tools/audit/validate_clusterd_claim_governance.py`
- `tests/test_validate_clusterd_claim_governance.py`
- `tools/audit/render_clusterd_claim_governance_evidence.py`
- `docs/validation/clusterd_claim_governance_validation.json`
- `docs/validation/clusterd_claim_governance.svg`
- `docs/validation/clusterd_claim_governance_audit.md`
- immutable archive listed above

## Validation

```text
python -m py_compile \
  tools/audit/validate_clusterd_claim_governance.py \
  tests/test_validate_clusterd_claim_governance.py

pytest -q tests/test_validate_clusterd_claim_governance.py

6 passed in 1.63s
```

This execution used an isolated repo-shaped fixture reconstructed from the exact
corrected Markdown bytes and exact tracked values consumed by the validator.
Corrected status was `VALIDATED` with zero findings. Reintroduced production/Rmax/
species-ID/“proving the sim” wording, a non-null recovery-ceiling Rmax, invalid
UTF-8, and output aliasing all failed closed. JSON and SVG parsing passed.

The corrected Markdown Git blobs are byte-identical to the validated fixture. The
committed renderer blob is byte-identical to the compiled renderer. Validator and
test blobs were re-fetched from `main`.

A complete-checkout execution of the current-repository integration test was not
run because the container could not resolve `github.com`. Repository-wide pytest,
ruff, ROOT/Geant4 reruns, link inventory, and broad CI are not claimed.

## Direct-main sequence

- `f05971e9e889b3ef232fa84067da196eb39281ef` — Cluster D summary correction
- `f914bda5ffaa44a745022dab2fbf7ec6de65bee6` — MV0 correction
- `cb0f77baead16bf6b251e1d76a5a0d93e8836e28` — MV5 correction
- `76399bc6b92e227a86f174b04e6d3fdb92dc7c51` — MV6 correction
- `8011274a9ca26449e9d8e0936fb4a982b0d75b98` — validator
- `64ef6819010abc7857429bf16e4b64b0a9809702` — tests
- `18f6aabc2daf5f1e6c24e42eec3a199bfdc55f3b` — renderer
- `0c57fbaec26ffcaf545f9b4738a58714b66a0cf9` — validation JSON
- `73ac046414b9aac9910f64b763ee8b4d1c6d6b14` — SVG evidence
- `090257c842f48fadb9ff9c28d3364431879c0328` — audit report
- `7c7fbb41dd30ede1bc543a404fb3d64e03583a0c` — active task
- `6baa52245af439fc87f6b0ae3194a6ed26382d82` — immutable archive
- `fd3212db157efae56986ffa626257b73facdfb87` — delivery handoff

The connector returned a successful direct-main commit SHA for each contents write
rather than conventional textual `git push` output. Fetching the handoff blob after
that write confirmed the delivery commit on remote `main`.

## Scientific boundary

No production calibration, absolute-energy closure, Rmax, PID transfer, anomaly
identity, stopping-power closure, or detector-performance result was generated.
This run corrected evidence classification and added a fail-closed claim gate.

## Open blockers and next work

1. content-address the external Cluster D ROOT/CSV/NPZ inputs and run the gate in a
   complete checkout;
2. resolve `BLK-MV0-001` with accepted observable, selection, and uncertainty
   contracts;
3. resolve `S-STAT-003` with a preregistered Rmax definition and uncertainty;
4. execute matched data/MC anomaly closure under `AUD-ANOM-001`;
5. migrate VIS-MC-002 to the canonical PSTAR parser and committed reference bytes.

## Coordination boundary

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector provides whole-file
replacement rather than byte-safe append/patch semantics, while the complete
append-only content was available only through truncated responses. Replacing a
partial reconstruction could erase unrelated provenance. The immutable archive
and this handoff are the append-equivalent record; mandatory aggregate
synchronization remains explicitly incomplete.

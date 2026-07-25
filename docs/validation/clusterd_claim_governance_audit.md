# Cluster D scientific-claim governance audit

- **Task:** `AUD-CLD-001`
- **Session:** `2026-07-25T170507Z`
- **Initial remote main:** `5367ec7bbf5f37989cd29eedd0700bd77542049b`
- **Source merge:** PR #919 / merge commit `5367ec7bbf5f37989cd29eedd0700bd77542049b`
- **Policy:** `CLUSTERD_PUBLIC_STATUS_MUST_NOT_OVERRIDE_CANONICAL_CLAIM_GATES`
- **Focused status:** `VALIDATED`
- **Scientific scope:** documentation and source-binding validation only

## Trigger

PR #919 merged a large regenerated MC-validation and campaign-aggregation bundle.
Its headline status table and three study reports used stronger scientific language
than the tracked evidence and canonical claim ledger support. Script exit status,
truth-labelled simulation composition, and analytic/toy self-closure were presented
as production calibration, accepted capacity, data species identity, or proof that
the simulation works.

No evidence was found that the merge changed the canonical ledger. The defect was
therefore a new public-documentation conflict with existing claim governance.

## Exact conflicts

### MV0

The merged summary labelled 110 ADC/MeV `PASS (PRODUCTION)`. The tracked Cluster D
`calibration.json` records:

- gain `110.0 ADC/MeV`;
- KS statistic `0.10773131550396098`;
- chi-square per degree of freedom `2928.1720074390482`;
- per-stave KS values from `0.19709479433376512` to `0.6026529124293721`.

The associated report itself classified the global KS result as `MARGINAL`, noted
that data peak height was compared with integrated MC EDep times gain, and used
absolute-path external inputs without a content-addressed run manifest. Canonical
`CL-013` remains a distinct 92 ADC/MeV data/MC proxy with status `GATED` under
`BLK-MV0-001`; canonical `CL-014` remains a `TENSION` record.

**Correction:** retain the new scan result as a source-specific marginal diagnostic,
not an authorized production calibration and not a supersession of `CL-013`.

### MV2

The merged summary said the truth tables closed the data-side absolute-energy
question. Truth-labelled MC range/EDep/track-length tables do not establish the
beam-data ADC-to-energy conversion, trigger/selection transfer, detector response,
or uncertainty.

**Correction:** classify as `TRUTH_LEVEL_MC_ONLY / TABLE GENERATED` and state that
the data-side absolute-energy problem remains open.

### MV5

The merged report said the toy study “pins Rmax” and treated 3.04–3.05 MHz as an
accepted capacity. Its exact JSON records:

- rounded input `tau_eff_new_ns = 124.8`;
- duty factor `0.38`;
- arithmetic product `3.0448717948717947 MHz`;
- `rmax_from_failure_ceiling_mhz = null`.

Thus no recovery-failure ceiling is crossed. Canonical `CL-010` withholds Rmax
under `S-STAT-003`; `CL-012` classifies 3.0448717948717947 MHz as superseded duty-
factor arithmetic. MV5 also reuses the S10b value rather than independently
validating it.

**Correction:** classify MV5 as blocked/toy diagnostic, preserve the arithmetic for
provenance, and explicitly withhold Rmax.

### MV6

The merged report said truth-labelled MC assigned a concrete particle identity to
the data anomaly. Its exact new JSON records:

- 7,848 toy MC tracks;
- 38 early-peak tracks;
- 25/38 C12-labelled early-peak tracks;
- GMM cluster 3 C12 purity `0.464339908952959` and 1,280 normal tracks versus 38
  early-peak tracks.

These counts describe a small toy-MC-defined morphology class. They do not measure
beam-data classifier efficiency, purity, false-positive rate, or species identity.
They also do not supersede canonical `CL-022`–`CL-024`, which refer to a different
87,555-track source run.

**Correction:** classify as `TRUTH_LEVEL_MC_ONLY / TOY_DIAGNOSTIC`; retain 25/38 as
truth-MC composition only; require matched data/MC closure under `AUD-ANOM-001`.

### VIS-MC and PSTAR

The merged heading “proving the sim works” was not supported. Several plots are
configuration checks or MC-internal closure by construction. VIS-MC-002 uses an
embedded coarse `PSTAR_POLYSTYRENE` table in `_common.py`, rather than the canonical
committed CSV bytes and strict parser introduced elsewhere in the repository.

**Correction:** label the figures internal diagnostics and explicitly state their
acceptance boundaries.

## Remediation

Updated:

- `reports/studies/clusterD/SUMMARY.md`
- `reports/studies/clusterD/mv_runs/mv0/REPORT.md`
- `reports/studies/clusterD/mv_runs/mv5/REPORT.md`
- `reports/studies/clusterD/mv_runs/mv6/REPORT.md`

Added:

- `tools/audit/validate_clusterd_claim_governance.py`
- `tests/test_validate_clusterd_claim_governance.py`
- `tools/audit/render_clusterd_claim_governance_evidence.py`
- `docs/validation/clusterd_claim_governance_validation.json`
- `docs/validation/clusterd_claim_governance.svg`
- this audit report

The validator binds public status wording to exact source JSON values and to the
43-column canonical records `CL-010`, `CL-011`, `CL-012`, `CL-013`, `CL-014`, and
`CL-022`. It uses strict UTF-8 single-read snapshots, records SHA-256 provenance,
rejects duplicate or malformed selected ledger rows, publishes JSON atomically,
and rejects destructive input/output aliasing.

## Validation

Executed in an isolated repo-shaped fixture reconstructed from the exact corrected
Markdown bytes and the exact tracked values consumed by the validator:

```text
python -m py_compile \
  tools/audit/validate_clusterd_claim_governance.py \
  tests/test_validate_clusterd_claim_governance.py

pytest -q tests/test_validate_clusterd_claim_governance.py

6 passed in 1.63s
```

Validated controls:

- corrected fixture: `VALIDATED`, zero findings;
- reintroduced production/Rmax/species-ID/“proving the sim” wording: `FLAWED`;
- non-null recovery-ceiling Rmax: `FLAWED`;
- invalid UTF-8: controlled status 2;
- output aliasing: rejected;
- JSON publication: atomic.

The exact corrected Markdown Git blobs match the bytes used by the fixture. The
committed renderer blob matches the locally compiled renderer and generated an SVG
that parsed successfully. Validator/test Git blobs were re-fetched from `main`.

A complete checkout execution of `test_current_repository_validates` was not run:
the execution container could not resolve `github.com`. Repository-wide pytest,
ruff, ROOT/Geant4 execution, the full link inventory, and GitHub Actions are not
claimed.

## Direct-main sequence through evidence generation

- `f05971e9e889b3ef232fa84067da196eb39281ef` — gate Cluster D summary claims
- `f914bda5ffaa44a745022dab2fbf7ec6de65bee6` — demote MV0 to gated proxy
- `cb0f77baead16bf6b251e1d76a5a0d93e8836e28` — block toy Rmax overclaim
- `76399bc6b92e227a86f174b04e6d3fdb92dc7c51` — demote MV6 to truth MC
- `8011274a9ca26449e9d8e0936fb4a982b0d75b98` — add fail-closed validator
- `64ef6819010abc7857429bf16e4b64b0a9809702` — add focused tests
- `18f6aabc2daf5f1e6c24e42eec3a199bfdc55f3b` — add evidence renderer
- `0c57fbaec26ffcaf545f9b4738a58714b66a0cf9` — add validation JSON
- `73ac046414b9aac9910f64b763ee8b4d1c6d6b14` — add SVG evidence

The GitHub contents API returned a successful commit SHA for every direct-main
write. Conventional `git push` stdout is unavailable through this connector.

## Scientific boundary and next work

This correction does not choose a production gain, close absolute energy, define
Rmax, identify the beam-data anomaly, validate PID transfer, validate Geant4/PSTAR
agreement, or reproduce the external campaign files.

Next high-priority work:

1. content-address the external ROOT/CSV/NPZ inputs and rerun the gate in a complete
   checkout;
2. resolve `BLK-MV0-001` with an accepted observable and uncertainty model;
3. resolve `S-STAT-003` with a preregistered capacity definition;
4. execute the matched anomaly closure required by `AUD-ANOM-001`;
5. migrate VIS-MC-002 to the canonical committed PSTAR parser and reference bytes.

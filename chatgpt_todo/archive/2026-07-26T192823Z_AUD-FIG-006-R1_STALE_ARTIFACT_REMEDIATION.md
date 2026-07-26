# AUD-FIG-006-R1 — stale managed-artifact remediation

## Session

- Stamp: `2026-07-26T192823Z`
- Owner: scheduled scientific-review session
- Initial remote main: `cbc5ef1cc194ae976ffb05a0f7a2305ec8428088`
- Policy: `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`
- Acceptance: focused software/provenance remediation `VALIDATED / COMPLETE`

## Defect and correction

`AUD-FIG-006` demonstrated that a prior canonical PNG or source-data CSV could survive when an entry became BLOCKED/QUARANTINED, failed, changed kind or suffix, or disappeared. The corrected builder records a complete per-entry `managed_artifacts` inventory, reconciles the previous report against the current registry, removes obsolete outputs for every non-PASS lifecycle, rejects unsafe IDs/paths/symlinks, and rolls the entire managed artifact set back when final report publication fails.

Deterministic transitions:

- PASS to BLOCKED: 2 prior files, 0 remaining;
- PASS to FAIL: 2 prior files, 0 remaining;
- removed entry: 2 prior files, 0 remaining;
- `.png` to `.pdf`: 1 obsolete artifact, 0 obsolete remaining;
- injected report failure: prior PNG, CSV, and report restored byte-for-byte;
- external prior-report path and `../ESCAPE` ID: rejected without external deletion.

## Validation

```text
python -m py_compile \
  tools/figure_registry/builder.py \
  tools/figure_registry/registry.py \
  tests/test_figure_registry_stale_artifact_remediation.py \
  tests/test_figure_registry_quantitative_publication_remediation.py

PYTHONPATH=. pytest -q \
  tests/test_figure_registry.py \
  tests/test_figure_registry_snapshot_remediation.py \
  tests/test_figure_registry_quantitative_publication_remediation.py \
  tests/test_figure_registry_duplicate_keys.py \
  tests/test_figure_registry_build_report_provenance.py \
  tests/test_figure_registry_stale_artifact_remediation.py

37 passed in 1.16s
```

The lifecycle regressions alone returned `9 passed in 0.81s`. Exact-source stale-artifact audit: `VALIDATED`, zero findings. JSON and SVG parsing passed. Maximum changed Python line length: 96.

Remote Git blobs:

- builder: `6f2b8066799f045fe8c3a05549139c871a2ef27e`
- registry: `c64bf734b244a114ea7d5f259b32421cd59aaa25`
- lifecycle tests: `38591487747c3881052a5c30932afda1d0997fc5`
- updated quantitative-publication tests: `1ac7fa4b8fafa6f3bffc742f8c95163775c25f82`

The container could not resolve `github.com`; validation used connector-inspected source reconstructions and the remote blob identities above.

## Direct-main sequence through evidence

- `48bfc1a87f77673c7ebac55d179c66bdd4cc6b39` — task claim
- `2628034e78a54a076d0032d814b746fa520283dd` — safe output IDs
- `136793fbbb085c32db8fbe966aa84acd59b5af82` — managed-artifact reconciliation
- `adcb5add0cd6638cfb5e3db865c08f35a96e8fab` — publication lifecycle test alignment
- `396c3bd5e8da0712b999f1e5ab00e6af02e1161e` — direct lifecycle regressions
- `90c66495d3c26afcc350560398cfa076348076dd` — evidence renderer
- `2aa6625d239729d78d4f7e415ae3213781dcbf35` — validation JSON
- `349ee591950631cd3fcdc26788609be086027b2c` — SVG evidence
- `a12164706f7b8a9ad98824107cff6cdabd64c87a` — audit report

Concurrent merges `fa5b063...` and `81470c3...` were inspected and did not modify the figure-registry area.

## Scientific boundary and next risk

No paper figure or scientific result was regenerated. Repository-wide pytest/ruff, complete registry build, paper build, link inventory, and GitHub Actions were not run.

A separate urgent review is required for the concurrent `scripts/check_rmax_formula.py` change: it calls 3.05 MHz “measured (occupancy)” while occupancy alone does not identify absolute rate without exposure, and it prints PASS before exiting status 1.

`SESSION_LOG.md` and long aggregate matrices still require a byte-safe coordinated append/update. They were not partially reconstructed in this archive commit.

# Figure-registry stale managed-artifact remediation

## Scope

Task `AUD-FIG-006-R1` remediates the software/provenance defect identified by `AUD-FIG-006`: an older canonical PNG or source-data CSV could survive after a registry entry became non-authorizing, failed, changed output kind/suffix, or disappeared.

Policy: `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`.

## Corrected contract

The builder now treats `build_report.json` as the prior managed-output manifest when it exists. Every PASS record contains a normalized `managed_artifacts` list. Before a new build, the builder snapshots all prior and currently expected managed paths. It then:

- removes prior outputs for BLOCKED, QUARANTINED, and excluded PRELIMINARY entries;
- removes prior and partial outputs for per-entry failures before publishing a FAIL record;
- reconciles IDs absent from the current registry;
- removes obsolete paths after kind or suffix changes;
- refuses prior-report paths outside the output directory, noncanonical paths, symbolic links, and nonregular managed targets;
- rejects unsafe registry IDs before path construction;
- preserves declared result, table, and source-artifact inputs when an input aliases a canonical target;
- restores the complete pre-build managed-artifact byte state if final report publication fails.

When no prior report exists, only exact canonical paths for current entries are adopted. An unattributable candidate fails closed rather than being guessed or deleted.

## Deterministic controls

| Transition | Prior canonical files | Files remaining after corrected build |
|---|---:|---:|
| PASS to BLOCKED | 2 | 0 |
| PASS to FAIL | 2 | 0 |
| Entry removed | 2 | 0 |
| Source suffix `.png` to `.pdf` | 1 obsolete | 0 obsolete |

An injected final-report publication failure restored the prior PNG and source-data CSV byte-for-byte and preserved the prior atomic report. A malicious prior-report path outside the output root and an unsafe `../ESCAPE` registry ID were rejected without deleting external files.

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

The new lifecycle file alone returned `9 passed in 0.81s`. The exact-source stale-artifact auditor returned `VALIDATED` with zero findings. The validation JSON parsed and the deterministic SVG parsed as XML. Changed Python lines are at most 96 characters.

The execution container could not resolve `github.com`; validation used connector-inspected source reconstructions and the exact remote Git blob identities recorded in the validation JSON. Two concurrent merges, `fa5b063...` and `81470c3...`, were inspected and did not modify the figure-registry implementation or tests.

## Scientific boundary

This is a software and artifact-provenance remediation. No paper figure, central value, uncertainty, calibration, timing result, PID result, stopping profile, pile-up rate, or detector-performance quantity was regenerated or accepted. The full shipped-registry build, repository-wide pytest and ruff, paper build, link inventory, and GitHub Actions were not run.

A separate urgent review remains for `scripts/check_rmax_formula.py`: the concurrent change calls 3.05 MHz “measured (occupancy)” and prints PASS while exiting with status 1. Occupancy alone does not identify an absolute rate without exposure; this was not modified in the focused figure-lifecycle task.

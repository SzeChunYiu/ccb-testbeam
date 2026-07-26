# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-006-R1`
- **Stamp:** `2026-07-26T192823Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `cbc5ef1cc194ae976ffb05a0f7a2305ec8428088`
- **Validated implementation/evidence/archive/active-task head:** `de161472fc37b54f66ff99ca1e953f1dc56a32d5`
- **Destination:** authenticated sequential commits directly to `main`; no force-push, transport branch, pull-request merge, or history rewrite.
- **Push result:** each GitHub contents write returned a successful commit SHA. Post-write remote history showed the complete focused sequence on `main`; concurrent merges `fa5b063...` and `81470c3...` landed after the task claim but before implementation and did not touch figure-registry files.
- **Acceptance:** focused software/provenance remediation `VALIDATED / COMPLETE`.

## Defect and policy

Policy: `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`.

The prior builder could leave an older canonical PNG or source-data CSV after an entry became BLOCKED/QUARANTINED, failed, changed output kind or suffix, or disappeared. A current report could therefore say non-PASS while an older paper artifact remained at the canonical path.

## Remediation

The builder now:

- publishes a complete normalized `managed_artifacts` list for every PASS entry;
- reads the prior `build_report.json` as the authoritative managed-output manifest;
- reconciles IDs removed from the current registry;
- removes outputs before BLOCKED, QUARANTINED, excluded PRELIMINARY, and FAIL records;
- removes obsolete prior paths after kind/suffix changes;
- adopts only exact current canonical paths when no previous report exists and fails closed on unattributable candidates;
- rejects unsafe entry IDs, output-root escape, noncanonical prior paths, symbolic links, and nonregular targets;
- protects declared result/table/source inputs from cleanup aliasing;
- snapshots the complete managed set and restores exact prior bytes if final report publication fails.

Managed-artifact policy recorded in reports:

`PREVIOUS_REPORT_RECONCILIATION_NONPASS_REMOVAL_REPORT_ROLLBACK`.

## Reproducible controls

- PASS to BLOCKED: two prior files, zero remaining.
- PASS to FAIL: two prior files, zero remaining.
- removed ID: two prior files, zero remaining.
- source suffix `.png` to `.pdf`: one obsolete artifact, zero obsolete remaining.
- injected final-report failure: prior PNG, source-data CSV, and report restored byte-for-byte.
- malicious outside prior-report path: rejected without external deletion.
- unsafe `../ESCAPE` registry ID: rejected before output construction.

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

Focused lifecycle regressions: `9 passed in 0.81s`. Exact-source stale-artifact audit: `VALIDATED`, zero findings. JSON and SVG parsing passed. Maximum changed Python line length: 96.

The execution container could not resolve `github.com`; validation used connector-inspected source reconstructions and exact remote Git blob identities.

## Files and identities

- `tools/figure_registry/builder.py` — Git blob `6f2b8066799f045fe8c3a05549139c871a2ef27e`
- `tools/figure_registry/registry.py` — Git blob `c64bf734b244a114ea7d5f259b32421cd59aaa25`
- `tests/test_figure_registry_stale_artifact_remediation.py` — Git blob `38591487747c3881052a5c30932afda1d0997fc5`
- `tests/test_figure_registry_quantitative_publication_remediation.py` — Git blob `1ac7fa4b8fafa6f3bffc742f8c95163775c25f82`
- validation JSON SHA-256 `902ad0d667a59ad23d48807c5500675d30cee4aa118e28156e97dad16caa6524`
- SVG SHA-256 `a27c796033d146b443f8516d92bc9a189a5923c6a5af5d8165680168661c2406`
- immutable record: `chatgpt_todo/archive/2026-07-26T192823Z_AUD-FIG-006-R1_STALE_ARTIFACT_REMEDIATION.md`

## Direct-main sequence

- `48bfc1a87f77673c7ebac55d179c66bdd4cc6b39` — task claim
- `2628034e78a54a076d0032d814b746fa520283dd` — safe output IDs
- `136793fbbb085c32db8fbe966aa84acd59b5af82` — managed-artifact reconciliation
- `adcb5add0cd6638cfb5e3db865c08f35a96e8fab` — publication lifecycle test alignment
- `396c3bd5e8da0712b999f1e5ab00e6af02e1161e` — lifecycle regressions
- `90c66495d3c26afcc350560398cfa076348076dd` — evidence renderer
- `2aa6625d239729d78d4f7e415ae3213781dcbf35` — validation JSON
- `349ee591950631cd3fcdc26788609be086027b2c` — SVG evidence
- `a12164706f7b8a9ad98824107cff6cdabd64c87a` — audit report
- `fca7cbc36df5c9e5e76f4ac95237033fe3028231` — immutable archive
- `de161472fc37b54f66ff99ca1e953f1dc56a32d5` — active-task completion

## Scientific boundary and unresolved risks

No paper figure, central value, uncertainty, calibration, timing result, PID result, stopping profile, pile-up rate, or detector-performance quantity was regenerated or accepted. Repository-wide pytest/ruff, the complete shipped-registry build, paper build, link inventory, and GitHub Actions were not run.

A separate urgent audit is required for the concurrent `scripts/check_rmax_formula.py` change: it describes 3.05 MHz as “measured (occupancy)” despite the unresolved exposure/rate-identifiability boundary and prints PASS before exiting with status 1.

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and long aggregate matrices were reviewed but not rewritten in this focused unit. Connector reads are paged while updates replace complete files; the immutable archive retains the append-equivalent record without risking historical provenance loss.

# Immutable handoff — AUD-FIG-005

## Session identity

- Stamp: `2026-07-26T170400Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `03851ff128a5a351f39c7754e47ac35fe80e0fa0`
- Validated implementation/test head: `bd81bce0fa0714f7473ae946db221e3bbdb918a5`
- Evidence head before archive: `e457f071796ca62cd68ac567354a72bbad1ba3ec`
- Policy: `FIGURE_BUILD_REPORT_MUST_BIND_TO_EXACT_REGISTRY_SNAPSHOT`
- Acceptance: `VALIDATED / COMPLETE` for the focused software/provenance unit.

## Reviewed area

`tools/figure_registry/registry.py`, `tools/figure_registry/builder.py`, package exports, duplicate-key regressions, prior validation evidence, current handoff, backlog, blockers, recent remote-main history, open PR #939, closed PR #868, and current-main status checks.

## Confirmed defect

The registry loader already created a content-addressed `RegistrySnapshot`, but the builder discarded that identity by calling `load_registry(path)` and wrote only a path string to `build_report.json`. A report therefore did not prove which exact registry bytes authorized its entries. `RegistryFormatError` also bypassed the CLI's `FigureRegistryError` catch.

## Delivered remediation

- Builder calls `load_registry_snapshot` once and derives entries from that snapshot.
- Every valid or structurally invalid report records registry path, SHA-256, byte count, snapshot method, and entry count.
- Duplicate-key, invalid-UTF8, malformed-YAML, and unreadable-registry failures are wrapped as controlled `FigureRegistryError` diagnostics.
- Format-invalid input emits no misleading build report.
- Existing top-level `registry` path remains for compatibility.

## Validation

```text
python -m py_compile \
  tools/figure_registry/registry.py \
  tools/figure_registry/builder.py \
  tests/test_figure_registry_duplicate_keys.py \
  tests/test_figure_registry_build_report_provenance.py

PYTHONPATH=. pytest -q \
  tests/test_figure_registry_duplicate_keys.py \
  tests/test_figure_registry_build_report_provenance.py

12 passed in 0.28s
```

Environment: Python 3.13.5, pytest 9.0.2, Matplotlib 3.10.8, PyYAML 6.0.3.

Exact published identities:

- builder blob `39dcd3b13d3886c43f3e9111291d420f86cc7c85`, 18,264 bytes, SHA-256 `78feca87c3693f4ccabc319043531b7b6b5d767f4270471d3d939a258d75ae76`;
- focused-test blob `f242097b78f812327f846e942b8eb0f589675d4b`, 4,779 bytes, SHA-256 `486abf6a3f7eabb4f4883515c3a9ac61db0a9f79ef0419a754486468cdfab046`;
- renderer blob `da2b4b44d067f7ebefd9aa058a5b3de9ecc9f54d`;
- maximum changed Python line length 93 for implementation/tests and 99 for renderer;
- validation JSON parsed and SVG parsed as XML.

Controls: exact 76-byte registry binding; replacement-after-snapshot stability; controlled duplicate-key and invalid-UTF8 CLI failures; structurally invalid report retaining exact provenance; one registry-path read during a quarantined build.

## Direct-main sequence through evidence

- `d28b9ecb08df895f23c4585e120f01a07ec8b283` — task claim
- `db1a05a5ce9003cd45e10df4f247c55733a06dc2` — implementation
- `bd81bce0fa0714f7473ae946db221e3bbdb918a5` — focused regressions
- `e021d194cd43c3efabe97d9d81293b69d464b5c2` — renderer
- `e95a05eda5330053a3a54d931f953723e5c81418` — validation JSON
- `fc3c6f3dbd9e69da59fc098f8be7455d55c287e3` — SVG evidence
- `e457f071796ca62cd68ac567354a72bbad1ba3ec` — audit report

## Scientific boundary and unrun checks

No registry entry, source result, paper figure, central value, uncertainty, calibration, timing result, PID result, stopping profile, pile-up rate, or detector-performance claim was revalidated or changed. Repository-wide pytest/ruff, complete shipped-registry build, paper build, link inventory, and GitHub Actions were not run. No status checks were attached to the initial or implementation head when inspected.

`SESSION_LOG.md` and long aggregate matrices were not partially reconstructed: connector reads are paged/truncated while writes replace the complete file, so a transcription-based append could erase unrelated provenance. This archive is the append-equivalent record and the limitation remains open.

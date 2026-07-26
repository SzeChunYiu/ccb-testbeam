# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-005`
- **Stamp:** `2026-07-26T170400Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `03851ff128a5a351f39c7754e47ac35fe80e0fa0`
- **Validated implementation/test head:** `bd81bce0fa0714f7473ae946db221e3bbdb918a5`
- **Validated evidence/archive/active-task head:** `987eea3cb0e5a0efd5259a1b216ca0467781cc01`
- **Destination:** authenticated sequential commits directly to `main`; no force-push or history rewrite.
- **Push result:** GitHub contents writes returned successful commit SHAs. Post-write history confirmed all focused files through `987eea3cb0e5a0efd5259a1b216ca0467781cc01` on remote `main`.
- **Acceptance:** focused software/provenance remediation `VALIDATED / COMPLETE`.

## Defect and remediation

Policy: `FIGURE_BUILD_REPORT_MUST_BIND_TO_EXACT_REGISTRY_SNAPSHOT`.

The builder previously discarded the exact `RegistrySnapshot` identity and wrote only a registry path to `build_report.json`. Registry parsing errors also bypassed the controlled CLI error boundary.

The builder now reads the registry once through `load_registry_snapshot`, derives entries from those retained bytes, records path/SHA-256/byte count/snapshot method/entry count in every valid or structurally invalid report, preserves the compatibility path field, and converts registry-format failures to one controlled `FigureRegistryError` diagnostic without a traceback. Format-invalid input does not produce a misleading report.

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

- Builder blob: `39dcd3b13d3886c43f3e9111291d420f86cc7c85`; SHA-256 `78feca87c3693f4ccabc319043531b7b6b5d767f4270471d3d939a258d75ae76`; 18,264 bytes.
- Test blob: `f242097b78f812327f846e942b8eb0f589675d4b`; SHA-256 `486abf6a3f7eabb4f4883515c3a9ac61db0a9f79ef0419a754486468cdfab046`; 4,779 bytes.
- Renderer blob: `da2b4b44d067f7ebefd9aa058a5b3de9ecc9f54d`.
- Exact snapshot, path-replacement, duplicate-key, invalid-UTF8, structural-invalid, and one-read controls passed.
- Validation JSON and SVG parsed successfully.

## Direct-main sequence

- `d28b9ecb08df895f23c4585e120f01a07ec8b283` — task claim
- `db1a05a5ce9003cd45e10df4f247c55733a06dc2` — implementation
- `bd81bce0fa0714f7473ae946db221e3bbdb918a5` — regressions
- `e021d194cd43c3efabe97d9d81293b69d464b5c2` — renderer
- `e95a05eda5330053a3a54d931f953723e5c81418` — JSON evidence
- `fc3c6f3dbd9e69da59fc098f8be7455d55c287e3` — SVG evidence
- `e457f071796ca62cd68ac567354a72bbad1ba3ec` — audit report
- `d3b126961d32291f3756dfe3a1f4614e8f15815c` — immutable archive
- `987eea3cb0e5a0efd5259a1b216ca0467781cc01` — completed active task

## Scientific boundary and limitations

No registry entry, paper figure, numerical result, uncertainty, calibration, timing, PID, stopping profile, pile-up rate, or detector-performance claim was revalidated. Repository-wide pytest/ruff, complete registry build, paper build, link inventory, and GitHub Actions were not run.

`SESSION_LOG.md` and the long aggregate ledgers were not partially reconstructed because connector reads are paged while writes replace whole files. The immutable archive is the append-equivalent record; this required synchronization gap remains explicit.

## Next action

Run the complete shipped registry and paper build in a clean checkout, then audit content-addressed consistency of report paths, source-data paths, and generated artifacts.

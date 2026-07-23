# Reports & build-artifact hygiene (REP-002)

Generated analysis reports and publication-figure builds are **derived artifacts**:
they are fully rebuildable from the committed source under `scripts/`, `src/`, and
`tools/`, and their raw inputs are documented in [`DATA.md`](DATA.md). They must
**not** be committed to the repository.

## Rule

- **Do not** `git add` generated report directories or rendered figure bundles.
- The `.gitignore` entries below block the outputs of the in-scope generator
  scripts so they cannot be staged accidentally. Mass-deleting already-tracked
  artifacts is explicitly **out of scope** for this change; this note only
  prevents *new* generated outputs from entering the tree.
- When a study is regenerated, write its output under `reports/<study>/` (or
  `paper/figures/` for publication figures) and leave it on the local filesystem
  / shared scratch only.

## Currently blocked paths (see `.gitignore`)

| Pattern | Producer |
|---|---|
| `/reports/data01_sample_split*/` | `scripts/data01_sample_split_staves.py` |
| `/reports/mv3_stopping_v2*/` | `scripts/mv3_stopping_v2.py` |
| `/reports/mv3_stopping_v3*/` | `scripts/mv3_stopping_v3.py` |
| `/paper/figures/` | `scripts/generate_all.py` / `tools.figure_registry.builder` |

## Publication figures

Publication figures are produced through the canonical, sha256-gated registry
driver (`tools.figure_registry.builder` with `paper/figures.yaml`) and written
to `paper/figures/`. Quantitative values are read from validated result bundles
only — never from in-source literals (see
[`src/ccb_figures/figures/fig20_key_results.py`](src/ccb_figures/figures/fig20_key_results.py)
and `tests/test_fig20_no_quantitative_literals.py`).

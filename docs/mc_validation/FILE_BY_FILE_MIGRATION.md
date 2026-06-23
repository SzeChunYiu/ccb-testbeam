# MC Validation — File-by-File Migration Map

Instruction-pack targets mapped to repository paths created for the MC validation program.

| Instruction pack | Repository path | Notes |
| --- | --- | --- |
| reporting/style.py | `src/ccb_mc_validation/reporting/style.py` | `apply_scientific_style()`, colorblind palette |
| reporting/primitives.py | `src/ccb_mc_validation/reporting/primitives.py` | `save_figure()` + JSON sidecar |
| reporting/comparison.py | `src/ccb_mc_validation/reporting/comparison.py` | `ratio_panel()`, `pull_panel()` |
| reporting/figures.py | `src/ccb_mc_validation/reporting/figures.py` | `FigureRecord`, `register_figure()` |
| reporting/registry.py | `src/ccb_mc_validation/reporting/registry.py` | `ResultRegistry` JSON load/save |
| reporting/renderer.py | `src/ccb_mc_validation/reporting/renderer.py` | `render_mv_report()` |
| reporting/tables.py | `src/ccb_mc_validation/reporting/tables.py` | `metrics_to_markdown_table()` |
| reporting/diagrams.py | `src/ccb_mc_validation/reporting/diagrams.py` | `program_dag_mermaid()` |
| reporting/captions.py | `src/ccb_mc_validation/reporting/captions.py` | `validate_caption()` |
| reporting/diagnostics.py | `src/ccb_mc_validation/reporting/diagnostics.py` | `lint_report()` |
| report template | `templates/mc_validation/report.md.j2` | `string.Template` syntax |
| style config | `configs/mc_validation/reporting/style.yaml` | Figure defaults |
| figure catalog | `configs/mc_validation/reporting/figure_catalog.yaml` | Minimal figure IDs |
| LUNARC site overlay | `configs/mc_validation/sites/lunarc.example.yaml` | `${CCB_MC_*}` env paths |
| SLURM MV0–MV5 | `geant4/jobs/mv*.sbatch` | `${CCB_MC_PYTHON:-python3}` prologue |
| SLURM pipeline | `geant4/jobs/mc_validation_pipeline.sbatch` | End-to-end orchestration |
| CI workflow | `.github/workflows/mc_validation_ci.yml` | pytest on push |
| config tests | `tests/test_config.py` | base.yaml + unknown-key rejection |
| manifest tests | `tests/test_manifest.py` | manifest roundtrip |
| lint tests | `tests/test_report_lint.py` | NaN/TODO/path lint |
| CLI smoke | `tests/test_cli_smoke.py` | `--help` exits 0 |
| S00 contract | `docs/mc_validation/contracts/observed_contracts.json` | From `scripts/01_build_pulse_table_from_root.py` |
| result registry | `reports/mc_validation_registry.json` | Empty skeleton |

Phase A–C modules (`config.py`, `cli.py`, `manifest.py`, study/truth/io layers) live alongside this reporting slice under `src/ccb_mc_validation/`.

# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: ccb-testbeam
#     language: python
#     name: ccb-testbeam
# ---

# %% tags=["parameters"]
RUN_ID = '20260625T064500Z_full_input_artifacted'
RUN_ROOT = None
STUDY_ID = "MV9"
EXECUTION_MODE = "artifact-summary"
ALLOW_FIXTURE = False

# %% [markdown] tags=["provenance"]
# # MC Validation Release Overview
#
# This paired-text notebook is an artifact-only reader entry point. It loads the frozen
# validation and summary artifacts for the injected `RUN_ID`; it must not rerun ROOT scans,
# GEANT4, digitization, model training, systematic arrays, or full-data rendering.

# %% tags=["provenance", "integrity"]
from pathlib import Path
import csv
import json

if RUN_ID is None:
    raise RuntimeError("RUN_ID must be injected for production notebook export")

run_root = Path(RUN_ROOT) if RUN_ROOT else Path.cwd()
validation_path = run_root / "VALIDATION.json"
metrics_path = run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv"
validation = json.loads(validation_path.read_text(encoding="utf-8"))
metrics = list(csv.DictReader(metrics_path.open("r", encoding="utf-8", newline="")))

if any(row.get("status") == "FIXTURE" for row in metrics):
    raise RuntimeError("fixture metrics are not allowed in production notebook export")

# %% [markdown] tags=["scope"]
# ## Scope and guardrail
#
# This notebook summarizes artifact validation and selected MV1-MV3/MV9 metrics only. It is
# intentionally marked partial until MV4-MV8, systematic arrays, the full figure catalog,
# executable notebooks, reports, thesis, and release QA are complete.

# %% tags=["primary-result"]
validation.get("status"), validation.get("job_state", {})

# %% tags=["primary-result"]
metrics

# %% [markdown] tags=["reproduction"]
# ## Reproduction
#
# From the repository root, rebuild this artifact-only export with:
#
# ```bash
# python scripts/mc_validation/run_pipeline.py --run-id "$RUN_ID" notebooks
# ```

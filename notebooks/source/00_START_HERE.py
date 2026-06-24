# %% [markdown]
# # 00 — Start here: MC validation execution
#
# **Question:** What is the current MC-validation run, and where are its artifacts?

# %%
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "notebooks"))
from _shared import load_run_state, repo_root, run_dir

parser = argparse.ArgumentParser()
parser.add_argument("--run-id", default=None)
args, _ = parser.parse_known_args()

runs_root = repo_root() / "reports/mc_validation/runs"
if args.run_id:
    RUN_ID = args.run_id
else:
    candidates = sorted(runs_root.iterdir()) if runs_root.is_dir() else []
    RUN_ID = candidates[-1].name if candidates else "unknown"

print("Repository:", repo_root())
print("Run ID:", RUN_ID)
state = load_run_state(RUN_ID) if (run_dir(RUN_ID) / "RUN_STATE.json").is_file() else {}
print(json.dumps(state, indent=2))

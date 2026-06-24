# %% [markdown]
# # 04 — MV1 particle ID (truth ceiling)

# %%
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "notebooks"))
from _shared import load_study_result

parser = argparse.ArgumentParser()
parser.add_argument("--run-id", required=True)
args, _ = parser.parse_known_args()

result = load_study_result(args.run_id, "MV1")
print("Status:", result.get("status"))
metrics = result.get("metrics", {})
for key in sorted(metrics):
    if "auc" in key or "purity" in key:
        print(f"  {key}: {metrics[key]}")

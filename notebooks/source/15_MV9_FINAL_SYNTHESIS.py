# %% [markdown]
# # 15 — MV9 final synthesis

# %%
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "notebooks"))
from _shared import repo_root

parser = argparse.ArgumentParser()
parser.add_argument("--run-id", required=True)
args, _ = parser.parse_known_args()

synth = repo_root() / "reports/mc_validation/runs" / args.run_id / "MV9" / "MV9_SYNTHESIS.md"
if synth.is_file():
    print(synth.read_text(encoding="utf-8"))
else:
    print("MV9 synthesis not found — status NOT_RUN")

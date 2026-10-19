"""Fail-closed A09 manuscript/fit contract; read actual checkout files."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
data = json.loads((ROOT/"reports/paper_1303_optical_campaign_20260815T2209Z/result.json").read_text())
rows = {x["energy_target"]: x for x in data["summaries"] if not x["is_negative_control"]}
assert set(rows) == {"E_vis", "E_raw"}
assert rows["E_vis"]["fit"]["slope_pe_per_MeV"] != rows["E_raw"]["fit"]["slope_pe_per_MeV"]
script = (ROOT/"scripts/single_stave/paper_a09_heldout_edep_reconstruction.py").read_text()
assert 'energy_col = f"{energy_target}_MeV"' in script
assert "fit_pooled_linear(x_train, y_train)" in script
chapter = (ROOT/"publication/chapters/09_energy_reconstruction.tex").read_text()
assert "pooled $E_{\\rm vis}$-calibrated linear response" not in chapter, "A09 caption falsely claims reuse of an E_vis fit"
print("SCOPED_DOC_CONSISTENCY_ONLY_NOT_PUBLICATION_CLEARANCE")

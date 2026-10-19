"""A09 scientific-text gate: scoped only, not physics release."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def gate(ok,reason):
    if not ok: raise SystemExit('BLOCKED: '+reason)
j=json.loads((R/'reports/paper_1303_optical_campaign_20260815T2209Z/result.json').read_text())
a={x['energy_target']:x for x in j['summaries'] if not x['is_negative_control']}
gate(set(a)=={'E_raw','E_vis'},'targets')
gate(a['E_raw']['fit']!=a['E_vis']['fit'],'fit identity')
s=(R/'scripts/single_stave/paper_a09_heldout_edep_reconstruction.py').read_text()
gate('energy_col = f"{energy_target}_MeV"' in s and 'fit_pooled_linear(x_train, y_train)' in s,'producer refit')
t=(R/'publication/chapters/09_energy_reconstruction.tex').read_text()
gate('pooled $E_{\\rm vis}$-calibrated linear response' not in t,'caption')
gate('serves as the negative control, alongside' not in t,'prose')
print('DOC_CHECK_ONLY_NOT_SCIENCE_CLEAR')

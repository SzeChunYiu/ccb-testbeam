#!/bin/bash
#SBATCH --job-name=v3val1m
#SBATCH --partition=lu48
#SBATCH -A lu2026-2-51
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3/val_v3_1m_%j.out
#SBATCH --error=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3/val_v3_1m_%j.err
set -euo pipefail
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python
cp /tmp/validate_v3_10k.py /tmp/validate_v3.py.tmp 2>/dev/null || true
cat > /tmp/val_v3_1m.py << 'PYEOF'
import uproot
import numpy as np

F = "/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3/output_krakow_v3_1M.root"
t = uproot.open(F)["hibeam"]
CHARGED = np.array(sorted({2212, 1000010020, 1000010030, 1000020030, 1000020040,
                           11, -11, 13, -13, 211, -211, 321, -321,
                           1000060120, 1000060130, 1000060140}), dtype=np.int64)

def fired(prefix, thr):
    out = np.zeros(int(t.num_entries), dtype=bool)
    for i, a in enumerate(t[f"{prefix}_EDep"].array(library="np")):
        out[i] = len(a) and np.asarray(a).sum() >= thr
    return out

n = int(t.num_entries)
print(f"events: {n}")
for thr in (0.5, 1.0, 2.0, 5.0):
    f1, f2 = fired("T1_trigger_log", thr), fired("T2_trigger_log", thr)
    print(f"thr={thr}: T1={f1.sum()} T2={f2.sum()} T1&T2={(f1&f2).sum()} ({(f1&f2).mean()*100:.4f}%)")

# two-arm identification
BR = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_Time"]
twoarm = np.zeros(n, dtype=bool)
ev = 0
for chunk in t.iterate(BR, step_size=50000, library="np"):
    LAY = chunk["Sci_bar_LayerID"]; L1 = chunk["Sci_bar_LayerID1"]
    PDG = chunk["Sci_bar_PDG"]; TM = chunk["Sci_bar_Time"]
    for i in range(len(LAY)):
        lay = np.asarray(LAY[i]).astype(np.int64); l1 = np.asarray(L1[i]).astype(np.int64)
        pdg = np.asarray(PDG[i]).astype(np.int64); tm = np.asarray(TM[i]).astype(np.float64)
        ch = np.isin(pdg, CHARGED)
        fb = (l1 == 1) & (lay == 0) & ch
        fa = (l1 == 2) & (lay == 0) & ch
        twoarm[ev] = fb.any() and fa.any() and abs(tm[fa].min() - tm[fb].min()) < 15.0
        ev += 1
print(f"two-arm events: {twoarm.sum()}")

f1, f2 = fired("T1_trigger_log", 0.5), fired("T2_trigger_log", 0.5)
both = f1 & f2
print(f"two-arm & T1&T2(0.5): {both[twoarm].sum()}/{twoarm.sum()} = {both[twoarm].mean():.4f} (ray prediction 0.289)")
print(f"non-two-arm & T1&T2: {both[~twoarm].sum()}")
np.save("/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3/v3_1m_twoarm_mask.npy", twoarm)
PYEOF
${PY} /tmp/val_v3_1m.py

#!/usr/bin/env python
"""#1045 Phase 2 geometry v3: instrument the BASELINE Trig_stacks as T1/T2.

v2 (translation-only paddles at r=30) is RETRACTED: its positions were the
sign-flipped antipodes of the arm axes -> 0/554 two-arm triggers in 1M.
MATTHIAS_RESPONSE ground truth = "T1/T2 trigger scintillator (PSci, 1 cm)".
The baseline geometry already contains Trig_stack_1 (B arm, -38 deg) and
Trig_stack_2 (A arm, +71.5 deg) with 2 PSci bars (20x8x1 cm) each -- passive.
v3 splits the shared Trig_bar logical volume into T1_trigger_log (stack_1)
and T2_trigger_log (stack_2) at IDENTICAL placements -> SD-instrumentable.
"""
import math
import ROOT

ROOT.gROOT.SetBatch(True)
BASE = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root"
OUT = "/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3/krakow_109_T1T2v3.root"

ROOT.TGeoManager.Import(BASE)
geo = ROOT.gGeoManager
top = geo.GetTopVolume()

def topmap():
    m = {}
    for i in range(top.GetNdaughters()):
        n = top.GetNode(i)
        t = n.GetMatrix().GetTranslation()
        m[n.GetName()] = (round(t[0], 6), round(t[1], 6), round(t[2], 6))
    return m

before = topmap()

nodes = [top.GetNode(i) for i in range(top.GetNdaughters())]
ts = {n.GetName(): n for n in nodes if n.GetName().startswith("Trig_stack")}
assert set(ts) == {"Trig_stack_1", "Trig_stack_2"}, sorted(ts)

bar_vol = geo.GetVolume("Trig_bar")
stack_vol = geo.GetVolume("Trig_stack")
bar_shape, bar_med = bar_vol.GetShape(), bar_vol.GetMedium()
stack_shape, stack_med = stack_vol.GetShape(), stack_vol.GetMedium()

# original daughter local placements (stacks share one logical container)
sv = ts["Trig_stack_1"].GetVolume()
assert sv.GetNdaughters() == 2
dau_local = []
for i in range(sv.GetNdaughters()):
    d = sv.GetNode(i)
    t = d.GetMatrix().GetTranslation()
    dau_local.append((t[0], t[1], t[2]))
print("original bar local placements:", dau_local)

# named bar volumes + per-stack containers, same shape/medium as baseline
t1bar = ROOT.TGeoVolume("T1_trigger_log", bar_shape, bar_med)
t2bar = ROOT.TGeoVolume("T2_trigger_log", bar_shape, bar_med)
c1 = ROOT.TGeoVolume("Trig_stack_T1", stack_shape, stack_med)
c2 = ROOT.TGeoVolume("Trig_stack_T2", stack_shape, stack_med)
for i, (x, y, z) in enumerate(dau_local):
    c1.AddNode(t1bar, i + 1, ROOT.TGeoTranslation(x, y, z))
    c2.AddNode(t2bar, i + 1, ROOT.TGeoTranslation(x, y, z))

# replace the two top-level nodes, preserving global matrices (clone first)
mats = {k: ROOT.TGeoHMatrix(ts[k].GetMatrix()) for k in ts}
for name, cont in (("Trig_stack_1", c1), ("Trig_stack_2", c2)):
    top.RemoveNode(ts[name])
    top.AddNode(cont, 1, mats[name])

# ---------- gates ----------
after = topmap()
ok = True

g1 = (len(after) == len(before) == 8)
print(f"GATE daughter-count 8->8: {'PASS' if g1 else 'FAIL'} ({len(before)}->{len(after)})")
ok &= g1

g2 = all(after.get(k) == v for k, v in before.items() if not k.startswith("Trig_stack"))
print(f"GATE non-Trig nodes byte-identical: {'PASS' if g2 else 'FAIL'}")
ok &= g2

g3 = (after.get("Trig_stack_T1_1") == before.get("Trig_stack_1")
      and after.get("Trig_stack_T2_1") == before.get("Trig_stack_2"))
print(f"GATE stack positions preserved: {'PASS' if g3 else 'FAIL'} "
      f"T1={after.get('Trig_stack_T1_1')} T2={after.get('Trig_stack_T2_1')}")
ok &= g3

for nm, want in (("Trig_stack_T1_1", -38.0), ("Trig_stack_T2_1", 71.5)):
    t = after[nm]
    ang = math.degrees(math.atan2(t[0], t[2]))
    oki = abs(ang - want) < 0.05
    print(f"GATE arm angle {nm}: {ang:+.2f} deg (want {want:+.1f}) {'PASS' if oki else 'FAIL'}")
    ok &= oki

for v in (t1bar, t2bar):
    s = v.GetShape()
    g = (abs(s.GetDX() - 10.0) < 1e-6 and abs(s.GetDY() - 4.0) < 1e-6
         and abs(s.GetDZ() - 0.5) < 1e-6
         and v.GetMedium().GetMaterial().GetName() == "PSci")
    print(f"GATE {v.GetName()} BBox(10,4,0.5) PSci: {'PASS' if g else 'FAIL'}")
    ok &= g

ROOT.gGeoManager.CheckOverlaps(0.001)
nbad = ROOT.gGeoManager.GetListOfOverlaps().GetEntries() if ROOT.gGeoManager.GetListOfOverlaps() else 0
print(f"GATE overlaps(0.001): {nbad} {'PASS' if nbad == 0 else 'FAIL'}")
ok &= (nbad == 0)

if not ok:
    print("GATES FAILED - not exporting")
    raise SystemExit(1)

import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)
geo.Export(OUT)
print("EXPORTED:", OUT)

import hashlib
h = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
print("sha256:", h)

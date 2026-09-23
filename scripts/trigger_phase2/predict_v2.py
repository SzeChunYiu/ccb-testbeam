import uproot, numpy as np

t = uproot.open("/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M/output_krakow_1M_phase2.root")["hibeam"]
CHARGED = np.array(sorted({2212,1000010020,1000010030,1000020030,1000020040,11,-11,13,-13,211,-211,321,-321,1000060120,1000060130,1000060140}), dtype=np.int64)
B_ARM, A_ARM = 1, 2
BR = ["Sci_bar_LayerID","Sci_bar_LayerID1","Sci_bar_PDG","Sci_bar_Time",
      "Sci_bar_GlobalPosition_X","Sci_bar_GlobalPosition_Y","Sci_bar_GlobalPosition_Z"]
EY = np.array([0.0,1.0,0.0])
arms = {
  "B(−38°,Trig1@r99)": dict(ex=np.array([0.788011,0,0.615661]), ez=np.array([-0.615661,0,0.788011]), node=np.array([-60.9505,0.0,78.0131]), arm=B_ARM),
  "A(71.5°,Trig2@r99)": dict(ex=np.array([0.317305,0,-0.948324]), ez=np.array([0.948324,0,0.317305]), node=np.array([93.884,0.0,31.4132]), arm=A_ARM),
}

n2 = 0
xc = {"B": [], "A": []}
yc = {"B": [], "A": []}
hitB = []; hitA = []
for chunk in t.iterate(BR, step_size=100000, library="np"):
    LAY = chunk["Sci_bar_LayerID"]; L1 = chunk["Sci_bar_LayerID1"]
    PDG = chunk["Sci_bar_PDG"]; TM = chunk["Sci_bar_Time"]
    PX = chunk["Sci_bar_GlobalPosition_X"]; PY = chunk["Sci_bar_GlobalPosition_Y"]; PZ = chunk["Sci_bar_GlobalPosition_Z"]
    for i in range(len(LAY)):
        lay = np.asarray(LAY[i]).astype(np.int64); l1 = np.asarray(L1[i]).astype(np.int64)
        pdg = np.asarray(PDG[i]).astype(np.int64); tm = np.asarray(TM[i]).astype(np.float64)
        ch = np.isin(pdg, CHARGED)
        fb = (l1==B_ARM)&(lay==0)&ch; fa = (l1==A_ARM)&(lay==0)&ch
        if not (fb.any() and fa.any()): continue
        if not abs(tm[fa].min()-tm[fb].min()) < 15.0: continue
        n2 += 1
        ev_hit = {}
        for name,a in arms.items():
            sel = fb if a["arm"]==B_ARM else fa
            j = int(np.argmin(np.where(sel, tm, np.inf)))
            p = np.array([float(PX[i][j]), float(PY[i][j]), float(PZ[i][j])])
            u = p/np.linalg.norm(p)
            d0 = float(a["node"] @ a["ez"])
            s = (d0 - float(p @ a["ez"])) / float(u @ a["ez"])
            q = p + s*u
            xc[name[0]].append(float((q - a["node"]) @ a["ex"]))
            yc[name[0]].append(float((q - a["node"]) @ EY))
            ev_hit[name[0]] = (abs(float((q - a["node"]) @ a["ex"])) <= 10.0) and (abs(float((q - a["node"]) @ EY)) <= 4.0)
        hitB.append(ev_hit["B"]); hitA.append(ev_hit["A"])

print(f"two-arm events: {n2}")
for k in ("B","A"):
    arr = np.array(xc[k]); yar = np.array(yc[k])
    print(f"arm {k}: x_c min={arr.min():.1f} p5={np.percentile(arr,5):.1f} med={np.median(arr):.1f} p95={np.percentile(arr,95):.1f} max={arr.max():.1f}")
    print(f"        |x_c|<=10: {np.mean(np.abs(arr)<=10):.3f}  |y_c|<=4: {np.mean(np.abs(yar)<=4):.3f}  |x_c|>50 (must be 0): {int(np.sum(np.abs(arr)>50))}")
hb, ha = np.array(hitB), np.array(hitA)
print(f"PREDICTED single-arm B in-bar: {hb.sum()}/{n2} = {hb.mean():.3f}")
print(f"PREDICTED single-arm A in-bar: {ha.sum()}/{n2} = {ha.mean():.3f}")
print(f"PREDICTED hardware coincidence (both in-bar): {(hb&ha).sum()}/{n2} = {(hb&ha).mean():.3f}")

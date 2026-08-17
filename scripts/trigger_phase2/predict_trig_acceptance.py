import uproot, numpy as np

F = "/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M/output_krakow_1M_phase2.root"
t = uproot.open(F)["hibeam"]
CHARGED = {2212,1000010020,1000010030,1000020030,1000020040,11,-11,13,-13,211,-211,321,-321,1000060120,1000060130,1000060140}
B_ARM, A_ARM = 1, 2
BR = ["Sci_bar_LayerID","Sci_bar_LayerID1","Sci_bar_PDG","Sci_bar_Time",
      "Sci_bar_GlobalPosition_X","Sci_bar_GlobalPosition_Y","Sci_bar_GlobalPosition_Z",
      "Sci_bar_Momentum_X","Sci_bar_Momentum_Y","Sci_bar_Momentum_Z"]

arms = {
  "B": dict(ex=np.array([0.788011,0,0.615661]), ey=np.array([0,1,0]),
            ez=np.array([-0.615661,0,0.788011]), node=np.array([-60.9505,0.0,78.0131]), arm=B_ARM),
  "A": dict(ex=np.array([0.317305,0,-0.948324]), ey=np.array([0,1,0]),
            ez=np.array([0.948324,0,0.317305]), node=np.array([93.884,0.0,31.4132]), arm=A_ARM),
}

n2 = 0
res = {k: {"mom": [], "ray": []} for k in arms}
both = {"mom": 0, "ray": 0}
for chunk in t.iterate(BR, step_size=50000, library="np"):
    for i in range(len(chunk["Sci_bar_LayerID"])):
        lay = np.asarray(chunk["Sci_bar_LayerID"][i]).astype(np.int64); l1 = np.asarray(chunk["Sci_bar_LayerID1"][i]).astype(np.int64)
        pdg = np.asarray(chunk["Sci_bar_PDG"][i]).astype(np.int64); tm = np.asarray(chunk["Sci_bar_Time"][i]).astype(np.float64)
        ch = np.isin(pdg, np.array(sorted(CHARGED), dtype=np.int64))
        fb = (l1==B_ARM)&(lay==0)&ch; fa = (l1==A_ARM)&(lay==0)&ch
        if not (fb.any() and fa.any()): continue
        if not abs(tm[fa].min()-tm[fb].min()) < 15.0: continue
        n2 += 1
        hits = {}
        for name,a in arms.items():
            sel = fb if a["arm"]==B_ARM else fa
            j = np.argmax(np.where(sel, tm, np.inf))  # earliest entering hit
            p = np.array([chunk["Sci_bar_GlobalPosition_X"][i][j],
                          chunk["Sci_bar_GlobalPosition_Y"][i][j],
                          chunk["Sci_bar_GlobalPosition_Z"][i][j]], float)
            mv = np.array([chunk["Sci_bar_Momentum_X"][i][j],
                           chunk["Sci_bar_Momentum_Y"][i][j],
                           chunk["Sci_bar_Momentum_Z"][i][j]], float)
            nrm = np.linalg.norm(mv)
            u = mv/nrm if nrm > 0 else p/np.linalg.norm(p)
            d0 = float(a["node"] @ a["ez"])
            out = {}
            for mode, dirv in (("mom", u), ("ray", p/np.linalg.norm(p))):
                s = (d0 - float(p @ a["ez"])) / float(dirv @ a["ez"])
                q = p + s*dirv
                x_c = float((q - a["node"]) @ a["ex"]); y_c = float((q - a["node"]) @ a["ey"])
                out[mode] = (s, x_c, y_c)
            res[name]["mom"].append(out["mom"]); res[name]["ray"].append(out["ray"])
            hits[name] = out
        for mode in ("mom","ray"):
            if abs(hits["B"][mode][1])<=10 and abs(hits["A"][mode][1])<=10 and \
               abs(hits["B"][mode][2])<=4 and abs(hits["A"][mode][2])<=4:
                both[mode] += 1

print(f"two-arm events: {n2}")
for name in ("B","A"):
    for mode in ("mom","ray"):
        arr = np.array([r[1] for r in res[name][mode]])
        sgn = np.array([r[0] for r in res[name][mode]])
        yarr = np.array([r[2] for r in res[name][mode]])
        print(f"arm {name} [{mode}] x_c: min={arr.min():.1f} p5={np.percentile(arr,5):.1f} med={np.median(arr):.1f} "
              f"p95={np.percentile(arr,95):.1f} max={arr.max():.1f} | |x_c|<=10: {(np.abs(arr)<=10).mean():.3f} "
              f"| |y_c|<=4: {(np.abs(yarr)<=4).mean():.3f} | s<0 (upstream): {(sgn<0).mean():.3f}")
for mode in ("mom","ray"):
    print(f"PREDICTED hardware coincidence (both arms in-bar): {both[mode]}/{n2} = {both[mode]/n2:.3f}")

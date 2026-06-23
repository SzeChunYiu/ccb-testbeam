#!/usr/bin/env python3
"""
mv1_mv2_truth_pid_energy.py
===========================
MV1 (particle ID p vs d) and MV2 (energy / range calibration) at MC truth level
for the CCB test beam B-stack.  No digitizer needed -- pure truth.

For every charged track in the B arm (Sci_bar_LayerID1==1) we group hits by
Sci_bar_TrackID within the event and build the per-track profile:
  - truth species (PDG; p / d / alpha / ...)
  - entry kinetic energy  Ekin = sqrt(|p|^2 + m^2) - m   (momentum at first hit)
  - per-layer EDep, total EDep, stop layer (max LayerID), n layers, track length

MV1 -- PID ceiling: the dE-E plane (EDep layer0 vs EDep layer1) and a simple
       traditional cut + an ML classifier give the *achievable* p/d separation
       any data method aspires to (ROC AUC, purity@90% eff).
MV2 -- range-energy: stop-depth / track-length vs entry Ekin per species (the
       PSTAR/power-law range model S14 uses); and how well Ekin is reconstructed
       from observables (stop layer + total EDep) -- tests the data-only claim
       that 10% absolute energy is unreachable.

Usage:
  python3 mv1_mv2_truth_pid_energy.py --mc output_krakow_1M.root --out <dir>
"""
import argparse, json, os
from functools import lru_cache
import numpy as np

B_ARM = 1
# rest masses [MeV]
MASS = {2212: 938.272, 1000010020: 1875.613, 1000010030: 2808.921,
        1000020030: 2808.391, 1000020040: 3727.379}
def mass_of(pdg):
    pdg = int(pdg)
    if pdg in MASS: return MASS[pdg]
    if abs(pdg) > 1_000_000_000:          # nucleus: A*amu approx
        A = (abs(pdg) // 10) % 1000
        return A * 931.494
    return 0.511 if abs(pdg) == 11 else 139.57  # e / pi fallback

@lru_cache(maxsize=None)
def charge(pdg):
    pdg = int(pdg); a = abs(pdg)
    if a > 1_000_000_000: return (a // 10_000) % 1000
    return {2212:1,2112:0,22:0,11:1,13:1,211:1,321:1}.get(a,0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    import uproot

    br = ["Sci_bar_TrackID","Sci_bar_LayerID","Sci_bar_LayerID1","Sci_bar_PDG",
          "Sci_bar_EDep","Sci_bar_TrackLength",
          "Sci_bar_Momentum_X","Sci_bar_Momentum_Y","Sci_bar_Momentum_Z"]
    # per-track records
    rec = {"pdg": [], "ekin": [], "edep_l0": [], "edep_l1": [],
           "edep_tot": [], "stop_layer": [], "nlayers": [], "tracklen": []}

    tree = uproot.open(args.mc)[args.tree]
    stop = args.max_events if args.max_events > 0 else None
    for ch in tree.iterate(br, step_size="200 MB", library="np", entry_stop=stop):
        TID=ch["Sci_bar_TrackID"]; L=ch["Sci_bar_LayerID"]; L1=ch["Sci_bar_LayerID1"]
        PD=ch["Sci_bar_PDG"]; ED=ch["Sci_bar_EDep"]; TL=ch["Sci_bar_TrackLength"]
        MX=ch["Sci_bar_Momentum_X"]; MY=ch["Sci_bar_Momentum_Y"]; MZ=ch["Sci_bar_Momentum_Z"]
        for i in range(len(L)):
            l=L[i]
            if len(l)==0: continue
            isB=(L1[i]==B_ARM)
            if not isB.any(): continue
            tid=TID[i]; pd=PD[i]; ed=ED[i]; ll=l
            for tr in np.unique(tid[isB]):
                m=isB&(tid==tr)
                p0=int(pd[m][0])
                if charge(p0)<1: continue            # charged only
                layers=ll[m]; eds=ed[m]
                # entry = lowest LayerID hit; use its momentum for Ekin
                order=np.argsort(layers)
                entry_idx=np.where(m)[0][order[0]]
                px,py,pz=MX[i][entry_idx],MY[i][entry_idx],MZ[i][entry_idx]
                pmag=float(np.sqrt(px*px+py*py+pz*pz))
                mm=mass_of(p0)
                ekin=float(np.sqrt(pmag*pmag+mm*mm)-mm)
                # per-layer edep (sum within a layer for this track)
                el={}
                for lay,e in zip(layers,eds): el[int(lay)]=el.get(int(lay),0.0)+float(e)
                rec["pdg"].append(p0)
                rec["ekin"].append(ekin)
                rec["edep_l0"].append(el.get(0,0.0))
                rec["edep_l1"].append(el.get(1,0.0))
                rec["edep_tot"].append(float(eds.sum()))
                rec["stop_layer"].append(int(layers.max()))
                rec["nlayers"].append(int(len(set(layers.tolist()))))
                rec["tracklen"].append(float(TL[i][m].sum()))

    for k in rec: rec[k]=np.asarray(rec[k])
    pdg=rec["pdg"]; isp=(pdg==2212); isd=(pdg==1000010020)
    out={"mc_file":os.path.abspath(args.mc),"n_tracks":int(pdg.size),
         "n_proton":int(isp.sum()),"n_deuteron":int(isd.sum())}

    # ---------- MV1: PID ceiling ----------
    # dE-E plane stats + simple classifiers on truth features
    def med(x): return float(np.median(x)) if x.size else 0.0
    out["MV1_pid"]={
        "deltaE_E_medians":{
            "proton":{"edep_l0":med(rec["edep_l0"][isp]),"edep_l1":med(rec["edep_l1"][isp]),
                      "edep_tot":med(rec["edep_tot"][isp]),"stop_layer":med(rec["stop_layer"][isp].astype(float))},
            "deuteron":{"edep_l0":med(rec["edep_l0"][isd]),"edep_l1":med(rec["edep_l1"][isd]),
                        "edep_tot":med(rec["edep_tot"][isd]),"stop_layer":med(rec["stop_layer"][isd].astype(float))},
        }
    }
    mask=isp|isd
    if mask.sum()>2000:
        X=np.column_stack([rec["edep_l0"][mask],rec["edep_l1"][mask],
                           rec["edep_tot"][mask],rec["stop_layer"][mask].astype(float)])
        y=isd[mask].astype(int)
        # split by a deterministic hash of index (run-free here; truth study)
        n=len(y); idx=np.arange(n); tr=idx%2==0; te=~tr
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.ensemble import HistGradientBoostingClassifier
            from sklearn.metrics import roc_auc_score
            lr=LogisticRegression(max_iter=500).fit(X[tr],y[tr])
            gb=HistGradientBoostingClassifier().fit(X[tr],y[tr])
            for name,mdl in (("logreg",lr),("hgb",gb)):
                s=mdl.predict_proba(X[te])[:,1]
                auc=float(roc_auc_score(y[te],s))
                # purity at 90% deuteron efficiency
                thr=np.quantile(s[y[te]==1],0.10)
                sel=s>=thr; pur=float((y[te][sel]==1).mean()) if sel.any() else 0.0
                out["MV1_pid"][f"{name}_auc"]=auc
                out["MV1_pid"][f"{name}_purity_at_90eff"]=pur
        except Exception as e:
            out["MV1_pid"]["_ml_error"]=str(e)
        # traditional single-cut on edep_l0 (deuterons deposit more in first layer)
        from numpy import quantile
        thr=float(np.median(np.concatenate([rec["edep_l0"][isp],rec["edep_l0"][isd]])))
        pred=(X[:,0]>thr).astype(int)
        tp=((pred==1)&(y==1)).sum(); fp=((pred==1)&(y==0)).sum()
        out["MV1_pid"]["cut_edep_l0_thr_MeV"]=thr
        out["MV1_pid"]["cut_purity"]=float(tp/(tp+fp)) if (tp+fp)>0 else 0.0
        out["MV1_pid"]["cut_efficiency"]=float(tp/max(int(y.sum()),1))

    # ---------- MV2: range-energy ----------
    def prof(mask):
        d={}
        for lay in range(8):
            mm=mask&(rec["stop_layer"]==lay)
            if mm.sum()>10:
                d[lay]={"n":int(mm.sum()),"mean_ekin_MeV":float(rec["ekin"][mm].mean()),
                        "mean_edep_tot_MeV":float(rec["edep_tot"][mm].mean()),
                        "mean_tracklen_mm":float(rec["tracklen"][mm].mean())}
        return d
    out["MV2_range_energy"]={"proton_stoplayer_vs_ekin":prof(isp),
                             "deuteron_stoplayer_vs_ekin":prof(isd)}
    # Ekin reconstruction from observables (stop_layer + edep_tot), per species, truth test
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
        for nm,msk in (("proton",isp),("deuteron",isd)):
            m=msk & (rec["ekin"]>0)
            if m.sum()<2000: continue
            Xe=np.column_stack([rec["stop_layer"][m].astype(float),rec["edep_tot"][m],
                                rec["edep_l0"][m],rec["nlayers"][m].astype(float)])
            ye=rec["ekin"][m]; n=len(ye); tr=np.arange(n)%2==0; te=~tr
            r=HistGradientBoostingRegressor().fit(Xe[tr],ye[tr])
            pe=r.predict(Xe[te]); res=(pe-ye[te])/np.clip(ye[te],1e-6,None)
            out["MV2_range_energy"][f"{nm}_ekin_recon_res68"]=float(np.percentile(np.abs(res),68))
            out["MV2_range_energy"][f"{nm}_ekin_mean_MeV"]=float(ye.mean())
    except Exception as e:
        out["MV2_range_energy"]["_ml_error"]=str(e)

    with open(os.path.join(args.out,"mv1_mv2_truth_summary.json"),"w") as fh:
        json.dump(out,fh,indent=2)
    np.savez_compressed(os.path.join(args.out,"truth_tracks.npz"),
        pdg=pdg.astype(np.int64),ekin=rec["ekin"].astype(np.float32),
        edep_l0=rec["edep_l0"].astype(np.float32),edep_l1=rec["edep_l1"].astype(np.float32),
        edep_tot=rec["edep_tot"].astype(np.float32),stop_layer=rec["stop_layer"].astype(np.int16))

    # plots
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig,ax=plt.subplots(1,2,figsize=(12,4.8))
        for lab,msk,c in (("proton",isp,"C0"),("deuteron",isd,"C3")):
            ax[0].scatter(rec["edep_tot"][msk][:4000],rec["edep_l0"][msk][:4000],s=3,alpha=0.3,label=lab,color=c)
        ax[0].set_xlabel("total EDep in B [MeV]");ax[0].set_ylabel("EDep first layer [MeV]")
        ax[0].set_title("MV1 dE-E plane (truth)");ax[0].legend()
        for lab,msk,c in (("proton",isp,"C0"),("deuteron",isd,"C3")):
            sl=rec["stop_layer"][msk];ek=rec["ekin"][msk]
            xs=range(8);ys=[ek[sl==l].mean() if (sl==l).sum()>10 else np.nan for l in xs]
            ax[1].plot(list(xs),ys,"o-",label=lab,color=c)
        ax[1].set_xlabel("stop layer");ax[1].set_ylabel("mean entry Ekin [MeV]")
        ax[1].set_title("MV2 range-energy (truth)");ax[1].legend()
        fig.tight_layout();fig.savefig(os.path.join(args.out,"mv1_mv2_truth.png"),dpi=130)
    except Exception as e:
        out["_plot_error"]=str(e)
        with open(os.path.join(args.out,"mv1_mv2_truth_summary.json"),"w") as fh:
            json.dump(out,fh,indent=2)

    print(json.dumps({k:out[k] for k in ("n_tracks","n_proton","n_deuteron")},indent=1))
    print("MV1:",json.dumps({k:v for k,v in out["MV1_pid"].items() if "auc" in k or "purity" in k},indent=1))
    print(f"[ok] wrote {args.out}/mv1_mv2_truth_summary.json")

if __name__=="__main__":
    main()

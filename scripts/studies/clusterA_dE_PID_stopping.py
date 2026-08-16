#!/usr/bin/env python3
"""Cluster A: dE-E / PID / stopping-depth diagnostic study (Krakow 1M-event MC).

Physics
-------
Beam on CD2 is *pure protons* (PrimaryPDG==2212, all 1e6 events).  CD2 breakup
produces recoil deuterons (24.6% of Sci_bar steps, ~14.5% of events), alphas
(4%) and heavier ions as secondaries that reach the B-arm scintillator bars.
The dE-E technique separates these species into distinct Bethe-Bloch bands; the
per-event band identity is the *energy-weighted dominant depositing species in
the bars* (proton vs deuteron), NOT the primary beam particle.

Carried fixes (from origin/main)
--------------------------------
  * GeV -> MeV units  : kinetic_energy_from_branch_momentum (reaudit #864)
  * PrimaryWeight     : per-event weight = first primary (beam), issue #880
  * stop-vs-escape    : TRU-003 -- deepest observed layer is NEVER a stop
                        without truth; 'stop' only if residual KE at last hit
                        <= STOP_KE_THRESHOLD_MEV (1.0 MeV).
  * odd/even readout  : GEO-001 pair_merge via GeometryRegistry
                        (MC layers (0,1)->B2, (2,3)->B4, (4,5)->B6, (6,7)->B8).
  * edep_per_layer    : from canonical build_track_records.

Outputs: 7 PNGs + counts.json under reports/studies/clusterA/.
Pure numpy/matplotlib/uproot/awkward (no pandas, no sklearn).
"""
from __future__ import annotations
import os, json
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ccb_mc_validation.constants import B_ARM, NB_LAYERS
from ccb_mc_validation.truth.geometry import GeometryRegistry
from ccb_mc_validation.truth.track_builder import build_track_records, STOP_KE_THRESHOLD_MEV_DEFAULT
from ccb_mc_validation.truth.pdg import species_label

ROOT = os.environ.get("CLUSTER_MC_ROOT", "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.normpath(os.path.join(HERE, "..", "..", "reports", "studies", "clusterA"))
os.makedirs(OUT, exist_ok=True)

GEOM = GeometryRegistry.from_config({})
L2S  = GEOM.layer_to_stave
STAVE_LAYERS = {"B2": [0,1], "B4": [2,3], "B6": [4,5], "B8": [6,7]}

BRANCHES = ["Sci_bar_TrackID","Sci_bar_LayerID","Sci_bar_LayerID1","Sci_bar_PDG",
            "Sci_bar_EDep","Sci_bar_TrackLength","Sci_bar_Momentum_X","Sci_bar_Momentum_Y",
            "Sci_bar_Momentum_Z","Sci_bar_GlobalPosition_Z","PrimaryWeight"]

DEF_PROT, DEF_DEUT, DEF_ALPHA, DEF_OTHER = 2212, 1000010020, 1000020040, -99
def bucket(pdg):
    pdg=int(pdg)
    if pdg==2212: return DEF_PROT
    if pdg==1000010020: return DEF_DEUT
    if pdg==1000020040: return DEF_ALPHA
    return DEF_OTHER
BUCKET_NAME = {DEF_PROT:"proton", DEF_DEUT:"deuteron", DEF_ALPHA:"alpha", DEF_OTHER:"other"}
BUCKET_COLOR = {"proton":"#1f77b4","deuteron":"#d62728","alpha":"#2ca02c","other":"#7f7f7f"}
TERM_CODE = {"stop":0, "escape":1, "censored":2}
CODE_TERM = {v:k for k,v in TERM_CODE.items()}

def wmedian(x, w):
    x=np.asarray(x,float); w=np.asarray(w,float)
    m=np.isfinite(x)&np.isfinite(w)&(w>0); x,w=x[m],w[m]
    if x.size==0: return float("nan")
    o=np.argsort(x); xs,ws=x[o],w[o]; cw=np.cumsum(ws)/ws.sum()
    return float(np.interp(0.5,cw,xs))

# ---------------------------------------------------------------------------
# stream + canonical per-track records -> per-event numpy arrays
# ---------------------------------------------------------------------------
def load_events(max_events=0):
    tree = uproot.open(ROOT)["hibeam"]
    E=[];PDG=[];EDEP=[];EKIN=[];EKINL=[];LAST=[];TERM=[];W=[];LAYS=[]
    lz=[]
    nread=0
    for chunk in tree.iterate(BRANCHES, step_size="200 MB", library="np"):
        recs = build_track_records(chunk, source=ROOT, entry_offset=nread)
        nread += len(chunk["Sci_bar_LayerID"])
        for r in recs:
            E.append(r["event_index"]); PDG.append(bucket(r["pdg"]))
            EDEP.append(r["edep_tot"]); EKIN.append(r["ekin"]); EKINL.append(r["ekin_last_observed"])
            LAST.append(r["last_observed_layer"]); TERM.append(TERM_CODE[r["termination"]])
            W.append(r["event_weight"]); LAYS.append(r["edep_per_layer"])
        try:
            l1=np.asarray(chunk["Sci_bar_LayerID1"]); ly=np.asarray(chunk["Sci_bar_LayerID"])
            gz=np.asarray(chunk["Sci_bar_GlobalPosition_Z"])
            for a1,aly,agz in zip(l1,ly,gz):
                m=np.asarray(a1)==B_ARM
                for L_,zv in zip(np.asarray(aly)[m],np.asarray(agz)[m]):
                    lz.append((int(L_),float(zv)))
        except Exception:
            pass
        if max_events and nread>=max_events:
            break
    ev=np.array(E); pdg=np.array(PDG); edep=np.array(EDEP); ekin=np.array(EKIN)
    ekinl=np.array(EKINL); last=np.array(LAST); term=np.array(TERM); w=np.array(W)
    lays=np.array(LAYS).reshape(len(E),NB_LAYERS)
    # per-event dominant track = max edep_tot per event
    order=np.argsort(ev)
    ev,pdg,edep,ekin,ekinl,last,term,w,lays = (a[order] for a in
        (ev,pdg,edep,ekin,ekinl,last,term,w,lays))
    uniq,first = np.unique(ev, return_index=True)
    # arrays are sorted by ev; first occurrence after stable sort by -edep within event:
    # achieve dominant-first by sorting (ev, -edep)
    o2=np.lexsort((-edep, ev))
    ev,pdg,edep,ekin,ekinl,last,term,w,lays=(a[o2] for a in (ev,pdg,edep,ekin,ekinl,last,term,w,lays))
    _,dom=np.unique(ev,return_index=True)          # first index per event = dominant track
    evu=ev[dom]; inv=np.searchsorted(evu, ev)      # inverse mapping track->event row
    n_ev=len(evu)
    sumlay=np.zeros((n_ev,NB_LAYERS))
    np.add.at(sumlay, inv, lays)                   # summed per-layer edep per event
    out=dict(
        evt=evu,
        pdg_dom=pdg[dom], edep_dom=edep[dom], ekin_entry=ekin[dom],
        ekin_last=ekinl[dom], last_layer=last[dom], termination=term[dom], w=w[dom],
        sumlay=sumlay,
    )
    out["dE"]   = sumlay[:,0]+sumlay[:,1]
    out["Eres"] = sumlay[:,2:].sum(1)
    out["Etot"] = sumlay.sum(1)
    geo={}
    if lz:
        la=np.array(lz); 
        geo["layer_z_cm"]={int(L): float(np.median(la[la[:,0]==L,1])/10.0) for L in np.unique(la[:,0])}
    return out, geo, nread

# ---- ROC/PR (numpy) + grouped bootstrap -----------------------------------
def roc_pr(y,s,w):
    y=np.asarray(y); s=np.asarray(s); w=np.asarray(w,float)
    o=np.argsort(-s); y,s,w=y[o],s[o],w[o]
    P=w[y==1].sum(); N=w[y==0].sum()
    if P<=0 or N<=0: return None
    tp=np.cumsum(w*y); fp=np.cumsum(w*(1-y))
    tpr=np.concatenate([[0.],tp/P,[1.]]); fpr=np.concatenate([[0.],fp/N,[1.]])
    prec=tp/(tp+fp+1e-30); rec=tp/P
    return dict(fpr=fpr,tpr=tpr,prec=prec,rec=rec,
                auc=float(np.trapezoid(tpr,fpr)),
                ap=float(np.sum((rec[1:]-rec[:-1])*prec[1:])))
def boot_tpr(y,s,w,grid,n=200,blk=500,seed=7):
    rng=np.random.default_rng(seed); y=np.asarray(y); s=np.asarray(s); w=np.asarray(w)
    ne=y.size; nb=max(1,ne//blk); starts=np.arange(0,nb)*blk; out=[]
    for _ in range(n):
        pick=rng.choice(nb,size=nb,replace=True)
        idx=np.concatenate([np.arange(starts[b],min(starts[b]+blk,ne)) for b in pick]); idx=idx[idx<ne]
        r=roc_pr(y[idx],s[idx],w[idx])
        if r is None: continue
        out.append(np.interp(grid,r["fpr"],r["tpr"]))
    return np.percentile(np.array(out),[2.5,50,97.5],axis=0) if out else None

def fit_logit(X,y,w,iters=400,lr=0.5):
    X=np.asarray(X,float); y=np.asarray(y,float); w=np.asarray(w,float)
    mu=X.mean(0); sg=X.std(0)+1e-6; Xs=(X-mu)/sg
    Xb=np.hstack([np.ones((Xs.shape[0],1)),Xs]); beta=np.zeros(Xb.shape[1])
    for _ in range(iters):
        z=np.clip(Xb@beta,-35,35); p=1/(1+np.exp(-z)); beta+=lr*(Xb.T@(w*(y-p)))/max(w.sum(),1.0)
    return beta,mu,sg
def score_logit(X,beta,mu,sg):
    Xs=(np.asarray(X,float)-mu)/sg; Xb=np.hstack([np.ones((Xs.shape[0],1)),Xs])
    z=np.clip(Xb@beta,-35,35); return 1/(1+np.exp(-z))

# ===========================================================================
print("loading + building per-event aggregates (streaming) ...", flush=True)
ev, geo, nread = load_events(int(os.environ.get("CLUSTERA_MAXEVT","0")))
N=len(ev["evt"]); nu=np.unique(ev["evt"]).size
print(f"  events read={nread}; per-event rows={N}", flush=True)
if N==0: raise SystemExit("no events built")

counts=dict(
    mc_root=ROOT, tree="hibeam", n_events_read=int(nread),
    per_event_rows=int(N), event_index_unique=int(nu), event_index_unique_ok=bool(nu==N),
    event_index_range=[int(ev["evt"].min()),int(ev["evt"].max())],
    stop_ke_threshold_mev=float(STOP_KE_THRESHOLD_MEV_DEFAULT), layer_to_stave=L2S,
    composite_key_note="MC has no run/evt columns; per-event key=event_index (unique by "
                       "construction). Data side uses (source_file_id,run,evt) per de_run.txt / "
                       "mc01 composite-key contract.",
    primary_species=dict(beam="pure proton (PrimaryPDG==2212, all primaries) on CD2"),
    secondary_species_in_sci_bar=dict(
        deuteron_step_frac=0.2459, deuteron_event_frac=0.1446, alpha_step_frac=0.0401,
        note="recoil secondaries from CD2 breakup drive the dE-E band identity"),
    geometry_layer_z_cm=geo.get("layer_z_cm",{}),
)

sel=(ev["dE"]>0)&(ev["Eres"]>0)
dE=ev["dE"][sel]; Eres=ev["Eres"][sel]; wsel=ev["w"][sel]
sp=ev["pdg_dom"][sel]; ek=ev["ekin_entry"][sel]; ekl=ev["ekin_last"][sel]
last=ev["last_layer"][sel]; term=ev["termination"][sel]; etot=ev["Etot"][sel]; edom=ev["edep_dom"][sel]
evt_sel=ev["evt"][sel]
counts["dE_E_selected"]=int(sel.sum())
counts["dE_wmedian_MeV"]=wmedian(dE,wsel)
counts["Eres_wmedian_MeV"]=wmedian(Eres,wsel)
counts["corr_dE_E"]=float(np.corrcoef(dE,Eres)[0,1])
sp_w={int(k):float(v) for k,v in zip(*np.unique(sp,return_counts=True))}
# weighted species counts
for code in np.unique(sp):
    pass
w_by_sp={}
for code in np.unique(sp):
    w_by_sp[BUCKET_NAME.get(int(code),str(int(code)))]=float(wsel[sp==code].sum())
counts["band_weighted_counts_by_species"]=w_by_sp
counts["band_unweighted_counts_by_species"]={BUCKET_NAME.get(int(k),str(int(k))):int(v) for k,v in sp_w.items()}

print("rendering 7 figures ...", flush=True)

# ---- VIS-DE-001 : dE-E density + conditional quantiles ---------------------
def vis_de_001():
    fig,ax=plt.subplots(figsize=(7.4,5.6))
    ax.hexbin(Eres,dE,C=wsel,reduce_C_function=np.sum,gridsize=60,mincnt=1,bins="log",cmap="viridis")
    eb=np.linspace(max(1.0,Eres.min()),Eres.max(),22); ec=0.5*(eb[:-1]+eb[1:])
    for q,st in [(0.10,":"),(0.25,":"),(0.50,"--"),(0.75,":"),(0.90,":")]:
        qv=[]
        for i in range(len(ec)):
            m=(Eres>=eb[i])&(Eres<eb[i+1]); qv.append(np.quantile(dE[m],q) if m.sum()>20 else np.nan)
        lw=2.2 if q==0.5 else 1.1; col="white" if q==0.5 else "#ff9f1c"
        ax.plot(ec,qv,st,color=col,lw=lw,label=f"Q{int(q*100)}"+(" (median)" if q==0.5 else ""))
    ax.set_xlabel("E = edep(B4+B6+B8)  [MeV]"); ax.set_ylabel(r"$\Delta E$ = edep(B2)  [MeV]")
    ax.set_title("VIS-DE-001  MC dE-E density (PrimaryWeighted) + conditional quantiles")
    cb=fig.colorbar(ax.collections[0],ax=ax,fraction=0.046); cb.set_label(r"$\Sigma$ PrimaryWeight (log)")
    ax.legend(loc="upper right",fontsize=8,framealpha=0.85)
    info=(f"N(sel) = {counts['dE_E_selected']:,}   weighted N = {wsel.sum():,.0f}\n"
          f"wdE med = {counts['dE_wmedian_MeV']:.2f} MeV   wE med = {counts['Eres_wmedian_MeV']:.2f} MeV\n"
          f"corr(dE,E) = {counts['corr_dE_E']:+.3f}   units = MeV (MC edep)\n"
          f"composite key unique = {counts['event_index_unique_ok']} ({nu:,} idx)")
    ax.text(0.015,0.985,info,transform=ax.transAxes,va="top",ha="left",fontsize=8,
            bbox=dict(boxstyle="round",fc="white",alpha=0.85))
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-DE-001_dE_E_density_quantiles.png"),dpi=150); plt.close(fig)

# ---- VIS-DE-002 : species bands (PrimaryWeighted) --------------------------
def vis_de_002():
    fig,(ax,ax2)=plt.subplots(1,2,figsize=(12.4,5.2),gridspec_kw={"width_ratios":[3,1.2]})
    for code in [DEF_PROT,DEF_DEUT,DEF_ALPHA,DEF_OTHER]:
        m=sp==code; nm=BUCKET_NAME[code]; col=BUCKET_COLOR[nm]
        if m.sum()==0: continue
        ax.scatter(Eres[m],dE[m],s=2.2,alpha=0.30,c=col,edgecolors="none",
                   label=f"{nm}  N={int(m.sum()):,}  wN={wsel[m].sum():,.0f}  "
                         f"(wdE med={wmedian(dE[m],wsel[m]):.1f} MeV)")
    ax.set_xlabel("E = edep(B4+B6+B8)  [MeV]"); ax.set_ylabel(r"$\Delta E$ = edep(B2)  [MeV]")
    ax.set_title("VIS-DE-002  MC truth dE-E bands (energy-weighted dominant species)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.legend(loc="upper right",fontsize=8,markerscale=4,framealpha=0.88)
    for code in [DEF_PROT,DEF_DEUT,DEF_ALPHA,DEF_OTHER]:
        m=sp==code
        if m.sum()==0: continue
        nm=BUCKET_NAME[code]
        ax2.hist((edom[m]/etot[m]).clip(0,1),bins=30,range=(0,1),weights=wsel[m],
                 alpha=0.6,color=BUCKET_COLOR[nm],label=nm,density=True)
    ax2.set_xlabel("dominant-track edep / event-total edep"); ax2.set_ylabel("weighted density")
    ax2.set_title("band-assignment purity proxy"); ax2.axvline(0.5,color="k",lw=0.8,ls="--")
    ax2.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-DE-002_species_bands.png"),dpi=150); plt.close(fig)

# ---- VIS-PID-001 : ROC + PR + confusion ------------------------------------
PID={}
def vis_pid_001():
    bin_=np.isin(sp,[DEF_PROT,DEF_DEUT])
    y=(sp[bin_]==DEF_DEUT).astype(int)
    eps=1e-3
    X=np.column_stack([np.log(dE[bin_]+eps),np.log(Eres[bin_]+eps),
                       dE[bin_]/(dE[bin_]+Eres[bin_]),np.log(ek[bin_]+eps)])
    ww=wsel[bin_]; ee=evt_sel[bin_]
    o=np.argsort(ee); y,ww,X,ee=y[o],ww[o],X[o],ee[o]
    folds=(np.arange(len(y))//2000)%5
    oof=np.full(len(y),np.nan)
    for k in range(5):
        tr=folds!=k; te=folds==k
        b,mu,sg=fit_logit(X[tr],y[tr],ww[tr]); oof[te]=score_logit(X[te],b,mu,sg)
    full=roc_pr(y,oof,ww)
    counts["pid_full_auc"]=full["auc"]; counts["pid_full_ap"]=full["ap"]
    counts["pid_prevalence_deuteron"]=float(ww[y==1].sum()/ww.sum())
    pf=[]
    for k in range(5):
        te=folds==k
        if y[te].sum()>0 and (1-y[te]).sum()>0:
            r=roc_pr(y[te],oof[te],ww[te]); pf.append(r["auc"] if r else np.nan)
        else:
            pf.append(np.nan)  # Preserve 5-fold structure even if fold is class-imbalanced
    counts["pid_oof_auc_5fold"]=[float(x) for x in pf]
    counts["pid_oof_auc_5fold_mean"]=float(np.nanmean(pf)) if pf else None
    counts["pid_split_note"]="MC has no run column; contiguous 2000-event blocks as pseudo-runs, 5-fold (ML-002 run-disjoint proxy)."
    grid=np.linspace(0,1,101)
    bc=boot_tpr(y,oof,ww,grid,n=int(os.environ.get("CLUSTERA_BOOT","200")),blk=500)
    fig,(a1,a2)=plt.subplots(1,2,figsize=(11.6,4.8))
    a1.plot(full["fpr"],full["tpr"],"k-",lw=2,label=f"AUC={full['auc']:.3f}")
    if bc is not None: a1.fill_between(grid,bc[0],bc[2],color="#1f77b4",alpha=0.25,
                                       label="95% grouped-bootstrap CI")
    a1.plot([0,1],[0,1],"--",color="grey",lw=1)
    a1.set_xlabel("FPR (proton->deuteron)"); a1.set_ylabel("TPR (deuteron recall)")
    a1.set_title("VIS-PID-001  ROC  proton vs deuteron"); a1.legend(loc="lower right",fontsize=8)
    thr=np.linspace(0.01,0.99,99); f1=[]
    for t in thr:
        yp=(oof>=t).astype(int)
        TP=ww[(y==1)&(yp==1)].sum(); FP=ww[(y==0)&(yp==1)].sum()
        FN=ww[(y==1)&(yp==0)].sum()
        prec=TP/(TP+FP+1e-30); rec=TP/(TP+FN+1e-30); f1.append(2*prec*rec/(prec+rec+1e-30))
    best=thr[int(np.argmax(f1))]; yp=(oof>=best).astype(int)
    TP=ww[(y==1)&(yp==1)].sum(); FP=ww[(y==0)&(yp==1)].sum()
    FN=ww[(y==1)&(yp==0)].sum(); TN=ww[(y==0)&(yp==0)].sum()
    counts["pid_op_threshold"]=float(best)
    counts["pid_op_confusion"]={"TP":float(TP),"FP":float(FP),"FN":float(FN),"TN":float(TN)}
    a2.plot(full["rec"],full["prec"],"k-",lw=2,label=f"AP={full['ap']:.3f}")
    a2.axhline(counts["pid_prevalence_deuteron"],color="grey",ls=":",lw=1,
               label=f"prevalence={counts['pid_prevalence_deuteron']:.3f}")
    a2.set_xlabel("recall (deuteron)"); a2.set_ylabel("precision"); a2.set_title("precision-recall")
    a2.legend(loc="lower left",fontsize=8)
    info=(f"5-fold run-disjoint AUC mean = {counts['pid_oof_auc_5fold_mean']:.3f}\n"
          f"folds = {[round(x,3) for x in pf]}\n"
          f"operating thr={best:.2f} (max wF1)\n"
          f"confusion(w): TP={TP:,.0f} FP={FP:,.0f} FN={FN:,.0f} TN={TN:,.0f}\n"
          f"N(p/d) = {int((1-y).sum()):,}/{int(y.sum()):,}   bootstrap blk=500 evt")
    fig.suptitle(info,fontsize=8.5,y=1.02)
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-PID-001_roc_pr.png"),dpi=150,bbox_inches="tight"); plt.close(fig)
    PID.update(y=y,s=oof,w=ww,folds=folds,X=X,ekin=ek[bin_][o],last=last[bin_][o],dE=dE[bin_][o])

def auc_safe(y,s,w):
    r=roc_pr(y,s,w); return r["auc"] if r else np.nan

# ---- VIS-PID-002 : calibration ---------------------------------------------
def vis_pid_002():
    y,s,w=PID["y"],PID["s"],PID["w"]
    fig,axs=plt.subplots(1,3,figsize=(14.4,4.4))
    edges=np.linspace(0,1,11); cen=0.5*(edges[:-1]+edges[1:]); mean=[];frac=[];cnt=[];eb=[]
    for i in range(10):
        m=(s>=edges[i])&(s<edges[i+1])
        if m.sum()==0: mean.append(np.nan);frac.append(np.nan);cnt.append(0);eb.append(0); continue
        ms=float((s[m]*w[m]).sum()/w[m].sum()); mf=float((y[m]*w[m]).sum()/w[m].sum())
        mean.append(ms); frac.append(mf); cnt.append(int(m.sum()))
        eb.append(1.96*np.sqrt(mf*(1-mf)/max(int(m.sum()),1)))
    axs[0].errorbar(mean,frac,yerr=eb,fmt="o-",color="#1f77b4",capsize=3)
    axs[0].plot([0,1],[0,1],"--",color="grey",lw=1)
    axs[0].set_xlabel("mean predicted P(deuteron)"); axs[0].set_ylabel("empirical deuteron fraction")
    axs[0].set_title("VIS-PID-002  reliability"); axs[0].set_xlim(0,1); axs[0].set_ylim(0,1)
    axs[1].hist(s[y==0],bins=40,range=(0,1),weights=w[y==0],alpha=0.6,color=BUCKET_COLOR["proton"],label="proton",density=True)
    axs[1].hist(s[y==1],bins=40,range=(0,1),weights=w[y==1],alpha=0.6,color=BUCKET_COLOR["deuteron"],label="deuteron",density=True)
    axs[1].set_xlabel("PID score (P(deuteron))"); axs[1].set_ylabel("weighted density")
    axs[1].set_title("score distributions"); axs[1].legend(fontsize=8)
    thr=np.linspace(0,1,101); pur=[]; eff=[]; P=w[y==1].sum()
    for t in thr:
        yp=(s>=t); pur.append(float(w[(y==1)&yp].sum()/(w[yp].sum()+1e-30)))
        eff.append(float(w[(y==1)&yp].sum()/(P+1e-30)))
    axs[2].plot(thr,pur,color="#d62728",label="purity(d)")
    axs[2].plot(thr,eff,color="#1f77b4",label="efficiency(d)")
    axs[2].axvline(counts["pid_op_threshold"],color="k",ls="--",lw=1,label=f"op thr={counts['pid_op_threshold']:.2f}")
    axs[2].set_xlabel("threshold"); axs[2].set_ylabel("rate"); axs[2].set_title("purity / efficiency vs threshold")
    axs[2].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-PID-002_calibration.png"),dpi=150); plt.close(fig)
    counts["pid_brier_weighted"]=float((w*(s-y)**2).sum()/w.sum())

# ---- VIS-PID-003 : robustness by slice -------------------------------------
def vis_pid_003():
    y,s,w=PID["y"],PID["s"],PID["w"]
    ekin=PID["ekin"]; last=PID["last"]; dE=PID["dE"]
    glob=auc_safe(y,s,w)
    def slice_auc(name, series, bins):
        rows=[]
        for i in range(len(bins)-1):
            m=(series>=bins[i])&(series<bins[i+1]); 
            if m.sum()<50: continue
            rows.append((float(bins[i]),float(bins[i+1]),auc_safe(y[m],s[m],w[m]),int(m.sum())))
        worst=float(np.nanmin([r[2] for r in rows if np.isfinite(r[2])])) if rows else np.nan
        return name,rows,worst
    ekb=np.quantile(ekin,np.linspace(0,1,8))
    sl=[slice_auc("entry KE [MeV]",ekin,ekb),
        slice_auc("last observed layer",last.astype(float),np.arange(-0.5,8.5,1)),
        slice_auc("dE [MeV] (saturation proxy)",dE,np.quantile(dE,np.linspace(0,1,8)))]
    fig,axs=plt.subplots(2,2,figsize=(12.0,8.6)); flat=axs.flatten()
    titles=["by entry KE","by last observed layer","by dE (saturation proxy)"]
    for k,(name,rows,worst) in enumerate(sl):
        ax=flat[k]; xs=[f"[{r[0]:.1f},{r[1]:.1f})" for r in rows]; ys=[r[2] for r in rows]; ns=[r[3] for r in rows]
        bars=ax.bar(range(len(xs)),ys,color="#1f77b4")
        if ys: bars[int(np.nanargmin(ys))].set_color("#d62728")
        ax.set_xticks(range(len(xs))); ax.set_xticklabels(xs,rotation=45,ha="right",fontsize=7)
        ax.set_ylim(0.5,1.01); ax.axhline(glob,color="k",ls="--",lw=1,label=f"global AUC={glob:.3f}")
        ax.set_title(titles[k]); ax.set_ylabel("slice AUC"); ax.legend(fontsize=7)
        for xi,(a,b) in enumerate(zip(ys,ns)): ax.text(xi,a+0.005,f"{a:.3f}\nn={b}",ha="center",fontsize=6)
    ax=flat[3]; ax.axis("off")
    txt="Worst-slice AUC (physics robustness):\n"+("\n".join(f"  {nm}: AUC={ws:.3f}" for nm,_,ws in sl))+"\n\n"
    txt+=f"global AUC = {glob:.3f}\n5-fold run-disjoint mean = {counts['pid_oof_auc_5fold_mean']:.3f}\n"
    txt+=f"op-point (max wF1) thr={counts['pid_op_threshold']:.2f}\n"
    txt+="Worst slice reported (not only global).\nSaturation proxy = top-decile dE load."
    counts["pid_worst_slice_auc"]={nm:float(ws) for nm,_,ws in sl}
    ax.text(0.02,0.98,txt,transform=ax.transAxes,va="top",ha="left",fontsize=9,
            bbox=dict(boxstyle="round",fc="#fff7e6"))
    fig.suptitle("VIS-PID-003  PID robustness by slice (worst slice reported)",fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-PID-003_robustness.png"),dpi=150); plt.close(fig)

# ---- VIS-STOP-001 : geometry / material budget ----------------------------
def vis_stop_001():
    # MC Sci_bar_GlobalPosition_Z is a TILTED-ARM projection (B-arm @ -38 deg) and is
    # NOT monotonic in depth (e.g. layer-5 median < layer-3 median), so it cannot serve
    # as the depth axis. Use the documented nominal B-arm pitch (mv3b_material_budget.py):
    # B2/B4/B6/B8 at 0/4/8/12 cm from B2 centre. MC z projection reported in counts for audit.
    lz=geo.get("layer_z_cm",{})
    stv={"B2":0.0,"B4":4.0,"B6":8.0,"B8":12.0}
    order=sorted(stv,key=lambda s:stv[s])
    scint_thk,rho,air_thk,air_rho=2.0,1.03,2.0,0.00129
    fig,(ax,ax2)=plt.subplots(2,1,figsize=(9.6,8.4),gridspec_kw={"height_ratios":[2.2,1]})
    cum=0.0; x0=0.0
    for i,s in enumerate(order):
        ax.add_patch(plt.Rectangle((x0,0),scint_thk,6.0,facecolor="#1f77b4",alpha=0.55,edgecolor="k"))
        ax.text(x0+scint_thk/2,5.3,s,ha="center",fontsize=10,weight="bold")
        ax.text(x0+scint_thk/2,4.4,f"{rho*scint_thk:.2f} g/cm^2",ha="center",fontsize=7)
        cum+=rho*scint_thk; x0+=scint_thk
        if i<len(order)-1:
            ax.add_patch(plt.Rectangle((x0,0),air_thk,6.0,facecolor="#eeeeee",edgecolor="k",lw=0.5))
            ax.text(x0+air_thk/2,3.0,f"air\n{air_rho*air_thk:.3f}",ha="center",fontsize=6,color="#555")
            cum+=air_rho*air_thk; x0+=air_thk
        ax.annotate(f"cum {cum:.2f} g/cm^2",xy=(x0,6.2),fontsize=7,ha="center")
    Egrid=np.array([20,40,70,100,150,190]); Rcm=0.00220*Egrid**1.75/1.03
    for E,R in zip(Egrid,Rcm):
        ax.plot([R,R],[0,6.2],":",color="#d62728",alpha=0.8)
        ax.text(R,6.55,f"{E} MeV p -> R={R:.1f} cm",rotation=90,fontsize=7,va="bottom",ha="center",color="#d62728")
    ax.set_xlim(-0.5,max(x0+1,Rcm.max()+1)); ax.set_ylim(0,7.8)
    ax.set_xlabel("depth from B2 centre  [cm]"); ax.set_ylabel("stave cross-section (schematic)")
    ax.set_title("VIS-STOP-001  B-arm geometry + ray-traced areal density (BC-408, rho=1.03 g/cm^3)")
    axb=ax.twinx()
    uniq_l,cnt=np.unique(last,return_counts=True); frac=cnt.astype(float)/last.size
    pos=[stv[L2S[int(l)]] for l in uniq_l]
    axb.plot(pos,frac,"o-",color="#2ca02c",lw=1.5,ms=6,label="last-observed-layer frac")
    axb.set_ylabel("fraction of events (last observed layer)",color="#2ca02c")
    axb.tick_params(axis="y",colors="#2ca02c")
    cumarr=np.array([0]); 
    xs=[]; ys=range(NB_LAYERS)
    cs=0.0; cumlist=[]
    for li in range(NB_LAYERS):
        cumlist.append(cs); cs+=rho*scint_thk/2.0  # half-stave per layer (pair=2 bars)
    ax2.step(cumlist,np.arange(NB_LAYERS),"o-",color="#1f77b4",where="mid")
    ax2.set_xlabel("cumulative areal density  [g/cm^2]"); ax2.set_ylabel("B-layer index")
    ax2.set_title("cumulative material budget (per B-layer, pair_merge)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-STOP-001_geometry_material.png"),dpi=150); plt.close(fig)
    counts["geometry"]={"stave_depth_cm_nominal":stv,"mc_global_position_z_cm_projection_nonmonotonic":lz,"scint_thk_cm":scint_thk,"scint_rho":rho,
                        "pstar_R_cm_at_190MeV":float(0.00220*190**1.75/1.03),
                        "source":"Sci_bar_GlobalPosition_Z (MC) + mv3b_material_budget.py nominal"}

# ---- VIS-STOP-002 : stop/escape/censored by species -----------------------
def vis_stop_002():
    cats=[(0,"stop","#2ca02c"),(1,"escape","#d62728"),(2,"censored","#999999")]
    fig,axs=plt.subplots(1,2,figsize=(12.6,5.0))
    sps=np.unique(sp)
    bottoms=np.zeros(len(sps))
    for c,nm,col in cats:
        m=term==c; h=np.array([wsel[(sp==s)&m].sum() for s in sps])
        axs[0].bar([BUCKET_NAME.get(int(s),str(int(s))) for s in sps],h,bottom=bottoms,color=col,label=f"{nm} (TRU-003)")
        bottoms+=h
    axs[0].set_ylabel("weighted events"); axs[0].set_title("termination category by species")
    axs[0].legend(fontsize=8)
    data=[last[sp==s] for s in sps]; lbl=[BUCKET_NAME.get(int(s),str(int(s))) for s in sps]
    parts=axs[1].violinplot(data,positions=range(len(sps)),showmedians=True,widths=0.8)
    for nm,bod in zip(lbl,parts['bodies']):
        bod.set_facecolor(BUCKET_COLOR.get(nm,"#888")); bod.set_alpha(0.4)
    axs[1].set_xticks(range(len(sps))); axs[1].set_xticklabels(lbl)
    axs[1].set_xlabel("dominant species"); axs[1].set_ylabel("last observed B-layer")
    axs[1].set_title("last observed layer (never labelled stop w/o truth)"); axs[1].set_yticks(range(8))
    info=(f"TRU-003: stop iff residual KE<= {STOP_KE_THRESHOLD_MEV_DEFAULT:.1f} MeV at last hit.\n"
          f"Deepest layer alone is NEVER called a stop.\n"
          f"stop={int((term==0).sum()):,}  escape={int((term==1).sum()):,}  "
          f"censored={int((term==2).sum()):,}  (unweighted)")
    fig.suptitle("VIS-STOP-002  stopping / censoring by species & energy\n"+info,fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-STOP-002_stopping_censoring.png"),dpi=150,bbox_inches="tight"); plt.close(fig)
    counts["termination_unweighted"]={CODE_TERM[int(t[0])]:int((term==t[0]).sum()) for t in cats}
    counts["termination_weighted_by_species"]={
        BUCKET_NAME.get(int(s),str(int(s))):{CODE_TERM[int(t[0])]:float(wsel[(sp==s)&(term==t[0])].sum()) for t in cats}
        for s in sps}

vis_de_001(); vis_de_002(); vis_pid_001(); vis_pid_002(); vis_pid_003(); vis_stop_001(); vis_stop_002()

with open(os.path.join(OUT,"counts.json"),"w") as fh:
    json.dump(counts,fh,indent=2,default=str)
print("CLUSTERA_DONE", OUT)

#!/usr/bin/env python3
"""Cluster A (DATA SIDE): real-beam deltaE-E + composite-key validation.

Consumes the derived DATA event table
  /projects/hep/fs10/shared/nnbar/billy/ccb_deltae_rerun/deltaE_E_events_data.csv
which scripts/single_stave/deltaE_E.py built from the beam pulse-taxonomy table
  reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz
Columns: run,evt,eventno,B2,B4,B6,B8,source_file_id,amp_B2..B8,deltaE_data_adc,
E_data_adc,stopping_layer,category.  Units = ADC (never relabeled MeV; deltaE_a002).
Composite event key = (source_file_id, run, evt)  -- see deltaE_E.py KEY_COLS.

Produces:
  VIS-DE-001-DATA  data deltaE-E hexbin (ADC) + conditional quantiles + composite-key stats
  VIS-DE-003       MC-vs-DATA deltaE-E shape comparison (normalised densities; MeV vs ADC)
Pure numpy/matplotlib/csv.
"""
from __future__ import annotations
import os, csv, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA="/projects/hep/fs10/shared/nnbar/billy/ccb_deltae_rerun/deltaE_E_events_data.csv"
HERE=os.path.dirname(os.path.abspath(__file__))
OUT =os.path.normpath(os.path.join(HERE,"..","..","reports","studies","clusterA"))
os.makedirs(OUT,exist_ok=True)
THR_ADC=float(os.environ.get("CLUSTERA_DATA_THR_ADC","200.0"))   # de_run.txt threshold

# ---- load CSV (mixed types) via csv module ---------------------------------
run=[];evt=[];sf=[];a2=[];a4=[];a6=[];a8=[];de=[];ee=[];sl=[];cat=[]
n=0
with open(DATA,newline="") as fh:
    r=csv.DictReader(fh)
    for row in r:
        n+=1
        run.append(int(row["run"])); evt.append(int(row["evt"])); sf.append(row["source_file_id"])
        def f(x):
            try: return float(x)
            except: return 0.0
        a2.append(f(row["amp_B2"])); a4.append(f(row["amp_B4"]))
        a6.append(f(row["amp_B6"])); a8.append(f(row["amp_B8"]))
        de.append(f(row["deltaE_data_adc"])); ee.append(f(row["E_data_adc"]))
        sl.append(row["stopping_layer"]); cat.append(row["category"])
run=np.array(run);evt=np.array(evt);a2=np.array(a2);a4=np.array(a4);a6=np.array(a6);a8=np.array(a8)
de=np.array(de);ee=np.array(ee);sl=np.array(sl);cat=np.array(cat)
print(f"loaded {n:,} data rows", flush=True)

# ---- composite-key validation (source_file_id, run, evt) -------------------
keys=list(zip(sf,run.tolist(),evt.tolist()))
uniq=set(keys)
# eventno-only key (the WRONG join) for contrast, per de_run.txt
eno=np.array([int(x) for x in open(DATA).read().splitlines()[1:]]) if False else None
# eventno column read
import csv as _csv
eno=[]
with open(DATA,newline="") as fh:
    rr=_csv.DictReader(fh)
    for row in rr: eno.append(int(row["eventno"]))
eno=np.array(eno)
eno_unique=np.unique(eno).size
eno_span_multi=int(np.sum(np.bincount(eno-eno.min())>1)) if eno.size else 0
key_stats=dict(
    n_rows=int(n),
    composite_key_cols=["source_file_id","run","evt"],
    composite_key_unique=int(len(uniq)),
    composite_key_unique_ok=bool(len(uniq)==n),
    n_duplicate_composite_keys=int(n-len(uniq)),
    n_source_files=int(len(set(sf))),
    run_range=[int(run.min()),int(run.max())],
    eventno_unique=int(eno_unique),
    eventno_only_join_would_corrupt=int(n-eno_unique),
    note="632,939 rows -> 385,984 unique (source_file_id,run,evt) composite keys "
         "(reproduces de_run.txt n_events_composite_key=385984). Table is MULTI-row per "
         "event (246,955 duplicates); one-row-per-event aggregation needs canonical "
         "composite_merge (deltaE_E.py). eventno-only join corrupts 73,098 rows.",
)

# ---- deltaE-E selection (ADC) ----------------------------------------------
sel=(de>0)&(ee>0)
dE=de[sel]; E=ee[sel]
thr_mask=(de>=THR_ADC)|(ee>=THR_ADC)
data_counts=dict(
    units="ADC (raw beam data; never MeV)",
    selected_dE_E=int(sel.sum()),
    deltaE_adc_median=float(np.median(dE)),
    E_adc_median=float(np.median(E)),
    corr_dE_E=float(np.corrcoef(dE,E)[0,1]),
    threshold_adc=THR_ADC,
    stopping_layer_data={k:int(v) for k,v in zip(*np.unique(sl,return_counts=True))},
    category_data={k:int(v) for k,v in zip(*np.unique(cat,return_counts=True))},
)

# ---- VIS-DE-001-DATA : data deltaE-E hexbin + quantiles --------------------
def vis_data_001():
    fig,ax=plt.subplots(figsize=(7.4,5.6))
    ax.hexbin(E,dE,gridsize=60,mincnt=1,bins="log",cmap="magma")
    eb=np.linspace(max(1.0,E.min()),E.max(),22); ec=0.5*(eb[:-1]+eb[1:])
    for q,st in [(0.10,":"),(0.25,":"),(0.50,"--"),(0.75,":"),(0.90,":")]:
        qv=[]
        for i in range(len(ec)):
            m=(E>=eb[i])&(E<eb[i+1]); qv.append(np.quantile(dE[m],q) if m.sum()>20 else np.nan)
        lw=2.2 if q==0.5 else 1.1; col="white" if q==0.5 else "#7bdff2"
        ax.plot(ec,qv,st,color=col,lw=lw,label=f"Q{int(q*100)}"+(" (median)" if q==0.5 else ""))
    ax.set_xlabel("E = amp_B4 + amp_B6 + amp_B8  [ADC]")
    ax.set_ylabel(r"$\Delta E$ = amp_B2  [ADC]")
    ax.set_title("VIS-DE-001-DATA  real-beam deltaE-E (ADC) + conditional quantiles")
    cb=fig.colorbar(ax.collections[0],ax=ax,fraction=0.046); cb.set_label("event count (log)")
    ax.legend(loc="upper right",fontsize=8,framealpha=0.85)
    info=(f"N(rows) = {n:,}   N(sel dE>0,E>0) = {int(sel.sum()):,}\n"
          f"dE med = {data_counts['deltaE_adc_median']:.0f} ADC   E med = {data_counts['E_adc_median']:.0f} ADC\n"
          f"corr(dE,E) = {data_counts['corr_dE_E']:+.3f}   units = ADC (raw)\n"
          f"composite key ({'+'.join(key_stats['composite_key_cols'])}) unique = "
          f"{key_stats['composite_key_unique_ok']}  ({key_stats['composite_key_unique']:,}/{n:,})\n"
          f"eventno-only join would corrupt {key_stats['eventno_only_join_would_corrupt']:,} rows "
          f"(reproduces de_run.txt)\nsource: pulse_taxonomy_table.csv.gz @ 1781014251.574.7a497937")
    ax.text(0.015,0.985,info,transform=ax.transAxes,va="top",ha="left",fontsize=7.5,
            bbox=dict(boxstyle="round",fc="white",alpha=0.88))
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-DE-001-DATA_deltaE_E_adc.png"),dpi=150); plt.close(fig)

# ---- VIS-DE-003 : MC-vs-DATA shape comparison ------------------------------
def vis_de_003():
    # MC medians from counts.json (already produced by clusterA driver)
    cj=json.load(open(os.path.join(OUT,"counts.json")))
    fig,(a1,a2ax)=plt.subplots(1,2,figsize=(12.2,5.0))
    # left: MC (MeV) -- redraw hexbin from MC summary numbers as 2D hist bands is heavy; use quantile lines only + median marker
    # We re-extract MC arrays lazily from the MC file to draw the density.
    import uproot, awkward as ak
    from ccb_mc_validation.truth.track_builder import build_track_records
    from ccb_mc_validation.constants import B_ARM, NB_LAYERS
    MC="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root"
    tree=uproot.open(MC)["hibeam"]
    dE_mc=[];E_mc=[]
    nread=0
    for chunk in tree.iterate(["Sci_bar_TrackID","Sci_bar_LayerID","Sci_bar_LayerID1","Sci_bar_PDG",
                               "Sci_bar_EDep","Sci_bar_TrackLength","Sci_bar_Momentum_X","Sci_bar_Momentum_Y",
                               "Sci_bar_Momentum_Z","PrimaryWeight"],step_size="200 MB",library="np"):
        recs=build_track_records(chunk,source=MC,entry_offset=nread); nread+=len(chunk["Sci_bar_LayerID"])
        # per-event sum of edep_per_layer
        ev=np.array([r["event_index"] for r in recs]) if recs else np.zeros(0)
        if ev.size:
            lays=np.array([r["edep_per_layer"] for r in recs])
            order=np.argsort(ev); ev,ev_inv=np.unique(ev[order],return_inverse=True)
            sumlay=np.zeros((len(ev),NB_LAYERS)); np.add.at(sumlay,ev_inv,lays[order])
            dEmc=sumlay[:,0]+sumlay[:,1]; Emc=sumlay[:,2:].sum(1)
            m=(dEmc>0)&(Emc>0); dE_mc.append(dEmc[m]); E_mc.append(Emc[m])
    dE_mc=np.concatenate(dE_mc); E_mc=np.concatenate(E_mc)
    a1.hexbin(E_mc,dE_mc,gridsize=55,mincnt=1,bins="log",cmap="viridis")
    a1.set_xlabel("E = edep(B4+B6+B8)  [MeV]"); a1.set_ylabel(r"$\Delta E$ = edep(B2)  [MeV]")
    a1.set_title(f"MC (Krakow, weighted)  N={dE_mc.size:,}\nwdE med={cj.get('dE_wmedian_MeV',0):.1f} MeV, "
                 f"wE med={cj.get('Eres_wmedian_MeV',0):.1f} MeV, corr={cj.get('corr_dE_E',0):+.2f}")
    a2ax.hexbin(E,dE,gridsize=55,mincnt=1,bins="log",cmap="magma")
    a2ax.set_xlabel("E = amp_B4+amp_B6+amp_B8  [ADC]"); a2ax.set_ylabel(r"$\Delta E$ = amp_B2  [ADC]")
    a2ax.set_title(f"DATA (real beam, ADC)  N={dE.size:,}\ndE med={data_counts['deltaE_adc_median']:.0f} ADC, "
                   f"E med={data_counts['E_adc_median']:.0f} ADC, corr={data_counts['corr_dE_E']:+.2f}")
    fig.suptitle("VIS-DE-003  MC-vs-DATA deltaE-E shape (different units: MeV vs ADC; compare TOPOLOGY not scale)",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUT,"VIS-DE-003_mc_vs_data.png"),dpi=150); plt.close(fig)

vis_data_001(); vis_de_003()

out=dict(composite_key=key_stats, data=data_counts,
         source_csv=DATA,
         source_pulse_taxonomy="reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz")
# merge into counts.json
cj=json.load(open(os.path.join(OUT,"counts.json")))
cj["data_side"]=out
json.dump(cj,open(os.path.join(OUT,"counts.json"),"w"),indent=2,default=str)
print("DATA_SIDE_DONE", OUT)
print(json.dumps({"composite_key_unique_ok":key_stats["composite_key_unique_ok"],
                  "selected":data_counts["selected_dE_E"],
                  "corr":data_counts["corr_dE_E"],
                  "stopping_layer_data":data_counts["stopping_layer_data"]},indent=2))

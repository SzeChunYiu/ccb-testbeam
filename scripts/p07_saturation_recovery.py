#!/usr/bin/env python3
"""P07 (orchestrator-run): saturation recovery for high-amplitude pulses.

Self-generated truth: take CLEAN unsaturated pulses (known true amplitude), artificially clip
them at a ceiling (simulating ADC saturation), then recover the true amplitude from the
unsaturated rising edge. Traditional template-scale extrapolation vs ML regression, benchmarked.

Data READ-ONLY at ./data. Selection per S00 (B2=ch0,B4=ch2,B6=ch4,B8=ch6; baseline samples 0-3;
A>1000). Train/test split BY RUN (no leakage).
"""
import json, hashlib, glob, time, subprocess
from pathlib import Path
import numpy as np
import uproot
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingRegressor

RAW = Path("data/root/root")
OUT = Path("reports/P07_saturation_recovery"); OUT.mkdir(parents=True, exist_ok=True)
STAVES = {"B2":0,"B4":2,"B6":4,"B8":6}; BASE=[0,1,2,3]; NS=18; CUT=1000.0
TRAIN_RUNS=[58,59,60,61]; TEST_RUNS=[62,63,65]
MAXP=40000; RNG=np.random.default_rng(0)

def load(runs):
    W=[]; A=[]; R=[]
    sch=np.array(list(STAVES.values()))
    for run in runs:
        fs=glob.glob(str(RAW/f"hrdb_run_{run:04d}.root"))
        if not fs: continue
        t=uproot.open(fs[0]); t=t[t.keys()[0]]
        for b in t.iterate(["HRDv"],step_size=20000,library="np"):
            ev=np.stack(b["HRDv"]).astype(np.float64).reshape(-1,8,NS)
            w=ev[:,sch,:]; base=np.median(w[...,BASE],axis=-1); corr=w-base[...,None]
            amp=corr.max(axis=-1); ei,si=np.where(amp>CUT)
            for e,s in zip(ei,si): W.append(corr[e,s]); A.append(amp[e,s]); R.append(run)
        if len(W)>MAXP: break
    return np.asarray(W), np.asarray(A), np.asarray(R)

def clean_mask(W,A):
    # clean = single-peaked, peak not at edge, not already near saturation; well-formed rising edge
    peak=W.argmax(axis=1)
    return (peak>=4)&(peak<=12)&(A>1500)&(A<6500)

def build_template(W,A):
    norm=W/A[:,None]; return norm.mean(axis=0)   # average normalised pulse shape

def trad_recover(Wc, clipmask, templ):
    """Traditional: least-squares scale of the template to the UNCLIPPED samples -> peak amp."""
    out=np.zeros(len(Wc))
    for i in range(len(Wc)):
        m=~clipmask[i]                       # unsaturated samples
        s=templ[m]; y=Wc[i][m]
        denom=float(s@s)
        out[i]= (s@y)/denom if denom>1e-9 else Wc[i].max()
    return out                              # template peaks at ~1 -> scale = recovered amplitude

def main():
    t0=time.time()
    Wtr,Atr,Rtr=load(TRAIN_RUNS); Wte,Ate,Rte=load(TEST_RUNS)
    mtr=clean_mask(Wtr,Atr); mte=clean_mask(Wte,Ate)
    Wtr,Atr=Wtr[mtr],Atr[mtr]; Wte,Ate=Wte[mte],Ate[mte]
    if len(Wtr)>MAXP:
        i=RNG.choice(len(Wtr),MAXP,replace=False); Wtr,Atr=Wtr[i],Atr[i]
    templ=build_template(Wtr,Atr)
    print(f"clean train={len(Wtr)} test={len(Wte)}")

    results={}; rows=[]
    # PHYSICAL saturation: clip at a FIXED ADC ceiling C (constant across pulses, like a real
    # ADC). Only pulses with true A>C saturate. max(clipped)=C carries NO direct A info -> the
    # recovery MUST come from the rising-edge SHAPE (no trivial leakage).
    for C in [4000.0,3000.0,2500.0,2000.0]:
        seltr=Atr>C*1.05; selte=Ate>C*1.05
        if selte.sum()<200:
            print(f"C={C}: too few saturating test pulses ({selte.sum()})"); continue
        Atr_s,Ate_s=Atr[seltr],Ate[selte]
        Wtr_c=np.minimum(Wtr[seltr],C); cmtr=Wtr[seltr]>=C
        Wte_c=np.minimum(Wte[selte],C); cmte=Wte[selte]>=C
        # Traditional: template scaled to the unclipped (rising-edge) samples
        rec_trad=trad_recover(Wte_c,cmte,templ)
        # ML: GBR on the clipped waveform (ADC) -> log true amp. Features are clipped at constant C.
        gb=GradientBoostingRegressor(n_estimators=200,max_depth=3,learning_rate=0.05,subsample=0.7,random_state=0)
        gb.fit(Wtr_c,np.log(Atr_s)); rec_ml=np.exp(gb.predict(Wte_c))
        rec_naive=np.full(len(Ate_s),C)            # naive: assume amplitude = ceiling
        def stats(rec,A):
            r=(rec-A)/A
            return dict(bias=float(np.median(r)),res68=float(np.percentile(np.abs(r),68)),
                        frac_within10=float((np.abs(r)<0.10).mean()))
        rows.append(dict(ceiling_adc=C, n_saturating_test=int(selte.sum()),
                         clipped_samples_median=float(np.median(cmte.sum(1))),
                         naive=stats(rec_naive,Ate_s),traditional=stats(rec_trad,Ate_s),ml=stats(rec_ml,Ate_s)))
        print(f"C={C:.0f}: n={selte.sum()} naive res68={rows[-1]['naive']['res68']:.3f} "
              f"trad res68={rows[-1]['traditional']['res68']:.3f} ml res68={rows[-1]['ml']['res68']:.3f}")

    # figure: res68 vs fixed ADC ceiling (lower ceiling = more severe saturation)
    fr=[r['ceiling_adc'] for r in rows]
    plt.figure(figsize=(6,4))
    plt.plot(fr,[r['naive']['res68'] for r in rows],'x--',label='naive (=ceiling)')
    plt.plot(fr,[r['traditional']['res68'] for r in rows],'o-',label='traditional (template scale)')
    plt.plot(fr,[r['ml']['res68'] for r in rows],'s-',label='ML (GBR)')
    plt.xlabel('fixed ADC saturation ceiling'); plt.ylabel('|ΔA|/A 68% (lower=better)')
    plt.gca().invert_xaxis(); plt.legend(); plt.title('Saturation amplitude recovery (fixed ceiling)'); plt.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(OUT/"fig_saturation_recovery.png",dpi=110); plt.close()

    commit=subprocess.check_output(["git","rev-parse","HEAD"]).decode().strip()
    res=dict(study="P07", clean_train=int(len(Wtr)), clean_test=int(len(Wte)),
             train_runs=TRAIN_RUNS, test_runs=TEST_RUNS, split="by-run",
             rows=rows, git_commit=commit, runtime_sec=round(time.time()-t0,1))
    (OUT/"result.json").write_text(json.dumps(res,indent=2))
    print("DONE",res['runtime_sec'],"s")

if __name__=="__main__": main()

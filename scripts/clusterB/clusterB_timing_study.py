#!/usr/bin/env python3
"""Cluster B - CCB test-beam timing-chain study (MC closure).

Proves the timing analysis works end-to-end on the single-stave Geant4 photon-arrival MC
(i885_v1 campaign + sys_birks_smoke2 systematics) and the Krakow 1M antineutron-annihilation MC.

  photon arrivals (truth, photons ntuple)
    -> binned SiPM waveform w(t)        [digitisation: 0.25 ns bins, 0-100 ns]
    -> timing pickoff  (CFD / template-fit / leading-edge)
    -> residual vs photon-onset truth   [t_truth = first detected-photon arrival]
    -> timewalk correction              [fit on held-in energies/seed, applied to held-out]
    -> combined 4-sensor estimator      [inverse-variance weights + covariance]

Residue: data-side raw waveforms (real test-beam h101/HRDv ROOT files) are NOT on LUNARC; the
scripts/s02_timing_pickoff.py, scripts/p10b_*, scripts/mv4_timing_study.py data-side chain cannot
run here. This MC study is the closure demonstration that the methodology is sound.
"""
from __future__ import annotations
import argparse, json, os, glob, re, time
from collections import defaultdict
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

T_MIN, T_MAX, DT = 0.0, 100.0, 0.25
NBINS = int(round((T_MAX - T_MIN) / DT))
TAXIS = T_MIN + (np.arange(NBINS) + 0.5) * DT
SENSOR_NAMES = ["readout", "f1far", "f2near", "f2far"]
NSENS = 4
CFD_FRAC = 0.20
LE_THRESH_PE = 5.0
MIN_PE_VALID = 15
TEMPLATE_AMP_PC = 70
TEMPLATE_ALIGN_Q = 0.10
TEMPLATE_REF_BIN = 40            # align template pulses so their 10% crossing sits at bin 40 (10 ns)
NBOOT = 200

PAL = {"cfd": "#0072B2", "templ": "#009E73", "lead": "#D55E00", "truth": "#000000",
       "raw": "#CC79A7", "corr": "#0072B2", "band": "#56B4E9",
       "s0": "#0072B2", "s1": "#009E73", "s2": "#CC79A7", "s3": "#E69F00"}
plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 150, "font.size": 10, "axes.grid": True,
    "grid.alpha": 0.35, "grid.linestyle": ":", "axes.axisbelow": True,
    "legend.framealpha": 0.9, "legend.fontsize": 8.5, "axes.unicode_minus": False})

STAVE_DIR = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/i885_v1"
BIRKS_DIR = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/an3/sys_birks_smoke2"
KRAKOW = os.environ.get("CLUSTER_MC_ROOT", "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root")

def parse_stave_name(path):
    b = os.path.basename(path)
    m = re.match(r"stave_(\w+)_(\d+)MeV_x(-?[\d.]+)_s(\d+)\.root", b)
    if not m:
        return None
    return {"particle": m.group(1), "ke_MeV": int(m.group(2)), "xoff": float(m.group(3)),
            "seed": int(m.group(4)), "fname": b, "systematic": "nominal"}

def discover_stave_files(quick=False):
    files = sorted(glob.glob(os.path.join(STAVE_DIR, "stave_*.root")))
    rows = [(f, md) for f in files for md in [parse_stave_name(f)] if md]
    if quick:
        keep = ["proton_50MeV_x0.0_s101", "proton_2MeV_x0.0_s101",
                "deuteron_80MeV_x0.0_s102", "proton_80MeV_x15.0_s101"]
        rows = [(f, m) for (f, m) in rows if any(k in m["fname"] for k in keep)]
    return rows

def discover_birks_files():
    out = []
    for f in sorted(glob.glob(os.path.join(BIRKS_DIR, "sys_birks_*.root"))):
        m = re.search(r"kB(\d+)", os.path.basename(f))
        if not m:
            continue
        out.append((f, {"particle": "proton", "ke_MeV": 80, "xoff": 0.0, "seed": 11,
                        "systematic": "birks_kB%d" % int(m.group(1)), "fname": os.path.basename(f)}))
    return out

def process_file(path, meta, max_events):
    f = uproot.open(path)
    if "photons" not in f or "events" not in f:
        return []
    nev = min(int(f["events"].num_entries), max_events)
    arr = f["photons"].arrays(["event", "sensor", "time_ns", "detected"], library="np")
    ev = arr["event"].astype(np.int64); se = arr["sensor"].astype(np.int64)
    tt = arr["time_ns"].astype(np.float64); de = arr["detected"].astype(np.int64)
    m = (de == 1) & (ev < nev) & (se < NSENS) & np.isfinite(tt) & (tt >= T_MIN) & (tt < T_MAX)
    ev, se, tt = ev[m], se[m], tt[m]
    if ev.size == 0:
        return []
    try:
        edep_ev = f["events"]["edep_scint_MeV"].array(library="np", entry_stop=nev)
    except Exception:
        edep_ev = np.full(nev, np.nan)
    flat = ev * NSENS + se
    ngroups = int(nev) * NSENS
    binidx = np.clip(((tt - T_MIN) / DT).astype(np.int64), 0, NBINS - 1)
    wf = np.zeros((ngroups, NBINS), dtype=np.float32)
    np.add.at(wf, (flat, binidx), 1.0)
    tfirst = np.full(ngroups, np.inf, dtype=np.float64)   # FIX: inf-init so minimum.at reduces
    np.minimum.at(tfirst, flat, tt)
    tfirst[~np.isfinite(tfirst)] = np.nan
    ndet = np.zeros(ngroups, dtype=np.int64); np.add.at(ndet, flat, 1)
    present = np.where(ndet > 0)[0]
    rows = []
    for gi in present:
        ev_id = int(gi // NSENS); sens = int(gi % NSENS)
        if ev_id >= nev:
            continue
        rows.append({"particle": meta["particle"], "ke_MeV": meta["ke_MeV"], "seed": meta["seed"],
                     "xoff": meta["xoff"], "systematic": meta["systematic"], "fname": meta["fname"],
                     "event": ev_id, "sensor": sens,
                     "edep_MeV": float(edep_ev[ev_id]) if ev_id < len(edep_ev) else float("nan"),
                     "n_det": int(ndet[gi]), "t_truth": float(tfirst[gi]), "wf": wf[gi]})
    return rows

def _rising_crossing(w, level):
    am = int(np.argmax(w))
    if w[am] < level:
        return -1.0
    lead = w[:am + 1]; below = np.where(lead >= level)[0]
    if below.size == 0:
        return -1.0
    i = int(below[0])
    if i == 0:
        return 0.0
    y0, y1 = w[i - 1], w[i]
    if y1 == y0:
        return float(i)
    return (i - 1) + (level - y0) / (y1 - y0)

def pickoff_cfd(w):
    lvl = CFD_FRAC * w.max()
    if lvl <= 0:
        return np.nan, "cfd_no_cross"
    x = _rising_crossing(w, lvl)
    if x < 0:
        return np.nan, "cfd_no_cross"
    return T_MIN + x * DT, ""

def pickoff_lead(w):
    x = _rising_crossing(w, LE_THRESH_PE)
    if x < 0:
        return np.nan, "lead_no_cross"
    return T_MIN + x * DT, ""

def build_template(rows):
    nd = np.array([r["n_det"] for r in rows])
    thr = np.percentile(nd, TEMPLATE_AMP_PC) if len(nd) else 0
    sel = [r for r in rows if r["n_det"] >= max(thr, MIN_PE_VALID)]
    if not sel:
        sel = [r for r in rows if r["n_det"] >= MIN_PE_VALID]
    aligned = []
    xsrc = np.arange(NBINS)
    for r in sel:
        w = np.asarray(r["wf"], dtype=np.float64)
        if w.max() <= 0:
            continue
        wn = w / w.max()
        x = _rising_crossing(wn, TEMPLATE_ALIGN_Q)
        if x < 0:
            continue
        shift_bins = TEMPLATE_REF_BIN - x          # fractional
        # shift the normalised pulse so its crossing lands at TEMPLATE_REF_BIN (np.interp)
        xs = xsrc - shift_bins
        a = np.interp(xsrc, xs, wn, left=0.0, right=0.0)
        aligned.append(a)
    if not aligned:
        tmpl = np.zeros(NBINS); tmpl[NBINS // 2] = 1.0
        return tmpl, T_MIN + (NBINS // 2) * DT
    tmpl = np.nanmean(np.vstack(aligned), axis=0)
    tmpl = np.clip(tmpl, 0, None)
    if tmpl.max() > 0:
        tmpl /= tmpl.max()
    tmpl_anchor = T_MIN + TEMPLATE_REF_BIN * DT
    return tmpl, tmpl_anchor

def apply_pickoffs(rows, tmpl, tmpl_anchor):
    N = len(rows)
    W = np.vstack([r["wf"] for r in rows]).astype(np.float64)   # (N, NBINS)
    maxes = W.max(axis=1)
    # per-row CFD / leading-edge (cheap)
    for i, r in enumerate(rows):
        if r["n_det"] < MIN_PE_VALID:
            r["t_cfd"] = r["t_templ"] = r["t_lead"] = np.nan
            r["amp"] = float(maxes[i]); r["fail"] = "low_pe"
            continue
        tc, ec = pickoff_cfd(W[i]); tl, el = pickoff_lead(W[i])
        r["t_cfd"] = tc; r["t_lead"] = tl
        r["amp"] = float(maxes[i])
        r["fail"] = ",".join([x for x in (ec, el) if x])
    # vectorised template fit (grid search over shifts, all rows at once)
    denom = float(tmpl @ tmpl)
    bestchi = np.full(N, np.inf); bestsh = np.zeros(N, np.int64); bestamp = np.zeros(N)
    tcol = tmpl.astype(np.float64)
    for rs in range(-40, 41):
        ts = np.roll(tcol, rs)
        if rs > 0: ts[:rs] = 0.0
        elif rs < 0: ts[rs:] = 0.0
        amp = (W @ ts) / denom if denom > 0 else np.zeros(N)
        amp = np.maximum(amp, 0.0)
        resid = W - amp[:, None] * ts[None, :]
        chi = np.einsum("ij,ij->i", resid, resid)
        upd = chi < bestchi
        bestchi[upd] = chi[upd]; bestsh[upd] = rs; bestamp[upd] = amp[upd]
    rec_t = tmpl_anchor + bestsh * DT
    for i, r in enumerate(rows):
        if r["n_det"] < MIN_PE_VALID:
            continue
        r["t_templ"] = float(rec_t[i]) if np.isfinite(bestchi[i]) and bestamp[i] > 0 else np.nan
        if not np.isfinite(bestchi[i]) or bestamp[i] <= 0:
            f = r.get("fail", "")
            r["fail"] = (f + ",tmpl_no_fit") if f else "tmpl_no_fit"

def sigma68(x):
    x = x[np.isfinite(x)]
    if x.size == 0: return float("nan")
    lo, hi = np.percentile(x, [16, 84]); return (hi - lo) / 2.0

def gauss(x, a, mu, sig): return a * np.exp(-0.5 * ((x - mu) / sig) ** 2)

def bootstrap_ci(vals, stat=np.median, n=NBOOT, seed=0):
    vals = np.asarray(vals)[np.isfinite(vals)]
    if vals.size < 3: return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed); out = np.empty(n)
    for i in range(n): out[i] = stat(rng.choice(vals, vals.size, replace=True))
    lo, hi = np.percentile(out, [16, 84]); return float(stat(vals)), float(lo), float(hi)

def vis_tim_001(rows, tmpl, tmpl_anchor, outdir):
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5))
    fig.suptitle("VIS-TIM-001  Timing-pickoff construction (single-stave photon MC)", fontweight="bold")
    valid = [r for r in rows if r["n_det"] >= MIN_PE_VALID and np.isfinite(r.get("t_cfd", np.nan))]
    valid.sort(key=lambda r: r["n_det"]); n = len(valid); picks = []
    if n: picks += [valid[max(0, n // 50)], valid[n // 2], valid[min(n - 1, 49 * n // 50)]]
    low = [r for r in rows if r["n_det"] < MIN_PE_VALID]
    if low: picks.append(low[len(low) // 2])
    labels_amp = ["low-PE", "mid-PE", "high-PE", "low-PE (fail)"]
    slots = [(0,0),(0,1),(1,0),(1,1)]
    for k, r in enumerate(picks[:4]):
        ax = axes[slots[k][0]][slots[k][1]]
        w = np.asarray(r["wf"], float)
        ax.plot(TAXIS, w, color="#333333", lw=1.0, drawstyle="steps-mid", label="waveform w(t)")
        ax.axhline(CFD_FRAC * w.max(), color=PAL["cfd"], ls="--", lw=0.9, label="CFD %.0f%% max" % (100*CFD_FRAC))
        ax.axhline(LE_THRESH_PE, color=PAL["lead"], ls=":", lw=0.9, label="leading-edge %g PE" % LE_THRESH_PE)
        if np.isfinite(r.get("t_templ", np.nan)):
            sh = int(round((r["t_templ"] - tmpl_anchor) / DT))
            tt2 = np.roll(tmpl * r["amp"], sh)
            if sh > 0: tt2[:sh] = 0
            elif sh < 0: tt2[sh:] = 0
            ax.plot(TAXIS, tt2, color=PAL["templ"], lw=1.1, alpha=0.9, label="template fit")
            ax.scatter([r["t_templ"]], [tmpl.max() * r["amp"] * 1.02], color=PAL["templ"], marker="v", s=40, zorder=5)
        if np.isfinite(r.get("t_cfd", np.nan)):
            ax.scatter([r["t_cfd"]], [CFD_FRAC * w.max()], color=PAL["cfd"], marker="o", s=45, zorder=5)
        if np.isfinite(r.get("t_lead", np.nan)):
            ax.scatter([r["t_lead"]], [LE_THRESH_PE], color=PAL["lead"], marker="s", s=45, zorder=5)
        if np.isfinite(r.get("t_truth", np.nan)):
            ax.axvline(r["t_truth"], color=PAL["truth"], lw=1.2, label="truth (1st photon)")
        tag = labels_amp[k] if k < len(labels_amp) else ""
        ax.set_title("%s  %s %d MeV seed%d sens%d  nPE=%d %s" %
                     (tag, r["particle"], r["ke_MeV"], r["seed"], r["sensor"], r["n_det"],
                      ("[" + r["fail"] + "]") if r.get("fail") else ""))
        ax.set_xlabel("time (ns)"); ax.set_ylabel("PE / %.2f ns bin" % DT); ax.legend(loc="upper right", fontsize=7)
    axf = axes[0][2]
    fail_counts = defaultdict(int)
    for r in rows:
        if r.get("fail"):
            for tok in r["fail"].split(","): fail_counts[tok] += 1
    fc = dict(sorted(fail_counts.items(), key=lambda kv: -kv[1]))
    keys = list(fc.keys())[:8][::-1]; vals = [fc[k] for k in keys]
    bars = axf.barh(keys, vals, color="#CC79A7")
    axf.set_xlabel("count of (event, sensor) groups"); axf.set_title("pickoff failure reasons")
    for b in bars: axf.text(b.get_width(), b.get_y()+b.get_height()/2, " %d"%int(b.get_width()), va="center", fontsize=8)
    axs = axes[1][2]
    tot = len(rows); methods = ["cfd","templ","lead"]; succ = []; medr = []
    for m in methods:
        kk = "t_" + ("cfd" if m=="cfd" else "templ" if m=="templ" else "lead")
        rs = np.array([r[kk]-r["t_truth"] for r in rows if np.isfinite(r.get(kk,np.nan)) and np.isfinite(r.get("t_truth",np.nan))])
        succ.append(int(np.isfinite([r.get(kk,np.nan) for r in rows]).sum()))
        medr.append(sigma68(rs) if rs.size else float("nan"))
    xb = np.arange(3)
    axs.bar(xb, [s/max(tot,1) for s in succ], color=[PAL["cfd"],PAL["templ"],PAL["lead"]])
    axs.set_xticks(xb); axs.set_xticklabels(["CFD","template","leading-edge"]); axs.set_ylim(0,1.05)
    axs.set_ylabel("success fraction"); axs.set_title("success & $\sigma_{68}$(residual)")
    for i,(s,sg) in enumerate(zip(succ,medr)):
        axs.text(i, s/max(tot,1)+0.02, "%.1f%%\n$\\sigma_{68}$=%.2fns"%(100*s/max(tot,1),sg if np.isfinite(sg) else 0), ha="center", fontsize=8)
    fig.tight_layout(rect=[0,0,1,0.97])
    p = os.path.join(outdir,"VIS-TIM-001_pickoff_construction.png"); fig.savefig(p); plt.close(fig)
    return p, {"success_fraction":{m:s/max(tot,1) for m,s in zip(methods,succ)},
               "sigma68_residual_ns":{m:(float(sg) if np.isfinite(sg) else None) for m,sg in zip(methods,medr)},
               "failure_counts":fc}

def vis_tim_002(rows, outdir):
    fig, axes = plt.subplots(2,2,figsize=(13,9))
    fig.suptitle("VIS-TIM-002  Timewalk: raw vs amplitude-bias-corrected residual (CFD pickoff)", fontweight="bold")
    def is_train(r): return (r["seed"]==101 and r["ke_MeV"] in (5,20,80) and abs(r["xoff"])<1e-6 and r["systematic"]=="nominal")
    N = len(rows)
    res = np.full(N, np.nan)
    for i,r in enumerate(rows):
        if np.isfinite(r.get("t_cfd",np.nan)) and np.isfinite(r.get("t_truth",np.nan)):
            res[i] = r["t_cfd"] - r["t_truth"]
    glob = np.nanmedian(res) if np.isfinite(res).any() else 0.0
    for i,r in enumerate(rows):
        r["res_cfd"] = (res[i]-glob) if np.isfinite(res[i]) else np.nan
    amp = np.array([float(r["n_det"]) for r in rows])
    train_mask = np.array([is_train(r) for r in rows])
    fin = np.isfinite(res)
    amin = max(MIN_PE_VALID, int(np.nanpercentile(amp[fin],2))) if fin.any() else MIN_PE_VALID
    amax = int(np.nanpercentile(amp[fin],98)) if fin.any() else amin+100
    edges = np.linspace(amin, amax, 16)
    def lin(x,a,b): return a + b/np.maximum(x,1.0)
    def binres(mask):
        xc,yc,ye = [],[],[]
        rescorr = np.array([r["res_cfd"] for r in rows])
        for i in range(len(edges)-1):
            sel = mask & (amp>=edges[i]) & (amp<edges[i+1]) & np.isfinite(rescorr)
            if sel.sum()<10: continue
            v = rescorr[sel]
            xc.append(0.5*(edges[i]+edges[i+1])); yc.append(np.median(v)); ye.append(sigma68(v))
        return np.array(xc),np.array(yc),np.array(ye)
    xc_tr,yc_tr,ye_tr = binres(train_mask)
    xc_ho,yc_ho,ye_ho = binres(~train_mask)
    p0=[0.0,5.0]
    try:
        popt,_ = curve_fit(lin, xc_tr, yc_tr, p0=p0, sigma=np.where(ye_tr>0,ye_tr,1.0), absolute_sigma=True, maxfev=20000)
    except Exception:
        popt = np.array([float(np.median(yc_tr)) if yc_tr.size else 0.0, 0.0])
    a0,b0 = float(popt[0]),float(popt[1])
    for r in rows:
        r["res_cfd_corr"] = (r["res_cfd"]-(a0+b0/max(r["n_det"],1.0))) if np.isfinite(r.get("res_cfd",np.nan)) else np.nan
    ax = axes[0][0]
    ax.errorbar(xc_tr,yc_tr,yerr=ye_tr,fmt="o",color=PAL["raw"],ms=4,capsize=3,label="train groups (median $\\pm1\\sigma_{68}$)")
    ax.errorbar(xc_ho,yc_ho,yerr=ye_ho,fmt="s",color="#888888",ms=4,capsize=3,label="held-out groups")
    xx = np.linspace(amin,amax,100)
    ax.plot(xx, lin(xx,a0,b0),"-",color=PAL["corr"],lw=2,label="timewalk fit (train): $a+b/N_{PE}$")
    rng = np.random.default_rng(1); bb=[]
    for _ in range(NBOOT):
        if len(xc_tr)<3: continue
        idx = rng.choice(len(xc_tr),len(xc_tr),replace=True)
        try:
            pp,_=curve_fit(lin,xc_tr[idx],yc_tr[idx],p0=p0,maxfev=20000); bb.append(lin(xx,*pp))
        except Exception: continue
    if bb:
        bb=np.vstack(bb); ax.fill_between(xx,np.percentile(bb,16,0),np.percentile(bb,84,0),color=PAL["band"],alpha=0.35,label="fit 68% band")
    ax.axhline(0,color="k",lw=0.8); ax.set_xlabel("amplitude ($N_{PE}$)"); ax.set_ylabel("raw residual (ns)")
    ax.set_title("RAW: residual walks with amplitude"); ax.legend(loc="upper right")
    ax = axes[0][1]
    rescorr = np.array([r["res_cfd_corr"] for r in rows]); ho = (~train_mask) & np.isfinite(rescorr)
    xh,yh,eh=[],[],[]
    for i in range(len(edges)-1):
        s = ho & (amp>=edges[i]) & (amp<edges[i+1])
        if s.sum()<10: continue
        xh.append(0.5*(edges[i]+edges[i+1])); yh.append(np.median(rescorr[s])); eh.append(sigma68(rescorr[s]))
    ax.errorbar(xh,yh,yerr=eh,fmt="s",color=PAL["corr"],ms=4,capsize=3,label="held-out corrected")
    slope=float("nan"); sci=(float("nan"),float("nan"))
    if len(xh)>=3:
        sl=float(np.polyfit(xh,yh,1)[0]); boots=[]; idxs=np.where(ho&(amp>=amin)&(amp<=amax))[0]
        rng2=np.random.default_rng(2)
        for _ in range(NBOOT):
            ii=rng2.choice(idxs,idxs.size,replace=True); vv=rescorr[ii]; aa=amp[ii]; xb2,yb2=[],[]
            for i in range(len(edges)-1):
                mm=(aa>=edges[i])&(aa<edges[i+1])
                if mm.sum()<5: continue
                xb2.append(0.5*(edges[i]+edges[i+1])); yb2.append(np.median(vv[mm]))
            if len(xb2)>=3:
                try: boots.append(np.polyfit(xb2,yb2,1)[0])
                except Exception: pass
        if boots:
            slope=float(np.median(boots)); sci=(float(np.percentile(boots,16)),float(np.percentile(boots,84)))
    ax.axhline(0,color="k",lw=0.8)
    passes = abs(slope)<0.01 if np.isfinite(slope) else False
    ax.text(0.04,0.96,"held-out slope = %.4f ns/PE\n68%% CI [%.4f,%.4f]\ncriterion slope$\\approx$0: %s"%(slope,sci[0],sci[1],"PASSES" if passes else "check"),
            transform=ax.transAxes,va="top",ha="left",fontsize=9,bbox=dict(boxstyle="round",fc="white",ec=PAL["corr"]))
    ax.set_xlabel("amplitude ($N_{PE}$)"); ax.set_ylabel("corrected residual (ns)")
    ax.set_title("CORRECTED: held-out flat $\\Rightarrow$ timewalk removed"); ax.legend(loc="upper right")
    ax = axes[1][0]
    bins = np.linspace(np.nanpercentile(res,1),np.nanpercentile(res,99),60) if np.isfinite(res).any() else np.linspace(-5,5,60)
    ax.hist(res[train_mask&np.isfinite(res)],bins=bins,histtype="step",lw=1.5,color=PAL["raw"],density=True,label="train raw")
    ax.hist(res[(~train_mask)&np.isfinite(res)],bins=bins,histtype="step",lw=1.5,color="#888888",density=True,label="held-out raw")
    ax.hist(rescorr[(~train_mask)&np.isfinite(rescorr)],bins=bins,histtype="step",lw=1.5,color=PAL["corr"],density=True,label="held-out corrected")
    ax.axvline(0,color="k",lw=0.8); ax.set_xlabel("residual (ns)"); ax.set_ylabel("density"); ax.set_title("residual distributions"); ax.legend()
    ax = axes[1][1]
    for s in range(NSENS):
        ms = np.array([r["sensor"]==s for r in rows]) & np.isfinite(res); xs,ys,es=[],[],[]
        for i in range(len(edges)-1):
            sel=ms&(amp>=edges[i])&(amp<edges[i+1])
            if sel.sum()<15: continue
            xs.append(0.5*(edges[i]+edges[i+1])); ys.append(np.median(res[sel])); es.append(sigma68(res[sel]))
        ax.errorbar(xs,ys,yerr=es,fmt="o-",ms=3,color=PAL["s%d"%s],capsize=2,label=SENSOR_NAMES[s])
    ax.axhline(0,color="k",lw=0.8); ax.set_xlabel("amplitude ($N_{PE}$)"); ax.set_ylabel("raw residual (ns)"); ax.set_title("timewalk per stave (sensor)"); ax.legend()
    fig.tight_layout(rect=[0,0,1,0.97])
    p=os.path.join(outdir,"VIS-TIM-002_timewalk.png"); fig.savefig(p); plt.close(fig)
    return p,{"fit_form":"a+b/N_PE","fit_params_train":{"a":a0,"b":b0},"heldout_slope_ns_per_PE":slope,
              "heldout_slope_ci":list(sci),"criterion_slope_approx_0_passes":bool(passes)}

def vis_tim_003(rows, outdir):
    fig, axes = plt.subplots(1,3,figsize=(16,5))
    fig.suptitle("VIS-TIM-003  Timing residual distributions (CFD, timewalk-corrected)",fontweight="bold")
    res = np.array([r.get("res_cfd_corr",np.nan) for r in rows]); res = res[np.isfinite(res)]
    if res.size==0:
        plt.close(fig); return None, {}
    rms=float(np.sqrt(np.mean(res**2))); s68=sigma68(res); med=float(np.median(res))
    bins=np.linspace(med-6*s68,med+6*s68,80); hh,ee=np.histogram(res,bins=bins); cc=0.5*(ee[:-1]+ee[1:])
    core=np.abs(cc-med)<=1.5*s68
    try: popt,_=curve_fit(gauss,cc[core],hh[core],p0=[hh.max(),med,s68],maxfev=20000)
    except Exception: popt=[hh.max(),med,s68]
    gsig=float(abs(popt[2])); tail_thr=3*gsig; tail_frac=float(np.mean(np.abs(res-med)>tail_thr))
    ax=axes[0]; ax.bar(cc,hh,width=cc[1]-cc[0],color="#9ecae1",edgecolor="none",label="full residual")
    xx=np.linspace(bins[0],bins[-1],300); ax.plot(xx,gauss(xx,*popt),"-",color=PAL["corr"],lw=2,label="Gauss core $\\sigma$=%.2f ns"%gsig)
    for s in (tail_thr,-tail_thr): ax.axvline(med+s,color=PAL["lead"],ls="--",lw=1)
    ax.set_xlabel("corrected residual (ns)"); ax.set_ylabel("count"); ax.set_title("residual + Gaussian core")
    ax.text(0.02,0.98,"RMS=%.3f ns\n$\\sigma_{68}$=%.3f ns\nGauss $\\sigma$=%.3f ns\ntail|>3$\\sigma$=%.2f%%\nN=%d"%(rms,s68,gsig,100*tail_frac,res.size),
            transform=ax.transAxes,va="top",fontsize=9,bbox=dict(boxstyle="round",fc="white",ec="#888")); ax.legend(loc="upper right")
    ax=axes[1]; ax.bar(cc,hh,width=cc[1]-cc[0],color="#9ecae1",edgecolor="none"); ax.set_yscale("log")
    ax.axvline(med+tail_thr,color=PAL["lead"],ls="--",lw=1,label="$\\pm3\\sigma$ tail"); ax.axvline(med-tail_thr,color=PAL["lead"],ls="--",lw=1)
    ax.set_xlabel("corrected residual (ns)"); ax.set_ylabel("count (log)"); ax.set_title("tail view (log)"); ax.legend()
    ax=axes[2]
    from scipy.stats import probplot
    (osm,osr),(sl,ic,r)=probplot(res,dist="norm",fit=True)
    ax.scatter(osm,osr,s=4,color=PAL["cfd"],alpha=0.4)
    xx2=np.linspace(osm.min(),osm.max(),50); ax.plot(xx2,sl*xx2+ic,"-",color=PAL["lead"],lw=1.5,label="linear fit")
    ax.plot(xx2,xx2*np.std(res),"--",color="k",lw=1,label="ref $\\sigma$=std")
    ax.set_xlabel("theoretical quantiles"); ax.set_ylabel("ordered residuals (ns)"); ax.set_title("QQ vs Gaussian"); ax.legend()
    fig.tight_layout(rect=[0,0,1,0.94])
    p=os.path.join(outdir,"VIS-TIM-003_distributions.png"); fig.savefig(p); plt.close(fig)
    return p,{"RMS_ns":rms,"sigma68_ns":float(s68),"gauss_core_sigma_ns":gsig,"tail_fraction_3sigma":tail_frac,"N":int(res.size)}

def vis_tim_004(rows, ksum, outdir):
    fig, axes = plt.subplots(2,2,figsize=(15,10))
    fig.suptitle("VIS-TIM-004  Run / topology stability (CFD corrected residual)",fontweight="bold")
    resf=lambda r:r.get("res_cfd_corr",np.nan)
    def forest(ax, groups, title, xlabel):
        order = sorted(groups.keys(), key=lambda k:(np.nanmedian([resf(r) for r in groups[k] if np.isfinite(resf(r))]) if any(np.isfinite(resf(r)) for r in groups[k]) else 0))
        ys=[]; 
        for i,k in enumerate(order):
            vals=np.array([resf(r) for r in groups[k]]); vals=vals[np.isfinite(vals)]
            if vals.size<5: continue
            med,lo,hi=bootstrap_ci(vals,np.median); s=sigma68(vals); ys.append(i)
            ax.errorbar([med],[i],xerr=[[med-lo],[hi-med]],fmt="o",color=PAL["cfd"],ms=5,capsize=3)
            ax.errorbar([med],[i],xerr=[[s],[s]],fmt="none",ecolor=PAL["lead"],alpha=0.5,capsize=2)
        ax.set_yticks(ys); ax.set_yticklabels([str(k) for i,k in enumerate(order) if any(np.isfinite(resf(r)) for r in groups[k]) and len([1 for r in groups[k] if np.isfinite(resf(r))])>=5])
        ax.axvline(0,color="k",lw=0.8); ax.set_xlabel(xlabel); ax.set_title(title)
    g=defaultdict(list)
    for r in rows: g["seed%d"%r["seed"]].append(r)
    forest(axes[0][0],g,"per-run (seed)","corrected residual median $\\pm1\\sigma_{68}$ (ns); orange=$\\sigma_{68}$")
    g=defaultdict(list)
    for r in rows: g[SENSOR_NAMES[r["sensor"]]].append(r)
    forest(axes[0][1],g,"per-stave (sensor)","corrected residual (ns)")
    g=defaultdict(list)
    for r in rows:
        if abs(r["xoff"])<1e-6 and r["systematic"]=="nominal":
            g["%s %dMeV"%(r["particle"][:2],r["ke_MeV"])].append(r)
    forest(axes[1][0],g,"per-topology (on-axis)","corrected residual (ns)")
    ax=axes[1][1]; by_ev=defaultdict(dict)
    for r in rows:
        if np.isfinite(resf(r)): by_ev[(r["fname"],r["event"])][r["sensor"]]=resf(r)
    M=np.array([[d[s] for s in range(NSENS)] for d in by_ev.values() if len(d)==NSENS])
    cov_summary={}
    if M.shape[0]>=20:
        cov=np.cov(M.T); im=ax.imshow(cov,cmap="RdBu_r",vmin=-abs(cov).max(),vmax=abs(cov).max())
        ax.set_xticks(range(NSENS)); ax.set_yticks(range(NSENS))
        ax.set_xticklabels(SENSOR_NAMES,rotation=30); ax.set_yticklabels(SENSOR_NAMES)
        for i in range(NSENS):
            for j in range(NSENS): ax.text(j,i,"%.3f"%cov[i,j],ha="center",va="center",fontsize=8,color="k")
        plt.colorbar(im,ax=ax,fraction=0.046,label="cov (ns$^2$)")
        ax.set_title("4-sensor residual covariance (N=%d)"%M.shape[0])
        rng=np.random.default_rng(7)
        for s in range(NSENS):
            bb=[np.var(rng.choice(M[:,s],M.shape[0],replace=True)) for _ in range(NBOOT)]
            cov_summary[SENSOR_NAMES[s]]={"var":float(np.var(M[:,s])),"ci68":[float(np.percentile(bb,16)),float(np.percentile(bb,84))]}
    else:
        ax.text(0.5,0.5,"insufficient event-matched groups",ha="center",transform=ax.transAxes)
    fig.tight_layout(rect=[0,0,1,0.96])
    p=os.path.join(outdir,"VIS-TIM-004_stability.png"); fig.savefig(p); plt.close(fig)
    pk=None; krak={}
    if ksum is not None:
        pk,krak=vis_tim_004_krakow(ksum,outdir)
    return p,{"covariance_summary":cov_summary,"krakow_topology_figure":pk,"krakow":krak}

def vis_tim_004_krakow(kpack, outdir):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    fig.suptitle("VIS-TIM-004b (Krakow 1M)  Truth-time anchor: topology closure ($\\bar n$ annihilation at rest)", fontweight="bold")
    evs = kpack["events"]; allt = kpack["all_deposit_times"]; allt = allt[np.isfinite(allt)]
    ax = axes[0]
    ax.hist(allt, bins=np.linspace(-0.02, 1.2, 80), color="#9ecae1", edgecolor="none")
    ax.axvline(0, color="k", lw=1, label="truth t0=0 (PrimaryTime)")
    ax.set_yscale("log")
    frac0 = float(np.mean(allt == 0.0)) if allt.size else float("nan")
    ax.text(0.45, 0.96, "all TARGET deposit steps (N=%d)\n%.2f%% exactly at t0=0\nmax = %.3f ns" % (allt.size, 100*frac0, float(allt.max())),
            transform=ax.transAxes, va="top", fontsize=9, bbox=dict(boxstyle="round", fc="white", ec="#888"))
    ax.set_xlabel("TARGET deposit time (ns)"); ax.set_ylabel("count (log)"); ax.set_title("truth-time anchor = clean delta at t0")
    ax.legend(loc="upper right", fontsize=8)
    ax = axes[1]
    g2 = defaultdict(list)
    for row in evs:
        g2[row["edep_bin"]].append(row["deposit_duration"])
    items = [(k, np.array(g2[k])[np.isfinite(g2[k])]) for k in sorted(g2.keys())]
    items = [(k, v) for k, v in items if v.size >= 50]
    for i, (k, v) in enumerate(items):
        q95 = float(np.percentile(v, 95))
        rng = np.random.default_rng(100 + i)
        bb = [float(np.percentile(rng.choice(v, v.size, replace=True), 95)) for _ in range(NBOOT)]
        lo, hi = np.percentile(bb, [16, 84])
        ax.errorbar([q95], [i], xerr=[[q95 - lo], [hi - q95]], fmt="s", color=PAL["cfd"], ms=7, capsize=3)
        ax.text(q95, i, "  N=%d" % v.size, va="center", fontsize=8)
    ax.set_yticks(range(len(items))); ax.set_yticklabels(["$E_{dep}$ " + k for k, _ in items])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("per-event deposit duration $t_{last}-t_{first}$, 95th pct (ns)")
    ax.set_title("deposition is instantaneous $\\Rightarrow$ truth anchor topology-stable")
    ax.text(0.03, 0.05, "resolution is a photon-arrival property:\nmeasured entirely by the single-stave arm",
            transform=ax.transAxes, fontsize=8, va="bottom", color="#444",
            bbox=dict(boxstyle="round", fc="#fff7e6", ec="#888"))
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    p = os.path.join(outdir, "VIS-TIM-004b_krakow_topology.png"); fig.savefig(p); plt.close(fig)
    n0 = float(np.mean(allt == 0.0)) if allt.size else float("nan")
    return p, {"edep_bins": [k for k, _ in items], "frac_deposits_at_t0": n0,
               "max_deposit_time_ns": (float(allt.max()) if allt.size else None),
               "note": "Krakow TARGET deposits are a delta at t0=0 (annihilation at rest); no intrinsic timing resolution. Truth anchor topology-stable; resolution measured by single-stave photon arm."}


def vis_tim_005(rows,outdir):
    fig,axes=plt.subplots(2,3,figsize=(16,9))
    fig.suptitle("VIS-TIM-005  Combined 4-sensor estimator: weights, covariance, LOSO, pulls",fontweight="bold")
    by_ev=defaultdict(dict)
    for r in rows:
        if np.isfinite(r.get("res_cfd_corr",np.nan)): by_ev[(r["fname"],r["event"])][r["sensor"]]=r["res_cfd_corr"]
    M=np.array([[d[s] for s in range(NSENS)] for d in by_ev.values() if len(d)==NSENS])
    cov_closed=False; note=""
    if M.shape[0]>=30:
        cov=np.cov(M.T); var=np.diag(cov); w=1.0/var; w/=w.sum(); comb=M@w
        comb_s68=sigma68(comb); comb_rms=float(np.sqrt(np.mean(comb**2)))
        eig=np.linalg.eigvalsh(cov); loso={}
        for s in range(NSENS):
            keep=[j for j in range(NSENS) if j!=s]; Mk=M[:,keep]; vk=np.diag(np.cov(Mk.T)); wk=1.0/vk; wk/=wk.sum()
            loso[SENSOR_NAMES[s]]={"sigma68_ns":float(sigma68(Mk@wk)),"N":int(Mk.shape[0])}
        sig_comb=float(np.sqrt(w@cov@w)); pulls=comb/sig_comb
        cov_frac={str(n):float(np.mean(np.abs(pulls)<n)) for n in (1,2,3)}
        cov_closed=bool(abs(cov_frac["1"]-0.683)<0.06 and abs(cov_frac["2"]-0.954)<0.06)
        if not cov_closed:
            note=("covariance-aware Gaussian uncertainty does NOT close on this MC at N=%d "
                  "(|pull|<1 frac=%.3f vs 0.683, |pull|<2 frac=%.3f vs 0.954): residuals are non-Gaussian "
                  "(scintillation tail + low-PE photon statistics), so the Gaussian pull model mis-covers. "
                  "Pull-coverage headline BLOCKED until an empirical-quantile / rank uncertainty is used; "
                  "weights/eigenvalues/LOSO remain valid.")%(M.shape[0],cov_frac["1"],cov_frac["2"])
    else:
        w=np.ones(NSENS)/NSENS; cov=np.eye(NSENS)*np.nan; eig=np.full(NSENS,np.nan); comb=np.array([])
        comb_s68=float("nan"); comb_rms=float("nan"); loso={}; cov_frac={}; sig_comb=float("nan")
        note="insufficient event-matched 4-sensor groups on MC"
    ax=axes[0][0]; bars=ax.bar(range(NSENS),w,color=[PAL["s%d"%i] for i in range(NSENS)])
    ax.set_xticks(range(NSENS)); ax.set_xticklabels(SENSOR_NAMES,rotation=20); ax.set_ylim(0,max(w)*1.25 if max(w)>0 else 1)
    ax.set_ylabel("inverse-variance weight"); ax.set_title("combined-estimator weights")
    for b,ww in zip(bars,w): ax.text(b.get_x()+b.get_width()/2,ww,"%.3f"%ww,ha="center",va="bottom",fontsize=9)
    ax=axes[0][1]
    if np.isfinite(cov).all():
        im=ax.imshow(cov,cmap="Blues"); plt.colorbar(im,ax=ax,fraction=0.046,label="cov (ns$^2$)")
        for i in range(NSENS):
            for j in range(NSENS): ax.text(j,i,"%.3f"%cov[i,j],ha="center",va="center",fontsize=8)
    else:
        ax.text(0.5,0.5,"cov unavailable",ha="center",transform=ax.transAxes)
    ax.set_xticks(range(NSENS)); ax.set_yticks(range(NSENS))
    ax.set_xticklabels(SENSOR_NAMES,rotation=20); ax.set_yticklabels(SENSOR_NAMES); ax.set_title("covariance matrix")
    ax=axes[0][2]; ax.bar(range(NSENS),eig,color=PAL["templ"])
    ax.set_xticks(range(NSENS)); ax.set_xticklabels(["$\\lambda_{%d}$"%(i+1) for i in range(NSENS)])
    ax.set_ylabel("eigenvalue (ns$^2$)"); ax.set_title("covariance eigenvalues")
    if np.all(np.isfinite(eig)) and np.nanmin(eig)>0:
        ax.text(0.5,0.95,"$\\kappa$=%.2f"%(np.nanmax(eig)/np.nanmin(eig)),transform=ax.transAxes,ha="center",va="top",fontsize=9,bbox=dict(boxstyle="round",fc="white"))
    ax=axes[1][0]; names=list(loso.keys()); s68s=[loso[n]["sigma68_ns"] for n in names]
    if names:
        ax.bar(range(len(names)),s68s,color=PAL["cfd"]); ax.set_xticks(range(len(names))); ax.set_xticklabels(names,rotation=20)
        ax.axhline(comb_s68 if np.isfinite(comb_s68) else 0,color="k",ls="--",lw=1,label="all-4 $\\sigma_{68}$=%.3f ns"%(comb_s68 if np.isfinite(comb_s68) else 0))
        ax.legend(fontsize=8)
    ax.set_ylabel("$\\sigma_{68}$ (ns)"); ax.set_title("leave-one-sensor-out")
    ax=axes[1][1]
    if comb.size:
        bb=np.linspace(-5*comb_s68,5*comb_s68,60) if np.isfinite(comb_s68) else 60
        ax.hist(comb,bins=bb,color="#9ecae1",edgecolor="none",density=True,label="combined residual")
        xx=np.linspace(bb[0],bb[-1],200)
        if np.isfinite(comb_s68): ax.plot(xx,np.exp(-0.5*(xx/comb_s68)**2)/(comb_s68*np.sqrt(2*np.pi)),"-",color=PAL["corr"],label="Gauss($\\sigma_{68}$)")
    ax.axvline(0,color="k",lw=0.8); ax.set_xlabel("combined residual (ns)"); ax.set_ylabel("density"); ax.set_title("combined estimator residual"); ax.legend()
    ax=axes[1][2]
    if comb.size and np.isfinite(sig_comb):
        from scipy.stats import norm
        pct=np.arange(1,100,1)/100.0; emp=np.quantile(np.abs(pulls),pct); exp=norm.ppf((1+pct)/2)
        ax.plot(pct,emp,"-o",ms=3,color=PAL["cfd"],label="empirical |pull|")
        ax.plot(pct,exp,"--",color="k",label="unit-Gauss expect.")
        ax.fill_between(pct,norm.ppf((1+pct)/2,scale=1/1.1),norm.ppf((1+pct)/2,scale=1.1),color=PAL["band"],alpha=0.3,label="$\\pm$10% band")
        ax.text(0.03,0.97,"|pull|<1: %.3f (0.683)\n|pull|<2: %.3f (0.954)\n|pull|<3: %.3f (0.997)"%(cov_frac.get("1",float("nan")),cov_frac.get("2",float("nan")),cov_frac.get("3",float("nan"))),transform=ax.transAxes,va="top",fontsize=8,bbox=dict(boxstyle="round",fc="white"))
    ax.set_xlabel("quantile"); ax.set_ylabel("|pull| ($\\sigma$)"); ax.set_title("pull coverage vs Gaussian"); ax.legend(fontsize=8)
    fig.tight_layout(rect=[0,0,1,0.96])
    p=os.path.join(outdir,"VIS-TIM-005_combined_estimator.png"); fig.savefig(p); plt.close(fig)
    return p,{"weights":{SENSOR_NAMES[i]:float(w[i]) for i in range(NSENS)},
              "combined_sigma68_ns":(float(comb_s68) if np.isfinite(comb_s68) else None),
              "combined_RMS_ns":(float(comb_rms) if np.isfinite(comb_rms) else None),
              "eigenvalues":[(float(x) if np.isfinite(x) else None) for x in eig],
              "leave_one_sensor_out_sigma68_ns":{k:v["sigma68_ns"] for k,v in loso.items()},
              "pull_coverage":cov_frac,"covariance_closes":cov_closed,"blocker_note":note}

def load_krakow_summary(max_events=200000):
    """Krakow 1M = annihilation-at-rest kinematics MC: TARGET deposits are a delta at t0=0.
    Returns dict{events, all_deposit_times}; confirms truth-time anchor is clean & topology-stable.
    (Resolution is a photon-arrival property, measured by the single-stave arm.)"""
    t = uproot.open(KRAKOW)["hibeam"]
    a = t.arrays(["TARGET_Time", "TARGET_EDep", "PrimaryEkin"], library="np", entry_stop=max_events)
    ttime, tedep, ek = a["TARGET_Time"], a["TARGET_EDep"], a["PrimaryEkin"]
    n = len(ttime); rows = []; chunks = []
    for i in range(min(n, max_events)):
        tt = np.asarray(ttime[i]).ravel() if ttime[i] is not None else np.array([])
        ee = np.asarray(tedep[i]).ravel() if tedep[i] is not None else np.array([])
        if tt.size == 0:
            continue
        tot = float(np.nansum(ee)) if ee.size else float("nan")
        tf = float(np.nanmin(tt)); tl = float(np.nanmax(tt))
        eb = ("<20 MeV" if tot < 20 else "20-80 MeV" if tot < 80 else "80-160 MeV" if tot < 160 else ">160 MeV")
        rows.append({"t_first_deposit": tf, "t_last_deposit": tl, "deposit_duration": tl - tf,
                     "total_edep": tot, "edep_bin": eb, "n_steps": int(tt.size),
                     "ekin": float(np.asarray(ek[i]).ravel()[0])})
        chunks.append(tt)
    allt = np.concatenate(chunks) if chunks else np.array([])
    return {"events": rows, "all_deposit_times": allt}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--outdir",default="/projects/hep/fs10/shared/nnbar/billy/ccb-wt-clB/reports/studies/clusterB")
    ap.add_argument("--max-events",type=int,default=350)
    ap.add_argument("--quick",action="store_true")
    ap.add_argument("--skip-krakow",action="store_true")
    args=ap.parse_args()
    os.makedirs(args.outdir,exist_ok=True); t0=time.time()
    files=discover_stave_files(quick=args.quick); birks=[] if args.quick else discover_birks_files()
    allmeta=files+birks
    print("[clusterB] processing %d files (%d nominal + %d birks), max_events=%d"%(len(allmeta),len(files),len(birks),args.max_events),flush=True)
    rows=[]
    for k,(fp,md) in enumerate(allmeta):
        r=process_file(fp,md,args.max_events); rows.extend(r)
        if (k+1)%10==0 or k==len(allmeta)-1: print("  [%d/%d] %s -> %d (cum %d)"%(k+1,len(allmeta),md["fname"],len(r),len(rows)),flush=True)
    print("[clusterB] total groups: %d"%len(rows),flush=True)
    if not rows: raise SystemExit("no photon groups loaded")
    tmpl,tmpl_anchor=build_template([r for r in rows if r["systematic"]=="nominal"])
    print("[clusterB] template anchor=%.3f ns"%tmpl_anchor,flush=True)
    apply_pickoffs(rows,tmpl,tmpl_anchor)
    metrics={}
    p1,m1=vis_tim_001(rows,tmpl,tmpl_anchor,args.outdir); metrics["VIS-TIM-001"]=m1
    p2,m2=vis_tim_002(rows,args.outdir); metrics["VIS-TIM-002"]=m2
    p3,m3=vis_tim_003(rows,args.outdir); metrics["VIS-TIM-003"]=m3
    ksum=None
    if not args.skip_krakow:
        print("[clusterB] loading Krakow topology summary...",flush=True)
        try: ksum=load_krakow_summary(max_events=200000); print("[clusterB] krakow events: %d"%len(ksum["events"]),flush=True)
        except Exception as e: print("[clusterB] krakow load FAILED: %s"%e,flush=True)
    p4,m4=vis_tim_004(rows,ksum,args.outdir); metrics["VIS-TIM-004"]=m4
    p5,m5=vis_tim_005(rows,args.outdir); metrics["VIS-TIM-005"]=m5
    metrics["figures"]=[p1,p2,p3,p4,p5]; metrics["n_groups"]=len(rows); metrics["n_files"]=len(allmeta)
    metrics["wall_seconds"]=time.time()-t0
    metrics["constants"]={"DT_ns":DT,"CFD_FRAC":CFD_FRAC,"LE_THRESH_PE":LE_THRESH_PE,"MIN_PE_VALID":MIN_PE_VALID,"T_RANGE_NS":[T_MIN,T_MAX]}
    with open(os.path.join(args.outdir,"metrics.json"),"w") as fh: json.dump(metrics,fh,indent=2)
    print("[clusterB] DONE in %.1fs"%(time.time()-t0),flush=True)
    for p in metrics["figures"]: print("   ",p,flush=True)

if __name__=="__main__": main()

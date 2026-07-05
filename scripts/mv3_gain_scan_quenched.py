#!/usr/bin/env python3
"""
mv3_gain_scan_quenched.py
=========================
Improvement item **B-M5** (reviewer M5): re-run the MV3 stopping-depth gain
scan with **Birks scintillation quenching ON**.

Context
-------
The trigger-consistent gain ~60 ADC/MeV (Phase-2 `mv3_stopping_v4_diagnostics`,
chi2/ndf 68,269 -> 625) was fitted on an **UNQUENCHED** threshold model
(``peak_adc = gain * edep * peak_frac``).  Phase-4 turned on the physically
correct per-hit Birks law (``birks.py``: ``light = edep / (1 + kB * dE/dx)``)
and found that at gain 60 the QUENCHED table has **zero** rows passing
A > 1000 net ADC -- because quenching drops the p/d light 10-30%.  So the
ADC/MeV gain that reproduces the data amplitude spectrum and the MV3 stave
profile must be HIGHER (Phase-4 predicted ~70-80).  Nobody had run the scan
quenched.  This script does.

What it does (faithful to the v4 diagnostic, one physics change)
----------------------------------------------------------------
* Reads the same 1M truth sample and the same B-stave data CSV.
* Replaces per-hit ``edep`` with per-hit **light** ``edep/(1 + kB*dE/dx)``,
  where dE/dx is derived EXACTLY as in ``mc02_build_mc_pulse_table.per_hit_dedx``:
  primary = truth ``edep_hit / step_length`` (step = consecutive-hit diff of the
  cumulative ``Sci_bar_TrackLength``, first hit of a locally-created track uses
  the raw length when <= FIRST_STEP_MAX_CM); fallback = the PSTAR/ASTAR-anchored
  species+energy lookup (``digitizer/birks.py``) with per-hit E_kin from the
  momentum branches.  Both detector arms are quenched.
* Fixed comparison configuration (the Phase-2 optimum family): **event basis,
  species-inclusive, paired LayerID mapping**, with the **A-arm coincidence
  trigger proxy** (B-M1's real Trig_bar flag is not yet in the tree -- see
  reports/, no mv3_v5* -- so the proxy is used, exactly as Phase 2).
* Scans gain over a fine grid bracketing the quenched optimum (~40-160 ADC/MeV)
  plus the 297 placeholder for reference.
* For each gain: threshold light (MeV) for A>1000, MC stave profile
  (B2/B4/B6/B8), and chi2/ndf vs data (all / sample_i / sample_ii).  Also
  the quenched B2 amplitude-median (deepest-stave) as an absolute-scale
  cross-check vs the data B2 net-median.

Threshold model identical to v4: ``peak_adc = gain * light * peak_frac(0.733)``,
fired if > 1000 ADC net.  chi2 identical to v4.

Output: mv3_gain_quenched.json + gain_curve.md (chi2-vs-gain curve).
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ccb_mc_validation.digitizer.birks import (  # noqa: E402
    DEFAULT_EKIN_MEV,
    KB_CM_PER_MEV,
    MIP_DEDX_MEV_PER_CM,
    PROTON_MASS_MEV,
    _LOG_E,
    _LOG_S,
    _PROTON_E_MEV,
)
from ccb_mc_validation.truth.pdg import mass_of, parse_pdg  # noqa: E402

STAVES = ["B2", "B4", "B6", "B8"]
B_ARM, A_ARM = 1, 2
CHARGED_PDGS = np.array([2212, 1000010020, 11, 13, 211, 321])
PEAK_FRAC = 0.7330
THRESHOLD_NET = 1000.0

# --- per-hit dE/dx constants (identical to mc02_build_mc_pulse_table) ---------
FIRST_STEP_MAX_CM = 5.0
MIN_STEP_CM = 1e-4
DEDX_MAX_MEV_PER_CM = 3.0e4

# Fine gain grid bracketing the predicted quenched optimum (~70-80), plus the
# 297 placeholder for reference.
GAINS = [
    40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0,
    100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 297.0,
]

# Data profile target (MV3 v3 folded semantics, |amplitude - baseline| > 1000),
# quoted in the task: all = 0.876 / 0.063 / 0.039 / 0.023.


# --- vectorised species+energy dE/dx (exact port of dedx_polystyrene_mev_per_cm)
def _proton_dedx_vec(ekin_mev: np.ndarray) -> np.ndarray:
    e = np.clip(ekin_mev, float(_PROTON_E_MEV[0]), float(_PROTON_E_MEV[-1]))
    return np.exp(np.interp(np.log(e), _LOG_E, _LOG_S))


def species_dedx_vec(pdg: np.ndarray, ekin: np.ndarray | None) -> np.ndarray:
    """Vectorised port of birks.dedx_polystyrene_mev_per_cm over an array."""
    n = pdg.size
    out = np.full(n, MIP_DEDX_MEV_PER_CM, dtype=np.float64)
    if ekin is None:
        ekin = np.full(n, np.nan)
    for code in np.unique(pdg):
        code = int(code)
        m = pdg == code
        info = parse_pdg(code)
        z = abs(float(info["charge_e"]))
        if z < 0.5:
            out[m] = MIP_DEDX_MEV_PER_CM
            continue
        ek = ekin[m].astype(np.float64).copy()
        bad = ~np.isfinite(ek) | (ek <= 0.0)
        default = DEFAULT_EKIN_MEV.get(code)
        if default is None:
            if info.get("kind") == "nucleus":
                default = float(info["A"])
            else:
                out[m] = MIP_DEDX_MEV_PER_CM
                continue
        ek[bad] = float(default)
        if code == 2212:
            out[m] = _proton_dedx_vec(ek)
            continue
        if info.get("kind") != "nucleus":
            out[m] = MIP_DEDX_MEV_PER_CM
            continue
        mass = max(mass_of(code), 1.0)
        e_p = ek * PROTON_MASS_MEV / mass
        s_p = _proton_dedx_vec(e_p)
        gamma = 1.0 + ek / mass
        beta = np.sqrt(np.clip(1.0 - 1.0 / (gamma * gamma), 1e-12, None))
        z_eff = z * (1.0 - np.exp(-125.0 * beta / z ** (2.0 / 3.0)))
        out[m] = z_eff * z_eff * s_p
    return out


def chunk_dedx(ev, tid, tracklen, edep, pdg, ekin):
    """Per-hit dE/dx [MeV/cm] for a full flattened chunk, grouping by (ev,tid).

    Faithful vectorisation of mc02_build_mc_pulse_table.per_hit_dedx: within
    each (event, track) group, step = consecutive-hit diff of the cumulative
    TrackLength (first hit = raw length only when 0<tl<=FIRST_STEP_MAX_CM);
    invalid -> species+energy fallback.
    """
    n = edep.size
    dedx = np.full(n, np.nan, dtype=np.float64)
    if tracklen is not None and tracklen.size == n:
        # sort by (ev, tid, tracklen); lexsort keys are last-primary
        order = np.lexsort((tracklen, tid, ev))
        e_s = ev[order]
        t_s = tid[order]
        tl_s = tracklen[order]
        ed_s = edep[order]
        new_group = np.ones(n, dtype=bool)
        new_group[1:] = (e_s[1:] != e_s[:-1]) | (t_s[1:] != t_s[:-1])
        steps = np.empty(n, dtype=np.float64)
        steps[1:] = np.diff(tl_s)
        steps[0] = np.nan
        # first hit of each group: raw cumulative length only if born locally
        first = np.flatnonzero(new_group)
        ftl = tl_s[first]
        steps[first] = np.where((ftl > 0.0) & (ftl <= FIRST_STEP_MAX_CM), ftl, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            vals = ed_s / steps
        ok = (
            np.isfinite(vals)
            & (steps >= MIN_STEP_CM)
            & (vals > 0.0)
            & (vals <= DEDX_MAX_MEV_PER_CM)
        )
        ds = np.full(n, np.nan)
        ds[ok] = vals[ok]
        dedx[order] = ds
    nan = ~np.isfinite(dedx)
    if nan.any():
        dedx[nan] = species_dedx_vec(pdg[nan], None if ekin is None else ekin[nan])
    return dedx


def hit_light(ev, tid, tracklen, edep, pdg, ekin):
    """Per-hit Birks light = edep / (1 + kB*dE/dx)."""
    dedx = chunk_dedx(ev, tid, tracklen, edep, pdg, ekin)
    return edep / (1.0 + KB_CM_PER_MEV * dedx)


def deepest_fired(fired: np.ndarray):
    has = fired.any(axis=1)
    deep = 3 - np.argmax(fired[:, ::-1], axis=1)
    return has, deep


def _mass_vec(pdg: np.ndarray) -> np.ndarray:
    out = np.zeros(pdg.size, dtype=np.float64)
    for code in np.unique(pdg):
        out[pdg == code] = mass_of(int(code))
    return out


def run_scan(mc_path, tree, max_events, step_size):
    import uproot
    import awkward as ak

    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_LayerID",
          "Sci_bar_PDG", "Sci_bar_EDep"]
    optional = ["Sci_bar_TrackLength", "Sci_bar_Momentum_X",
                "Sci_bar_Momentum_Y", "Sci_bar_Momentum_Z"]

    tr = uproot.open(mc_path)[tree]
    have = set(tr.keys())
    use_opt = [b for b in optional if b in have]
    read = br + use_opt
    has_tl = "Sci_bar_TrackLength" in use_opt
    has_mom = all(f"Sci_bar_Momentum_{a}" in use_opt for a in "XYZ")

    # per-gain accumulators: stave counts for trigger none / acoinc
    counts = {(g, t): np.zeros(4, dtype=np.int64) for g in GAINS
              for t in ("none", "acoinc")}
    # B2 amplitude cross-check: gather deepest-stave==B2 light values at each gain
    b2_amp_light = {g: [] for g in GAINS}   # light of B2 when B2 is deepest fired (acoinc)
    stop = max_events if max_events > 0 else None
    n_events_total = 0

    for ch in tr.iterate(read, step_size=step_size, library="ak", entry_stop=stop):
        tid_j = ch["Sci_bar_TrackID"]
        nper = ak.to_numpy(ak.num(tid_j))
        nev = len(nper)
        ev = np.repeat(np.arange(nev), nper)
        tid = ak.to_numpy(ak.flatten(tid_j)).astype(np.int64)
        l1 = ak.to_numpy(ak.flatten(ch["Sci_bar_LayerID1"])).astype(np.int64)
        ly = ak.to_numpy(ak.flatten(ch["Sci_bar_LayerID"])).astype(np.int64)
        pdg = ak.to_numpy(ak.flatten(ch["Sci_bar_PDG"])).astype(np.int64)
        ed = ak.to_numpy(ak.flatten(ch["Sci_bar_EDep"])).astype(np.float64)
        tl = (ak.to_numpy(ak.flatten(ch["Sci_bar_TrackLength"])).astype(np.float64)
              if has_tl else None)
        if has_mom:
            px = ak.to_numpy(ak.flatten(ch["Sci_bar_Momentum_X"])).astype(np.float64)
            py = ak.to_numpy(ak.flatten(ch["Sci_bar_Momentum_Y"])).astype(np.float64)
            pz = ak.to_numpy(ak.flatten(ch["Sci_bar_Momentum_Z"])).astype(np.float64)
            # momentum branches are GeV/c -> MeV/c (matches mc02 builder)
            pmag = np.sqrt(px * px + py * py + pz * pz) * 1000.0
            mass = _mass_vec(pdg)
            ekin = np.sqrt(pmag * pmag + mass * mass) - mass
        else:
            ekin = None

        # ---------- A-stack trigger proxy: quenched light per (event,bar) -----
        mA = (l1 == A_ARM) & (ly >= 0) & (ly <= 3)
        if mA.any():
            lightA = hit_light(ev[mA], tid[mA], None if tl is None else tl[mA],
                               ed[mA], pdg[mA], None if ekin is None else ekin[mA])
            a_light = np.zeros((nev, 4))
            np.add.at(a_light, (ev[mA], ly[mA]), lightA)
            a_maxbar = a_light.max(axis=1)   # MeV light; trigger if gain*pf*max>thr
        else:
            a_maxbar = np.zeros(nev)

        # ---------- B-stack: per-hit quenched light, group by (event,track) ---
        mB = (l1 == B_ARM) & (ly >= 0) & (ly <= 7)
        if not mB.any():
            n_events_total += nev
            continue
        evb, tidb, lyb, pdgb, edb = ev[mB], tid[mB], ly[mB], pdg[mB], ed[mB]
        tlb = None if tl is None else tl[mB]
        ekb = None if ekin is None else ekin[mB]
        lightB = hit_light(evb, tidb, tlb, edb, pdgb, ekb)

        # group by (event, track); first-hit PDG = species-inclusive keeps all
        order = np.lexsort((tidb, evb))
        evb, tidb, lyb, lightB = evb[order], tidb[order], lyb[order], lightB[order]
        new = np.ones(len(evb), dtype=bool)
        new[1:] = (evb[1:] != evb[:-1]) | (tidb[1:] != tidb[:-1])
        gid = np.cumsum(new) - 1
        G = gid[-1] + 1
        starts = np.flatnonzero(new)
        g_ev = evb[starts]
        # paired-map light per group: layers {0,1}->B2 ... {6,7}->B8
        light8 = np.zeros((G, 8))
        np.add.at(light8, (gid, lyb), lightB)
        sedep = np.stack([light8[:, 0] + light8[:, 1],
                          light8[:, 2] + light8[:, 3],
                          light8[:, 4] + light8[:, 5],
                          light8[:, 6] + light8[:, 7]], axis=1)  # (G,4) light MeV

        # species-inclusive: all depositing groups
        g_any = light8.sum(axis=1) > 0

        # event basis: per-(event,stave) summed light over groups
        ev_stave = np.zeros((nev, 4))
        gm = g_any
        np.add.at(ev_stave,
                  (np.repeat(g_ev[gm], 4), np.tile(np.arange(4), gm.sum())),
                  sedep[gm].ravel())

        for gain in GAINS:
            thr_mev = THRESHOLD_NET / (gain * PEAK_FRAC)
            fired_ev = ev_stave > thr_mev
            hasE, deepE = deepest_fired(fired_ev)
            a_trig = a_maxbar > thr_mev
            for trig in ("none", "acoinc"):
                esel = hasE if trig == "none" else (hasE & a_trig)
                c = np.bincount(deepE[esel], minlength=4)
                counts[(gain, trig)] += c
            # B2 amplitude cross-check: events where B2 is deepest fired (acoinc)
            b2sel = (hasE & a_trig) & (deepE == 0)
            if b2sel.any():
                b2_amp_light[gain].append(ev_stave[b2sel, 0])

        n_events_total += nev

    b2_med = {}
    for g in GAINS:
        if b2_amp_light[g]:
            vals = np.concatenate(b2_amp_light[g])
            b2_med[g] = float(np.median(vals) * g * PEAK_FRAC)  # median B2 amplitude ADC
        else:
            b2_med[g] = None
    return counts, b2_med, n_events_total


def data_stopping_fractions(data_csv, threshold_net=THRESHOLD_NET):
    """Identical to MV3 v3 / v4: per-event deepest stave with |net| > threshold."""
    df = pd.read_csv(data_csv)
    df["net_adc"] = (df["amplitude_adc"] - df["baseline_adc"]).abs()
    df = df[df["net_adc"] > threshold_net]
    stave_rank = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    df["stave_rank"] = df["stave"].map(stave_rank)
    results = {}
    groups = [
        ("all", df),
        ("sample_i", df[df["group"].str.contains("sample_i") & ~df["group"].str.contains("sample_ii")]),
        ("sample_ii", df[df["group"].str.contains("sample_ii")]),
    ]
    for name, sub in groups:
        ev_deepest = sub.groupby(["run", "evt"])["stave_rank"].max()
        cnt = ev_deepest.value_counts().to_dict()
        counts = {s: int(cnt.get(i, 0)) for i, s in enumerate(STAVES)}
        total = sum(counts.values())
        results[name] = {
            "counts": counts, "n_events": total,
            "fractions": {s: counts[s] / total if total else 0.0 for s in STAVES},
        }
    # B2 net-amplitude median (all selected B2 rows) for the scale cross-check
    b2 = df[df["stave"] == "B2"]["net_adc"]
    results["b2_net_median_adc"] = float(np.median(b2)) if len(b2) else None
    return results


def chi2_vs(mc_counts: np.ndarray, data_counts: np.ndarray):
    tot = mc_counts.sum()
    if tot == 0:
        return None, 0
    mc_f = mc_counts / tot
    n_data = data_counts.sum()
    exp = mc_f * n_data
    ok = exp > 0
    chi2 = float(((data_counts[ok] - exp[ok]) ** 2 / exp[ok]).sum())
    ndf = int(ok.sum()) - 1
    return chi2, ndf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--step-size", default="200 MB")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"[quenched-scan] start={stamp}")

    data_res = data_stopping_fractions(args.data)
    for k in ("all", "sample_i", "sample_ii"):
        v = data_res[k]
        print(f"[data:{k}] n={v['n_events']} " +
              " ".join(f"{s}={v['fractions'][s]:.3f}" for s in STAVES))
    print(f"[data] B2 net-median ADC = {data_res['b2_net_median_adc']}")

    counts, b2_med, nev = run_scan(args.mc, args.tree, args.max_events, args.step_size)
    print(f"[quenched-scan] events processed: {nev}")

    data_arrays = {k: np.array([data_res[k]["counts"][s] for s in STAVES], dtype=float)
                   for k in ("all", "sample_i", "sample_ii")}

    rows = []
    for gain in GAINS:
        for trig in ("none", "acoinc"):
            c = counts[(gain, trig)]
            tot = int(c.sum())
            fr = (c / tot).tolist() if tot else [0.0] * 4
            thr_light = THRESHOLD_NET / (gain * PEAK_FRAC)
            row = {
                "gain": gain, "trigger": trig, "n": tot,
                "threshold_light_mev": thr_light,
                "fractions": {s: fr[i] for i, s in enumerate(STAVES)},
                "b2_amp_median_adc": b2_med.get(gain) if trig == "acoinc" else None,
            }
            for dk in ("all", "sample_i", "sample_ii"):
                chi2, ndf = chi2_vs(c.astype(float), data_arrays[dk])
                row[f"chi2_ndf_{dk}"] = (chi2 / max(ndf, 1)) if chi2 is not None else None
                row[f"chi2_{dk}"] = chi2
                row[f"ndf_{dk}"] = ndf
            rows.append(row)

    # primary curve = acoinc trigger vs data(all)
    acoinc = [r for r in rows if r["trigger"] == "acoinc"]
    scored = [r for r in acoinc if r["chi2_ndf_all"] is not None]
    best = min(scored, key=lambda r: r["chi2_ndf_all"]) if scored else None

    out = {
        "study_id": "MV3-B-M5-quenched-gain-scan",
        "generated_utc": stamp,
        "mc_file": args.mc,
        "n_events_processed": nev,
        "threshold_adc": THRESHOLD_NET, "peak_frac": PEAK_FRAC,
        "kb_cm_per_mev": KB_CM_PER_MEV,
        "config": "event basis, species-inclusive, paired map, A-arm trigger proxy, Birks ON",
        "gains_scanned": GAINS,
        "data": data_res,
        "best_acoinc_all": best,
        "grid": rows,
    }
    jpath = os.path.join(args.out, "mv3_gain_quenched.json")
    with open(jpath, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[quenched-scan] wrote {jpath}")

    mdpath = os.path.join(args.out, "gain_curve.md")
    with open(mdpath, "w") as fh:
        fh.write("# Quenched MV3 gain scan (event / inclusive / paired / trigger proxy / Birks ON)\n\n")
        fh.write(f"Data target (all): " + " ".join(
            f"{s}={data_res['all']['fractions'][s]:.3f}" for s in STAVES) + "\n\n")
        fh.write("| gain | thr light MeV | n | B2 | B4 | B6 | B8 | chi2/ndf all | chi2/ndf S-I | chi2/ndf S-II | B2 amp med ADC |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in acoinc:
            def f(x):
                return f"{x:.1f}" if x is not None else "-"
            b2a = r["b2_amp_median_adc"]
            fh.write(f"| {r['gain']:.0f} | {r['threshold_light_mev']:.3f} | {r['n']} | "
                     + " | ".join(f"{r['fractions'][s]:.3f}" for s in STAVES)
                     + f" | {f(r['chi2_ndf_all'])} | {f(r['chi2_ndf_sample_i'])} "
                     f"| {f(r['chi2_ndf_sample_ii'])} | "
                     + (f"{b2a:.0f}" if b2a is not None else "-") + " |\n")
    print(f"[quenched-scan] wrote {mdpath}")

    if best:
        print(f"[quenched-scan] BEST acoinc vs data(all): gain={best['gain']:.0f} "
              f"chi2/ndf={best['chi2_ndf_all']:.1f} n={best['n']} "
              + " ".join(f"{s}={best['fractions'][s]:.3f}" for s in STAVES)
              + f" B2ampMed={best['b2_amp_median_adc']}")
    print(f"[quenched-scan] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()

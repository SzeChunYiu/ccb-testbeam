#!/usr/bin/env python3
"""
mv3_stopping_v5_realtrigger.py
==============================
B-M1 / STUDY_GAPS NEW-01 : re-fit the MV3 stopping-depth profile with a REAL
simulated two-arm trigger, replacing the truth-level A-HRD coincidence PROXY of
mv3 v4 (which collapsed chi2/ndf 68,269 -> 625 but was only a proxy).

Input MC = a fresh hibeam_g4 Krakow production, IDENTICAL to the original 1M
sample except the trigger-paddle logical volume `Trig_bar` is added to the scored
`Detectors`, so the truth tree now carries genuine GEANT4 sensitive-detector
energy deposits in the A- and B-arm trigger paddles:

    Trig_bar_EDep      [MeV]  per-hit deposited energy in a trigger paddle
    Trig_bar_LayerID1         arm: 1 = B-arm (-38 deg), 2 = A-arm (+71.5 deg)
    Trig_bar_LayerID          paddle index (0,1 : the two staggered paddles)
    Trig_bar_Time      [ns]   hit time
    Trig_bar_PDG              true particle

REAL trigger (Sample I / two-arm coincidence):
    A_fired = max EDep over A-arm (LayerID1==2) paddle hits > TRIG_EDEP_THRESH
    B_fired = max EDep over B-arm (LayerID1==1) paddle hits > TRIG_EDEP_THRESH
    trigger = A_fired AND B_fired AND |t_A - t_B| < TRIG_WINDOW
This is a genuine energy-deposit coincidence in the paddle *volumes* (real SD
scoring), not the mv3 v4 truth-track-entry / A-HRD proxy.

The B-stack deepest-stave ("stopping depth") machinery and the chi2 are IDENTICAL
to mv3 v4 (imported), so the untriggered and proxy columns reproduce v4 bit-for-bit
and the ONLY new ingredient is the real trigger flag.

Trigger modes scored per grid point:
    none          : no trigger (MV3 v3 behaviour)              -> ~68,269 ref
    proxy_ahrd    : v4 proxy, require an A-HRD Sci_bar hit      -> ~3,141 / 625
    real_coinc    : REAL Trig_bar A&B paddle coincidence        <- the B-M1 result
    real_Aonly    : REAL A-paddle fired only (B implicit)       (sensitivity)

Output: mv3v5_grid.json + grid_table.md in --out.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mv3_stopping_v4_diagnostics import (  # noqa: E402
    STAVES, B_ARM, A_ARM, CHARGED_PDGS, PEAK_FRAC, THRESHOLD_NET, GAINS,
    MAPPINGS, deepest_fired, stave_edep_from_layers, chi2_vs,
    data_stopping_fractions,
)

TRIG_EDEP_THRESH = 0.5   # MeV in a trigger paddle to count as "fired" (MIP ~2 MeV)
TRIG_WINDOW = 20.0       # ns A/B coincidence window (prompt MC: TOF-limited)
TRIG_MODES = ("none", "proxy_ahrd", "real_coinc", "real_Aonly")
# scored axes kept deliberately close to v4's decisive points
BASES = ("track", "event")
SPECIES = ("filtered", "inclusive")
MAPPING = "paired"       # v4 closed the mapping question -> paired stands


def run_grid_v5(mc_path, tree, max_events, step_size,
                trig_thresh=TRIG_EDEP_THRESH, trig_window=TRIG_WINDOW):
    import uproot
    import awkward as ak

    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_LayerID",
          "Sci_bar_PDG", "Sci_bar_EDep",
          "Trig_bar_LayerID1", "Trig_bar_EDep", "Trig_bar_Time"]

    combos = []
    for basis in BASES:
        for species in SPECIES:
            for gain in GAINS:
                for trig in TRIG_MODES:
                    combos.append((basis, species, MAPPING, gain, trig))
    counts = {c: np.zeros(4, dtype=np.int64) for c in combos}

    # real-trigger diagnostics
    trig_diag = {"n_events": 0, "A_fired": 0, "B_fired": 0, "coinc": 0,
                 "proxy_ahrd": 0}
    # composition of the real-trigger-selected B profile (event basis, paired, g92)
    comp_real = {}

    tr = uproot.open(mc_path)[tree]
    stop = max_events if max_events > 0 else None

    for ch in tr.iterate(br, step_size=step_size, library="ak", entry_stop=stop):
        tid_j = ch["Sci_bar_TrackID"]
        nper = ak.to_numpy(ak.num(tid_j))
        nev = len(nper)
        ev = np.repeat(np.arange(nev), nper)
        tid = ak.to_numpy(ak.flatten(tid_j)).astype(np.int64)
        l1 = ak.to_numpy(ak.flatten(ch["Sci_bar_LayerID1"])).astype(np.int64)
        ly = ak.to_numpy(ak.flatten(ch["Sci_bar_LayerID"])).astype(np.int64)
        pdg = ak.to_numpy(ak.flatten(ch["Sci_bar_PDG"])).astype(np.int64)
        ed = ak.to_numpy(ak.flatten(ch["Sci_bar_EDep"])).astype(np.float64)

        # ---------- A-HRD proxy (v4): per (event,bar) summed A-stack Sci_bar edep
        mA = (l1 == A_ARM) & (ly >= 0) & (ly <= 3)
        a_edep = np.zeros((nev, 4))
        np.add.at(a_edep, (ev[mA], ly[mA]), ed[mA])
        a_maxbar = a_edep.max(axis=1)   # gain*pf*max > thr => proxy fires

        # ---------- REAL trigger from Trig_bar SD deposits --------------------
        t_arm = ch["Trig_bar_LayerID1"]
        t_ed = ch["Trig_bar_EDep"]
        t_tm = ch["Trig_bar_Time"]
        # per-event max paddle EDep + its time, per arm
        a_mask = (t_arm == A_ARM)
        b_mask = (t_arm == B_ARM)
        a_ed_ev = ak.to_numpy(ak.fill_none(ak.max(ak.where(a_mask, t_ed, -1.0), axis=1), -1.0))
        b_ed_ev = ak.to_numpy(ak.fill_none(ak.max(ak.where(b_mask, t_ed, -1.0), axis=1), -1.0))
        # representative (earliest above-threshold) time per arm for the window cut
        big = 1e9
        a_t_ev = ak.to_numpy(ak.fill_none(ak.min(ak.where(a_mask & (t_ed > trig_thresh), t_tm, big), axis=1), big))
        b_t_ev = ak.to_numpy(ak.fill_none(ak.min(ak.where(b_mask & (t_ed > trig_thresh), t_tm, big), axis=1), big))
        A_fired = a_ed_ev > trig_thresh
        B_fired = b_ed_ev > trig_thresh
        coinc_time = np.abs(a_t_ev - b_t_ev) < trig_window
        real_coinc = A_fired & B_fired & coinc_time
        real_Aonly = A_fired

        trig_diag["n_events"] += nev
        trig_diag["A_fired"] += int(A_fired.sum())
        trig_diag["B_fired"] += int(B_fired.sum())
        trig_diag["coinc"] += int(real_coinc.sum())

        # ---------- B-stack: group hits by (event, track) --------------------
        mB = (l1 == B_ARM) & (ly >= 0) & (ly <= 7)
        evb, tidb, lyb, pdgb, edb = ev[mB], tid[mB], ly[mB], pdg[mB], ed[mB]
        if len(evb) == 0:
            continue
        order = np.lexsort((tidb, evb))
        evb, tidb, lyb, pdgb, edb = (evb[order], tidb[order], lyb[order],
                                     pdgb[order], edb[order])
        new = np.ones(len(evb), dtype=bool)
        new[1:] = (evb[1:] != evb[:-1]) | (tidb[1:] != tidb[:-1])
        gid = np.cumsum(new) - 1
        G = gid[-1] + 1
        starts = np.flatnonzero(new)
        g_ev = evb[starts]
        g_pdg = np.abs(pdgb[starts])
        edep8 = np.zeros((G, 8))
        np.add.at(edep8, (gid, lyb), edb)

        g_filtered = np.isin(g_pdg, CHARGED_PDGS)
        g_any = edep8.sum(axis=1) > 0
        species_masks = {"filtered": g_filtered & g_any, "inclusive": g_any}

        # per-event trigger selectors keyed by trigger mode (indexed by g_ev)
        def trig_event_mask(mode):
            if mode == "none":
                return np.ones(nev, dtype=bool)
            if mode == "proxy_ahrd":
                return None  # gain-dependent, handled inline
            if mode == "real_coinc":
                return real_coinc
            if mode == "real_Aonly":
                return real_Aonly
            raise ValueError(mode)

        sedep = stave_edep_from_layers(edep8, MAPPING)  # (G,4) MeV
        for gain in GAINS:
            thr_mev = THRESHOLD_NET / (gain * PEAK_FRAC)
            fired_trk = sedep > thr_mev
            a_trig_proxy = a_maxbar > thr_mev            # (nev,)
            has, deep = deepest_fired(fired_trk)
            # event-basis per-(event,stave) summed edep is species-dependent
            for species, smask in species_masks.items():
                # ---- track basis ----
                sel_base = smask & has
                for trig in TRIG_MODES:
                    if trig == "proxy_ahrd":
                        tmask_ev = a_trig_proxy
                    else:
                        tmask_ev = trig_event_mask(trig)
                    tsel = sel_base & tmask_ev[g_ev]
                    counts[("track", species, MAPPING, gain, trig)] += \
                        np.bincount(deep[tsel], minlength=4)
                # ---- event basis ----
                ev_stave = np.zeros((nev, 4))
                gm = smask
                np.add.at(ev_stave, (np.repeat(g_ev[gm], 4),
                                     np.tile(np.arange(4), gm.sum())),
                          sedep[gm].ravel())
                fired_ev = ev_stave > thr_mev
                hasE, deepE = deepest_fired(fired_ev)
                for trig in TRIG_MODES:
                    if trig == "proxy_ahrd":
                        tmask_ev = a_trig_proxy
                    else:
                        tmask_ev = trig_event_mask(trig)
                    esel = hasE & tmask_ev
                    counts[("event", species, MAPPING, gain, trig)] += \
                        np.bincount(deepE[esel], minlength=4)

        # composition of the real-coincidence-selected B profile (paired, g92, track)
        thr92 = THRESHOLD_NET / (92.0 * PEAK_FRAC)
        has92, deep92 = deepest_fired(sedep > thr92)
        from mv3_stopping_v4_diagnostics import classify_pdg
        cls = classify_pdg(g_pdg)
        sel = g_any & has92 & real_coinc[g_ev]
        for cname in np.unique(cls[sel]):
            m = sel & (cls == cname)
            c = np.bincount(deep92[m], minlength=4)
            comp_real[str(cname)] = (np.asarray(comp_real.get(str(cname), np.zeros(4, dtype=np.int64))) + c).tolist()

    trig_diag["proxy_ahrd"] = None  # proxy count is gain-dependent; omit scalar
    return counts, trig_diag, comp_real


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--step-size", default="200 MB")
    ap.add_argument("--trig-thresh", type=float, default=TRIG_EDEP_THRESH)
    ap.add_argument("--trig-window", type=float, default=TRIG_WINDOW)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"[mv3v5] start={stamp} thresh={args.trig_thresh} window={args.trig_window}")

    data_res = data_stopping_fractions(args.data)
    for k, v in data_res.items():
        print(f"[data:{k}] n={v['n_events']} " +
              " ".join(f"{s}={v['fractions'][s]:.3f}" for s in STAVES))

    counts, trig_diag, comp_real = run_grid_v5(
        args.mc, args.tree, args.max_events, args.step_size,
        args.trig_thresh, args.trig_window)
    print(f"[mv3v5] trigger diag: {trig_diag}")

    data_arrays = {k: np.array([v["counts"][s] for s in STAVES], dtype=float)
                   for k, v in data_res.items()}

    rows = []
    for (basis, species, mapping, gain, trig), c in counts.items():
        tot = int(c.sum())
        fr = (c / tot).tolist() if tot else [0.0] * 4
        row = {"basis": basis, "species": species, "mapping": mapping,
               "gain": gain, "trigger": trig, "n": tot,
               "fractions": {s: fr[i] for i, s in enumerate(STAVES)}}
        for dk in ("all", "sample_i", "sample_ii"):
            chi2, ndf = chi2_vs(c.astype(float), data_arrays[dk])
            row[f"chi2_ndf_{dk}"] = (chi2 / max(ndf, 1)) if chi2 is not None else None
        rows.append(row)
    rows.sort(key=lambda r: (r["chi2_ndf_all"] if r["chi2_ndf_all"] is not None else 1e30))

    out = {
        "study_id": "MV3v5-realtrigger",
        "generated_utc": stamp,
        "mc_file": args.mc,
        "trig_edep_thresh_mev": args.trig_thresh,
        "trig_window_ns": args.trig_window,
        "threshold_adc": THRESHOLD_NET, "peak_frac": PEAK_FRAC,
        "gains_scanned": GAINS,
        "trigger_diagnostics": trig_diag,
        "data": data_res,
        "composition_real_coinc_paired_g92_track": comp_real,
        "grid": rows,
    }
    jpath = os.path.join(args.out, "mv3v5_grid.json")
    with open(jpath, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[mv3v5] wrote {jpath}")

    mdpath = os.path.join(args.out, "grid_table.md")
    with open(mdpath, "w") as fh:
        fh.write("| basis | species | mapping | gain | trigger | n | B2 | B4 | B6 | B8 "
                 "| chi2/ndf all | chi2/ndf S-I | chi2/ndf S-II |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows[:60]:
            fh.write(f"| {r['basis']} | {r['species']} | {r['mapping']} | {r['gain']:.0f} "
                     f"| {r['trigger']} | {r['n']} | "
                     + " | ".join(f"{r['fractions'][s]:.3f}" for s in STAVES)
                     + f" | {r['chi2_ndf_all']:.1f} | {r['chi2_ndf_sample_i']:.1f} "
                     f"| {r['chi2_ndf_sample_ii']:.1f} |\n")
    print(f"[mv3v5] wrote {mdpath}")

    # key reference points
    def find(basis, species, gain, trig):
        for r in rows:
            if (r["basis"], r["species"], r["gain"], r["trigger"]) == (basis, species, gain, trig):
                return r
        return None
    for label, (b, s, g, tg) in {
        "untriggered ref (track/filtered/g92)": ("track", "filtered", 92.0, "none"),
        "proxy A-HRD (event/inclusive/g60)": ("event", "inclusive", 60.0, "proxy_ahrd"),
        "REAL coinc (event/inclusive/g60)": ("event", "inclusive", 60.0, "real_coinc"),
        "REAL coinc (track/inclusive/g60)": ("track", "inclusive", 60.0, "real_coinc"),
    }.items():
        r = find(b, s, g, tg)
        if r:
            print(f"[mv3v5] {label}: chi2/ndf(all)={r['chi2_ndf_all']:.1f} n={r['n']} "
                  + " ".join(f"{k}={r['fractions'][k]:.3f}" for k in STAVES))
    best = rows[0]
    print(f"[mv3v5] BEST: {best['basis']}/{best['species']}/g{best['gain']:.0f}/{best['trigger']} "
          f"chi2/ndf={best['chi2_ndf_all']:.1f} "
          + " ".join(f"{k}={best['fractions'][k]:.3f}" for k in STAVES))
    print(f"[mv3v5] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
mv3_stopping_v4_diagnostics.py
==============================
Phase-2 stage-2 CHEAP diagnostics on the EXISTING 1M truth sample: how much of
the MV3 v3 FAIL (chi2/ndf = 68,269) is explained WITHOUT new geometry?

Recomputes the MC deepest-stave ("stopping-depth") profile over a full grid of
comparison-hypothesis axes, against the fixed data profile:

  axes
  ----
  basis   : track  (MV3 v3 behaviour: per-track deepest fired stave)
            event  (data-like: per-event, per-stave edep summed over tracks,
                    deepest stave whose summed pulse is above threshold)
  species : filtered   (MV3 v3 CHARGED_PDGS = {p, d, e, mu, pi, K})
            inclusive  (ALL depositing tracks: adds alpha, C12, He3, t, ions)
  mapping : paired    ({0,1}->B2, {2,3}->B4, {4,5}->B6, {6,7}->B8; MV3 v3 guess)
            odd_read  (bars B1..B8 = layers 0..7; only even-numbered bars read:
                       layers 1,3,5,7 -> B2,B4,B6,B8; even layers unread)
            even_read (layers 0,2,4,6 -> B2,B4,B6,B8; odd layers unread)
  gain    : scan 60..300 ADC/MeV (gain is unknown; MV0 anchors disagree 60..297)
  trigger : none    (MV3 v3 behaviour: no trigger simulated)
            acoinc  (proxy for the Sample-I two-arm coincidence trigger:
                     require >=1 A-stack bar (LayerID1==2) with summed edep
                     above the same ADC threshold at the same gain)

Threshold model identical to MV3 v3: peak_adc = gain * edep * peak_frac(0.733);
fired if > 1000 ADC net.

chi2 identical to MV3 v3: expected = mc_frac * n_data_events,
chi2 = sum (obs-exp)^2/exp over staves with exp>0; ndf = (#mc_frac>0) - 1.
Every combo is scored against data(all), data(sample_i) and data(sample_ii).

Output: mv3v4_grid.json + REPORT-ready markdown table (grid_table.md).
"""
from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

STAVES = ["B2", "B4", "B6", "B8"]
B_ARM, A_ARM = 1, 2
CHARGED_PDGS = np.array([2212, 1000010020, 11, 13, 211, 321])
PEAK_FRAC = 0.7330
THRESHOLD_NET = 1000.0
GAINS = [60.0, 80.0, 92.0, 110.0, 130.0, 150.0, 180.0, 220.0, 260.0, 297.0, 300.0]

MAPPINGS = {
    # kind, spec
    "paired":    ("pair",   [(0, 1), (2, 3), (4, 5), (6, 7)]),
    "odd_read":  ("single", [1, 3, 5, 7]),
    "even_read": ("single", [0, 2, 4, 6]),
}

PDG_CLASS = [
    (2212, "p"), (1000010020, "d"), (1000010030, "t"),
    (1000020030, "He3"), (1000020040, "alpha"), (1000060120, "C12"),
]


def classify_pdg(pdg_abs: np.ndarray) -> np.ndarray:
    out = np.full(pdg_abs.shape, "other", dtype=object)
    for code, name in PDG_CLASS:
        out[pdg_abs == code] = name
    out[np.isin(pdg_abs, (11, 13, 211, 321))] = "e/mu/pi/K"
    ion = (pdg_abs > 1000000000) & (out == "other")
    out[ion] = "other_ion"
    return out


def stave_edep_from_layers(edep8: np.ndarray, mapping: str) -> np.ndarray:
    kind, spec = MAPPINGS[mapping]
    if kind == "pair":
        return np.stack([edep8[:, a] + edep8[:, b] for a, b in spec], axis=1)
    return edep8[:, spec]


def deepest_fired(fired: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """fired: (N,4) bool -> (has_any, deepest_index)."""
    has = fired.any(axis=1)
    deep = 3 - np.argmax(fired[:, ::-1], axis=1)
    return has, deep


def run_grid(mc_path: str, tree: str, max_events: int, step_size: str):
    import uproot

    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_LayerID",
          "Sci_bar_PDG", "Sci_bar_EDep"]

    combos = []
    for basis in ("track", "event"):
        for species in ("filtered", "inclusive"):
            for mapping in MAPPINGS:
                for gain in GAINS:
                    for trig in ("none", "acoinc"):
                        combos.append((basis, species, mapping, gain, trig))
    counts = {c: np.zeros(4, dtype=np.int64) for c in combos}
    none_fired = {c: 0 for c in combos}

    # composition bookkeeping at the reference point (paired, gain=92, track, none)
    comp_ref = {}

    tr = uproot.open(mc_path)[tree]
    stop = max_events if max_events > 0 else None
    n_events_total = 0

    for ch in tr.iterate(br, step_size=step_size, library="ak", entry_stop=stop):
        import awkward as ak
        tid_j = ch["Sci_bar_TrackID"]
        nper = ak.to_numpy(ak.num(tid_j))
        nev = len(nper)
        ev = np.repeat(np.arange(nev), nper)
        tid = ak.to_numpy(ak.flatten(tid_j)).astype(np.int64)
        l1 = ak.to_numpy(ak.flatten(ch["Sci_bar_LayerID1"])).astype(np.int64)
        ly = ak.to_numpy(ak.flatten(ch["Sci_bar_LayerID"])).astype(np.int64)
        pdg = ak.to_numpy(ak.flatten(ch["Sci_bar_PDG"])).astype(np.int64)
        ed = ak.to_numpy(ak.flatten(ch["Sci_bar_EDep"])).astype(np.float64)

        # ---------- A-stack (trigger proxy): per (event, bar) summed edep ----
        mA = (l1 == A_ARM) & (ly >= 0) & (ly <= 3)
        a_edep = np.zeros((nev, 4))
        np.add.at(a_edep, (ev[mA], ly[mA]), ed[mA])
        a_maxbar = a_edep.max(axis=1)  # MeV; trigger fires if gain*pf*max > thr

        # ---------- B-stack: group hits by (event, track) --------------------
        mB = (l1 == B_ARM) & (ly >= 0) & (ly <= 7)
        evb, tidb, lyb, pdgb, edb = ev[mB], tid[mB], ly[mB], pdg[mB], ed[mB]
        if len(evb) == 0:
            n_events_total += nev
            continue
        order = np.lexsort((tidb, evb))  # stable: original hit order kept in ties
        evb, tidb, lyb, pdgb, edb = (evb[order], tidb[order], lyb[order],
                                     pdgb[order], edb[order])
        new = np.ones(len(evb), dtype=bool)
        new[1:] = (evb[1:] != evb[:-1]) | (tidb[1:] != tidb[:-1])
        gid = np.cumsum(new) - 1
        G = gid[-1] + 1
        starts = np.flatnonzero(new)
        g_ev = evb[starts]
        g_pdg = np.abs(pdgb[starts])   # first hit's PDG, as in MV3 v3
        edep8 = np.zeros((G, 8))
        np.add.at(edep8, (gid, lyb), edb)

        g_filtered = np.isin(g_pdg, CHARGED_PDGS)
        g_any = edep8.sum(axis=1) > 0
        species_masks = {"filtered": g_filtered & g_any, "inclusive": g_any}

        for mapping in MAPPINGS:
            sedep = stave_edep_from_layers(edep8, mapping)  # (G,4) MeV
            for gain in GAINS:
                thr_mev = THRESHOLD_NET / (gain * PEAK_FRAC)
                fired_trk = sedep > thr_mev                # (G,4)
                a_trig = a_maxbar > thr_mev                # (nev,)
                for species, smask in species_masks.items():
                    # ---- track basis ----
                    has, deep = deepest_fired(fired_trk)
                    sel = smask & has
                    for trig in ("none", "acoinc"):
                        tsel = sel if trig == "none" else (sel & a_trig[g_ev])
                        c = np.bincount(deep[tsel], minlength=4)
                        counts[("track", species, mapping, gain, trig)] += c
                        nofire = smask if trig == "none" else (smask & a_trig[g_ev])
                        none_fired[("track", species, mapping, gain, trig)] += int(
                            (nofire & ~has).sum())
                    # ---- event basis: per-(event,stave) summed edep ----
                    ev_stave = np.zeros((nev, 4))
                    gm = smask
                    np.add.at(ev_stave, (np.repeat(g_ev[gm], 4),
                                         np.tile(np.arange(4), gm.sum())),
                              sedep[gm].ravel())
                    fired_ev = ev_stave > thr_mev
                    hasE, deepE = deepest_fired(fired_ev)
                    for trig in ("none", "acoinc"):
                        esel = hasE if trig == "none" else (hasE & a_trig)
                        c = np.bincount(deepE[esel], minlength=4)
                        counts[("event", species, mapping, gain, trig)] += c

        # composition at reference point: paired, gain 92, track basis, no trig
        sedep = stave_edep_from_layers(edep8, "paired")
        thr_mev = THRESHOLD_NET / (92.0 * PEAK_FRAC)
        has, deep = deepest_fired(sedep > thr_mev)
        cls = classify_pdg(g_pdg)
        sel = g_any & has
        for cname in np.unique(cls[sel]):
            m = sel & (cls == cname)
            c = np.bincount(deep[m], minlength=4)
            comp_ref[str(cname)] = (np.asarray(comp_ref.get(str(cname), np.zeros(4, dtype=np.int64)))
                                    + c).tolist()

        n_events_total += nev

    return counts, none_fired, comp_ref, n_events_total


def data_stopping_fractions(data_csv, threshold_net=THRESHOLD_NET):
    """Identical to MV3 v3: per-event deepest stave with net_adc > threshold."""
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
    print(f"[mv3v4] start={stamp}")

    data_res = data_stopping_fractions(args.data)
    for k, v in data_res.items():
        print(f"[data:{k}] n={v['n_events']} " +
              " ".join(f"{s}={v['fractions'][s]:.3f}" for s in STAVES))

    counts, none_fired, comp_ref, nev = run_grid(
        args.mc, args.tree, args.max_events, args.step_size)
    print(f"[mv3v4] events processed: {nev}")

    data_arrays = {k: np.array([v["counts"][s] for s in STAVES], dtype=float)
                   for k, v in data_res.items()}

    rows = []
    for (basis, species, mapping, gain, trig), c in counts.items():
        tot = int(c.sum())
        fr = (c / tot).tolist() if tot else [0.0] * 4
        row = {
            "basis": basis, "species": species, "mapping": mapping,
            "gain": gain, "trigger": trig, "n": tot,
            "fractions": {s: fr[i] for i, s in enumerate(STAVES)},
        }
        for dk in ("all", "sample_i", "sample_ii"):
            chi2, ndf = chi2_vs(c.astype(float), data_arrays[dk])
            row[f"chi2_ndf_{dk}"] = (chi2 / max(ndf, 1)) if chi2 is not None else None
        rows.append(row)
    rows.sort(key=lambda r: (r["chi2_ndf_all"] if r["chi2_ndf_all"] is not None else 1e30))

    out = {
        "study_id": "MV3v4-diagnostic-grid",
        "generated_utc": stamp,
        "mc_file": args.mc,
        "n_events_processed": nev,
        "threshold_adc": THRESHOLD_NET, "peak_frac": PEAK_FRAC,
        "gains_scanned": GAINS,
        "data": data_res,
        "composition_ref_paired_g92_track": comp_ref,
        "grid": rows,
    }
    jpath = os.path.join(args.out, "mv3v4_grid.json")
    with open(jpath, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[mv3v4] wrote {jpath}")

    # markdown table: best 40 + the MV3 v3 reference row
    mdpath = os.path.join(args.out, "grid_table.md")
    with open(mdpath, "w") as fh:
        fh.write("| basis | species | mapping | gain | trigger | n | B2 | B4 | B6 | B8 "
                 "| chi2/ndf all | chi2/ndf S-I | chi2/ndf S-II |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows[:40]:
            fh.write(f"| {r['basis']} | {r['species']} | {r['mapping']} | {r['gain']:.0f} "
                     f"| {r['trigger']} | {r['n']} | "
                     + " | ".join(f"{r['fractions'][s]:.3f}" for s in STAVES)
                     + f" | {r['chi2_ndf_all']:.1f} | {r['chi2_ndf_sample_i']:.1f} "
                     f"| {r['chi2_ndf_sample_ii']:.1f} |\n")
    print(f"[mv3v4] wrote {mdpath}")

    best = rows[0]
    print("[mv3v4] BEST vs data(all): "
          f"{best['basis']}/{best['species']}/{best['mapping']}/gain={best['gain']:.0f}/"
          f"{best['trigger']} chi2/ndf={best['chi2_ndf_all']:.1f} "
          + " ".join(f"{s}={best['fractions'][s]:.3f}" for s in STAVES))
    # reference: MV3 v3 point
    for r in rows:
        if (r["basis"], r["species"], r["mapping"], r["gain"], r["trigger"]) == \
           ("track", "filtered", "paired", 92.0, "none"):
            print(f"[mv3v4] MV3v3 reference point chi2/ndf(all)={r['chi2_ndf_all']:.1f} "
                  + " ".join(f"{s}={r['fractions'][s]:.3f}" for s in STAVES))
    print(f"[mv3v4] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()

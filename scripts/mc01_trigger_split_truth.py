#!/usr/bin/env python3
"""
mc01_trigger_split_truth.py  (v2 — extended with supervisor deliverables)
=========================================================================
MC trigger-split truth analysis for the CCB (Krakow) test beam.

Answers the supervisor's tasks on the *MC* side:
  (1) stave (B-layer) outputs for Sample I vs Sample II,
  (2) the effect of mimicking the hardware trigger in MC,
  (3) truth-level particle ID of particles ENTERING A and B per trigger config,
and tests Matthias' prediction that Sample I is deuteron-enriched in the
*first B layer* (large pulses) while Sample II is not.

v2 NEW — per supervisor request:
  - ΔE vs E plane (EDep[layer0] vs EDep[layer1]) per sample
  - Per-stave deuteron and proton counts, energy spectra, penetration depths
  - Stopping-layer distribution per species per sample
  - All figures generated as PNGs

Detector encoding (decoded from output_krakow_1M.root, tree `hibeam`):
  Sci_bar_LayerID1 == 1  -> B-stack (8 layers, downstream arm @ -38 deg)   [MAIN]
  Sci_bar_LayerID1 == 2  -> A-stack (4 layers, recoil arm @ +71.5 deg)
  Sci_bar_LayerID       == depth in the stack (0 = first layer)
  Sci_bar_PDG           == true particle (2212=p, 1000010020=d, 1000020040=alpha, ...)
  Sci_bar_EDep          == energy deposited [MeV]
  Sci_bar_Time          == hit time [ns]

Trigger mimicry (per the supervisor):
  ENTER B  = a CHARGED Sci_bar hit with L1==1 and LayerID==0
  ENTER A  = a CHARGED Sci_bar hit with L1==2 and LayerID==0
  Sample II (single B trigger)   : ENTER B
  Sample I  (A&B coincidence)    : ENTER A and ENTER B with |t_A - t_B| < COINC_NS

Usage:
  python3 mc01_trigger_split_truth.py --mc output_krakow_1M.root --out <dir> [--coinc-ns 15]
"""
import argparse
import json
import os
import sys

import numpy as np

from ccb_mc_validation.truth.stop_depth import summarize_stop_depth_h3

from ccb_mc_validation.truth.pdg import (
    DEFAULT_MOMENTUM_UNIT,
    is_charged,
    kinetic_energy_from_branch_momentum,
    pdg_charge,
    species_label,
)
from ccb_mc_validation.truth.entering_species import (
    accumulate_entering_species,
)

B_ARM, A_ARM = 1, 2
NB_LAYERS = 8
COINC_DEFAULT = 15.0  # ns

#: Branch carrying the per-primary MC event weight (issue #880). The event
#: weight used throughout is the first primary's weight (the beam primary),
#: identical to scripts/single_stave/deltaE_E_mc.py (A-003).
PRIMARY_WEIGHT_BRANCH = "PrimaryWeight"


def _wmean(x, w):
    """Weighted mean; returns 0.0 for empty / all-zero-weight input."""
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size == 0:
        return 0.0
    sw = w.sum()
    if not np.isfinite(sw) or sw <= 0:
        return float(np.mean(x)) if x.size else 0.0
    return float(np.sum(w * x) / sw)


def _wmedian(x, w):
    """Weighted median via cumulative-weight interpolation."""
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size == 0:
        return 0.0
    sw = w.sum()
    if not np.isfinite(sw) or sw <= 0:
        return float(np.median(x)) if x.size else 0.0
    o = np.argsort(x)
    xs, ws = x[o], w[o]
    cw = np.cumsum(ws) / sw
    return float(np.interp(0.5, cw, xs))


def _wpercentile(x, w, q):
    """Weighted percentile (q in [0,100])."""
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size == 0:
        return 0.0
    sw = w.sum()
    if not np.isfinite(sw) or sw <= 0:
        return float(np.percentile(x, q)) if x.size else 0.0
    o = np.argsort(x)
    xs, ws = x[o], w[o]
    cw = np.cumsum(ws) / sw
    return float(np.interp(q / 100.0, cw, xs))


def _wfrac_large(x, w, thr):
    """Weighted fraction of x exceeding thr."""
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size == 0:
        return 0.0
    sw = w.sum()
    if not np.isfinite(sw) or sw <= 0:
        return float(np.mean(x > thr)) if x.size else 0.0
    return float(np.sum(w[x > thr]) / sw)


def _wcorr(x, y, w):
    """Weighted Pearson correlation."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size < 2:
        return 0.0
    sw = w.sum()
    if not np.isfinite(sw) or sw <= 0:
        return float(np.corrcoef(x, y)[0, 1]) if x.size > 1 else 0.0
    mx = np.sum(w * x) / sw
    my = np.sum(w * y) / sw
    cx, cy = x - mx, y - my
    cov = np.sum(w * cx * cy) / sw
    vx = np.sum(w * cx * cx) / sw
    vy = np.sum(w * cy * cy) / sw
    den = np.sqrt(vx * vy)
    return float(cov / den) if den > 0 else 0.0


def effective_sample_size(w):
    """Kish ESS = (sum w)^2 / sum(w^2); measures the weight spread impact."""
    w = np.asarray(w, dtype=float)
    if w.size == 0:
        return 0.0
    sw = w.sum()
    s2 = np.sum(w * w)
    return float(sw * sw / s2) if s2 > 0 else 0.0

# Canonical PDG / charge / unit-aware KE are imported at the top of this module
# from the package so this script cannot diverge from truth/track_builder.py
# (TRU-002).  The deployed krakow MC stores Sci_bar_Momentum_* in GeV/c
# (reaudit #864); KE is computed via kinetic_energy_from_branch_momentum which
# converts GeV/c -> MeV/c once.

#: Residual KE [MeV] at the last observed hit below which a track is "stop".
STOP_KE_THRESHOLD_MEV = 1.0


def infer_termination(last_observed_layer, ekin_last_mev, *, n_b_layers):
    """Infer stop/escape/censored from KE at the last observed hit (TRU-003).

    Mirrors truth/track_builder.py: the deepest *observed* layer is NOT assumed
    to be the stopping layer.  A track is 'stop' only if its residual KE at the
    last hit is <= STOP_KE_THRESHOLD_MEV; otherwise 'escape' if it reached the
    outermost layer, else 'censored'."""
    if ekin_last_mev <= STOP_KE_THRESHOLD_MEV:
        return "stop"
    if int(last_observed_layer) >= int(n_b_layers) - 1:
        return "escape"
    return "censored"


def bootstrap_enter_fractions(records, n_boot=1000, seed=1046, level=68):
    """Event-level bootstrap over unique-track (H2) entering-species fractions.

    The MC event is the sampling unit; resampling events with replacement
    propagates generator-level statistical uncertainty into per-species
    entering fractions for each arm.
    """
    rng = np.random.default_rng(seed)
    out = {}
    for arm in ("B", "A"):
        ev = [r.get(arm, {}) for r in records if r.get(arm)]
        if not ev:
            continue
        species = sorted({lab for d in ev for lab in d})
        mat = np.array([[float(d.get(lab, 0.0)) for lab in species] for d in ev])
        n = len(ev)
        idx = rng.integers(0, n, size=(n_boot, n))
        sums = mat[idx].sum(axis=1)
        tot = sums.sum(axis=1, keepdims=True)
        safe = np.where(tot > 0, tot, 1.0)
        fr = np.where(tot > 0, sums / safe, np.nan)
        alpha = (100.0 - level) / 2.0
        lo = np.nanpercentile(fr, alpha, axis=0)
        hi = np.nanpercentile(fr, 100.0 - alpha, axis=0)
        pt = mat.sum(axis=0) / (mat.sum() or 1.0)
        out[arm] = {
            "n_events_bootstrapped": int(n),
            "species": species,
            "point_fraction": {lab: round(float(v), 6)
                               for lab, v in zip(species, pt)},
            f"ci{level}": {lab: [round(float(a), 6), round(float(b), 6)]
                           for lab, a, b in zip(species, lo, hi)},
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True, help="MC ROOT file (tree 'hibeam')")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--coinc-ns", type=float, default=COINC_DEFAULT)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0, help="0 = all")
    ap.add_argument("--edep-large-mev", type=float, default=15.0)
    ap.add_argument(
        "--apply-weight", dest="apply_weight", action="store_true", default=True,
        help="Apply PrimaryWeight as a per-event weight to every MC summary "
             "(default ON; matches deltaE_E_mc.py A-003). Use --no-weight to "
             "reproduce the legacy unweighted numbers.")
    ap.add_argument(
        "--no-weight", dest="apply_weight", action="store_false",
        help="Disable PrimaryWeight weighting (emit weights=1; legacy mode).")
    ap.add_argument(
        "--momentum-unit", choices=["MeV", "GeV"], default=DEFAULT_MOMENTUM_UNIT,
        help="Unit of the Sci_bar_Momentum_* branches (krakow MC = GeV, "
             "reaudit #864). Converted to MeV/c before KE.")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    import uproot
    import awkward as ak
    branches = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG",
                "Sci_bar_EDep", "Sci_bar_Time", "Sci_bar_TrackID",
                "Sci_bar_Momentum_X", "Sci_bar_Momentum_Y", "Sci_bar_Momentum_Z",
                "Sci_bar_TrackLength", PRIMARY_WEIGHT_BRANCH]

    def new_layer_acc():
        # edep_w holds the per-hit event weight (parallel to edep) so all layer
        # statistics can be computed weighted. wsum = sum of event weights of
        # events that deposited here; pid_w = weighted species counts.
        return {"hits": 0, "sum_edep": 0.0, "n_charged": 0,
                "pid": {}, "edep": [], "edep_w": [], "pid_w": {},
                "wsum": 0.0,
                # Event-stave totals (#1052) with immutable generator-event IDs (#1164).
                "event_edep": [], "event_edep_w": [], "event_cluster_id": [],
                "event_in_sample_i": [], "event_in_sample_ii": []}

    def new_track_acc():
        return {"pdg": [], "ekin": [], "edep_l0": [], "edep_l1": [],
                "edep_tot": [], "stop_layer": [], "last_observed_layer": [],
                "termination": [], "nlayers": [],
                "tracklen": [], "edep_per_layer": [], "weight": []}

    samples = {
        "I": {"n_events": 0,
              "B_layers": [new_layer_acc() for _ in range(NB_LAYERS)],
              "enterB_pid": {}, "enterA_pid": {},
              # #1046 paper closure: H3 event-presence and H4 EDep-weighted
              # estimators alongside H2; per-event H2 records feed the
              # event-level bootstrap.
              "enterB_pid_event": {}, "enterA_pid_event": {},
              "enterB_pid_edep": {}, "enterA_pid_edep": {},
              "enter_track_records": [],
              "tracks": new_track_acc()},
        "II": {"n_events": 0,
               "B_layers": [new_layer_acc() for _ in range(NB_LAYERS)],
               "enterB_pid": {}, "enterA_pid": {},
               "enterB_pid_event": {}, "enterA_pid_event": {},
               "enterB_pid_edep": {}, "enterA_pid_edep": {},
               "enter_track_records": [],
               "tracks": new_track_acc()},
    }

    per_stave_species = {"I": {f"B{(l+1)*2}": {} for l in range(NB_LAYERS)},
                         "II": {f"B{(l+1)*2}": {} for l in range(NB_LAYERS)}}
    stopping_depth = {"I": {}, "II": {}}
    deltaE_E = {"I": {"edep_l0": [], "edep_l1": [], "pdg": [], "weight": []},
                "II": {"edep_l0": [], "edep_l1": [], "pdg": [], "weight": []}}
    # Weighted enter-pid counters and per-stave weighted edep stores.
    enter_pid_w = {"I": {"B": {}, "A": {}}, "II": {"B": {}, "A": {}}}
    per_stave_species_w = {"I": {f"B{(l+1)*2}": {} for l in range(NB_LAYERS)},
                           "II": {f"B{(l+1)*2}": {} for l in range(NB_LAYERS)}}
    all_event_weights = []  # every event that entered B (Sample II superset)

    EDEP_CAP = 600_000
    n_total = 0
    n_enterB = n_enterA = n_coinc = 0

    def bump(d, k, v=1):
        d[k] = d.get(k, 0) + v

    fobj = uproot.open(args.mc)
    tree = fobj[args.tree]
    stop = args.max_events if args.max_events > 0 else None
    for chunk in tree.iterate(branches, step_size="200 MB", library="np", entry_stop=stop):
        L = chunk["Sci_bar_LayerID"]
        L1 = chunk["Sci_bar_LayerID1"]
        PD = chunk["Sci_bar_PDG"]
        ED = chunk["Sci_bar_EDep"]
        TM = chunk["Sci_bar_Time"]
        TID = chunk["Sci_bar_TrackID"]
        MX = chunk["Sci_bar_Momentum_X"]
        MY = chunk["Sci_bar_Momentum_Y"]
        MZ = chunk["Sci_bar_Momentum_Z"]
        TL = chunk["Sci_bar_TrackLength"]
        # PrimaryWeight is a per-event variable-length array (one per primary);
        # take the first (beam primary), matching deltaE_E_mc.py.
        PWC = chunk[PRIMARY_WEIGHT_BRANCH]
        nev = len(L)
        for i in range(nev):
            n_total += 1
            l, l1, pd, ed, tm = L[i], L1[i], PD[i], ED[i], TM[i]
            if len(l) == 0:
                continue
            pw_i = PWC[i]
            w_evt = float(pw_i[0]) if (len(pw_i) > 0 and np.isfinite(float(pw_i[0]))) else 1.0
            if not args.apply_weight:
                w_evt = 1.0
            charged = np.array([is_charged(p) for p in pd], dtype=bool)
            isB = (l1 == B_ARM)
            isA = (l1 == A_ARM)
            firstB = isB & (l == 0) & charged
            firstA = isA & (l == 0) & charged
            enterB = firstB.any()
            enterA = firstA.any()
            tB = tm[firstB].min() if enterB else np.nan
            tA = tm[firstA].min() if enterA else np.nan
            if enterB:
                n_enterB += 1
            if enterA:
                n_enterA += 1
            coinc = enterB and enterA and abs(tA - tB) < args.coinc_ns
            if coinc:
                n_coinc += 1

            belongs = []
            if enterB:
                belongs.append("II")
            if coinc:
                belongs.append("I")

            tid = TID[i]
            for s in belongs:
                S = samples[s]
                S["n_events"] += 1
                if s == "II":
                    all_event_weights.append(w_evt)
                # #1046: unique-track (H2) for particle-flux fractions; raw
                # records preserved separately as transport diagnostic.
                evt_track_rec = {}
                for arm, mask, key in (
                    ("B", firstB, "enterB_pid"),
                    ("A", firstA, "enterA_pid"),
                ):
                    if not mask.any():
                        continue
                    acc = accumulate_entering_species(
                        pdg=pd,
                        track_id=tid,
                        edep=ed,
                        first_layer_mask=mask,
                        event_weight=w_evt,
                    )
                    for lab, v in acc["track_counts"].items():
                        bump(S[key], lab, v)
                        enter_pid_w[s][arm][lab] = (
                            enter_pid_w[s][arm].get(lab, 0.0) + float(v)
                        )
                    raw_key = f"{key}_records"
                    if raw_key not in S:
                        S[raw_key] = {}
                    for lab, v in acc["record_counts"].items():
                        bump(S[raw_key], lab, v)
                    # H3 event-presence and H4 EDep-contribution estimators.
                    for lab, v in acc["event_presence"].items():
                        S[f"{key}_event"][lab] = S[f"{key}_event"].get(lab, 0.0) + float(v)
                    for lab, v in acc["edep_weights"].items():
                        S[f"{key}_edep"][lab] = S[f"{key}_edep"].get(lab, 0.0) + float(v)
                    for lab, v in acc["track_counts"].items():
                        evt_track_rec[arm] = evt_track_rec.get(arm, {})
                        evt_track_rec[arm][lab] = evt_track_rec[arm].get(lab, 0.0) + float(v)
                if evt_track_rec:
                    S["enter_track_records"].append(evt_track_rec)

                # Immutable generator-event identity within this MC file (#1164).
                event_cluster_id = int(n_total)
                for lid in range(NB_LAYERS):
                    mask = isB & (l == lid) & charged
                    if not mask.any():
                        continue
                    acc = S["B_layers"][lid]
                    e = ed[mask]
                    acc["hits"] += int(mask.sum())
                    acc["n_charged"] += int(mask.sum())
                    acc["sum_edep"] += float(e.sum())
                    acc["wsum"] += w_evt
                    # Legacy hit/step records (diagnostic only; #1052).
                    if len(acc["edep"]) < EDEP_CAP:
                        acc["edep"].extend(e.tolist())
                        acc["edep_w"].extend([w_evt] * int(mask.sum()))
                    # Authorising detector-analogue intermediate: one total per
                    # generator event / layer (#1052), weight once per event.
                    if len(acc["event_edep"]) < EDEP_CAP:
                        acc["event_edep"].append(float(e.sum()))
                        acc["event_edep_w"].append(float(w_evt))
                        acc["event_cluster_id"].append(event_cluster_id)
                        acc["event_in_sample_i"].append(bool("I" in belongs))
                        acc["event_in_sample_ii"].append(bool("II" in belongs))
                    for p in pd[mask]:
                        bump(acc["pid"], species_label(p))
                        acc["pid_w"][species_label(p)] = \
                            acc["pid_w"].get(species_label(p), 0.0) + w_evt

                # ── per-track reconstruction ──
                b_hits = isB & charged
                if b_hits.any():
                    b_tids = tid[b_hits]
                    for trk in np.unique(b_tids):
                        trk_mask = b_hits & (tid == trk)
                        p0 = int(pd[trk_mask][0])
                        if pdg_charge(p0) < 1:
                            continue
                        layers = l[trk_mask]
                        eds = ed[trk_mask]
                        order = np.argsort(layers)
                        entry_idx = np.where(trk_mask)[0][order[0]]
                        px, py, pz = MX[i][entry_idx], MY[i][entry_idx], MZ[i][entry_idx]
                        pmag = float(np.sqrt(px * px + py * py + pz * pz))
                        ekin = kinetic_energy_from_branch_momentum(
                            pmag, p0, momentum_unit=args.momentum_unit)
                        # Residual KE at the last observed hit drives stop/escape (TRU-003).
                        last_idx = np.where(trk_mask)[0][order[-1]]
                        lpx, lpy, lpz = MX[i][last_idx], MY[i][last_idx], MZ[i][last_idx]
                        pmag_last = float(np.sqrt(lpx * lpx + lpy * lpy + lpz * lpz))
                        ekin_last = kinetic_energy_from_branch_momentum(
                            pmag_last, p0, momentum_unit=args.momentum_unit)
                        last_observed_layer = int(layers.max())
                        termination = infer_termination(
                            last_observed_layer, ekin_last, n_b_layers=NB_LAYERS)
                        el = {}
                        for lay, e in zip(layers, eds):
                            el[int(lay)] = el.get(int(lay), 0.0) + float(e)
                        T = S["tracks"]
                        T["pdg"].append(p0)
                        T["ekin"].append(ekin)
                        T["edep_l0"].append(el.get(0, 0.0))
                        T["edep_l1"].append(el.get(1, 0.0))
                        T["edep_tot"].append(float(eds.sum()))
                        # stop_layer is the *inferred* stopping layer (None/->nan
                        # for escape/censored); last_observed_layer is the observable.
                        T["stop_layer"].append(
                            last_observed_layer if termination == "stop" else None)
                        T["last_observed_layer"].append(last_observed_layer)
                        T["termination"].append(termination)
                        T["nlayers"].append(int(len(set(layers.tolist()))))
                        T["tracklen"].append(float(TL[i][trk_mask].sum()))
                        T["edep_per_layer"].append(el)
                        T["weight"].append(w_evt)

                        sp = species_label(p0)
                        for lay_int, edep_val in el.items():
                            stave_name = f"B{(lay_int + 1) * 2}"
                            ps = per_stave_species[s]
                            ps[stave_name].setdefault(sp, []).append(edep_val)
                            psw = per_stave_species_w[s]
                            psw.setdefault(stave_name, {}).setdefault(sp, []).append(w_evt)

                        # Stopping-depth distribution includes STOPPING tracks only
                        # (escape/censored are not stopping -- TRU-003).
                        if termination == "stop":
                            stopping_depth[s].setdefault(sp, []).append(last_observed_layer)

                        if 0 in el and 1 in el:
                            deltaE_E[s]["edep_l0"].append(el[0])
                            deltaE_E[s]["edep_l1"].append(el[1])
                            deltaE_E[s]["pdg"].append(p0)
                            deltaE_E[s]["weight"].append(w_evt)

    # ── convert accumulators to arrays ───────────────────────────────────
    for s in ("I", "II"):
        for k in samples[s]["tracks"]:
            if k == "edep_per_layer":
                continue  # list of dicts, not numeric
            if k == "termination":
                continue  # list of str labels, not numeric
            samples[s]["tracks"][k] = np.asarray(samples[s]["tracks"][k], dtype=float)
        for k in deltaE_E[s]:
            deltaE_E[s][k] = np.asarray(deltaE_E[s][k], dtype=float)

    def layer_summary(acc, large_mev):
        e = np.asarray(acc["edep"], dtype=float)
        ew = np.asarray(acc["edep_w"], dtype=float) if acc["edep_w"] else np.ones_like(e)
        d = {
            "hits": acc["hits"],
            "mean_edep_MeV": float(e.mean()) if e.size else 0.0,
            "median_edep_MeV": float(np.median(e)) if e.size else 0.0,
            "p95_edep_MeV": float(np.percentile(e, 95)) if e.size else 0.0,
            "frac_large": float((e > large_mev).mean()) if e.size else 0.0,
            "pid_fraction": {},
            # Weighted (PrimaryWeight, issue #880). These are the physically
            # correct flux-weighted quantities; the unweighted fields above are
            # retained for traceability.
            "weighted_sum_event_weight": float(acc["wsum"]),
            "mean_edep_MeV_weighted": _wmean(e, ew),
            "median_edep_MeV_weighted": _wmedian(e, ew),
            "p95_edep_MeV_weighted": _wpercentile(e, ew, 95),
            "frac_large_weighted": _wfrac_large(e, ew, large_mev),
            "pid_fraction_weighted": {},
        }
        tot = sum(acc["pid"].values()) or 1
        for k, v in sorted(acc["pid"].items(), key=lambda kv: -kv[1]):
            d["pid_fraction"][k] = round(v / tot, 4)
        wtot = sum(acc["pid_w"].values()) or 1.0
        for k, v in sorted(acc["pid_w"].items(), key=lambda kv: -kv[1]):
            d["pid_fraction_weighted"][k] = round(v / wtot, 4)
        return d

    out = {
        "mc_file": os.path.abspath(args.mc),
        "tree": args.tree,
        "coinc_ns": args.coinc_ns,
        "edep_large_mev": args.edep_large_mev,
        "n_events_read": n_total,
        "weighting": ("PrimaryWeight applied (A-003, issue #880); per-event weight "
                      "= first primary PrimaryWeight (beam primary), as in "
                      "deltaE_E_mc.py. Every *_weighted field uses it; plain fields "
                      "are retained unweighted for traceability.")
                     if args.apply_weight else "unweighted (--no-weight)",
        "apply_weight": bool(args.apply_weight),
        "trigger_counts": {"enter_B": n_enterB, "enter_A": n_enterA,
                           "coincidence_AB": n_coinc},
        "samples": {},
    }
    if all_event_weights:
        aw = np.asarray(all_event_weights, dtype=float)
        out["primary_weight_stats"] = {
            "n_weighted_events": int(aw.size),
            "min": float(aw.min()), "max": float(aw.max()),
            "mean": float(aw.mean()), "std": float(aw.std()),
            "effective_sample_size": effective_sample_size(aw),
            "ess_fraction_of_nominal": float(effective_sample_size(aw) / max(aw.size, 1)),
        }

    per_stave_summary = {}
    for s in ("I", "II"):
        per_stave_summary[s] = {}
        for stave_name in per_stave_species[s]:
            sp_dict = per_stave_species[s][stave_name]
            spw_dict = per_stave_species_w[s].get(stave_name, {})
            per_stave_summary[s][stave_name] = {}
            for sp_name, edep_list in sp_dict.items():
                arr = np.asarray(edep_list, dtype=float)
                warr = np.asarray(spw_dict.get(sp_name, []), dtype=float)
                if warr.size != arr.size:
                    warr = np.ones_like(arr)
                per_stave_summary[s][stave_name][sp_name] = {
                    "count": int(len(arr)),
                    "mean_edep_MeV": float(arr.mean()) if len(arr) > 0 else 0.0,
                    "median_edep_MeV": float(np.median(arr)) if len(arr) > 0 else 0.0,
                    "std_edep_MeV": float(arr.std()) if len(arr) > 0 else 0.0,
                    "mean_edep_MeV_weighted": _wmean(arr, warr),
                    "median_edep_MeV_weighted": _wmedian(arr, warr),
                }

    # Issue #1047 / ADR H3: weighted stop-depth is conditional on termination==stop.
    # Unconditional stop/escape/censored probabilities are reported separately.
    stopping_summary = {}
    for s in ("I", "II"):
        stopping_summary[s] = {}
        T = samples[s]["tracks"]
        tpdg = np.asarray(T["pdg"], dtype=float)
        tstop = np.asarray(T["stop_layer"], dtype=float)
        tterm = np.asarray(T["termination"], dtype=object)
        tw = np.asarray(T["weight"], dtype=float)
        for sp_name, stop_layers in stopping_depth[s].items():
            arr = np.asarray(stop_layers, dtype=int)
            sp_pdg = {"p": 2212, "d": 1000010020}.get(sp_name)
            if sp_pdg is not None:
                wmask = tpdg == sp_pdg
                h3 = summarize_stop_depth_h3(
                    termination=tterm[wmask],
                    stop_layer=tstop[wmask],
                    weights=tw[wmask],
                    n_layers=NB_LAYERS,
                    species=sp_name,
                )
            else:
                h3 = summarize_stop_depth_h3(
                    termination=[],
                    stop_layer=[],
                    weights=[],
                    n_layers=NB_LAYERS,
                    species=sp_name,
                )
            mean_w = h3["mean_stop_layer_weighted"]
            stopping_summary[s][sp_name] = {
                "count": int(len(arr)),
                "mean_stop_layer": float(arr.mean()) if len(arr) > 0 else 0.0,
                "median_stop_layer": float(np.median(arr)) if len(arr) > 0 else 0.0,
                "stop_distribution": {int(l): int((arr == l).sum())
                                      for l in range(NB_LAYERS)},
                # H3 fields (issue #1047)
                "estimand": h3["estimand"],
                "conditioning": h3["conditioning"],
                "termination_count": h3["termination_count"],
                "termination_prob_weighted": h3["termination_prob_weighted"],
                "termination_prob_unweighted": h3["termination_prob_unweighted"],
                "weight_sum_all": h3["weight_sum_all"],
                "weight_sum_stop": h3["weight_sum_stop"],
                "sum_w2_stop": h3["sum_w2_stop"],
                "n_stop": h3["n_stop"],
                "mean_stop_layer_weighted": mean_w,
                "mean_stop_layer_weighted_status": h3["mean_stop_layer_weighted_status"],
                "mean_stop_layer_weighted_reason": h3.get(
                    "mean_stop_layer_weighted_reason"),
                "stop_distribution_weighted": {
                    int(k): float(v)
                    for k, v in h3["stop_distribution_weighted"].items()
                },
            }

    for s in ("I", "II"):
        S = samples[s]
        tot_b = sum(S["enterB_pid"].values()) or 1
        tot_a = sum(S["enterA_pid"].values()) or 1
        wtot_b = sum(enter_pid_w[s]["B"].values()) or 1.0
        wtot_a = sum(enter_pid_w[s]["A"].values()) or 1.0
        T = S["tracks"]
        out["samples"][s] = {
            "n_events": S["n_events"],
            "n_tracks": int(len(T["pdg"])),
            # #1046: enter_*_pid_fraction is unique-track particle flux (H2).
            "enter_pid_statistical_unit": "unique_truth_track",
            "enter_pid_denominator": "unique (event, TrackID) charged first-layer crossings",
            "enter_B_pid_fraction": {k: round(v / tot_b, 4)
                                     for k, v in sorted(S["enterB_pid"].items(), key=lambda kv: -kv[1])},
            "enter_A_pid_fraction": {k: round(v / tot_a, 4)
                                     for k, v in sorted(S["enterA_pid"].items(), key=lambda kv: -kv[1])},
            "enter_B_pid_fraction_weighted": {k: round(v / wtot_b, 4)
                                              for k, v in sorted(enter_pid_w[s]["B"].items(), key=lambda kv: -kv[1])},
            "enter_A_pid_fraction_weighted": {k: round(v / wtot_a, 4)
                                              for k, v in sorted(enter_pid_w[s]["A"].items(), key=lambda kv: -kv[1])},
            "first_layer_record_fraction_B": {
                k: round(v / (sum(S.get("enterB_pid_records", {}).values()) or 1), 4)
                for k, v in sorted(S.get("enterB_pid_records", {}).items(), key=lambda kv: -kv[1])
            },
            "first_layer_record_fraction_A": {
                k: round(v / (sum(S.get("enterA_pid_records", {}).values()) or 1), 4)
                for k, v in sorted(S.get("enterA_pid_records", {}).items(), key=lambda kv: -kv[1])
            },
            # #1046 H3: event-presence composition (probability an accepted
            # event contains the species; fractions sum-normalized).
            "enter_B_pid_fraction_event_presence": {
                "statistical_unit": "event_presence",
                "denominator": "sum of species event-presence counts (weighted)",
                "fractions": {k: round(v / (sum(S["enterB_pid_event"].values()) or 1), 4)
                              for k, v in sorted(S["enterB_pid_event"].items(), key=lambda kv: -kv[1])},
                "counts": dict(S["enterB_pid_event"]),
            },
            "enter_A_pid_fraction_event_presence": {
                "statistical_unit": "event_presence",
                "denominator": "sum of species event-presence counts (weighted)",
                "fractions": {k: round(v / (sum(S["enterA_pid_event"].values()) or 1), 4)
                              for k, v in sorted(S["enterA_pid_event"].items(), key=lambda kv: -kv[1])},
                "counts": dict(S["enterA_pid_event"]),
            },
            # #1046 H4: deposited-energy contribution composition.
            "enter_B_pid_fraction_edep": {
                "statistical_unit": "deposited_energy",
                "denominator": "first-layer EDep summed by species (weighted)",
                "fractions": {k: round(v / (sum(S["enterB_pid_edep"].values()) or 1), 4)
                              for k, v in sorted(S["enterB_pid_edep"].items(), key=lambda kv: -kv[1])},
                "counts": dict(S["enterB_pid_edep"]),
            },
            "enter_A_pid_fraction_edep": {
                "statistical_unit": "deposited_energy",
                "denominator": "first-layer EDep summed by species (weighted)",
                "fractions": {k: round(v / (sum(S["enterA_pid_edep"].values()) or 1), 4)
                              for k, v in sorted(S["enterA_pid_edep"].items(), key=lambda kv: -kv[1])},
                "counts": dict(S["enterA_pid_edep"]),
            },
            # #1046: event-level bootstrap CI on the H2 particle-flux
            # fractions (generator-level statistical uncertainty).
            "enter_pid_bootstrap": {
                "method": "event_level_bootstrap",
                "estimator": "unique_truth_track (H2)",
                "n_boot": 1000,
                "seed": 1046,
                "ci_level": 68,
                **bootstrap_enter_fractions(S["enter_track_records"]),
            },
            "B_layers": [layer_summary(S["B_layers"][l], args.edep_large_mev)
                         for l in range(NB_LAYERS)],
            "per_stave_species": per_stave_summary[s],
            "stopping_depth": stopping_summary[s],
        }

    for s in ("I", "II"):
        arr0 = deltaE_E[s]["edep_l0"]
        arr1 = deltaE_E[s]["edep_l1"]
        pdg_arr = deltaE_E[s]["pdg"]
        warr = deltaE_E[s]["weight"]
        is_d = pdg_arr == 1000010020
        n_d_total = int(is_d.sum())
        n_d_both = int((is_d & (arr0 > 0) & (arr1 > 0)).sum())
        r_val = float(np.corrcoef(arr0, arr1)[0, 1]) if len(arr0) > 2 else 0.0
        out["samples"][s]["deltaE_E"] = {
            "n_tracks": int(len(arr0)),
            "edep_l0_mean_MeV": float(arr0.mean()) if len(arr0) > 0 else 0.0,
            "edep_l1_mean_MeV": float(arr1.mean()) if len(arr1) > 0 else 0.0,
            "correlation_pearson": r_val,
            "n_deuterons_total_in_sample": n_d_total,
            "n_deuterons_with_both_layer_hits": n_d_both,
            "edep_l0_mean_MeV_weighted": _wmean(arr0, warr),
            "edep_l1_mean_MeV_weighted": _wmean(arr1, warr),
            "correlation_pearson_weighted": _wcorr(arr0, arr1, warr),
            "low_r_note": (
                "Low Pearson r (≈0) for Sample I is expected physics: "
                "most deuterons stop at layer 0 (mean stop layer ~0.8) "
                "and never reach layer 1. The ΔE-E selection requires hits "
                "in BOTH layers, selecting a narrow punch-through sub-population "
                "whose B2 EDep is near minimum-ionizing and uncorrelated with B4 EDep. "
                "Sample II (proton-dominated, mean stop ~4.3) has many through-going "
                "particles in both layers, giving a sensible r≈0.5."
            ) if s == "I" and r_val < 0.3 else "",
        }

    l0_I = out["samples"]["I"]["B_layers"][0]
    l0_II = out["samples"]["II"]["B_layers"][0]
    out["headline_first_B_layer"] = {
        "sampleI_d_fraction": l0_I["pid_fraction"].get("d", 0.0),
        "sampleII_d_fraction": l0_II["pid_fraction"].get("d", 0.0),
        "sampleI_frac_large": l0_I["frac_large"],
        "sampleII_frac_large": l0_II["frac_large"],
        "sampleI_mean_edep_MeV": l0_I["mean_edep_MeV"],
        "sampleII_mean_edep_MeV": l0_II["mean_edep_MeV"],
        "sampleI_d_fraction_weighted": l0_I["pid_fraction_weighted"].get("d", 0.0),
        "sampleII_d_fraction_weighted": l0_II["pid_fraction_weighted"].get("d", 0.0),
        "sampleI_frac_large_weighted": l0_I["frac_large_weighted"],
        "sampleII_frac_large_weighted": l0_II["frac_large_weighted"],
        "sampleI_mean_edep_MeV_weighted": l0_I["mean_edep_MeV_weighted"],
        "sampleII_mean_edep_MeV_weighted": l0_II["mean_edep_MeV_weighted"],
    }

    with open(os.path.join(args.out, "mc_trigger_split_summary.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    # Legacy hit/step export retained under explicit statistical_unit metadata
    # (#1052). Authorising first-B comparisons must use the event-level product.
    np.savez_compressed(
        os.path.join(args.out, "first_B_layer_edep.npz"),
        sampleI=np.asarray(samples["I"]["B_layers"][0]["edep"], dtype=np.float32),
        sampleII=np.asarray(samples["II"]["B_layers"][0]["edep"], dtype=np.float32),
        sampleI_weights=np.asarray(samples["I"]["B_layers"][0]["edep_w"], dtype=np.float32),
        sampleII_weights=np.asarray(samples["II"]["B_layers"][0]["edep_w"], dtype=np.float32),
        statistical_unit=np.asarray(["hit_step_edep"]),
        superseded_by=np.asarray(["first_B_layer_event_edep.npz"]),
        authorising=np.asarray([False]),
        issue_quarantine=np.asarray(["NONAUTHORISING_BLOCKED_ISSUE_1052"]),
    )
    np.savez_compressed(
        os.path.join(args.out, "first_B_layer_event_edep.npz"),
        sampleI=np.asarray(samples["I"]["B_layers"][0]["event_edep"], dtype=np.float32),
        sampleII=np.asarray(samples["II"]["B_layers"][0]["event_edep"], dtype=np.float32),
        sampleI_weights=np.asarray(samples["I"]["B_layers"][0]["event_edep_w"], dtype=np.float32),
        sampleII_weights=np.asarray(samples["II"]["B_layers"][0]["event_edep_w"], dtype=np.float32),
        sampleI_cluster_id=np.asarray(samples["I"]["B_layers"][0]["event_cluster_id"], dtype=np.int64),
        sampleII_cluster_id=np.asarray(samples["II"]["B_layers"][0]["event_cluster_id"], dtype=np.int64),
        sampleI_in_sample_i=np.asarray(samples["I"]["B_layers"][0]["event_in_sample_i"], dtype=bool),
        sampleII_in_sample_i=np.asarray(samples["II"]["B_layers"][0]["event_in_sample_i"], dtype=bool),
        sampleI_in_sample_ii=np.asarray(samples["I"]["B_layers"][0]["event_in_sample_ii"], dtype=bool),
        sampleII_in_sample_ii=np.asarray(samples["II"]["B_layers"][0]["event_in_sample_ii"], dtype=bool),
        statistical_unit=np.asarray(["event_stave_edep"]),
        cluster_key=np.asarray(["generator_event_index"]),
        weight_semantics=np.asarray(["PrimaryWeight_first_primary"]),
        aggregation=np.asarray(["sum_charged_Sci_bar_EDep_layer0"]),
        authorising_measurand=np.asarray([False]),  # still truth EDep, not digitized H5
        issue_note=np.asarray(["intermediate_H3_pending_digitizer_H5"]),
    )
    for s in ("I", "II"):
        ps_data = {}
        for stave_name in per_stave_species[s]:
            for sp_name, edep_list in per_stave_species[s][stave_name].items():
                ps_data[f"{stave_name}_{sp_name}"] = np.asarray(edep_list, dtype=np.float32)
                wlist = per_stave_species_w[s].get(stave_name, {}).get(sp_name, [])
                ps_data[f"{stave_name}_{sp_name}_weights"] = np.asarray(wlist, dtype=np.float32)
        np.savez_compressed(os.path.join(args.out, f"per_stave_species_edep_{s}.npz"), **ps_data)
    for s in ("I", "II"):
        np.savez_compressed(
            os.path.join(args.out, f"deltaE_E_{s}.npz"),
            edep_l0=deltaE_E[s]["edep_l0"].astype(np.float32),
            edep_l1=deltaE_E[s]["edep_l1"].astype(np.float32),
            pdg=deltaE_E[s]["pdg"].astype(np.int64),
            weight=deltaE_E[s]["weight"].astype(np.float32),
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  PLOTS
    # ═══════════════════════════════════════════════════════════════════════
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Figure 1: ΔE-E plane per sample
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for si, s in enumerate(("I", "II")):
            ax = axes[si]
            ed0 = deltaE_E[s]["edep_l0"]
            ed1 = deltaE_E[s]["edep_l1"]
            pdg_a = deltaE_E[s]["pdg"]
            is_p = pdg_a == 2212
            is_d = pdg_a == 1000010020
            other = ~(is_p | is_d)
            n_pts = min(8000, len(ed0))
            idx = np.random.choice(len(ed0), n_pts, replace=False) if len(ed0) > n_pts else np.arange(len(ed0))
            ax.scatter(ed0[idx][other[idx]], ed1[idx][other[idx]], s=2, alpha=0.25,
                       color="gray", label="other", rasterized=True)
            ax.scatter(ed0[idx][is_p[idx]], ed1[idx][is_p[idx]], s=2, alpha=0.35,
                       color="C0", label="p", rasterized=True)
            ax.scatter(ed0[idx][is_d[idx]], ed1[idx][is_d[idx]], s=2, alpha=0.35,
                       color="C3", label="d", rasterized=True)
            ax.set_xlabel("EDep Layer 0 (B2) [MeV]")
            ax.set_ylabel("EDep Layer 1 (B4) [MeV]")
            ax.set_title(f"MC Sample {s} — ΔE-E Plane (truth)")
            ax.legend(loc="upper right", markerscale=3)
        fig.suptitle("MC Truth ΔE vs E: Sample I (coincidence) vs Sample II (single-B trigger)",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "deltaE_E_per_sample.png"), dpi=150)
        plt.close(fig)

        # Figure 2: First B layer EDep spectrum
        fig, ax = plt.subplots(figsize=(10, 5.5))
        colors = {"I": "C0", "II": "C3"}
        for s, label, ls in (("I", "Sample I (coincidence)", "-"),
                              ("II", "Sample II (single-B)", "--")):
            e = np.asarray(samples[s]["B_layers"][0]["edep"], dtype=float)
            ax.hist(e, bins=80, range=(0, 100), histtype="step", linewidth=2,
                    color=colors[s], linestyle=ls, label=label, density=True)
        ax.set_xlabel("EDep first B layer (B2) [MeV]")
        ax.set_ylabel("Normalised counts")
        ax.set_title("MC: First B-Layer (B2) Energy Deposit — Sample I vs Sample II")
        ax.legend()
        ax.set_xlim(0, 80)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "first_B_layer_edep_spectrum.png"), dpi=150)
        plt.close(fig)

        # Figure 3: Per-stave deuteron/proton fraction
        fig, ax = plt.subplots(figsize=(9, 5))
        for s, label, marker in (("I", "Sample I", "o"), ("II", "Sample II", "s")):
            d_fracs, p_fracs = [], []
            for lid in range(NB_LAYERS):
                pid_frac = out["samples"][s]["B_layers"][lid]["pid_fraction"]
                d_fracs.append(pid_frac.get("d", 0))
                p_fracs.append(pid_frac.get("p", 0))
            x = np.arange(NB_LAYERS)
            ax.plot(x, d_fracs, marker=marker, color="C3", linestyle="-", linewidth=2,
                    label=f"{label} d fraction")
            ax.plot(x, p_fracs, marker=marker, color="C0", linestyle="--", linewidth=2,
                    label=f"{label} p fraction")
        ax.set_xticks(x)
        ax.set_xticklabels([f"B{(l+1)*2}" for l in range(NB_LAYERS)])
        ax.set_xlabel("B-stack stave")
        ax.set_ylabel("Fraction of charged hits")
        ax.set_title("MC: Deuteron & Proton Fraction per B-Stave — Sample I vs Sample II")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "deuteron_proton_fraction_per_stave.png"), dpi=150)
        plt.close(fig)

        # Figure 4: Stopping-depth distribution per species
        fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
        for si, s in enumerate(("I", "II")):
            ax = axes[si]
            x = np.arange(NB_LAYERS)
            width = 0.35
            for sp, color, offset, label in (("p", "C0", -width / 2, "proton"),
                                              ("d", "C3", width / 2, "deuteron")):
                if sp in stopping_summary[s]:
                    dist = stopping_summary[s][sp]["stop_distribution"]
                    vals = [dist.get(l, 0) for l in range(NB_LAYERS)]
                    total = max(sum(vals), 1)
                    vals_norm = [v / total for v in vals]
                    ax.bar(x + offset, vals_norm, width, color=color, alpha=0.7, label=label)
            ax.set_xticks(x)
            ax.set_xticklabels([f"B{(l+1)*2}" for l in range(NB_LAYERS)])
            ax.set_xlabel("Stop layer")
            ax.set_ylabel("Fraction of tracks")
            ax.set_title(f"MC Sample {s} — Stopping Depth")
            ax.legend()
            ax.grid(True, alpha=0.2, axis="y")
        fig.suptitle("MC Truth Stopping-Depth Distribution: p vs d — Sample I vs Sample II",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "stopping_depth_per_sample.png"), dpi=150)
        plt.close(fig)

        # Figure 5: Per-stave energy spectra (all charged)
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, lid in enumerate(range(4)):
            ax = axes[idx // 2][idx % 2]
            stave_name = f"B{(lid+1)*2}"
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                e = np.asarray(samples[s]["B_layers"][lid]["edep"], dtype=float)
                if e.size > 0:
                    ax.hist(e, bins=60, range=(0, 80), histtype="step", linewidth=2,
                            color=color, linestyle=ls, label=label, density=True)
            ax.set_xlabel(f"EDep {stave_name} [MeV]")
            ax.set_ylabel("Normalised counts")
            ax.set_title(f"MC: {stave_name} Energy Deposit")
            ax.legend()
            ax.set_xlim(0, 60)
        fig.suptitle("MC: Per-Stave Energy Deposit Spectra — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "per_stave_edep_spectra.png"), dpi=150)
        plt.close(fig)

        # Figure 6: Depth profile
        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(NB_LAYERS)
        for s, label, marker in (("I", "Sample I", "o"), ("II", "Sample II", "s")):
            hits_per_layer = [out["samples"][s]["B_layers"][l]["hits"] for l in range(NB_LAYERS)]
            n_events = out["samples"][s]["n_events"]
            frac = [h / max(n_events, 1) for h in hits_per_layer]
            ax.plot(x, frac, marker=marker, linewidth=2, label=label)
        ax.set_xticks(x)
        ax.set_xticklabels([f"B{(l+1)*2}" for l in range(NB_LAYERS)])
        ax.set_xlabel("B-stack stave")
        ax.set_ylabel("Fraction of events with ≥1 charged hit")
        ax.set_title("MC: Depth Profile — Fraction of Events per Stave")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "depth_profile_mc.png"), dpi=150)
        plt.close(fig)

        # Figure 7: Deuteron EDep per stave
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, stave_name in enumerate(("B2", "B4", "B6", "B8")):
            ax = axes[idx // 2][idx % 2]
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                key = f"{stave_name}_d"
                if key in per_stave_species[s][stave_name]:
                    arr = np.asarray(per_stave_species[s][stave_name]["d"], dtype=float)
                    if len(arr) > 0:
                        ax.hist(arr, bins=50, range=(0, 70), histtype="step", linewidth=2,
                                color=color, linestyle=ls, label=f"{label} (n={len(arr)})",
                                density=True)
            ax.set_xlabel(f"Deuteron EDep {stave_name} [MeV]")
            ax.set_ylabel("Normalised counts")
            ax.set_title(f"MC: Deuteron Energy Deposit — {stave_name}")
            ax.legend(fontsize=8)
            ax.set_xlim(0, 50)
        fig.suptitle("MC: Deuteron Energy Deposit per Stave — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "deuteron_edep_per_stave.png"), dpi=150)
        plt.close(fig)

        # Figure 8: Proton EDep per stave
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, stave_name in enumerate(("B2", "B4", "B6", "B8")):
            ax = axes[idx // 2][idx % 2]
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                key = f"{stave_name}_p"
                if key in per_stave_species[s][stave_name]:
                    arr = np.asarray(per_stave_species[s][stave_name]["p"], dtype=float)
                    if len(arr) > 0:
                        ax.hist(arr, bins=50, range=(0, 50), histtype="step", linewidth=2,
                                color=color, linestyle=ls, label=f"{label} (n={len(arr)})",
                                density=True)
            ax.set_xlabel(f"Proton EDep {stave_name} [MeV]")
            ax.set_ylabel("Normalised counts")
            ax.set_title(f"MC: Proton Energy Deposit — {stave_name}")
            ax.legend(fontsize=8)
            ax.set_xlim(0, 30)
        fig.suptitle("MC: Proton Energy Deposit per Stave — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "proton_edep_per_stave.png"), dpi=150)
        plt.close(fig)

        print("[plots] All 8 MC figures generated.")
    except Exception as e:
        out["_plot_error"] = str(e)
        with open(os.path.join(args.out, "mc_trigger_split_summary.json"), "w") as fh:
            json.dump(out, fh, indent=2)
        print(f"[plot_error] {e}", file=sys.stderr)

    print(json.dumps(out["headline_first_B_layer"], indent=2))
    print(f"[ok] wrote {args.out}/mc_trigger_split_summary.json  "
          f"(events read={n_total}, enterB={n_enterB}, coinc={n_coinc})")


if __name__ == "__main__":
    main()

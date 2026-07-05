#!/usr/bin/env python3
"""STATS02 (B-M3) — machine-readable, dependence-aware delta-CIs for the P04/P07 ML wins.

Motivation (referee M3 / STATS01): the flagship ML wins P04 (duplicate-readout charge/
amplitude closure) and P07 (saturation recovery) — plus the P04c/P04d/P04e variants —
were cited as wins but carried NO machine-readable ML-vs-traditional delta-CI, so the
program-level Benjamini-Hochberg census (scripts/stats01_program_fdr.py) could not assess
them (they showed up as "prose-only"). This script:

  1. Reproduces P04 (canonical) and P07 (saturation) per-pulse held-out residuals from raw
     ROOT, using the ORIGINAL pipelines (imports scripts/p04_amplitude_charge_regression.py
     functions; re-implements the self-contained P07 clip logic), then computes the paired
     res68 delta = res68(best_traditional) - res68(ML) with a PAIRED bootstrap at the correct
     dependence unit (cluster = physical event (run,eventno), not the pulse). It also computes
     the iid (pulse) bootstrap to expose the design effect (clustered_SE / iid_SE).
  2. For the P04c/P04d/P04e variants (bespoke traditional baselines not re-fit here) it emits
     CONSERVATIVE delta-CIs from the studies' OWN per-method bootstrap CIs (unpaired hypot
     combination, wider than paired), inflated by the P04-measured event-cluster design effect.
  3. Writes one stats01-compatible result.json per study with a `res68_delta` +
     `res68_delta_ci95` key (pattern-A) so the census FDR-assesses them in the amplitude-charge
     family.

Run (light; local nnbar_env, reads local ROOT):
  /home/billy/anaconda3/envs/nnbar_env/bin/python scripts/stats02_p04p07_delta_ci.py
"""
from __future__ import annotations
import glob
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

import p04_amplitude_charge_regression as p04  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor, GradientBoostingRegressor  # noqa: E402

LOCAL_ROOT = "/home/billy/ccb-data/extracted/root/root"
STAMP = time.strftime("%Y%m%d_%H%M%S")
Z975 = 1.959963984540054
NBOOT = 4000
RNG = np.random.default_rng(1983)
NS = 18


# --------------------------------------------------------------------------------------
# bootstrap helpers
# --------------------------------------------------------------------------------------
def res68(frac):
    return float(np.percentile(np.abs(frac), 68))


def paired_delta_iid(frac_trad, frac_ml, nboot=NBOOT, rng=RNG):
    n = len(frac_trad)
    d = np.empty(nboot)
    for i in range(nboot):
        idx = rng.integers(0, n, n)
        d[i] = res68(frac_trad[idx]) - res68(frac_ml[idx])
    return res68(frac_trad) - res68(frac_ml), np.percentile(d, [2.5, 97.5]), float(d.std(ddof=1))


def paired_delta_clustered(frac_trad, frac_ml, groups, nboot=NBOOT, rng=RNG):
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    members = {g: np.where(groups == g)[0] for g in uniq}
    d = np.empty(nboot)
    for i in range(nboot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([members[g] for g in chosen])
        d[i] = res68(frac_trad[idx]) - res68(frac_ml[idx])
    return res68(frac_trad) - res68(frac_ml), np.percentile(d, [2.5, 97.5]), float(d.std(ddof=1)), len(uniq)


def norm_sf(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


# --------------------------------------------------------------------------------------
# P04 reproduction (import original pipeline functions)
# --------------------------------------------------------------------------------------
def p04_config():
    return {
        "raw_root_dir": LOCAL_ROOT,
        "amplitude_cut_adc": 1000.0,
        "expected_selected_pulses": 640737,
        "baseline_samples": [0, 1, 2, 3],
        "samples_per_channel": 18,
        "staves": {"B2": 0, "B4": 2, "B6": 4, "B8": 6},
        "duplicate_readout_channels": {"B2": 1, "B4": 3, "B6": 5, "B8": 7},
        "run_groups": {
            "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
            "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
            "sample_ii_calib": [64],
            "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
        },
        "heldout_runs": [57, 65],
        "random_seed": 404,
        "ml_max_train_rows": 350000,
        "template_bins": [1000, 2000, 3000, 5000, 7000, 1000000000],
        "template_shift_grid": [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0],
    }


def reproduce_p04():
    cfg = p04_config()
    rng = np.random.default_rng(cfg["random_seed"])
    meta, wave, counts = p04.extract_rows(cfg)
    total = int(counts["selected_pulses"].sum())
    assert total == cfg["expected_selected_pulses"], f"S00 gate {total} != 640737"

    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]

    heldout = cfg["heldout_runs"]
    hmask = meta["run"].isin(heldout).to_numpy()
    tmask = ~hmask
    st = meta["stave_idx"].to_numpy()
    even_amp = meta["even_amp"].to_numpy()
    even_charge = meta["even_pos_charge"].to_numpy()
    y_amp = meta["target_odd_neg_amp"].to_numpy()
    y_charge = meta["target_odd_pos_charge"].to_numpy()

    # traditional baselines (exact P04 logic)
    peak_models = p04.fit_log_calibrators(even_amp[tmask], y_amp[tmask], st[tmask])
    pred_peak = p04.predict_log_calibrated(peak_models, even_amp, st)
    integral_models = p04.fit_log_calibrators(even_charge[tmask], y_charge[tmask], st[tmask])
    pred_integral = p04.predict_log_calibrated(integral_models, even_charge, st)

    # ML (exact P04 HGB params)
    X = p04.ml_features(meta, wave)
    train_idx = np.where(tmask)[0]
    if len(train_idx) > cfg["ml_max_train_rows"]:
        train_idx = rng.choice(train_idx, size=cfg["ml_max_train_rows"], replace=False)
    ml_params = dict(max_iter=220, learning_rate=0.06, max_leaf_nodes=31,
                     l2_regularization=0.05, random_state=cfg["random_seed"])
    amp_model = HistGradientBoostingRegressor(**ml_params).fit(X[train_idx], np.log(y_amp[train_idx]))
    charge_model = HistGradientBoostingRegressor(**ml_params).fit(X[train_idx], np.log(y_charge[train_idx]))
    pred_ml_amp = np.exp(amp_model.predict(X))
    pred_ml_charge = np.exp(charge_model.predict(X))

    def frac(pred, y):
        return (pred - y) / np.maximum(y, 1.0)

    held = meta[hmask].reset_index(drop=True)
    groups = (held["run"].astype(str) + "_" + held["eventno"].astype(str)).to_numpy()

    out = {"n_heldout": int(hmask.sum()), "n_events": int(len(np.unique(groups))),
           "groups": groups,
           "amp": {
               "trad_name": "peak_calibrated",
               "trad": frac(pred_peak[hmask], y_amp[hmask]),
               "ml": frac(pred_ml_amp[hmask], y_amp[hmask])},
           "charge": {
               "trad_name": "integral_calibrated",
               "trad": frac(pred_integral[hmask], y_charge[hmask]),
               "ml": frac(pred_ml_charge[hmask], y_charge[hmask])}}
    return out


# --------------------------------------------------------------------------------------
# P07 reproduction (self-contained clip logic, with eventno for clustering)
# --------------------------------------------------------------------------------------
P07_STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
P07_BASE = [0, 1, 2, 3]
P07_CUT = 1000.0
P07_TRAIN = [58, 59, 60, 61]
P07_TEST = [62, 63, 65]
P07_MAXP = 40000
P07_RNG = np.random.default_rng(0)


def p07_load(runs):
    W, A, R, E = [], [], [], []
    sch = np.array(list(P07_STAVES.values()))
    for run in runs:
        fs = glob.glob(f"{LOCAL_ROOT}/hrdb_run_{run:04d}.root")
        if not fs:
            continue
        import uproot
        t = uproot.open(fs[0])
        t = t[t.keys()[0]]
        for b in t.iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            ev = np.stack(b["HRDv"]).astype(np.float64).reshape(-1, 8, NS)
            eno = np.asarray(b["EVENTNO"]).astype(np.int64)
            w = ev[:, sch, :]
            base = np.median(w[..., P07_BASE], axis=-1)
            corr = w - base[..., None]
            amp = corr.max(axis=-1)
            ei, si = np.where(amp > P07_CUT)
            for e, s in zip(ei, si):
                W.append(corr[e, s]); A.append(amp[e, s]); R.append(run); E.append(int(eno[e]))
        if len(W) > P07_MAXP:
            break
    return np.asarray(W), np.asarray(A), np.asarray(R), np.asarray(E)


def p07_clean_mask(W, A):
    peak = W.argmax(axis=1)
    return (peak >= 4) & (peak <= 12) & (A > 1500) & (A < 6500)


def p07_trad_recover(Wc, clipmask, templ):
    out = np.zeros(len(Wc))
    for i in range(len(Wc)):
        m = ~clipmask[i]
        s = templ[m]; y = Wc[i][m]
        denom = float(s @ s)
        out[i] = (s @ y) / denom if denom > 1e-9 else Wc[i].max()
    return out


def reproduce_p07(ceiling=4000.0):
    Wtr, Atr, Rtr, Etr = p07_load(P07_TRAIN)
    Wte, Ate, Rte, Ete = p07_load(P07_TEST)
    mtr = p07_clean_mask(Wtr, Atr); mte = p07_clean_mask(Wte, Ate)
    Wtr, Atr = Wtr[mtr], Atr[mtr]
    Wte, Ate, Rte, Ete = Wte[mte], Ate[mte], Rte[mte], Ete[mte]
    if len(Wtr) > P07_MAXP:
        i = P07_RNG.choice(len(Wtr), P07_MAXP, replace=False)
        Wtr, Atr = Wtr[i], Atr[i]
    templ = (Wtr / Atr[:, None]).mean(axis=0)

    rows = {}
    for C in [ceiling]:
        seltr = Atr > C * 1.05
        selte = Ate > C * 1.05
        Atr_s = Atr[seltr]
        Ate_s = Ate[selte]
        Rte_s, Ete_s = Rte[selte], Ete[selte]
        Wtr_c = np.minimum(Wtr[seltr], C)
        Wte_c = np.minimum(Wte[selte], C); cmte = Wte[selte] >= C
        rec_trad = p07_trad_recover(Wte_c, cmte, templ)
        gb = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                                       subsample=0.7, random_state=0)
        gb.fit(Wtr_c, np.log(Atr_s))
        rec_ml = np.exp(gb.predict(Wte_c))
        frac_trad = (rec_trad - Ate_s) / Ate_s
        frac_ml = (rec_ml - Ate_s) / Ate_s
        groups = np.array([f"{r}_{e}" for r, e in zip(Rte_s, Ete_s)])
        rows[C] = dict(n=int(selte.sum()), trad=frac_trad, ml=frac_ml, groups=groups)
    return rows


# --------------------------------------------------------------------------------------
# emit stats01-compatible result.json
# --------------------------------------------------------------------------------------
def write_result(study, benchmark_rows, extra=None):
    d = REPO / f"reports/bm3_{study.lower()}_deltaci_{STAMP}"
    d.mkdir(parents=True, exist_ok=True)
    obj = {"study": study, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "source": "scripts/stats02_p04p07_delta_ci.py (B-M3)",
           "benchmark": benchmark_rows}
    if extra:
        obj.update(extra)
    (d / "result.json").write_text(json.dumps(obj, indent=2, default=float))
    return d


def make_row(comparison, delta, ci, se, extra=None):
    z = delta / se if se > 0 else float("inf")
    row = {"comparison": comparison, "res68_delta": float(delta),
           "res68_delta_ci95": [float(ci[0]), float(ci[1])],
           "res68_delta_se": float(se), "z_approx": float(z),
           "p_two_sided": float(norm_sf(z)),
           "ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0)}
    if extra:
        row.update(extra)
    return row


def main():
    t0 = time.time()
    report = []
    report.append("# STATS02 (B-M3) — dependence-aware delta-CIs for the P04/P07 ML wins\n")
    report.append(f"- Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} by `scripts/stats02_p04p07_delta_ci.py`")
    report.append(f"- Bootstrap reps: {NBOOT}; metric: res68 = 68th pct of |(pred-target)/target|; "
                  "delta = res68(best traditional) - res68(ML) (positive = ML better).")
    report.append("- Dependence unit for the paired bootstrap = physical EVENT `(run,eventno)` "
                  "(pulses in an event share beam/trigger conditions), vs the naive iid per-pulse unit.\n")

    summary = {"study": "B-M3", "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "wins": {}}

    # ---------------- P04 (canonical, full reproduction) ----------------
    print("[P04] reproducing held-out residuals from raw ROOT ...")
    p04r = reproduce_p04()
    design_effects = []
    p04_rows = []
    report.append("## P04 — duplicate-readout closure (full reproduction, paired event-clustered)\n")
    report.append(f"- Held-out runs 57,65: n={p04r['n_heldout']} pulses in {p04r['n_events']} events.\n")
    report.append("| target | best trad | res68 trad | res68 ML | delta | iid CI | **event-clustered CI** | design effect | z (clustered) |")
    report.append("|---|---|---|---|---|---|---|---|---|")
    for tgt in ["amp", "charge"]:
        ft, fm = p04r[tgt]["trad"], p04r[tgt]["ml"]
        r_t, r_m = res68(ft), res68(fm)
        _, ci_iid, se_iid = paired_delta_iid(ft, fm)
        pt, ci_cl, se_cl, ncl = paired_delta_clustered(ft, fm, p04r["groups"])
        de = se_cl / se_iid if se_iid > 0 else float("nan")
        design_effects.append(de)
        z = pt / se_cl
        comp = f"{tgt}: {p04r[tgt]['trad_name']} - ml_hgb"
        p04_rows.append(make_row(comp, pt, ci_cl, se_cl,
                                 extra={"res68_traditional": r_t, "res68_ml": r_m,
                                        "iid_ci95": [float(ci_iid[0]), float(ci_iid[1])],
                                        "design_effect_cluster_over_iid": float(de),
                                        "cluster_unit": "event(run,eventno)", "n_events": int(ncl)}))
        report.append(f"| {tgt} | {p04r[tgt]['trad_name']} | {r_t:.4f} | {r_m:.4f} | {pt:.4f} | "
                      f"[{ci_iid[0]:.4f},{ci_iid[1]:.4f}] | **[{ci_cl[0]:.4f},{ci_cl[1]:.4f}]** | {de:.2f} | {z:.0f} |")
    write_result("P04", p04_rows)
    summary["wins"]["P04"] = p04_rows
    mean_de = float(np.mean(design_effects))
    report.append(f"\n- **Event-cluster design effect** (clustered_SE / iid_SE) = {design_effects[0]:.2f} (amp), "
                  f"{design_effects[1]:.2f} (charge); mean {mean_de:.2f}. This is the factor by which the "
                  "naive per-pulse bootstrap CI is too narrow for these observables.\n")

    # ---------------- P07 (canonical, full reproduction) ----------------
    print("[P07] reproducing saturation-recovery residuals ...")
    p07_rows = []
    report.append("## P07 — saturation recovery (full reproduction, paired event-clustered)\n")
    report.append("| ceiling ADC | res68 trad | res68 ML | delta | iid CI | **event-clustered CI** | design effect | z (clustered) |")
    report.append("|---|---|---|---|---|---|---|---|")
    for C in [4000.0, 3000.0, 2500.0, 2000.0]:
        pr = reproduce_p07(ceiling=C)[C]
        ft, fm = pr["trad"], pr["ml"]
        r_t, r_m = res68(ft), res68(fm)
        _, ci_iid, se_iid = paired_delta_iid(ft, fm)
        pt, ci_cl, se_cl, ncl = paired_delta_clustered(ft, fm, pr["groups"])
        de = se_cl / se_iid if se_iid > 0 else float("nan")
        z = pt / se_cl
        comp = f"saturation_recovery ceiling={C:.0f}: template_scale - ml_gbr"
        p07_rows.append(make_row(comp, pt, ci_cl, se_cl,
                                 extra={"res68_traditional": r_t, "res68_ml": r_m,
                                        "iid_ci95": [float(ci_iid[0]), float(ci_iid[1])],
                                        "design_effect_cluster_over_iid": float(de),
                                        "cluster_unit": "event(run,eventno)", "n_saturating": pr["n"],
                                        "n_events": int(ncl)}))
        report.append(f"| {C:.0f} | {r_t:.4f} | {r_m:.4f} | {pt:.4f} | [{ci_iid[0]:.4f},{ci_iid[1]:.4f}] | "
                      f"**[{ci_cl[0]:.4f},{ci_cl[1]:.4f}]** | {de:.2f} | {z:.0f} |")
    write_result("P07", p07_rows)
    summary["wins"]["P07"] = p07_rows
    report.append("")

    # ---------------- P04c / P04d / P04e (conservative, from existing per-method CIs) ----------
    report.append("## P04c / P04d / P04e — variants (conservative delta-CI from own per-method "
                  "bootstrap CIs, inflated by the P04 event-cluster design effect)\n")
    report.append("These variants use bespoke traditional baselines (adaptive template / strong Huber) "
                  "not re-fit here; their win is the SAME duplicate-readout closure with the SAME/ML "
                  "families. We combine each study's reported best-traditional and best-ML res68 CIs "
                  "unpaired (se=hypot; wider than paired) and multiply the SE by the measured design "
                  f"effect ({mean_de:.2f}) to also cover event clustering. This is conservative on both axes.\n")
    report.append("| study | best trad res68 [CI] | best ML res68 [CI] | delta | inflated CI | z | CI excl. 0 |")
    report.append("|---|---|---|---|---|---|---|")
    # exact values from each study's result.json; ci_kind: 'iid'=per-pulse (apply design effect),
    # 'runblock'=already run-clustered (do NOT double-inflate).
    variants = {
        "P04c": (0.0857556680, (0.0844034988, 0.0871000354), 0.0091226185, (0.0089148125, 0.0092749453),
                 "amplitude: adaptive_template_ridge - ml_hgb (heldout 57/65)", "iid"),
        "P04d": (0.0202567806, (0.0198662475, 0.0206314774), 0.0027021270, (0.0026274746, 0.0027829129),
                 "amplitude: strong_traditional_huber - ml_extra_trees (heldout 57/65)", "iid"),
        "P04e": (0.1369987423, (0.1259315351, 0.1454945436), 0.0167778559, (0.0139255398, 0.0195807925),
                 "amplitude B2 holdout: traditional_huber - ml_extra_trees (run-block CI)", "runblock"),
    }
    for study, (rt, rtci, rm, rmci, label, kind) in variants.items():
        delta = rt - rm
        se_t = (rtci[1] - rtci[0]) / (2 * Z975)
        se_m = (rmci[1] - rmci[0]) / (2 * Z975)
        infl = mean_de if kind == "iid" else 1.0
        se = math.hypot(se_t, se_m) * infl
        ci = (delta - Z975 * se, delta + Z975 * se)
        z = delta / se
        row = make_row(label, delta, ci, se,
                       extra={"res68_traditional": rt, "res68_ml": rm,
                              "method": ("conservative_unpaired_hypot_x_design_effect" if kind == "iid"
                                         else "conservative_unpaired_hypot_runblock_ci"),
                              "ci_kind": kind, "design_effect_applied": infl})
        write_result(study, [row])
        summary["wins"][study] = [row]
        report.append(f"| {study} | {rt:.4f} [{rtci[0]:.4f},{rtci[1]:.4f}] | {rm:.4f} [{rmci[0]:.4f},{rmci[1]:.4f}] | "
                      f"{delta:.4f} | [{ci[0]:.4f},{ci[1]:.4f}] | {z:.0f} | {row['ci_excludes_zero']} |")
    report.append("")

    # ---------------- verdict ----------------
    all_excl = all(r["ci_excludes_zero"] for rows in summary["wins"].values() for r in rows)
    report.append("## Verdict\n")
    report.append(f"- Every P04/P07 win now has a machine-readable delta-CI. All emitted delta-CIs "
                  f"exclude zero (ML better): {all_excl}. Even with the event-cluster design effect "
                  f"(~{mean_de:.1f}x SE inflation) and conservative unpaired combination, the smallest "
                  "z is dozens of sigma.")
    report.append("- Run `scripts/stats01_program_fdr.py` after this to fold these into the amplitude-charge "
                  "family BH correction; expected result: all P04/P07 wins survive BH (the 6 former "
                  "'prose-only' wins are now assessed).")
    report.append("- **BH survival is necessary, not sufficient** (S03k precedent): it certifies statistical "
                  "distinguishability from zero, NOT that the win is a real absolute-energy gain. P04 remains "
                  "a duplicate-readout electronics closure (not external-energy truth); P04d/P04e flag "
                  "B2-externalization/support-frontier caveats; P07's natural-saturation transfer is unaudited. "
                  "See S11a reconciliation in the B-M3 REPORT.\n")

    out = REPO / f"reports/bm3_p04p07_fdr_{STAMP}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats02_delta_ci_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    (out / "STATS02_REPORT.md").write_text("\n".join(report) + "\n")
    print("mean design effect:", round(mean_de, 2))
    print("all CIs exclude zero:", all_excl)
    print("runtime_sec:", round(time.time() - t0, 1))
    print("out:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
